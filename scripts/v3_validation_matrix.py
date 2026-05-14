"""
V3 validation matrix for POST /api/org-tree (Step 3 verification).
Run with cwd = repo root; dev server on 127.0.0.1:8000.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from server.auth import create_access_token

ORG = "58ea7177-3d39-49ad-abe6-8d1dbac7f1da"
SA_UID = "2e0d94bd-391f-475e-aacc-0e28b5c488e2"
BASE = "http://127.0.0.1:8000/api/org-tree"

TOKEN = create_access_token({"sub": SA_UID, "org_id": ORG, "role": "SUPER_ADMIN"})


def post(body: dict) -> tuple[int, str]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        BASE,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


def curl_line(body: dict) -> str:
    j = json.dumps(body, separators=(",", ":"))
    return (
        f'curl -s -i -X POST {BASE} '
        f'-H "Authorization: Bearer <SUPER_ADMIN_TOKEN>" '
        f'-H "Content-Type: application/json" '
        f"-d '{j}'"
    )


def main() -> None:
    con = sqlite3.connect(os.path.join(_REPO, "manufacturing_os.db"))
    cur = con.cursor()
    cur.execute(
        "SELECT id FROM org_nodes WHERE org_id = ? AND node_type = 'PLANT' LIMIT 1",
        (ORG,),
    )
    row = cur.fetchone()
    con.close()
    if not row:
        raise SystemExit("No PLANT org node for org " + ORG)
    plant_id = row[0]

    results: list[tuple[str, int, str, dict, int, str]] = []

    def run(case: str, expect: int, body: dict) -> tuple[int, str]:
        status, body_text = post(body)
        results.append((case, expect, curl_line(body), body, status, body_text))
        return status, body_text

    def parse_id(body_text: str) -> str | None:
        if not body_text.strip().startswith("{"):
            return None
        try:
            return json.loads(body_text)["id"]
        except (json.JSONDecodeError, KeyError):
            return None

    # --- 1 ---
    st, txt = run("1", 200, {"node_type": "REGION", "name": "V3TestRegionRoot", "parent_id": ORG})
    region_root_id = parse_id(txt) if st == 200 else None
    if not region_root_id:
        raise SystemExit(f"Case 1 failed: status={st} body={txt[:200]}")

    # --- 2 ---
    run("2", 400, {"node_type": "REGION", "name": "V3TestRegionUnderPlant", "parent_id": plant_id})

    # --- 3 ---
    st, txt = run("3", 200, {"node_type": "CORPORATE_FUNCTION", "name": "V3TestCorpRoot", "parent_id": ORG})
    corp_id = parse_id(txt) if st == 200 else None
    if not corp_id:
        raise SystemExit(f"Case 3 failed: status={st}")

    # --- 4 ---
    run(
        "4",
        200,
        {"node_type": "PLANT", "name": "V3TestPlantUnderRegion", "parent_id": region_root_id},
    )

    # --- 5 ---
    run(
        "5",
        400,
        {"node_type": "PLANT", "name": "V3TestPlantUnderCorp", "parent_id": corp_id},
    )

    # --- 6 ---
    st, txt = run(
        "6a_setup",
        200,
        {"node_type": "DEPARTMENT", "name": "V3TestDeptForCase6", "parent_id": plant_id},
    )
    dept6 = parse_id(txt) if st == 200 else None
    if not dept6:
        raise SystemExit("Case 6a failed")
    run(
        "6",
        400,
        {"node_type": "PLANT", "name": "V3TestPlantUnderDept", "parent_id": dept6},
    )

    # --- 7 ---
    st, txt = run(
        "7",
        200,
        {"node_type": "DEPARTMENT", "name": "V3TestDeptCase7", "parent_id": plant_id},
    )
    dept7 = parse_id(txt) if st == 200 else None
    if not dept7:
        raise SystemExit("Case 7 failed")

    # --- 8 ---
    run(
        "8",
        200,
        {"node_type": "DEPARTMENT", "name": "V3TestDeptCase8", "parent_id": corp_id},
    )

    # --- 9 ---
    run(
        "9",
        200,
        {"node_type": "TEAM", "name": "V3TestTeamCase9", "parent_id": dept7},
    )

    # --- 10 ---
    run(
        "10",
        400,
        {"node_type": "TEAM", "name": "V3TestTeamUnderPlant", "parent_id": plant_id},
    )

    # --- 11 ---
    run(
        "11",
        400,
        {
            "node_type": "ORGANIZATION",
            "name": "V3TestFakeOrgRoot",
            "parent_id": ORG,
        },
    )

    for case, expect, curl, _body, status, body_text in results:
        if case == "6a_setup":
            continue
        snippet = body_text.replace("\n", " ")[:160]
        ok = "OK" if status == expect else f"FAIL expected {expect}"
        print(f"\n### Case {case} ({ok})")
        print(curl)
        print(f"Status: {status}")
        print(f"Body: {snippet}")

    con = sqlite3.connect(os.path.join(_REPO, "manufacturing_os.db"))
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM org_nodes WHERE name LIKE 'V3Test%'")
    before = cur.fetchone()[0]
    cur.execute("DELETE FROM org_nodes WHERE name LIKE 'V3Test%'")
    deleted = cur.rowcount
    con.commit()
    cur.execute("SELECT COUNT(*) FROM org_nodes WHERE name LIKE 'V3Test%'")
    after = cur.fetchone()[0]
    con.close()
    print("\n### Cleanup DELETE FROM org_nodes WHERE name LIKE 'V3Test%'")
    print(f"rows_matching_before: {before}, rows_deleted: {deleted}, rows_matching_after: {after}")

    bad = []
    for case, expect, _, _, status, _txt in results:
        if case == "6a_setup":
            continue
        if status != expect:
            bad.append((case, expect, status))
    if bad:
        print("\n*** MATRIX FAILURES ***", bad)
        raise SystemExit(1)
    print("\nAll matrix expectations met.")


if __name__ == "__main__":
    main()
