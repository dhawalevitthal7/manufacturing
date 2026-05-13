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

    # Map system_role to allowed OKR creation levels
    ROLE_CREATION_LEVELS = {
        "SUPER_ADMIN": ["ORGANIZATION", "PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"],
        "CEO": ["ORGANIZATION"],
        "VP_OPERATIONS": ["PLANT", "DEPARTMENT"],
        "VP_MANUFACTURING": ["PLANT", "DEPARTMENT"],
        "PLANT_HEAD": ["PLANT", "DEPARTMENT", "TEAM"],
        "OPERATIONS_HEAD": ["PLANT", "DEPARTMENT"],
        "DEPT_HEAD": ["DEPARTMENT", "TEAM"],
        "MANAGER": ["TEAM", "INDIVIDUAL"],
        "TEAM_LEAD": ["INDIVIDUAL"],
        "SUPERVISOR": ["INDIVIDUAL"],
        "EMPLOYEE": [],  # Cannot create strategic OKRs
        "OPERATOR": [],
        "TECHNICIAN": [],
    }

    # Map system_role to required scope for creation
    ROLE_CREATION_SCOPE = {
        "SUPER_ADMIN": "ORGANIZATION",
        "CEO": "ORGANIZATION",
        "VP_OPERATIONS": "ORGANIZATION",
        "VP_MANUFACTURING": "ORGANIZATION",
        "PLANT_HEAD": "PLANT",
        "OPERATIONS_HEAD": "PLANT",
        "DEPT_HEAD": "DEPARTMENT",
        "MANAGER": "TEAM",
        "TEAM_LEAD": "TEAM",
        "SUPERVISOR": "TEAM",
        "EMPLOYEE": "INDIVIDUAL",
        "OPERATOR": "INDIVIDUAL",
        "TECHNICIAN": "INDIVIDUAL",
    }

    # Map OKR level to approval roles at each stage
    APPROVAL_ROLES_BY_LEVEL = {
        "ORGANIZATION": ["CEO", "SUPER_ADMIN"],
        "PLANT": ["PLANT_HEAD", "VP_OPERATIONS", "VP_MANUFACTURING", "SUPER_ADMIN"],
        "DEPARTMENT": ["DEPT_HEAD", "PLANT_HEAD", "VP_OPERATIONS", "SUPER_ADMIN"],
        "TEAM": ["MANAGER", "DEPT_HEAD", "PLANT_HEAD", "SUPER_ADMIN"],
        "INDIVIDUAL": ["MANAGER", "TEAM_LEAD", "DEPT_HEAD", "PLANT_HEAD", "SUPER_ADMIN"],
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
        system_role = user.system_role
        allowed_levels = self.ROLE_CREATION_LEVELS.get(system_role, [])

        if okr_level.upper() not in allowed_levels:
            return False, (
                f"Role '{system_role}' cannot create {okr_level} OKRs. "
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
    ) -> Tuple[bool, str]:
        """
        Validate that OKR creation follows proper hierarchy chain.
        
        Rules:
        - ORGANIZATION OKRs have no parent
        - PLANT OKRs can optionally link to ORGANIZATION parent
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

        # PLANT OKRs
        if okr_level == "PLANT":
            if not plant_id:
                return False, "PLANT OKRs must specify a plant_id"
            if department_id or team_id:
                return False, "PLANT OKRs cannot be scoped to department/team"
            if parent_okr and parent_okr.level.upper() != "ORGANIZATION":
                return False, (
                    f"PLANT OKR parent must be ORGANIZATION level, "
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
                valid_parent_levels = ["ORGANIZATION", "PLANT", "DEPARTMENT"]
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
        
        Approval authority:
        - ORGANIZATION OKRs: approved by CEO/SUPER_ADMIN
        - PLANT OKRs: approved by Plant Head/VP/SUPER_ADMIN
        - DEPARTMENT OKRs: approved by Department Head/Plant Head/VP/SUPER_ADMIN
        - TEAM OKRs: approved by Manager/Department Head/Plant Head/SUPER_ADMIN
        - INDIVIDUAL OKRs: approved by Mgr/Team Lead/Department Head/Plant Head/SUPER_ADMIN
        """
        okr_level = okr.level.upper()
        approver_role = approver.system_role

        # Get list of roles that can approve this OKR level
        approving_roles = self.APPROVAL_ROLES_BY_LEVEL.get(okr_level, [])

        if approver_role not in approving_roles:
            return False, (
                f"Role '{approver_role}' cannot approve {okr_level} OKRs. "
                f"Approving roles: {', '.join(approving_roles)}"
            )

        # Verify approver is in the correct hierarchy scope
        if okr_level == "PLANT":
            if okr.plant_id and approver.plant_id != okr.plant_id:
                if approver_role not in ["SUPER_ADMIN", "VP_OPERATIONS", "VP_MANUFACTURING", "CEO"]:
                    return False, (
                        f"Approver must be in the same plant or have organization-wide authority"
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

        # VP-level can see all OKRs (they manage multiple plants)
        if user.system_role in ["VP_OPERATIONS", "VP_MANUFACTURING"]:
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

        # VP-level and above always superior
        if potential_superior.system_role in ["VP_OPERATIONS", "VP_MANUFACTURING", "CEO", "SUPER_ADMIN"]:
            return True

        return False

    def get_approval_chain_for_okr(
        self,
        okr: Objective,
        org_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Get the approval chain for an OKR showing who must approve it.
        Returns list of roles/users who can approve at each stage.
        """
        okr_level = okr.level.upper()
        approving_roles = self.APPROVAL_ROLES_BY_LEVEL.get(okr_level, [])

        chain = []
        for role in approving_roles:
            # Get users with this role in relevant scope
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
                })

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
