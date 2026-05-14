"""
Canonical system roles and normalization (Phase 3).

Single source of truth for role strings used in authorization and OKR gating.
Legacy DB/JWT values are normalized on read; see LEGACY_ROLE_ALIASES.
"""

from __future__ import annotations

import enum
import logging
from typing import Final, Mapping

logger = logging.getLogger(__name__)


class SystemRole(str, enum.Enum):
    """Platform + business hierarchy roles stored canonically after normalization."""

    SUPER_ADMIN = "SUPER_ADMIN"
    CEO = "CEO"
    VP_OPERATIONS = "VP_OPERATIONS"
    REGIONAL_HEAD = "REGIONAL_HEAD"
    PLANT_HEAD = "PLANT_HEAD"
    DEPT_HEAD = "DEPT_HEAD"
    MANAGER = "MANAGER"
    TEAM_LEAD = "TEAM_LEAD"
    SUPERVISOR = "SUPERVISOR"
    EMPLOYEE = "EMPLOYEE"
    HR_HEAD = "HR_HEAD"
    CFO = "CFO"
    CMO = "CMO"
    CTO = "CTO"


# SUPER_ADMIN is intentionally absent: platform role, not a business hierarchy level.
ROLE_TO_BUSINESS_LEVEL: Final[Mapping[SystemRole, int]] = {
    SystemRole.CEO: 0,
    SystemRole.CFO: 1,
    SystemRole.CMO: 1,
    SystemRole.CTO: 1,
    SystemRole.HR_HEAD: 1,
    SystemRole.VP_OPERATIONS: 1,
    SystemRole.REGIONAL_HEAD: 1,
    SystemRole.PLANT_HEAD: 2,
    SystemRole.DEPT_HEAD: 3,
    SystemRole.MANAGER: 4,
    SystemRole.TEAM_LEAD: 5,
    SystemRole.SUPERVISOR: 5,
    SystemRole.EMPLOYEE: 6,
}

LEGACY_ROLE_ALIASES: Final[dict[str, SystemRole]] = {
    "VP_MANUFACTURING": SystemRole.VP_OPERATIONS,
    "OPERATIONS_HEAD": SystemRole.PLANT_HEAD,
    "OPERATOR": SystemRole.EMPLOYEE,
    "TECHNICIAN": SystemRole.EMPLOYEE,
    "INSPECTOR": SystemRole.EMPLOYEE,
    "HR_ADMIN": SystemRole.HR_HEAD,
    "PLANT_MANAGER": SystemRole.PLANT_HEAD,
    "FACTORY_DIRECTOR": SystemRole.PLANT_HEAD,
}


def get_business_level(role: SystemRole) -> int | None:
    """Return business hierarchy level, or None for SUPER_ADMIN (no business level)."""
    return ROLE_TO_BUSINESS_LEVEL.get(role)


# OKR objective levels (hierarchy API / Objective.level). Order used for API lists.
OBJECTIVE_LEVEL_ORDER: Final[tuple[str, ...]] = (
    "ORGANIZATION",
    "PLANT",
    "DEPARTMENT",
    "TEAM",
    "INDIVIDUAL",
)

# Migrated from okr_hierarchy_workflow.ROLE_CREATION_LEVELS (canonical SystemRole keys).
# SUPER_ADMIN and CEO are handled by executive bypass in can_create_objective_at_level.
# REGIONAL_HEAD aligns with VP_OPERATIONS. CFO/CMO/CTO: corporate function heads -> DEPARTMENT only.
ROLE_TO_ALLOWED_OBJECTIVE_LEVELS: Final[Mapping[SystemRole, frozenset[str]]] = {
    SystemRole.VP_OPERATIONS: frozenset({"PLANT", "DEPARTMENT"}),
    SystemRole.REGIONAL_HEAD: frozenset({"PLANT", "DEPARTMENT"}),
    SystemRole.PLANT_HEAD: frozenset({"PLANT", "DEPARTMENT", "TEAM"}),
    SystemRole.DEPT_HEAD: frozenset({"DEPARTMENT", "TEAM"}),
    SystemRole.MANAGER: frozenset({"TEAM", "INDIVIDUAL"}),
    SystemRole.TEAM_LEAD: frozenset({"INDIVIDUAL"}),
    SystemRole.SUPERVISOR: frozenset({"INDIVIDUAL"}),
    SystemRole.EMPLOYEE: frozenset(),
    SystemRole.HR_HEAD: frozenset(),
    SystemRole.CFO: frozenset({"DEPARTMENT"}),
    SystemRole.CMO: frozenset({"DEPARTMENT"}),
    SystemRole.CTO: frozenset({"DEPARTMENT"}),
}


def allowed_objective_levels_for(role: SystemRole) -> list[str]:
    """Sorted objective levels the role may create (API / UI). CEO and SUPER_ADMIN: all five."""
    if role in (SystemRole.SUPER_ADMIN, SystemRole.CEO):
        return list(OBJECTIVE_LEVEL_ORDER)
    allowed = ROLE_TO_ALLOWED_OBJECTIVE_LEVELS.get(role, frozenset())
    return [lvl for lvl in OBJECTIVE_LEVEL_ORDER if lvl in allowed]


def can_create_objective_at_level(role: SystemRole, objective_level: str) -> bool:
    """
    Whether ``role`` may create an OKR whose ``Objective.level`` is ``objective_level``.

    Executive bypass: SUPER_ADMIN and CEO may create at any objective level.
    Other roles: truth table ``ROLE_TO_ALLOWED_OBJECTIVE_LEVELS`` (from legacy hierarchy workflow).
    """
    lvl = (objective_level or "").strip().upper()
    if lvl not in OBJECTIVE_LEVEL_ORDER:
        return False
    if role in (SystemRole.SUPER_ADMIN, SystemRole.CEO):
        return True
    return lvl in ROLE_TO_ALLOWED_OBJECTIVE_LEVELS.get(role, frozenset())


def can_create_okr_at_level(
    role: SystemRole,
    user_business_level: int | None,
    target_level: int,
) -> bool:
    """
    Whether role may create an OKR anchored at the given business level.

    SUPER_ADMIN bypasses business-level gating. Others need a business level
    and may create at their level or one step below, capped at the deepest
    business level (EMPLOYEE) so there is no phantom level below individual.
    """
    if role == SystemRole.SUPER_ADMIN:
        return True
    if user_business_level is None:
        return False
    max_level = max(ROLE_TO_BUSINESS_LEVEL.values())
    if target_level < 0 or target_level > max_level:
        return False
    return target_level in (user_business_level, user_business_level + 1)


def normalize_role(raw: str) -> SystemRole:
    """
    Map raw system_role (DB/JWT) to SystemRole.

    Unknown strings become EMPLOYEE (minimum privileges) with a WARNING log.
    """
    s = (raw or "").strip()
    if not s:
        logger.warning(
            "Empty system_role; normalizing to EMPLOYEE (minimum privileges)."
        )
        return SystemRole.EMPLOYEE
    try:
        return SystemRole(s)
    except ValueError:
        pass
    mapped = LEGACY_ROLE_ALIASES.get(s)
    if mapped is not None:
        return mapped
    logger.warning(
        "Unknown system_role %r; normalizing to EMPLOYEE (minimum privileges).",
        s,
    )
    return SystemRole.EMPLOYEE


def normalize_role_strict(raw: str) -> SystemRole:
    """
    Same as normalize_role but raises ValueError for unknown input.

    For tests and offline verification only — not for request handling.
    """
    s = (raw or "").strip()
    if not s:
        raise ValueError("Empty system_role")
    try:
        return SystemRole(s)
    except ValueError:
        pass
    if s in LEGACY_ROLE_ALIASES:
        return LEGACY_ROLE_ALIASES[s]
    raise ValueError(f"Unknown system_role: {raw!r}")


__all__ = [
    "SystemRole",
    "LEGACY_ROLE_ALIASES",
    "OBJECTIVE_LEVEL_ORDER",
    "ROLE_TO_ALLOWED_OBJECTIVE_LEVELS",
    "ROLE_TO_BUSINESS_LEVEL",
    "allowed_objective_levels_for",
    "can_create_objective_at_level",
    "can_create_okr_at_level",
    "get_business_level",
    "normalize_role",
    "normalize_role_strict",
]
