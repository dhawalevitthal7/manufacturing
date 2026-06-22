"""
Permissions Service - Centralized permission and visibility logic for enterprise RBAC.

This service implements the visibility matrix:
role/designation + permissions + hierarchy scope + module visibility = workspace experience

NOT role = page (simplistic)
BUT comprehensive enterprise RBAC with organization-specific configuration.
"""

import json
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from server.models import (
    User,
    UserPermissionProfile,
    ModuleAccess,
    DashboardModule,
    OrgNode,
)
from server.roles import SystemRole, normalize_role


# ===== DEFAULT PERMISSION MATRIX =====
# Keys are SystemRole enum members; organizations can override in ModuleAccess table.

_SUPER_ADMIN_MODULES: tuple[str, ...] = (
    "ORG_OKRS",
    "PLANT_OKRS",
    "DEPT_OKRS",
    "TEAM_OKRS",
    "EMPLOYEE_OKRS",
    "PROGRESS_TRACKING",
    "ALIGNMENT_DASHBOARD",
    "REVIEW_DASHBOARD",
    "REVIEW_ANALYTICS",
    "TEAM_MANAGEMENT",
    "DEPT_VISIBILITY",
    "PLANT_VISIBILITY",
    "ORG_VISIBILITY",
    "EMPLOYEE_DIRECTORY",
    "REPORTING_STRUCTURE",
    "APPROVAL_QUEUE",
    "ESCALATION_MGMT",
    "AI_INSIGHTS",
    "AUDIT_LOGS",
)

_VP_OPS_STYLE_MODULES: tuple[str, ...] = (
    "PLANT_OKRS",
    "DEPT_OKRS",
    "TEAM_OKRS",
    "PROGRESS_TRACKING",
    "ALIGNMENT_DASHBOARD",
    "REVIEW_DASHBOARD",
    "REVIEW_ANALYTICS",
    "APPROVAL_QUEUE",
    "ESCALATION_MGMT",
    "AI_INSIGHTS",
)


def _capabilities_for_role(role: SystemRole) -> dict:
    return DEFAULT_ROLE_CAPABILITIES.get(role, DEFAULT_ROLE_CAPABILITIES[SystemRole.EMPLOYEE])


def _region_scope_id_for_user(user: User, db: Session) -> Optional[str]:
    """Resolve REGION org node id for REGIONAL_HEAD (org_node_id or region head assignment)."""
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


DEFAULT_ROLE_CAPABILITIES: dict[SystemRole, dict] = {
    SystemRole.SUPER_ADMIN: {
        "scope_type": "ORGANIZATION",
        "can_view_all_plants": True,
        "can_view_all_departments": True,
        "can_view_all_teams": True,
        "can_view_all_employees": True,
        "can_create_plants": True,
        "can_create_departments": True,
        "can_create_teams": True,
        "can_create_designations": True,
        "can_configure_permissions": True,
        "can_invite_employees": True,
        "can_assign_roles": True,
        "can_access_analytics": True,
        "can_access_audit_logs": True,
        "modules": list(_SUPER_ADMIN_MODULES),
    },
    SystemRole.CEO: {
        "scope_type": "ORGANIZATION",
        "can_view_all_plants": True,
        "can_view_all_departments": True,
        "can_view_all_teams": True,
        "can_view_all_employees": True,
        "can_create_plants": False,
        "can_create_departments": False,
        "can_create_teams": False,
        "can_create_designations": False,
        "can_configure_permissions": False,
        "can_invite_employees": False,
        "can_assign_roles": False,
        "can_access_analytics": True,
        "can_access_audit_logs": True,
        "modules": [
            "ORG_OKRS",
            "PLANT_OKRS",
            "DEPT_OKRS",
            "TEAM_OKRS",
            "ALIGNMENT_DASHBOARD",
            "REVIEW_ANALYTICS",
            "AI_INSIGHTS",
        ],
    },
    SystemRole.VP_OPERATIONS: {
        "scope_type": "ORGANIZATION",
        "can_view_all_plants": True,
        "can_view_all_departments": True,
        "can_view_all_teams": False,
        "can_view_all_employees": False,
        "can_create_plants": False,
        "can_create_departments": False,
        "can_create_teams": False,
        "can_create_designations": False,
        "can_configure_permissions": False,
        "can_invite_employees": False,
        "can_assign_roles": False,
        "can_access_analytics": True,
        "can_access_audit_logs": False,
        "modules": list(_VP_OPS_STYLE_MODULES),
    },
    SystemRole.COO: {
        "scope_type": "ORGANIZATION",
        "can_view_all_plants": True,
        "can_view_all_departments": True,
        "can_view_all_teams": False,
        "can_view_all_employees": False,
        "can_create_plants": False,
        "can_create_departments": False,
        "can_create_teams": False,
        "can_create_designations": False,
        "can_configure_permissions": False,
        "can_invite_employees": False,
        "can_assign_roles": False,
        "can_access_analytics": True,
        "can_access_audit_logs": False,
        "modules": list(_VP_OPS_STYLE_MODULES),
    },
    SystemRole.CRO: {
        "scope_type": "ORGANIZATION",
        "can_view_all_plants": True,
        "can_view_all_departments": True,
        "can_view_all_teams": False,
        "can_view_all_employees": False,
        "can_create_plants": False,
        "can_create_departments": False,
        "can_create_teams": False,
        "can_create_designations": False,
        "can_configure_permissions": False,
        "can_invite_employees": False,
        "can_assign_roles": False,
        "can_access_analytics": True,
        "can_access_audit_logs": False,
        "modules": list(_VP_OPS_STYLE_MODULES),
    },
    SystemRole.REGIONAL_HEAD: {
        "scope_type": "REGION",
        "can_view_all_plants": True,
        "can_view_all_departments": True,
        "can_view_all_teams": True,
        "can_view_all_employees": True,
        "can_create_plants": False,
        "can_create_departments": False,
        "can_create_teams": False,
        "can_create_designations": False,
        "can_configure_permissions": False,
        "can_invite_employees": False,
        "can_assign_roles": False,
        "can_access_analytics": True,
        "can_access_audit_logs": False,
        "modules": list(_VP_OPS_STYLE_MODULES),
    },
    SystemRole.CFO: {
        "scope_type": "ORGANIZATION",
        "can_view_all_plants": True,
        "can_view_all_departments": True,
        "can_view_all_teams": True,
        "can_view_all_employees": True,
        "can_create_plants": False,
        "can_create_departments": False,
        "can_create_teams": False,
        "can_create_designations": False,
        "can_configure_permissions": False,
        "can_invite_employees": False,
        "can_assign_roles": False,
        "can_access_analytics": True,
        "can_access_audit_logs": True,
        "modules": [
            "ORG_OKRS",
            "ORG_VISIBILITY",
            "PLANT_OKRS",
            "DEPT_OKRS",
            "ALIGNMENT_DASHBOARD",
            "REVIEW_ANALYTICS",
            "APPROVAL_QUEUE",
            "AI_INSIGHTS",
        ],
    },
    SystemRole.CMO: {
        "scope_type": "ORGANIZATION",
        "can_view_all_plants": True,
        "can_view_all_departments": True,
        "can_view_all_teams": True,
        "can_view_all_employees": True,
        "can_create_plants": False,
        "can_create_departments": False,
        "can_create_teams": False,
        "can_create_designations": False,
        "can_configure_permissions": False,
        "can_invite_employees": False,
        "can_assign_roles": False,
        "can_access_analytics": True,
        "can_access_audit_logs": False,
        "modules": [
            "ORG_OKRS",
            "ORG_VISIBILITY",
            "DEPT_OKRS",
            "TEAM_OKRS",
            "ALIGNMENT_DASHBOARD",
            "REVIEW_DASHBOARD",
            "REVIEW_ANALYTICS",
            "AI_INSIGHTS",
        ],
    },
    SystemRole.CTO: {
        "scope_type": "ORGANIZATION",
        "can_view_all_plants": True,
        "can_view_all_departments": True,
        "can_view_all_teams": True,
        "can_view_all_employees": True,
        "can_create_plants": False,
        "can_create_departments": False,
        "can_create_teams": False,
        "can_create_designations": False,
        "can_configure_permissions": False,
        "can_invite_employees": False,
        "can_assign_roles": False,
        "can_access_analytics": True,
        "can_access_audit_logs": False,
        "modules": [
            "ORG_OKRS",
            "PLANT_OKRS",
            "DEPT_OKRS",
            "TEAM_OKRS",
            "EMPLOYEE_OKRS",
            "PROGRESS_TRACKING",
            "ALIGNMENT_DASHBOARD",
            "APPROVAL_QUEUE",
            "AI_INSIGHTS",
        ],
    },
    SystemRole.CPO: {
        "scope_type": "ORGANIZATION",
        "can_view_all_plants": True,
        "can_view_all_departments": True,
        "can_view_all_teams": True,
        "can_view_all_employees": True,
        "can_create_plants": False,
        "can_create_departments": False,
        "can_create_teams": False,
        "can_create_designations": False,
        "can_configure_permissions": False,
        "can_invite_employees": False,
        "can_assign_roles": False,
        "can_access_analytics": True,
        "can_access_audit_logs": False,
        "modules": [
            "ORG_OKRS",
            "ORG_VISIBILITY",
            "PLANT_OKRS",
            "DEPT_OKRS",
            "ALIGNMENT_DASHBOARD",
            "REVIEW_ANALYTICS",
            "APPROVAL_QUEUE",
            "AI_INSIGHTS",
        ],
    },
    SystemRole.CSO: {
        "scope_type": "ORGANIZATION",
        "can_view_all_plants": True,
        "can_view_all_departments": True,
        "can_view_all_teams": True,
        "can_view_all_employees": True,
        "can_create_plants": False,
        "can_create_departments": False,
        "can_create_teams": False,
        "can_create_designations": False,
        "can_configure_permissions": False,
        "can_invite_employees": False,
        "can_assign_roles": False,
        "can_access_analytics": True,
        "can_access_audit_logs": False,
        "modules": [
            "ORG_OKRS",
            "ORG_VISIBILITY",
            "PLANT_OKRS",
            "DEPT_OKRS",
            "ALIGNMENT_DASHBOARD",
            "REVIEW_ANALYTICS",
            "APPROVAL_QUEUE",
            "AI_INSIGHTS",
        ],
    },
    SystemRole.CHRO: {
        "scope_type": "ORGANIZATION",
        "can_view_all_plants": True,
        "can_view_all_departments": True,
        "can_view_all_teams": True,
        "can_view_all_employees": True,
        "can_create_plants": False,
        "can_create_departments": False,
        "can_create_teams": False,
        "can_create_designations": False,
        "can_configure_permissions": False,
        "can_invite_employees": False,
        "can_assign_roles": False,
        "can_access_analytics": True,
        "can_access_audit_logs": True,
        "modules": [
            "ORG_OKRS",
            "ORG_VISIBILITY",
            "PLANT_OKRS",
            "DEPT_OKRS",
            "ALIGNMENT_DASHBOARD",
            "REVIEW_ANALYTICS",
            "APPROVAL_QUEUE",
            "AI_INSIGHTS",
        ],
    },
    SystemRole.FUNCTIONAL_SUB_HEAD: {
        "scope_type": "ORGANIZATION",
        "can_view_all_plants": True,
        "can_view_all_departments": True,
        "can_view_all_teams": False,
        "can_view_all_employees": False,
        "can_create_plants": False,
        "can_create_departments": False,
        "can_create_teams": False,
        "can_create_designations": False,
        "can_configure_permissions": False,
        "can_invite_employees": False,
        "can_assign_roles": False,
        "can_access_analytics": True,
        "can_access_audit_logs": False,
        "modules": [
            "DEPT_OKRS",
            "TEAM_OKRS",
            "ALIGNMENT_DASHBOARD",
            "APPROVAL_QUEUE",
            "AI_INSIGHTS",
        ],
    },
    SystemRole.AREA_SALES_MANAGER: {
        "scope_type": "DEPARTMENT",
        "can_view_all_plants": False,
        "can_view_all_departments": False,
        "can_view_all_teams": True,
        "can_view_all_employees": False,
        "can_create_plants": False,
        "can_create_departments": False,
        "can_create_teams": False,
        "can_create_designations": False,
        "can_configure_permissions": False,
        "can_invite_employees": False,
        "can_assign_roles": False,
        "can_access_analytics": True,
        "can_access_audit_logs": False,
        "modules": [
            "TEAM_OKRS",
            "EMPLOYEE_OKRS",
            "PROGRESS_TRACKING",
            "ALIGNMENT_DASHBOARD",
            "REVIEW_DASHBOARD",
            "APPROVAL_QUEUE",
        ],
    },
    SystemRole.PLANT_HEAD: {
        "scope_type": "PLANT",
        "can_view_all_plants": False,
        "can_view_all_departments": False,
        "can_view_all_teams": False,
        "can_view_all_employees": False,
        "can_create_plants": False,
        "can_create_departments": False,
        "can_create_teams": False,
        "can_create_designations": False,
        "can_configure_permissions": False,
        "can_invite_employees": False,
        "can_assign_roles": False,
        "can_access_analytics": True,
        "can_access_audit_logs": False,
        "modules": [
            "PLANT_OKRS",
            "DEPT_OKRS",
            "TEAM_OKRS",
            "EMPLOYEE_OKRS",
            "PROGRESS_TRACKING",
            "ALIGNMENT_DASHBOARD",
            "REVIEW_DASHBOARD",
            "REVIEW_ANALYTICS",
            "TEAM_MANAGEMENT",
            "DEPT_VISIBILITY",
            "APPROVAL_QUEUE",
            "ESCALATION_MGMT",
            "AI_INSIGHTS",
        ],
    },
    SystemRole.DEPT_HEAD: {
        "scope_type": "DEPARTMENT",
        "can_view_all_plants": False,
        "can_view_all_departments": False,
        "can_view_all_teams": False,
        "can_view_all_employees": False,
        "can_create_plants": False,
        "can_create_departments": False,
        "can_create_teams": False,
        "can_create_designations": False,
        "can_configure_permissions": False,
        "can_invite_employees": False,
        "can_assign_roles": False,
        "can_access_analytics": True,
        "can_access_audit_logs": False,
        "modules": [
            "DEPT_OKRS",
            "TEAM_OKRS",
            "EMPLOYEE_OKRS",
            "PROGRESS_TRACKING",
            "ALIGNMENT_DASHBOARD",
            "REVIEW_DASHBOARD",
            "REVIEW_ANALYTICS",
            "TEAM_MANAGEMENT",
            "APPROVAL_QUEUE",
            "ESCALATION_MGMT",
            "AI_INSIGHTS",
        ],
    },
    SystemRole.MANAGER: {
        "scope_type": "DEPARTMENT",
        "can_view_all_plants": False,
        "can_view_all_departments": False,
        "can_view_all_teams": False,
        "can_view_all_employees": False,
        "can_create_plants": False,
        "can_create_departments": False,
        "can_create_teams": False,
        "can_create_designations": False,
        "can_configure_permissions": False,
        "can_invite_employees": False,
        "can_assign_roles": False,
        "can_access_analytics": True,
        "can_access_audit_logs": False,
        "modules": [
            "TEAM_OKRS",
            "EMPLOYEE_OKRS",
            "PROGRESS_TRACKING",
            "ALIGNMENT_DASHBOARD",
            "REVIEW_DASHBOARD",
            "TEAM_MANAGEMENT",
            "APPROVAL_QUEUE",
            "ESCALATION_MGMT",
        ],
    },
    SystemRole.TEAM_LEAD: {
        "scope_type": "TEAM",
        "can_view_all_plants": False,
        "can_view_all_departments": False,
        "can_view_all_teams": False,
        "can_view_all_employees": False,
        "can_create_plants": False,
        "can_create_departments": False,
        "can_create_teams": False,
        "can_create_designations": False,
        "can_configure_permissions": False,
        "can_invite_employees": False,
        "can_assign_roles": False,
        "can_access_analytics": False,
        "can_access_audit_logs": False,
        "modules": [
            "TEAM_OKRS",
            "EMPLOYEE_OKRS",
            "PROGRESS_TRACKING",
            "ALIGNMENT_DASHBOARD",
            "APPROVAL_QUEUE",
            "ESCALATION_MGMT",
        ],
    },
    SystemRole.SUPERVISOR: {
        "scope_type": "TEAM",
        "can_view_all_plants": False,
        "can_view_all_departments": False,
        "can_view_all_teams": False,
        "can_view_all_employees": False,
        "can_create_plants": False,
        "can_create_departments": False,
        "can_create_teams": False,
        "can_create_designations": False,
        "can_configure_permissions": False,
        "can_invite_employees": False,
        "can_assign_roles": False,
        "can_access_analytics": False,
        "can_access_audit_logs": False,
        "modules": ["EMPLOYEE_OKRS", "PROGRESS_TRACKING", "APPROVAL_QUEUE"],
    },
    SystemRole.EMPLOYEE: {
        "scope_type": "INDIVIDUAL",
        "can_view_all_plants": False,
        "can_view_all_departments": False,
        "can_view_all_teams": False,
        "can_view_all_employees": False,
        "can_create_plants": False,
        "can_create_departments": False,
        "can_create_teams": False,
        "can_create_designations": False,
        "can_configure_permissions": False,
        "can_invite_employees": False,
        "can_assign_roles": False,
        "can_access_analytics": False,
        "can_access_audit_logs": False,
        "modules": [
            "EMPLOYEE_OKRS",
            "PROGRESS_TRACKING",
            "REVIEW_DASHBOARD",
            "AI_OKR_ASSIST",
        ],
    },
    SystemRole.HR_HEAD: {
        "scope_type": "ORGANIZATION",
        "can_view_all_plants": True,
        "can_view_all_departments": True,
        "can_view_all_teams": True,
        "can_view_all_employees": True,
        "can_create_plants": False,
        "can_create_departments": False,
        "can_create_teams": False,
        "can_create_designations": False,
        "can_configure_permissions": False,
        "can_invite_employees": True,
        "can_assign_roles": False,
        "can_access_analytics": True,
        "can_access_audit_logs": True,
        "modules": [
            "REVIEW_DASHBOARD",
            "REVIEW_ANALYTICS",
            "EMPLOYEE_DIRECTORY",
            "REPORTING_STRUCTURE",
            "APPROVAL_QUEUE",
            "AI_INSIGHTS",
        ],
    },
}


def _profile_capability_signature(profile: UserPermissionProfile) -> tuple:
    """Stable tuple for idempotent backfill: did this profile already match defaults?"""
    raw_mods = profile.module_permissions or ""
    try:
        arr = json.loads(raw_mods) if raw_mods else []
        mods_norm = json.dumps(sorted(arr, key=lambda x: str(x.get("module_key", ""))))
    except json.JSONDecodeError:
        mods_norm = raw_mods
    return (
        profile.system_role,
        profile.scope_type,
        profile.scoped_plant_id,
        profile.scoped_department_id,
        profile.scoped_team_id,
        getattr(profile, "scoped_region_id", None),
        profile.can_view_all_plants,
        profile.can_view_all_departments,
        profile.can_view_all_teams,
        profile.can_view_all_employees,
        profile.can_create_plants,
        profile.can_create_departments,
        profile.can_create_teams,
        profile.can_create_designations,
        profile.can_configure_permissions,
        profile.can_invite_employees,
        profile.can_assign_roles,
        profile.can_access_analytics,
        profile.can_access_audit_logs,
        mods_norm,
    )


def initialize_user_permissions(
    user: User, db: Session, *, commit: bool = True
) -> UserPermissionProfile:
    """
    Initialize or update a user's permission profile based on their role.
    Called when:
    1. User registers as SUPER_ADMIN
    2. User is invited/created with a specific role
    3. User's role is changed
    """
    role = normalize_role(user.system_role)
    capabilities = _capabilities_for_role(role)

    # Build module permissions by querying ModuleAccess rules
    module_permissions = _get_module_permissions(user, db)

    # Find or create permission profile
    profile = db.query(UserPermissionProfile).filter(
        UserPermissionProfile.user_id == user.id
    ).first()

    if not profile:
        profile = UserPermissionProfile(
            org_id=user.org_id,
            user_id=user.id,
        )

    # Update with current values
    profile.system_role = user.system_role
    profile.designation_id = user.designation_id
    profile.scope_type = capabilities["scope_type"]

    # Set hierarchy scope (legacy plant/dept/team columns)
    profile.scoped_plant_id = user.plant_id
    profile.scoped_department_id = user.department_id
    profile.scoped_team_id = user.team_id

    if capabilities["scope_type"] == "REGION":
        profile.scoped_region_id = _region_scope_id_for_user(user, db)
    else:
        profile.scoped_region_id = None

    # Set capabilities
    profile.can_view_all_plants = capabilities["can_view_all_plants"]
    profile.can_view_all_departments = capabilities["can_view_all_departments"]
    profile.can_view_all_teams = capabilities["can_view_all_teams"]
    profile.can_view_all_employees = capabilities["can_view_all_employees"]
    profile.can_create_plants = capabilities["can_create_plants"]
    profile.can_create_departments = capabilities["can_create_departments"]
    profile.can_create_teams = capabilities["can_create_teams"]
    profile.can_create_designations = capabilities["can_create_designations"]
    profile.can_configure_permissions = capabilities["can_configure_permissions"]
    profile.can_invite_employees = capabilities["can_invite_employees"]
    profile.can_assign_roles = capabilities["can_assign_roles"]
    profile.can_access_analytics = capabilities["can_access_analytics"]
    profile.can_access_audit_logs = capabilities["can_access_audit_logs"]

    # Set module permissions as JSON
    profile.module_permissions = json.dumps(module_permissions)

    db.add(profile)
    if commit:
        db.commit()
        db.refresh(profile)
    else:
        db.flush()
    return profile


def get_user_permission_profile(user_id: str, db: Session) -> Optional[Dict]:
    """
    Get complete permission profile for a user.
    Returns all permissions, capabilities, and module access.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None

    profile = db.query(UserPermissionProfile).filter(
        UserPermissionProfile.user_id == user_id
    ).first()

    if not profile:
        # Initialize if not exists
        profile = initialize_user_permissions(user, db)

    modules = []
    if profile.module_permissions:
        try:
            modules = json.loads(profile.module_permissions)
        except json.JSONDecodeError:
            modules = []

    return {
        "user_id": user.id,
        "system_role": profile.system_role,
        "designation_id": profile.designation_id,
        "scope_type": profile.scope_type,
        "scoped_plant_id": profile.scoped_plant_id,
        "scoped_department_id": profile.scoped_department_id,
        "scoped_team_id": profile.scoped_team_id,
        "scoped_region_id": profile.scoped_region_id,
        "can_view_all_plants": profile.can_view_all_plants,
        "can_view_all_departments": profile.can_view_all_departments,
        "can_view_all_teams": profile.can_view_all_teams,
        "can_view_all_employees": profile.can_view_all_employees,
        "can_create_plants": profile.can_create_plants,
        "can_create_departments": profile.can_create_departments,
        "can_create_teams": profile.can_create_teams,
        "can_create_designations": profile.can_create_designations,
        "can_configure_permissions": profile.can_configure_permissions,
        "can_invite_employees": profile.can_invite_employees,
        "can_assign_roles": profile.can_assign_roles,
        "can_access_analytics": profile.can_access_analytics,
        "can_access_audit_logs": profile.can_access_audit_logs,
        "modules": modules,
    }


def _get_module_permissions(user: User, db: Session) -> List[Dict]:
    """
    Get module permissions for a user based on their role and designation.
    Queries ModuleAccess table for configured rules.
    For SUPER_ADMIN, grants full access to all modules.
    """
    if user.system_role == "SUPER_ADMIN":
        modules = db.query(DashboardModule).all()
        return [
            {
                "module_key": m.key,
                "module_name": m.name,
                "category": m.category,
                "can_view": True,
                "can_create": True,
                "can_edit": True,
                "can_approve": True,
                "can_delete": True,
            }
            for m in modules
        ]

    # Query ModuleAccess rules for this role and designation
    rules = (
        db.query(ModuleAccess)
        .filter(ModuleAccess.org_id == user.org_id)
        .filter(
            (ModuleAccess.system_role == user.system_role)
            | (ModuleAccess.designation_id == user.designation_id)
        )
        .all()
    )

    # Merge permissions (OR logic)
    module_perms = {}
    for rule in rules:
        mod = db.query(DashboardModule).filter(DashboardModule.id == rule.module_id).first()
        if not mod:
            continue
        if mod.key not in module_perms:
            module_perms[mod.key] = {
                "module_key": mod.key,
                "module_name": mod.name,
                "category": mod.category,
                "can_view": False,
                "can_create": False,
                "can_edit": False,
                "can_approve": False,
                "can_delete": False,
            }
        p = module_perms[mod.key]
        p["can_view"] = p["can_view"] or rule.can_view
        p["can_create"] = p["can_create"] or rule.can_create
        p["can_edit"] = p["can_edit"] or rule.can_edit
        p["can_approve"] = p["can_approve"] or rule.can_approve
        p["can_delete"] = p["can_delete"] or rule.can_delete

    # Add default module access from DEFAULT_ROLE_CAPABILITIES
    role_enum = normalize_role(user.system_role)
    role_default_modules = _capabilities_for_role(role_enum).get("modules", [])
    for mod_key in role_default_modules:
        if mod_key not in module_perms:
            mod = db.query(DashboardModule).filter(DashboardModule.key == mod_key).first()
            if mod:
                module_perms[mod_key] = {
                    "module_key": mod.key,
                    "module_name": mod.name,
                    "category": mod.category,
                    "can_view": True,
                    "can_create": False,
                    "can_edit": False,
                    "can_approve": False,
                    "can_delete": False,
                }

    return list(module_perms.values())


def can_user_access_module(user_id: str, module_key: str, action: str, db: Session) -> bool:
    """
    Check if user can perform an action on a module.
    action: view, create, edit, approve, delete
    """
    profile = get_user_permission_profile(user_id, db)
    if not profile:
        return False

    for mod in profile.get("modules", []):
        if mod["module_key"] == module_key:
            action_key = f"can_{action}"
            return mod.get(action_key, False)

    return False
