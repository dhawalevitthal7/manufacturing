"""
Permission Matrix Routes — Enterprise RBAC configuration API.
Provides endpoints for the admin to view the full permission registry,
get/set per-role permission rules, and seed defaults.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from server.database import get_db
from server.models import RolePermissionRule
from server.permission_registry import (
    PERMISSION_REGISTRY, PERMISSION_CATEGORIES, HIERARCHY_SCOPES,
    SYSTEM_ROLES, ALL_ACTIONS,
)
from server.auth import require_super_admin
from server.services.audit_service import audit_super_admin_action, ROLE_MATRIX_WRITE

router = APIRouter(prefix="/api/permission-matrix", tags=["permission-matrix"])


# ── Schemas ──
class PermissionRuleUpdate(BaseModel):
    permission_key: str
    can_view: bool = False
    can_create: bool = False
    can_edit: bool = False
    can_delete: bool = False
    can_approve: bool = False
    can_assign: bool = False
    can_manage: bool = False
    hierarchy_scope: str = "SELF"

class BulkPermissionUpdate(BaseModel):
    system_role: str
    rules: List[PermissionRuleUpdate]


# ── Registry (static catalog) ──

@router.get("/registry")
def get_permission_registry():
    """Return the full permission catalog: categories, permissions, scopes, roles."""
    return {
        "categories": PERMISSION_CATEGORIES,
        "permissions": PERMISSION_REGISTRY,
        "hierarchy_scopes": HIERARCHY_SCOPES,
        "system_roles": SYSTEM_ROLES,
        "actions": ALL_ACTIONS,
    }


# ── Configured Rules (per org, per role) ──

@router.get("/rules")
def get_permission_rules(
    db: Session = Depends(get_db),
    org_id: str = "",
    system_role: str = "",
):
    """Get all configured permission rules for an org, optionally filtered by role."""
    q = db.query(RolePermissionRule).filter(RolePermissionRule.org_id == org_id)
    if system_role:
        q = q.filter(RolePermissionRule.system_role == system_role)
    rules = q.all()
    return [_serialize_rule(r) for r in rules]


@router.get("/rules/{role}")
def get_role_rules(role: str, db: Session = Depends(get_db), org_id: str = ""):
    """Get all permission rules for a specific role."""
    rules = db.query(RolePermissionRule).filter(
        RolePermissionRule.org_id == org_id,
        RolePermissionRule.system_role == role,
    ).all()
    # Return a dict keyed by permission_key for easy frontend consumption
    result = {}
    for r in rules:
        result[r.permission_key] = {
            "id": r.id,
            "can_view": r.can_view,
            "can_create": r.can_create,
            "can_edit": r.can_edit,
            "can_delete": r.can_delete,
            "can_approve": r.can_approve,
            "can_assign": r.can_assign,
            "can_manage": r.can_manage,
            "hierarchy_scope": r.hierarchy_scope,
        }
    return result


@router.put("/rules/bulk")
def bulk_update_rules(
    payload: BulkPermissionUpdate,
    db: Session = Depends(get_db),
    org_id: str = "",
    _auth: dict = Depends(require_super_admin),
):
    """Bulk upsert permission rules for a role. SUPER_ADMIN only."""
    upserted = 0
    for rule_data in payload.rules:
        existing = db.query(RolePermissionRule).filter(
            RolePermissionRule.org_id == org_id,
            RolePermissionRule.system_role == payload.system_role,
            RolePermissionRule.permission_key == rule_data.permission_key,
        ).first()
        if existing:
            existing.can_view = rule_data.can_view
            existing.can_create = rule_data.can_create
            existing.can_edit = rule_data.can_edit
            existing.can_delete = rule_data.can_delete
            existing.can_approve = rule_data.can_approve
            existing.can_assign = rule_data.can_assign
            existing.can_manage = rule_data.can_manage
            existing.hierarchy_scope = rule_data.hierarchy_scope
            db.add(existing)
        else:
            db.add(RolePermissionRule(
                org_id=org_id,
                system_role=payload.system_role,
                permission_key=rule_data.permission_key,
                can_view=rule_data.can_view,
                can_create=rule_data.can_create,
                can_edit=rule_data.can_edit,
                can_delete=rule_data.can_delete,
                can_approve=rule_data.can_approve,
                can_assign=rule_data.can_assign,
                can_manage=rule_data.can_manage,
                hierarchy_scope=rule_data.hierarchy_scope,
            ))
        upserted += 1
    db.commit()
    audit_super_admin_action(
        org_id=org_id,
        actor_user_id=str(_auth.get("sub") or ""),
        action=ROLE_MATRIX_WRITE,
        entity_type="ROLE_PERMISSION_RULE",
        entity_id=None,
        details={"op": "bulk", "system_role": payload.system_role, "upserted": upserted},
    )
    return {"upserted": upserted, "role": payload.system_role}


@router.post("/seed-defaults")
def seed_default_rules(
    db: Session = Depends(get_db),
    org_id: str = "",
    _auth: dict = Depends(require_super_admin),
):
    """Seed sensible default permission rules for all system roles."""
    from server.permission_registry import PERMISSION_REGISTRY
    created = 0
    for role in SYSTEM_ROLES:
        scope = _default_scope(role)
        for perm in PERMISSION_REGISTRY:
            existing = db.query(RolePermissionRule).filter(
                RolePermissionRule.org_id == org_id,
                RolePermissionRule.system_role == role,
                RolePermissionRule.permission_key == perm["key"],
            ).first()
            if existing:
                continue
            flags = _default_flags(role, perm)
            db.add(RolePermissionRule(
                org_id=org_id, system_role=role,
                permission_key=perm["key"], hierarchy_scope=scope, **flags,
            ))
            created += 1
    db.commit()
    audit_super_admin_action(
        org_id=org_id,
        actor_user_id=str(_auth.get("sub") or ""),
        action=ROLE_MATRIX_WRITE,
        entity_type="ROLE_PERMISSION_RULE",
        entity_id=org_id,
        details={"op": "seed", "created": created},
    )
    return {"seeded": created}


# ── Helpers ──

def _serialize_rule(r: RolePermissionRule) -> dict:
    return {
        "id": r.id, "system_role": r.system_role,
        "permission_key": r.permission_key,
        "can_view": r.can_view, "can_create": r.can_create,
        "can_edit": r.can_edit, "can_delete": r.can_delete,
        "can_approve": r.can_approve, "can_assign": r.can_assign,
        "can_manage": r.can_manage, "hierarchy_scope": r.hierarchy_scope,
    }


def _default_scope(role: str) -> str:
    return {
        "SUPER_ADMIN": "ORGANIZATION", "CEO": "ORGANIZATION",
        "VP_OPERATIONS": "ORGANIZATION", "HR_HEAD": "ORGANIZATION", "CHRO": "ORGANIZATION",
        "CFO": "ORGANIZATION", "CMO": "ORGANIZATION", "CPO": "ORGANIZATION", "CSO": "ORGANIZATION",
        "CTO": "ORGANIZATION", "COO": "ORGANIZATION", "CRO": "ORGANIZATION",
        "FUNCTIONAL_SUB_HEAD": "ORGANIZATION",
        "HR_ADMIN": "ORGANIZATION", "PLANT_HEAD": "PLANT",
        "PLANT_MANAGER": "PLANT", "DEPT_HEAD": "DEPARTMENT",
        "AREA_SALES_MANAGER": "DEPARTMENT",
        "MANAGER": "TEAM", "TEAM_LEAD": "TEAM",
        "SUPERVISOR": "DIRECT_REPORTS", "EMPLOYEE": "SELF",
    }.get(role, "SELF")


def _default_flags(role: str, perm: dict) -> dict:
    """Generate sensible default permission flags per role."""
    cat = perm["category"]
    actions = perm["actions"]
    f = {"can_view": False, "can_create": False, "can_edit": False,
         "can_delete": False, "can_approve": False, "can_assign": False, "can_manage": False}

    if role == "SUPER_ADMIN":
        for a in actions:
            f[f"can_{a}"] = True
        return f

    if role in ("CEO", "VP_OPERATIONS"):
        f["can_view"] = "view" in actions
        if cat in ("APPROVAL",):
            f["can_approve"] = "approve" in actions
        return f

    if role in ("HR_HEAD", "HR_ADMIN", "CHRO", "CFO", "CMO", "CPO", "CSO", "CTO", "FUNCTIONAL_SUB_HEAD"):
        f["can_view"] = "view" in actions
        if cat in ("EMPLOYEE", "REVIEW", "OKR", "PROGRESS", "ALIGNMENT", "APPROVAL"):
            if "view" in actions:
                f["can_view"] = True
            if cat in ("APPROVAL", "OKR", "PROGRESS") and "approve" in actions:
                f["can_approve"] = True
        if cat in ("EMPLOYEE", "REVIEW"):
            for a in actions:
                f[f"can_{a}"] = True
        if cat == "SETTINGS":
            f["can_manage"] = "manage" in actions
        return f

    if role in ("PLANT_HEAD", "PLANT_MANAGER"):
        if cat in ("PLANT", "DEPARTMENT", "TEAM", "OKR", "PROGRESS", "REVIEW", "ALIGNMENT", "HIERARCHY"):
            f["can_view"] = "view" in actions
        if cat in ("OKR", "PROGRESS"):
            f["can_approve"] = "approve" in actions
        if cat == "PLANT":
            f["can_edit"] = "edit" in actions
        return f

    if role == "DEPT_HEAD":
        if cat in ("DEPARTMENT", "TEAM", "OKR", "PROGRESS", "REVIEW", "ALIGNMENT"):
            f["can_view"] = "view" in actions
        if cat in ("OKR", "PROGRESS"):
            f["can_approve"] = "approve" in actions
        return f

    if role in ("MANAGER", "TEAM_LEAD"):
        if cat in ("TEAM", "OKR", "PROGRESS", "REVIEW", "ALIGNMENT"):
            f["can_view"] = "view" in actions
        if cat == "PROGRESS":
            f["can_approve"] = "approve" in actions
            f["can_create"] = "create" in actions
        if cat == "OKR":
            f["can_create"] = "create" in actions
            f["can_edit"] = "edit" in actions
        return f

    if role == "SUPERVISOR":
        if cat in ("PROGRESS", "OKR"):
            f["can_view"] = "view" in actions
            f["can_create"] = "create" in actions
        return f

    # EMPLOYEE
    if cat in ("OKR", "PROGRESS", "REVIEW"):
        f["can_view"] = "view" in actions
    if cat == "PROGRESS":
        f["can_create"] = "create" in actions
    if perm["key"] == "REV_SELF":
        f["can_create"] = True
    return f
