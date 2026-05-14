"""
V3.5a — compact mutation matrix vs 127.0.0.1:8000.

Uses manufacturing_os.db for org A ids (same org as scripts/v4_step4_verify.py).

Does not DELETE teams/plants used elsewhere (Category A team DELETE is spot-checked
on a disposable team created first by SUPER_ADMIN).
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import uuid
import urllib.error
import urllib.request

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from server.auth import create_access_token  # noqa: E402

ORG_A = "58ea7177-3d39-49ad-abe6-8d1dbac7f1da"
SA_A = "2e0d94bd-391f-475e-aacc-0e28b5c488e2"
ORG_B = "9147ec73-5e06-4b48-bb83-563f7cb162d7"
SA_B = "f88a6282-3527-45bd-9e18-e13a79251bfe"
MGR_A = "5809a034-5977-463d-b486-aae39718e9bc"
PH_A = "19bc0473-705b-4324-9c3b-bd0c8da41f69"
BASE = "http://127.0.0.1:8000"


def req(method: str, path: str, token: str | None, body: dict | None) -> int:
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


def main() -> None:
    db = os.path.join(_REPO, "manufacturing_os.db")
    con = sqlite3.connect(db)
    cur = con.cursor()
    plant_a = cur.execute(
        "SELECT id FROM plants WHERE org_id=? AND is_active=1 LIMIT 1", (ORG_A,)
    ).fetchone()[0]
    team_a = cur.execute(
        "SELECT id FROM teams WHERE org_id=? AND is_active=1 LIMIT 1", (ORG_A,)
    ).fetchone()[0]
    dept_id = cur.execute(
        "SELECT id FROM departments WHERE org_id=? AND is_active=1 LIMIT 1", (ORG_A,)
    ).fetchone()[0]
    other_user = cur.execute(
        "SELECT id FROM users WHERE org_id=? AND id!=? LIMIT 1", (ORG_A, MGR_A)
    ).fetchone()[0]
    roster_uid = cur.execute(
        """
        SELECT u.id FROM users u
        JOIN teams t ON t.id = ?
        JOIN departments d ON d.id = t.department_id
        WHERE u.org_id = ? AND u.plant_id = d.plant_id
        LIMIT 1
        """,
        (team_a, ORG_A),
    ).fetchone()
    roster_uid = roster_uid[0] if roster_uid else other_user
    desig_a = cur.execute(
        "SELECT id FROM designations WHERE org_id=? AND is_active=1 LIMIT 1", (ORG_A,)
    ).fetchone()
    con.close()

    tok_sa = create_access_token({"sub": SA_A, "org_id": ORG_A, "role": "SUPER_ADMIN"})
    tok_sa_b = create_access_token({"sub": SA_B, "org_id": ORG_B, "role": "SUPER_ADMIN"})
    tok_mgr = create_access_token({"sub": MGR_A, "org_id": ORG_A, "role": "MANAGER"})
    tok_ph = create_access_token({"sub": PH_A, "org_id": ORG_A, "role": "PLANT_HEAD"})
    tok_hr = create_access_token({"sub": MGR_A, "org_id": ORG_A, "role": "HR_HEAD"})

    # Roster row for lead-status probe (DB may have no team_members rows)
    req(
        "POST",
        f"/api/teams/{team_a}/members?member_user_id={roster_uid}&is_team_lead=false",
        tok_sa,
        None,
    )
    member_on_team = roster_uid

    if not desig_a:
        req("POST", "/api/org/designations", tok_sa, {"name": "V35Desig", "level": 3, "category": "X"})
        con = sqlite3.connect(db)
        desig_a = con.execute(
            "SELECT id FROM designations WHERE org_id=? AND name='V35Desig' LIMIT 1", (ORG_A,)
        ).fetchone()[0]
        con.close()
    else:
        desig_a = desig_a[0]

    # disposable team for DELETE row
    body_team = {"department_id": dept_id, "name": "V35DisposableTeam", "member_user_ids": []}
    st_ct = req("POST", "/api/teams", tok_sa, body_team)
    disposable_team = None
    if st_ct == 200:
        con = sqlite3.connect(db)
        disposable_team = con.execute(
            "SELECT id FROM teams WHERE org_id=? AND name='V35DisposableTeam' LIMIT 1", (ORG_A,)
        ).fetchone()
        disposable_team = disposable_team[0] if disposable_team else None
        con.close()

    mod_id = None
    try:
        with urllib.request.urlopen(
            urllib.request.Request(
                BASE + "/api/permissions/modules",
                headers={"Authorization": f"Bearer {tok_sa}"},
            ),
            timeout=20,
        ) as resp:
            mods = json.loads(resp.read().decode())
            if mods:
                mod_id = mods[0]["id"]
    except OSError:
        pass

    plant_body = {"name": "V35Plant", "location": "L", "code": "V35C"}
    rows: list[tuple[str, str, int, int, str]] = []

    def row(label: str, cat: str, mgr: int, sa: int, audit: str) -> None:
        rows.append((label, cat, mgr, sa, audit))

    # Category A
    tests_a: list[tuple[str, str, str, dict | None]] = [
        ("POST /api/org/plants", "POST", "/api/org/plants", plant_body),
        ("PUT /api/org/plants/{id}", "PUT", f"/api/org/plants/{plant_a}", {"name": "pune", "location": "L", "code": "c"}),
        ("PUT /api/org", "PUT", "/api/org?name=v35org", None),
        ("POST /api/org/departments", "POST", "/api/org/departments", {"plant_id": plant_a, "name": "V35DeptX", "dept_type": "HR"}),
        ("POST /api/org/departments/seed-defaults", "POST", f"/api/org/departments/seed-defaults?plant_id={plant_a}", None),
        ("POST /api/org/shifts", "POST", "/api/org/shifts", {"plant_id": plant_a, "name": "V35Shift"}),
        ("POST /api/org/designations", "POST", "/api/org/designations", {"name": "V35Desig2", "level": 9}),
        ("POST /api/org/designations/seed-defaults", "POST", "/api/org/designations/seed-defaults", None),
        ("PUT /api/org/designations/{id}", "PUT", f"/api/org/designations/{desig_a}", {"name": "V35Desig", "level": 3}),
        ("POST /api/org/teams", "POST", "/api/org/teams", {"department_id": dept_id, "name": "V35OrgTeamX", "member_user_ids": []}),
        ("POST /api/permissions/seed-defaults", "POST", "/api/permissions/seed-defaults", None),
        ("PUT /api/permission-matrix/rules/bulk", "PUT", "/api/permission-matrix/rules/bulk", {"system_role": "EMPLOYEE", "rules": []}),
        ("POST /api/permission-matrix/seed-defaults", "POST", "/api/permission-matrix/seed-defaults", None),
        ("POST /api/teams", "POST", "/api/teams", {"department_id": dept_id, "name": "V35TeamsApi", "member_user_ids": []}),
        ("PUT /api/teams/{id}", "PUT", f"/api/teams/{team_a}", {"name": "abc"}),
        (
            "PUT /api/teams/.../lead-status",
            "PUT",
            f"/api/teams/{team_a}/members/{member_on_team}/lead-status?is_team_lead=false",
            None,
        ),
    ]
    for label, method, path, body in tests_a:
        m = req(method, path, tok_mgr, body)
        s = req(method, path, tok_sa, body)
        row(label, "A", m, s, "audit" if s == 200 else "—")

    if mod_id:
        acc_body = {"module_id": mod_id, "system_role": "EMPLOYEE", "can_view": True}
        m = req("POST", "/api/permissions/access", tok_mgr, acc_body)
        s = req("POST", "/api/permissions/access", tok_sa, acc_body)
        row("POST /api/permissions/access", "A", m, s, "audit" if s == 200 else "—")
        m = req("POST", "/api/permissions/access/bulk", tok_mgr, {"access_rules": []})
        s = req("POST", "/api/permissions/access/bulk", tok_sa, {"access_rules": []})
        row("POST /api/permissions/access/bulk", "A", m, s, "audit" if s == 200 else "—")
        con = sqlite3.connect(db)
        rid = con.execute(
            "SELECT id FROM module_access WHERE org_id=? AND module_id=? LIMIT 1", (ORG_A, mod_id)
        ).fetchone()
        con.close()
        if rid:
            m = req("DELETE", f"/api/permissions/access/{rid[0]}", tok_mgr, None)
            s = req("DELETE", f"/api/permissions/access/{rid[0]}", tok_sa, None)
            row("DELETE /api/permissions/access/{id}", "A", m, s, "audit" if s in (200, 404) else "—")

    m = req("PUT", f"/api/permissions/user/{other_user}/permissions", tok_mgr, {"plant_id": plant_a})
    s = req("PUT", f"/api/permissions/user/{other_user}/permissions", tok_sa, {"plant_id": plant_a})
    row("PUT /api/permissions/user/.../permissions", "A", m, s, "audit" if s == 200 else "—")

    if disposable_team:
        m = req("DELETE", f"/api/teams/{disposable_team}", tok_mgr, None)
        s = req("DELETE", f"/api/teams/{disposable_team}", tok_sa, None)
        row("DELETE /api/teams/{id}", "A", m, s, "audit" if s == 200 else "—")

    print("endpoint | cat | non-admin | SUPER_ADMIN | audit-note")
    print("---|---|---|---|---")
    for a, b, c, d, e in rows:
        print(f"{a} | {b} | {c} | {d} | {e}")

    bad = [r for r in rows if r[1] == "A" and r[2] == 200]
    if bad:
        print("FAIL: non-admin got 200 on Category A:", bad)
        sys.exit(1)
    ph = req("POST", "/api/org/plants", tok_ph, plant_body)
    print("spot PLANT_HEAD POST /api/org/plants:", ph, "(expect 403)")
    if ph == 200:
        sys.exit(1)

    print("\nCategory B (MANAGER vs HR_HEAD vs SA) — key endpoints")
    u = str(uuid.uuid4())[:8]
    emp_mgr = {"email": f"mgr{u}@test.local", "name": "E", "password": "Welcome@123", "system_role": "EMPLOYEE"}
    emp_hr = {"email": f"hr{u}@test.local", "name": "E", "password": "Welcome@123", "system_role": "EMPLOYEE"}
    emp_sa = {"email": f"sa{u}@test.local", "name": "E", "password": "Welcome@123", "system_role": "EMPLOYEE"}
    print(
        "POST /api/employees mgr/hr/sa:",
        req("POST", "/api/employees", tok_mgr, emp_mgr),
        req("POST", "/api/employees", tok_hr, emp_hr),
        req("POST", "/api/employees", tok_sa, emp_sa),
    )
    print("PUT /api/employees HR system_role change (expect 403):", req("PUT", f"/api/employees/{other_user}", tok_hr, {"system_role": "PLANT_HEAD"}))
    print("POST onboard mgr/hr:", req("POST", "/api/auth/onboard-employee", tok_mgr, {"email": f"x{u}@test.local", "name": "n", "password": "p"}), req("POST", "/api/auth/onboard-employee", tok_hr, {"email": f"y{u}@test.local", "name": "n", "password": "p"}))

    print("\nV3.5b cross-tenant PUT (expect 404) — org B token mutating org A rows")
    print("plant:", req("PUT", f"/api/org/plants/{plant_a}", tok_sa_b, {"name": "x", "location": "L", "code": "c"}))
    print("designation:", req("PUT", f"/api/org/designations/{desig_a}", tok_sa_b, {"name": "x", "level": 1}))
    print("team:", req("PUT", f"/api/teams/{team_a}", tok_sa_b, {"name": "x"}))

    print("\nOK.")


if __name__ == "__main__":
    main()
