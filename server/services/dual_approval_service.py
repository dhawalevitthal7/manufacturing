"""
Ordered dual-approval chain for OKR creation and progress submissions.

Stage 1 (LINE): Plant Head / line manager must approve first.
Stage 2 (FUNCTIONAL): Corporate functional head approves after stage 1.
Finalization runs only when all required stages are satisfied.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from server.models import (
    ApprovalStep,
    AuditLog,
    KeyResult,
    Objective,
    ProgressSubmission,
    ProgressUpdate,
    User,
)
from server.okr_cascade_service import OKRCascadeService
from server.okr_utils import calculate_kr_progress
from server.services.manager_resolution import resolve_approvers

logger = logging.getLogger(__name__)

SUBJECT_OKR_CREATION = "OKR_CREATION"
SUBJECT_PROGRESS_SUBMISSION = "PROGRESS_SUBMISSION"

STEP_LINE = "LINE"
STEP_FUNCTIONAL = "FUNCTIONAL"

STATUS_PENDING = "PENDING"
STATUS_APPROVED = "APPROVED"
STATUS_REJECTED = "REJECTED"
STATUS_SKIPPED = "SKIPPED"


class DualApprovalError(ValueError):
    """Raised when an approval action is invalid."""


def _approver_user(db: Session, user_id: Optional[str]) -> Optional[User]:
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id, User.is_active == True).first()


def get_steps(
    db: Session,
    subject_type: str,
    subject_id: str,
) -> List[ApprovalStep]:
    return (
        db.query(ApprovalStep)
        .filter(
            ApprovalStep.subject_type == subject_type,
            ApprovalStep.subject_id == subject_id,
        )
        .order_by(ApprovalStep.sequence_order.asc())
        .all()
    )


def current_step(
    db: Session,
    subject_type: str,
    subject_id: str,
) -> Optional[ApprovalStep]:
    for step in get_steps(db, subject_type, subject_id):
        if step.status == STATUS_PENDING:
            return step
    return None


def chain_status(
    db: Session,
    subject_type: str,
    subject_id: str,
) -> Dict[str, Any]:
    """Expose per-stage status for UI badges."""
    steps = get_steps(db, subject_type, subject_id)
    result: Dict[str, Any] = {
        "line": None,
        "functional": None,
        "steps": [],
        "current_step_id": None,
        "current_approval_type": None,
        "is_complete": False,
    }
    for step in steps:
        approver = _approver_user(db, step.approver_id)
        entry = {
            "id": step.id,
            "sequence_order": step.sequence_order,
            "approval_type": step.approval_type,
            "status": step.status,
            "approver_id": step.approver_id,
            "approver_name": approver.name if approver else None,
            "approver_role": step.approver_role,
            "decided_at": step.decided_at.isoformat() if step.decided_at else None,
            "comment": step.comment,
        }
        result["steps"].append(entry)
        if step.approval_type == STEP_LINE:
            result["line"] = step.status
        elif step.approval_type == STEP_FUNCTIONAL:
            result["functional"] = step.status

    pending = current_step(db, subject_type, subject_id)
    if pending:
        result["current_step_id"] = pending.id
        result["current_approval_type"] = pending.approval_type
    else:
        result["is_complete"] = all(
            s.status in (STATUS_APPROVED, STATUS_SKIPPED) for s in steps
        )
    return result


def _clear_steps(db: Session, subject_type: str, subject_id: str) -> None:
    db.query(ApprovalStep).filter(
        ApprovalStep.subject_type == subject_type,
        ApprovalStep.subject_id == subject_id,
    ).delete(synchronize_session=False)


def _add_step(
    db: Session,
    org_id: str,
    subject_type: str,
    subject_id: str,
    sequence_order: int,
    approval_type: str,
    approver: Optional[User],
    *,
    status: str = STATUS_PENDING,
) -> ApprovalStep:
    step = ApprovalStep(
        id=str(uuid.uuid4()),
        org_id=org_id,
        subject_type=subject_type,
        subject_id=subject_id,
        sequence_order=sequence_order,
        approval_type=approval_type,
        approver_id=approver.id if approver else None,
        approver_role=approver.system_role if approver else None,
        status=status,
    )
    db.add(step)
    return step


def _sync_okr_pending_approver(db: Session, okr: Objective) -> None:
    step = current_step(db, SUBJECT_OKR_CREATION, okr.id)
    if step and step.approver_id:
        okr.pending_approver_user_id = step.approver_id
        okr.pending_approver_role = step.approver_role
    else:
        okr.pending_approver_user_id = None
        okr.pending_approver_role = None


def _sync_submission_pending(db: Session, submission: ProgressSubmission) -> None:
    step = current_step(db, SUBJECT_PROGRESS_SUBMISSION, submission.id)
    if step:
        submission.next_approver_role = step.approver_role
        submission.validation_level = step.approver_role
    else:
        submission.next_approver_role = None


def _objective_for_subject(
    db: Session, subject_type: str, subject_id: str
) -> Optional[Objective]:
    if subject_type == SUBJECT_OKR_CREATION:
        return db.query(Objective).filter(Objective.id == subject_id).first()
    if subject_type != SUBJECT_PROGRESS_SUBMISSION:
        return None
    submission = (
        db.query(ProgressSubmission)
        .filter(ProgressSubmission.id == subject_id)
        .first()
    )
    if not submission or not submission.key_result_id:
        return None
    kr = db.query(KeyResult).filter(KeyResult.id == submission.key_result_id).first()
    if not kr:
        return None
    return db.query(Objective).filter(Objective.id == kr.objective_id).first()


def _requires_functional_approval(
    db: Session, subject_type: str, subject_id: str
) -> bool:
    """
    Individual employee OKRs and KR progress need only line approval
    (dept head / team lead / manager). Team+ creation and progress keep
    the functional executive step.
    """
    objective = _objective_for_subject(db, subject_type, subject_id)
    if not objective:
        return subject_type != SUBJECT_PROGRESS_SUBMISSION
    return (objective.level or "").upper() != "INDIVIDUAL"


def build_chain(
    db: Session,
    org_id: str,
    subject_type: str,
    subject_id: str,
    submitter_id: str,
) -> Dict[str, Any]:
    """
    Create ordered approval steps from submitter reporting relationships.
    """
    _clear_steps(db, subject_type, subject_id)
    approvers = resolve_approvers(db, submitter_id, org_id)
    line_user = _approver_user(db, approvers.get("line"))
    functional_user = _approver_user(db, approvers.get("functional"))
    require_functional = _requires_functional_approval(db, subject_type, subject_id)

    if not line_user and not functional_user:
        raise DualApprovalError("No approvers could be resolved for this submission")

    steps: List[ApprovalStep] = []
    if line_user:
        steps.append(
            _add_step(
                db,
                org_id,
                subject_type,
                subject_id,
                1,
                STEP_LINE,
                line_user,
            )
        )
    if functional_user and require_functional:
        steps.append(
            _add_step(
                db,
                org_id,
                subject_type,
                subject_id,
                2,
                STEP_FUNCTIONAL,
                functional_user,
            )
        )
    elif line_user:
        steps.append(
            _add_step(
                db,
                org_id,
                subject_type,
                subject_id,
                2,
                STEP_FUNCTIONAL,
                None,
                status=STATUS_SKIPPED,
            )
        )

    if subject_type == SUBJECT_OKR_CREATION:
        okr = db.query(Objective).filter(Objective.id == subject_id).first()
        if okr:
            okr.creation_primary_approved_at = None
            okr.creation_primary_approved_by_id = None
            okr.creation_functional_approved_at = None
            okr.creation_functional_approved_by_id = None
            _sync_okr_pending_approver(db, okr)
    elif subject_type == SUBJECT_PROGRESS_SUBMISSION:
        submission = (
            db.query(ProgressSubmission)
            .filter(ProgressSubmission.id == subject_id)
            .first()
        )
        if submission:
            _sync_submission_pending(db, submission)

    db.flush()
    return chain_status(db, subject_type, subject_id)


def _line_step_approved(db: Session, subject_type: str, subject_id: str) -> bool:
    line_step = (
        db.query(ApprovalStep)
        .filter(
            ApprovalStep.subject_type == subject_type,
            ApprovalStep.subject_id == subject_id,
            ApprovalStep.approval_type == STEP_LINE,
        )
        .first()
    )
    if not line_step:
        return True
    return line_step.status == STATUS_APPROVED


def approve(
    db: Session,
    step_id: str,
    approver_id: str,
    comment: str = "",
    *,
    manager_value: Optional[float] = None,
    allow_line_delegate: bool = False,
) -> Dict[str, Any]:
    step = db.query(ApprovalStep).filter(ApprovalStep.id == step_id).first()
    if not step:
        raise DualApprovalError("Approval step not found")
    if step.status != STATUS_PENDING:
        raise DualApprovalError(f"Step is not pending (status={step.status})")
    if step.approver_id != approver_id:
        delegate_ok = (
            allow_line_delegate
            and step.approval_type == STEP_LINE
            and step.subject_type == SUBJECT_PROGRESS_SUBMISSION
        )
        if not delegate_ok:
            raise DualApprovalError("You are not the assigned approver for this step")
    if step.approval_type == STEP_FUNCTIONAL and not _line_step_approved(
        db, step.subject_type, step.subject_id
    ):
        raise DualApprovalError(
            "Awaiting line approval before functional head can approve"
        )

    now = datetime.utcnow()
    step.status = STATUS_APPROVED
    step.decided_at = now
    step.comment = comment or None

    approver = _approver_user(db, approver_id)
    if step.subject_type == SUBJECT_OKR_CREATION and approver:
        okr = db.query(Objective).filter(Objective.id == step.subject_id).first()
        if okr:
            if step.approval_type == STEP_LINE:
                okr.creation_primary_approved_by_id = approver_id
                okr.creation_primary_approved_at = now
            elif step.approval_type == STEP_FUNCTIONAL:
                okr.creation_functional_approved_by_id = approver_id
                okr.creation_functional_approved_at = now

    next_step = current_step(db, step.subject_type, step.subject_id)
    if next_step:
        if step.subject_type == SUBJECT_OKR_CREATION:
            okr = db.query(Objective).filter(Objective.id == step.subject_id).first()
            if okr:
                _sync_okr_pending_approver(db, okr)
        elif step.subject_type == SUBJECT_PROGRESS_SUBMISSION:
            submission = (
                db.query(ProgressSubmission)
                .filter(ProgressSubmission.id == step.subject_id)
                .first()
            )
            if submission:
                _sync_submission_pending(db, submission)
        db.flush()
        return {
            "finalized": False,
            "chain": chain_status(db, step.subject_type, step.subject_id),
            "message": "Approval recorded; awaiting next stage",
        }

    _finalize(db, step.subject_type, step.subject_id, approver_id, manager_value=manager_value)
    db.flush()
    return {
        "finalized": True,
        "chain": chain_status(db, step.subject_type, step.subject_id),
        "message": "All required approvals complete",
    }


def reject(
    db: Session,
    step_id: str,
    approver_id: str,
    comment: str,
    *,
    allow_line_delegate: bool = False,
) -> Dict[str, Any]:
    step = db.query(ApprovalStep).filter(ApprovalStep.id == step_id).first()
    if not step:
        raise DualApprovalError("Approval step not found")
    if step.status != STATUS_PENDING:
        raise DualApprovalError(f"Step is not pending (status={step.status})")
    if step.approver_id != approver_id:
        delegate_ok = (
            allow_line_delegate
            and step.approval_type == STEP_LINE
            and step.subject_type == SUBJECT_PROGRESS_SUBMISSION
        )
        if not delegate_ok:
            raise DualApprovalError("You are not the assigned approver for this step")
    if step.approval_type == STEP_FUNCTIONAL and not _line_step_approved(
        db, step.subject_type, step.subject_id
    ):
        raise DualApprovalError(
            "Awaiting line approval before functional head can reject"
        )
    if not (comment or "").strip():
        raise DualApprovalError("Rejection comment is required")

    step.status = STATUS_REJECTED
    step.decided_at = datetime.utcnow()
    step.comment = comment.strip()

    if step.subject_type == SUBJECT_OKR_CREATION:
        okr = db.query(Objective).filter(Objective.id == step.subject_id).first()
        if okr:
            from server.services.okr_lifecycle_service import reject_okr

            reject_okr(okr, comment.strip())
            okr.creation_primary_approved_at = None
            okr.creation_primary_approved_by_id = None
            okr.creation_functional_approved_at = None
            okr.creation_functional_approved_by_id = None
    elif step.subject_type == SUBJECT_PROGRESS_SUBMISSION:
        submission = (
            db.query(ProgressSubmission)
            .filter(ProgressSubmission.id == step.subject_id)
            .first()
        )
        if submission:
            submission.status = "REJECTED"
            submission.reviewed_by_id = approver_id
            submission.reviewed_at = datetime.utcnow()
            submission.manager_note = comment.strip()
            submission.next_approver_role = None

    db.flush()
    return {
        "finalized": True,
        "chain": chain_status(db, step.subject_type, step.subject_id),
        "message": "Rejected and returned to submitter",
    }


def _finalize(
    db: Session,
    subject_type: str,
    subject_id: str,
    final_approver_id: str,
    *,
    manager_value: Optional[float] = None,
) -> None:
    if subject_type == SUBJECT_OKR_CREATION:
        okr = db.query(Objective).filter(Objective.id == subject_id).first()
        if okr:
            from server.services.okr_lifecycle_service import activate_okr

            activate_okr(okr, db)
            okr.creation_approved_by_id = final_approver_id
            okr.creation_approved_at = datetime.utcnow()
    elif subject_type == SUBJECT_PROGRESS_SUBMISSION:
        _finalize_progress_submission(
            db, subject_id, final_approver_id, manager_value=manager_value
        )


def _finalize_progress_submission(
    db: Session,
    submission_id: str,
    approver_id: str,
    *,
    manager_value: Optional[float] = None,
) -> None:
    submission = (
        db.query(ProgressSubmission)
        .filter(ProgressSubmission.id == submission_id)
        .first()
    )
    if not submission or not submission.key_result_id:
        return

    reviewer = _approver_user(db, approver_id)
    final_value = (
        manager_value
        if manager_value is not None
        else submission.manager_value
        if submission.manager_value is not None
        else submission.employee_value
    )

    kr = db.query(KeyResult).filter(KeyResult.id == submission.key_result_id).first()
    if not kr:
        return

    previous_value = kr.current_value
    kr.current_value = final_value

    # ── Normalization Engine: compute correct % based on KPI behavior ──
    from server.services.progress_normalization_service import (
        calculate_progress,
        NormalizationError,
    )
    try:
        norm_result = calculate_progress(kr, final_value)
        pct = norm_result.normalized_progress
    except NormalizationError:
        # Fallback for malformed KRs
        pct = min((final_value / kr.target_value * 100) if kr.target_value > 0 else 0, 100)

    kr.normalized_progress = pct
    kr.last_actual_value = final_value
    kr.last_calculated_at = datetime.utcnow()
    kr.status = (
        "COMPLETED" if pct >= 100 else "IN_PROGRESS" if pct > 0 else "NOT_STARTED"
    )

    audit = ProgressUpdate(
        id=str(uuid.uuid4()),
        key_result_id=kr.id,
        submitted_by_id=submission.submitted_by_id,
        validated_by_id=approver_id,
        previous_value=previous_value,
        new_value=final_value,
        notes=submission.employee_note or submission.manager_note,
        status="APPROVED",
        validation_level=reviewer.system_role if reviewer else None,
        progress_source="MANUAL",
        validated_at=datetime.utcnow(),
    )
    db.add(audit)

    # Audit log for normalization
    try:
        kpi_behavior = getattr(kr, "kpi_behavior", "HIGHER_IS_BETTER") or "HIGHER_IS_BETTER"
        norm_audit = AuditLog(
            org_id=submission.objective_id or "",
            user_id=submission.submitted_by_id or "",
            action="PROGRESS_NORMALIZATION",
            entity_type="KEY_RESULT",
            entity_id=kr.id,
            details=json.dumps({
                "actual_value": final_value,
                "old_value": previous_value,
                "normalized_progress": pct,
                "kpi_behavior": kpi_behavior,
                "target_value": kr.target_value,
                "formula_used": norm_result.formula_used if 'norm_result' in dir() else "fallback",
                "calculated_at": datetime.utcnow().isoformat(),
            }),
        )
        db.add(norm_audit)
    except Exception:
        pass  # Non-blocking audit

    objective = db.query(Objective).filter(Objective.id == kr.objective_id).first()
    if objective:
        OKRCascadeService(db).refresh_objective_progress_for_session(objective.id)
        OKRCascadeService(db).propagate_progress_upward(objective.id)

    submission.status = "APPROVED"
    submission.reviewed_by_id = approver_id
    submission.reviewed_at = datetime.utcnow()
    submission.next_approver_role = None

    chain_entries = []
    for step in get_steps(db, SUBJECT_PROGRESS_SUBMISSION, submission_id):
        chain_entries.append(
            {
                "role": step.approver_role,
                "user_id": step.approver_id,
                "action": "approve",
                "approval_type": step.approval_type,
                "timestamp": step.decided_at.isoformat() if step.decided_at else None,
            }
        )
    submission.validation_chain = json.dumps(chain_entries)


def approve_current_step_for_subject(
    db: Session,
    subject_type: str,
    subject_id: str,
    approver_id: str,
    comment: str = "",
    *,
    manager_value: Optional[float] = None,
    allow_line_delegate: bool = False,
) -> Dict[str, Any]:
    step = current_step(db, subject_type, subject_id)
    if not step:
        raise DualApprovalError("No pending approval step for this item")
    return approve(
        db,
        step.id,
        approver_id,
        comment,
        manager_value=manager_value,
        allow_line_delegate=allow_line_delegate,
    )


def reject_current_step_for_subject(
    db: Session,
    subject_type: str,
    subject_id: str,
    approver_id: str,
    comment: str,
    *,
    allow_line_delegate: bool = False,
) -> Dict[str, Any]:
    step = current_step(db, subject_type, subject_id)
    if not step:
        raise DualApprovalError("No pending approval step for this item")
    return reject(db, step.id, approver_id, comment, allow_line_delegate=allow_line_delegate)


def finalize_individual_progress_after_line_approval(
    db: Session, org_id: Optional[str] = None
) -> int:
    """
    Apply KR updates for individual employee progress stuck on a functional step
    after line approval (legacy dual chain before line-only rule).
    """
    q = db.query(ApprovalStep).filter(
        ApprovalStep.subject_type == SUBJECT_PROGRESS_SUBMISSION,
        ApprovalStep.approval_type == STEP_FUNCTIONAL,
        ApprovalStep.status == STATUS_PENDING,
    )
    if org_id:
        q = q.filter(ApprovalStep.org_id == org_id)

    finalized = 0
    for step in q.all():
        if _progress_requires_functional_approval(
            db, SUBJECT_PROGRESS_SUBMISSION, step.subject_id
        ):
            continue
        if not _line_step_approved(db, SUBJECT_PROGRESS_SUBMISSION, step.subject_id):
            continue

        step.status = STATUS_SKIPPED
        step.decided_at = datetime.utcnow()
        step.comment = "Not required for individual employee progress"

        line_step = (
            db.query(ApprovalStep)
            .filter(
                ApprovalStep.subject_type == SUBJECT_PROGRESS_SUBMISSION,
                ApprovalStep.subject_id == step.subject_id,
                ApprovalStep.approval_type == STEP_LINE,
            )
            .first()
        )
        approver_id = line_step.approver_id if line_step else None
        if not approver_id:
            submission = (
                db.query(ProgressSubmission)
                .filter(ProgressSubmission.id == step.subject_id)
                .first()
            )
            approver_id = submission.submitted_by_id if submission else None
        if not approver_id:
            continue

        _finalize(db, SUBJECT_PROGRESS_SUBMISSION, step.subject_id, approver_id)
        finalized += 1

    if finalized:
        db.commit()
    return finalized


def repair_functional_approval_steps(db: Session, org_id: Optional[str] = None) -> int:
    """
    Re-point pending FUNCTIONAL steps at the resolved executive functional head.
    Needed when dotted-line seed order assigned dept head instead of CMO/CFO/etc.
    """
    q = db.query(ApprovalStep).filter(
        ApprovalStep.approval_type == STEP_FUNCTIONAL,
        ApprovalStep.status == STATUS_PENDING,
    )
    if org_id:
        q = q.filter(ApprovalStep.org_id == org_id)

    repaired = 0
    for step in q.all():
        if step.subject_type == SUBJECT_PROGRESS_SUBMISSION and not _progress_requires_functional_approval(
            db, SUBJECT_PROGRESS_SUBMISSION, step.subject_id
        ):
            continue
        submitter_id: Optional[str] = None
        if step.subject_type == SUBJECT_PROGRESS_SUBMISSION:
            sub = (
                db.query(ProgressSubmission)
                .filter(ProgressSubmission.id == step.subject_id)
                .first()
            )
            submitter_id = sub.submitted_by_id if sub else None
        elif step.subject_type == SUBJECT_OKR_CREATION:
            okr = db.query(Objective).filter(Objective.id == step.subject_id).first()
            submitter_id = okr.owner_id if okr else None
        if not submitter_id:
            continue

        approvers = resolve_approvers(
            db, submitter_id, step.org_id, persist_if_missing=False
        )
        functional_id = approvers.get("functional")
        if not functional_id or functional_id == step.approver_id:
            continue

        functional_user = _approver_user(db, functional_id)
        if not functional_user:
            continue

        step.approver_id = functional_id
        step.approver_role = functional_user.system_role

        if step.subject_type == SUBJECT_OKR_CREATION:
            okr = db.query(Objective).filter(Objective.id == step.subject_id).first()
            if okr:
                _sync_okr_pending_approver(db, okr)
        elif step.subject_type == SUBJECT_PROGRESS_SUBMISSION:
            submission = (
                db.query(ProgressSubmission)
                .filter(ProgressSubmission.id == step.subject_id)
                .first()
            )
            if submission:
                _sync_submission_pending(db, submission)
        repaired += 1

    if repaired:
        db.commit()
    return repaired


def pending_subject_ids_for_approver(
    db: Session,
    org_id: str,
    approver_id: str,
    subject_type: str,
    *,
    approval_type: Optional[str] = None,
) -> List[str]:
    """
    Subject IDs where the given user is the current pending-step approver.
    Functional queue only shows items whose line step is already approved.
    """
    q = db.query(ApprovalStep).filter(
        ApprovalStep.org_id == org_id,
        ApprovalStep.subject_type == subject_type,
        ApprovalStep.approver_id == approver_id,
        ApprovalStep.status == STATUS_PENDING,
    )
    if approval_type:
        q = q.filter(ApprovalStep.approval_type == approval_type)

    subject_ids: List[str] = []
    for step in q.all():
        if step.approval_type == STEP_FUNCTIONAL and not _line_step_approved(
            db, subject_type, step.subject_id
        ):
            continue
        active = current_step(db, subject_type, step.subject_id)
        if active and active.id == step.id:
            subject_ids.append(step.subject_id)
    return subject_ids


def attach_chain_to_dict(
    db: Session,
    subject_type: str,
    subject_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    payload["approval_chain_status"] = chain_status(db, subject_type, subject_id)
    return payload
