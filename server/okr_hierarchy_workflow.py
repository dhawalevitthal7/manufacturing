"""
OKR Hierarchy Workflow Service
===============================

Implements strict hierarchy-based OKR creation, assignment, validation, and approval workflow.
Ensures OKRs cascade from higher to lower levels, with proper authorization checks and 
approval workflows flowing upward.

Hierarchy Structure:
  Organization → Plant → Department → Team → Employee

Creation Rights:
- CEO/Executives: ORGANIZATION level
- VP Manufacturing/Operations Head: PLANT level
- Plant Head: PLANT level (own plant) or DEPARTMENT level
- Department Head: DEPARTMENT level or TEAM level
- Manager: TEAM level or EMPLOYEE level
- Team Lead: EMPLOYEE level (if permitted)
- Employee: EMPLOYEE level (only for self-assignment, not for creation)

Approval/Validation Rights (flows upward):
- Employee progress → validated by Team Lead/Manager
- Team execution → validated by Department Head
- Department execution → validated by Plant Head
- Plant execution → monitored by VP/Operations
- Organization execution → monitored by CEO
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from server.models import (
    User, Objective, KeyResult, ProgressUpdate, ReviewCycle,
    Plant, Department, Team, TeamMember, ReportingRelationship,
    UserPermissionProfile, Organization,
)
from server.roles import (
    allowed_objective_levels_for,
    can_create_objective_at_level,
    normalize_role,
)


class OKRHierarchyWorkflow:
    """
    Manages hierarchy-based OKR creation, assignment, validation, and approval workflow.
    """

    def __init__(self, db: Session):
        self.db = db

    # ────────────────────────────────────────────────────────────────────────────
    # HIERARCHY MAPPING
    # ────────────────────────────────────────────────────────────────────────────

    HIERARCHY_LEVELS = {
        "ORGANIZATION": 0,
        "PLANT": 1,
        "DEPARTMENT": 2,
        "TEAM": 3,
        "INDIVIDUAL": 4,  # Employee level
    }

    LEVEL_ORDER = ["ORGANIZATION", "PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"]

    # OKR creation levels: server.roles.can_create_objective_at_level (ROLE_TO_ALLOWED_OBJECTIVE_LEVELS).
    # SUPER_ADMIN removed from default approver routing (Phase 6 manual override).
    APPROVAL_ROLES_BY_LEVEL = {
        "ORGANIZATION": ["CEO", "CFO", "CMO", "CTO"],
        "REGION": ["CRO", "CEO"],
        "PLANT": ["COO", "CEO"],
        "DEPARTMENT": ["DEPT_HEAD", "PLANT_HEAD", "VP_OPERATIONS"],
        "TEAM": ["MANAGER", "DEPT_HEAD", "PLANT_HEAD"],
        "INDIVIDUAL": ["MANAGER", "TEAM_LEAD", "DEPT_HEAD", "PLANT_HEAD"],
    }

    # ────────────────────────────────────────────────────────────────────────────
    # CREATION VALIDATION
    # ────────────────────────────────────────────────────────────────────────────

    def can_create_okr_at_level(
        self,
        user: User,
        okr_level: str,
        org_id: str,
    ) -> Tuple[bool, str]:
        """
        Check if user can create an OKR at the specified level.
        Returns: (can_create: bool, reason: str)
        """
        role = normalize_role(user.system_role)
        okr_u = okr_level.upper()
        if not can_create_objective_at_level(role, okr_u):
            allowed_levels = allowed_objective_levels_for(role)
            return False, (
                f"Role '{user.system_role}' cannot create {okr_level} OKRs. "
                f"Allowed levels: {', '.join(allowed_levels) or 'None (read-only role)'}"
            )

        # Verify user has permission profile configured
        perm_profile = self.db.query(UserPermissionProfile).filter(
            UserPermissionProfile.user_id == user.id
        ).first()

        if not perm_profile:
            return False, "User permission profile not configured"

        return True, ""

    def validate_okr_hierarchy_chain(
        self,
        creator: User,
        okr_level: str,
        parent_okr: Optional[Objective],
        plant_id: Optional[str],
        department_id: Optional[str],
        team_id: Optional[str],
        region_id: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Validate that OKR creation follows proper hierarchy chain.
        
        Rules:
        - ORGANIZATION OKRs have no parent
        - REGION OKRs can optionally link to ORGANIZATION parent
        - PLANT OKRs can optionally link to ORGANIZATION or REGION parent
        - DEPARTMENT OKRs must link to PLANT parent (directly or transitively)
        - TEAM OKRs must link to DEPARTMENT parent (directly or transitively)
        - INDIVIDUAL OKRs must link to TEAM parent (directly or transitively)
        """
        okr_level = okr_level.upper()

        # ORGANIZATION OKRs
        if okr_level == "ORGANIZATION":
            if parent_okr is not None:
                return False, "ORGANIZATION OKRs cannot have a parent"
            if plant_id or department_id or team_id:
                return False, "ORGANIZATION OKRs cannot be scoped to plant/department/team"
            return True, ""

        # REGION OKRs
        if okr_level == "REGION":
            if not region_id:
                return False, "REGION OKRs must specify a region_id"
            if plant_id or department_id or team_id:
                return False, "REGION OKRs cannot be scoped to plant/department/team"
            if parent_okr and parent_okr.level.upper() != "ORGANIZATION":
                return False, (
                    f"REGION OKR parent must be ORGANIZATION level, "
                    f"got {parent_okr.level}"
                )
            return True, ""

        # PLANT OKRs
        if okr_level == "PLANT":
            if not plant_id:
                return False, "PLANT OKRs must specify a plant_id"
            if department_id or team_id:
                return False, "PLANT OKRs cannot be scoped to department/team"
            if parent_okr and parent_okr.level.upper() not in ("ORGANIZATION", "REGION"):
                return False, (
                    f"PLANT OKR parent must be ORGANIZATION or REGION level, "
                    f"got {parent_okr.level}"
                )
            return True, ""

        # DEPARTMENT OKRs
        if okr_level == "DEPARTMENT":
            if not plant_id or not department_id:
                return False, "DEPARTMENT OKRs must specify plant_id and department_id"
            if team_id:
                return False, "DEPARTMENT OKRs cannot be scoped to team"
            if parent_okr:
                valid_parent_levels = ["ORGANIZATION", "REGION", "PLANT", "DEPARTMENT"]
                if parent_okr.level.upper() not in valid_parent_levels:
                    return False, (
                        f"DEPARTMENT OKR parent must be one of {valid_parent_levels}, "
                        f"got {parent_okr.level}"
                    )
                if parent_okr.plant_id != plant_id:
                    return False, (
                        f"DEPARTMENT OKR parent must be in same plant. "
                        f"Parent plant: {parent_okr.plant_id}, OKR plant: {plant_id}"
                    )
            return True, ""

        # TEAM OKRs
        if okr_level == "TEAM":
            if not plant_id or not department_id or not team_id:
                return False, (
                    "TEAM OKRs must specify plant_id, department_id, and team_id"
                )
            if parent_okr:
                valid_parent_levels = ["ORGANIZATION", "PLANT", "DEPARTMENT", "TEAM"]
                if parent_okr.level.upper() not in valid_parent_levels:
                    return False, (
                        f"TEAM OKR parent must be one of {valid_parent_levels}, "
                        f"got {parent_okr.level}"
                    )
                if parent_okr.plant_id != plant_id:
                    return False, (
                        f"TEAM OKR parent must be in same plant. "
                        f"Parent plant: {parent_okr.plant_id}, OKR plant: {plant_id}"
                    )
                if parent_okr.department_id and parent_okr.department_id != department_id:
                    return False, (
                        f"TEAM OKR parent must be in same department (if specified). "
                        f"Parent dept: {parent_okr.department_id}, OKR dept: {department_id}"
                    )
            return True, ""

        # INDIVIDUAL OKRs
        if okr_level == "INDIVIDUAL":
            if not plant_id or not department_id or not team_id:
                return False, (
                    "INDIVIDUAL OKRs must specify plant_id, department_id, and team_id"
                )
            if parent_okr:
                valid_parent_levels = list(self.HIERARCHY_LEVELS.keys())
                if parent_okr.level.upper() not in valid_parent_levels:
                    return False, (
                        f"INDIVIDUAL OKR parent must be one of {valid_parent_levels}, "
                        f"got {parent_okr.level}"
                    )
                if parent_okr.plant_id != plant_id:
                    return False, (
                        f"INDIVIDUAL OKR parent must be in same plant"
                    )
                if parent_okr.department_id and parent_okr.department_id != department_id:
                    return False, (
                        f"INDIVIDUAL OKR parent must be in same department (if specified)"
                    )
                if parent_okr.team_id and parent_okr.team_id != team_id:
                    return False, (
                        f"INDIVIDUAL OKR parent must be in same team (if specified)"
                    )
            return True, ""

        return False, f"Invalid OKR level: {okr_level}"

    def creation_alignment_track_for_approver(
        self,
        approver: User,
        okr: Objective,
        org_id: str,
    ) -> Tuple[Optional[str], str]:
        """
        Phase 4.4: which creation-approval track(s) this approver may satisfy.

        Primary uses ``can_approve_okr`` on this OKR. Functional uses the same check on the
        functional-parent objective (same authority as approving that parent row).
        Returns (\"primary\" | \"functional\" | \"both\", \"\") or (None, reason).
        """
        if okr.pending_approver_user_id and approver.id == okr.pending_approver_user_id:
            return "primary", ""
        primary_ok, pr = self.can_approve_okr(approver, okr, org_id)
        fp = None
        if okr.functional_parent_obj_id:
            fp = (
                self.db.query(Objective)
                .filter(Objective.id == okr.functional_parent_obj_id)
                .first()
            )
        if not fp:
            if primary_ok:
                return "primary", ""
            return None, pr

        fp_ok, fr = self.can_approve_okr(approver, fp, org_id)
        if primary_ok and fp_ok:
            return "both", ""
        if primary_ok:
            return "primary", pr
        if fp_ok:
            return "functional", fr
        return None, pr or fr

    def can_validate_progress_including_functional_alignment(
        self,
        validator: User,
        okr: Objective,
        submitter: User,
    ) -> Tuple[bool, str]:
        """
        Phase 4.4: allow validators who sit on the functional-parent OKR's validation chain
        to approve progress on this OKR (dual reporting).
        """
        ok, reason = self.can_validate_progress(validator, okr, submitter)
        if ok:
            return True, ""
        if not okr.functional_parent_obj_id:
            return False, reason
        fp = (
            self.db.query(Objective)
            .filter(Objective.id == okr.functional_parent_obj_id)
            .first()
        )
        if not fp:
            return False, reason
        ok2, reason2 = self.can_validate_progress(validator, fp, submitter)
        if ok2:
            return True, ""
        return False, reason

    def _approval_chain_rows_for_objective(
        self,
        okr: Objective,
        org_id: str,
        alignment: str,
    ) -> List[Dict[str, Any]]:
        """Build approval-chain user rows for one objective scope (primary or functional parent)."""
        okr_level = okr.level.upper()
        approving_roles = self.APPROVAL_ROLES_BY_LEVEL.get(okr_level, [])
        chain: List[Dict[str, Any]] = []
        for role in approving_roles:
            if okr_level == "ORGANIZATION":
                users = self.db.query(User).filter(
                    User.system_role == role,
                    User.org_id == org_id,
                    User.is_active == True,
                ).all()
            elif okr_level == "PLANT" and okr.plant_id:
                users = self.db.query(User).filter(
                    User.system_role == role,
                    User.plant_id == okr.plant_id,
                    User.org_id == org_id,
                    User.is_active == True,
                ).all()
            elif okr_level == "DEPARTMENT" and okr.department_id:
                users = self.db.query(User).filter(
                    User.system_role == role,
                    User.department_id == okr.department_id,
                    User.org_id == org_id,
                    User.is_active == True,
                ).all()
            elif okr_level in ["TEAM", "INDIVIDUAL"] and okr.team_id:
                users = self.db.query(User).filter(
                    User.system_role == role,
                    User.team_id == okr.team_id,
                    User.org_id == org_id,
                    User.is_active == True,
                ).all()
            else:
                users = self.db.query(User).filter(
                    User.system_role == role,
                    User.org_id == org_id,
                    User.is_active == True,
                ).all()

            for user in users:
                chain.append({
                    "role": role,
                    "user_id": user.id,
                    "user_name": user.name,
                    "email": user.email,
                    "alignment": alignment,
                })
        return chain

    # ────────────────────────────────────────────────────────────────────────────
    # ASSIGNMENT & CASCADING
    # ────────────────────────────────────────────────────────────────────────────

    def can_assign_okr_to_user(
        self,
        creator: User,
        assignee: User,
        okr_level: str,
        org_id: str,
    ) -> Tuple[bool, str]:
        """
        Check if creator can assign an OKR to assignee at the specified level.
        
        Rules:
        - Creator must have authority at that level or higher
        - Assignee's role must allow OKR ownership at that level
        - Hierarchy must be respected (no cross-plant assignments)
        """
        okr_level = okr_level.upper()
        creator_role = creator.system_role
        assignee_role = assignee.system_role

        # Check creator has permission to create at this level
        can_create, reason = self.can_create_okr_at_level(creator, okr_level, org_id)
        if not can_create:
            return False, f"Creator: {reason}"

        # Get assignee's permission profile
        assignee_perm = self.db.query(UserPermissionProfile).filter(
            UserPermissionProfile.user_id == assignee.id
        ).first()

        if not assignee_perm:
            return False, "Assignee permission profile not configured"

        # Assignee cannot own OKRs they cannot view
        if okr_level == "ORGANIZATION":
            if assignee_perm.scope_type not in ["ORGANIZATION"]:
                return False, (
                    f"Assignee with scope '{assignee_perm.scope_type}' "
                    f"cannot own ORGANIZATION OKRs"
                )
        elif okr_level == "PLANT":
            # NOTE: REGION scope intentionally not handled here. A REGIONAL_HEAD
            # creating a PLANT-level OKR cannot, in Phase 3, assign that OKR to a
            # plant employee whose plant sits under their region. This is a known
            # limitation tracked for Phase 4 (matrix reporting), where the path-based
            # scope check will replace the per-level allow-list.
            if assignee_perm.scope_type not in ["ORGANIZATION", "PLANT"]:
                return False, (
                    f"Assignee with scope '{assignee_perm.scope_type}' "
                    f"cannot own PLANT OKRs"
                )
        elif okr_level == "DEPARTMENT":
            if assignee_perm.scope_type not in ["ORGANIZATION", "PLANT", "DEPARTMENT"]:
                return False, (
                    f"Assignee with scope '{assignee_perm.scope_type}' "
                    f"cannot own DEPARTMENT OKRs"
                )
        elif okr_level == "TEAM":
            if assignee_perm.scope_type not in ["ORGANIZATION", "PLANT", "DEPARTMENT", "TEAM"]:
                return False, (
                    f"Assignee with scope '{assignee_perm.scope_type}' "
                    f"cannot own TEAM OKRs"
                )
        # INDIVIDUAL OKRs can be assigned to anyone with appropriate hierarchy access

        # Verify no cross-plant assignment
        if assignee.plant_id and creator.plant_id and assignee.plant_id != creator.plant_id:
            if creator_role not in ["SUPER_ADMIN", "CEO", "VP_OPERATIONS", "VP_MANUFACTURING"]:
                return False, (
                    "Cannot assign OKR to user in different plant "
                    "(unless SUPER_ADMIN or VP-level)"
                )

        return True, ""

    def get_okr_recipients_in_hierarchy(
        self,
        org_id: str,
        okr_level: str,
        scope_plant_id: Optional[str] = None,
        scope_dept_id: Optional[str] = None,
        scope_team_id: Optional[str] = None,
    ) -> List[User]:
        """
        Get list of users who can receive OKR assignments at the specified level.
        
        For ORGANIZATION OKRs: CEO, VP-level executives
        For PLANT OKRs: Plant Heads in that plant
        For DEPARTMENT OKRs: Department Heads in that department
        For TEAM OKRs: Managers/Team Leads in that team
        For INDIVIDUAL OKRs: Individual employees
        """
        okr_level = okr_level.upper()

        if okr_level == "ORGANIZATION":
            # Organization-level: CEO and VP-level roles
            return self.db.query(User).filter(
                User.org_id == org_id,
                User.system_role.in_(["CEO", "VP_OPERATIONS", "VP_MANUFACTURING"]),
                User.is_active == True,
            ).all()

        elif okr_level == "PLANT":
            if not scope_plant_id:
                return []
            # Plant-level: Plant Heads in that plant
            return self.db.query(User).filter(
                User.org_id == org_id,
                User.plant_id == scope_plant_id,
                User.system_role.in_(["PLANT_HEAD", "OPERATIONS_HEAD"]),
                User.is_active == True,
            ).all()

        elif okr_level == "DEPARTMENT":
            if not scope_dept_id:
                return []
            # Department-level: Department Heads in that department
            return self.db.query(User).filter(
                User.org_id == org_id,
                User.department_id == scope_dept_id,
                User.system_role.in_(["DEPT_HEAD"]),
                User.is_active == True,
            ).all()

        elif okr_level == "TEAM":
            if not scope_team_id:
                return []
            # Team-level: Managers and Team Leads in that team
            return self.db.query(User).filter(
                or_(
                    and_(
                        User.org_id == org_id,
                        User.team_id == scope_team_id,
                        User.system_role.in_(["MANAGER", "TEAM_LEAD"]),
                    ),
                    and_(
                        User.org_id == org_id,
                        TeamMember.user_id == User.id,
                        TeamMember.team_id == scope_team_id,
                        TeamMember.is_team_lead == True,
                    ),
                ),
                User.is_active == True,
            ).all()

        elif okr_level == "INDIVIDUAL":
            if not scope_team_id:
                # Return all employees in organization
                return self.db.query(User).filter(
                    User.org_id == org_id,
                    User.system_role.in_(
                        ["EMPLOYEE", "SUPERVISOR", "OPERATOR", "TECHNICIAN"]
                    ),
                    User.is_active == True,
                ).all()
            else:
                # Return team members in that team
                team_member_ids = self.db.query(TeamMember.user_id).filter(
                    TeamMember.team_id == scope_team_id,
                    TeamMember.is_active == True,
                ).all()
                return self.db.query(User).filter(
                    User.id.in_([tm[0] for tm in team_member_ids]),
                    User.is_active == True,
                ).all()

        return []

    # ────────────────────────────────────────────────────────────────────────────
    # APPROVAL WORKFLOW
    # ────────────────────────────────────────────────────────────────────────────

    def can_approve_okr(
        self,
        approver: User,
        okr: Objective,
        org_id: str,
    ) -> Tuple[bool, str]:
        """
        Check if user can approve an OKR.
        
        Approval authority (default chain; SUPER_ADMIN uses Phase-6 override, not listed):
        - ORGANIZATION OKRs: CEO
        - PLANT OKRs: Plant Head / VP
        - DEPARTMENT OKRs: Department Head / Plant Head / VP
        - TEAM OKRs: Manager / Department Head / Plant Head
        - INDIVIDUAL OKRs: Manager / Team Lead / Department Head / Plant Head
        """
        okr_level = okr.level.upper()
        approver_role = approver.system_role

        # Resolved pending approver always may act on this OKR.
        if okr.pending_approver_user_id and approver.id == okr.pending_approver_user_id:
            return True, ""

        # Get list of roles that can approve this OKR level
        approving_roles = self.APPROVAL_ROLES_BY_LEVEL.get(okr_level, [])

        if approver_role not in approving_roles:
            return False, (
                f"Role '{approver_role}' cannot approve {okr_level} OKRs. "
                f"Approving roles: {', '.join(approving_roles)}"
            )

        # Verify approver is in the correct hierarchy scope
        if okr_level == "REGION":
            if approver_role in ["CRO", "CEO", "SUPER_ADMIN"]:
                return True, ""

        elif okr_level == "PLANT":
            if approver_role in ["COO", "CEO", "SUPER_ADMIN"]:
                return True, ""
            if okr.plant_id and approver.plant_id != okr.plant_id:
                if approver_role not in ["VP_OPERATIONS", "VP_MANUFACTURING"]:
                    return False, (
                        "Approver must be in the same plant or have organization-wide authority"
                    )

        elif okr_level == "DEPARTMENT":
            if okr.department_id and approver.department_id != okr.department_id:
                if approver_role not in ["SUPER_ADMIN", "VP_OPERATIONS", "VP_MANUFACTURING", "PLANT_HEAD", "CEO"]:
                    return False, (
                        f"Approver must be in the same department or have higher hierarchy authority"
                    )

        elif okr_level in ["TEAM", "INDIVIDUAL"]:
            if okr.plant_id and approver.plant_id != okr.plant_id:
                if approver_role not in ["SUPER_ADMIN", "VP_OPERATIONS", "VP_MANUFACTURING", "CEO"]:
                    return False, (
                        f"Approver must be in the same plant or have higher hierarchy authority"
                    )

        return True, ""

    def can_validate_progress(
        self,
        validator: User,
        okr: Objective,
        submitter: User,
    ) -> Tuple[bool, str]:
        """
        Check if user can validate progress for an OKR.
        
        Validation authority flows upward:
        - Individual progress: validated by Team Lead/Manager one level up
        - Team progress: validated by Department Head
        - Department progress: validated by Plant Head
        - Plant progress: validated by VP/Operations Head
        - Organization progress: validated by CEO
        """
        validator_role = validator.system_role
        okr_level = okr.level.upper()
        submitter_role = submitter.system_role if submitter else ""

        # Plant Head submitting plant-level KR progress → COO validates
        if okr_level == "PLANT" and submitter_role == "PLANT_HEAD":
            if validator_role == "COO":
                return True, ""
            if validator_role in ("CEO", "SUPER_ADMIN"):
                return True, ""
            return False, "Plant Head plant-level progress must be validated by the COO"

        # Regional Head submitting region-level KR progress → CRO validates
        if okr_level == "REGION" and submitter_role == "REGIONAL_HEAD":
            if validator_role == "CRO":
                return True, ""
            if validator_role in ("CEO", "SUPER_ADMIN"):
                return True, ""
            return False, "Regional Head region-level progress must be validated by the CRO"

        # Validators must be in management/review position
        if validator_role not in self.APPROVAL_ROLES_BY_LEVEL.get(okr_level, []):
            return False, f"Role '{validator_role}' cannot validate {okr_level} OKRs"

        # Must be in same hierarchy chain (direct manager or higher)
        # Check reporting relationship or hierarchy
        is_direct_manager = self._is_direct_manager(validator, submitter)
        is_hierarchy_superior = self._is_hierarchy_superior(
            validator, submitter, okr_level
        )

        if not (is_direct_manager or is_hierarchy_superior):
            return False, (
                "Validator must be direct manager or hierarchy superior "
                "of the OKR owner/submitter"
            )

        return True, ""

    # ────────────────────────────────────────────────────────────────────────────
    # VISIBILITY & ACCESS CONTROL
    # ────────────────────────────────────────────────────────────────────────────

    def get_visible_okrs_for_user(
        self,
        user: User,
        org_id: str,
    ) -> List[Objective]:
        """
        Get all OKRs visible to a user based on hierarchy scope and permissions.
        
        Visibility Rules:
        - SUPER_ADMIN: All OKRs
        - CEO: All OKRs (org-level perspective)
        - VP-level: All OKRs in plants they oversee
        - Plant Head: All OKRs in their plant
        - Department Head: All OKRs in their department
        - Manager: OKRs in their team
        - Team Lead: OKRs in their team
        - Employee: Own OKRs and team/org OKRs they can see
        """
        perm_profile = self.db.query(UserPermissionProfile).filter(
            UserPermissionProfile.user_id == user.id
        ).first()

        if not perm_profile:
            # User has no permission profile - return only their own OKRs
            return self.db.query(Objective).filter(
                Objective.owner_id == user.id
            ).all()

        query = self.db.query(Objective).filter(
            Objective.org_id == org_id
        )

        # SUPER_ADMIN and CEO can see all OKRs
        if user.system_role in ["SUPER_ADMIN", "CEO"]:
            return query.all()

        # VP-level, COO, CRO can see all OKRs (org-wide oversight)
        if user.system_role in ["VP_OPERATIONS", "VP_MANUFACTURING", "COO", "CRO"]:
            return query.all()

        # Plant Head can see all OKRs in their plant
        if user.system_role == "PLANT_HEAD":
            if user.plant_id:
                return query.filter(
                    or_(
                        Objective.plant_id == user.plant_id,
                        Objective.level == "ORGANIZATION",
                    )
                ).all()

        # Department Head can see department + team + individual + org
        if user.system_role == "DEPT_HEAD":
            if user.department_id:
                return query.filter(
                    or_(
                        Objective.department_id == user.department_id,
                        Objective.level.in_(["ORGANIZATION", "PLANT"]),
                    )
                ).all()

        # Manager and Team Lead can see team + individual + higher levels
        if user.system_role in ["MANAGER", "TEAM_LEAD"]:
            if user.team_id:
                return query.filter(
                    or_(
                        Objective.team_id == user.team_id,
                        Objective.level.in_(["ORGANIZATION", "PLANT", "DEPARTMENT"]),
                    )
                ).all()

        # Employee/Operator/Technician can see their own OKRs, team OKRs, and org OKRs
        own_okrs = query.filter(Objective.owner_id == user.id)
        team_okrs = query.filter(Objective.team_id == user.team_id) if user.team_id else self.db.query(Objective).filter(Objective.id == None)
        org_okrs = query.filter(Objective.level.in_(["ORGANIZATION", "PLANT", "DEPARTMENT"]))

        return own_okrs.union(team_okrs).union(org_okrs).all()

    def can_view_okr(
        self,
        user: User,
        okr: Objective,
    ) -> bool:
        """Quick check if user can view a specific OKR."""
        visible_okrs = self.get_visible_okrs_for_user(user, okr.org_id)
        return any(o.id == okr.id for o in visible_okrs)

    # ────────────────────────────────────────────────────────────────────────────
    # HELPER METHODS
    # ────────────────────────────────────────────────────────────────────────────

    def _is_direct_manager(self, potential_manager: User, employee: User) -> bool:
        """Check if potential_manager is the direct manager of employee."""
        rel = self.db.query(ReportingRelationship).filter(
            ReportingRelationship.employee_id == employee.id,
            ReportingRelationship.manager_id == potential_manager.id,
            ReportingRelationship.relationship_type == "DIRECT",
            ReportingRelationship.is_active == True,
        ).first()
        return rel is not None

    def _is_hierarchy_superior(
        self,
        potential_superior: User,
        subordinate: User,
        okr_level: str,
    ) -> bool:
        """
        Check if potential_superior is hierarchy superior to subordinate
        based on OKR level and organizational structure.
        """
        okr_level = okr_level.upper()

        # For INDIVIDUAL OKRs, check same team/department/plant
        if okr_level == "INDIVIDUAL":
            if subordinate.team_id and potential_superior.team_id == subordinate.team_id:
                # Same team, check role
                return potential_superior.system_role in ["MANAGER", "TEAM_LEAD"]
            if subordinate.department_id and potential_superior.department_id == subordinate.department_id:
                # Same department, check role
                return potential_superior.system_role in ["DEPT_HEAD", "MANAGER"]
            if subordinate.plant_id and potential_superior.plant_id == subordinate.plant_id:
                # Same plant, check role
                return potential_superior.system_role in ["PLANT_HEAD", "DEPT_HEAD", "MANAGER"]

        # For TEAM OKRs, check department/plant
        if okr_level == "TEAM":
            if subordinate.department_id and potential_superior.department_id == subordinate.department_id:
                return potential_superior.system_role in ["DEPT_HEAD"]
            if subordinate.plant_id and potential_superior.plant_id == subordinate.plant_id:
                return potential_superior.system_role in ["PLANT_HEAD"]

        # For DEPARTMENT OKRs, check plant
        if okr_level == "DEPARTMENT":
            if subordinate.plant_id and potential_superior.plant_id == subordinate.plant_id:
                return potential_superior.system_role in ["PLANT_HEAD"]

        # For PLANT OKRs, COO / CEO approve plant-head submissions
        if okr_level == "PLANT":
            if potential_superior.system_role in ["COO", "CEO", "VP_OPERATIONS", "VP_MANUFACTURING"]:
                return True

        # For REGION OKRs, CRO / CEO approve regional-head submissions
        if okr_level == "REGION":
            if potential_superior.system_role in ["CRO", "CEO", "CFO", "CMO", "CTO"]:
                return True

        # VP-level and above always superior for lower scopes
        if potential_superior.system_role in ["VP_OPERATIONS", "VP_MANUFACTURING", "CEO", "SUPER_ADMIN", "COO", "CRO"]:
            return True

        return False

    def get_approval_chain_for_okr(
        self,
        okr: Objective,
        org_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Get the approval chain for an OKR showing who must approve it.

        Phase 4.4: each entry includes ``alignment`` — ``primary`` (solid hierarchy on this OKR)
        or ``functional`` (approvers taken from the functional-parent objective's level/scope).
        """
        chain = self._approval_chain_rows_for_objective(okr, org_id, "primary")
        if okr.functional_parent_obj_id:
            fp = (
                self.db.query(Objective)
                .filter(Objective.id == okr.functional_parent_obj_id)
                .first()
            )
            if fp:
                chain.extend(
                    self._approval_chain_rows_for_objective(fp, org_id, "functional")
                )
        return chain

    def get_suggested_parent_okr(
        self,
        child_level: str,
        child_plant_id: Optional[str],
        child_department_id: Optional[str],
        child_team_id: Optional[str],
        org_id: str,
    ) -> Optional[Objective]:
        """
        Suggest the most appropriate parent OKR for a new OKR at the given level.
        """
        child_level = child_level.upper()

        # PLANT OKRs should link to ORGANIZATION
        if child_level == "PLANT":
            return self.db.query(Objective).filter(
                Objective.level == "ORGANIZATION",
                Objective.org_id == org_id,
                Objective.status == "ACTIVE",
            ).first()

        # DEPARTMENT OKRs should link to PLANT
        if child_level == "DEPARTMENT" and child_plant_id:
            return self.db.query(Objective).filter(
                Objective.level == "PLANT",
                Objective.plant_id == child_plant_id,
                Objective.org_id == org_id,
                Objective.status == "ACTIVE",
            ).first()

        # TEAM OKRs should link to DEPARTMENT
        if child_level == "TEAM" and child_department_id:
            return self.db.query(Objective).filter(
                Objective.level == "DEPARTMENT",
                Objective.department_id == child_department_id,
                Objective.org_id == org_id,
                Objective.status == "ACTIVE",
            ).first()

        # INDIVIDUAL OKRs should link to TEAM
        if child_level == "INDIVIDUAL" and child_team_id:
            return self.db.query(Objective).filter(
                Objective.level == "TEAM",
                Objective.team_id == child_team_id,
                Objective.org_id == org_id,
                Objective.status == "ACTIVE",
            ).first()

        return None
