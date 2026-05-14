"""
Verify server.roles (Phase 3.1). Run from repository root:

  python scripts/verify_roles_module.py
"""

from __future__ import annotations

import os
import sqlite3
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from server.roles import (  # noqa: E402
    LEGACY_ROLE_ALIASES,
    OBJECTIVE_LEVEL_ORDER,
    ROLE_TO_ALLOWED_OBJECTIVE_LEVELS,
    ROLE_TO_BUSINESS_LEVEL,
    SystemRole,
    allowed_objective_levels_for,
    can_create_objective_at_level,
    can_create_okr_at_level,
    get_business_level,
    normalize_role,
    normalize_role_strict,
)

# Union of role literals from backend grep (c), frontend grep (d), and Phase 3
# strings that appear in OKR / cascade code paths but had zero quoted hits.
REQUIRED_RAW_ROLE_STRINGS = frozenset(
    {
        "SUPER_ADMIN",
        "CEO",
        "VP_OPERATIONS",
        "VP_MANUFACTURING",
        "REGIONAL_HEAD",
        "PLANT_HEAD",
        "PLANT_MANAGER",
        "DEPT_HEAD",
        "MANAGER",
        "TEAM_LEAD",
        "SUPERVISOR",
        "EMPLOYEE",
        "HR_HEAD",
        "HR_ADMIN",
        "CFO",
        "CMO",
        "CTO",
        "OPERATIONS_HEAD",
        "FACTORY_DIRECTOR",
        "OPERATOR",
        "TECHNICIAN",
        "INSPECTOR",
    }
)


def _canonical_values() -> set[str]:
    return {e.value for e in SystemRole}


def main() -> int:
    errors: list[str] = []

    # Every alias value is a valid SystemRole member (typo guard).
    for key, val in LEGACY_ROLE_ALIASES.items():
        if not isinstance(val, SystemRole):
            errors.append(f"LEGACY_ROLE_ALIASES[{key!r}] is not a SystemRole: {val!r}")

    # LEGACY keys must not duplicate canonical enum strings (aliases only).
    canon = _canonical_values()
    for key in LEGACY_ROLE_ALIASES:
        if key in canon:
            errors.append(f"LEGACY_ROLE_ALIASES must not list canonical key {key!r}")

    # Superset: every required raw string is either canonical or has an alias.
    covered = canon | set(LEGACY_ROLE_ALIASES.keys())
    for s in sorted(REQUIRED_RAW_ROLE_STRINGS):
        if s not in covered:
            errors.append(f"MISSING ALIAS OR ENUM: {s!r} (add to SystemRole or LEGACY_ROLE_ALIASES)")

    db_path = os.path.join(_REPO, "manufacturing_os.db")
    db_roles: set[str] = set()
    if os.path.isfile(db_path):
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        cur.execute("SELECT DISTINCT system_role FROM users WHERE system_role IS NOT NULL")
        db_roles = {row[0] for row in cur.fetchall()}
        con.close()
        for s in sorted(db_roles):
            if s not in covered:
                errors.append(f"MISSING ALIAS OR ENUM (from DB): {s!r}")
            try:
                normalize_role_strict(s)
            except ValueError as exc:
                errors.append(f"DB role {s!r}: {exc}")

    if errors:
        print("verify_roles_module: FAILED")
        for e in errors:
            print(" ", e)
        return 1

    if db_roles:
        print("verify_roles_module: DB distinct system_role values:", sorted(db_roles))
    elif os.path.isfile(db_path):
        print("verify_roles_module: DB had no user system_role rows")
    else:
        print("verify_roles_module: no manufacturing_os.db; skipped DB role check")

    for s in LEGACY_ROLE_ALIASES:
        normalize_role_strict(s)
    for s in canon:
        normalize_role_strict(s)

    if os.path.isfile(db_path):
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        cur.execute("SELECT DISTINCT system_role FROM users WHERE system_role IS NOT NULL")
        for (sr,) in cur.fetchall():
            r = normalize_role(sr)
            assert isinstance(r, SystemRole)
        con.close()

    assert get_business_level(SystemRole.SUPER_ADMIN) is None
    assert get_business_level(SystemRole.CEO) == 0

    # can_create_okr_at_level matrix (business levels from ROLE_TO_BUSINESS_LEVEL).
    assert can_create_okr_at_level(SystemRole.CEO, 0, 0) is True
    assert can_create_okr_at_level(SystemRole.CEO, 0, 1) is True
    assert can_create_okr_at_level(SystemRole.CEO, 0, 2) is False

    assert can_create_okr_at_level(SystemRole.PLANT_HEAD, 2, 2) is True
    assert can_create_okr_at_level(SystemRole.PLANT_HEAD, 2, 3) is True
    assert can_create_okr_at_level(SystemRole.PLANT_HEAD, 2, 1) is False

    assert can_create_okr_at_level(SystemRole.EMPLOYEE, 6, 6) is True
    assert can_create_okr_at_level(SystemRole.EMPLOYEE, 6, 7) is False

    assert can_create_okr_at_level(SystemRole.MANAGER, None, 4) is False
    assert can_create_okr_at_level(SystemRole.SUPER_ADMIN, None, 99) is True
    assert can_create_okr_at_level(SystemRole.SUPER_ADMIN, None, 0) is True

    # --- can_create_objective_at_level (Phase 3.3 truth table) ---
    for lvl in OBJECTIVE_LEVEL_ORDER:
        assert can_create_objective_at_level(SystemRole.SUPER_ADMIN, lvl) is True
        assert can_create_objective_at_level(SystemRole.CEO, lvl) is True

    assert can_create_objective_at_level(SystemRole.REGIONAL_HEAD, "PLANT") is True
    assert can_create_objective_at_level(SystemRole.REGIONAL_HEAD, "DEPARTMENT") is True
    assert can_create_objective_at_level(SystemRole.REGIONAL_HEAD, "ORGANIZATION") is False

    for lvl in OBJECTIVE_LEVEL_ORDER:
        assert can_create_objective_at_level(SystemRole.EMPLOYEE, lvl) is False

    assert can_create_objective_at_level(SystemRole.VP_OPERATIONS, "PLANT") is True
    assert can_create_objective_at_level(SystemRole.VP_OPERATIONS, "DEPARTMENT") is True
    assert can_create_objective_at_level(SystemRole.VP_OPERATIONS, "ORGANIZATION") is False

    assert can_create_objective_at_level(SystemRole.PLANT_HEAD, "TEAM") is True
    assert can_create_objective_at_level(SystemRole.PLANT_HEAD, "ORGANIZATION") is False

    assert can_create_objective_at_level(SystemRole.DEPT_HEAD, "TEAM") is True
    assert can_create_objective_at_level(SystemRole.DEPT_HEAD, "PLANT") is False

    assert can_create_objective_at_level(SystemRole.MANAGER, "TEAM") is True
    assert can_create_objective_at_level(SystemRole.MANAGER, "PLANT") is False

    assert can_create_objective_at_level(SystemRole.TEAM_LEAD, "INDIVIDUAL") is True
    assert can_create_objective_at_level(SystemRole.TEAM_LEAD, "TEAM") is False

    assert can_create_objective_at_level(SystemRole.SUPERVISOR, "INDIVIDUAL") is True
    assert can_create_objective_at_level(SystemRole.SUPERVISOR, "TEAM") is False

    for r, expected in ROLE_TO_ALLOWED_OBJECTIVE_LEVELS.items():
        for lvl in OBJECTIVE_LEVEL_ORDER:
            assert can_create_objective_at_level(r, lvl) == (lvl in expected)

    assert allowed_objective_levels_for(SystemRole.CEO) == list(OBJECTIVE_LEVEL_ORDER)
    assert allowed_objective_levels_for(SystemRole.MANAGER) == ["TEAM", "INDIVIDUAL"]
    assert allowed_objective_levels_for(SystemRole.HR_HEAD) == []

    print("verify_roles_module: OK")
    print("  SystemRole count:", len(SystemRole))
    print("  LEGACY_ROLE_ALIASES count:", len(LEGACY_ROLE_ALIASES))
    print("  ROLE_TO_BUSINESS_LEVEL keys:", len(ROLE_TO_BUSINESS_LEVEL))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
