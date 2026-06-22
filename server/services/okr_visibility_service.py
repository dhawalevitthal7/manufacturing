"""
Hierarchical OKR visibility: subtree (downward) + exactly one parent level (alignment peek).

Regional head sees East subtree + Organization OKRs only.
Plant head sees plant subtree + parent Region OKR only, etc.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from server.models import (
    Department,
    Objective,
    OrgNode,
    ReportingRelationship,
    Team,
    User,
    UserPermissionProfile,
)
from server.roles import SystemRole, normalize_role, FUNCTIONAL_APPROVER_ROLES

# Levels shown in UI tabs per anchor (includes parent peek level where applicable)
VISIBLE_LEVELS_BY_ANCHOR: Dict[str, List[str]] = {
    "ORGANIZATION": ["ORGANIZATION", "REGION", "PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"],
    "REGION": ["ORGANIZATION", "REGION", "PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"],
    "PLANT": ["REGION", "PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"],
    "DEPARTMENT": ["PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"],
    "TEAM": ["DEPARTMENT", "TEAM", "INDIVIDUAL"],
    "EMPLOYEE": ["TEAM", "INDIVIDUAL"],
}

PARENT_LEVEL: Dict[str, Optional[str]] = {
    "ORGANIZATION": None,
    "REGION": "ORGANIZATION",
    "PLANT": "REGION",
    "DEPARTMENT": "PLANT",
    "TEAM": "DEPARTMENT",
    "EMPLOYEE": "TEAM",
}


def _permission_profile(user: User, db: Session) -> Optional[UserPermissionProfile]:
    return (
        db.query(UserPermissionProfile)
        .filter(UserPermissionProfile.user_id == user.id)
        .first()
    )


def resolve_region_scope_id(
    user: User, db: Session, profile: Optional[UserPermissionProfile] = None
) -> Optional[str]:
    profile = profile or _permission_profile(user, db)
    if profile and profile.scoped_region_id:
        return profile.scoped_region_id
    if user.org_node_id:
        node = db.query(OrgNode).filter(OrgNode.id == user.org_node_id).first()
        if node and str(node.node_type) == "REGION":
            return node.id
    region = (
        db.query(OrgNode)
        .filter(
            OrgNode.org_id == user.org_id,
            OrgNode.node_type == "REGION",
            OrgNode.head_user_id == user.id,
        )
        .first()
    )
    return region.id if region else None


def resolve_plant_scope_id(
    user: User, db: Session, profile: Optional[UserPermissionProfile] = None
) -> Optional[str]:
    profile = profile or _permission_profile(user, db)
    if profile and profile.scoped_plant_id:
        return profile.scoped_plant_id
    if user.plant_id:
        return user.plant_id
    if user.org_node_id:
        node = db.query(OrgNode).filter(OrgNode.id == user.org_node_id).first()
        if node and str(node.node_type) == "PLANT":
            return node.id
    plant = (
        db.query(OrgNode)
        .filter(
            OrgNode.org_id == user.org_id,
            OrgNode.node_type == "PLANT",
            OrgNode.head_user_id == user.id,
        )
        .first()
    )
    return plant.id if plant else None


def resolve_department_scope_id(
    user: User, db: Session, profile: Optional[UserPermissionProfile] = None
) -> Optional[str]:
    profile = profile or _permission_profile(user, db)
    if profile and profile.scoped_department_id:
        return profile.scoped_department_id
    if user.department_id:
        return user.department_id
    if user.org_node_id:
        node = db.query(OrgNode).filter(OrgNode.id == user.org_node_id).first()
        if node and str(node.node_type) == "DEPARTMENT":
            return node.id
    dept = (
        db.query(OrgNode)
        .filter(
            OrgNode.org_id == user.org_id,
            OrgNode.node_type == "DEPARTMENT",
            OrgNode.head_user_id == user.id,
        )
        .first()
    )
    return dept.id if dept else None


def resolve_team_scope_id(
    user: User, db: Session, profile: Optional[UserPermissionProfile] = None
) -> Optional[str]:
    profile = profile or _permission_profile(user, db)
    if profile and profile.scoped_team_id:
        return profile.scoped_team_id
    if user.team_id:
        return user.team_id
    if user.org_node_id:
        node = db.query(OrgNode).filter(OrgNode.id == user.org_node_id).first()
        if node and str(node.node_type) == "TEAM":
            return node.id
    team = (
        db.query(OrgNode)
        .filter(
            OrgNode.org_id == user.org_id,
            OrgNode.node_type == "TEAM",
            OrgNode.head_user_id == user.id,
        )
        .first()
    )
    return team.id if team else None


def build_plant_region_map(db: Session, org_id: str) -> Dict[str, Dict[str, str]]:
    """Map plant_id -> {region_id, region_name}."""
    plant_nodes = (
        db.query(OrgNode)
        .filter(OrgNode.org_id == org_id, OrgNode.node_type == "PLANT")
        .all()
    )
    parent_ids = {p.parent_id for p in plant_nodes if p.parent_id}
    if not parent_ids:
        return {}

    parents = {
        n.id: n
        for n in db.query(OrgNode)
        .filter(OrgNode.id.in_(parent_ids), OrgNode.node_type == "REGION")
        .all()
    }
    out: Dict[str, Dict[str, str]] = {}
    for p in plant_nodes:
        parent = parents.get(p.parent_id) if p.parent_id else None
        if parent:
            out[p.id] = {"region_id": parent.id, "region_name": parent.name}
    return out


def plant_ids_for_region(
    plant_region_map: Dict[str, Dict[str, str]], region_id: str
) -> List[str]:
    return [
        pid for pid, info in plant_region_map.items() if info.get("region_id") == region_id
    ]


def get_user_okr_scope(user: User, db: Session) -> Dict[str, Any]:
    """
    Anchor scope for OKR visibility.
    Returns: level, scope_id, visible_levels, parent_level, region_id, plant_id, department_id, team_id
    """
    role = normalize_role(user.system_role)
    profile = _permission_profile(user, db)

    if role in (SystemRole.SUPER_ADMIN, SystemRole.CEO):
        return {
            "level": "ORGANIZATION",
            "scope_id": user.org_id,
            "visible_levels": VISIBLE_LEVELS_BY_ANCHOR["ORGANIZATION"],
            "parent_level": None,
            "unrestricted": True,
            "region_id": None,
            "plant_id": None,
            "department_id": None,
            "team_id": None,
        }

    if role in (SystemRole.REGIONAL_HEAD, SystemRole.VP_OPERATIONS, SystemRole.CRO):
        region_id = resolve_region_scope_id(user, db, profile)
        return {
            "level": "REGION" if role != SystemRole.CRO else "ORGANIZATION",
            "scope_id": region_id if role != SystemRole.CRO else user.org_id,
            "visible_levels": VISIBLE_LEVELS_BY_ANCHOR["REGION" if role != SystemRole.CRO else "ORGANIZATION"],
            "parent_level": PARENT_LEVEL["REGION"] if role != SystemRole.CRO else None,
            "unrestricted": role == SystemRole.CRO,
            "region_id": region_id if role != SystemRole.CRO else None,
            "plant_id": None,
            "department_id": None,
            "team_id": None,
        }

    if role == SystemRole.COO:
        return {
            "level": "ORGANIZATION",
            "scope_id": user.org_id,
            "visible_levels": VISIBLE_LEVELS_BY_ANCHOR["ORGANIZATION"],
            "parent_level": None,
            "unrestricted": True,
            "region_id": None,
            "plant_id": None,
            "department_id": None,
            "team_id": None,
        }

    if role == SystemRole.PLANT_HEAD:
        plant_id = resolve_plant_scope_id(user, db, profile)
        prm = build_plant_region_map(db, user.org_id)
        region_id = prm.get(plant_id or "", {}).get("region_id") if plant_id else None
        return {
            "level": "PLANT",
            "scope_id": plant_id,
            "visible_levels": VISIBLE_LEVELS_BY_ANCHOR["PLANT"],
            "parent_level": PARENT_LEVEL["PLANT"],
            "unrestricted": False,
            "region_id": region_id,
            "plant_id": plant_id,
            "department_id": None,
            "team_id": None,
        }

    if role == SystemRole.DEPT_HEAD:
        dept_id = resolve_department_scope_id(user, db, profile)
        dept = (
            db.query(Department)
            .filter(Department.id == dept_id, Department.org_id == user.org_id)
            .first()
            if dept_id
            else None
        )
        return {
            "level": "DEPARTMENT",
            "scope_id": dept_id,
            "visible_levels": VISIBLE_LEVELS_BY_ANCHOR["DEPARTMENT"],
            "parent_level": PARENT_LEVEL["DEPARTMENT"],
            "unrestricted": False,
            "region_id": None,
            "plant_id": dept.plant_id if dept else user.plant_id,
            "department_id": dept_id,
            "team_id": None,
        }

    if role == SystemRole.MANAGER:
        # Managers oversee a department (multiple teams); they are not team-scoped.
        dept_id = resolve_department_scope_id(user, db, profile)
        dept = (
            db.query(Department)
            .filter(Department.id == dept_id, Department.org_id == user.org_id)
            .first()
            if dept_id
            else None
        )
        return {
            "level": "DEPARTMENT",
            "scope_id": dept_id,
            "visible_levels": VISIBLE_LEVELS_BY_ANCHOR["DEPARTMENT"],
            "parent_level": PARENT_LEVEL["DEPARTMENT"],
            "unrestricted": False,
            "region_id": None,
            "plant_id": dept.plant_id if dept else user.plant_id,
            "department_id": dept_id,
            "team_id": None,
        }

    if role in (SystemRole.TEAM_LEAD, SystemRole.SUPERVISOR):
        team_id = resolve_team_scope_id(user, db, profile)
        team = (
            db.query(Team).filter(Team.id == team_id, Team.org_id == user.org_id).first()
            if team_id
            else None
        )
        return {
            "level": "TEAM",
            "scope_id": team_id,
            "visible_levels": VISIBLE_LEVELS_BY_ANCHOR["TEAM"],
            "parent_level": PARENT_LEVEL["TEAM"],
            "unrestricted": False,
            "region_id": None,
            "plant_id": user.plant_id,
            "department_id": team.department_id if team else user.department_id,
            "team_id": team_id,
        }

    if role in FUNCTIONAL_APPROVER_ROLES or role == SystemRole.FUNCTIONAL_SUB_HEAD:
        return {
            "level": "FUNCTIONAL",
            "scope_id": user.id,
            "visible_levels": VISIBLE_LEVELS_BY_ANCHOR["ORGANIZATION"],
            "parent_level": "ORGANIZATION",
            "unrestricted": False,
            "functional_head": True,
            "region_id": None,
            "plant_id": None,
            "department_id": None,
            "team_id": None,
        }

    if role == SystemRole.AREA_SALES_MANAGER:
        return {
            "level": "DEPARTMENT",
            "scope_id": resolve_department_scope_id(user, db, profile),
            "visible_levels": VISIBLE_LEVELS_BY_ANCHOR["DEPARTMENT"],
            "parent_level": PARENT_LEVEL["DEPARTMENT"],
            "unrestricted": False,
            "region_id": None,
            "plant_id": user.plant_id,
            "department_id": user.department_id,
            "team_id": None,
        }

    return {
        "level": "EMPLOYEE",
        "scope_id": user.id,
        "visible_levels": VISIBLE_LEVELS_BY_ANCHOR["EMPLOYEE"],
        "parent_level": PARENT_LEVEL["EMPLOYEE"],
        "unrestricted": False,
        "region_id": None,
        "plant_id": user.plant_id,
        "department_id": user.department_id,
        "team_id": user.team_id,
    }


def _subtree_conditions(
    scope: Dict[str, Any],
    org_id: str,
    db: Session,
    plant_region_map: Dict[str, Dict[str, str]],
) -> List[Any]:
    """SQLAlchemy OR clauses for objectives in the user's downward subtree."""
    level = scope.get("level")
    scope_id = scope.get("scope_id")
    if not scope_id:
        return []

    clauses: List[Any] = []

    if level == "REGION":
        plant_ids = plant_ids_for_region(plant_region_map, scope_id)
        clauses.append(Objective.region_id == scope_id)
        if plant_ids:
            clauses.append(Objective.plant_id.in_(plant_ids))
            dept_rows = (
                db.query(Department.id)
                .filter(Department.org_id == org_id, Department.plant_id.in_(plant_ids))
                .all()
            )
            dept_ids = [r[0] for r in dept_rows]
            if dept_ids:
                clauses.append(Objective.department_id.in_(dept_ids))
                team_rows = (
                    db.query(Team.id).filter(Team.department_id.in_(dept_ids)).all()
                )
                team_ids = [r[0] for r in team_rows]
                if team_ids:
                    clauses.append(Objective.team_id.in_(team_ids))

    elif level == "PLANT":
        clauses.append(Objective.plant_id == scope_id)
        dept_rows = (
            db.query(Department.id)
            .filter(Department.org_id == org_id, Department.plant_id == scope_id)
            .all()
        )
        dept_ids = [r[0] for r in dept_rows]
        if dept_ids:
            clauses.append(Objective.department_id.in_(dept_ids))
            team_rows = db.query(Team.id).filter(Team.department_id.in_(dept_ids)).all()
            team_ids = [r[0] for r in team_rows]
            if team_ids:
                clauses.append(Objective.team_id.in_(team_ids))

    elif level == "DEPARTMENT":
        clauses.append(Objective.department_id == scope_id)
        team_rows = db.query(Team.id).filter(Team.department_id == scope_id).all()
        team_ids = [r[0] for r in team_rows]
        if team_ids:
            clauses.append(Objective.team_id.in_(team_ids))

    elif level == "TEAM":
        clauses.append(Objective.team_id == scope_id)

    elif level == "EMPLOYEE":
        clauses.append(Objective.owner_id == scope_id)

    return clauses


def _parent_peek_conditions(
    scope: Dict[str, Any],
    org_id: str,
    db: Session,
    plant_region_map: Dict[str, Dict[str, str]],
) -> List[Any]:
    """Exactly one level above the user's anchor (alignment context only)."""
    anchor = scope.get("level")
    parent_level = PARENT_LEVEL.get(anchor or "")
    if not parent_level:
        return []

    if parent_level == "ORGANIZATION":
        return [Objective.level == "ORGANIZATION", Objective.org_id == org_id]

    if parent_level == "REGION":
        region_id = scope.get("region_id")
        if not region_id and scope.get("plant_id"):
            region_id = plant_region_map.get(scope["plant_id"], {}).get("region_id")
        if region_id:
            return [
                Objective.level == "REGION",
                Objective.region_id == region_id,
            ]
        return []

    if parent_level == "PLANT":
        plant_id = scope.get("plant_id")
        if plant_id:
            return [Objective.level == "PLANT", Objective.plant_id == plant_id]
        return []

    if parent_level == "DEPARTMENT":
        dept_id = scope.get("department_id")
        if dept_id:
            return [
                Objective.level == "DEPARTMENT",
                Objective.department_id == dept_id,
            ]
        return []

    if parent_level == "TEAM":
        team_id = scope.get("team_id")
        if team_id:
            return [Objective.level == "TEAM", Objective.team_id == team_id]
        return []

    return []


def _functional_alignment_conditions(
    user: User,
    org_id: str,
    db: Session,
) -> List[Any]:
    """
    Functional heads see dotted-line department OKRs across all plants:
    - owned by dotted-line / reviewer subordinates
    - aligned via functional_parent_obj_id to this head's objectives
    - this head's own vertical / org OKRs
    """
    clauses: List[Any] = []

    dotted_owner_rows = (
        db.query(ReportingRelationship.employee_id)
        .filter(
            ReportingRelationship.manager_id == user.id,
            ReportingRelationship.relationship_type.in_(("DOTTED_LINE", "REVIEWER")),
            ReportingRelationship.is_active == True,
        )
        .all()
    )
    dotted_owner_ids = [r[0] for r in dotted_owner_rows if r[0]]
    if dotted_owner_ids:
        clauses.append(Objective.owner_id.in_(dotted_owner_ids))

    head_obj_rows = (
        db.query(Objective.id)
        .filter(Objective.org_id == org_id, Objective.owner_id == user.id)
        .all()
    )
    head_obj_ids = [r[0] for r in head_obj_rows if r[0]]
    if head_obj_ids:
        clauses.append(Objective.functional_parent_obj_id.in_(head_obj_ids))

    clauses.append(and_(Objective.org_id == org_id, Objective.owner_id == user.id))
    return clauses


def build_visibility_filter(
    user: User,
    db: Session,
    org_id: str,
) -> Optional[Any]:
    """
    Combined OR filter for visible objectives, or None if unrestricted (CEO).
    """
    scope = get_user_okr_scope(user, db)
    if scope.get("unrestricted"):
        return None

    plant_region_map = build_plant_region_map(db, org_id)
    subtree = _subtree_conditions(scope, org_id, db, plant_region_map)
    parent = _parent_peek_conditions(scope, org_id, db, plant_region_map)
    functional = (
        _functional_alignment_conditions(user, org_id, db)
        if scope.get("functional_head")
        else []
    )

    all_parts: List[Any] = []
    if subtree:
        all_parts.append(or_(*subtree))
    if parent:
        all_parts.append(and_(*parent) if len(parent) > 1 else parent[0])
    if functional:
        all_parts.append(or_(*functional))

    if not all_parts:
        # No resolved scope — show nothing rather than entire org
        return Objective.id.is_(None)

    return or_(*all_parts) if len(all_parts) > 1 else all_parts[0]


def apply_okr_visibility_filter(query, user: User, db: Session, org_id: str):
    """Apply hierarchy visibility to an Objective query."""
    filt = build_visibility_filter(user, db, org_id)
    if filt is None:
        return query
    return query.filter(filt)


def apply_optional_scope_narrowing(
    query,
    scope: Dict[str, Any],
    *,
    plant_id: Optional[str] = None,
    department_id: Optional[str] = None,
    team_id: Optional[str] = None,
    db: Session,
    org_id: str,
):
    """Narrow within allowed scope when client passes optional filters."""
    if scope.get("unrestricted"):
        if plant_id:
            query = query.filter(Objective.plant_id == plant_id)
        if department_id:
            query = query.filter(Objective.department_id == department_id)
        if team_id:
            query = query.filter(Objective.team_id == team_id)
        return query

    prm = build_plant_region_map(db, org_id)
    anchor = scope.get("level")

    if plant_id:
        allowed = False
        if anchor == "REGION" and scope.get("region_id"):
            allowed = plant_id in plant_ids_for_region(prm, scope["region_id"])
        elif anchor in ("PLANT", "DEPARTMENT", "TEAM", "EMPLOYEE"):
            allowed = plant_id == scope.get("plant_id") or (
                anchor == "REGION"
                and scope.get("region_id")
                and plant_id in plant_ids_for_region(prm, scope["region_id"])
            )
        if allowed:
            query = query.filter(Objective.plant_id == plant_id)

    if department_id:
        allowed = False
        if anchor == "DEPARTMENT" and scope.get("department_id") == department_id:
            allowed = True
        elif anchor in ("PLANT", "REGION") and scope.get("plant_id"):
            dept = db.query(Department).filter(Department.id == department_id).first()
            allowed = dept and dept.plant_id == scope.get("plant_id")
        elif anchor == "REGION" and scope.get("region_id"):
            dept = db.query(Department).filter(Department.id == department_id).first()
            if dept:
                allowed = dept.plant_id in plant_ids_for_region(prm, scope["region_id"])
        if allowed:
            query = query.filter(Objective.department_id == department_id)

    if team_id:
        allowed = False
        if scope.get("team_id") == team_id:
            allowed = True
        elif scope.get("department_id"):
            team = db.query(Team).filter(Team.id == team_id).first()
            allowed = team and team.department_id == scope.get("department_id")
        if allowed:
            query = query.filter(Objective.team_id == team_id)

    return query


def visibility_scope_response(user: User, db: Session) -> Dict[str, Any]:
    """API payload for frontend tabs and plant dropdown."""
    scope = get_user_okr_scope(user, db)
    org_id = user.org_id
    plant_ids: List[str] = []
    if scope.get("level") == "REGION" and scope.get("region_id"):
        prm = build_plant_region_map(db, org_id)
        plant_ids = plant_ids_for_region(prm, scope["region_id"])
    elif scope.get("plant_id"):
        plant_ids = [scope["plant_id"]]

    region_name = None
    if scope.get("region_id"):
        node = db.query(OrgNode).filter(OrgNode.id == scope["region_id"]).first()
        region_name = node.name if node else None

    return {
        "anchor_level": scope.get("level"),
        "scope_id": scope.get("scope_id"),
        "visible_levels": scope.get("visible_levels", []),
        "parent_level": scope.get("parent_level"),
        "unrestricted": scope.get("unrestricted", False),
        "region_id": scope.get("region_id"),
        "region_name": region_name,
        "plant_ids": plant_ids,
        "plant_id": scope.get("plant_id"),
        "department_id": scope.get("department_id"),
        "team_id": scope.get("team_id"),
    }


def get_functional_okrs(
    db: Session,
    org_id: str,
    viewer: User,
    function_area: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Functional / vertical OKRs grouped by function_area with org alignment summary.
    CEO/SUPER_ADMIN: all functions (optional filter). Functional heads: own function only.
    """
    from server.services.function_area_service import (
        FUNCTION_AREAS,
        FUNCTION_AREA_LABELS,
        function_area_for_user,
        normalize_function_area,
        objective_to_summary_dict,
        viewer_may_see_function_area,
    )

    role = normalize_role(viewer.system_role)
    requested = normalize_function_area(function_area)
    viewer_area = function_area_for_user(viewer)

    if role not in (SystemRole.CEO, SystemRole.SUPER_ADMIN):
        if not viewer_area:
            return {"functions": [], "viewer_function_area": None}
        if requested and requested != viewer_area:
            return {"functions": [], "viewer_function_area": viewer_area}
        areas_filter = [viewer_area]
    else:
        areas_filter = [requested] if requested else list(FUNCTION_AREAS)

    q = db.query(Objective).filter(
        Objective.org_id == org_id,
        or_(
            Objective.level == "VERTICAL",
            Objective.function_area.isnot(None),
        ),
    )
    if len(areas_filter) == 1:
        q = q.filter(Objective.function_area == areas_filter[0])
    elif requested:
        q = q.filter(Objective.function_area == requested)
    else:
        q = q.filter(Objective.function_area.in_(areas_filter))

    objectives = q.order_by(Objective.created_at.desc()).all()
    grouped: Dict[str, List[Objective]] = {a: [] for a in areas_filter}
    for obj in objectives:
        area = normalize_function_area(obj.function_area)
        if not area or area not in grouped:
            continue
        if not viewer_may_see_function_area(viewer, area):
            continue
        grouped[area].append(obj)

    functions_out: List[Dict[str, Any]] = []
    for area in areas_filter:
        objs = grouped.get(area) or []
        if not objs:
            continue
        summaries = [objective_to_summary_dict(o, db) for o in objs]
        avg_progress = sum(s["progress"] for s in summaries) / len(summaries)
        org_parents = []
        for s in summaries:
            if s.get("parent_id") and s.get("parent_level") == "ORGANIZATION":
                org_parents.append(
                    {
                        "objective_id": s["id"],
                        "org_parent_id": s["parent_id"],
                        "org_parent_title": s.get("parent_title"),
                    }
                )
        functions_out.append(
            {
                "function_area": area,
                "function_label": FUNCTION_AREA_LABELS.get(area, area),
                "objective_count": len(summaries),
                "aggregate_progress": round(avg_progress, 1),
                "vertical_okrs": [s for s in summaries if s.get("level") == "VERTICAL"],
                "objectives": summaries,
                "org_alignments": org_parents,
            }
        )

    return {
        "viewer_function_area": viewer_area,
        "functions": functions_out,
    }


def get_function_structure(
    db: Session,
    org_id: str,
    viewer: User,
) -> Dict[str, Any]:
    """
    Function hierarchy for a functional head: vertical OKRs → sub-heads + plant departments.
    Strictly scoped to the viewer's function_area.
    """
    from server.services.function_area_service import (
        FUNCTION_AREA_LABELS,
        dotted_line_subordinate_ids,
        function_area_for_user,
        inherit_function_area_from_parent,
        node_kind_for_objective,
        objective_to_summary_dict,
    )

    area = function_area_for_user(viewer)
    role = normalize_role(viewer.system_role)
    if role in (SystemRole.CEO, SystemRole.SUPER_ADMIN):
        raise ValueError("Use /functional-overview for CEO-wide function visibility")
    if not area:
        return {"function_area": None, "trees": []}

    vertical_q = db.query(Objective).filter(
        Objective.org_id == org_id,
        Objective.function_area == area,
        Objective.level.in_(("VERTICAL", "ORGANIZATION")),
    )
    vertical_okrs = vertical_q.filter(
        or_(Objective.owner_id == viewer.id, Objective.level == "VERTICAL")
    ).all()
    if not vertical_okrs:
        vertical_okrs = vertical_q.all()

    vertical_ids = {v.id for v in vertical_okrs}
    subordinate_ids = set(dotted_line_subordinate_ids(db, viewer.id))

    sub_head_objs = (
        db.query(Objective)
        .filter(
            Objective.org_id == org_id,
            Objective.function_area == area,
            Objective.level.in_(("SUB_DEPARTMENT", "VERTICAL")),
            Objective.owner_id != viewer.id,
        )
        .all()
    )
    sub_heads = [
        o
        for o in sub_head_objs
        if o.owner_id in subordinate_ids
        or (o.functional_parent_obj_id and o.functional_parent_obj_id in vertical_ids)
    ]

    dept_clauses = []
    if vertical_ids:
        dept_clauses.append(Objective.functional_parent_obj_id.in_(vertical_ids))
    if subordinate_ids:
        dept_clauses.append(
            and_(
                Objective.level == "DEPARTMENT",
                Objective.owner_id.in_(subordinate_ids),
            )
        )
    plant_departments: List[Objective] = []
    if dept_clauses:
        plant_departments = (
            db.query(Objective)
            .filter(Objective.org_id == org_id, or_(*dept_clauses))
            .order_by(Objective.plant_id, Objective.title)
            .all()
        )
    for dept in plant_departments:
        if not dept.function_area:
            inherited = inherit_function_area_from_parent(db, dept.functional_parent_obj_id)
            if inherited and inherited != area:
                continue
        elif dept.function_area != area:
            continue

    trees: List[Dict[str, Any]] = []
    for vertical in vertical_okrs:
        v_summary = objective_to_summary_dict(vertical, db)
        v_sub_heads = [
            objective_to_summary_dict(o, db)
            for o in sub_heads
            if o.functional_parent_obj_id == vertical.id
            or (not o.functional_parent_obj_id and o.function_area == area)
        ]
        v_depts = [
            objective_to_summary_dict(o, db)
            for o in plant_departments
            if o.functional_parent_obj_id == vertical.id
        ]
        unlinked_depts = [
            objective_to_summary_dict(o, db)
            for o in plant_departments
            if o not in [x for x in plant_departments if x.functional_parent_obj_id == vertical.id]
            and o.owner_id in subordinate_ids
        ]
        trees.append(
            {
                "vertical": v_summary,
                "sub_heads": v_sub_heads,
                "plant_departments": v_depts + unlinked_depts,
                "org_parent_id": vertical.parent_id,
                "org_parent_title": v_summary.get("parent_title"),
            }
        )

    if not trees and (sub_heads or plant_departments):
        trees.append(
            {
                "vertical": None,
                "sub_heads": [objective_to_summary_dict(o, db) for o in sub_heads],
                "plant_departments": [
                    objective_to_summary_dict(o, db) for o in plant_departments
                ],
                "org_parent_id": None,
                "org_parent_title": None,
            }
        )

    return {
        "function_area": area,
        "function_label": FUNCTION_AREA_LABELS.get(area, area),
        "node_kind_root": "FUNCTIONAL_VERTICAL",
        "trees": trees,
    }
