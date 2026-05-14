"""Step 6 verification (API + SQL). Requires server on 127.0.0.1:8000."""
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


def req(method: str, url: str, tok: str, body: dict | None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body else None
    h = {"Content-Type": "application/json", "Authorization": f"Bearer {tok}"}
    r = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def main() -> None:
    tok = create_access_token({"sub": SA_A, "org_id": ORG_A, "role": "SUPER_ADMIN"})
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM org_nodes WHERE org_id=? AND node_type='REGION' AND is_active=1",
        (ORG_A,),
    )
    n_regions = cur.fetchone()[0]
    print("V6a: REGION count for org A:", n_regions, "(UI: dropdown visible iff > 0)")

    for name in ("Step6TestPlantWithRegion", "Step6TestPlantNoRegion", "Step6TempRegion"):
        cur.execute("DELETE FROM plants WHERE name=?", (name,))
        cur.execute("DELETE FROM org_nodes WHERE name=?", (name,))
    con.commit()

    st, reg = req("POST", f"{BASE_TREE}/regions", tok, {"name": "Step6TempRegion", "code": "S6TR"})
    rid = reg.get("id") if st == 200 else None
    print("Temp region POST", st, rid)
    if not rid:
        con.close()
        raise SystemExit(1)

    st2, pl = req("POST", BASE_ORG, tok, {"name": "Step6TestPlantWithRegion", "region_id": rid})
    print("V6b plant with region", st2, pl.get("id"))
    cur.execute(
        """SELECT p.id, p.name, n.parent_id, n.depth, n.path
        FROM plants p JOIN org_nodes n ON n.id = p.id
        WHERE p.name = 'Step6TestPlantWithRegion'"""
    )
    row = cur.fetchone()
    print("V6b SQL:", row)
    if row:
        segs = row[4].split(".") if row[4] else []
        print("  parent_id==region:", row[2] == rid, "depth==2:", row[3] == 2, "path_segments==3:", len(segs) == 3)

    st3, pl2 = req("POST", BASE_ORG, tok, {"name": "Step6TestPlantNoRegion"})
    print("V6c plant no region", st3, pl2.get("id"))
    cur.execute(
        """SELECT p.id, p.name, n.parent_id, n.depth, n.path
        FROM plants p JOIN org_nodes n ON n.id = p.id
        WHERE p.name = 'Step6TestPlantNoRegion'"""
    )
    row2 = cur.fetchone()
    print("V6c SQL:", row2)
    if row2:
        segs2 = row2[4].split(".") if row2[4] else []
        print("  parent_id==org:", row2[2] == ORG_A, "depth==1:", row2[3] == 1, "path_segments==2:", len(segs2) == 2)

    cur.execute(
        "SELECT COUNT(*) FROM plants WHERE name LIKE 'Step6Test%' OR name LIKE 'Step6Temp%'"
    )
    bp = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM org_nodes WHERE name LIKE 'Step6Test%' OR name LIKE 'Step6Temp%'"
    )
    bo = cur.fetchone()[0]
    print("V6d before cleanup — plants:", bp, "org_nodes:", bo)

    for name in ("Step6TestPlantWithRegion", "Step6TestPlantNoRegion", "Step6TempRegion"):
        cur.execute("DELETE FROM plants WHERE name=?", (name,))
        cur.execute("DELETE FROM org_nodes WHERE name=?", (name,))
    con.commit()

    cur.execute(
        "SELECT COUNT(*) FROM plants WHERE name LIKE 'Step6Test%' OR name LIKE 'Step6Temp%'"
    )
    ap = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM org_nodes WHERE name LIKE 'Step6Test%' OR name LIKE 'Step6Temp%'"
    )
    ao = cur.fetchone()[0]
    print("V6d after cleanup — plants:", ap, "org_nodes:", ao)
    con.close()


if __name__ == "__main__":
    main()
