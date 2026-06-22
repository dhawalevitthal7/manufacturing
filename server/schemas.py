from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any


# ===== AUTH =====
class RegisterRequest(BaseModel):
    company_name: str
    domain: Optional[str] = None
    org_size: Optional[str] = None
    admin_name: str
    admin_email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


# ===== ORGANIZATION =====
class PlantCreate(BaseModel):
    name: str
    location: Optional[str] = None
    code: Optional[str] = None
    region_id: Optional[str] = None


class OrgTreeNamedNodeCreate(BaseModel):
    """Body for POST /api/org-tree/regions and POST /api/org-tree/corporate-functions."""

    name: str
    code: Optional[str] = None
    head_user_id: Optional[str] = None

class DepartmentCreate(BaseModel):
    plant_id: str
    name: str
    dept_type: Optional[str] = None

class TeamCreate(BaseModel):
    department_id: str
    name: str
    lead_id: Optional[str] = None
    # Roster on create; users must belong to the team's plant (plant_id or dept in that plant).
    member_user_ids: Optional[List[str]] = None


class TeamUpdate(BaseModel):
    """Body for PUT /api/teams/{team_id} (SUPER_ADMIN)."""

    name: Optional[str] = None
    department_id: Optional[str] = None
    lead_id: Optional[str] = None


class ShiftCreate(BaseModel):
    plant_id: str
    name: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    supervisor_id: Optional[str] = None

class DesignationCreate(BaseModel):
    name: str
    level: int = 0
    category: Optional[str] = None


# ===== ORGANIZATION TREE (OrgNode) =====
class OrgNodeCreate(BaseModel):
    """Create a new org tree node."""
    node_type: str  # ORGANIZATION, REGION, CORPORATE_FUNCTION, PLANT, DEPARTMENT, TEAM, etc.
    name: str
    parent_id: Optional[str] = None  # If None, must be creating an org root
    code: Optional[str] = None
    head_user_id: Optional[str] = None
    node_metadata: Optional[Dict[str, Any]] = None

class OrgNodeUpdate(BaseModel):
    """Update an existing org tree node."""
    name: Optional[str] = None
    code: Optional[str] = None
    head_user_id: Optional[str] = None
    parent_id: Optional[str] = None  # Move node to a new parent
    node_metadata: Optional[Dict[str, Any]] = None
    functional_parent_id: Optional[str] = None  # dotted-line parent (SUPER_ADMIN); omit key to leave unchanged

class OrgNodeResponse(BaseModel):
    """Response representation of an org tree node with children."""
    id: str
    org_id: str
    parent_id: Optional[str]
    functional_parent_id: Optional[str] = None
    node_type: str
    name: str
    code: Optional[str]
    head_user_id: Optional[str]
    path: str
    depth: int
    node_metadata: Optional[Dict[str, Any]]
    is_active: bool
    children: Optional[List["OrgNodeResponse"]] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


# ===== EMPLOYEES =====
class EmployeeCreate(BaseModel):
    """Direct employee creation — no invitation flow. Admin sets password directly."""
    name: str
    email: str
    password: str = "Welcome@123"
    employee_id: Optional[str] = None
    system_role: str = "EMPLOYEE"
    plant_id: Optional[str] = None
    department_id: Optional[str] = None
    team_id: Optional[str] = None
    designation_id: Optional[str] = None
    shift_id: Optional[str] = None

class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    system_role: Optional[str] = None
    plant_id: Optional[str] = None
    department_id: Optional[str] = None
    team_id: Optional[str] = None
    designation_id: Optional[str] = None
    shift_id: Optional[str] = None
    is_active: Optional[bool] = None

class EmployeeBulkCreate(BaseModel):
    """Bulk creation of employees."""
    employees: List[EmployeeCreate]


# ===== REPORTING RELATIONSHIPS =====
class ReportingRelCreate(BaseModel):
    employee_id: str
    manager_id: str
    relationship_type: str  # DIRECT, DOTTED_LINE, REVIEWER, APPROVER

class ReportingRelBulkCreate(BaseModel):
    relationships: List[ReportingRelCreate]


# ===== DASHBOARD MODULE ACCESS =====
class ModuleAccessCreate(BaseModel):
    module_id: str
    system_role: Optional[str] = None
    designation_id: Optional[str] = None
    can_view: bool = False
    can_create: bool = False
    can_edit: bool = False
    can_approve: bool = False
    can_delete: bool = False

class ModuleAccessBulkUpdate(BaseModel):
    access_rules: List[ModuleAccessCreate]


# ===== USER INVITATIONS & PERMISSIONS =====
class UserInvitationCreate(BaseModel):
    """Invite a user with pre-assigned role and permissions."""
    invited_email: str
    system_role: str
    designation_id: Optional[str] = None
    plant_id: Optional[str] = None
    department_id: Optional[str] = None
    team_id: Optional[str] = None

class UserInvitationAccept(BaseModel):
    """Accept an invitation and set password."""
    invitation_token: str
    name: str
    password: str

class UserPermissionUpdate(BaseModel):
    """Update a user's permissions and role assignment."""
    system_role: Optional[str] = None
    designation_id: Optional[str] = None
    plant_id: Optional[str] = None
    department_id: Optional[str] = None
    team_id: Optional[str] = None

class ModulePermission(BaseModel):
    module_key: str
    module_name: str
    category: str
    can_view: bool = False
    can_create: bool = False
    can_edit: bool = False
    can_approve: bool = False
    can_delete: bool = False

class UserPermissionProfile(BaseModel):
    """Complete permission profile for a user."""
    user_id: str
    system_role: str
    scope_type: str
    scoped_plant_id: Optional[str] = None
    scoped_department_id: Optional[str] = None
    scoped_team_id: Optional[str] = None
    scoped_region_id: Optional[str] = None
    can_view_all_plants: bool
    can_view_all_departments: bool
    can_view_all_teams: bool
    can_view_all_employees: bool
    can_create_plants: bool
    can_create_departments: bool
    can_create_teams: bool
    can_create_designations: bool
    can_configure_permissions: bool
    can_invite_employees: bool
    can_assign_roles: bool
    can_access_analytics: bool
    can_access_audit_logs: bool
    modules: List[ModulePermission]


# ===== OKRs =====
class ObjectiveCreate(BaseModel):
    title: str
    description: Optional[str] = None
    level: str = "INDIVIDUAL"
    parent_id: Optional[str] = None
    cycle_id: Optional[str] = None
    owner_id: Optional[str] = None
    region_id: Optional[str] = None
    plant_id: Optional[str] = None
    department_id: Optional[str] = None
    team_id: Optional[str] = None
    function_area: Optional[str] = None
    function_node_id: Optional[str] = None

class ObjectiveAssignCreate(BaseModel):
    """
    Manager assigns an OKR to an employee.
    Similar to creating an INDIVIDUAL OKR but explicitly assigns it to another user.
    """
    title: str
    description: Optional[str] = None
    employee_user_id: str  # Who to assign this OKR to
    parent_id: Optional[str] = None
    cycle_id: Optional[str] = None
    plant_id: Optional[str] = None
    department_id: Optional[str] = None
    team_id: Optional[str] = None
    key_results: List['KeyResultCreate'] = []

class ObjectiveUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    level: Optional[str] = None
    parent_id: Optional[str] = None
    status: Optional[str] = None
    function_area: Optional[str] = None
    function_node_id: Optional[str] = None


class ObjectiveFunctionalParentPatch(BaseModel):
    """PATCH /api/okrs/{obj_id} — SUPER_ADMIN only; exactly one field."""

    model_config = ConfigDict(extra="forbid")

    functional_parent_obj_id: Optional[str] = None

class KeyResultCreate(BaseModel):
    title: str
    target_value: float = 100.0
    unit: str = "%"
    weight: float = 1.0

class KeyResultUpdate(BaseModel):
    title: Optional[str] = None
    target_value: Optional[float] = None
    unit: Optional[str] = None
    weight: Optional[float] = None


class KRIngestSourceConfigure(BaseModel):
    """Phase 8: configure auto-ingest for a key result."""
    source_system: str
    source_metric_tag: str
    transform_expr: Optional[str] = None
    is_active: bool = True
    rotate_token: bool = False


class ProgressUpdateCreate(BaseModel):
    """Legacy progress update. Kept for backward compatibility."""
    new_value: float
    notes: Optional[str] = None
    blockers: Optional[str] = None
    evidence_url: Optional[str] = None

class ProgressSubmissionCreate(BaseModel):
    """
    Employee submits progress for a key result.
    Employee provides their value and notes.
    Manager will review and optionally approve/override.
    """
    key_result_id: str
    employee_value: float
    employee_note: Optional[str] = None

class ProgressSubmissionReview(BaseModel):
    """
    Manager reviews employee's progress submission.
    Can approve (accept employee value), override (use manager value), or request revision.
    """
    action: str  # "approve", "override", "reject", "revision_requested"
    manager_value: Optional[float] = None  # Required if action is "override"
    manager_note: Optional[str] = None

class ProgressValidation(BaseModel):
    status: str  # APPROVED, REJECTED, REVISION_REQUESTED
    validation_notes: Optional[str] = None

class ProgressSubmissionResponse(BaseModel):
    """Response for a progress submission."""
    id: str
    key_result_id: str
    submitted_by: str
    submitted_by_id: str
    reviewed_by: Optional[str]
    reviewed_by_id: Optional[str]
    employee_value: float
    employee_note: Optional[str]
    manager_value: Optional[float]
    manager_note: Optional[str]
    status: str
    validation_level: Optional[str]
    next_approver_role: Optional[str]
    created_at: str
    reviewed_at: Optional[str]


# ===== CYCLES =====
class CycleCreate(BaseModel):
    name: str
    cycle_type: str = "QUARTERLY"
    start_date: str
    end_date: str
    freeze_date: str
    applies_to_levels: Optional[List[int]] = None

# ===== REVIEWS =====
class ReviewCycleCreate(BaseModel):
    name: str
    cycle_type: str = "QUARTERLY"
    start_date: str
    end_date: str

class ReviewCreate(BaseModel):
    cycle_id: str
    reviewee_id: str
    reviewer_id: str
    skip_level_reviewer_id: Optional[str] = None

class SelfReviewSubmit(BaseModel):
    self_rating: int
    self_review_text: str

class ManagerReviewSubmit(BaseModel):
    manager_rating: int
    manager_review_text: str
    strengths: Optional[str] = None
    improvements: Optional[str] = None

class SkipLevelReviewSubmit(BaseModel):
    skip_level_rating: int
    skip_level_review_text: str

class CalibrationSubmit(BaseModel):
    calibrated_rating: int
    calibration_notes: Optional[str] = None
    final_rating: int
