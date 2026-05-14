"""
Phase 3.3 verification harness (V3.3a-h). Run from repo root:

  python scripts/verify_v33_substep.py
"""

from __future__ import annotations

import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

ORG_ID = "58ea7177-3d39-49ad-abe6-8d1dbac7f1da"

OLD_ROLE_CREATION_LEVELS = {
    "SUPER_ADMIN": ["ORGANIZATION", "PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"],
    "CEO": ["ORGANIZATION"],
    "VP_OPERATIONS": ["PLANT", "DEPARTMENT"],
    "PLANT_HEAD": ["PLANT", "DEPARTMENT", "TEAM"],
    "DEPT_HEAD": ["DEPARTMENT", "TEAM"],
    "MANAGER": ["TEAM", "INDIVIDUAL"],
    "TEAM_LEAD": ["INDIVIDUAL"],
    "SUPERVISOR": ["INDIVIDUAL"],
    "EMPLOYEE": [],
    "HR_HEAD": [],
}


def main() -> None:
    from fastapi.testclient import TestClient
    from main import app
    from server.database import SessionLocal
    from server.models import Objective
    from server.okr_hierarchy_workflow import OKRHierarchyWorkflow
    from server.roles import (
        OBJECTIVE_LEVEL_ORDER,
        SystemRole,
        allowed_objective_levels_for,
    )

    roles_check = [
        SystemRole.SUPER_ADMIN,
        SystemRole.CEO,
        SystemRole.VP_OPERATIONS,
        SystemRole.PLANT_HEAD,
        SystemRole.DEPT_HEAD,
        SystemRole.MANAGER,
        SystemRole.TEAM_LEAD,
        SystemRole.SUPERVISOR,
        SystemRole.EMPLOYEE,
        SystemRole.HR_HEAD,
    ]

    print("=" * 72)
    print("V3.3a — OLD vs NEW (workflow ROLE_CREATION_LEVELS vs roles policy)")
    print("=" * 72)
    for r in roles_check:
        key = r.value
        old_list = OLD_ROLE_CREATION_LEVELS.get(key, [])
        old_set = set(old_list)
        new_set = set(allowed_objective_levels_for(r))
        added = sorted(new_set - old_set)
        removed = sorted(old_set - new_set)
        note = ""
        if r == SystemRole.CEO:
            note = " (intentional: CEO bypass -> all five levels)"
        elif not added and not removed:
            note = " (unchanged)"
        print(f"  {key}")
        print(f"    OLD: {sorted(old_set)}")
        print(f"    NEW: {sorted(new_set)}")
        if added or removed:
            print(f"    vs OLD: +{added} -{removed}{note}")
        else:
            print(f"    vs OLD: same set{note}")

    print("\n" + "=" * 72)
    print("V3.3b — REGIONAL_HEAD, CFO, CMO, CTO")
    print("=" * 72)
    for r in (SystemRole.REGIONAL_HEAD, SystemRole.CFO, SystemRole.CMO, SystemRole.CTO):
        print(f"  {r.value}: {allowed_objective_levels_for(r)}")

    print("\n" + "=" * 72)
    print("V3.3c — SUPER_ADMIN in APPROVAL_ROLES_BY_LEVEL literals (file scan)")
    print("=" * 72)
    path = os.path.join(ROOT, "server", "okr_hierarchy_workflow.py")
    text = open(path, encoding="utf-8").read()
    m = re.search(r"APPROVAL_ROLES_BY_LEVEL\s*=\s*\{([^}]+)\}", text, re.DOTALL)
    block = m.group(1) if m else ""
    bad = "SUPER_ADMIN" in block
    print("  SUPER_ADMIN appears inside APPROVAL_ROLES_BY_LEVEL dict block:", bad, "(expected False)")
    print("  (Other SUPER_ADMIN mentions in file for scope bypass are OK.)")

    client = TestClient(app)

    print("\n" + "=" * 72)
    print("V3.3d — POST /api/okrs/hierarchy/validate/can-create (compact)")
    print("=" * 72)
    con = sqlite3.connect(os.path.join(ROOT, "manufacturing_os.db"))
    cur = con.cursor()
    users = {
        e: (uid, sr)
        for e, uid, sr in cur.execute(
            """SELECT email, id, system_role FROM users
               WHERE org_id=? AND email IN (
                 'admin@tata.com','r@tata.com','j@tata.com','a@tata.com',
                 'b@tata.com','manager@tata.com','s@tata.com')""",
            (ORG_ID,),
        ).fetchall()
    }
    con.close()
    by_email = users

    def hit(email: str, level: str):
        uid, _ = by_email[email]
        r = client.post(
            "/api/okrs/hierarchy/validate/can-create",
            params={"user_id": uid, "okr_level": level, "org_id": ORG_ID},
        )
        j = r.json()
        return j.get("can_create"), j.get("allowed_levels")

    matrix_emails = [
        ("admin@tata.com", "SUPER_ADMIN"),
        ("r@tata.com", "CEO"),
        ("j@tata.com", "VP_OPERATIONS"),
        ("a@tata.com", "PLANT_HEAD"),
        ("b@tata.com", "DEPT_HEAD"),
        ("manager@tata.com", "MANAGER"),
        ("s@tata.com", "EMPLOYEE"),
    ]
    print("  role x level -> can_create, allowed_levels snippet")
    for em, label in matrix_emails:
        row = []
        for lvl in OBJECTIVE_LEVEL_ORDER:
            cc, al = hit(em, lvl)
            row.append(f"{lvl[:3]}={'Y' if cc else 'N'}")
        _, al_full = hit(em, "PLANT")
        print(f"  {label:16} {' '.join(row)} | example allowed={al_full}")

    print("\n" + "=" * 72)
    print("V3.3e — POST /api/okrs create (flat route)")
    print("=" * 72)
    con = sqlite3.connect(os.path.join(ROOT, "manufacturing_os.db"))
    row = con.execute(
        """SELECT u.id, u.plant_id, u.department_id, u.team_id FROM users u
           WHERE u.email='manager@tata.com'"""
    ).fetchone()
    mgr_id, p_id, d_id, t_id = row
    ceo = con.execute("SELECT id FROM users WHERE email='r@tata.com'").fetchone()[0]
    emp = con.execute("SELECT id FROM users WHERE email='s@tata.com'").fetchone()[0]
    ph = con.execute("SELECT id FROM users WHERE email='a@tata.com'").fetchone()[0]
    con.close()

    def post_okr(uid: str, role: str, level: str, **scope):
        body = {"title": f"V33 test {level}", "level": level, **scope}
        return client.post(
            "/api/okrs",
            params={"org_id": ORG_ID, "user_id": uid, "role": role},
            json=body,
        )

    r1 = post_okr(emp, "EMPLOYEE", "ORGANIZATION")
    r2 = post_okr(ceo, "CEO", "TEAM", plant_id=p_id, department_id=d_id, team_id=t_id)
    r3 = post_okr(ph, "PLANT_HEAD", "TEAM", plant_id=p_id, department_id=d_id, team_id=t_id)
    r4 = post_okr(mgr_id, "MANAGER", "PLANT", plant_id=p_id)
    print(f"  EMPLOYEE ORGANIZATION -> {r1.status_code}")
    print(f"  CEO TEAM -> {r2.status_code}")
    print(f"  PLANT_HEAD TEAM -> {r3.status_code}")
    print(f"  MANAGER PLANT -> {r4.status_code}")

    print("\n" + "=" * 72)
    print("V3.3h — GET /api/okrs/allowed-levels")
    print("=" * 72)
    for role in ("CEO", "MANAGER", "EMPLOYEE"):
        rr = client.get("/api/okrs/allowed-levels", params={"role": role})
        print(f"  {role}: {rr.json()}")

    print("\n" + "=" * 72)
    print("V3.3i — approval chain roles (no SUPER_ADMIN in chain list)")
    print("=" * 72)
    db = SessionLocal()
    okr = (
        db.query(Objective)
        .filter(Objective.org_id == ORG_ID, Objective.level == "DEPARTMENT")
        .first()
    )
    wf = OKRHierarchyWorkflow(db)
    chain = wf.get_approval_chain_for_okr(okr, ORG_ID) if okr else []
    roles_in_chain = [c["role"] for c in chain]
    print(f"  sample OKR id={okr.id if okr else None} level={okr.level if okr else None}")
    print(f"  chain roles (flattened): {roles_in_chain[:20]}...")
    print(f"  SUPER_ADMIN in chain: {'SUPER_ADMIN' in roles_in_chain}")
    db.close()

    print("\n" + "=" * 72)
    print("V3.3f — ROLE_CREATION_SCOPE references (server/*.py only)")
    print("=" * 72)
    import pathlib

    hits = []
    for p in pathlib.Path(ROOT, "server").rglob("*.py"):
        t = p.read_text(encoding="utf-8", errors="replace")
        if "ROLE_CREATION_SCOPE" in t:
            hits.append(str(p.relative_to(ROOT)))
    print("  files:", hits or "(none)")

    print("\n" + "=" * 72)
    print("V3.3g — grep ROLE_CREATE_LEVELS | ROLE_CREATION_LEVELS (server/*.py)")
    print("=" * 72)
    hits2 = []
    for p in pathlib.Path(ROOT, "server").rglob("*.py"):
        t = p.read_text(encoding="utf-8", errors="replace")
        if "ROLE_CREATE_LEVELS" in t or "ROLE_CREATION_LEVELS" in t:
            hits2.append(str(p.relative_to(ROOT)))
    print("  files:", hits2)

    print("\nDone.")


if __name__ == "__main__":
    main()
