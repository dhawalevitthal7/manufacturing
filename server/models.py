import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, UniqueConstraint, JSON
from sqlalchemy.orm import relationship
from server.database import Base


def gen_uuid():
    return str(uuid.uuid4())


# ===== TENANT ROOT =====
class Organization(Base):
    __tablename__ = "organizations"
    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    domain = Column(String)
    industry = Column(String, default="Manufacturing")
    size = Column(String)
    setup_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===== ORGANIZATION TREE (UNIFIED HIERARCHY) =====
class NodeType(str, enum.Enum):
    """Types of nodes in the organization tree."""
    ORGANIZATION = "ORGANIZATION"
    REGION = "REGION"
    CORPORATE_FUNCTION = "CORPORATE_FUNCTION"
    PLANT = "PLANT"
    VERTICAL = "VERTICAL"  # sub-function under corp function
    DEPARTMENT = "DEPARTMENT"
    SUB_DEPARTMENT = "SUB_DEPARTMENT"
    TEAM = "TEAM"


class OrgNode(Base):
    """
    Self-referential organization tree node. Replaces rigid Plant→Department→Team
    with flexible hierarchy that supports Region, Corporate Functions, and future levels.

    # OrgNode path/depth invariants (enforce everywhere — see server/services/org_tree_service.py):
    # - path is a dotted string of UUIDs from org root down to this node.
    # - path for ORGANIZATION root = "<org_id>" (no dots).
    # - path for any other node = parent.path + "." + this.id
    # - depth = path.count('.')  -- always derived from path; never store a different value.
    # - this.id matches the legacy entity id for PLANT, DEPARTMENT, TEAM nodes.
    # - this.id is a freshly generated UUID for ORGANIZATION root, and (later, Phase 2)
    #   for REGION and CORPORATE_FUNCTION nodes.
    """
    __tablename__ = "org_nodes"
    id = Column(String, primary_key=True, default=gen_uuid)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)
    parent_id = Column(String, ForeignKey("org_nodes.id"), nullable=True, index=True)
    node_type = Column(String, nullable=False, index=True)  # Enum value as string
    name = Column(String, nullable=False)
    code = Column(String, nullable=True)  # e.g., "PLT-RAJ-01", "FIN-001"
    head_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    path = Column(String, nullable=False, index=True)  # Materialized path for ancestor/descendant queries
    depth = Column(Integer, nullable=False, index=True)  # 0 for org, increases downward
    node_metadata = Column(JSON, default=dict)  # Type-specific fields (region info, functional area, etc.)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    parent = relationship("OrgNode", remote_side=[id], backref="children", foreign_keys=[parent_id])
    head = relationship("User", foreign_keys=[head_user_id])


# ===== MANUFACTURING STRUCTURE =====
class Plant(Base):
    __tablename__ = "plants"
    id = Column(String, primary_key=True, default=gen_uuid)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    name = Column(String, nullable=False)
    location = Column(String)
    code = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Department(Base):
    __tablename__ = "departments"
    id = Column(String, primary_key=True, default=gen_uuid)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    plant_id = Column(String, ForeignKey("plants.id"), nullable=False)
    name = Column(String, nullable=False)
    dept_type = Column(String)  # PRODUCTION, QUALITY, MAINTENANCE, etc.
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Team(Base):
    __tablename__ = "teams"
    id = Column(String, primary_key=True, default=gen_uuid)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    department_id = Column(String, ForeignKey("departments.id"), nullable=False)
    name = Column(String, nullable=False)
    lead_id = Column(String, ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class TeamMember(Base):
    """Team membership - tracks which users are members of which teams."""
    __tablename__ = "team_members"
    id = Column(String, primary_key=True, default=gen_uuid)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    team_id = Column(String, ForeignKey("teams.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    is_team_lead = Column(Boolean, default=False)  # Team lead designation
    role_in_team = Column(String, default="MEMBER")  # LEAD, MEMBER, CONTRIBUTOR
    joined_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint('team_id', 'user_id', name='uq_team_member'),
    )


class Shift(Base):
    __tablename__ = "shifts"
    id = Column(String, primary_key=True, default=gen_uuid)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    plant_id = Column(String, ForeignKey("plants.id"), nullable=False)
    name = Column(String, nullable=False)
    start_time = Column(String)
    end_time = Column(String)
    supervisor_id = Column(String, ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===== DESIGNATION (Business Hierarchy) =====
class Designation(Base):
    __tablename__ = "designations"
    id = Column(String, primary_key=True, default=gen_uuid)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    name = Column(String, nullable=False)
    level = Column(Integer, default=0)  # lower number = higher authority
    category = Column(String)  # LEADERSHIP, PLANT_LEADERSHIP, MANAGEMENT, OPERATIONAL
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===== USERS / EMPLOYEES =====
class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=gen_uuid)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=False)
    employee_id = Column(String)
    system_role = Column(String, default="EMPLOYEE")  # SUPER_ADMIN, HR_ADMIN, PLANT_MANAGER, DEPT_HEAD, MANAGER, SUPERVISOR, EMPLOYEE
    is_active = Column(Boolean, default=True)
    is_org_creator = Column(Boolean, default=False)
    avatar_color = Column(String, default="#6366f1")
    # Assignment fields (legacy — kept for backward compatibility)
    plant_id = Column(String, ForeignKey("plants.id"), nullable=True)
    department_id = Column(String, ForeignKey("departments.id"), nullable=True)
    team_id = Column(String, ForeignKey("teams.id"), nullable=True)
    designation_id = Column(String, ForeignKey("designations.id"), nullable=True)
    shift_id = Column(String, ForeignKey("shifts.id"), nullable=True)
    # OrgNode assignment (Phase 1 — the primary hierarchy location)
    org_node_id = Column(String, ForeignKey("org_nodes.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===== REPORTING RELATIONSHIPS =====
class ReportingRelationship(Base):
    """Supports direct, dotted-line, reviewer, and approver relationships."""
    __tablename__ = "reporting_relationships"
    id = Column(String, primary_key=True, default=gen_uuid)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    employee_id = Column(String, ForeignKey("users.id"), nullable=False)  # the subordinate
    manager_id = Column(String, ForeignKey("users.id"), nullable=False)   # the superior
    relationship_type = Column(String, nullable=False)  # DIRECT, DOTTED_LINE, REVIEWER, APPROVER
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint('employee_id', 'manager_id', 'relationship_type', name='uq_reporting_rel'),
    )


# ===== DASHBOARD MODULE ACCESS =====
class DashboardModule(Base):
    """Registry of all available dashboard modules."""
    __tablename__ = "dashboard_modules"
    id = Column(String, primary_key=True, default=gen_uuid)
    key = Column(String, unique=True, nullable=False)  # e.g., ORG_OKRS, PLANT_OKRS, ALIGNMENT, etc.
    name = Column(String, nullable=False)
    description = Column(Text)
    category = Column(String)  # OKR, REVIEW, ANALYTICS, MANAGEMENT, VISIBILITY
    created_at = Column(DateTime, default=datetime.utcnow)


class ModuleAccess(Base):
    """Configurable access: which system_role or designation can access which module."""
    __tablename__ = "module_access"
    id = Column(String, primary_key=True, default=gen_uuid)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    module_id = Column(String, ForeignKey("dashboard_modules.id"), nullable=False)
    # Access can be granted by system_role OR designation_id (or both)
    system_role = Column(String, nullable=True)
    designation_id = Column(String, ForeignKey("designations.id"), nullable=True)
    can_view = Column(Boolean, default=False)
    can_create = Column(Boolean, default=False)
    can_edit = Column(Boolean, default=False)
    can_approve = Column(Boolean, default=False)
    can_delete = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===== USER PERMISSION PROFILE =====
class UserPermissionProfile(Base):
    """User's complete permission profile combining role, designation, hierarchy scope, and module access."""
    __tablename__ = "user_permission_profiles"
    id = Column(String, primary_key=True, default=gen_uuid)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True)
    # Role info
    system_role = Column(String, nullable=False)  # SUPER_ADMIN, CEO, VP_OPS, PLANT_HEAD, DEPT_HEAD, MANAGER, TEAM_LEAD, SUPERVISOR, EMPLOYEE, HR_HEAD
    designation_id = Column(String, ForeignKey("designations.id"), nullable=True)
    # Hierarchy scope - what they can see/manage
    scope_type = Column(String, default="NONE")  # ORGANIZATION, PLANT, DEPARTMENT, TEAM, INDIVIDUAL
    scoped_plant_id = Column(String, ForeignKey("plants.id"), nullable=True)
    scoped_department_id = Column(String, ForeignKey("departments.id"), nullable=True)
    scoped_team_id = Column(String, ForeignKey("teams.id"), nullable=True)
    # Special flags
    can_view_all_plants = Column(Boolean, default=False)
    can_view_all_departments = Column(Boolean, default=False)
    can_view_all_teams = Column(Boolean, default=False)
    can_view_all_employees = Column(Boolean, default=False)
    can_create_plants = Column(Boolean, default=False)
    can_create_departments = Column(Boolean, default=False)
    can_create_teams = Column(Boolean, default=False)
    can_create_designations = Column(Boolean, default=False)
    can_configure_permissions = Column(Boolean, default=False)
    can_invite_employees = Column(Boolean, default=False)
    can_assign_roles = Column(Boolean, default=False)
    can_access_analytics = Column(Boolean, default=False)
    can_access_audit_logs = Column(Boolean, default=False)
    # Module visibility - serialized list of module permissions
    module_permissions = Column(Text)  # JSON: [{"module_key": "ORG_OKRS", "can_view": true, "can_create": true, ...}]
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint('org_id', 'user_id', name='uq_user_perm_profile'),
    )


# ===== USER INVITATION =====
class UserInvitation(Base):
    """Track user invitations with assigned roles and permissions."""
    __tablename__ = "user_invitations"
    id = Column(String, primary_key=True, default=gen_uuid)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    invited_email = Column(String, nullable=False)
    invited_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    # Pre-assigned role and permissions
    system_role = Column(String, nullable=False)
    designation_id = Column(String, ForeignKey("designations.id"), nullable=True)
    plant_id = Column(String, ForeignKey("plants.id"), nullable=True)
    department_id = Column(String, ForeignKey("departments.id"), nullable=True)
    team_id = Column(String, ForeignKey("teams.id"), nullable=True)
    # Invitation metadata
    status = Column(String, default="PENDING")  # PENDING, ACCEPTED, REVOKED
    invitation_token = Column(String, unique=True)
    accepted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)


# ===== OKR SYSTEM =====
class Objective(Base):
    __tablename__ = "objectives"
    id = Column(String, primary_key=True, default=gen_uuid)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    parent_id = Column(String, ForeignKey("objectives.id"), nullable=True)
    cycle_id = Column(String, ForeignKey("review_cycles.id"), nullable=True)
    assigned_by_id = Column(String, ForeignKey("users.id"), nullable=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    level = Column(String, default="INDIVIDUAL")  # ORGANIZATION, PLANT, DEPARTMENT, TEAM, INDIVIDUAL
    status = Column(String, default="ACTIVE")  # ACTIVE, COMPLETED, ARCHIVED
    progress = Column(Float, default=0.0)
    # Scope binding
    plant_id = Column(String, ForeignKey("plants.id"), nullable=True)
    department_id = Column(String, ForeignKey("departments.id"), nullable=True)
    team_id = Column(String, ForeignKey("teams.id"), nullable=True)
    # Hierarchy-based workflow fields
    creation_approval_status = Column(String, default="PENDING")  # PENDING, APPROVED, REJECTED, REVISION_REQUESTED
    creation_approved_by_id = Column(String, ForeignKey("users.id"), nullable=True)
    creation_approved_at = Column(DateTime, nullable=True)
    creation_approval_notes = Column(Text)
    visibility_scope = Column(String, default="STANDARD")  # STANDARD, RESTRICTED, PUBLIC (for visibility control)
    allows_cascade = Column(Boolean, default=True)  # Whether this OKR can be parent for child OKRs
    # Quarterly Planning Fields
    quarter = Column(String, nullable=True)  # Q1, Q2, Q3, Q4
    year = Column(Integer, nullable=True)  # 2025, 2026, etc.
    # AI-Assisted OKR Fields
    ai_generated = Column(Boolean, default=False)  # Whether this OKR was AI-suggested
    ai_metadata = Column(Text, nullable=True)  # JSON metadata from AI generation
    okr_status = Column(String, default="DRAFT")  # DRAFT, PROPOSED, APPROVED, ACTIVE, COMPLETED, ARCHIVED
    created_at = Column(DateTime, default=datetime.utcnow)


class KeyResult(Base):
    __tablename__ = "key_results"
    id = Column(String, primary_key=True, default=gen_uuid)
    objective_id = Column(String, ForeignKey("objectives.id"), nullable=False)
    title = Column(String, nullable=False)
    target_value = Column(Float, default=100.0)
    current_value = Column(Float, default=0.0)
    unit = Column(String, default="%")
    status = Column(String, default="NOT_STARTED")  # NOT_STARTED, IN_PROGRESS, COMPLETED
    weight = Column(Float, default=1.0)  # for weighted progress calculation
    created_at = Column(DateTime, default=datetime.utcnow)


class ProgressSubmission(Base):
    """
    Track employee progress submission separately from validation.
    This allows employees to submit progress independently, 
    and managers to review/approve with optional override.
    
    Can track either:
    - Individual KR progress (key_result_id set, objective_id derived)
    - Parent objective cascading progress (key_result_id null, objective_id set)
    """
    __tablename__ = "progress_submissions"
    id = Column(String, primary_key=True, default=gen_uuid)
    key_result_id = Column(String, ForeignKey("key_results.id"), nullable=True)  # Individual KR submission
    objective_id = Column(String, ForeignKey("objectives.id"), nullable=True)  # Parent-level submission
    submitted_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    reviewed_by_id = Column(String, ForeignKey("users.id"), nullable=True)
    # Employee submission
    employee_value = Column(Float, nullable=False)  # What employee submits
    employee_note = Column(Text, nullable=True)
    # Manager review/override
    manager_value = Column(Float, nullable=True)  # Manager override value (if different)
    manager_note = Column(Text, nullable=True)
    # Status tracking
    status = Column(String, default="PENDING")  # PENDING, APPROVED, REJECTED, REVISION_REQUESTED
    # Workflow tracking
    validation_level = Column(String)  # TEAM_LEAD, MANAGER, DEPT_HEAD, PLANT_HEAD, VP, CEO
    validation_chain = Column(Text)  # JSON array of all validators in approval chain
    next_approver_role = Column(String)  # Role of next approver
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)


class ProgressUpdate(Base):
    """
    Legacy progress tracking. Kept for backward compatibility.
    New submissions should use ProgressSubmission model.
    """
    __tablename__ = "progress_updates"
    id = Column(String, primary_key=True, default=gen_uuid)
    key_result_id = Column(String, ForeignKey("key_results.id"), nullable=False)
    submitted_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    validated_by_id = Column(String, ForeignKey("users.id"), nullable=True)
    previous_value = Column(Float, default=0.0)
    new_value = Column(Float, default=0.0)
    notes = Column(Text)
    blockers = Column(Text)
    evidence_url = Column(String)
    status = Column(String, default="PENDING")  # PENDING, APPROVED, REJECTED, REVISION_REQUESTED
    validation_notes = Column(Text)
    # Hierarchy-based validation workflow
    validation_level = Column(String)  # TEAM_LEAD, MANAGER, DEPT_HEAD, PLANT_HEAD, VP, CEO (indicates who validated)
    validation_chain = Column(Text)  # JSON array tracking all validators in chain
    next_approver_role = Column(String)  # Role of next approver in chain
    approved_at = Column(DateTime, nullable=True)
    # Auto-progress tracking
    auto_tracked = Column(Boolean, default=False)  # Whether progress was auto-updated by AI
    ai_coaching_notes = Column(Text, nullable=True)  # AI-generated coaching suggestions
    created_at = Column(DateTime, default=datetime.utcnow)
    validated_at = Column(DateTime, nullable=True)


# ===== REVIEW SYSTEM =====
class ReviewCycle(Base):
    __tablename__ = "review_cycles"
    id = Column(String, primary_key=True, default=gen_uuid)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    name = Column(String, nullable=False)
    cycle_type = Column(String, default="QUARTERLY")  # QUARTERLY, MONTHLY, YEARLY
    start_date = Column(String, nullable=False)
    end_date = Column(String, nullable=False)
    status = Column(String, default="ACTIVE")  # DRAFT, ACTIVE, CLOSED
    created_at = Column(DateTime, default=datetime.utcnow)


class Review(Base):
    __tablename__ = "reviews"
    id = Column(String, primary_key=True, default=gen_uuid)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    cycle_id = Column(String, ForeignKey("review_cycles.id"), nullable=False)
    reviewee_id = Column(String, ForeignKey("users.id"), nullable=False)
    reviewer_id = Column(String, ForeignKey("users.id"), nullable=False)
    skip_level_reviewer_id = Column(String, ForeignKey("users.id"), nullable=True)
    # Status flow: SELF_REVIEW_PENDING → MANAGER_REVIEW_PENDING → SKIP_LEVEL_PENDING → CALIBRATION_PENDING → COMPLETED
    status = Column(String, default="SELF_REVIEW_PENDING")
    # Self review
    self_rating = Column(Integer)
    self_review_text = Column(Text)
    self_submitted_at = Column(DateTime, nullable=True)
    # Manager review
    manager_rating = Column(Integer)
    manager_review_text = Column(Text)
    manager_submitted_at = Column(DateTime, nullable=True)
    # Skip-level review
    skip_level_rating = Column(Integer)
    skip_level_review_text = Column(Text)
    skip_level_submitted_at = Column(DateTime, nullable=True)
    # Calibration
    calibrated_rating = Column(Integer)
    calibration_notes = Column(Text)
    calibrated_by_id = Column(String, ForeignKey("users.id"), nullable=True)
    calibrated_at = Column(DateTime, nullable=True)
    # AI intelligence
    ai_summary = Column(Text)
    ai_strengths = Column(Text)
    ai_improvements = Column(Text)
    ai_risk_flags = Column(Text)
    # Final
    final_rating = Column(Integer)
    strengths = Column(Text)
    improvements = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


# ===== AUDIT LOG =====
class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String, primary_key=True, default=gen_uuid)
    org_id = Column(String, nullable=False)
    user_id = Column(String, nullable=False)
    action = Column(String, nullable=False)  # CREATE, UPDATE, DELETE, LOGIN, APPROVE, REJECT
    entity_type = Column(String)  # USER, OBJECTIVE, KEY_RESULT, REVIEW, etc.
    entity_id = Column(String)
    details = Column(Text)  # JSON string with change details
    ip_address = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===== ENTERPRISE PERMISSION MATRIX =====
class RolePermissionRule(Base):
    """Granular permission rule: maps a system_role to a permission_key with action flags."""
    __tablename__ = "role_permission_rules"
    id = Column(String, primary_key=True, default=gen_uuid)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    system_role = Column(String, nullable=False)  # SUPER_ADMIN, CEO, MANAGER, etc.
    permission_key = Column(String, nullable=False)  # From permission_registry
    can_view = Column(Boolean, default=False)
    can_create = Column(Boolean, default=False)
    can_edit = Column(Boolean, default=False)
    can_delete = Column(Boolean, default=False)
    can_approve = Column(Boolean, default=False)
    can_assign = Column(Boolean, default=False)
    can_manage = Column(Boolean, default=False)
    hierarchy_scope = Column(String, default="SELF")  # ORGANIZATION, PLANT, DEPARTMENT, TEAM, DIRECT_REPORTS, SUBTREE, SELF
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("org_id", "system_role", "permission_key", name="uq_role_perm_key"),
    )
