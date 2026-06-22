"""
OKR Submission and Approval Service
====================================

Implements the hierarchical submission and approval workflows for OKR progress.

Submission Flow:
1. Employee submits personal progress → Manager/Team Lead reviews
2. Team Lead submits team progress → Manager reviews
3. Department Head submits department OKR progress → Plant Head reviews
4. Plant Head submits plant OKR progress → Regional Head reviews
5. Regional Head submits regional OKR progress → CEO reviews

Each submission creates an audit trail and can be approved, rejected, or requires revision.
"""

from typing import Optional, List, Dict, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from server.models import User, Organization
from server.okr_models import OKR, OKRSubmission, OKRApproval, SubmissionStatus, ApprovalAction
from server.roles import normalize_role


class OKRSubmissionService:
    """
    Manages OKR progress submission and approval workflows.
    Ensures proper authorization and hierarchical validation.
    """

    def __init__(self, db: Session):
        self.db = db

    # ────────────────────────────────────────────────────────────────────────────
    # SUBMISSION LOGIC
    # ────────────────────────────────────────────────────────────────────────────

    def can_submit_okr_progress(
        self,
        user: User,
        okr: OKR,
        org_id: str,
    ) -> Tuple[bool, str]:
        """
        Check if user can submit progress for an OKR.
        
        Rules:
        - Employee can only submit their own personal OKRs
        - Manager/Team Lead can submit team progress
        - Department Head can submit department OKRs
        - Plant Head can submit plant OKRs for their plant
        - Regional Head can submit regional OKRs for their region
        - CEO can submit organization OKRs
        """
        role = normalize_role(user.system_role)

        # Must be OKR owner
        if okr.owner_id != user.id:
            return False, f"User is not the owner of this OKR"

        # Organization must match
        if okr.org_id != org_id:
            return False, f"OKR organization does not match user's organization"

        # Check role-based submission rights
        allowed_roles = {
            "EMPLOYEE": ["EMPLOYEE", "MANAGER", "TEAM_LEAD"],
            "TEAM": ["MANAGER", "TEAM_LEAD", "DEPT_HEAD"],
            "DEPARTMENT": ["DEPT_HEAD", "PLANT_HEAD"],
            "PLANT": ["PLANT_HEAD", "VP_OPERATIONS", "VP_MANUFACTURING"],
            "REGION": ["VP_OPERATIONS", "VP_MANUFACTURING", "CEO"],
            "ORGANIZATION": ["CEO", "CFO", "CMO", "CTO"],
        }

        level = okr.level_type.value.upper() if hasattr(okr.level_type, 'value') else str(okr.level_type).upper()
        if level not in allowed_roles or role not in allowed_roles[level]:
            return False, f"Role '{user.system_role}' cannot submit {level} OKR progress"

        return True, "Authorized to submit"

    def get_approvers_for_okr(self, okr: OKR, db: Session) -> List[User]:
        """
        Get list of users who can approve this OKR submission.
        
        Approval hierarchy:
        - Employee OKR → Manager or Team Lead
        - Team OKR → Department Head
        - Department OKR → Plant Head
        - Plant OKR → Regional Head (VP Operations)
        - Regional OKR → CEO
        - Organization OKR → CEO (can self-approve)
        """
        approver_roles = {
            "EMPLOYEE": ["MANAGER", "TEAM_LEAD"],
            "TEAM": ["DEPT_HEAD", "MANAGER"],
            "DEPARTMENT": ["PLANT_HEAD"],
            "PLANT": ["VP_OPERATIONS", "VP_MANUFACTURING"],
            "REGION": ["CEO"],
            "ORGANIZATION": ["CEO"],
        }

        level = okr.level_type.value.upper() if hasattr(okr.level_type, 'value') else str(okr.level_type).upper()
        
        if level not in approver_roles:
            return []

        approver_role_list = approver_roles[level]

        # Build query filters based on OKR level and hierarchy
        filters = []
        
        if level == "EMPLOYEE":
            # Get manager or team lead for this employee
            # This requires querying reporting relationships
            pass
        elif level == "TEAM":
            # Get department head for team's department
            if okr.department_id:
                filters.append(
                    User.department_id == okr.department_id
                )
        elif level == "DEPARTMENT":
            # Get plant head for department's plant
            if okr.plant_id:
                filters.append(
                    User.plant_id == okr.plant_id
                )
        elif level == "PLANT":
            # Get regional head (VP Operations) for plant's region
            if okr.region_id:
                filters.append(
                    User.region_id == okr.region_id
                )
        elif level == "REGION":
            # Get CEO for organization
            filters.append(
                User.org_id == okr.org_id
            )
        elif level == "ORGANIZATION":
            # Get CEO
            filters.append(
                User.org_id == okr.org_id
            )

        # Add role filter
        filters.append(
            User.system_role.in_(approver_role_list)
        )

        # Execute query
        approvers = db.query(User).filter(and_(*filters)).all()
        return approvers

    def submit_okr_progress(
        self,
        user: User,
        okr_id: str,
        comments: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Submit OKR progress for approval.
        Creates submission audit record.
        """
        okr = self.db.query(OKR).filter(OKR.id == okr_id).first()
        if not okr:
            return False, "OKR not found"

        can_submit, reason = self.can_submit_okr_progress(user, okr, okr.org_id)
        if not can_submit:
            return False, reason

        # Update OKR submission status
        okr.submission_status = SubmissionStatus.SUBMITTED
        okr.submitted_at = datetime.utcnow()
        okr.submitted_by_id = user.id
        
        self.db.add(okr)
        self.db.commit()

        return True, "OKR progress submitted for approval"

    # ────────────────────────────────────────────────────────────────────────────
    # APPROVAL LOGIC
    # ────────────────────────────────────────────────────────────────────────────

    def can_approve_okr_submission(
        self,
        user: User,
        okr: OKR,
    ) -> Tuple[bool, str]:
        """
        Check if user can approve an OKR submission.
        """
        if okr.submission_status != SubmissionStatus.SUBMITTED:
            return False, f"OKR is not in submitted state (current: {okr.submission_status})"

        # Get valid approvers and check if user is one
        approvers = self.get_approvers_for_okr(okr, self.db)
        approver_ids = [a.id for a in approvers]

        if user.id not in approver_ids:
            return False, f"User is not authorized to approve this OKR"

        return True, "Authorized to approve"

    def approve_okr_submission(
        self,
        user: User,
        okr_id: str,
        action: ApprovalAction,
        comments: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Approve or reject an OKR submission.
        
        Actions:
        - APPROVE: Accept the submitted progress
        - REJECT: Reject and return to draft
        - REQUEST_REVISION: Request changes
        - OVERRIDE: Override previous approval
        """
        okr = self.db.query(OKR).filter(OKR.id == okr_id).first()
        if not okr:
            return False, "OKR not found"

        can_approve, reason = self.can_approve_okr_submission(user, okr)
        if not can_approve:
            return False, reason

        # Process action
        if action == ApprovalAction.APPROVE:
            okr.submission_status = SubmissionStatus.APPROVED
            okr.approved_at = datetime.utcnow()
            okr.approved_by_id = user.id
            message = "OKR progress approved"
        elif action == ApprovalAction.REJECT:
            okr.submission_status = SubmissionStatus.REJECTED
            message = "OKR progress rejected"
        elif action == ApprovalAction.REQUEST_REVISION:
            okr.submission_status = SubmissionStatus.REVISE_REQUESTED
            message = "Revision requested for OKR progress"
        elif action == ApprovalAction.OVERRIDE:
            okr.submission_status = SubmissionStatus.APPROVED
            okr.approved_at = datetime.utcnow()
            okr.approved_by_id = user.id
            message = "OKR approval overridden"
        else:
            return False, f"Unknown action: {action}"

        okr.approval_comments = comments
        
        self.db.add(okr)
        self.db.commit()

        return True, message


# ============================================================================
# SCOPE FILTERING FOR ROLE-BASED DATA ISOLATION
# ============================================================================

def get_accessible_okrs_for_user(user: User, db: Session) -> List[OKR]:
    """
    Get all OKRs that the user can see based on their role and hierarchy position.
    
    Rules:
    - SUPER_ADMIN: Can see all OKRs
    - CEO: Can see organization and all regional OKRs
    - VP/Regional Head: Can see their region's OKRs (plants, departments, teams)
    - Plant Head: Can see their plant's OKRs (departments, teams)
    - Department Head: Can see their department's OKRs
    - Manager/Team Lead: Can see their team's OKRs
    - Employee: Can see own OKRs + team OKRs if team member
    """
    role = normalize_role(user.system_role)
    org_id = user.org_id

    filters = [OKR.org_id == org_id]

    if role == "SUPER_ADMIN":
        # Can see everything in org
        pass
    elif role == "CEO":
        # Can see organization and regional OKRs
        filters.append(
            OKR.level_type.in_(["organization", "region"])
        )
    elif role in ["VP_OPERATIONS", "VP_MANUFACTURING"]:
        # Can see region, plant, department, team level in their region
        if user.region_id:
            filters.append(
                and_(
                    OKR.region_id == user.region_id,
                    OKR.level_type.in_(["region", "plant", "department", "team", "employee"])
                )
            )
    elif role == "PLANT_HEAD":
        # Can see plant, department, team level in their plant
        if user.plant_id:
            filters.append(
                and_(
                    OKR.plant_id == user.plant_id,
                    OKR.level_type.in_(["plant", "department", "team", "employee"])
                )
            )
    elif role == "DEPT_HEAD":
        # Can see department, team level in their department
        if user.department_id:
            filters.append(
                and_(
                    OKR.department_id == user.department_id,
                    OKR.level_type.in_(["department", "team", "employee"])
                )
            )
    elif role in ["MANAGER", "TEAM_LEAD"]:
        # Can see team and employee OKRs
        if user.team_id:
            filters.append(
                and_(
                    OKR.team_id == user.team_id,
                    OKR.level_type.in_(["team", "employee"])
                )
            )
    elif role == "EMPLOYEE":
        # Can see own OKRs + team OKRs if part of team
        or_filters = [
            OKR.owner_id == user.id
        ]
        if user.team_id:
            or_filters.append(
                and_(
                    OKR.team_id == user.team_id,
                    OKR.level_type == "team"
                )
            )
        filters.append(or_(*or_filters))

    okrs = db.query(OKR).filter(and_(*filters)).all()
    return okrs
