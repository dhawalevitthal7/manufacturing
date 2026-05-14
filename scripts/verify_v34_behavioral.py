"""
V3.4c / V3.4d / V3.4f / V3.4g behavioral verification (TestClient + SQLite).

Run from repository root:

  python scripts/verify_v34_behavioral.py

Uses org ``58ea7177-3d39-49ad-abe6-8d1dbac7f1da`` (user-facing shorthand 58ea177…).
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from typing import Any

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from main import app  # noqa: E402
from server.auth import create_access_token, get_password_hash, _canonical_role_for_token  # noqa: E402
from server.database import SessionLocal  # noqa: E402
from server.models import User  # noqa: E402
from server.permissions_service import initialize_user_permissions  # noqa: E402
from server.roles import SystemRole  # noqa: E402

ORG_ID = "58ea7177-3d39-49ad-abe6-8d1dbac7f1da"
REGION_SOUTH_ID = "1734cfb4-f123-4f05-8853-9938cb990355"
PLANT_PUNE_ID = "28b56b64-b156-44ca-942f-ff2dc2576b1a"
TEAM_ORG_NODE_ID = "8758b45e-c4f0-432f-96f6-7df9245e89c5"

DB_PATH = os.path.join(_REPO, "manufacturing_os.db")

ROLE_USER_EMAILS: dict[SystemRole, str] = {
    SystemRole.SUPER_ADMIN: "admin@tata.com",
    SystemRole.CEO: "r@tata.com",
    SystemRole.VP_OPERATIONS: "j@tata.com",
    SystemRole.PLANT_HEAD: "a@tata.com",
    SystemRole.DEPT_HEAD: "b@tata.com",
    SystemRole.MANAGER: "rajesh@tata.com",
    SystemRole.EMPLOYEE: "s@tata.com",
}


def _sqlite_counts() -> dict[str, int]:
    c = sqlite3.connect(DB_PATH)
    try:
        return {
            "users": c.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "profiles": c.execute("SELECT COUNT(*) FROM user_permission_profiles").fetchone()[0],
            "regions": c.execute(
                "SELECT COUNT(*) FROM org_nodes WHERE node_type='REGION'"
            ).fetchone()[0],
        }
    finally:
        c.close()


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(
        {
            "sub": user.id,
            "org_id": user.org_id,
            "role": _canonical_role_for_token(user.system_role),
        }
    )
    return {"Authorization": f"Bearer {token}"}


def _compact_profile_row(role: SystemRole, data: dict[str, Any]) -> str:
    mods = data.get("modules") or []
    mod_keys = [m.get("module_key", "?") for m in mods[:3]]
    scoped: list[str] = []
    for k in ("scoped_plant_id", "scoped_department_id", "scoped_team_id", "scoped_region_id"):
        v = data.get(k)
        if v:
            short = k.replace("scoped_", "").replace("_id", "")
            scoped.append(f"{short}={v[:8]}…")
    scoped_s = ",".join(scoped) if scoped else "-"
    return (
        f"{role.value} | {data.get('scope_type')} | {scoped_s} | "
        f"{data.get('can_view_all_employees')} | {data.get('can_access_audit_logs')} | "
        f"{', '.join(mod_keys)}"
    )


def _ensure_temp_users(db) -> None:
    hp = get_password_hash("V34test!")
    specs: list[tuple[str, str, str, str | None, str | None, str | None]] = [
        ("v34c_teamlead@test.local", "V34 TeamLead", "TEAM_LEAD", TEAM_ORG_NODE_ID, None, None),
        ("v34c_supervisor@test.local", "V34 Supervisor", "SUPERVISOR", TEAM_ORG_NODE_ID, None, None),
        ("v34c_hrhead@test.local", "V34 HR", "HR_HEAD", ORG_ID, None, None),
        ("v34c_regional@test.local", "V34 Regional C", "REGIONAL_HEAD", REGION_SOUTH_ID, None, None),
        ("v34c_cfo@test.local", "V34 CFO", "CFO", ORG_ID, None, None),
        ("v34c_cmo@test.local", "V34 CMO", "CMO", ORG_ID, None, None),
        ("v34c_cto@test.local", "V34 CTO", "CTO", ORG_ID, None, None),
        ("v34d_rh@test.local", "V34d RH", "REGIONAL_HEAD", REGION_SOUTH_ID, None, None),
        ("v34d_rh_edge@test.local", "V34d RH Edge", "REGIONAL_HEAD", None, None, None),
    ]
    for email, name, role_s, org_node_id, plant_id, team_id in specs:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            continue
        u = User(
            org_id=ORG_ID,
            email=email,
            password_hash=hp,
            name=name,
            system_role=role_s,
            is_active=True,
            org_node_id=org_node_id,
            plant_id=plant_id,
            team_id=team_id,
        )
        db.add(u)
        db.flush()
        db.refresh(u)
        initialize_user_permissions(u, db)
    db.commit()


def _user_by_email(db, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def main() -> int:
    counts_before = _sqlite_counts()
    print("=== COUNTS BEFORE ===", counts_before)

    db = SessionLocal()
    try:
        _ensure_temp_users(db)
    finally:
        db.close()

    client = TestClient(app)

    db = SessionLocal()
    try:
        print("\n=== V3.4c Per-role GET /api/permissions/my-permissions ===\n")
        failures: list[str] = []
        admin = _user_by_email(db, "admin@tata.com")
        if not admin:
            failures.append("No admin@tata.com")
        else:
            client.get("/api/permissions/modules", headers=_auth_headers(admin))
        for role in SystemRole:
            email = ROLE_USER_EMAILS.get(role)
            if email is None:
                mapping = {
                    SystemRole.TEAM_LEAD: "v34c_teamlead@test.local",
                    SystemRole.SUPERVISOR: "v34c_supervisor@test.local",
                    SystemRole.HR_HEAD: "v34c_hrhead@test.local",
                    SystemRole.REGIONAL_HEAD: "v34c_regional@test.local",
                    SystemRole.CFO: "v34c_cfo@test.local",
                    SystemRole.CMO: "v34c_cmo@test.local",
                    SystemRole.CTO: "v34c_cto@test.local",
                }
                email = mapping.get(role)
            if not email:
                failures.append(f"No user mapped for {role}")
                continue
            user = _user_by_email(db, email)
            if not user:
                failures.append(f"Missing user {email} for {role}")
                continue
            initialize_user_permissions(user, db)
            db.refresh(user)
            r = client.get(
                "/api/permissions/my-permissions",
                headers=_auth_headers(user),
            )
            if r.status_code != 200:
                failures.append(f"{role.value} HTTP {r.status_code} {r.text[:200]}")
                continue
            data = r.json()
            print(_compact_profile_row(role, data))

            if role == SystemRole.CEO:
                if not (data["can_view_all_employees"] and data["can_access_audit_logs"]):
                    failures.append(f"CEO flags wrong: {data}")
            elif role == SystemRole.HR_HEAD:
                if not data["can_access_audit_logs"]:
                    failures.append(f"HR_HEAD audit: {data}")
            elif role == SystemRole.REGIONAL_HEAD and email == "v34c_regional@test.local":
                if data["scope_type"] != "REGION" or not data.get("scoped_region_id"):
                    failures.append(f"REGIONAL_HEAD scope: {data}")
            elif role == SystemRole.CFO:
                if not data["can_access_audit_logs"]:
                    failures.append(f"CFO audit: {data}")
            elif role == SystemRole.CMO:
                if data["can_access_audit_logs"]:
                    failures.append(f"CMO audit should False: {data}")
            elif role == SystemRole.CTO:
                if data["can_access_audit_logs"]:
                    failures.append(f"CTO audit should False: {data}")
            elif role == SystemRole.EMPLOYEE:
                if data["scope_type"] != "INDIVIDUAL":
                    failures.append(f"EMPLOYEE scope: {data}")

        if failures:
            print("\n*** V3.4c FAILURES ***")
            for f in failures:
                print(" ", f)
            return 1

        print("\n=== V3.4d REGIONAL_HEAD scope ===\n")
        rh = _user_by_email(db, "v34d_rh@test.local")
        if not rh:
            print("MISSING v34d_rh user")
            return 1
        initialize_user_permissions(rh, db)
        db.refresh(rh)
        row = db.execute(
            text(
                "SELECT scope_type, scoped_region_id FROM user_permission_profiles "
                "WHERE user_id = :uid"
            ),
            {"uid": rh.id},
        ).fetchone()
        print("SQL profile (v34d_rh):", row)
        if row[0] != "REGION" or row[1] != REGION_SOUTH_ID:
            print("FAIL: profile row mismatch")
            return 1

        hdr = _auth_headers(rh)

        t1 = client.get("/api/org-tree", headers=hdr)
        print("Test1 GET /api/org-tree status:", t1.status_code)
        body = t1.json()
        print("Test1 body (truncated):", json.dumps(body)[:1200])

        def _root_summary(tree: Any) -> list[dict]:
            if isinstance(tree, dict) and "roots" in tree:
                return [
                    {"id": r.get("id"), "node_type": r.get("node_type"), "name": r.get("name")}
                    for r in (tree.get("roots") or [])
                ]
            if isinstance(tree, dict) and tree.get("id"):
                return [{"id": tree.get("id"), "node_type": tree.get("node_type"), "name": tree.get("name")}]
            return []

        roots = _root_summary(body)
        print("Test1 root node ids/types:", json.dumps(roots))

        t2 = client.get(f"/api/org-tree/{REGION_SOUTH_ID}", headers=hdr)
        print("Test2 inside region (region id) status:", t2.status_code)

        t3 = client.get(f"/api/org-tree/{PLANT_PUNE_ID}", headers=hdr)
        print("Test3 outside region (pune plant) status:", t3.status_code)

        t4 = client.get(f"/api/org-tree/{REGION_SOUTH_ID}", headers=hdr)
        print("Test4 region self status:", t4.status_code)

        edge = _user_by_email(db, "v34d_rh_edge@test.local")
        if not edge:
            print("MISSING edge user")
            return 1
        db.execute(
            text("UPDATE user_permission_profiles SET scoped_region_id = NULL WHERE user_id = :uid"),
            {"uid": edge.id},
        )
        db.execute(
            text("UPDATE users SET org_node_id = NULL WHERE id = :uid"),
            {"uid": edge.id},
        )
        db.commit()
        db.refresh(edge)
        edge_hdr = _auth_headers(edge)
        t5 = client.get("/api/org-tree", headers=edge_hdr)
        print("Test5 edge GET /api/org-tree status:", t5.status_code)
        print("Test5 edge body:", json.dumps(t5.json())[:800])

        if t2.status_code != 200 or t4.status_code != 200:
            print("FAIL: expected 200 for in-region node")
            return 1
        if t3.status_code != 403:
            print("FAIL: expected 403 for plant outside region, got", t3.status_code)
            return 1
        if t1.status_code != 200:
            print("FAIL org-tree")
            return 1
        if len(roots) != 1 or roots[0].get("id") != REGION_SOUTH_ID:
            print("FAIL: expected single root = south India region", roots)
            return 1

        print("\n=== V3.4f seed-defaults + module_access ===\n")
        admin = _user_by_email(db, "admin@tata.com")
        if not admin:
            print("No SUPER_ADMIN admin@tata.com")
            return 1
        sf = client.post(
            "/api/permissions/seed-defaults",
            headers=_auth_headers(admin),
        )
        print("seed-defaults status:", sf.status_code, sf.text[:500])
        cx = sqlite3.connect(DB_PATH)
        try:
            roles = [
                r[0]
                for r in cx.execute(
                    "SELECT DISTINCT system_role FROM module_access "
                    "WHERE system_role IS NOT NULL ORDER BY 1"
                )
            ]
            print("DISTINCT system_role:", roles)
            for s in roles:
                if str(s).startswith("SystemRole"):
                    print("FAIL: non-canonical repr in module_access:", s)
                    return 1
        finally:
            cx.close()

    finally:
        db.close()

    print("\n=== V3.4g CLEANUP ===\n")
    counts_pre_del = _sqlite_counts()
    cx = sqlite3.connect(DB_PATH)
    try:
        stmts = [
            "DELETE FROM user_permission_profiles WHERE user_id IN "
            "(SELECT id FROM users WHERE email LIKE 'v34%')",
            "DELETE FROM users WHERE email LIKE 'v34%'",
        ]
        for s in stmts:
            print("EXEC:", s)
            cx.execute(s)
        cx.commit()
    finally:
        cx.close()
    counts_after = _sqlite_counts()
    print("users before/after cleanup:", counts_pre_del["users"], counts_after["users"])
    print("profiles before/after:", counts_pre_del["profiles"], counts_after["profiles"])
    print("regions (all orgs) before/after:", counts_pre_del["regions"], counts_after["regions"])

    print("\nDONE — V3.4c/d/f/g evidence complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
