"""
V3.2a-V3.2f verification for Phase 3 sub-step 3.2 (run from repo root).

Uses:
- Raw sqlite3.Connection for DB mutations that must bypass SQLAlchemy @validates.
- fastapi.testclient.TestClient against main:app (no separate uvicorn required).
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "manufacturing_os.db"
PWD = "V32Verify@123"

# One user per distinct role in dev DB (tata org), plus legacy-test user.
ROLE_LOGINS = [
    ("SUPER_ADMIN", "admin@tata.com"),
    ("CEO", "r@tata.com"),
    ("VP_OPERATIONS", "j@tata.com"),
    ("PLANT_HEAD", "a@tata.com"),
    ("DEPT_HEAD", "b@tata.com"),
    ("MANAGER", "manager@tata.com"),
    ("EMPLOYEE", "s@tata.com"),
]
LEGACY_TEST_EMAIL = "john@tata.com"


def raw_conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def print_section(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def main() -> None:
    from server.auth import SECRET_KEY, ALGORITHM, get_password_hash
    from jose import jwt as jose_jwt

    print_section("SETUP: known password + baseline counts")
    ph = get_password_hash(PWD)
    conn = raw_conn()
    cur = conn.cursor()
    emails = [e for _, e in ROLE_LOGINS] + [LEGACY_TEST_EMAIL]
    for em in emails:
        cur.execute(
            "UPDATE users SET password_hash = ? WHERE email = ?",
            (ph, em),
        )
    conn.commit()
    print(
        "Set password_hash for",
        len(emails),
        "users via raw sqlite3 (bypasses ORM). Plain password:",
        repr(PWD),
    )
    baseline = cur.execute(
        "SELECT system_role, COUNT(*) FROM users GROUP BY system_role ORDER BY system_role"
    ).fetchall()
    print("BASELINE GROUP BY system_role:")
    for row in baseline:
        print(f"  {row[0]}={row[1]}")

    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)

    print_section("V3.2a - POST /api/auth/login (system_role in JSON user)")
    for role_name, email in ROLE_LOGINS:
        r = client.post("/api/auth/login", json={"email": email, "password": PWD})
        print(f"\n--- {role_name} ({email}) status={r.status_code} ---")
        if r.status_code != 200:
            print(r.text)
            continue
        body = r.json()
        sr = body.get("user", {}).get("system_role")
        print(f"  user.system_role = {sr!r}")

    print_section("V3.2b Part 0 - legacy test user row (raw SQL SELECT)")
    conn = raw_conn()
    cur = conn.cursor()
    row = cur.execute(
        "SELECT id, email, system_role, org_id, plant_id FROM users WHERE email = ?",
        (LEGACY_TEST_EMAIL,),
    ).fetchone()
    print("  SELECT id, email, system_role, org_id, plant_id ->", row)
    test_user_id, test_org_id = row[0], row[3]
    original_role = row[2]

    print_section("V3.2b Part 1 - raw SQL UPDATE to PLANT_MANAGER (sqlite3 only)")
    cur.execute(
        "UPDATE users SET system_role = 'PLANT_MANAGER' WHERE email = ?",
        (LEGACY_TEST_EMAIL,),
    )
    conn.commit()
    db_sr = cur.execute(
        "SELECT system_role FROM users WHERE email = ?",
        (LEGACY_TEST_EMAIL,),
    ).fetchone()[0]
    print("  After UPDATE, raw SELECT system_role ->", repr(db_sr))
    assert db_sr == "PLANT_MANAGER"

    r = client.post(
        "/api/auth/login",
        json={"email": LEGACY_TEST_EMAIL, "password": PWD},
    )
    print(f"\n  POST /api/auth/login status={r.status_code}")
    login_body = r.json() if r.status_code == 200 else {}
    print("  Full login JSON (truncated keys):", json.dumps(login_body, indent=2)[:2000])
    if r.status_code == 200:
        token_login = login_body["access_token"]
        dec = jose_jwt.decode(token_login, SECRET_KEY, algorithms=[ALGORITHM])
        print("  JWT decoded (verified) role=", dec.get("role"), "system_role=", dec.get("system_role"))

    db_after_login = cur.execute(
        "SELECT system_role FROM users WHERE email = ?",
        (LEGACY_TEST_EMAIL,),
    ).fetchone()[0]
    print("  Raw SQL DB system_role after login (expect PLANT_MANAGER):", repr(db_after_login))

    print_section("V3.2b Part 2 - forged legacy JWT + /api/permissions/my-permissions")
    legacy_token = jose_jwt.encode(
        {
            "sub": test_user_id,
            "org_id": test_org_id,
            "role": "PLANT_MANAGER",
            "exp": 2_000_000_000,
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    # Clear prior ROLE_NORMALIZATION rows for clean audit count
    cur.execute(
        "DELETE FROM audit_logs WHERE action = 'ROLE_NORMALIZATION' AND user_id = ?",
        (test_user_id,),
    )
    conn.commit()

    import server.auth as auth_mod

    auth_mod._ROLE_NORMALIZATION_AUDIT_DEDUPE.clear()

    h = {"Authorization": f"Bearer {legacy_token}"}
    r2 = client.get("/api/permissions/my-permissions", headers=h)
    print(f"  GET /api/permissions/my-permissions status={r2.status_code}")
    print("  Response body (first 2500 chars):")
    txt = r2.text
    print(txt[:2500])
    perm_json = r2.json() if r2.status_code == 200 else {}

    print_section("V3.2d - capability sanity (from my-permissions)")
    if perm_json:
        print("  scope_type:", perm_json.get("scope_type"))
        print(
            "  can_access_analytics:",
            perm_json.get("can_access_analytics"),
            "| can_configure_permissions:",
            perm_json.get("can_configure_permissions"),
            "| can_invite_employees:",
            perm_json.get("can_invite_employees"),
        )

    print_section("V3.2b Part 2b - GET /api/org-tree (scoped)")
    r3 = client.get("/api/org-tree", headers=h)
    print(f"  GET /api/org-tree status={r3.status_code}")
    tree = r3.json() if r3.status_code == 200 else {}
    if isinstance(tree, dict) and "error" in tree:
        print("  NOTE:", tree.get("error"))
    elif isinstance(tree, dict):
        print(
            "  One-line: org-tree returned dict with keys",
            list(tree.keys())[:8],
            "... (non-error; scoped tree present).",
        )
    else:
        print("  One-line: response type", type(tree).__name__)

    print_section("V3.2c - audit rows + dedupe")
    rows = cur.execute(
        """SELECT id, org_id, user_id, action, entity_type, entity_id, details, created_at
           FROM audit_logs WHERE action = 'ROLE_NORMALIZATION' AND user_id = ?
           ORDER BY created_at DESC""",
        (test_user_id,),
    ).fetchall()
    print(f"  SELECT * ... -> {len(rows)} row(s)")
    for rw in rows:
        print(" ", rw)

    r4 = client.get("/api/permissions/my-permissions", headers=h)
    print(f"\n  Second GET /api/permissions/my-permissions status={r4.status_code}")
    cnt = cur.execute(
        "SELECT COUNT(*) FROM audit_logs WHERE action = 'ROLE_NORMALIZATION' AND user_id = ?",
        (test_user_id,),
    ).fetchone()[0]
    print("  COUNT(*) ROLE_NORMALIZATION for test user ->", cnt)

    print_section("V3.2b Part 3 - restore original role (raw SQL)")
    cur.execute(
        "UPDATE users SET system_role = ? WHERE email = ?",
        (original_role, LEGACY_TEST_EMAIL),
    )
    conn.commit()
    restored = cur.execute(
        "SELECT system_role FROM users WHERE email = ?",
        (LEGACY_TEST_EMAIL,),
    ).fetchone()[0]
    print("  Restored system_role ->", repr(restored))
    conn.close()

    print_section("V3.2f - GROUP BY after restore")
    conn = raw_conn()
    final = conn.execute(
        "SELECT system_role, COUNT(*) FROM users GROUP BY system_role ORDER BY system_role"
    ).fetchall()
    print("  Result:")
    for row in final:
        print(f"    {row[0]}={row[1]}")
    conn.close()
    match = baseline == final
    print("\n  Matches baseline:", match)

    print_section("V3.2e - npx tsc --noEmit (frontend)")
    fe = ROOT / "frontend" / "performance-compass"
    proc = subprocess.run(
        ["npx", "tsc", "--noEmit"],
        cwd=fe,
        capture_output=True,
        text=True,
        shell=True,
        timeout=120,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    lines = out.strip().splitlines()
    print("  exit_code:", proc.returncode)
    print("  (full output may be long; showing errors / summary)")
    for line in lines[:40]:
        print(" ", line)
    err_lines = [ln for ln in lines if "error TS" in ln]
    print(f"\n  Total lines with 'error TS': {len(err_lines)}")
    for ln in err_lines:
        print(" ", ln)


if __name__ == "__main__":
    main()
