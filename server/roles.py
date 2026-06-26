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
    CHRO = "CHRO"
    COO = "COO"
    CRO = "CRO"
    CFO = "CFO"
    CMO = "CMO"
    CPO = "CPO"
    CSO = "CSO"
    CTO = "CTO"
    FUNCTIONAL_SUB_HEAD = "FUNCTIONAL_SUB_HEAD"
    AREA_SALES_MANAGER = "AREA_SALES_MANAGER"


# SUPER_ADMIN is intentionally absent: platform role, not a business hierarchy level.
ROLE_TO_BUSINESS_LEVEL: Final[Mapping[SystemRole, int]] = {
    SystemRole.CEO: 0,
    SystemRole.CFO: 1,
    SystemRole.CMO: 1,
    SystemRole.CTO: 1,
    SystemRole.CPO: 1,
    SystemRole.CSO: 1,
    SystemRole.HR_HEAD: 1,
    SystemRole.CHRO: 1,
    SystemRole.VP_OPERATIONS: 1,
    SystemRole.COO: 1,
    SystemRole.CRO: 1,
    SystemRole.REGIONAL_HEAD: 1,
    SystemRole.FUNCTIONAL_SUB_HEAD: 2,
    SystemRole.PLANT_HEAD: 2,
    SystemRole.AREA_SALES_MANAGER: 3,
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

# Functional-head roles that may act as functional (dotted-line) approvers.
FUNCTIONAL_APPROVER_ROLES: Final[frozenset[SystemRole]] = frozenset({
    SystemRole.COO,
    SystemRole.CRO,
    SystemRole.CFO,
    SystemRole.CMO,
    SystemRole.CHRO,
    SystemRole.HR_HEAD,
    SystemRole.CPO,
    SystemRole.CSO,
    SystemRole.CTO,
})


def get_business_level(role: SystemRole) -> int | None:
    """Return business hierarchy level, or None for SUPER_ADMIN (no business level)."""
    return ROLE_TO_BUSINESS_LEVEL.get(role)


# OKR objective levels (hierarchy API / Objective.level). Order used for API lists.
OBJECTIVE_LEVEL_ORDER: Final[tuple[str, ...]] = (
    "ORGANIZATION",
    "VERTICAL",
    "REGION",
    "PLANT",
    "DEPARTMENT",
    "SUB_DEPARTMENT",
    "TEAM",
    "INDIVIDUAL",
)

# Adjacent hierarchy level for AI cascade (generic engine).
CASCADE_CHILD_LEVEL: Final[dict[str, str]] = {
    "ORGANIZATION": "REGION",
    "VERTICAL": "REGION",
    "REGION": "PLANT",
    "PLANT": "DEPARTMENT",
    "DEPARTMENT": "TEAM",
    "SUB_DEPARTMENT": "TEAM",
    "TEAM": "INDIVIDUAL",
}

# Every parent level with a defined child in CASCADE_CHILD_LEVEL may trigger AI cascade.
AI_CASCADE_ENABLED_PARENT_LEVELS: Final[frozenset[str]] = frozenset(CASCADE_CHILD_LEVEL.keys())


def next_cascade_child_level(parent_level: str) -> str | None:
    """Return the child objective level for AI cascade, or None if not cascadable."""
    return CASCADE_CHILD_LEVEL.get((parent_level or "").strip().upper())


def is_ai_cascade_enabled(parent_level: str) -> bool:
    """Whether AI cascade is enabled for this parent objective level."""
    return (parent_level or "").strip().upper() in AI_CASCADE_ENABLED_PARENT_LEVELS

# Migrated from okr_hierarchy_workflow.ROLE_CREATION_LEVELS (canonical SystemRole keys).
# SUPER_ADMIN and CEO are handled by executive bypass in can_create_objective_at_level.
# REGIONAL_HEAD aligns with VP_OPERATIONS. CFO/CMO/CTO: corporate function heads -> DEPARTMENT only.
ROLE_TO_ALLOWED_OBJECTIVE_LEVELS: Final[Mapping[SystemRole, frozenset[str]]] = {
    SystemRole.VP_OPERATIONS: frozenset({"REGION", "PLANT", "DEPARTMENT"}),
    SystemRole.COO: frozenset({"ORGANIZATION", "VERTICAL", "PLANT", "DEPARTMENT"}),
    SystemRole.CRO: frozenset({"ORGANIZATION", "VERTICAL", "REGION", "DEPARTMENT"}),
    SystemRole.REGIONAL_HEAD: frozenset({"REGION", "PLANT", "DEPARTMENT"}),
    SystemRole.PLANT_HEAD: frozenset({"PLANT", "DEPARTMENT", "TEAM"}),
    SystemRole.DEPT_HEAD: frozenset({"DEPARTMENT", "TEAM"}),
    SystemRole.MANAGER: frozenset({"TEAM", "INDIVIDUAL"}),
    SystemRole.TEAM_LEAD: frozenset({"INDIVIDUAL"}),
    SystemRole.SUPERVISOR: frozenset({"INDIVIDUAL"}),
    SystemRole.EMPLOYEE: frozenset(),
    SystemRole.HR_HEAD: frozenset({"ORGANIZATION", "VERTICAL", "DEPARTMENT"}),
    SystemRole.CHRO: frozenset({"ORGANIZATION", "VERTICAL", "DEPARTMENT"}),
    SystemRole.CFO: frozenset({"ORGANIZATION", "VERTICAL", "DEPARTMENT"}),
    SystemRole.CMO: frozenset({"ORGANIZATION", "VERTICAL", "DEPARTMENT"}),
    SystemRole.CPO: frozenset({"ORGANIZATION", "VERTICAL"}),
    SystemRole.CSO: frozenset({"ORGANIZATION", "VERTICAL"}),
    SystemRole.CTO: frozenset({"DEPARTMENT"}),
    SystemRole.FUNCTIONAL_SUB_HEAD: frozenset({"VERTICAL", "SUB_DEPARTMENT"}),
    SystemRole.AREA_SALES_MANAGER: frozenset({"TEAM", "INDIVIDUAL"}),
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


def objective_level_to_business_level(objective_level: str) -> int | None:
    """Map ``Objective.level`` to business hierarchy depth (see Phase 6 lifecycle)."""
    mapping = {
        "ORGANIZATION": 0,
        "VERTICAL": 1,
        "REGION": 1,
        "PLANT": 2,
        "DEPARTMENT": 3,
        "SUB_DEPARTMENT": 3,
        "TEAM": 4,
        "INDIVIDUAL": 6,
    }
    return mapping.get((objective_level or "").strip().upper())


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
    "FUNCTIONAL_APPROVER_ROLES",
    "LEGACY_ROLE_ALIASES",
    "OBJECTIVE_LEVEL_ORDER",
    "CASCADE_CHILD_LEVEL",
    "AI_CASCADE_ENABLED_PARENT_LEVELS",
    "next_cascade_child_level",
    "is_ai_cascade_enabled",
    "ROLE_TO_ALLOWED_OBJECTIVE_LEVELS",
    "ROLE_TO_BUSINESS_LEVEL",
    "allowed_objective_levels_for",
    "can_create_objective_at_level",
    "can_create_okr_at_level",
    "objective_level_to_business_level",
    "get_business_level",
    "normalize_role",
    "normalize_role_strict",
]
