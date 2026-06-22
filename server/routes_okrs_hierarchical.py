"""
API Routes for Hierarchical OKR Operations
===========================================

Implements REST endpoints for:
- Creating OKRs at specific hierarchical levels (region, plant, department)
- Filtering OKRs based on user role and hierarchy position
- Submitting OKR progress
- Approving/rejecting OKR submissions
- Managing approval workflows
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
from datetime import datetime

from server.database import get_db
from server.auth import get_jwt_payload
from server.models import User
from server.okr_models import OKR, OKRSubmission, OKRApproval, SubmissionStatus, ApprovalAction, OKRLevelType
from server.okr_submission_service import OKRSubmissionService, get_accessible_okrs_for_user
from server.schemas import ObjectiveCreate
from server.roles import normalize_role

router = APIRouter(prefix="/api/v1/okrs", tags=["hierarchical-okrs"])


# ────────────────────────────────────────────────────────────────────────────
# HELPER: Get current user from JWT
# ────────────────────────────────────────────────────────────────────────────

def get_current_user(payload: dict = Depends(get_jwt_payload), db: Session = Depends(get_db)) -> User:
    """Extract and validate current user from JWT payload."""
    # Try multiple JWT claim names
    user_id = payload.get("sub") or payload.get("user_id") or payload.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token: no user ID")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user


# ────────────────────────────────────────────────────────────────────────────
# OKR SCOPE & FILTERING ENDPOINTS
# ────────────────────────────────────────────────────────────────────────────

@router.get("/accessible")
def get_accessible_okrs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    quarter: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    level_type: Optional[str] = Query(None),
):
    """
    Get all OKRs accessible to the current user based on their role and hierarchy.
    
    **Rules:**
    - SUPER_ADMIN: All OKRs in organization
    - CEO: Organization and regional OKRs
    - VP/Regional Head: All OKRs in their region
    - Plant Head: All OKRs in their plant
    - Department Head: All OKRs in their department
    - Manager/Team Lead: Team and employee OKRs
    - Employee: Own OKRs + team OKRs
    """
    try:
        okrs = get_accessible_okrs_for_user(current_user, db)
        
        # Apply filters if provided
        if quarter:
            okrs = [o for o in okrs if o.quarter == quarter]
        if year:
            okrs = [o for o in okrs if o.year == year]
        if level_type:
            okrs = [o for o in okrs if str(o.level_type).lower() == level_type.lower()]
        
        # Serialize OKRs
        result = []
        for okr in okrs:
            owner = db.query(User).filter(User.id == okr.owner_id).first()
            result.append({
                "id": okr.id,
                "objective": okr.objective,
                "level_type": okr.level_type.value if hasattr(okr.level_type, 'value') else str(okr.level_type),
                "owner": {
                    "id": owner.id,
                    "name": owner.name,
                    "email": owner.email,
                } if owner else None,
                "status": okr.status.value if hasattr(okr.status, 'value') else str(okr.status),
                "submission_status": okr.submission_status.value if hasattr(okr.submission_status, 'value') else str(okr.submission_status),
                "progress": okr.progress,
                "quarter": okr.quarter,
                "year": okr.year,
                "region_id": okr.region_id,
                "plant_id": okr.plant_id,
                "department_id": okr.department_id,
                "team_id": okr.team_id,
            })
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching accessible OKRs: {str(e)}")


@router.get("/region/{region_id}")
def get_region_okrs(
    region_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all OKRs for a specific region.
    Only accessible to users in that region or higher roles.
    """
    role = normalize_role(current_user.system_role)
    
    # Check authorization
    if role not in ["SUPER_ADMIN", "CEO", "VP_OPERATIONS", "VP_MANUFACTURING"]:
        raise HTTPException(status_code=403, detail="Not authorized to view region OKRs")
    
    if role in ["VP_OPERATIONS", "VP_MANUFACTURING"] and current_user.region_id != region_id:
        raise HTTPException(status_code=403, detail="Can only view your own region")
    
    # Get all OKRs for this region
    okrs = db.query(OKR).filter(
        OKR.region_id == region_id,
        OKR.org_id == current_user.org_id
    ).all()
    
    return [{
        "id": o.id,
        "objective": o.objective,
        "level_type": o.level_type.value if hasattr(o.level_type, 'value') else str(o.level_type),
        "progress": o.progress,
        "status": o.status.value if hasattr(o.status, 'value') else str(o.status),
        "submission_status": o.submission_status.value if hasattr(o.submission_status, 'value') else str(o.submission_status),
    } for o in okrs]


@router.get("/plant/{plant_id}")
def get_plant_okrs(
    plant_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all OKRs for a specific plant.
    Only accessible to users in that plant or higher roles.
    """
    role = normalize_role(current_user.system_role)
    
    if role not in ["SUPER_ADMIN", "CEO", "VP_OPERATIONS", "VP_MANUFACTURING", "PLANT_HEAD"]:
        raise HTTPException(status_code=403, detail="Not authorized to view plant OKRs")
    
    if role == "PLANT_HEAD" and current_user.plant_id != plant_id:
        raise HTTPException(status_code=403, detail="Can only view your own plant")
    
    okrs = db.query(OKR).filter(
        OKR.plant_id == plant_id,
        OKR.org_id == current_user.org_id
    ).all()
    
    return [{
        "id": o.id,
        "objective": o.objective,
        "level_type": o.level_type.value if hasattr(o.level_type, 'value') else str(o.level_type),
        "progress": o.progress,
        "status": o.status.value if hasattr(o.status, 'value') else str(o.status),
        "submission_status": o.submission_status.value if hasattr(o.submission_status, 'value') else str(o.submission_status),
    } for o in okrs]


@router.get("/department/{department_id}")
def get_department_okrs(
    department_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all OKRs for a specific department.
    Only accessible to users in that department or higher roles.
    """
    role = normalize_role(current_user.system_role)
    
    if role not in ["SUPER_ADMIN", "CEO", "VP_OPERATIONS", "VP_MANUFACTURING", "PLANT_HEAD", "DEPT_HEAD"]:
        raise HTTPException(status_code=403, detail="Not authorized to view department OKRs")
    
    if role == "DEPT_HEAD" and current_user.department_id != department_id:
        raise HTTPException(status_code=403, detail="Can only view your own department")
    
    okrs = db.query(OKR).filter(
        OKR.department_id == department_id,
        OKR.org_id == current_user.org_id
    ).all()
    
    return [{
        "id": o.id,
        "objective": o.objective,
        "level_type": o.level_type.value if hasattr(o.level_type, 'value') else str(o.level_type),
        "progress": o.progress,
        "status": o.status.value if hasattr(o.status, 'value') else str(o.status),
        "submission_status": o.submission_status.value if hasattr(o.submission_status, 'value') else str(o.submission_status),
    } for o in okrs]


# ────────────────────────────────────────────────────────────────────────────
# SUBMISSION & APPROVAL ENDPOINTS
# ────────────────────────────────────────────────────────────────────────────

@router.post("/{okr_id}/submit")
def submit_okr_progress(
    okr_id: str,
    comments: Optional[str] = Body(None, embed=True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit OKR progress for approval.
    
    Submission hierarchy:
    - Employee submits personal progress → Manager/Team Lead approves
    - Team Lead submits team progress → Manager approves
    - Department Head submits department OKR → Plant Head approves
    - Plant Head submits plant OKR → Regional Head approves
    - Regional Head submits regional OKR → CEO approves
    """
    try:
        service = OKRSubmissionService(db)
        success, message = service.submit_okr_progress(current_user, okr_id, comments)
        
        if not success:
            raise HTTPException(status_code=400, detail=message)
        
        okr = db.query(OKR).filter(OKR.id == okr_id).first()
        return {
            "success": True,
            "message": message,
            "okr_id": okr_id,
            "submission_status": okr.submission_status.value if hasattr(okr.submission_status, 'value') else str(okr.submission_status),
            "submitted_at": okr.submitted_at.isoformat() if okr.submitted_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error submitting OKR progress: {str(e)}")


@router.get("/submissions/pending")
def get_pending_submissions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all OKR submissions pending approval for the current user.
    
    Returns OKRs submitted for the current user's approval based on their role.
    """
    try:
        service = OKRSubmissionService(db)
        
        # Get all OKRs awaiting approval where current user is an approver
        pending_okrs = db.query(OKR).filter(
            OKR.submission_status == SubmissionStatus.SUBMITTED,
            OKR.org_id == current_user.org_id
        ).all()
        
        # Filter to only ones this user can approve
        approvable = []
        for okr in pending_okrs:
            can_approve, _ = service.can_approve_okr_submission(current_user, okr)
            if can_approve:
                approvable.append(okr)
        
        result = []
        for okr in approvable:
            owner = db.query(User).filter(User.id == okr.owner_id).first()
            result.append({
                "id": okr.id,
                "objective": okr.objective,
                "level_type": okr.level_type.value if hasattr(okr.level_type, 'value') else str(okr.level_type),
                "progress": okr.progress,
                "owner": {
                    "id": owner.id,
                    "name": owner.name,
                    "email": owner.email,
                } if owner else None,
                "submitted_at": okr.submitted_at.isoformat() if okr.submitted_at else None,
                "submitted_by": {
                    "id": okr.submitted_by.id,
                    "name": okr.submitted_by.name,
                } if okr.submitted_by else None,
            })
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching pending submissions: {str(e)}")


@router.post("/{okr_id}/approve")
def approve_okr_submission(
    okr_id: str,
    action: str = Body(..., embed=True),  # "approve", "reject", "request_revision"
    comments: Optional[str] = Body(None, embed=True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Approve, reject, or request revision on an OKR submission.
    
    **Actions:**
    - `approve`: Accept the submitted progress
    - `reject`: Reject and return to draft state
    - `request_revision`: Request changes before approval
    - `override`: Override previous approval (SUPER_ADMIN only)
    """
    try:
        # Map string action to enum
        action_map = {
            "approve": ApprovalAction.APPROVE,
            "reject": ApprovalAction.REJECT,
            "request_revision": ApprovalAction.REQUEST_REVISION,
            "override": ApprovalAction.OVERRIDE,
        }
        
        if action not in action_map:
            raise HTTPException(status_code=400, detail=f"Invalid action: {action}")
        
        approval_action = action_map[action]
        
        service = OKRSubmissionService(db)
        success, message = service.approve_okr_submission(
            current_user,
            okr_id,
            approval_action,
            comments
        )
        
        if not success:
            raise HTTPException(status_code=400, detail=message)
        
        okr = db.query(OKR).filter(OKR.id == okr_id).first()
        
        # Create approval record
        approval = OKRApproval(
            id=str(uuid.uuid4()),
            okr_id=okr_id,
            approved_by_id=current_user.id,
            approval_date=datetime.utcnow(),
            action=approval_action,
            approval_comments=comments,
            approval_status=okr.submission_status,
        )
        db.add(approval)
        db.commit()
        
        return {
            "success": True,
            "message": message,
            "okr_id": okr_id,
            "action": action,
            "submission_status": okr.submission_status.value if hasattr(okr.submission_status, 'value') else str(okr.submission_status),
            "approved_at": okr.approved_at.isoformat() if okr.approved_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error approving OKR submission: {str(e)}")


@router.get("/{okr_id}/approvals")
def get_okr_approval_history(
    okr_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the approval history for an OKR.
    Shows all approvals, rejections, and revision requests.
    """
    try:
        okr = db.query(OKR).filter(OKR.id == okr_id).first()
        if not okr:
            raise HTTPException(status_code=404, detail="OKR not found")
        
        # Check authorization
        service = OKRSubmissionService(db)
        accessible = get_accessible_okrs_for_user(current_user, db)
        if okr not in accessible:
            raise HTTPException(status_code=403, detail="Not authorized to view this OKR")
        
        approvals = db.query(OKRApproval).filter(OKRApproval.okr_id == okr_id).order_by(OKRApproval.approval_date.desc()).all()
        
        result = []
        for approval in approvals:
            approver = db.query(User).filter(User.id == approval.approved_by_id).first()
            result.append({
                "id": approval.id,
                "action": approval.action.value if hasattr(approval.action, 'value') else str(approval.action),
                "status": approval.approval_status.value if hasattr(approval.approval_status, 'value') else str(approval.approval_status),
                "approved_by": {
                    "id": approver.id,
                    "name": approver.name,
                } if approver else None,
                "comments": approval.approval_comments,
                "approval_date": approval.approval_date.isoformat(),
            })
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching approval history: {str(e)}")
