"""Step 4 verification V4a-V4i. Requires uvicorn on 127.0.0.1:8000."""
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
ORG_B = "9147ec73-5e06-4b48-bb83-563f7cb162d7"
SA_B = "f88a6282-3527-45bd-9e18-e13a79251bfe"
PH_A = "19bc0473-705b-4324-9c3b-bd0c8da41f69"

BASE_TREE = "http://127.0.0.1:8000/api/org-tree"
BASE_ORG = "http://127.0.0.1:8000/api/org/plants"


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


def main() -> None:
    tok_a = create_access_token({"sub": SA_A, "org_id": ORG_A, "role": "SUPER_ADMIN"})
    tok_b = create_access_token({"sub": SA_B, "org_id": ORG_B, "role": "SUPER_ADMIN"})
    tok_ph = create_access_token({"sub": PH_A, "org_id": ORG_A, "role": "PLANT_HEAD"})

    print("=== V4b dedicated endpoints ===")
    st, body = req_json("POST", f"{BASE_TREE}/regions", tok_a, {"name": "Step4TestRegion"})
    print("POST /regions (admin)", st, body[:200])
    reg = json.loads(body) if st == 200 else {}
    rid = reg.get("id")

    st2, body2 = req_json("POST", f"{BASE_TREE}/corporate-functions", tok_a, {"name": "Step4TestCorp"})
    print("POST /corporate-functions (admin)", st2, body2[:200])

    st3, body3 = req_json("POST", f"{BASE_TREE}/regions", tok_ph, {"name": "Step4TestRegion2"})
    print("POST /regions (plant_head, expect 403)", st3, body3[:120])

    st4, body4 = req_json("POST", f"{BASE_TREE}/regions", None, {"name": "Step4TestRegion3"})
    print("POST /regions (no auth)", st4, body4[:120])

    print("\n=== V4c cross-org region_id ===")
    st5, body5 = req_json(
        "POST",
        BASE_ORG,
        tok_b,
        {"name": "Step4TestPlantCrossOrg", "region_id": rid},
    )
    print("POST plants org B with region from org A", st5, body5[:200])

    print("\n=== V4d plant with region ===")
    st6, body6 = req_json(
        "POST",
        BASE_ORG,
        tok_a,
        {"name": "Step4TestPlantWithRegion", "region_id": rid},
    )
    print("POST plants with region", st6, body6[:200])

    print("\n=== V4e plant no region ===")
    st7, body7 = req_json("POST", BASE_ORG, tok_a, {"name": "Step4TestPlantNoRegion"})
    print("POST plants no region", st7, body7[:200])

    con = sqlite3.connect(os.path.join(_REPO, "manufacturing_os.db"))
    cur = con.cursor()
    cur.execute(
        "SELECT id, node_type, parent_id, depth, path FROM org_nodes WHERE name = ?",
        ("Step4TestPlantWithRegion",),
    )
    print("SQL Step4TestPlantWithRegion", cur.fetchall())
    cur.execute(
        "SELECT id, node_type, parent_id, depth, path FROM org_nodes WHERE name = ?",
        ("Step4TestPlantNoRegion",),
    )
    print("SQL Step4TestPlantNoRegion", cur.fetchall())
    cur.execute("SELECT id FROM org_nodes WHERE org_id=? AND node_type='PLANT' AND name NOT LIKE 'Step4Test%' LIMIT 1", (ORG_A,))
    existing_plant = cur.fetchone()
    con.close()
    pid = existing_plant[0] if existing_plant else None

    print("\n=== V4f invalid region_id ===")
    if pid:
        st8, body8 = req_json(
            "POST",
            BASE_ORG,
            tok_a,
            {"name": "Step4TestPlantBadParent", "region_id": pid},
        )
        print("region_id=PLANT node", st8, body8[:200])
    fake = "00000000-0000-4000-8000-000000000001"
    st9, body9 = req_json("POST", BASE_ORG, tok_a, {"name": "Step4TestPlantFake", "region_id": fake})
    print("region_id nonexistent", st9, body9[:200])

    print("\n=== V4g grep hint: run grep NodeType.REGION in routes ===")

    print("\n=== V4i duplicate region name ===")
    st_d1, _ = req_json("POST", f"{BASE_TREE}/regions", tok_a, {"name": "Step4DupRegion"})
    st_d2, b_d2 = req_json("POST", f"{BASE_TREE}/regions", tok_a, {"name": "Step4DupRegion"})
    print("first dup", st_d1, "second dup", st_d2, b_d2[:180])


if __name__ == "__main__":
    main()
