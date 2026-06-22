"""
Corporate function tagging for vertical OKRs and function-scoped visibility.

function_area values align functional heads to their corporate vertical:
OPERATIONS, FINANCE, HR, SALES_MARKETING, PROCUREMENT, TECHNICAL, REGIONS.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from server.models import Objective, OrgNode, ReportingRelationship, User
from server.roles import SystemRole, normalize_role, FUNCTIONAL_APPROVER_ROLES

FUNCTION_AREAS: Tuple[str, ...] = (
    "OPERATIONS",
    "FINANCE",
    "HR",
    "SALES_MARKETING",
    "PROCUREMENT",
    "TECHNICAL",
    "REGIONS",
)

ROLE_TO_FUNCTION_AREA: Dict[SystemRole, str] = {
    SystemRole.COO: "OPERATIONS",
    SystemRole.CFO: "FINANCE",
    SystemRole.CHRO: "HR",
    SystemRole.HR_HEAD: "HR",
    SystemRole.CMO: "SALES_MARKETING",
    SystemRole.CPO: "PROCUREMENT",
    SystemRole.CSO: "TECHNICAL",
    SystemRole.CRO: "REGIONS",
}

FUNCTION_AREA_LABELS: Dict[str, str] = {
    "OPERATIONS": "Operations",
    "FINANCE": "Finance",
    "HR": "HR & IR",
    "SALES_MARKETING": "Sales & Marketing",
    "PROCUREMENT": "Procurement & SCM",
    "TECHNICAL": "Technical / Quality / HSE",
    "REGIONS": "Regions",
}


def normalize_function_area(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    val = raw.strip().upper()
    return val if val in FUNCTION_AREAS else None


def function_area_for_role(role: SystemRole) -> Optional[str]:
    return ROLE_TO_FUNCTION_AREA.get(role)


def function_area_for_user(user: User) -> Optional[str]:
    return function_area_for_role(normalize_role(user.system_role))


def viewer_may_see_function_area(viewer: User, area: Optional[str]) -> bool:
    """Functional heads are restricted to their own function_area."""
    role = normalize_role(viewer.system_role)
    if role in (SystemRole.CEO, SystemRole.SUPER_ADMIN):
        return True
    viewer_area = function_area_for_user(viewer)
    if not viewer_area:
        return False
    return normalize_function_area(area) == viewer_area


def resolve_function_node_id(
    db: Session, org_id: str, function_area: Optional[str]
) -> Optional[str]:
    """Best-effort link to a CORPORATE_FUNCTION / VERTICAL org node."""
    if not function_area:
        return None
    node = (
        db.query(OrgNode)
        .filter(
            OrgNode.org_id == org_id,
            OrgNode.node_type.in_(("CORPORATE_FUNCTION", "VERTICAL")),
            OrgNode.is_active == True,
        )
        .filter(
            OrgNode.code == function_area,
        )
        .first()
    )
    if node:
        return node.id
    label = FUNCTION_AREA_LABELS.get(function_area, function_area)
    node = (
        db.query(OrgNode)
        .filter(
            OrgNode.org_id == org_id,
            OrgNode.node_type.in_(("CORPORATE_FUNCTION", "VERTICAL")),
            OrgNode.name.ilike(f"%{label.split('/')[0].strip()}%"),
            OrgNode.is_active == True,
        )
        .first()
    )
    return node.id if node else None


def inherit_function_area_from_parent(
    db: Session, functional_parent_obj_id: Optional[str]
) -> Optional[str]:
    if not functional_parent_obj_id:
        return None
    parent = db.query(Objective).filter(Objective.id == functional_parent_obj_id).first()
    if not parent:
        return None
    return normalize_function_area(parent.function_area)


def resolve_function_area_on_create(
    db: Session,
    creator: User,
    *,
    level: str,
    explicit_area: Optional[str],
    functional_parent_obj_id: Optional[str] = None,
    org_id: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Determine function_area (+ optional function_node_id) for a new/updated objective.
    """
    lvl = (level or "").strip().upper()
    explicit = normalize_function_area(explicit_area)

    if explicit:
        area = explicit
    elif functional_parent_obj_id:
        area = inherit_function_area_from_parent(db, functional_parent_obj_id)
    elif lvl in ("VERTICAL", "SUB_DEPARTMENT"):
        role = normalize_role(creator.system_role)
        area = function_area_for_role(role)
        if not area and role == SystemRole.FUNCTIONAL_SUB_HEAD:
            dotted = (
                db.query(ReportingRelationship)
                .filter(
                    ReportingRelationship.employee_id == creator.id,
                    ReportingRelationship.relationship_type.in_(("DOTTED_LINE", "REVIEWER")),
                    ReportingRelationship.is_active == True,
                )
                .first()
            )
            if dotted:
                mgr = db.query(User).filter(User.id == dotted.manager_id).first()
                if mgr:
                    area = function_area_for_user(mgr)
    else:
        area = None

    node_id = None
    if area and org_id:
        node_id = resolve_function_node_id(db, org_id, area)
    return area, node_id


def node_kind_for_objective(obj: Objective) -> str:
    lvl = (obj.level or "").upper()
    if lvl == "ORGANIZATION":
        return "ORG"
    if lvl == "VERTICAL":
        return "FUNCTIONAL_VERTICAL"
    if lvl == "REGION":
        return "ORG"
    if lvl == "PLANT":
        return "PLANT"
    if lvl in ("DEPARTMENT", "SUB_DEPARTMENT"):
        return "DEPARTMENT"
    if lvl == "TEAM":
        return "TEAM"
    return "INDIVIDUAL"


def dotted_line_subordinate_ids(db: Session, manager_id: str) -> List[str]:
    rows = (
        db.query(ReportingRelationship.employee_id)
        .filter(
            ReportingRelationship.manager_id == manager_id,
            ReportingRelationship.relationship_type.in_(("DOTTED_LINE", "REVIEWER")),
            ReportingRelationship.is_active == True,
        )
        .all()
    )
    return [r[0] for r in rows if r[0]]


def objective_to_summary_dict(obj: Objective, db: Session) -> Dict[str, Any]:
    owner = db.query(User).filter(User.id == obj.owner_id).first()
    parent = (
        db.query(Objective).filter(Objective.id == obj.parent_id).first()
        if obj.parent_id
        else None
    )
    fp = (
        db.query(Objective).filter(Objective.id == obj.functional_parent_obj_id).first()
        if obj.functional_parent_obj_id
        else None
    )
    return {
        "id": obj.id,
        "title": obj.title,
        "level": obj.level,
        "function_area": obj.function_area,
        "function_node_id": obj.function_node_id,
        "progress": float(obj.progress or 0),
        "okr_status": obj.okr_status,
        "owner_id": obj.owner_id,
        "owner_name": owner.name if owner else None,
        "parent_id": obj.parent_id,
        "parent_title": parent.title if parent else None,
        "parent_level": parent.level if parent else None,
        "functional_parent_obj_id": obj.functional_parent_obj_id,
        "functional_parent_title": fp.title if fp else None,
        "plant_id": obj.plant_id,
        "department_id": obj.department_id,
        "node_kind": node_kind_for_objective(obj),
    }
