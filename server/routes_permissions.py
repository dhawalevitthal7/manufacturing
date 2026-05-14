"""
Permissions Routes - Handles role-based access control, module visibility, and user invitations.

Implements enterprise RBAC:
- User permission profiles (role + designation + hierarchy scope + module access)
- Module access configuration
- User invitations with pre-assigned roles
- Permission updates
"""

import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from server.database import get_db
from server.models import (
    DashboardModule, ModuleAccess, Designation, User, Organization,
    UserPermissionProfile, UserInvitation
)
from server.schemas import (
    ModuleAccessCreate, ModuleAccessBulkUpdate, UserInvitationCreate,
    UserInvitationAccept, UserPermissionUpdate
)
from server.auth import _canonical_role_for_token, create_access_token, get_password_hash, require_super_admin, require_super_admin_or_hr_head
from server.permissions_service import (
    initialize_user_permissions, get_user_permission_profile,
    DEFAULT_ROLE_CAPABILITIES
)
from server.services.audit_service import (
    audit_super_admin_action,
    MODULE_ACCESS_WRITE,
    PERMISSION_SEED,
    ROLE_ASSIGN,
)

router = APIRouter(prefix="/api/permissions", tags=["permissions"])

# All available dashboard modules — seeded on first call
DEFAULT_MODULES = [
    {"key": "ORG_OKRS", "name": "Organization OKRs", "category": "OKR", "description": "View and manage organization-level objectives"},
    {"key": "PLANT_OKRS", "name": "Plant OKRs", "category": "OKR", "description": "View and manage plant-level objectives"},
    {"key": "DEPT_OKRS", "name": "Department OKRs", "category": "OKR", "description": "View and manage department-level objectives"},
    {"key": "TEAM_OKRS", "name": "Team OKRs", "category": "OKR", "description": "View and manage team-level objectives"},
    {"key": "EMPLOYEE_OKRS", "name": "Employee OKRs", "category": "OKR", "description": "View and manage individual employee objectives"},
    {"key": "PROGRESS_TRACKING", "name": "Progress Tracking", "category": "OKR", "description": "Track and validate OKR progress updates"},
    {"key": "ALIGNMENT_DASHBOARD", "name": "Alignment Dashboard", "category": "ANALYTICS", "description": "Strategic alignment visualization across hierarchy"},
    {"key": "REVIEW_DASHBOARD", "name": "Review Dashboard", "category": "REVIEW", "description": "Manage and view performance reviews"},
    {"key": "REVIEW_ANALYTICS", "name": "Review Analytics", "category": "ANALYTICS", "description": "Performance review analytics and trends"},
    {"key": "TEAM_MANAGEMENT", "name": "Team Management", "category": "MANAGEMENT", "description": "Create and manage teams"},
    {"key": "DEPT_VISIBILITY", "name": "Department Visibility", "category": "VISIBILITY", "description": "View department execution data"},
    {"key": "PLANT_VISIBILITY", "name": "Plant Visibility", "category": "VISIBILITY", "description": "View plant-wide execution data"},
    {"key": "ORG_VISIBILITY", "name": "Organization Visibility", "category": "VISIBILITY", "description": "View organization-wide execution data"},
    {"key": "EMPLOYEE_DIRECTORY", "name": "Employee Directory", "category": "MANAGEMENT", "description": "View and manage employee directory"},
    {"key": "REPORTING_STRUCTURE", "name": "Reporting Structure", "category": "MANAGEMENT", "description": "View and configure reporting hierarchy"},
    {"key": "APPROVAL_QUEUE", "name": "Approval Queue", "category": "MANAGEMENT", "description": "Manage pending approvals and validations"},
    {"key": "ESCALATION_MGMT", "name": "Escalation Management", "category": "MANAGEMENT", "description": "Manage and track escalations"},
    {"key": "AI_INSIGHTS", "name": "AI Insights", "category": "ANALYTICS", "description": "AI-generated execution and performance insights"},
    {"key": "AUDIT_LOGS", "name": "Audit Logs", "category": "MANAGEMENT", "description": "View system audit trail"},
]


# ============================================================================
# MODULE MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/modules")
def list_modules(db: Session = Depends(get_db)):
    """Get all dashboard modules. Seeds defaults if empty."""
    # TODO(phase-3-followup): GET should not have write side-effects. Move seed logic to a dedicated POST.
    modules = db.query(DashboardModule).all()
    if not modules:
        for m in DEFAULT_MODULES:
            db.add(DashboardModule(key=m["key"], name=m["name"], category=m["category"], description=m["description"]))
        db.commit()
        modules = db.query(DashboardModule).all()
    return [{"id": m.id, "key": m.key, "name": m.name, "category": m.category, "description": m.description} for m in modules]


# ============================================================================
# MODULE ACCESS CONFIGURATION
# ============================================================================

@router.get("/access")
def list_access_rules(db: Session = Depends(get_db), org_id: str = "", system_role: str = "", designation_id: str = ""):
    """Get configured module access rules for an org."""
    q = db.query(ModuleAccess).filter(ModuleAccess.org_id == org_id)
    if system_role:
        q = q.filter(ModuleAccess.system_role == system_role)
    if designation_id:
        q = q.filter(ModuleAccess.designation_id == designation_id)
    rules = q.all()
    result = []
    for r in rules:
        mod = db.query(DashboardModule).filter(DashboardModule.id == r.module_id).first()
        desig = db.query(Designation).filter(Designation.id == r.designation_id).first() if r.designation_id else None
        result.append({
            "id": r.id, "module_id": r.module_id, "module_key": mod.key if mod else None,
            "module_name": mod.name if mod else None,
            "system_role": r.system_role, "designation_id": r.designation_id,
            "designation_name": desig.name if desig else None,
            "can_view": r.can_view, "can_create": r.can_create, "can_edit": r.can_edit,
            "can_approve": r.can_approve, "can_delete": r.can_delete,
        })
    return result


@router.post("/access")
def create_access_rule(
    req: ModuleAccessCreate,
    db: Session = Depends(get_db),
    org_id: str = "",
    _auth: dict = Depends(require_super_admin),
):
    """Create a module access rule for a system_role or designation."""
    if not req.system_role and not req.designation_id:
        raise HTTPException(400, "Must specify system_role or designation_id")
    rule = ModuleAccess(
        org_id=org_id, module_id=req.module_id,
        system_role=req.system_role, designation_id=req.designation_id,
        can_view=req.can_view, can_create=req.can_create,
        can_edit=req.can_edit, can_approve=req.can_approve, can_delete=req.can_delete,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    audit_super_admin_action(
        org_id=org_id,
        actor_user_id=str(_auth.get("sub") or ""),
        action=MODULE_ACCESS_WRITE,
        entity_type="MODULE_ACCESS",
        entity_id=rule.id,
        details={"op": "create", "module_id": req.module_id},
    )
    return {"id": rule.id, "status": "created"}


@router.post("/access/bulk")
def bulk_update_access(
    req: ModuleAccessBulkUpdate,
    db: Session = Depends(get_db),
    org_id: str = "",
    _auth: dict = Depends(require_super_admin),
):
    """Bulk set module access rules. Replaces existing rules for matching role/designation."""
    created = 0
    for r in req.access_rules:
        # Upsert: delete existing, create new
        q = db.query(ModuleAccess).filter(ModuleAccess.org_id == org_id, ModuleAccess.module_id == r.module_id)
        if r.system_role:
            q = q.filter(ModuleAccess.system_role == r.system_role)
        if r.designation_id:
            q = q.filter(ModuleAccess.designation_id == r.designation_id)
        q.delete()

        rule = ModuleAccess(
            org_id=org_id, module_id=r.module_id,
            system_role=r.system_role, designation_id=r.designation_id,
            can_view=r.can_view, can_create=r.can_create,
            can_edit=r.can_edit, can_approve=r.can_approve, can_delete=r.can_delete,
        )
        db.add(rule)
        created += 1
    db.commit()
    audit_super_admin_action(
        org_id=org_id,
        actor_user_id=str(_auth.get("sub") or ""),
        action=MODULE_ACCESS_WRITE,
        entity_type="MODULE_ACCESS",
        entity_id=None,
        details={"op": "bulk", "rules_written": created},
    )
    return {"updated": created}


@router.delete("/access/{rule_id}")
def delete_access_rule(
    rule_id: str,
    db: Session = Depends(get_db),
    org_id: str = "",
    _auth: dict = Depends(require_super_admin),
):
    """Delete a module access rule."""
    rule = db.query(ModuleAccess).filter(ModuleAccess.id == rule_id, ModuleAccess.org_id == org_id).first()
    if not rule:
        raise HTTPException(404)
    rid = rule.id
    mid = rule.module_id
    db.delete(rule)
    db.commit()
    audit_super_admin_action(
        org_id=org_id,
        actor_user_id=str(_auth.get("sub") or ""),
        action=MODULE_ACCESS_WRITE,
        entity_type="MODULE_ACCESS",
        entity_id=rid,
        details={"op": "delete", "module_id": mid},
    )
    return {"status": "deleted"}


@router.post("/seed-defaults")
def seed_default_access(
    db: Session = Depends(get_db),
    org_id: str = "",
    _auth: dict = Depends(require_super_admin),
):
    """Seed sensible default module access for standard system roles."""
    # Ensure modules exist
    modules = db.query(DashboardModule).all()
    if not modules:
        for m in DEFAULT_MODULES:
            db.add(DashboardModule(key=m["key"], name=m["name"], category=m["category"], description=m["description"]))
        db.commit()
        modules = db.query(DashboardModule).all()

    mod_map = {m.key: m.id for m in modules}

    # Create default rules based on each role's module list
    created = 0
    for role, capabilities in DEFAULT_ROLE_CAPABILITIES.items():
        role_key = role.value
        for mod_key in capabilities.get("modules", []):
            mid = mod_map.get(mod_key)
            if not mid:
                continue
            existing = db.query(ModuleAccess).filter(
                ModuleAccess.org_id == org_id,
                ModuleAccess.module_id == mid,
                ModuleAccess.system_role == role_key,
            ).first()
            if existing:
                continue
            rule = ModuleAccess(
                org_id=org_id, module_id=mid, system_role=role_key,
                can_view=True,
                can_create=False,
                can_approve=False,
                can_edit=False,
            )
            db.add(rule)
            created += 1

    db.commit()
    audit_super_admin_action(
        org_id=org_id,
        actor_user_id=str(_auth.get("sub") or ""),
        action=PERMISSION_SEED,
        entity_type="MODULE_ACCESS",
        entity_id=org_id,
        details={"created_rules": created},
    )
    return {"created": created}


# ============================================================================
# USER PERMISSION PROFILE ENDPOINTS
# ============================================================================

@router.get("/my-modules")
def get_my_modules(db: Session = Depends(get_db), org_id: str = "", user_id: str = ""):
    """
    Get dashboard modules the current user can access.
    Returns array of module objects with granular permissions.
    """
    profile = get_user_permission_profile(user_id, db)
    if not profile:
        raise HTTPException(404, "User not found")

    return profile.get("modules", [])


@router.get("/my-permissions")
def get_my_permissions(db: Session = Depends(get_db), org_id: str = "", user_id: str = ""):
    """
    Get complete permission profile for current user.
    Includes role, designation, hierarchy scope, and all capabilities.
    """
    profile = get_user_permission_profile(user_id, db)
    if not profile:
        raise HTTPException(404, "User not found")

    return profile


@router.get("/user/{target_user_id}/profile")
def get_user_permissions(
    target_user_id: str,
    db: Session = Depends(get_db),
    org_id: str = "",
    _auth: dict = Depends(require_super_admin_or_hr_head),
):
    """Get permission profile for a specific user (admin view)."""
    profile = get_user_permission_profile(target_user_id, db)
    if not profile:
        raise HTTPException(404, "User not found")

    return profile


@router.put("/user/{target_user_id}/permissions")
def update_user_permissions(
    target_user_id: str,
    update: UserPermissionUpdate,
    db: Session = Depends(get_db),
    org_id: str = "",
    _auth: dict = Depends(require_super_admin),
):
    """Update a user's role and permissions (SUPER_ADMIN only)."""
    target_user = db.query(User).filter(User.id == target_user_id).first()
    if not target_user:
        raise HTTPException(404, "User not found")
    if target_user.org_id != org_id:
        raise HTTPException(404, "User not found")

    payload = update.model_dump(exclude_unset=True)
    if update.system_role is not None:
        target_user.system_role = update.system_role
    if update.designation_id is not None:
        target_user.designation_id = update.designation_id
    if update.plant_id is not None:
        target_user.plant_id = update.plant_id
    if update.department_id is not None:
        target_user.department_id = update.department_id
    if update.team_id is not None:
        target_user.team_id = update.team_id

    db.add(target_user)
    db.commit()

    # Reinitialize permission profile
    initialize_user_permissions(target_user, db)

    audit_super_admin_action(
        org_id=org_id,
        actor_user_id=str(_auth.get("sub") or ""),
        action=ROLE_ASSIGN,
        entity_type="USER",
        entity_id=target_user_id,
        details={"fields": list(payload.keys()), "values": payload},
    )

    return get_user_permission_profile(target_user_id, db)


# ============================================================================
# USER INVITATION ENDPOINTS
# ============================================================================

@router.post("/invitations")
def invite_user(
    invitation: UserInvitationCreate,
    db: Session = Depends(get_db),
    org_id: str = "",
    _auth: dict = Depends(require_super_admin_or_hr_head),
):
    """
    Invite a user with pre-assigned role and permissions.
    Sends invitation with temporary token.
    """
    user_id = str(_auth.get("sub") or "")

    # Check if email already exists
    existing = db.query(User).filter(User.email == invitation.invited_email).first()
    if existing:
        raise HTTPException(400, "Email already registered")

    # Check for existing pending invitation
    pending = db.query(UserInvitation).filter(
        UserInvitation.invited_email == invitation.invited_email,
        UserInvitation.status == "PENDING"
    ).first()
    if pending:
        raise HTTPException(400, "Invitation already pending for this email")

    # Create invitation with token
    token = secrets.token_urlsafe(32)
    user_inv = UserInvitation(
        org_id=org_id,
        invited_email=invitation.invited_email,
        invited_by_id=user_id,
        system_role=invitation.system_role,
        designation_id=invitation.designation_id,
        plant_id=invitation.plant_id,
        department_id=invitation.department_id,
        team_id=invitation.team_id,
        invitation_token=token,
        status="PENDING",
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    db.add(user_inv)
    db.commit()
    db.refresh(user_inv)

    # TODO: Send email with invitation link containing token
    # Email should include: invitation_url + token

    return {
        "id": user_inv.id,
        "email": user_inv.invited_email,
        "status": "PENDING",
        "token": token,  # In production, only send via secure email link
        "expires_at": user_inv.expires_at.isoformat()
    }


@router.post("/invitations/accept")
def accept_invitation(accept: UserInvitationAccept, db: Session = Depends(get_db)):
    """Accept invitation and create user account with assigned permissions."""
    # Find invitation by token
    invitation = db.query(UserInvitation).filter(
        UserInvitation.invitation_token == accept.invitation_token,
        UserInvitation.status == "PENDING"
    ).first()

    if not invitation:
        raise HTTPException(404, "Invalid or expired invitation")

    if invitation.expires_at < datetime.utcnow():
        raise HTTPException(400, "Invitation has expired")

    # Check email doesn't already exist
    existing = db.query(User).filter(User.email == invitation.invited_email).first()
    if existing:
        raise HTTPException(400, "Email already registered")

    # Create user with invitation details
    org = db.query(Organization).filter(Organization.id == invitation.org_id).first()
    if not org:
        raise HTTPException(404, "Organization not found")

    import random
    AVATAR_COLORS = ["#6366f1","#8b5cf6","#ec4899","#f43f5e","#f97316","#eab308","#22c55e","#14b8a6","#0ea5e9","#3b82f6"]

    user = User(
        org_id=invitation.org_id,
        email=invitation.invited_email,
        password_hash=get_password_hash(accept.password),
        name=accept.name,
        system_role=invitation.system_role,
        designation_id=invitation.designation_id,
        plant_id=invitation.plant_id,
        department_id=invitation.department_id,
        team_id=invitation.team_id,
        avatar_color=random.choice(AVATAR_COLORS),
    )
    db.add(user)
    db.flush()

    # Mark invitation as accepted
    invitation.status = "ACCEPTED"
    invitation.accepted_at = datetime.utcnow()
    db.add(invitation)
    db.commit()
    db.refresh(user)

    # Initialize permissions
    initialize_user_permissions(user, db)

    token = create_access_token(
        {"sub": user.id, "org_id": user.org_id, "role": _canonical_role_for_token(user.system_role)}
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "system_role": user.system_role,
            "org_id": user.org_id,
            "org_name": org.name,
            "permissions": get_user_permission_profile(user.id, db)
        }
    }


@router.get("/invitations")
def list_invitations(
    db: Session = Depends(get_db),
    org_id: str = "",
    _auth: dict = Depends(require_super_admin_or_hr_head),
):
    """List all pending and accepted invitations for an org (admin view)."""
    invitations = db.query(UserInvitation).filter(UserInvitation.org_id == org_id).all()
    return [
        {
            "id": inv.id,
            "email": inv.invited_email,
            "system_role": inv.system_role,
            "status": inv.status,
            "invited_at": inv.created_at.isoformat(),
            "accepted_at": inv.accepted_at.isoformat() if inv.accepted_at else None,
            "expires_at": inv.expires_at.isoformat()
        }
        for inv in invitations
    ]


@router.delete("/invitations/{invitation_id}")
def revoke_invitation(
    invitation_id: str,
    db: Session = Depends(get_db),
    org_id: str = "",
    _auth: dict = Depends(require_super_admin_or_hr_head),
):
    """Revoke a pending invitation."""
    invitation = db.query(UserInvitation).filter(
        UserInvitation.id == invitation_id,
        UserInvitation.org_id == org_id,
    ).first()
    if not invitation:
        raise HTTPException(404, "Invitation not found")

    invitation.status = "REVOKED"
    db.add(invitation)
    db.commit()
    return {"status": "revoked"}
