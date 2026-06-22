"""Phase 4.1 verification (V4.1a–g). Run from repo root: python scripts/_v41_verify.py"""
from __future__ import annotations

import json
import os
import sqlite3
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402
from server.auth import create_access_token  # noqa: E402
from server.database import engine  # noqa: E402
from server.schema_migrations import apply_sqlite_schema_migrations  # noqa: E402

ORG_A = "58ea7177-3d39-49ad-abe6-8d1dbac7f1da"
SA_A = "2e0d94bd-391f-475e-aacc-0e28b5c488e2"
ORG_B = "9147ec73-5e06-4b48-bb83-563f7cb162d7"


def _db():
    return sqlite3.connect(os.path.join(_REPO, "manufacturing_os.db"))


def _token():
    return create_access_token(
        {"sub": SA_A, "org_id": ORG_A, "role": "SUPER_ADMIN"},
    )


def _client():
    return TestClient(app)


def v41a():
    print("=== V4.1a ===")
    con = _db()
    cur = con.cursor()
    n1 = cur.execute("SELECT COUNT(*) FROM org_nodes").fetchone()[0]
    o1 = cur.execute("SELECT COUNT(*) FROM objectives").fetchone()[0]
    fk = cur.execute("PRAGMA foreign_keys").fetchone()[0]
    print("before migration loop counts (already migrated): org_nodes", n1, "objectives", o1)
    print("PRAGMA foreign_keys (raw sqlite3 connection):", fk)
    con.close()

    apply_sqlite_schema_migrations(engine)
    apply_sqlite_schema_migrations(engine)

    con = _db()
    cur = con.cursor()
    n2 = cur.execute("SELECT COUNT(*) FROM org_nodes").fetchone()[0]
    o2 = cur.execute("SELECT COUNT(*) FROM objectives").fetchone()[0]
    print("after 2x apply_sqlite_schema_migrations: org_nodes", n2, "objectives", o2)
    assert n1 == n2 and o1 == o2

    print("--- PRAGMA table_info(org_nodes) ---")
    for row in cur.execute("PRAGMA table_info(org_nodes)"):
        print(row)
    print("--- PRAGMA table_info(objectives) ---")
    for row in cur.execute("PRAGMA table_info(objectives)"):
        print(row)
    con.close()


def _find_plant_dept_cf(cur):
    plant = cur.execute(
        "SELECT id, name FROM org_nodes WHERE org_id=? AND node_type='PLANT' LIMIT 1",
        (ORG_A,),
    ).fetchone()
    if not plant:
        raise SystemExit("No PLANT in org A")
    plant_id, plant_name = plant
    dept = cur.execute(
        "SELECT id, name FROM org_nodes WHERE org_id=? AND node_type='DEPARTMENT' AND parent_id=? LIMIT 1",
        (ORG_A, plant_id),
    ).fetchone()
    cf = cur.execute(
        "SELECT id, name FROM org_nodes WHERE org_id=? AND node_type='CORPORATE_FUNCTION' LIMIT 1",
        (ORG_A,),
    ).fetchone()
    return plant_id, plant_name, dept, cf


def v41bcd():
    con = _db()
    cur = con.cursor()
    plant_id, _, dept, cf = _find_plant_dept_cf(cur)
    if not dept:
        raise SystemExit("No DEPARTMENT under plant — create one manually")
    if not cf:
        raise SystemExit("No CORPORATE_FUNCTION in org A")
    dept_id, _ = dept
    cf_id, _ = cf

    # Create V41Test nodes
    from server.database import SessionLocal
    from server.models import OrgNode
    from server.services.org_tree_service import create_child_node

    db = SessionLocal()
    v_cf_org_b = None
    try:
        root = db.query(OrgNode).filter(OrgNode.id == ORG_A, OrgNode.org_id == ORG_A).first()
        if not root:
            raise SystemExit("missing org root")

        def mk(nt, name, parent_id):
            n = create_child_node(
                parent_id=parent_id,
                node_type=nt,
                name=name,
                org_id=ORG_A,
                db=db,
            )
            db.add(n)
            db.flush()
            return n.id

        v_plant = mk("PLANT", "V41TestPlant", ORG_A)
        v_dept = mk("DEPARTMENT", "V41TestFinanceDept", v_plant)
        v_cf = mk("CORPORATE_FUNCTION", "V41TestCorpFinance", ORG_A)
        # HQ dept under CF (not under plant)
        v_hq_dept = mk("DEPARTMENT", "V41TestHQDept", v_cf)
        # TEAM under plant dept for descendant test
        v_team = mk("TEAM", "V41TestTeamUnderDept", v_dept)
        root_b = db.query(OrgNode).filter(OrgNode.id == ORG_B, OrgNode.org_id == ORG_B).first()
        v_cf_org_b = None
        if root_b:
            nb = create_child_node(
                parent_id=ORG_B,
                node_type="CORPORATE_FUNCTION",
                name="V41TestOrgBCF",
                org_id=ORG_B,
                db=db,
            )
            db.add(nb)
            db.flush()
            v_cf_org_b = nb.id
        db.commit()
    finally:
        db.close()

    c = _client()
    tok = _token()
    h = {"Authorization": f"Bearer {tok}"}
    q = f"?org_id={ORG_A}"

    def patch(node_id, body):
        r = c.patch(f"/api/org-tree/{node_id}{q}", headers=h, json=body)
        return r.status_code, r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text

    print("=== V4.1b PATCH plant dept -> corp CF ===")
    sc, body = patch(v_dept, {"functional_parent_id": v_cf})
    print(sc, body)

    con = _db()
    cur = con.cursor()
    print(
        "SQL V41Test%",
        cur.execute(
            "SELECT id, parent_id, functional_parent_id, node_type, name FROM org_nodes WHERE name LIKE 'V41Test%'"
        ).fetchall(),
    )
    con.close()

    print("=== V4.1c rejection matrix ===")
    # 1 PLANT with functional_parent CF
    sc, b = patch(v_plant, {"functional_parent_id": v_cf})
    print("PLANT->CF", sc, b.get("detail") if isinstance(b, dict) else b)
    # 2 TEAM -> CF
    sc, b = patch(v_team, {"functional_parent_id": v_cf})
    print("TEAM->CF", sc, b.get("detail") if isinstance(b, dict) else b)
    # 3 HQ dept under CF
    sc, b = patch(v_hq_dept, {"functional_parent_id": v_cf})
    print("HQ_DEPT->CF", sc, b.get("detail") if isinstance(b, dict) else b)
    # 4 plant dept -> PLANT (wrong type)
    sc, b = patch(v_dept, {"functional_parent_id": v_plant})
    print("DEPT->PLANT", sc, b.get("detail") if isinstance(b, dict) else b)
    # 5 cross-org: CORPORATE_FUNCTION in org B
    if v_cf_org_b:
        sc, b = patch(v_dept, {"functional_parent_id": v_cf_org_b})
        print("CROSS_ORG", sc, b.get("detail") if isinstance(b, dict) else b)
    else:
        print("CROSS_ORG skip — no org B root")

    sc, b = patch(v_dept, {"functional_parent_id": v_team})
    print("DEPT->descendant_TEAM", sc, b.get("detail") if isinstance(b, dict) else b)

    print("=== V4.1d clear with null ===")
    sc, b = patch(v_dept, {"functional_parent_id": None})
    print(sc, b)
    con = _db()
    cur = con.cursor()
    row = cur.execute(
        "SELECT functional_parent_id FROM org_nodes WHERE id=?",
        (v_dept,),
    ).fetchone()
    print("functional_parent_id after clear:", row)
    con.close()

    print("=== V4.1e GET tree field presence (sample) ===")
    tok = _token()
    r = c.get(f"/api/org-tree?org_id={ORG_A}&user_id={SA_A}", headers={"Authorization": f"Bearer {tok}"})
    data = r.json()

    def walk(d, found):
        if isinstance(d, dict):
            if "functional_parent_id" not in d and "id" in d and d.get("node_type"):
                found.append(f"missing functional_parent_id on {d.get('id')}")
            for k, v in d.items():
                walk(v, found)
        elif isinstance(d, list):
            for x in d:
                walk(x, found)

    f = []
    walk(data, f)
    print("GET /api/org-tree issues:", f[:5] if f else "none (or non-node dicts)")
    r2 = c.get(f"/api/org-tree/{v_dept}?org_id={ORG_A}&user_id={SA_A}", headers={"Authorization": f"Bearer {tok}"})
    j2 = r2.json()
    print("GET single has functional_parent_id:", "functional_parent_id" in j2, "value", j2.get("functional_parent_id"))

    print("=== V4.1g cleanup ===")
    con = _db()
    cur = con.cursor()
    before = cur.execute("SELECT COUNT(*) FROM org_nodes WHERE name LIKE 'V41Test%'").fetchone()[0]
    print("before delete count V41Test%", before)
    cur.execute("DELETE FROM org_nodes WHERE name LIKE 'V41Test%'")
    con.commit()
    after = cur.execute("SELECT COUNT(*) FROM org_nodes WHERE name LIKE 'V41Test%'").fetchone()[0]
    print("after", after)
    con.close()


if __name__ == "__main__":
    v41a()
    v41bcd()
