"""
OKR Constellation Visualization Routes
=======================================

Role-based constellation visualization endpoint that shows OKR alignment
scoped to the user's role and organizational scope.

Scope by Role:
- CEO/SUPER_ADMIN: Organization → All Regions
- ADMIN: Organization → All Regions
- REGIONAL_HEAD: Region → All Plants in region
- PLANT_HEAD: Plant → All Departments in plant
- DEPT_HEAD: Department → All Teams in department
- MANAGER: Department → All Teams in department (same orbit as dept head)
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import Optional, List, Dict, Any
from datetime import datetime
import time
import logging
import json

from server.database import get_db
from server.models import (
    User, Objective, KeyResult, Organization, OrgNode,
    Plant, Department, Team, TeamMember, ReportingRelationship,
    UserPermissionProfile, ObjectiveConnection, Cycle,
)
from server.roles import normalize_role, SystemRole
from server.auth import get_jwt_payload
from server.services.okr_visibility_service import apply_okr_visibility_filter
from server.services.function_area_service import (
    FUNCTION_AREA_LABELS,
    function_area_for_user,
    node_kind_for_objective,
    normalize_function_area,
)
from server.roles import FUNCTIONAL_APPROVER_ROLES

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

router = APIRouter(prefix="/api/v1/okr/constellation", tags=["constellation"])

# ────────────────────────────────────────────────────────────────────────────
# IN-MEMORY RESPONSE CACHE (30 second TTL)
# ────────────────────────────────────────────────────────────────────────────
_constellation_cache: Dict[str, Any] = {}
_CACHE_TTL_SECONDS = 30


def _get_cache_key(
    user_id: str,
    org_id: str,
    levels: str,
    progress_min: int,
    progress_max: int,
    cycle_id: str = "",
    function_area: str = "",
    group_by: str = "",
) -> str:
    return (
        f"{user_id}:{org_id}:{levels or ''}:{progress_min}:{progress_max}:"
        f"{cycle_id or ''}:{function_area or ''}:{group_by or ''}"
    )


def _resolve_cycle_id(db: Session, org_id: str, cycle_id: Optional[str]) -> Optional[str]:
    if cycle_id:
        cycle = db.query(Cycle).filter(Cycle.id == cycle_id, Cycle.org_id == org_id).first()
        if not cycle:
            raise HTTPException(404, "Cycle not found")
        return cycle_id
    active = (
        db.query(Cycle)
        .filter(Cycle.org_id == org_id, Cycle.status.in_(("ACTIVE", "FROZEN")))
        .order_by(Cycle.start_date.desc())
        .first()
    )
    return active.id if active else None


def _alignment_score(progress: float) -> int:
    return int(75 if progress >= 50 else 50 if progress >= 30 else 25)


def _connection_type_to_alignment(conn_type: str) -> str:
    mapping = {
        "SUPPORTS": "support",
        "DEPENDS_ON": "dependency",
        "RELATED_TO": "cross-functional",
    }
    return mapping.get((conn_type or "").upper(), "cross-functional")


def _get_cached(key: str) -> Optional[Dict]:
    entry = _constellation_cache.get(key)
    if entry and (time.time() - entry["ts"]) < _CACHE_TTL_SECONDS:
        logger.info(f"CONSTELLATION: Cache HIT for key={key[:40]}...")
        return entry["data"]
    return None


def _set_cache(key: str, data: Dict) -> None:
    _constellation_cache[key] = {"data": data, "ts": time.time()}
    # Evict old entries (keep max 50)
    if len(_constellation_cache) > 50:
        oldest_key = min(_constellation_cache, key=lambda k: _constellation_cache[k]["ts"])
        del _constellation_cache[oldest_key]


# ────────────────────────────────────────────────────────────────────────────
# HELPERS
# ────────────────────────────────────────────────────────────────────────────

def get_current_user_from_jwt(payload: dict, db: Session) -> User:
    """Resolve current user from JWT payload and database."""
    user_id = payload.get("sub") or payload.get("user_id") or payload.get("id")
    if not user_id:
        raise HTTPException(401, "No user_id in token")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(401, "User not found")
    
    return user


def _require_constellation_access(user: User) -> None:
    """Constellation / alignment map is not available to individual contributors."""
    if normalize_role(user.system_role) == SystemRole.EMPLOYEE:
        raise HTTPException(
            status_code=403,
            detail="Alignment constellation is not available for employees",
        )


# ────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ────────────────────────────────────────────────────────────────────────────

# Levels returned for orbital view (center + orbiting children) when client omits `levels`
SCOPE_VIEW_LEVELS: Dict[str, List[str]] = {
  # Full hierarchy for client-side progressive expansion (default display: center + depth-1)
    "ORGANIZATION": ["ORGANIZATION", "REGION", "PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"],
    # REGION / PLANT must include TEAM + INDIVIDUAL so orbit expansion shows teams & employees
    "REGION": ["REGION", "PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"],
    "PLANT": ["PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"],
    "DEPARTMENT": ["DEPARTMENT", "TEAM", "INDIVIDUAL"],
    "TEAM": ["TEAM", "INDIVIDUAL"],
    "EMPLOYEE": ["INDIVIDUAL"],
}


def _permission_profile(user: User, db: Session) -> Optional[UserPermissionProfile]:
    return (
        db.query(UserPermissionProfile)
        .filter(UserPermissionProfile.user_id == user.id)
        .first()
    )


def _resolve_region_scope_id(
    user: User, db: Session, profile: Optional[UserPermissionProfile]
) -> Optional[str]:
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


def _resolve_plant_scope_id(
    user: User, db: Session, profile: Optional[UserPermissionProfile]
) -> Optional[str]:
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


def _resolve_department_scope_id(
    user: User, db: Session, profile: Optional[UserPermissionProfile]
) -> Optional[str]:
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


def _resolve_team_scope_id(
    user: User, db: Session, profile: Optional[UserPermissionProfile]
) -> Optional[str]:
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


def _plant_ids_for_region(
    plant_region_map: Dict[str, Dict[str, str]], region_id: str
) -> List[str]:
    return [
        pid for pid, info in plant_region_map.items() if info.get("region_id") == region_id
    ]


def _apply_hierarchy_scope_filter(
    query,
    scope: Dict[str, Any],
    org_id: str,
    db: Session,
    plant_region_map: Dict[str, Dict[str, str]],
):
    """Filter objectives to the user's region / plant / department / team."""
    level = scope.get("level")
    scope_id = scope.get("scope_id")
    if not scope_id or level == "ORGANIZATION":
        return query

    if level == "REGION":
        plant_ids = _plant_ids_for_region(plant_region_map, scope_id)
        clauses = [Objective.region_id == scope_id]
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
                    db.query(Team.id)
                    .filter(Team.department_id.in_(dept_ids))
                    .all()
                )
                team_ids = [r[0] for r in team_rows]
                if team_ids:
                    clauses.append(Objective.team_id.in_(team_ids))
        return query.filter(or_(*clauses))

    if level == "PLANT":
        clauses = [Objective.plant_id == scope_id]
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
        return query.filter(or_(*clauses))

    if level == "DEPARTMENT":
        clauses = [Objective.department_id == scope_id]
        team_rows = db.query(Team.id).filter(Team.department_id == scope_id).all()
        team_ids = [r[0] for r in team_rows]
        if team_ids:
            clauses.append(Objective.team_id.in_(team_ids))
        return query.filter(or_(*clauses))

    if level == "TEAM":
        return query.filter(Objective.team_id == scope_id)

    if level == "EMPLOYEE":
        return query.filter(Objective.owner_id == scope_id)

    return query


def _short_team_display_name(name: Optional[str]) -> str:
    """Show 'Team A' instead of 'Production Team A' on constellation labels."""
    if not name:
        return "Team"
    trimmed = name.strip()
    marker = " Team "
    idx = trimmed.rfind(marker)
    if idx >= 0:
        return trimmed[idx + 1 :]
    return trimmed


def _health_from_progress(progress: float) -> tuple:
    if progress >= 80:
        return "healthy", "low", "ahead"
    if progress >= 60:
        return "needs_attention", "medium", "on_track"
    if progress >= 40:
        return "critical", "high", "behind"
    return "blocked", "critical", "critical_delay"


def _synthetic_orbit_node(
    node_id: str,
    name: str,
    level: str,
    progress: float,
    user: User,
    *,
    region: Optional[str] = None,
    plant: Optional[str] = None,
    department: Optional[str] = None,
    team: Optional[str] = None,
    strategic_weight: int = 4,
) -> Dict[str, Any]:
    prog_int = int(progress)
    health, risk, trend = _health_from_progress(progress)
    display_name = _short_team_display_name(name) if level == "team" else name
    return {
        "id": node_id,
        "objective": display_name,
        "entity_name": display_name,
        "owner_id": None,
        "owner_name": "—",
        "owner_role": user.system_role if user else "Unknown",
        "level": level,
        "region_name": name if level == "region" else None,
        "plant_name": name if level == "plant" else None,
        "department_name": name if level == "department" else None,
        "team_name": _short_team_display_name(name) if level == "team" else None,
        "progress": prog_int,
        "own_progress": prog_int,
        "alignment_contribution": 0,
        "final_progress": prog_int,
        "alignment_health": health,
        "confidence_score": 50,
        "risk_level": risk,
        "trend_status": trend,
        "strategic_weight": strategic_weight,
        "is_orphaned": True,
        "plant": plant,
        "region": region,
        "department": department,
        "team": team,
    }


def resolve_scope_entity_name(scope: Dict[str, Any], db: Session) -> str:
    """Human-readable label for the user's scope center."""
    level = scope.get("level")
    scope_id = scope.get("scope_id")
    if not scope_id:
        return "Organization"

    if level == "ORGANIZATION":
        org = db.query(Organization).filter(Organization.id == scope_id).first()
        return org.name if org else "Organization"

    if level == "REGION":
        node = db.query(OrgNode).filter(OrgNode.id == scope_id).first()
        return node.name if node else "Region"

    if level == "PLANT":
        plant = db.query(Plant).filter(Plant.id == scope_id).first()
        if plant:
            return plant.name
        node = db.query(OrgNode).filter(OrgNode.id == scope_id).first()
        return node.name if node else "Plant"

    if level == "DEPARTMENT":
        dept = db.query(Department).filter(Department.id == scope_id).first()
        if dept:
            return dept.name
        node = db.query(OrgNode).filter(OrgNode.id == scope_id).first()
        return node.name if node else "Department"

    if level == "TEAM":
        team = db.query(Team).filter(Team.id == scope_id).first()
        if team:
            return team.name
        node = db.query(OrgNode).filter(OrgNode.id == scope_id).first()
        return node.name if node else "Team"

    return "My OKRs"


def get_user_scope(user: User, db: Session) -> Dict[str, Any]:
    """
    Determine the scope of OKRs a user should see based on their role.
    Returns: {level: str, scope_id: str, allowed_child_levels: [str]}
    """
    role = normalize_role(user.system_role)
    profile = _permission_profile(user, db)

    if role in [SystemRole.SUPER_ADMIN, SystemRole.CEO]:
        return {
            "level": "ORGANIZATION",
            "scope_id": user.org_id,
            "allowed_child_levels": [
                "ORGANIZATION", "VERTICAL", "SUB_DEPARTMENT",
                "REGION", "PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL",
            ],
            "view_levels": SCOPE_VIEW_LEVELS["ORGANIZATION"],
            "min_level": "ORGANIZATION",
            "max_level": "INDIVIDUAL",
        }

    elif role in [SystemRole.REGIONAL_HEAD, SystemRole.VP_OPERATIONS]:
        region_id = _resolve_region_scope_id(user, db, profile)
        return {
            "level": "REGION",
            "scope_id": region_id,
            "allowed_child_levels": ["REGION", "PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"],
            "view_levels": SCOPE_VIEW_LEVELS["REGION"],
            "min_level": "REGION",
            "max_level": "INDIVIDUAL",
        }

    elif role == SystemRole.CRO:
        return {
            "level": "ORGANIZATION",
            "scope_id": user.org_id,
            "allowed_child_levels": ["ORGANIZATION", "REGION", "PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"],
            "view_levels": SCOPE_VIEW_LEVELS["ORGANIZATION"],
            "min_level": "ORGANIZATION",
            "max_level": "INDIVIDUAL",
        }

    elif role == SystemRole.COO:
        return {
            "level": "ORGANIZATION",
            "scope_id": user.org_id,
            "allowed_child_levels": ["ORGANIZATION", "PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"],
            "view_levels": SCOPE_VIEW_LEVELS["ORGANIZATION"],
            "min_level": "ORGANIZATION",
            "max_level": "INDIVIDUAL",
        }

    elif role in [SystemRole.PLANT_HEAD]:
        plant_id = _resolve_plant_scope_id(user, db, profile)
        return {
            "level": "PLANT",
            "scope_id": plant_id,
            "allowed_child_levels": ["PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"],
            "view_levels": SCOPE_VIEW_LEVELS["PLANT"],
            "min_level": "PLANT",
            "max_level": "INDIVIDUAL",
        }

    elif role in [SystemRole.DEPT_HEAD]:
        dept_id = _resolve_department_scope_id(user, db, profile)
        return {
            "level": "DEPARTMENT",
            "scope_id": dept_id,
            "allowed_child_levels": ["DEPARTMENT", "TEAM", "INDIVIDUAL"],
            "view_levels": SCOPE_VIEW_LEVELS["DEPARTMENT"],
            "min_level": "DEPARTMENT",
            "max_level": "INDIVIDUAL",
        }

    elif role == SystemRole.MANAGER:
        dept_id = _resolve_department_scope_id(user, db, profile)
        return {
            "level": "DEPARTMENT",
            "scope_id": dept_id,
            "allowed_child_levels": ["DEPARTMENT", "TEAM", "INDIVIDUAL"],
            "view_levels": SCOPE_VIEW_LEVELS["DEPARTMENT"],
            "min_level": "DEPARTMENT",
            "max_level": "INDIVIDUAL",
        }

    elif role in [SystemRole.TEAM_LEAD, SystemRole.SUPERVISOR]:
        team_id = _resolve_team_scope_id(user, db, profile)
        return {
            "level": "TEAM",
            "scope_id": team_id,
            "allowed_child_levels": ["TEAM", "INDIVIDUAL"],
            "view_levels": SCOPE_VIEW_LEVELS["TEAM"],
            "min_level": "TEAM",
            "max_level": "INDIVIDUAL",
        }

    elif role in FUNCTIONAL_APPROVER_ROLES or role == SystemRole.FUNCTIONAL_SUB_HEAD:
        area = function_area_for_user(user)
        return {
            "level": "FUNCTIONAL",
            "scope_id": user.id,
            "function_area": area,
            "allowed_child_levels": [
                "ORGANIZATION", "VERTICAL", "SUB_DEPARTMENT",
                "REGION", "PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL",
            ],
            "view_levels": ["organization", "vertical", "plant", "department", "team", "employee"],
            "min_level": "VERTICAL",
            "max_level": "INDIVIDUAL",
        }

    else:
        return {
            "level": "EMPLOYEE",
            "scope_id": user.id,
            "allowed_child_levels": ["INDIVIDUAL"],
            "view_levels": SCOPE_VIEW_LEVELS["EMPLOYEE"],
            "min_level": "INDIVIDUAL",
            "max_level": "INDIVIDUAL",
        }


def _build_plant_region_map(db: Session, org_id: str) -> Dict[str, Dict[str, str]]:
    """Map plant_id -> region_id and region_name from org tree (plant node's parent region)."""
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


def _effective_region_id(
    objective: Objective, plant_region_map: Dict[str, Dict[str, str]]
) -> Optional[str]:
    if objective.region_id:
        return objective.region_id
    if objective.plant_id and objective.plant_id in plant_region_map:
        return plant_region_map[objective.plant_id]["region_id"]
    return None


def _build_entity_name_maps(
    db: Session,
    objectives: List[Objective],
    plant_region_map: Optional[Dict[str, Dict[str, str]]] = None,
) -> Dict[str, Dict[str, str]]:
    """Pre-fetch org unit names for constellation node labels."""
    region_ids: set = set()
    plant_ids: set = set()
    dept_ids: set = set()
    team_ids: set = set()

    prm = plant_region_map or {}
    for obj in objectives:
        rid = _effective_region_id(obj, prm)
        if rid:
            region_ids.add(rid)
        if obj.region_id:
            region_ids.add(obj.region_id)
        if obj.plant_id:
            plant_ids.add(obj.plant_id)
        if obj.department_id:
            dept_ids.add(obj.department_id)
        if obj.team_id:
            team_ids.add(obj.team_id)

    region_map = {
        n.id: n.name
        for n in db.query(OrgNode).filter(OrgNode.id.in_(region_ids)).all()
    } if region_ids else {}
    plant_map = {
        p.id: p.name for p in db.query(Plant).filter(Plant.id.in_(plant_ids)).all()
    } if plant_ids else {}
    dept_map = {
        d.id: d.name
        for d in db.query(Department).filter(Department.id.in_(dept_ids)).all()
    } if dept_ids else {}
    team_map = {
        t.id: t.name for t in db.query(Team).filter(Team.id.in_(team_ids)).all()
    } if team_ids else {}

    return {
        "region": region_map,
        "plant": plant_map,
        "department": dept_map,
        "team": team_map,
    }


def build_constellation_node(
    objective: Objective,
    user: User,
    user_map: Dict[str, User],
    name_maps: Optional[Dict[str, Dict[str, str]]] = None,
    plant_region_map: Optional[Dict[str, Dict[str, str]]] = None,
    *,
    function_cluster: Optional[str] = None,
) -> Dict[str, Any]:
    """Convert an Objective to a constellation node."""
    # Fetch owner from pre-built map (avoid N+1 query)
    owner = user_map.get(objective.owner_id)
    owner_role = owner.system_role if owner else "Unknown"
    
    # Progress from objective
    progress = float(objective.progress or 0)
    
    # Calculate confidence score based on status
    status_confidence_map = {
        "DRAFT": 30,
        "PENDING": 50,
        "APPROVED": 70,
        "ACTIVE": 75,
        "COMPLETED": 95,
        "ARCHIVED": 0,
    }
    confidence = status_confidence_map.get(objective.okr_status or objective.status or "DRAFT", 50)
    
    # Determine alignment health based on progress
    if progress >= 80 and confidence >= 75:
        health = "healthy"
    elif progress >= 60 and confidence >= 60:
        health = "needs_attention"
    elif progress >= 40:
        health = "critical"
    else:
        health = "blocked"
    
    # Determine risk level based on progress and status
    if progress < 40 or objective.okr_status == "REJECTED":
        risk = "critical"
    elif progress < 60:
        risk = "high"
    elif progress < 80:
        risk = "medium"
    else:
        risk = "low"
    
    # Determine trend (ahead/on_track/behind/critical_delay)
    if progress >= 80:
        trend = "ahead"
    elif progress >= 60:
        trend = "on_track"
    elif progress >= 40:
        trend = "behind"
    else:
        trend = "critical_delay"
    
    # Calculate strategic weight based on level (higher levels = higher weight)
    level_weights = {
        "ORGANIZATION": 5,
        "VERTICAL": 5,
        "REGION": 5,
        "PLANT": 4,
        "DEPARTMENT": 3,
        "SUB_DEPARTMENT": 3,
        "TEAM": 2,
        "INDIVIDUAL": 1,
    }
    strategic_weight = level_weights.get(objective.level or "INDIVIDUAL", 1)
    
    # Calculate alignment contribution (based on having a parent)
    alignment_contribution = 75 if objective.parent_id else 0

    level_raw = (objective.level or "INDIVIDUAL").upper()
    level = level_raw.lower()
    if level == "individual":
        level = "employee"
    if level_raw == "VERTICAL":
        level = "organization"
    if level_raw == "SUB_DEPARTMENT":
        level = "department"

    fa = normalize_function_area(objective.function_area)
    nk = node_kind_for_objective(objective)

    nm = name_maps or {}
    prm = plant_region_map or {}
    effective_region = _effective_region_id(objective, prm)
    region_name = None
    if effective_region:
        region_name = nm.get("region", {}).get(effective_region)
        if not region_name and objective.plant_id and objective.plant_id in prm:
            region_name = prm[objective.plant_id].get("region_name")
    plant_name = nm.get("plant", {}).get(objective.plant_id) if objective.plant_id else None
    dept_name = nm.get("department", {}).get(objective.department_id) if objective.department_id else None
    team_name = nm.get("team", {}).get(objective.team_id) if objective.team_id else None
    if team_name:
        team_name = _short_team_display_name(team_name)

    entity_name = None
    if level_raw == "REGION" and region_name:
        entity_name = region_name
    elif level_raw == "PLANT" and plant_name:
        entity_name = plant_name
    elif level_raw == "DEPARTMENT" and dept_name:
        entity_name = dept_name
    elif level_raw == "TEAM" and team_name:
        entity_name = team_name
    elif level in ("employee",) and owner:
        entity_name = owner.name
    
    return {
        "id": objective.id,
        "objective": objective.title or objective.description or "Unnamed Objective",
        "owner_id": objective.owner_id,
        "owner_name": owner.name if owner else "Unknown",
        "owner_role": owner_role,
        "level": level,
        "entity_name": entity_name,
        "region_name": region_name,
        "plant_name": plant_name,
        "department_name": dept_name,
        "team_name": team_name,
        "progress": int(progress),
        "own_progress": int(progress),
        "alignment_contribution": int(alignment_contribution),
        "final_progress": int(progress),
        "alignment_health": health,
        "confidence_score": int(confidence),
        "risk_level": risk,
        "trend_status": trend,
        "strategic_weight": strategic_weight,
        "is_orphaned": not bool(objective.parent_id),
        "plant": objective.plant_id if objective.level not in ["ORGANIZATION"] else None,
        "region": (
            effective_region
            if level_raw in ["REGION", "PLANT"] and effective_region
            else (objective.region_id if level_raw in ["REGION", "PLANT"] else None)
        ),
        "department": objective.department_id
        if (objective.level or "").upper() in ["DEPARTMENT", "TEAM", "INDIVIDUAL"]
        else None,
        "team": objective.team_id
        if (objective.level or "").upper() in ["TEAM", "INDIVIDUAL"]
        else None,
        "function_area": fa,
        "function_area_label": FUNCTION_AREA_LABELS.get(fa, fa) if fa else None,
        "node_kind": nk,
        "function_cluster": function_cluster or fa,
        "created_at": objective.created_at.isoformat() if objective.created_at else None,
        "updated_at": objective.created_at.isoformat() if objective.created_at else None,
    }


def augment_org_region_orbit_nodes(
    nodes: List[Dict[str, Any]],
    objectives: List[Objective],
    org_id: str,
    db: Session,
    user: User,
    plant_region_map: Dict[str, Dict[str, str]],
) -> List[Dict[str, Any]]:
    """
    CEO/org view: ensure each org-tree region appears on the orbit even when
    there are no REGION-level OKRs (UltraTech seed only creates PLANT OKRs).
    """
    region_nodes_db = (
        db.query(OrgNode)
        .filter(
            OrgNode.org_id == org_id,
            OrgNode.node_type == "REGION",
            OrgNode.is_active == True,
        )
        .all()
    )
    if not region_nodes_db:
        return nodes

    covered = {n.get("region") for n in nodes if n.get("level") == "region"}

    by_region: Dict[str, List[Objective]] = {}
    for obj in objectives:
        if (obj.level or "").upper() != "PLANT":
            continue
        rid = _effective_region_id(obj, plant_region_map)
        if rid:
            by_region.setdefault(rid, []).append(obj)

    extra: List[Dict[str, Any]] = []
    for rnode in region_nodes_db:
        if rnode.id in covered:
            continue
        group = by_region.get(rnode.id, [])
        progress = (
            sum(float(o.progress or 0) for o in group) / len(group) if group else 0.0
        )
        prog_int = int(progress)
        if progress >= 80:
            health, risk, trend = "healthy", "low", "ahead"
        elif progress >= 60:
            health, risk, trend = "needs_attention", "medium", "on_track"
        elif progress >= 40:
            health, risk, trend = "critical", "high", "behind"
        else:
            health, risk, trend = "blocked", "critical", "critical_delay"

        extra.append(
            _synthetic_orbit_node(
                f"region-orbit-{rnode.id}",
                rnode.name,
                "region",
                progress,
                user,
                region=rnode.id,
                strategic_weight=5,
            )
        )

    if extra:
        logger.info(f"CONSTELLATION: Added {len(extra)} synthetic region orbit nodes from org tree")
    return nodes + extra


def augment_region_plant_orbit_nodes(
    nodes: List[Dict[str, Any]],
    objectives: List[Objective],
    region_id: str,
    org_id: str,
    db: Session,
    user: User,
    plant_region_map: Dict[str, Dict[str, str]],
) -> List[Dict[str, Any]]:
    """Region head view: one orbit bubble per plant in this region."""
    plant_nodes_db = (
        db.query(OrgNode)
        .filter(
            OrgNode.org_id == org_id,
            OrgNode.node_type == "PLANT",
            OrgNode.parent_id == region_id,
            OrgNode.is_active == True,
        )
        .all()
    )
    if not plant_nodes_db:
        plant_ids = _plant_ids_for_region(plant_region_map, region_id)
        plant_nodes_db = [
            db.query(OrgNode).filter(OrgNode.id == pid).first()
            for pid in plant_ids
        ]
        plant_nodes_db = [p for p in plant_nodes_db if p]

    covered = {n.get("plant") for n in nodes if n.get("level") == "plant"}
    by_plant: Dict[str, List[Objective]] = {}
    for obj in objectives:
        if (obj.level or "").upper() != "PLANT":
            continue
        pid = obj.plant_id
        if not pid:
            continue
        rid = _effective_region_id(obj, plant_region_map)
        if rid == region_id or pid in _plant_ids_for_region(plant_region_map, region_id):
            by_plant.setdefault(pid, []).append(obj)

    extra: List[Dict[str, Any]] = []
    for pnode in plant_nodes_db:
        if pnode.id in covered:
            continue
        group = by_plant.get(pnode.id, [])
        progress = (
            sum(float(o.progress or 0) for o in group) / len(group) if group else 0.0
        )
        extra.append(
            _synthetic_orbit_node(
                f"plant-orbit-{pnode.id}",
                pnode.name,
                "plant",
                progress,
                user,
                plant=pnode.id,
                region=region_id,
                strategic_weight=4,
            )
        )

    if extra:
        logger.info(f"CONSTELLATION: Added {len(extra)} plant orbit nodes for region {region_id}")
    return nodes + extra


def augment_plant_department_orbit_nodes(
    nodes: List[Dict[str, Any]],
    objectives: List[Objective],
    plant_id: str,
    org_id: str,
    db: Session,
    user: User,
) -> List[Dict[str, Any]]:
    """Plant head view: departments orbiting the plant."""
    dept_rows = (
        db.query(Department)
        .filter(Department.org_id == org_id, Department.plant_id == plant_id, Department.is_active == True)
        .all()
    )
    covered = {n.get("department") for n in nodes if n.get("level") == "department"}
    by_dept: Dict[str, List[Objective]] = {}
    for obj in objectives:
        if (obj.level or "").upper() != "DEPARTMENT":
            continue
        if obj.department_id and (obj.plant_id == plant_id or obj.department_id in [d.id for d in dept_rows]):
            by_dept.setdefault(obj.department_id, []).append(obj)

    extra: List[Dict[str, Any]] = []
    for dept in dept_rows:
        if dept.id in covered:
            continue
        group = by_dept.get(dept.id, [])
        progress = (
            sum(float(o.progress or 0) for o in group) / len(group) if group else 0.0
        )
        extra.append(
            _synthetic_orbit_node(
                f"dept-orbit-{dept.id}",
                dept.name,
                "department",
                progress,
                user,
                plant=plant_id,
                department=dept.id,
                strategic_weight=3,
            )
        )

    if extra:
        logger.info(f"CONSTELLATION: Added {len(extra)} department orbit nodes for plant {plant_id}")
    return nodes + extra


def augment_department_team_orbit_nodes(
    nodes: List[Dict[str, Any]],
    objectives: List[Objective],
    department_id: str,
    org_id: str,
    db: Session,
    user: User,
) -> List[Dict[str, Any]]:
    """Dept / manager view: ensure every team in the department appears on the orbit."""
    team_rows = (
        db.query(Team)
        .filter(Team.org_id == org_id, Team.department_id == department_id, Team.is_active == True)
        .all()
    )
    if not team_rows:
        return nodes

    team_ids = {t.id for t in team_rows}
    covered = {
        n.get("team")
        for n in nodes
        if n.get("level") == "team" and n.get("team") in team_ids
    }

    by_team: Dict[str, List[Objective]] = {}
    for obj in objectives:
        if not obj.team_id or obj.team_id not in team_ids:
            continue
        if (obj.level or "").upper() in ("TEAM", "INDIVIDUAL"):
            by_team.setdefault(obj.team_id, []).append(obj)

    extra: List[Dict[str, Any]] = []
    for team in team_rows:
        if team.id in covered:
            continue
        group = by_team.get(team.id, [])
        progress = (
            sum(float(o.progress or 0) for o in group) / len(group) if group else 0.0
        )
        extra.append(
            _synthetic_orbit_node(
                f"team-orbit-{team.id}",
                team.name,
                "team",
                progress,
                user,
                department=department_id,
                team=team.id,
                strategic_weight=2,
            )
        )

    if extra:
        logger.info(
            f"CONSTELLATION: Added {len(extra)} team orbit nodes for dept {department_id} "
            f"({len(team_rows)} teams total)"
        )
    return nodes + extra


def _department_ids_for_plants(db: Session, org_id: str, plant_ids: List[str]) -> List[str]:
    if not plant_ids:
        return []
    rows = (
        db.query(Department.id)
        .filter(
            Department.org_id == org_id,
            Department.plant_id.in_(plant_ids),
            Department.is_active == True,
        )
        .all()
    )
    return [r[0] for r in rows]


def _augment_departments_and_teams_for_plants(
    nodes: List[Dict[str, Any]],
    objectives: List[Objective],
    plant_ids: List[str],
    org_id: str,
    db: Session,
    user: User,
) -> List[Dict[str, Any]]:
    """Ensure department + team orbit nodes exist for every plant in the list."""
    for plant_id in plant_ids:
        nodes = augment_plant_department_orbit_nodes(
            nodes, objectives, plant_id, org_id, db, user
        )
    dept_ids = _department_ids_for_plants(db, org_id, plant_ids)
    for dept_id in dept_ids:
        nodes = augment_department_team_orbit_nodes(
            nodes, objectives, dept_id, org_id, db, user
        )
    return nodes


def ensure_scope_center_node(
    nodes: List[Dict[str, Any]],
    scope: Dict[str, Any],
    scope_entity_name: str,
    objectives: List[Objective],
    user: User,
    plant_region_map: Dict[str, Dict[str, str]],
) -> List[Dict[str, Any]]:
    """Inject a center node for the user's scope when no OKR exists at that level."""
    level = scope.get("level")
    scope_id = scope.get("scope_id")
    if not scope_id or level == "ORGANIZATION":
        return nodes

    level_lower = {
        "REGION": "region",
        "PLANT": "plant",
        "DEPARTMENT": "department",
        "TEAM": "team",
    }.get(level or "", "")

    def _matches_center(n: Dict[str, Any]) -> bool:
        if n.get("level") != level_lower:
            return False
        if level == "REGION":
            return n.get("region") == scope_id or n.get("id") == scope_id
        if level == "PLANT":
            return n.get("plant") == scope_id
        if level == "DEPARTMENT":
            return n.get("department") == scope_id
        if level == "TEAM":
            return n.get("team") == scope_id
        return False

    if any(_matches_center(n) for n in nodes):
        return nodes

    child_objs: List[Objective] = []
    if level == "REGION":
        for obj in objectives:
            if (obj.level or "").upper() == "PLANT":
                rid = _effective_region_id(obj, plant_region_map)
                if rid == scope_id:
                    child_objs.append(obj)
    elif level == "PLANT":
        child_objs = [
            o for o in objectives if (o.level or "").upper() == "DEPARTMENT" and o.plant_id == scope_id
        ]
    elif level == "DEPARTMENT":
        child_objs = [
            o for o in objectives
            if (o.level or "").upper() == "TEAM" and o.department_id == scope_id
        ]
    elif level == "TEAM":
        child_objs = [
            o for o in objectives
            if (o.level or "").upper() == "INDIVIDUAL" and o.team_id == scope_id
        ]

    progress = (
        sum(float(o.progress or 0) for o in child_objs) / len(child_objs) if child_objs else 0.0
    )
    center = _synthetic_orbit_node(
        f"center-{level_lower}-{scope_id}",
        scope_entity_name,
        level_lower,
        progress,
        user,
        region=scope_id if level == "REGION" else None,
        plant=scope_id if level == "PLANT" else None,
        department=scope_id if level == "DEPARTMENT" else None,
        team=scope_id if level == "TEAM" else None,
        strategic_weight=5,
    )
    return [center] + nodes


def _make_edge(
    source: str,
    target: str,
    alignment_type: str,
    progress: float,
    *,
    edge_type: str = "CASCADE",
    is_dashed: bool = False,
    is_upstream: bool = False,
) -> Dict[str, Any]:
    alignment_score = _alignment_score(progress)
    is_broken = alignment_score < 40
    dashed = is_dashed or edge_type == "FUNCTIONAL"
    return {
        "source": source,
        "target": target,
        "contribution_weight": min(5, max(1, int((alignment_score or 50) / 20))),
        "alignment_type": alignment_type,
        "edge_type": edge_type,
        "contribution_score": alignment_score,
        "is_broken": is_broken,
        "is_dashed": dashed,
        "is_upstream": is_upstream,
    }


def get_alignment_edges(
    objectives: List[Objective],
    user: User,
    db: Session,
    org_id: str,
) -> List[Dict[str, Any]]:
    """Build cascade, functional, and peer-connection edges."""
    start_time = time.time()
    edges: List[Dict[str, Any]] = []
    seen = set()
    okr_ids = {obj.id for obj in objectives}

    level_to_type = {
        "ORGANIZATION": "strategic",
        "REGION": "strategic",
        "PLANT": "operational",
        "DEPARTMENT": "operational",
        "TEAM": "support",
        "INDIVIDUAL": "dependency",
    }

    def _add(edge: Dict[str, Any]) -> None:
        key = (edge["source"], edge["target"], edge.get("edge_type"), edge["alignment_type"])
        if key in seen:
            return
        seen.add(key)
        edges.append(edge)

    for obj in objectives:
        progress = float(obj.progress or 0)
        if obj.parent_id and obj.parent_id in okr_ids:
            _add(_make_edge(
                obj.parent_id,
                obj.id,
                level_to_type.get(obj.level or "INDIVIDUAL", "dependency"),
                progress,
                edge_type="CASCADE",
            ))
        if obj.functional_parent_obj_id and obj.functional_parent_obj_id in okr_ids:
            _add(_make_edge(
                obj.functional_parent_obj_id,
                obj.id,
                "cross-functional",
                progress,
                edge_type="FUNCTIONAL",
                is_dashed=True,
            ))

    connections = (
        db.query(ObjectiveConnection)
        .filter(ObjectiveConnection.org_id == org_id)
        .all()
    )
    obj_by_id = {o.id: o for o in objectives}
    for conn in connections:
        if conn.objective_id_1 not in okr_ids or conn.objective_id_2 not in okr_ids:
            continue
        src_obj = obj_by_id.get(conn.objective_id_1)
        tgt_obj = obj_by_id.get(conn.objective_id_2)
        if not src_obj or not tgt_obj:
            continue
        avg_progress = (float(src_obj.progress or 0) + float(tgt_obj.progress or 0)) / 2
        _add(_make_edge(
            conn.objective_id_1,
            conn.objective_id_2,
            _connection_type_to_alignment(conn.connection_type),
            avg_progress,
            edge_type=conn.connection_type or "RELATED_TO",
            is_dashed=True,
        ))

    elapsed = time.time() - start_time
    logger.info(f"ALIGNMENT: Built {len(edges)} edges in {elapsed:.3f}s")
    return edges


def add_upstream_parent_stubs(
    nodes: List[Dict[str, Any]],
    objectives: List[Objective],
    db: Session,
    current_user: User,
    user_map: Dict[str, User],
    name_maps: Dict[str, Dict[str, str]],
    plant_region_map: Dict[str, Dict[str, str]],
) -> List[Dict[str, Any]]:
    """Add collapsed upstream parent nodes when parent is outside scoped set."""
    node_ids = {n["id"] for n in nodes}
    missing_parent_ids = set()
    for obj in objectives:
        if obj.parent_id and obj.parent_id not in node_ids:
            missing_parent_ids.add(obj.parent_id)
        if obj.functional_parent_obj_id and obj.functional_parent_obj_id not in node_ids:
            missing_parent_ids.add(obj.functional_parent_obj_id)

    if not missing_parent_ids:
        return nodes

    parents = db.query(Objective).filter(Objective.id.in_(missing_parent_ids)).all()
    extra = [
        build_constellation_node(p, current_user, user_map, name_maps, plant_region_map)
        for p in parents
    ]
    for n in extra:
        n["is_upstream_stub"] = True
        n["is_orphaned"] = False
    return extra + nodes


def build_line_of_sight_chain(
    objectives: List[Objective],
    user_id: str,
    db: Session,
) -> List[Dict[str, Any]]:
    """Upward chain from employee's primary objective to organization."""
    primary = next(
        (o for o in objectives if o.owner_id == user_id and (o.level or "").upper() == "INDIVIDUAL"),
        None,
    )
    if not primary:
        primary = next((o for o in objectives if o.owner_id == user_id), None)
    if not primary:
        return []

    chain: List[Dict[str, Any]] = []
    visited = set()
    current = primary
    while current and current.id not in visited:
        visited.add(current.id)
        chain.append({
            "id": current.id,
            "title": current.title,
            "level": (current.level or "INDIVIDUAL").lower(),
            "progress": int(current.progress or 0),
        })
        if not current.parent_id:
            break
        current = db.query(Objective).filter(Objective.id == current.parent_id).first()
    return chain


# ────────────────────────────────────────────────────────────────────────────
# MAIN CONSTELLATION ENDPOINT
# ────────────────────────────────────────────────────────────────────────────

@router.get("")
def get_constellation(
    org_id: str = Query(..., description="Organization ID"),
    levels: Optional[str] = Query(None, description="Comma-separated OKR levels to include"),
    progress_min: Optional[int] = Query(0, description="Minimum progress percentage"),
    progress_max: Optional[int] = Query(100, description="Maximum progress percentage"),
    include_orphaned: Optional[bool] = Query(True, description="Include orphaned OKRs"),
    cycle_id: Optional[str] = Query(None, description="Performance cycle ID"),
    function_area: Optional[str] = Query(None, description="Filter by corporate function"),
    group_by: Optional[str] = Query(None, description="Group nodes: function"),
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    """
    Get constellation data for visualization.
    Automatically filters based on user's role and organizational scope.
    
    Returns:
    {
        nodes: [ConstellationNode],
        edges: [ConstellationEdge],
        metadata: {
            total_okrs: int,
            total_users: int,
            organization_name: str,
            user_scope: str,
            generated_at: str
        }
    }
    """
    request_start = time.time()
    logger.info(f"CONSTELLATION: Starting request for org_id={org_id}")
    
    # Get current user
    auth_start = time.time()
    current_user = get_current_user_from_jwt(payload, db)
    _require_constellation_access(current_user)
    auth_elapsed = time.time() - auth_start
    logger.debug(f"CONSTELLATION: Auth check took {auth_elapsed:.3f}s")
    
    resolved_cycle_id = _resolve_cycle_id(db, org_id, cycle_id)
    fa_filter = normalize_function_area(function_area)
    role = normalize_role(current_user.system_role)
    if role not in (SystemRole.CEO, SystemRole.SUPER_ADMIN):
        viewer_fa = function_area_for_user(current_user)
        if viewer_fa:
            fa_filter = viewer_fa
        elif fa_filter:
            raise HTTPException(403, "Not authorized to view this function area")

    group_mode = (group_by or "").strip().lower() == "function"

    # Check cache first
    cache_key = _get_cache_key(
        current_user.id,
        org_id,
        levels,
        progress_min,
        progress_max,
        resolved_cycle_id or "",
        fa_filter or "",
        "function" if group_mode else "",
    )
    cached = _get_cached(cache_key)
    if cached:
        cached["metadata"]["from_cache"] = True
        cached["metadata"]["total_time_ms"] = int((time.time() - request_start) * 1000)
        return cached
    
    # Verify user's org access
    if current_user.org_id != org_id and normalize_role(current_user.system_role) != SystemRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Access denied to this organization")
    
    # Get user's scope
    scope = get_user_scope(current_user, db)
    logger.info(f"CONSTELLATION: User scope is {scope['level']} (role={current_user.system_role})")
    
    # Parse requested levels
    requested_levels = []
    if levels:
        requested_levels = [l.strip().upper() for l in levels.split(",")]
        if "EMPLOYEE" in requested_levels:
            requested_levels = [
                "INDIVIDUAL" if l == "EMPLOYEE" else l for l in requested_levels
            ]
    else:
        requested_levels = scope.get("view_levels") or scope["allowed_child_levels"]
    
    # Filter to only levels user can see
    filtered_levels = [l for l in requested_levels if l in scope["allowed_child_levels"]]
    
    if not filtered_levels:
        filtered_levels = scope.get("view_levels") or scope["allowed_child_levels"]
    
    logger.debug(f"CONSTELLATION: Filtered levels = {filtered_levels}")
    
    plant_region_map = _build_plant_region_map(db, org_id)

    # Build query — visibility service for parity with OKR list (subtree + parent peek)
    query_start = time.time()
    query = db.query(Objective).filter(Objective.org_id == org_id)
    query = apply_okr_visibility_filter(query, current_user, db, org_id)

    if filtered_levels:
        query = query.filter(Objective.level.in_(filtered_levels))

    if resolved_cycle_id:
        query = query.filter(
            or_(Objective.cycle_id == resolved_cycle_id, Objective.cycle_id.is_(None))
        )

    if fa_filter:
        query = query.filter(Objective.function_area == fa_filter)

    query = query.filter(
        and_(
            Objective.progress >= progress_min,
            Objective.progress <= progress_max,
        )
    )
    
    # Execute query
    objectives = query.all()
    query_elapsed = time.time() - query_start
    logger.info(f"CONSTELLATION: DB query returned {len(objectives)} objectives in {query_elapsed:.3f}s")
    
    # Filter orphaned if needed
    if not include_orphaned:
        objects_before = len(objectives)
        objectives = [obj for obj in objectives if obj.parent_id]
        logger.debug(f"CONSTELLATION: Filtered orphaned: {objects_before} → {len(objectives)}")
    
    # OPTIMIZATION: Pre-fetch all users to avoid N+1 query
    user_fetch_start = time.time()
    owner_ids = [obj.owner_id for obj in objectives if obj.owner_id]
    user_map = {}
    if owner_ids:
        users = db.query(User).filter(User.id.in_(owner_ids)).all()
        user_map = {user.id: user for user in users}
        logger.info(f"CONSTELLATION: Fetched {len(users)} unique users in {time.time() - user_fetch_start:.3f}s")
    
    # Build constellation nodes
    nodes_start = time.time()
    name_maps = _build_entity_name_maps(db, objectives, plant_region_map)
    nodes = [
        build_constellation_node(
            obj,
            current_user,
            user_map,
            name_maps,
            plant_region_map,
            function_cluster=obj.function_area if group_mode else None,
        )
        for obj in objectives
    ]
    nodes = add_upstream_parent_stubs(
        nodes, objectives, db, current_user, user_map, name_maps, plant_region_map
    )

    scope_entity_name = resolve_scope_entity_name(scope, db)
    nodes = ensure_scope_center_node(
        nodes, scope, scope_entity_name, objectives, current_user, plant_region_map
    )

    if scope["level"] == "ORGANIZATION":
        nodes = augment_org_region_orbit_nodes(
            nodes, objectives, org_id, db, current_user, plant_region_map
        )
        region_ids = {
            n.get("region")
            for n in nodes
            if n.get("level") == "region" and n.get("region")
        }
        for rid in region_ids:
            nodes = augment_region_plant_orbit_nodes(
                nodes,
                objectives,
                rid,
                org_id,
                db,
                current_user,
                plant_region_map,
            )
        plant_ids = {
            n.get("plant")
            for n in nodes
            if n.get("level") == "plant" and n.get("plant")
        }
        for pid in plant_ids:
            nodes = augment_plant_department_orbit_nodes(
                nodes, objectives, pid, org_id, db, current_user
            )
        dept_ids = {
            n.get("department")
            for n in nodes
            if n.get("level") == "department" and n.get("department")
        }
        for did in dept_ids:
            nodes = augment_department_team_orbit_nodes(
                nodes, objectives, did, org_id, db, current_user
            )
    elif scope["level"] == "REGION" and scope.get("scope_id"):
        region_id = scope["scope_id"]
        nodes = augment_region_plant_orbit_nodes(
            nodes,
            objectives,
            region_id,
            org_id,
            db,
            current_user,
            plant_region_map,
        )
        plant_ids = list(_plant_ids_for_region(plant_region_map, region_id))
        nodes = _augment_departments_and_teams_for_plants(
            nodes, objectives, plant_ids, org_id, db, current_user
        )
    elif scope["level"] == "PLANT" and scope.get("scope_id"):
        plant_id = scope["scope_id"]
        nodes = augment_plant_department_orbit_nodes(
            nodes, objectives, plant_id, org_id, db, current_user
        )
        dept_ids = _department_ids_for_plants(db, org_id, [plant_id])
        for dept_id in dept_ids:
            nodes = augment_department_team_orbit_nodes(
                nodes, objectives, dept_id, org_id, db, current_user
            )
    elif scope["level"] == "DEPARTMENT" and scope.get("scope_id"):
        nodes = augment_department_team_orbit_nodes(
            nodes, objectives, scope["scope_id"], org_id, db, current_user
        )

    nodes_elapsed = time.time() - nodes_start
    logger.info(f"CONSTELLATION: Built {len(nodes)} nodes in {nodes_elapsed:.3f}s")
    
    # Build edges (cascade + cross-functional + peer connections)
    edge_objectives = objectives
    extra_parent_ids = {
        n["id"] for n in nodes if n.get("is_upstream_stub")
    }
    if extra_parent_ids:
        extra_objs = db.query(Objective).filter(Objective.id.in_(extra_parent_ids)).all()
        edge_objectives = list({o.id: o for o in objectives + extra_objs}.values())
    edges = get_alignment_edges(edge_objectives, current_user, db, org_id)

    line_of_sight = []
    if scope["level"] == "EMPLOYEE":
        line_of_sight = build_line_of_sight_chain(objectives, current_user.id, db)
    
    # Get organization info
    org = db.query(Organization).filter(Organization.id == org_id).first()
    org_name = org.name if org else org_id
    
    # Count unique owners
    unique_owners = set(obj.owner_id for obj in objectives if obj.owner_id)
    
    total_elapsed = time.time() - request_start
    logger.info(
        f"CONSTELLATION: Request complete in {total_elapsed:.3f}s | "
        f"Nodes: {len(nodes)}, Edges: {len(edges)}, Users: {len(unique_owners)}"
    )
    
    broken_count = len([e for e in edges if e.get("is_broken")])
    orphan_count = len([n for n in nodes if n.get("is_orphaned") and not n.get("is_upstream_stub")])
    cascade_edges = len([e for e in edges if e.get("edge_type") == "CASCADE"])
    functional_edges = len([e for e in edges if e.get("edge_type") == "FUNCTIONAL"])

    function_stats: Dict[str, Any] = {}
    for n in nodes:
        fa = n.get("function_area")
        if not fa:
            continue
        bucket = function_stats.setdefault(
            fa,
            {"count": 0, "avg_progress": 0.0, "functional_edges": 0, "label": FUNCTION_AREA_LABELS.get(fa, fa)},
        )
        bucket["count"] += 1
        bucket["avg_progress"] += n.get("progress", 0)
    for fa, bucket in function_stats.items():
        if bucket["count"]:
            bucket["avg_progress"] = round(bucket["avg_progress"] / bucket["count"], 1)
        node_ids = {n["id"] for n in nodes if n.get("function_area") == fa}
        bucket["functional_edges"] = len(
            [
                e
                for e in edges
                if e.get("edge_type") == "FUNCTIONAL"
                and e["source"] in node_ids
                and e["target"] in node_ids
            ]
        )

    result = {
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            "total_okrs": len(nodes),
            "total_users": len(unique_owners),
            "organization_name": org_name,
            "user_scope": scope["level"],
            "scope_id": scope["scope_id"],
            "scope_entity_name": scope_entity_name,
            "cycle_id": resolved_cycle_id,
            "function_area_filter": fa_filter,
            "group_by": "function" if group_mode else None,
            "function_area_stats": function_stats,
            "cascade_edge_count": cascade_edges,
            "functional_edge_count": functional_edges,
            "orphaned_count": orphan_count,
            "broken_alignment_count": broken_count,
            "line_of_sight": line_of_sight,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "query_time_ms": int(query_elapsed * 1000),
            "total_time_ms": int(total_elapsed * 1000),
        },
    }
    
    # Cache for subsequent requests
    _set_cache(cache_key, result)
    
    return result


@router.get("/stats")
def get_constellation_stats(
    org_id: str = Query(..., description="Organization ID"),
    cycle_id: Optional[str] = Query(None, description="Performance cycle ID"),
    function_area: Optional[str] = Query(None, description="Filter by corporate function"),
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    """Get statistics for constellation visualization."""
    current_user = get_current_user_from_jwt(payload, db)
    _require_constellation_access(current_user)
    resolved_cycle_id = _resolve_cycle_id(db, org_id, cycle_id)
    fa_filter = normalize_function_area(function_area)
    role = normalize_role(current_user.system_role)
    if role not in (SystemRole.CEO, SystemRole.SUPER_ADMIN):
        viewer_fa = function_area_for_user(current_user)
        if viewer_fa:
            fa_filter = viewer_fa

    query = db.query(Objective).filter(Objective.org_id == org_id)
    query = apply_okr_visibility_filter(query, current_user, db, org_id)
    if resolved_cycle_id:
        query = query.filter(
            or_(Objective.cycle_id == resolved_cycle_id, Objective.cycle_id.is_(None))
        )
    if fa_filter:
        query = query.filter(Objective.function_area == fa_filter)

    objectives = query.all()
    
    # Calculate health distribution based on progress
    def get_health(progress):
        progress = float(progress or 0)
        if progress >= 80:
            return "healthy"
        elif progress >= 60:
            return "needs_attention"
        elif progress >= 40:
            return "critical"
        else:
            return "blocked"
    
    health_dist = {
        "healthy": len([o for o in objectives if get_health(o.progress) == "healthy"]),
        "needs_attention": len([o for o in objectives if get_health(o.progress) == "needs_attention"]),
        "critical": len([o for o in objectives if get_health(o.progress) == "critical"]),
        "blocked": len([o for o in objectives if get_health(o.progress) == "blocked"]),
    }
    
    # Calculate risk distribution
    def get_risk(progress, status):
        progress = float(progress or 0)
        if progress < 40 or status == "REJECTED":
            return "critical"
        elif progress < 60:
            return "high"
        elif progress < 80:
            return "medium"
        else:
            return "low"
    
    risk_dist = {
        "critical": len([o for o in objectives if get_risk(o.progress, o.okr_status) == "critical"]),
        "high": len([o for o in objectives if get_risk(o.progress, o.okr_status) == "high"]),
        "medium": len([o for o in objectives if get_risk(o.progress, o.okr_status) == "medium"]),
        "low": len([o for o in objectives if get_risk(o.progress, o.okr_status) == "low"]),
    }
    
    # Calculate level distribution
    level_dist = {}
    for level in ["ORGANIZATION", "REGION", "PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"]:
        level_dist[level] = len([o for o in objectives if o.level == level])
    
    avg_progress = sum(float(o.progress or 0) for o in objectives) / len(objectives) if objectives else 0
    avg_confidence = 70  # Default confidence since we calculate it dynamically
    
    edges = get_alignment_edges(objectives, current_user, db, org_id)

    by_function: Dict[str, Any] = {}
    for obj in objectives:
        fa = normalize_function_area(obj.function_area)
        if not fa:
            continue
        bucket = by_function.setdefault(
            fa,
            {
                "label": FUNCTION_AREA_LABELS.get(fa, fa),
                "count": 0,
                "unaligned_departments": 0,
                "avg_progress": 0.0,
            },
        )
        bucket["count"] += 1
        bucket["avg_progress"] += float(obj.progress or 0)
        if (obj.level or "").upper() == "DEPARTMENT" and not obj.functional_parent_obj_id:
            bucket["unaligned_departments"] += 1
    for fa, bucket in by_function.items():
        if bucket["count"]:
            bucket["avg_progress"] = round(bucket["avg_progress"] / bucket["count"], 1)
        node_ids = {o.id for o in objectives if o.function_area == fa}
        bucket["functional_edge_count"] = len(
            [
                e
                for e in edges
                if e.get("edge_type") == "FUNCTIONAL"
                and e["source"] in node_ids
                and e["target"] in node_ids
            ]
        )

    return {
        "totalNodes": len(objectives),
        "totalEdges": len(edges),
        "healthDistribution": health_dist,
        "riskDistribution": risk_dist,
        "levelDistribution": level_dist,
        "avgProgress": int(avg_progress),
        "avgConfidence": int(avg_confidence),
        "orphanedCount": len([o for o in objectives if not o.parent_id]),
        "brokenAlignmentCount": len([e for e in edges if e.get("is_broken")]),
        "cascadeEdgeCount": len([e for e in edges if e.get("edge_type") == "CASCADE"]),
        "functionalEdgeCount": len([e for e in edges if e.get("edge_type") == "FUNCTIONAL"]),
        "functionAreaFilter": fa_filter,
        "byFunction": by_function,
    }


def _generate_rule_insights(nodes: List[Dict], edges: List[Dict]) -> List[Dict[str, Any]]:
    """Rule-based alignment insights (mirrors frontend alignmentUtils)."""
    insights: List[Dict[str, Any]] = []
    target_ids = {e["target"] for e in edges}

    for node in nodes:
        if node.get("level") == "organization" or node.get("is_upstream_stub"):
            continue
        if node["id"] not in target_ids and not node.get("is_orphaned"):
            insights.append({
                "id": f"orphan-{node['id']}",
                "type": "orphan",
                "severity": "high",
                "title": f"Unaligned OKR: {(node.get('objective') or 'Untitled')[:60]}",
                "description": "This OKR has no parent alignment edge in your scope.",
                "affectedNodes": [node["id"]],
                "actionable": True,
                "actionText": "Link to parent OKR",
            })

    weak = [e for e in edges if e.get("contribution_score", 100) < 40 or e.get("is_broken")]
    if len(weak) > max(1, len(edges) * 0.2):
        insights.append({
            "id": "weak-alignments",
            "type": "weak_alignment",
            "severity": "high",
            "title": f"{len(weak)} weak alignment connections",
            "description": "More than 20% of alignment edges have low contribution scores.",
            "affectedNodes": list({e["source"] for e in weak} | {e["target"] for e in weak})[:10],
            "impact": int(len(weak) / max(len(edges), 1) * 100),
            "actionable": True,
            "actionText": "Review underperforming links",
        })

    for node in nodes:
        children = [e for e in edges if e["source"] == node["id"]]
        if len(children) >= 3:
            avg = sum(e.get("contribution_score", 0) for e in children) / len(children)
            if avg < 50:
                insights.append({
                    "id": f"bottleneck-{node['id']}",
                    "type": "bottleneck",
                    "severity": "critical",
                    "title": f"Bottleneck: {(node.get('objective') or 'Untitled')[:50]}",
                    "description": f"{len(children)} dependents with avg alignment {int(avg)}%.",
                    "affectedNodes": [node["id"]],
                    "impact": int(avg),
                    "actionable": True,
                    "actionText": "Investigate cascade",
                })

    critical_nodes = [n for n in nodes if n.get("risk_level") == "critical"]
    if critical_nodes:
        insights.append({
            "id": "risk-propagation",
            "type": "risk_propagation",
            "severity": "critical",
            "title": f"{len(critical_nodes)} OKRs at critical risk",
            "description": "Low progress may propagate up the alignment chain.",
            "affectedNodes": [n["id"] for n in critical_nodes[:8]],
            "actionable": True,
            "actionText": "Open risk view",
        })

    return insights[:12]


@router.get("/insights")
def get_constellation_insights(
    org_id: str = Query(..., description="Organization ID"),
    cycle_id: Optional[str] = Query(None),
    include_ai: bool = Query(True, description="Include Azure OpenAI prescriptions"),
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    """Rule-based + optional AI alignment insights."""
    current_user = get_current_user_from_jwt(payload, db)
    if current_user.org_id != org_id and normalize_role(current_user.system_role) != SystemRole.SUPER_ADMIN:
        raise HTTPException(403, "Access denied")

    data = get_constellation(
        org_id=org_id,
        levels=None,
        progress_min=0,
        progress_max=100,
        include_orphaned=True,
        cycle_id=cycle_id,
        db=db,
        payload=payload,
    )
    nodes = data["nodes"]
    edges = data["edges"]
    rule_insights = _generate_rule_insights(nodes, edges)

    ai_prescriptions: List[Dict[str, Any]] = []
    if include_ai and rule_insights:
        try:
            from server.services.azure_openai_service import AzureOpenAIService, _ai_configured
            if _ai_configured():
                svc = AzureOpenAIService()
                context = json.dumps({
                    "insights": rule_insights[:5],
                    "org": data["metadata"].get("organization_name"),
                    "scope": data["metadata"].get("user_scope"),
                })
                prompt = (
                    "You are a manufacturing OKR alignment advisor. Given these alignment gaps, "
                    "return JSON with key 'prescriptions': array of up to 3 objects with "
                    "title, description, priority (critical|high|medium). Be specific to manufacturing "
                    f"(OEE, quality, maintenance, supply chain). Context: {context}"
                )
                result = svc._complete_json(
                    "Respond only with valid JSON.",
                    prompt,
                )
                ai_prescriptions = result.get("prescriptions", [])[:3]
        except Exception as exc:
            logger.warning(f"AI insights fallback: {exc}")
            ai_prescriptions = [{
                "title": "AI unavailable",
                "description": str(exc)[:200],
                "priority": "low",
            }]

    return {
        "rule_insights": rule_insights,
        "ai_prescriptions": ai_prescriptions,
        "metadata": data["metadata"],
    }


@router.post("/connections")
def create_objective_connection(
    org_id: str = Query(...),
    body: dict = Body(...),
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    """Create explicit cross-functional peer link between two objectives."""
    current_user = get_current_user_from_jwt(payload, db)
    role = normalize_role(current_user.system_role)
    if role not in (
        SystemRole.CEO, SystemRole.SUPER_ADMIN, SystemRole.PLANT_HEAD,
        SystemRole.DEPT_HEAD, SystemRole.REGIONAL_HEAD, SystemRole.VP_OPERATIONS,
        SystemRole.COO, SystemRole.CRO,
    ):
        raise HTTPException(403, "Insufficient role to create connections")

    obj1_id = body.get("objective_id_1")
    obj2_id = body.get("objective_id_2")
    conn_type = (body.get("connection_type") or "RELATED_TO").upper()
    if conn_type not in ("SUPPORTS", "DEPENDS_ON", "RELATED_TO"):
        raise HTTPException(400, "connection_type must be SUPPORTS, DEPENDS_ON, or RELATED_TO")
    if not obj1_id or not obj2_id or obj1_id == obj2_id:
        raise HTTPException(400, "objective_id_1 and objective_id_2 required and must differ")

    o1 = db.query(Objective).filter(Objective.id == obj1_id, Objective.org_id == org_id).first()
    o2 = db.query(Objective).filter(Objective.id == obj2_id, Objective.org_id == org_id).first()
    if not o1 or not o2:
        raise HTTPException(404, "One or both objectives not found")

    existing = (
        db.query(ObjectiveConnection)
        .filter(
            ObjectiveConnection.org_id == org_id,
            or_(
                and_(
                    ObjectiveConnection.objective_id_1 == obj1_id,
                    ObjectiveConnection.objective_id_2 == obj2_id,
                ),
                and_(
                    ObjectiveConnection.objective_id_1 == obj2_id,
                    ObjectiveConnection.objective_id_2 == obj1_id,
                ),
            ),
        )
        .first()
    )
    if existing:
        raise HTTPException(409, "Connection already exists")

    conn = ObjectiveConnection(
        org_id=org_id,
        objective_id_1=obj1_id,
        objective_id_2=obj2_id,
        connection_type=conn_type,
        cycle_id=o1.cycle_id or o2.cycle_id,
        created_by_id=current_user.id,
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    _constellation_cache.clear()
    return {
        "id": conn.id,
        "objective_id_1": conn.objective_id_1,
        "objective_id_2": conn.objective_id_2,
        "connection_type": conn.connection_type,
    }


@router.delete("/connections/{connection_id}")
def delete_objective_connection(
    connection_id: str,
    org_id: str = Query(...),
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    current_user = get_current_user_from_jwt(payload, db)
    conn = (
        db.query(ObjectiveConnection)
        .filter(ObjectiveConnection.id == connection_id, ObjectiveConnection.org_id == org_id)
        .first()
    )
    if not conn:
        raise HTTPException(404, "Connection not found")
    db.delete(conn)
    db.commit()
    _constellation_cache.clear()
    return {"deleted": True}
