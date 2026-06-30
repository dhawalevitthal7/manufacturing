"""
Progress Submission & Validation Routes
=========================================

Handles employee progress submission, manager review/approval, and cascade propagation.
Adapted from currentreview to support:
- Employee progress submission (employee_value + notes)
- Manager review with optional override (manager_value + notes)
- Approval workflows with role-based validation chain
- AI coaching integration (optional)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
import logging
import uuid

logger = logging.getLogger(__name__)

from server.database import get_db
from server.models import (
    ProgressSubmission, ProgressUpdate, KeyResult, Objective, User, ReviewCycle,
    Team, Department, Plant, ReportingRelationship, TeamMember, UserPermissionProfile,
)
from server.schemas import (
    ProgressUpdateCreate, ProgressValidation, 
    ProgressSubmissionCreate, ProgressSubmissionReview, ProgressSubmissionResponse
)
from server.okr_cascade_service import (
    OKRCascadeService, calculate_kr_progress, score_to_rating
)
from server.okr_hierarchy_workflow import OKRHierarchyWorkflow
from server.services.okr_progress_permissions import can_submit_okr_progress
from server.services.okr_visibility_service import (
    apply_okr_visibility_filter,
    apply_optional_scope_narrowing,
    get_user_okr_scope,
)
from server.services.dual_approval_service import (
    SUBJECT_PROGRESS_SUBMISSION,
    STEP_LINE,
    STEP_FUNCTIONAL,
    DualApprovalError,
    build_chain,
    chain_status,
    approve_current_step_for_subject,
    reject_current_step_for_subject,
    pending_subject_ids_for_approver,
    current_step,
)
from server.roles import FUNCTIONAL_APPROVER_ROLES, normalize_role

router = APIRouter(prefix="/api/progress", tags=["progress"])


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _team_scope_ids_for_validator(db: Session, user: User) -> list[str]:
    """Team IDs this user may validate progress for (same team, roster lead, or Team.lead_id)."""
    ids: list[str] = []
    if user.team_id:
        ids.append(user.team_id)
    for (tid,) in (
        db.query(TeamMember.team_id)
        .filter(
            TeamMember.user_id == user.id,
            TeamMember.is_active == True,
            TeamMember.is_team_lead == True,
        )
        .all()
    ):
        if tid not in ids:
            ids.append(tid)
    for (tid,) in db.query(Team.id).filter(Team.lead_id == user.id).all():
        if tid not in ids:
            ids.append(tid)
    return ids


def _primary_approver_role_for_level(level: str) -> str:
    """Who must approve progress at each OKR level (one step up the cascade)."""
    return {
        "INDIVIDUAL": "MANAGER",
        "TEAM": "DEPT_HEAD",
        "DEPARTMENT": "PLANT_HEAD",
        "PLANT": "VP_OPERATIONS",
        "REGION": "CEO",
        "ORGANIZATION": "CEO",
    }.get((level or "").upper(), "MANAGER")


def _user_covers_region(db: Session, user: User, region_id: str) -> bool:
    if not region_id or not user:
        return False
    if user.org_node_id == region_id:
        return True
    profile = (
        db.query(UserPermissionProfile)
        .filter(UserPermissionProfile.user_id == user.id)
        .first()
    )
    if profile and profile.scoped_region_id == region_id:
        return True
    return False


def _user_can_validate_progress_submission(
    db: Session,
    reviewer: User,
    objective: Objective,
    submitter_id: str,
) -> bool:
    """
    Hierarchical progress validation:
    - Individual/Team → Manager / Dept Head
    - Department → Plant Head (same plant)
    - Plant → Regional Head (VP, same region)
    - Region → CEO
    """
    if not reviewer or not objective:
        return False
    if submitter_id and submitter_id != "system" and submitter_id == reviewer.id:
        return False

    level = (objective.level or "").upper()
    role = reviewer.system_role

    if role == "SUPER_ADMIN":
        return True

    # Executive levels: CEO validates region/org progress
    if level in ("REGION", "ORGANIZATION"):
        submitter = (
            db.query(User).filter(User.id == submitter_id).first()
            if submitter_id and submitter_id != "system"
            else None
        )
        if level == "REGION" and submitter and submitter.system_role == "REGIONAL_HEAD":
            if role == "CRO":
                return reviewer.org_id == objective.org_id
            if role in ("CEO", "SUPER_ADMIN"):
                return reviewer.org_id == objective.org_id
            return False
        if role in ("CEO", "CFO", "CMO", "CTO"):
            return reviewer.org_id == objective.org_id
        return False

    # Plant-level OKR progress from Plant Head → COO; others unchanged
    if level == "PLANT":
        submitter = (
            db.query(User).filter(User.id == submitter_id).first()
            if submitter_id and submitter_id != "system"
            else None
        )
        if submitter and submitter.system_role == "PLANT_HEAD":
            if role == "COO":
                return reviewer.org_id == objective.org_id
            if role in ("CEO", "SUPER_ADMIN"):
                return reviewer.org_id == objective.org_id
            return False
        if role in ("VP_OPERATIONS", "VP_MANUFACTURING", "REGIONAL_HEAD"):
            if objective.region_id:
                return _user_covers_region(db, reviewer, objective.region_id)
            return reviewer.org_id == objective.org_id
        if role == "PLANT_HEAD" and objective.plant_id and reviewer.plant_id == objective.plant_id:
            return True
        if role == "CEO":
            return reviewer.org_id == objective.org_id
        return False

    # Department-level → plant head of that plant
    if level == "DEPARTMENT":
        if role == "PLANT_HEAD" and objective.plant_id and reviewer.plant_id == objective.plant_id:
            return True
        if role in ("VP_OPERATIONS", "VP_MANUFACTURING", "CEO"):
            if objective.region_id and role in ("VP_OPERATIONS", "VP_MANUFACTURING"):
                return _user_covers_region(db, reviewer, objective.region_id)
            return role == "CEO" and reviewer.org_id == objective.org_id
        return False

    # Team / individual: use workflow (manager, dept head, plant head in chain)
    if submitter_id and submitter_id != "system":
        submitter = db.query(User).filter(User.id == submitter_id).first()
        if submitter:
            wf = OKRHierarchyWorkflow(db)
            ok_align, _ = wf.can_validate_progress_including_functional_alignment(
                reviewer, objective, submitter
            )
            if ok_align:
                return True

    tid = objective.team_id
    if not tid:
        return False

    if reviewer.system_role == "MANAGER" and reviewer.team_id == tid:
        return True

    if reviewer.system_role in ("TEAM_LEAD", "SUPERVISOR") and reviewer.team_id == tid:
        return True

    tm = (
        db.query(TeamMember)
        .filter(
            TeamMember.team_id == tid,
            TeamMember.user_id == reviewer.id,
            TeamMember.is_active == True,
            TeamMember.is_team_lead == True,
        )
        .first()
    )
    if tm:
        return True

    team = db.query(Team).filter(Team.id == tid).first()
    if team and team.lead_id == reviewer.id:
        return True

    return False


def _user_can_review_progress_submission(
    db: Session,
    reviewer: User,
    submission: ProgressSubmission,
    objective: Objective,
) -> bool:
    """
    Who may approve/reject a ProgressSubmission.

    LINE step: assigned line approver (team lead) OR any manager/dept head in the
    submitter's hierarchy chain (same team/dept/plant rules).
    FUNCTIONAL step: only the assigned functional-head approver on that step.
    """
    step = current_step(db, SUBJECT_PROGRESS_SUBMISSION, submission.id)
    if step:
        if step.approver_id and step.approver_id == reviewer.id:
            return True
        if step.approval_type == STEP_LINE:
            return _user_can_validate_progress_submission(
                db, reviewer, objective, submission.submitted_by_id or ""
            )
        return False
    return _user_can_validate_progress_submission(
        db, reviewer, objective, submission.submitted_by_id or ""
    )


def _pending_item_from_update(update: ProgressUpdate, db: Session) -> Optional[dict]:
    kr = db.query(KeyResult).filter(KeyResult.id == update.key_result_id).first()
    if not kr:
        return None
    obj = db.query(Objective).filter(Objective.id == kr.objective_id).first()
    if not obj:
        return None
    submitter = db.query(User).filter(User.id == update.submitted_by_id).first()
    return {
        "id": update.id,
        "key_result_id": update.key_result_id,
        "key_result_title": kr.title,
        "objective_id": obj.id,
        "objective_title": obj.title,
        "objective_level": obj.level,
        "submitted_by": submitter.name if submitter else None,
        "submitted_by_id": update.submitted_by_id,
        "previous_value": update.previous_value,
        "new_value": update.new_value,
        "notes": update.notes,
        "blockers": update.blockers,
        "status": update.status,
        "created_at": update.created_at.isoformat() if update.created_at else None,
        "source": "legacy_update",
    }


def _pending_item_from_submission(submission: ProgressSubmission, db: Session) -> Optional[dict]:
    if not submission.key_result_id:
        return None
    kr = db.query(KeyResult).filter(KeyResult.id == submission.key_result_id).first()
    if not kr:
        return None
    obj = db.query(Objective).filter(Objective.id == kr.objective_id).first()
    if not obj:
        return None
    submitter = db.query(User).filter(User.id == submission.submitted_by_id).first()
    return {
        "id": submission.id,
        "key_result_id": submission.key_result_id,
        "key_result_title": kr.title,
        "objective_id": obj.id,
        "objective_title": obj.title,
        "objective_level": obj.level,
        "submitted_by": submitter.name if submitter else None,
        "submitted_by_id": submission.submitted_by_id,
        "previous_value": kr.current_value,
        "new_value": submission.employee_value,
        "notes": submission.employee_note,
        "blockers": None,
        "status": submission.status,
        "created_at": submission.created_at.isoformat() if submission.created_at else None,
        "source": "submission",
    }


def _get_submission_dict(submission: ProgressSubmission, db: Session) -> dict:
    """Serialize a progress submission to dict."""
    submitter = db.query(User).filter(User.id == submission.submitted_by_id).first()
    reviewer = db.query(User).filter(User.id == submission.reviewed_by_id).first() if submission.reviewed_by_id else None
    
    payload = {
        "id": submission.id,
        "key_result_id": submission.key_result_id,
        "submitted_by": submitter.name if submitter else None,
        "submitted_by_id": submission.submitted_by_id,
        "reviewed_by": reviewer.name if reviewer else None,
        "reviewed_by_id": submission.reviewed_by_id,
        "employee_value": submission.employee_value,
        "employee_note": submission.employee_note,
        "manager_value": submission.manager_value,
        "manager_note": submission.manager_note,
        "status": submission.status,
        "validation_level": submission.validation_level,
        "next_approver_role": submission.next_approver_role,
        "created_at": submission.created_at.isoformat() if submission.created_at else None,
        "reviewed_at": submission.reviewed_at.isoformat() if submission.reviewed_at else None,
    }
    # ── Normalization fields ──
    if submission.key_result_id:
        kr = db.query(KeyResult).filter(KeyResult.id == submission.key_result_id).first()
        if kr:
            payload["normalized_progress"] = getattr(kr, "normalized_progress", None) or 0.0
            payload["kpi_behavior"] = getattr(kr, "kpi_behavior", "HIGHER_IS_BETTER")
            payload["actual_value"] = getattr(kr, "last_actual_value", None)
            payload["target_value"] = kr.target_value
            payload["unit"] = kr.unit
            # Compute formula_used on-the-fly for display
            try:
                from server.services.progress_normalization_service import calculate_progress
                result = calculate_progress(kr, kr.current_value or 0.0)
                payload["formula_used"] = result.formula_used
            except Exception:
                payload["formula_used"] = None
    payload["approval_chain_status"] = chain_status(
        db, SUBJECT_PROGRESS_SUBMISSION, submission.id
    )
    return payload


def _determine_next_approver(
    objective: Objective, 
    reviewer_role: str,
    db: Session
) -> tuple[str, str]:
    """
    Determine the next approver in the chain based on OKR level and reviewer role.
    Returns (next_approver_role, next_approver_id or empty string)
    
    Chain: EMPLOYEE → MANAGER → DEPT_HEAD → PLANT_HEAD → CEO
    """
    if objective.level == "INDIVIDUAL":
        if reviewer_role == "MANAGER":
            return ("DEPT_HEAD", "")
        elif reviewer_role == "DEPT_HEAD":
            return ("PLANT_HEAD", "")
        elif reviewer_role == "PLANT_HEAD":
            return ("CEO", "")
    
    elif objective.level == "TEAM":
        if reviewer_role == "MANAGER":
            return ("DEPT_HEAD", "")
        elif reviewer_role == "DEPT_HEAD":
            return ("PLANT_HEAD", "")
        elif reviewer_role == "PLANT_HEAD":
            return ("CEO", "")
    
    elif objective.level == "DEPARTMENT":
        if reviewer_role == "DEPT_HEAD":
            return ("PLANT_HEAD", "")
        elif reviewer_role == "PLANT_HEAD":
            return ("CEO", "")
    
    elif objective.level == "PLANT":
        if reviewer_role == "PLANT_HEAD":
            return ("CEO", "")
    
    return ("", "")  # No more approvers


# ══════════════════════════════════════════════════════════════════════════════
# NEW PROGRESS SUBMISSION WORKFLOW
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/submissions", response_model=ProgressSubmissionResponse, status_code=201)
def submit_progress(
    req: ProgressSubmissionCreate,
    db: Session = Depends(get_db),
    org_id: str = "",
    user_id: str = "",
):
    """
    Employee submits progress for a key result.
    Creates a ProgressSubmission record with PENDING status.
    Manager will review and approve/override.
    """
    # Verify KR exists
    kr = db.query(KeyResult).filter(KeyResult.id == req.key_result_id).first()
    if not kr:
        raise HTTPException(status_code=404, detail="Key Result not found")
    
    # Get objective
    objective = db.query(Objective).filter(Objective.id == kr.objective_id).first()
    if not objective:
        raise HTTPException(status_code=404, detail="Objective not found")
        
    # Check if cycle is frozen
    if objective.cycle_id:
        from server.models import Cycle
        cycle = db.query(Cycle).filter(Cycle.id == objective.cycle_id).first()
        if cycle and cycle.status in ("FROZEN", "CLOSED"):
            raise HTTPException(
                status_code=409, 
                detail=f"Cannot submit progress: The cycle '{cycle.name}' is currently {cycle.status}."
            )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    can_submit, submit_reason = can_submit_okr_progress(user, objective, db)
    if not can_submit:
        raise HTTPException(status_code=403, detail=submit_reason)
    
    approver_role = _primary_approver_role_for_level(objective.level)

    # Create progress submission
    submission = ProgressSubmission(
        id=str(uuid.uuid4()),
        key_result_id=req.key_result_id,
        objective_id=objective.id,
        submitted_by_id=user_id,
        employee_value=req.employee_value,
        employee_note=req.employee_note,
        status="PENDING",
        validation_level=approver_role,
        next_approver_role=approver_role,
    )
    
    db.add(submission)
    db.flush()
    try:
        build_chain(db, org_id, SUBJECT_PROGRESS_SUBMISSION, submission.id, user_id)
    except DualApprovalError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(submission)
    
    return _get_submission_dict(submission, db)


@router.get("/submissions/pending", response_model=List[ProgressSubmissionResponse])
def get_pending_submissions(
    db: Session = Depends(get_db),
    org_id: str = "",
    user_id: str = "",
    team_id: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    stage: Optional[str] = Query(None, description="line | functional"),
):
    """
    Pending progress submissions the current user is allowed to validate
    (managers, team leads / roster leads, department and plant heads, executives).
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    approval_type = None
    if stage:
        st = stage.strip().lower()
        if st == "line":
            approval_type = STEP_LINE
        elif st == "functional":
            approval_type = STEP_FUNCTIONAL
        else:
            raise HTTPException(status_code=400, detail="stage must be line or functional")

    # Items where this user is the current dual-approval step assignee (CMO, CFO, etc.)
    direct_ids = set(
        pending_subject_ids_for_approver(
            db,
            org_id,
            user_id,
            SUBJECT_PROGRESS_SUBMISSION,
            approval_type=approval_type,
        )
    )

    user_role = normalize_role(user.system_role)
    is_functional_head = user_role in FUNCTIONAL_APPROVER_ROLES
    if approval_type == STEP_FUNCTIONAL or (is_functional_head and approval_type is None):
        if not direct_ids:
            return []
        submissions = (
            db.query(ProgressSubmission)
            .filter(ProgressSubmission.id.in_(list(direct_ids)))
            .order_by(ProgressSubmission.created_at.desc())
            .all()
        )
        return [_get_submission_dict(s, db) for s in submissions]

    visible_ids = set(direct_ids)

    query = (
        db.query(ProgressSubmission)
        .filter(
            ProgressSubmission.status == "PENDING",
            ProgressSubmission.key_result_id.isnot(None),
        )
        .join(KeyResult, KeyResult.id == ProgressSubmission.key_result_id)
        .join(Objective, Objective.id == KeyResult.objective_id)
        .filter(Objective.org_id == org_id)
    )

    if team_id:
        query = query.filter(Objective.team_id == team_id)
    elif department_id:
        query = query.filter(Objective.department_id == department_id)
    else:
        if user.system_role in ("CEO", "VP_OPERATIONS"):
            pass
        else:
            scope_parts = []
            if user.system_role == "PLANT_HEAD" and user.plant_id:
                scope_parts.append(Objective.plant_id == user.plant_id)
            if user.system_role == "DEPT_HEAD" and user.department_id:
                scope_parts.append(Objective.department_id == user.department_id)

            team_scope = set(_team_scope_ids_for_validator(db, user))
            if user.system_role == "MANAGER" and user.team_id:
                team_scope.add(user.team_id)
            if user.system_role in ("TEAM_LEAD", "SUPERVISOR") and user.team_id:
                team_scope.add(user.team_id)
            if team_scope:
                scope_parts.append(Objective.team_id.in_(list(team_scope)))

            if scope_parts:
                query = query.filter(or_(*scope_parts))
            elif not visible_ids:
                return []

    submissions = query.order_by(ProgressSubmission.created_at.desc()).all()

    for s in submissions:
        if s.id in visible_ids:
            continue
        kr = db.query(KeyResult).filter(KeyResult.id == s.key_result_id).first()
        if not kr:
            continue
        obj = db.query(Objective).filter(Objective.id == kr.objective_id).first()
        if not obj:
            continue
        if not _user_can_review_progress_submission(db, user, s, obj):
            continue
        visible_ids.add(s.id)

    if not visible_ids:
        return []

    ordered = (
        db.query(ProgressSubmission)
        .filter(ProgressSubmission.id.in_(list(visible_ids)))
        .order_by(ProgressSubmission.created_at.desc())
        .all()
    )
    return [_get_submission_dict(s, db) for s in ordered]


@router.post("/submissions/{submission_id}/review", response_model=ProgressSubmissionResponse)
def review_progress_submission(
    submission_id: str,
    req: ProgressSubmissionReview,
    db: Session = Depends(get_db),
    org_id: str = "",
    user_id: str = "",
):
    """
    Manager reviews and approves/rejects/overrides a progress submission.
    
    After approval:
    1. Updates KR current_value
    2. Recalculates objective progress using weighted formula
    3. Cascades progress upward through parent chain (bottom-up approach)
    4. Each cascaded parent's progress is saved after approval at that stage
    
    Actions:
    - "approve": Accept employee's submitted value
    - "override": Use manager's value instead
    - "reject": Reject and ask for revision
    - "revision_requested": Request employee to revise
    """
    # Get submission
    submission = db.query(ProgressSubmission).filter(
        ProgressSubmission.id == submission_id
    ).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Progress submission not found")
    
    if submission.status != "PENDING":
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot review submission with status {submission.status}"
        )

    reviewer_user = db.query(User).filter(User.id == user_id).first()
    if not reviewer_user:
        raise HTTPException(status_code=404, detail="Reviewer not found")

    objective_for_auth: Optional[Objective] = None
    if submission.key_result_id:
        kr_auth = db.query(KeyResult).filter(KeyResult.id == submission.key_result_id).first()
        if kr_auth:
            objective_for_auth = db.query(Objective).filter(Objective.id == kr_auth.objective_id).first()
    elif submission.objective_id:
        objective_for_auth = db.query(Objective).filter(Objective.id == submission.objective_id).first()

    if submission.key_result_id and objective_for_auth is None:
        raise HTTPException(status_code=400, detail="Key result not found for this submission")

    if not objective_for_auth:
        raise HTTPException(status_code=400, detail="Objective not found for this submission")

    if not _user_can_review_progress_submission(
        db, reviewer_user, submission, objective_for_auth
    ):
        step = current_step(db, SUBJECT_PROGRESS_SUBMISSION, submission_id)
        if step and step.approval_type == STEP_FUNCTIONAL:
            assigned = db.query(User).filter(User.id == step.approver_id).first()
            who = assigned.email if assigned else "the assigned functional approver"
            raise HTTPException(
                status_code=403,
                detail=f"Not authorized: awaiting functional approval from {who}",
            )
        raise HTTPException(status_code=403, detail="Not authorized to review this submission")

    step = current_step(db, SUBJECT_PROGRESS_SUBMISSION, submission_id)
    line_delegate = bool(
        step
        and step.approval_type == STEP_LINE
        and step.approver_id
        and step.approver_id != user_id
        and _user_can_validate_progress_submission(
            db, reviewer_user, objective_for_auth, submission.submitted_by_id or ""
        )
    )
    
    # Validate action
    action = req.action.lower()
    if action not in ["approve", "override", "reject", "revision_requested"]:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    # Override requires manager_value
    if action == "override" and req.manager_value is None:
        raise HTTPException(
            status_code=400,
            detail="manager_value is required when action is 'override'"
        )

    submission.manager_note = req.manager_note
    if action == "override":
        submission.manager_value = req.manager_value

    manager_value_for_finalize = (
        req.manager_value if action == "override" else None
    )

    try:
        if action in ("approve", "override"):
            result = approve_current_step_for_subject(
                db,
                SUBJECT_PROGRESS_SUBMISSION,
                submission_id,
                user_id,
                req.manager_note or "",
                manager_value=manager_value_for_finalize,
                allow_line_delegate=line_delegate,
            )
            if not result.get("finalized"):
                submission.status = "PENDING"
        elif action in ("reject", "revision_requested"):
            reason = req.manager_note or "Rejected"
            reject_current_step_for_subject(
                db,
                SUBJECT_PROGRESS_SUBMISSION,
                submission_id,
                user_id,
                reason,
                allow_line_delegate=line_delegate,
            )
            if action == "revision_requested":
                submission.status = "REVISION_REQUESTED"
    except DualApprovalError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    db.commit()
    db.refresh(submission)

    result_payload = _get_submission_dict(submission, db)
    if submission.status == "APPROVED" and submission.key_result_id:
        kr_out = db.query(KeyResult).filter(KeyResult.id == submission.key_result_id).first()
        obj_out = (
            db.query(Objective).filter(Objective.id == kr_out.objective_id).first()
            if kr_out
            else None
        )
        if kr_out:
            result_payload["kr_current_value"] = kr_out.current_value
            result_payload["kr_progress_pct"] = round(calculate_kr_progress(kr_out), 1)
        if obj_out:
            result_payload["objective_progress"] = obj_out.progress
    return result_payload


def _recalc_weighted_progress(objective: Objective, db: Session):
    """
    Recalculate objective progress.

    Phase 4.4 / 4.3: when this row has rollup children (``parent_id`` or
    ``functional_parent_obj_id`` edges into this id), use the same aggregation as
    ``OKRCascadeService``; otherwise from key results only.
    """
    OKRCascadeService(db).refresh_objective_progress_for_session(objective.id)
    db.flush()


def _get_next_approver_in_chain(objective_level: str, approver_role: str) -> tuple[str, str]:
    """
    Determine the next approver in the chain based on OKR level and current approver role.
    
    Cascade chain: EMPLOYEE → MANAGER → DEPT_HEAD → PLANT_HEAD → CEO
    
    Returns (next_approver_role, next_validation_level)
    """
    chain_map = {
        "INDIVIDUAL": {
            "MANAGER": ("DEPT_HEAD", "DEPARTMENT_HEAD"),
            "DEPT_HEAD": ("PLANT_HEAD", "PLANT_HEAD"),
            "PLANT_HEAD": ("VP_OPERATIONS", "VP_OPERATIONS"),
        },
        "TEAM": {
            "MANAGER": ("DEPT_HEAD", "DEPARTMENT_HEAD"),
            "DEPT_HEAD": ("PLANT_HEAD", "PLANT_HEAD"),
            "PLANT_HEAD": ("VP_OPERATIONS", "VP_OPERATIONS"),
        },
        "DEPARTMENT": {
            "DEPT_HEAD": ("PLANT_HEAD", "PLANT_HEAD"),
            "PLANT_HEAD": ("VP_OPERATIONS", "VP_OPERATIONS"),
        },
        "PLANT": {
            "PLANT_HEAD": ("VP_OPERATIONS", "VP_OPERATIONS"),
            "VP_OPERATIONS": ("CEO", "CEO"),
            "VP_MANUFACTURING": ("CEO", "CEO"),
            "REGIONAL_HEAD": ("CEO", "CEO"),
        },
        "REGION": {
            "VP_OPERATIONS": ("CEO", "CEO"),
            "VP_MANUFACTURING": ("CEO", "CEO"),
            "REGIONAL_HEAD": ("CEO", "CEO"),
        },
        "ORGANIZATION": {
            "CEO": ("CEO", "CEO"),
        },
    }
    
    level_chain = chain_map.get(objective_level, {})
    next_info = level_chain.get(approver_role, ("", ""))
    return next_info


def _find_user_for_role(db: Session, role: str, objective: Objective) -> Optional[User]:
    """
    Find the user with the given role who should approve at the next level.
    Scopes the search based on the objective's hierarchy placement.
    """
    query = db.query(User).filter(User.system_role == role)
    
    # Scope based on objective level
    if objective.level == "INDIVIDUAL" and objective.team_id:
        # Find MANAGER of this team
        query = query.filter(User.team_id == objective.team_id)
    elif objective.level == "TEAM" and objective.department_id:
        # Find DEPT_HEAD of this department
        query = query.filter(User.department_id == objective.department_id)
    elif objective.level == "DEPARTMENT" and objective.plant_id:
        # Find PLANT_HEAD of this plant
        query = query.filter(User.plant_id == objective.plant_id)
    elif objective.level == "PLANT":
        # Find CEO (org-level)
        query = query.filter(User.org_id == objective.org_id)
    
    return query.first()


def _auto_create_parent_submission(
    child_objective: Objective,
    parent_objective: Objective,
    approver_role: str,
    db: Session,
) -> Optional[ProgressSubmission]:
    """
    After child objective is approved, auto-create a submission for parent objective
    using the calculated progress from cascading children.

    Uses the parent's first key result as anchor (SQLite requires key_result_id NOT NULL).
    """
    if not approver_role:
        return None

    parent_kr = (
        db.query(KeyResult)
        .filter(KeyResult.objective_id == parent_objective.id)
        .order_by(KeyResult.created_at)
        .first()
    )
    if not parent_kr:
        return None

    nested = db.begin_nested()
    try:
        _recalc_weighted_progress(parent_objective, db)

        parent_progress = float(parent_objective.progress or 0.0)
        if parent_kr.target_value and parent_kr.target_value > 0:
            employee_value = (parent_progress / 100.0) * parent_kr.target_value
        else:
            employee_value = parent_progress

        submission = ProgressSubmission(
            id=str(uuid.uuid4()),
            key_result_id=parent_kr.id,
            objective_id=parent_objective.id,
            submitted_by_id="system",
            employee_value=employee_value,
            employee_note=f"Auto-cascaded from child: {child_objective.title}",
            status="PENDING",
            validation_level=approver_role,
            next_approver_role=approver_role,
            created_at=datetime.utcnow(),
        )

        db.add(submission)
        db.flush()
        nested.commit()
        return submission
    except Exception as e:
        nested.rollback()
        logger.warning("Error creating parent submission: %s", e)
        return None


def _propagate_approval_upward(
    objective: Objective,
    db: Session,
    reviewer_role: str,
) -> Dict[str, Any]:
    """
    After an objective is approved, cascade approval upward through parent chain.

    Phase 4.4: also walks the dotted-line ``functional_parent_obj_id`` branch (when not
    already visited on the solid chain), mirroring ``OKRCascadeService.propagate_progress_upward``.
    """
    cascade_chain = []
    visited = {objective.id}

    def step_solid_chain(current_obj: Objective) -> None:
        while current_obj.parent_id and current_obj.parent_id not in visited:
            parent = (
                db.query(Objective)
                .filter(Objective.id == current_obj.parent_id)
                .first()
            )
            if not parent:
                break
            visited.add(parent.id)
            next_role = _primary_approver_role_for_level(parent.level)
            _recalc_weighted_progress(parent, db)
            # Skip queue item when the same role already approved (e.g. CEO approves region → org rollup).
            if next_role and next_role != reviewer_role:
                parent_submission = _auto_create_parent_submission(
                    current_obj,
                    parent,
                    next_role,
                    db,
                )
                if parent_submission:
                    cascade_chain.append({
                        "objective_id": parent.id,
                        "objective_title": parent.title,
                        "objective_level": parent.level,
                        "progress": parent.progress,
                        "submission_id": parent_submission.id,
                        "next_approver_role": next_role,
                    })
            current_obj = parent

    step_solid_chain(objective)

    obj_r = db.query(Objective).filter(Objective.id == objective.id).first()
    if (
        obj_r
        and obj_r.functional_parent_obj_id
        and obj_r.functional_parent_obj_id not in visited
    ):
        fp = (
            db.query(Objective)
            .filter(Objective.id == obj_r.functional_parent_obj_id)
            .first()
        )
        if fp:
            visited.add(fp.id)
            next_role = _primary_approver_role_for_level(fp.level)
            _recalc_weighted_progress(fp, db)
            if next_role and next_role != reviewer_role:
                parent_submission = _auto_create_parent_submission(
                    obj_r,
                    fp,
                    next_role,
                    db,
                )
                if parent_submission:
                    cascade_chain.append({
                        "objective_id": fp.id,
                        "objective_title": fp.title,
                        "objective_level": fp.level,
                        "progress": fp.progress,
                        "submission_id": parent_submission.id,
                        "next_approver_role": next_role,
                    })
            step_solid_chain(fp)

    return {
        "success": True,
        "chain_length": len(cascade_chain),
        "chain": cascade_chain,
    }


@router.get("/submissions/{key_result_id}/history", response_model=List[ProgressSubmissionResponse])
def get_submission_history(
    key_result_id: str,
    db: Session = Depends(get_db),
    org_id: str = "",
):
    """Get all progress submissions for a specific key result."""
    kr = db.query(KeyResult).filter(KeyResult.id == key_result_id).first()
    if not kr:
        raise HTTPException(status_code=404, detail="Key Result not found")
    
    submissions = db.query(ProgressSubmission).filter(
        ProgressSubmission.key_result_id == key_result_id
    ).order_by(ProgressSubmission.created_at.desc()).all()
    
    return [_get_submission_dict(s, db) for s in submissions]


# ══════════════════════════════════════════════════════════════════════════════
# LEGACY PROGRESS UPDATE ENDPOINTS (Backward Compatibility)
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/submit")
def submit_progress_legacy(
    req: ProgressUpdateCreate,
    key_result_id: str,
    db: Session = Depends(get_db),
    org_id: str = "",
    user_id: str = "",
):
    """
    Legacy endpoint: Submit a progress update for a key result.
    Use /submissions endpoint instead for new implementations.
    """
    kr = db.query(KeyResult).filter(KeyResult.id == key_result_id).first()
    if not kr:
        raise HTTPException(status_code=404, detail="Key Result not found")
    
    objective = db.query(Objective).filter(Objective.id == kr.objective_id).first()
    if not objective:
        raise HTTPException(status_code=404, detail="Objective not found")
        
    # Check if cycle is frozen
    if objective.cycle_id:
        from server.models import Cycle
        cycle = db.query(Cycle).filter(Cycle.id == objective.cycle_id).first()
        if cycle and cycle.status in ("FROZEN", "CLOSED"):
            raise HTTPException(
                status_code=409, 
                detail=f"Cannot submit progress: The cycle '{cycle.name}' is currently {cycle.status}."
            )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    can_submit, submit_reason = can_submit_okr_progress(user, objective, db)
    if not can_submit:
        raise HTTPException(status_code=403, detail=submit_reason)
    
    previous_value = kr.current_value
    
    progress_update = ProgressUpdate(
        id=str(uuid.uuid4()),
        key_result_id=key_result_id,
        submitted_by_id=user_id,
        previous_value=previous_value,
        new_value=req.new_value,
        notes=req.notes,
        blockers=req.blockers,
        evidence_url=req.evidence_url,
        status="PENDING",
    )
    
    db.add(progress_update)
    db.commit()
    db.refresh(progress_update)
    
    return {
        "id": progress_update.id,
        "key_result_id": key_result_id,
        "previous_value": previous_value,
        "new_value": req.new_value,
        "status": progress_update.status,
        "notes": progress_update.notes,
        "created_at": progress_update.created_at.isoformat(),
    }


@router.get("/pending")
def get_pending_validations(
    db: Session = Depends(get_db),
    org_id: str = "",
    user_id: str = "",
    team_id: Optional[str] = None,
    department_id: Optional[str] = None,
    cycle_id: Optional[str] = None,
):
    """
    Pending KR progress awaiting this user's approval.
    Includes both legacy ProgressUpdate rows and ProgressSubmission rows.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    def _scope_objective_query(base_q):
        scoped = apply_okr_visibility_filter(base_q, user, db, org_id)
        okr_scope = get_user_okr_scope(user, db)
        scoped = apply_optional_scope_narrowing(
            scoped,
            okr_scope,
            plant_id=None,
            department_id=department_id,
            team_id=team_id,
            db=db,
            org_id=org_id,
        )
        if team_id:
            scoped = scoped.filter(Objective.team_id == team_id)
        if department_id:
            scoped = scoped.filter(Objective.department_id == department_id)
        if cycle_id:
            scoped = scoped.filter(Objective.cycle_id == cycle_id)
        return scoped

    result: list[dict] = []
    seen_ids: set[str] = set()

    # ── New workflow: ProgressSubmission ──
    sub_q = (
        db.query(ProgressSubmission)
        .filter(
            ProgressSubmission.status == "PENDING",
            ProgressSubmission.key_result_id.isnot(None),
        )
        .join(KeyResult, KeyResult.id == ProgressSubmission.key_result_id)
        .join(Objective, Objective.id == KeyResult.objective_id)
        .filter(Objective.org_id == org_id)
    )
    sub_q = _scope_objective_query(sub_q)
    for submission in sub_q.order_by(ProgressSubmission.created_at.desc()).all():
        kr = db.query(KeyResult).filter(KeyResult.id == submission.key_result_id).first()
        obj = db.query(Objective).filter(Objective.id == kr.objective_id).first() if kr else None
        if not obj:
            continue
        if not _user_can_review_progress_submission(db, user, submission, obj):
            continue
        item = _pending_item_from_submission(submission, db)
        if item and item["id"] not in seen_ids:
            seen_ids.add(item["id"])
            result.append(item)

    # ── Legacy: ProgressUpdate ──
    upd_q = (
        db.query(ProgressUpdate)
        .filter(ProgressUpdate.status == "PENDING")
        .join(KeyResult, KeyResult.id == ProgressUpdate.key_result_id)
        .join(Objective, Objective.id == KeyResult.objective_id)
        .filter(Objective.org_id == org_id)
    )
    upd_q = _scope_objective_query(upd_q)
    for update in upd_q.order_by(ProgressUpdate.created_at.desc()).all():
        kr = db.query(KeyResult).filter(KeyResult.id == update.key_result_id).first()
        obj = db.query(Objective).filter(Objective.id == kr.objective_id).first() if kr else None
        if not obj or not _user_can_validate_progress_submission(db, user, obj, update.submitted_by_id):
            continue
        item = _pending_item_from_update(update, db)
        if item and item["id"] not in seen_ids:
            seen_ids.add(item["id"])
            result.append(item)

    result.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return result


@router.post("/{update_id}/validate")
def validate_progress_update(
    update_id: str,
    req: ProgressValidation,
    db: Session = Depends(get_db),
    org_id: str = "",
    user_id: str = "",
):
    """
    Manager or team lead validates a legacy progress update.
    """
    update = db.query(ProgressUpdate).filter(ProgressUpdate.id == update_id).first()
    if not update:
        raise HTTPException(status_code=404, detail="Progress update not found")

    if update.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Cannot validate update with status {update.status}")

    reviewer_user = db.query(User).filter(User.id == user_id).first()
    kr_auth = db.query(KeyResult).filter(KeyResult.id == update.key_result_id).first()
    obj_auth = db.query(Objective).filter(Objective.id == kr_auth.objective_id).first() if kr_auth else None
    if not reviewer_user or not obj_auth:
        raise HTTPException(status_code=404, detail="Not found")
    if not _user_can_validate_progress_submission(db, reviewer_user, obj_auth, update.submitted_by_id):
        raise HTTPException(status_code=403, detail="Not authorized to validate this update")

    new_status = req.status.upper()
    
    if new_status not in ["APPROVED", "REJECTED", "REVISION_REQUESTED"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    update.status = new_status
    update.validated_by_id = user_id
    update.validated_at = datetime.utcnow()
    update.validation_notes = req.validation_notes
    
    if new_status == "APPROVED":
        kr = db.query(KeyResult).filter(KeyResult.id == update.key_result_id).first()
        if kr:
            kr.current_value = update.new_value
            pct = min((update.new_value / kr.target_value * 100) if kr.target_value > 0 else 0, 100)
            kr.status = "COMPLETED" if pct >= 100 else "IN_PROGRESS" if pct > 0 else "NOT_STARTED"

            objective = db.query(Objective).filter(Objective.id == kr.objective_id).first()
            if objective:
                _recalc_weighted_progress(objective, db)
                OKRCascadeService(db).propagate_progress_upward(objective.id)
    
    db.commit()
    db.refresh(update)
    
    return {
        "id": update.id,
        "status": update.status,
        "validated_by_id": user_id,
        "validated_at": update.validated_at.isoformat() if update.validated_at else None,
        "validation_notes": update.validation_notes,
    }


@router.get("/key-result/{kr_id}/history")
def get_kr_progress_history(
    kr_id: str,
    db: Session = Depends(get_db),
    org_id: str = "",
):
    """Get all progress updates for a specific key result."""
    kr = db.query(KeyResult).filter(KeyResult.id == kr_id).first()
    if not kr:
        raise HTTPException(status_code=404, detail="Key Result not found")
    
    updates = db.query(ProgressUpdate).filter(
        ProgressUpdate.key_result_id == kr_id
    ).order_by(ProgressUpdate.created_at.desc()).all()
    
    result = []
    for update in updates:
        submitter = db.query(User).filter(User.id == update.submitted_by_id).first()
        validator = db.query(User).filter(User.id == update.validated_by_id).first() if update.validated_by_id else None
        
        result.append({
            "id": update.id,
            "previous_value": update.previous_value,
            "new_value": update.new_value,
            "submitted_by": submitter.name if submitter else None,
            "notes": update.notes,
            "blockers": update.blockers,
            "evidence_url": update.evidence_url,
            "status": update.status,
            "validated_by": validator.name if validator else None,
            "validation_notes": update.validation_notes,
            "created_at": update.created_at.isoformat(),
            "validated_at": update.validated_at.isoformat() if update.validated_at else None,
        })
    
    return result


@router.get("/objective/{objective_id}/summary")
def get_objective_progress_summary(
    objective_id: str,
    db: Session = Depends(get_db),
    org_id: str = "",
):
    """Get progress summary for an objective including all KRs and their statuses."""
    obj = db.query(Objective).filter(Objective.id == objective_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Objective not found")
    
    krs = db.query(KeyResult).filter(KeyResult.objective_id == objective_id).all()
    
    kr_summaries = []
    for kr in krs:
        progress_pct = calculate_kr_progress(kr)
        updates = db.query(ProgressUpdate).filter(
            ProgressUpdate.key_result_id == kr.id
        ).order_by(ProgressUpdate.created_at.desc()).all()
        
        latest_update = updates[0] if updates else None
        pending_count = sum(1 for u in updates if u.status == "PENDING")
        
        kr_summaries.append({
            "id": kr.id,
            "title": kr.title,
            "target_value": kr.target_value,
            "current_value": kr.current_value,
            "unit": kr.unit,
            "weight": kr.weight,
            "progress_pct": progress_pct,
            "status": kr.status,
            "latest_update": latest_update.created_at.isoformat() if latest_update else None,
            "pending_validations": pending_count,
            "total_updates": len(updates),
        })
    
    return {
        "objective_id": objective_id,
        "objective_title": obj.title,
        "objective_level": obj.level,
        "overall_progress": obj.progress,
        "overall_rating": score_to_rating(obj.progress),
        "key_results": kr_summaries,
    }


# ══════════════════════════════════════════════════════════════════════════════
# MULTI-LEVEL CASCADING APPROVAL ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/submissions/cascade/pending")
def get_cascading_submissions(
    db: Session = Depends(get_db),
    org_id: str = "",
    user_id: str = "",
    level: Optional[str] = Query(None),
):
    """
    Get parent-level (auto-cascaded) submissions waiting for approval.
    These are auto-created when child objectives are approved.
    
    ?level=TEAM - Get TEAM-level submissions (parent cascade from INDIVIDUAL)
    ?level=DEPARTMENT - Get DEPARTMENT-level submissions (parent cascade from TEAM)
    etc.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get cascading submissions (where key_result_id is null but objective_id is set)
    query = db.query(ProgressSubmission).filter(
        ProgressSubmission.status == "PENDING",
        ProgressSubmission.key_result_id == None,
        ProgressSubmission.objective_id != None,
    )
    
    # Filter by level if specified
    if level:
        query = query.join(Objective).filter(Objective.level == level.upper())
    
    # Filter by user's approval scope
    if user.system_role in ["MANAGER", "DEPT_HEAD", "PLANT_HEAD"]:
        if user.system_role == "MANAGER" and user.team_id:
            query = query.join(Objective).filter(
                Objective.team_id == user.team_id
            )
        elif user.system_role == "DEPT_HEAD" and user.department_id:
            query = query.join(Objective).filter(
                Objective.department_id == user.department_id
            )
        elif user.system_role == "PLANT_HEAD" and user.plant_id:
            query = query.join(Objective).filter(
                Objective.plant_id == user.plant_id
            )
    
    submissions = query.order_by(ProgressSubmission.created_at.desc()).all()
    return [_get_submission_dict(s, db) for s in submissions]


@router.get("/submissions/{submission_id}/cascade-chain")
def get_submission_cascade_chain(
    submission_id: str,
    db: Session = Depends(get_db),
    org_id: str = "",
):
    """
    Get the full cascade chain for a submission.
    Shows where it originated and where it's going.
    """
    submission = db.query(ProgressSubmission).filter(
        ProgressSubmission.id == submission_id
    ).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    chain = []
    
    # Get the objective this submission is for
    if submission.key_result_id:
        kr = db.query(KeyResult).filter(KeyResult.id == submission.key_result_id).first()
        if kr:
            obj = db.query(Objective).filter(Objective.id == kr.objective_id).first()
    else:
        obj = db.query(Objective).filter(Objective.id == submission.objective_id).first()
    
    if not obj:
        return {"chain": [], "message": "Objective not found"}
    
    # Walk up the hierarchy
    current = obj
    visited = set()
    
    while current and current.id not in visited:
        visited.add(current.id)
        
        # Get submission status for this level
        level_submission = db.query(ProgressSubmission).filter(
            or_(
                ProgressSubmission.objective_id == current.id,
                (
                    and_(
                        ProgressSubmission.objective_id == None,
                        KeyResult.objective_id == current.id,
                        ProgressSubmission.key_result_id == KeyResult.id,
                    )
                ),
            )
        ).first()
        
        chain.append({
            "objective_id": current.id,
            "level": current.level,
            "title": current.title,
            "progress": current.progress or 0,
            "status": level_submission.status if level_submission else "PENDING",
            "submission_id": level_submission.id if level_submission else None,
        })
        
        # Move to parent
        if current.parent_id:
            current = db.query(Objective).filter(Objective.id == current.parent_id).first()
        else:
            current = None
    
    return {
        "chain": chain,
        "total_levels": len(chain),
        "current_submission_id": submission_id,
    }


@router.get("/approvals/dashboard")
def get_approvals_dashboard(
    db: Session = Depends(get_db),
    org_id: str = "",
    user_id: str = "",
):
    """
    Get a dashboard summary for the approval queue.
    Shows pending approvals by level and status.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get all pending submissions
    all_pending = db.query(ProgressSubmission).filter(
        ProgressSubmission.status == "PENDING"
    ).all()
    
    # Group by validation level
    by_level = {}
    for submission in all_pending:
        level = submission.validation_level or "UNKNOWN"
        if level not in by_level:
            by_level[level] = {"count": 0, "individual": 0, "team": 0, "department": 0, "plant": 0}
        
        by_level[level]["count"] += 1
    
    # Get user's specific queue (dual-approval assignee, any role)
    user_queue_ids = pending_subject_ids_for_approver(
        db, org_id, user_id, SUBJECT_PROGRESS_SUBMISSION
    )
    user_submissions = (
        db.query(ProgressSubmission)
        .filter(ProgressSubmission.id.in_(user_queue_ids))
        .order_by(ProgressSubmission.created_at.desc())
        .all()
        if user_queue_ids
        else []
    )
    user_queue = [_get_submission_dict(s, db) for s in user_submissions]
    
    return {
        "user_role": user.system_role,
        "total_pending": len(all_pending),
        "by_level": by_level,
        "user_queue": user_queue,
        "user_queue_count": len(user_queue),
    }
