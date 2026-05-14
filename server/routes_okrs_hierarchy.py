"""
Hierarchy-Based OKR Routes
===========================

Implements REST API endpoints for strict hierarchy-based OKR creation, assignment,
validation, and approval workflow.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from datetime import datetime

from server.database import get_db
from server.models import (
    User, Objective, KeyResult, ProgressUpdate, ReviewCycle,
    Plant, Department, Team, TeamMember, ReportingRelationship,
)
from server.okr_hierarchy_workflow import OKRHierarchyWorkflow
from server.roles import allowed_objective_levels_for, normalize_role
from server.schemas import ObjectiveCreate, KeyResultCreate, ProgressUpdateCreate

router = APIRouter(prefix="/api/okrs/hierarchy", tags=["okrs-hierarchy"])


# ────────────────────────────────────────────────────────────────────────────
# VALIDATION ENDPOINTS
# ────────────────────────────────────────────────────────────────────────────

@router.post("/validate/can-create")
def validate_can_create(
    db: Session = Depends(get_db),
    user_id: str = "",
    okr_level: str = "",
    org_id: str = "",
):
    """
    Check if user can create an OKR at the specified level.
    Returns: {can_create: bool, reason: str, allowed_levels: [str]}
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"can_create": False, "reason": "User not found"}

    workflow = OKRHierarchyWorkflow(db)
    can_create, reason = workflow.can_create_okr_at_level(user, okr_level, org_id)

    allowed_levels = allowed_objective_levels_for(normalize_role(user.system_role))

    return {
        "can_create": can_create,
        "reason": reason,
        "user_role": user.system_role,
        "allowed_levels": allowed_levels,
        "requested_level": okr_level,
    }


@router.post("/validate/hierarchy-chain")
def validate_hierarchy_chain(
    db: Session = Depends(get_db),
    user_id: str = "",
    okr_level: str = "",
    parent_id: Optional[str] = None,
    plant_id: Optional[str] = None,
    department_id: Optional[str] = None,
    team_id: Optional[str] = None,
    org_id: str = "",
):
    """
    Validate that OKR creation follows proper hierarchy chain rules.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    parent_okr = None
    if parent_id:
        parent_okr = db.query(Objective).filter(Objective.id == parent_id).first()
        if not parent_okr:
            raise HTTPException(404, "Parent objective not found")

    workflow = OKRHierarchyWorkflow(db)
    valid, reason = workflow.validate_okr_hierarchy_chain(
        user,
        okr_level,
        parent_okr,
        plant_id,
        department_id,
        team_id,
    )

    return {
        "valid": valid,
        "reason": reason,
        "suggested_parent": None,
    }


@router.post("/validate/can-assign")
def validate_can_assign(
    db: Session = Depends(get_db),
    creator_id: str = "",
    assignee_id: str = "",
    okr_level: str = "",
    org_id: str = "",
):
    """
    Check if creator can assign an OKR to assignee at the specified level.
    """
    creator = db.query(User).filter(User.id == creator_id).first()
    if not creator:
        raise HTTPException(404, "Creator user not found")

    assignee = db.query(User).filter(User.id == assignee_id).first()
    if not assignee:
        raise HTTPException(404, "Assignee user not found")

    workflow = OKRHierarchyWorkflow(db)
    can_assign, reason = workflow.can_assign_okr_to_user(
        creator, assignee, okr_level, org_id
    )

    return {
        "can_assign": can_assign,
        "reason": reason,
        "creator_role": creator.system_role,
        "assignee_role": assignee.system_role,
    }


@router.post("/validate/can-approve")
def validate_can_approve(
    db: Session = Depends(get_db),
    approver_id: str = "",
    okr_id: str = "",
    org_id: str = "",
):
    """
    Check if user can approve an OKR for creation.
    """
    approver = db.query(User).filter(User.id == approver_id).first()
    if not approver:
        raise HTTPException(404, "Approver user not found")

    okr = db.query(Objective).filter(Objective.id == okr_id).first()
    if not okr:
        raise HTTPException(404, "Objective not found")

    workflow = OKRHierarchyWorkflow(db)
    can_approve, reason = workflow.can_approve_okr(approver, okr, org_id)

    approval_chain = workflow.get_approval_chain_for_okr(okr, org_id)

    return {
        "can_approve": can_approve,
        "reason": reason,
        "approver_role": approver.system_role,
        "okr_level": okr.level,
        "approval_chain": approval_chain,
    }


# ────────────────────────────────────────────────────────────────────────────
# OKR CREATION ENDPOINTS
# ────────────────────────────────────────────────────────────────────────────

@router.post("/create")
def create_okr_hierarchical(
    req: ObjectiveCreate,
    db: Session = Depends(get_db),
    org_id: str = "",
    user_id: str = "",
):
    """
    Create an OKR with hierarchy-based validation and workflow.
    
    Request body:
    {
        "title": "Increase Production Efficiency",
        "description": "Reduce cycle time by 20%",
        "level": "PLANT",  # ORGANIZATION, PLANT, DEPARTMENT, TEAM, INDIVIDUAL
        "owner_id": "user123",  # Who will own this OKR
        "parent_id": "okr456",  # Optional parent for cascading
        "plant_id": "plant123",
        "department_id": "dept123",
        "team_id": "team123",
        "cycle_id": "cycle123"
    }
    """
    creator = db.query(User).filter(User.id == user_id).first()
    if not creator:
        raise HTTPException(404, "Creator user not found")

    workflow = OKRHierarchyWorkflow(db)

    # Validate creator can create at this level
    can_create, reason = workflow.can_create_okr_at_level(
        creator, req.level.upper(), org_id
    )
    if not can_create:
        raise HTTPException(403, reason)

    # Get parent OKR if specified
    parent_okr = None
    if req.parent_id:
        parent_okr = db.query(Objective).filter(
            Objective.id == req.parent_id
        ).first()
        if not parent_okr:
            raise HTTPException(404, "Parent objective not found")

    # Validate hierarchy chain
    valid, reason = workflow.validate_okr_hierarchy_chain(
        creator,
        req.level.upper(),
        parent_okr,
        req.plant_id,
        req.department_id,
        req.team_id,
    )
    if not valid:
        raise HTTPException(400, reason)

    # Validate owner/assignee if different from creator
    owner_id = req.owner_id or user_id
    if owner_id != user_id:
        owner = db.query(User).filter(User.id == owner_id).first()
        if not owner:
            raise HTTPException(404, "Owner user not found")

        can_assign, reason = workflow.can_assign_okr_to_user(
            creator, owner, req.level.upper(), org_id
        )
        if not can_assign:
            raise HTTPException(403, reason)

    # Create the objective
    obj = Objective(
        org_id=org_id,
        owner_id=owner_id,
        assigned_by_id=user_id if owner_id != user_id else None,
        parent_id=req.parent_id,
        cycle_id=req.cycle_id,
        title=req.title,
        description=req.description,
        level=req.level.upper(),
        plant_id=req.plant_id,
        department_id=req.department_id,
        team_id=req.team_id,
        # New workflow fields
        creation_approval_status="PENDING",
        visibility_scope="STANDARD",
        allows_cascade=True,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)

    # Get approval chain for this OKR
    approval_chain = workflow.get_approval_chain_for_okr(obj, org_id)

    return {
        "id": obj.id,
        "title": obj.title,
        "level": obj.level,
        "owner_id": obj.owner_id,
        "status": obj.status,
        "creation_approval_status": obj.creation_approval_status,
        "approval_chain": approval_chain,
        "message": f"OKR created successfully. Pending approval from: {', '.join([a['role'] for a in approval_chain[:1]])}"
    }


# ────────────────────────────────────────────────────────────────────────────
# OKR APPROVAL ENDPOINTS
# ────────────────────────────────────────────────────────────────────────────

@router.post("/{okr_id}/approve")
def approve_okr_creation(
    okr_id: str,
    approval_notes: str = "",
    db: Session = Depends(get_db),
    approver_id: str = "",
    org_id: str = "",
):
    """
    Approve an OKR for creation by someone in the approval chain.
    """
    okr = db.query(Objective).filter(Objective.id == okr_id).first()
    if not okr:
        raise HTTPException(404, "Objective not found")

    approver = db.query(User).filter(User.id == approver_id).first()
    if not approver:
        raise HTTPException(404, "Approver user not found")

    workflow = OKRHierarchyWorkflow(db)
    can_approve, reason = workflow.can_approve_okr(approver, okr, org_id)
    if not can_approve:
        raise HTTPException(403, reason)

    # Update OKR approval status
    okr.creation_approval_status = "APPROVED"
    okr.creation_approved_by_id = approver_id
    okr.creation_approved_at = datetime.utcnow()
    okr.creation_approval_notes = approval_notes
    db.commit()

    return {
        "id": okr.id,
        "title": okr.title,
        "creation_approval_status": okr.creation_approval_status,
        "approved_by": approver.name,
        "approved_at": okr.creation_approved_at.isoformat(),
        "message": "OKR approval completed successfully"
    }


@router.post("/{okr_id}/reject")
def reject_okr_creation(
    okr_id: str,
    rejection_reason: str,
    db: Session = Depends(get_db),
    rejector_id: str = "",
    org_id: str = "",
):
    """
    Reject an OKR creation and request revisions.
    """
    okr = db.query(Objective).filter(Objective.id == okr_id).first()
    if not okr:
        raise HTTPException(404, "Objective not found")

    rejector = db.query(User).filter(User.id == rejector_id).first()
    if not rejector:
        raise HTTPException(404, "Rejector user not found")

    workflow = OKRHierarchyWorkflow(db)
    can_approve, reason = workflow.can_approve_okr(rejector, okr, org_id)
    if not can_approve:
        raise HTTPException(403, reason)

    if not rejection_reason:
        raise HTTPException(400, "Rejection reason is required")

    # Update OKR status
    okr.creation_approval_status = "REVISION_REQUESTED"
    okr.creation_approval_notes = rejection_reason
    db.commit()

    return {
        "id": okr.id,
        "title": okr.title,
        "creation_approval_status": okr.creation_approval_status,
        "rejection_reason": rejection_reason,
        "message": "OKR creation rejected. Owner has been notified to revise."
    }


# ────────────────────────────────────────────────────────────────────────────
# OKR ASSIGNMENT ENDPOINTS
# ────────────────────────────────────────────────────────────────────────────

@router.get("/recipients")
def get_okr_recipients(
    db: Session = Depends(get_db),
    okr_level: str = "",
    org_id: str = "",
    plant_id: Optional[str] = None,
    department_id: Optional[str] = None,
    team_id: Optional[str] = None,
):
    """
    Get list of users who can receive OKR assignments at the specified level.
    """
    workflow = OKRHierarchyWorkflow(db)
    recipients = workflow.get_okr_recipients_in_hierarchy(
        org_id,
        okr_level,
        plant_id,
        department_id,
        team_id,
    )

    return {
        "level": okr_level,
        "recipients": [
            {
                "id": r.id,
                "name": r.name,
                "email": r.email,
                "role": r.system_role,
                "plant_id": r.plant_id,
                "department_id": r.department_id,
                "team_id": r.team_id,
            }
            for r in recipients
        ]
    }


@router.post("/{okr_id}/assign")
def assign_okr_to_user(
    okr_id: str,
    assignee_id: str,
    db: Session = Depends(get_db),
    assigner_id: str = "",
    org_id: str = "",
):
    """
    Assign an approved OKR to a user.
    """
    okr = db.query(Objective).filter(Objective.id == okr_id).first()
    if not okr:
        raise HTTPException(404, "Objective not found")

    assigner = db.query(User).filter(User.id == assigner_id).first()
    if not assigner:
        raise HTTPException(404, "Assigner user not found")

    assignee = db.query(User).filter(User.id == assignee_id).first()
    if not assignee:
        raise HTTPException(404, "Assignee user not found")

    # Only assign if OKR is approved
    if okr.creation_approval_status != "APPROVED":
        raise HTTPException(
            400,
            f"OKR must be APPROVED before assignment (current status: {okr.creation_approval_status})"
        )

    workflow = OKRHierarchyWorkflow(db)
    can_assign, reason = workflow.can_assign_okr_to_user(
        assigner, assignee, okr.level, org_id
    )
    if not can_assign:
        raise HTTPException(403, reason)

    # Update OKR owner
    okr.owner_id = assignee_id
    okr.assigned_by_id = assigner_id
    db.commit()

    return {
        "id": okr.id,
        "title": okr.title,
        "owner_id": okr.owner_id,
        "owner_name": assignee.name,
        "assigned_by": assigner.name,
        "message": f"OKR assigned to {assignee.name}"
    }


# ────────────────────────────────────────────────────────────────────────────
# VISIBILITY & ACCESS ENDPOINTS
# ────────────────────────────────────────────────────────────────────────────

@router.get("/visible")
def get_visible_okrs(
    db: Session = Depends(get_db),
    org_id: str = "",
    user_id: str = "",
):
    """
    Get all OKRs visible to the user based on hierarchy and permissions.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    workflow = OKRHierarchyWorkflow(db)
    visible_okrs = workflow.get_visible_okrs_for_user(user, org_id)

    return {
        "user_id": user_id,
        "user_role": user.system_role,
        "visible_okr_count": len(visible_okrs),
        "okrs": [
            {
                "id": o.id,
                "title": o.title,
                "level": o.level,
                "owner_name": db.query(User).filter(User.id == o.owner_id).first().name if o.owner_id else None,
                "status": o.status,
                "progress": o.progress,
            }
            for o in visible_okrs
        ]
    }


@router.post("/can-view/{okr_id}")
def check_can_view_okr(
    okr_id: str,
    db: Session = Depends(get_db),
    user_id: str = "",
):
    """
    Check if user can view a specific OKR.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    okr = db.query(Objective).filter(Objective.id == okr_id).first()
    if not okr:
        raise HTTPException(404, "Objective not found")

    workflow = OKRHierarchyWorkflow(db)
    can_view = workflow.can_view_okr(user, okr)

    return {
        "user_id": user_id,
        "okr_id": okr_id,
        "can_view": can_view,
    }


# ────────────────────────────────────────────────────────────────────────────
# APPROVAL CHAIN ENDPOINTS
# ────────────────────────────────────────────────────────────────────────────

@router.get("/{okr_id}/approval-chain")
def get_approval_chain(
    okr_id: str,
    db: Session = Depends(get_db),
    org_id: str = "",
):
    """
    Get the approval chain for an OKR showing who must approve it.
    """
    okr = db.query(Objective).filter(Objective.id == okr_id).first()
    if not okr:
        raise HTTPException(404, "Objective not found")

    workflow = OKRHierarchyWorkflow(db)
    chain = workflow.get_approval_chain_for_okr(okr, org_id)

    return {
        "okr_id": okr_id,
        "okr_level": okr.level,
        "approval_chain": chain,
        "total_approvers": len(chain),
    }


@router.get("/{okr_id}/suggested-parent")
def get_suggested_parent(
    okr_id: str,
    db: Session = Depends(get_db),
):
    """
    Get suggested parent OKR for alignment cascading.
    """
    okr = db.query(Objective).filter(Objective.id == okr_id).first()
    if not okr:
        raise HTTPException(404, "Objective not found")

    workflow = OKRHierarchyWorkflow(db)
    parent = workflow.get_suggested_parent_okr(
        okr.level,
        okr.plant_id,
        okr.department_id,
        okr.team_id,
        okr.org_id,
    )

    if parent:
        return {
            "suggested_parent_id": parent.id,
            "suggested_parent_title": parent.title,
            "suggested_parent_level": parent.level,
        }
    return {"suggested_parent_id": None}


# ────────────────────────────────────────────────────────────────────────────
# PROGRESS VALIDATION ENDPOINTS
# ────────────────────────────────────────────────────────────────────────────

@router.post("/progress/{progress_id}/validate")
def validate_progress(
    progress_id: str,
    validation_notes: str = "",
    db: Session = Depends(get_db),
    validator_id: str = "",
    org_id: str = "",
):
    """
    Validate progress update for an OKR (flows upward in hierarchy).
    """
    progress = db.query(ProgressUpdate).filter(
        ProgressUpdate.id == progress_id
    ).first()
    if not progress:
        raise HTTPException(404, "Progress update not found")

    validator = db.query(User).filter(User.id == validator_id).first()
    if not validator:
        raise HTTPException(404, "Validator user not found")

    # Get the related objective
    kr = db.query(KeyResult).filter(
        KeyResult.id == progress.key_result_id
    ).first()
    if not kr:
        raise HTTPException(404, "Key result not found")

    okr = db.query(Objective).filter(
        Objective.id == kr.objective_id
    ).first()
    if not okr:
        raise HTTPException(404, "Objective not found")

    submitter = db.query(User).filter(
        User.id == progress.submitted_by_id
    ).first()

    workflow = OKRHierarchyWorkflow(db)
    can_validate, reason = workflow.can_validate_progress(
        validator, okr, submitter
    )
    if not can_validate:
        raise HTTPException(403, reason)

    # Update progress
    progress.status = "APPROVED"
    progress.validated_by_id = validator_id
    progress.validated_at = datetime.utcnow()
    progress.validation_notes = validation_notes
    progress.validation_level = validator.system_role

    # Update key result value
    kr.current_value = progress.new_value
    kr.status = "IN_PROGRESS"

    db.commit()

    return {
        "progress_id": progress_id,
        "status": progress.status,
        "validated_by": validator.name,
        "message": "Progress validated successfully"
    }
