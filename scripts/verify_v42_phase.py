"""Phase 4.2 verification V4.2a–g. Run: python scripts/verify_v42_phase.py from repo root."""
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
from server.database import engine, SessionLocal  # noqa: E402
from server.models import Objective, OrgNode, User, ReviewCycle  # noqa: E402
from server.schema_migrations import apply_sqlite_schema_migrations  # noqa: E402
from server.services.org_tree_service import create_child_node  # noqa: E402

ORG_A = "58ea7177-3d39-49ad-abe6-8d1dbac7f1da"
SA_A = "2e0d94bd-391f-475e-aacc-0e28b5c488e2"
CEO_A = None  # resolved from DB


def _db():
    return sqlite3.connect(os.path.join(_REPO, "manufacturing_os.db"))


def _sa_token():
    return create_access_token({"sub": SA_A, "org_id": ORG_A, "role": "SUPER_ADMIN"})


def _non_sa_token():
    global CEO_A
    con = _db()
    cur = con.cursor()
    row = cur.execute(
        "SELECT id FROM users WHERE org_id=? AND UPPER(system_role)='CEO' LIMIT 1",
        (ORG_A,),
    ).fetchone()
    con.close()
    if not row:
        return None
    CEO_A = row[0]
    return create_access_token({"sub": CEO_A, "org_id": ORG_A, "role": "CEO"})


def v42a():
    print("=== V4.2a ===")
    con = _db()
    cur = con.cursor()
    o0 = cur.execute("SELECT COUNT(*) FROM objectives").fetchone()[0]
    print("objectives count before", o0)
    for row in cur.execute("PRAGMA table_info(objectives)"):
        if row[1] in ("functional_parent_obj_id", "id"):
            print("objectives col", row)
    for row in cur.execute("PRAGMA table_info(org_nodes)"):
        if row[1] == "functional_parent_id":
            print("org_nodes col", row)
    fk = cur.execute("PRAGMA foreign_keys").fetchone()[0]
    print("PRAGMA foreign_keys (sqlite)", fk)
    con.close()
    apply_sqlite_schema_migrations(engine)
    apply_sqlite_schema_migrations(engine)
    con = _db()
    cur = con.cursor()
    o1 = cur.execute("SELECT COUNT(*) FROM objectives").fetchone()[0]
    print("objectives count after 2x migration", o1, "unchanged" if o1 == o0 else "CHANGED")


def main():
    v42a()
    db = SessionLocal()
    cycle_id = None
    try:
        row = db.query(ReviewCycle).filter(ReviewCycle.org_id == ORG_A).first()
        if row:
            cycle_id = row.id
        else:
            rc = ReviewCycle(
                org_id=ORG_A,
                name="V42TestCycle",
                start_date="2026-01-01",
                end_date="2026-12-31",
            )
            db.add(rc)
            db.commit()
            db.refresh(rc)
            cycle_id = rc.id
    finally:
        db.close()

    if not cycle_id:
        print("SKIP V4.2b+: could not obtain cycle_id")
        return

    db = SessionLocal()
    plant_id = dept_id = cf_id = None
    plant_obj = corp_obj = None
    prev_node = None
    try:
        v_plant = create_child_node(
            parent_id=ORG_A,
            node_type="PLANT",
            name="V42TestPlant",
            org_id=ORG_A,
            db=db,
        )
        db.add(v_plant)
        db.flush()
        plant_id = v_plant.id
        v_dept = create_child_node(
            parent_id=plant_id,
            node_type="DEPARTMENT",
            name="V42TestPlantDept",
            org_id=ORG_A,
            db=db,
        )
        db.add(v_dept)
        db.flush()
        dept_id = v_dept.id
        v_cf = create_child_node(
            parent_id=ORG_A,
            node_type="CORPORATE_FUNCTION",
            name="V42TestCorpFunc",
            org_id=ORG_A,
            db=db,
        )
        db.add(v_cf)
        db.flush()
        cf_id = v_cf.id

        # Corporate target: owner org_node = CF (Option A branch 2)
        u = db.query(User).filter(User.id == SA_A).first()
        prev_node = u.org_node_id
        u.org_node_id = cf_id
        db.flush()

        plant_obj = Objective(
            org_id=ORG_A,
            owner_id=SA_A,
            title="V42TestPlantObj",
            description="x",
            level="DEPARTMENT",
            plant_id=plant_id,
            department_id=dept_id,
            team_id=None,
            cycle_id=cycle_id,
        )
        corp_obj = Objective(
            org_id=ORG_A,
            owner_id=SA_A,
            title="V42TestCorpObj",
            description="y",
            level="ORGANIZATION",
            cycle_id=cycle_id,
        )
        db.add(plant_obj)
        db.add(corp_obj)
        db.commit()
        db.refresh(plant_obj)
        db.refresh(corp_obj)

        team_row = (
            db.query(OrgNode)
            .filter(OrgNode.org_id == ORG_A, OrgNode.node_type == "TEAM")
            .first()
        )
        real_team_id = team_row.id if team_row else None

        c = TestClient(app)
        q = f"?org_id={ORG_A}"
        h_sa = {"Authorization": f"Bearer {_sa_token()}"}

        print("=== V4.2b PATCH happy path ===")
        r = c.patch(
            f"/api/okrs/{plant_obj.id}{q}",
            headers=h_sa,
            json={"functional_parent_obj_id": corp_obj.id},
        )
        print(r.status_code, r.json().get("functional_parent_obj_id") if r.status_code == 200 else r.json())

        con = _db()
        cur = con.cursor()
        print(
            "SQL V42Test%",
            cur.execute(
                "SELECT id, parent_id, functional_parent_obj_id, department_id, cycle_id, level FROM objectives WHERE title LIKE 'V42Test%'"
            ).fetchall(),
        )
        con.close()

        print("=== V4.2c matrix (subset) ===")
        # Row 1 CEO
        tok_ceo = _non_sa_token()
        if tok_ceo:
            r1 = c.patch(
                f"/api/okrs/{plant_obj.id}{q}",
                headers={"Authorization": f"Bearer {tok_ceo}"},
                json={"functional_parent_obj_id": corp_obj.id},
            )
            print("1 CEO", r1.status_code, r1.json().get("detail"))

        # Row 2 POST create
        r2 = c.post(f"/api/okrs{q}", headers=h_sa, json={"title": "x", "level": "DEPARTMENT", "functional_parent_obj_id": corp_obj.id})
        print("2 POST", r2.status_code, r2.json().get("detail"))

        # Row 3 empty string
        r3 = c.patch(f"/api/okrs/{plant_obj.id}{q}", headers=h_sa, json={"functional_parent_obj_id": "  "})
        print("3 empty", r3.status_code, r3.json().get("detail"))

        # Row 4-6: TEAM objective (needs real team_id FK)
        if real_team_id:
            team_obj = Objective(
                org_id=ORG_A,
                owner_id=SA_A,
                title="V42TestTeamObj",
                level="TEAM",
                plant_id=plant_id,
                department_id=dept_id,
                team_id=real_team_id,
                cycle_id=cycle_id,
            )
            db.add(team_obj)
            db.commit()
            db.refresh(team_obj)
            r4 = c.patch(
                f"/api/okrs/{team_obj.id}{q}",
                headers=h_sa,
                json={"functional_parent_obj_id": corp_obj.id},
            )
            print("4-6 TEAM", r4.status_code, r4.json().get("detail"))
        else:
            print("4-6 TEAM skip — no TEAM org node in org A")

        # Row 7 cross-org: use corp_obj id is same org - need other org objective
        other = db.query(Objective).filter(Objective.org_id != ORG_A).first()
        if other:
            r7 = c.patch(
                f"/api/okrs/{plant_obj.id}{q}",
                headers=h_sa,
                json={"functional_parent_obj_id": other.id},
            )
            print("7 cross", r7.status_code, r7.json().get("detail"))

        # Row 8 self
        r8 = c.patch(f"/api/okrs/{plant_obj.id}{q}", headers=h_sa, json={"functional_parent_obj_id": plant_obj.id})
        print("8 self", r8.status_code, r8.json().get("detail"))

        # Row 9 descendant: child under plant_obj
        child = Objective(
            org_id=ORG_A,
            owner_id=SA_A,
            title="V42TestChildObj",
            level="DEPARTMENT",
            plant_id=plant_id,
            department_id=dept_id,
            team_id=None,
            parent_id=plant_obj.id,
            cycle_id=cycle_id,
        )
        db.add(child)
        db.commit()
        db.refresh(child)
        r9 = c.patch(
            f"/api/okrs/{plant_obj.id}{q}",
            headers=h_sa,
            json={"functional_parent_obj_id": child.id},
        )
        print("9 desc", r9.status_code, r9.json().get("detail"))

        # Row 12 cycle mismatch
        plant2 = Objective(
            org_id=ORG_A,
            owner_id=SA_A,
            title="V42TestPlantObj2",
            level="DEPARTMENT",
            plant_id=plant_id,
            department_id=dept_id,
            team_id=None,
            cycle_id=None,
        )
        db.add(plant2)
        db.commit()
        db.refresh(plant2)
        r12 = c.patch(
            f"/api/okrs/{plant2.id}{q}",
            headers=h_sa,
            json={"functional_parent_obj_id": corp_obj.id},
        )
        print("12 cycle", r12.status_code, r12.json().get("detail"))

        # Row 10 vs 11: target with owner org root only
        orphan = Objective(
            org_id=ORG_A,
            owner_id=SA_A,
            title="V42TestOrphanCorp",
            level="ORGANIZATION",
            cycle_id=cycle_id,
        )
        db.add(orphan)
        db.commit()
        db.refresh(orphan)
        u2 = db.query(User).filter(User.id == SA_A).first()
        u2.org_node_id = ORG_A
        db.commit()
        r11 = c.patch(
            f"/api/okrs/{plant_obj.id}{q}",
            headers=h_sa,
            json={"functional_parent_obj_id": orphan.id},
        )
        print("10/11 orphan", r11.status_code, r11.json().get("detail"))
        u2.org_node_id = cf_id
        db.commit()

        # restore link for 4.2d-e
        c.patch(f"/api/okrs/{plant_obj.id}{q}", headers=h_sa, json={"functional_parent_obj_id": corp_obj.id})

        print("=== V4.2d clear ===")
        rd = c.patch(f"/api/okrs/{plant_obj.id}{q}", headers=h_sa, json={"functional_parent_obj_id": None})
        print(rd.status_code, rd.json().get("functional_parent_obj_id"))

        print("=== V4.2e GET ===")
        c.patch(f"/api/okrs/{plant_obj.id}{q}", headers=h_sa, json={"functional_parent_obj_id": corp_obj.id})
        g1 = c.get(f"/api/okrs/{plant_obj.id}", headers=h_sa)
        print("GET single has key", "functional_parent_obj_id" in g1.json(), g1.json().get("functional_parent_obj_id"))
        g2 = c.get(f"/api/okrs{q}", headers=h_sa)
        arr = g2.json()
        miss = [x.get("id") for x in arr if isinstance(x, dict) and "functional_parent_obj_id" not in x]
        print("GET list missing field count", len(miss), "sample", miss[:3])

    finally:
        try:
            u = db.query(User).filter(User.id == SA_A).first()
            if u is not None and prev_node is not None:
                u.org_node_id = prev_node
                db.commit()
        except Exception:
            db.rollback()
        db.close()

    print("=== V4.2g cleanup ===")
    con = _db()
    cur = con.cursor()
    b1 = cur.execute("SELECT COUNT(*) FROM objectives WHERE title LIKE 'V42Test%'").fetchone()[0]
    b2 = cur.execute("SELECT COUNT(*) FROM org_nodes WHERE name LIKE 'V42Test%'").fetchone()[0]
    cur.execute("DELETE FROM objectives WHERE title LIKE 'V42Test%'")
    cur.execute("DELETE FROM org_nodes WHERE name LIKE 'V42Test%'")
    con.commit()
    print("DELETE objectives V42Test%; before", b1, "after", cur.execute("SELECT COUNT(*) FROM objectives WHERE title LIKE 'V42Test%'").fetchone()[0])
    print("DELETE org_nodes V42Test%; before", b2, "after", cur.execute("SELECT COUNT(*) FROM org_nodes WHERE name LIKE 'V42Test%'").fetchone()[0])
    con.close()


if __name__ == "__main__":
    main()
