"""Step 5 verification helper: region + plant + node detail + delete guard + SQL cleanup.

Uses the same JWT pattern as scripts/v4_step4_verify.py. Requires API on 127.0.0.1:8000.
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

ORG_A = "58ea7177-3d39-49ad-abe6-8d1dbac7f1da"
SA_A = "2e0d94bd-391f-475e-aacc-0e28b5c488e2"

BASE_TREE = "http://127.0.0.1:8000/api/org-tree"
BASE_ORG = "http://127.0.0.1:8000/api/org/plants"
DB_PATH = os.path.join(_REPO, "manufacturing_os.db")

REGION_NAME = "Step5MatrixVerifyRegion"
PLANT_NAME = "Step5MatrixVerifyPlant"


def req_json(method: str, url: str, token: str | None, body: dict | None) -> tuple[int, str]:
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def count_matches(cur: sqlite3.Cursor) -> tuple[int, int]:
    cur.execute("SELECT COUNT(*) FROM org_nodes WHERE name = ?", (REGION_NAME,))
    r1 = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM org_nodes WHERE name = ?", (PLANT_NAME,))
    r2 = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM plants WHERE name = ?", (PLANT_NAME,))
    p = cur.fetchone()[0]
    return r1 + r2, p


def main() -> None:
    tok = create_access_token({"sub": SA_A, "org_id": ORG_A, "role": "SUPER_ADMIN"})

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    print("=== SQL row counts BEFORE cleanup-style probe (existing Step5 rows) ===")
    org_before, plants_before = count_matches(cur)

    # Idempotent: remove leftovers from a prior failed run
    cur.execute("DELETE FROM plants WHERE name = ?", (PLANT_NAME,))
    cur.execute("DELETE FROM org_nodes WHERE name = ?", (PLANT_NAME,))
    cur.execute("DELETE FROM org_nodes WHERE name = ?", (REGION_NAME,))
    con.commit()
    print("After deleting any prior Step5 test rows:", count_matches(cur))

    print("\n=== POST region (same contract as UI create) ===")
    st, body = req_json("POST", f"{BASE_TREE}/regions", tok, {"name": REGION_NAME, "code": "S5MR"})
    print("status", st, body[:300])
    if st != 200:
        con.close()
        raise SystemExit(1)
    region = json.loads(body)
    rid = region["id"]

    print("\n=== POST plant with region_id (Step 4 + 5 integration) ===")
    st2, body2 = req_json(
        "POST",
        BASE_ORG,
        tok,
        {"name": PLANT_NAME, "region_id": rid},
    )
    print("status", st2, body2[:300])
    if st2 != 200:
        con.close()
        raise SystemExit(1)
    plant = json.loads(body2)
    pid = plant["id"]

    print("\n=== GET org node (prefetch contract for delete dialog) ===")
    st3, body3 = req_json("GET", f"{BASE_TREE}/{rid}", tok, None)
    detail = json.loads(body3)
    children = detail.get("children") or []
    print("status", st3, "child_count", len(children))
    assert len(children) == 1, children
    assert children[0].get("node_type") == "PLANT", children[0]

    print("\n=== DELETE region (expect 400; UI disables Delete when child_count > 0) ===")
    st4, body4 = req_json("DELETE", f"{BASE_TREE}/{rid}", tok, None)
    print("status", st4, body4[:200])
    assert st4 == 400, st4

    print("\n=== SQL cleanup (plant row + org_nodes) ===")
    org_mid, plants_mid = count_matches(cur)
    print("Row counts before SQL deletes — org_nodes matching names:", org_mid, "plants:", plants_mid)

    cur.execute("DELETE FROM plants WHERE id = ?", (pid,))
    del_plants = cur.rowcount
    cur.execute("DELETE FROM org_nodes WHERE id = ?", (pid,))
    del_on_plant = cur.rowcount
    cur.execute("DELETE FROM org_nodes WHERE id = ?", (rid,))
    del_on_region = cur.rowcount
    con.commit()

    org_after, plants_after = count_matches(cur)
    print(
        "Deleted plants rows:", del_plants,
        "org_nodes (plant id):", del_on_plant,
        "org_nodes (region id):", del_on_region,
    )
    print("Row counts AFTER SQL deletes — org_nodes matching names:", org_after, "plants:", plants_after)
    con.close()


if __name__ == "__main__":
    main()
