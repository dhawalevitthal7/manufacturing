"""Unified dual-approval queue endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from server.database import get_db
from server.models import Objective, ProgressSubmission, KeyResult, User
from server.services.dual_approval_service import (
    SUBJECT_OKR_CREATION,
    SUBJECT_PROGRESS_SUBMISSION,
    STEP_FUNCTIONAL,
    STEP_LINE,
    chain_status,
    pending_subject_ids_for_approver,
)

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


def _serialize_okr_queue_item(db: Session, okr: Objective) -> dict:
    owner = db.query(User).filter(User.id == okr.owner_id).first()
    return {
        "subject_type": SUBJECT_OKR_CREATION,
        "subject_id": okr.id,
        "title": okr.title,
        "level": okr.level,
        "owner_name": owner.name if owner else None,
        "okr_status": okr.okr_status,
        "creation_approval_status": okr.creation_approval_status,
        "approval_chain_status": chain_status(db, SUBJECT_OKR_CREATION, okr.id),
    }


def _serialize_progress_queue_item(db: Session, submission: ProgressSubmission) -> dict:
    kr = (
        db.query(KeyResult).filter(KeyResult.id == submission.key_result_id).first()
        if submission.key_result_id
        else None
    )
    obj = (
        db.query(Objective).filter(Objective.id == kr.objective_id).first()
        if kr
        else None
    )
    submitter = db.query(User).filter(User.id == submission.submitted_by_id).first()
    return {
        "subject_type": SUBJECT_PROGRESS_SUBMISSION,
        "subject_id": submission.id,
        "key_result_id": submission.key_result_id,
        "key_result_title": kr.title if kr else None,
        "objective_title": obj.title if obj else None,
        "objective_level": obj.level if obj else None,
        "submitted_by_name": submitter.name if submitter else None,
        "employee_value": submission.employee_value,
        "status": submission.status,
        "approval_chain_status": chain_status(
            db, SUBJECT_PROGRESS_SUBMISSION, submission.id
        ),
    }


@router.get("/my-queue")
def my_approval_queue(
    stage: Optional[str] = Query(None, description="line | functional"),
    subject: Optional[str] = Query(None, description="okr | progress | all"),
    db: Session = Depends(get_db),
    org_id: str = "",
    user_id: str = "",
):
    """
    Pending dual-approval items for the current user.
    ``stage=line`` → line (Plant Head) queue; ``stage=functional`` → functional head queue.
    """
    if not org_id or not user_id:
        raise HTTPException(400, "org_id or user_id not found in token")

    approval_type = None
    if stage:
        st = stage.strip().lower()
        if st == "line":
            approval_type = STEP_LINE
        elif st == "functional":
            approval_type = STEP_FUNCTIONAL
        else:
            raise HTTPException(400, "stage must be line or functional")

    subject_filter = (subject or "all").strip().lower()
    items = []

    if subject_filter in ("all", "okr"):
        okr_ids = pending_subject_ids_for_approver(
            db,
            org_id,
            user_id,
            SUBJECT_OKR_CREATION,
            approval_type=approval_type,
        )
        if okr_ids:
            okrs = (
                db.query(Objective)
                .filter(Objective.org_id == org_id, Objective.id.in_(okr_ids))
                .order_by(Objective.created_at.desc())
                .all()
            )
            items.extend(_serialize_okr_queue_item(db, o) for o in okrs)

    if subject_filter in ("all", "progress"):
        sub_ids = pending_subject_ids_for_approver(
            db,
            org_id,
            user_id,
            SUBJECT_PROGRESS_SUBMISSION,
            approval_type=approval_type,
        )
        if sub_ids:
            subs = (
                db.query(ProgressSubmission)
                .filter(ProgressSubmission.id.in_(sub_ids))
                .order_by(ProgressSubmission.created_at.desc())
                .all()
            )
            items.extend(_serialize_progress_queue_item(db, s) for s in subs)

    return {"items": items, "count": len(items)}


@router.get("/chain/{subject_type}/{subject_id}")
def get_approval_chain(
    subject_type: str,
    subject_id: str,
    db: Session = Depends(get_db),
    org_id: str = "",
):
    """Fetch dual-approval chain status for an OKR or progress submission."""
    st = subject_type.strip().upper()
    if st not in (SUBJECT_OKR_CREATION, SUBJECT_PROGRESS_SUBMISSION):
        raise HTTPException(400, "Invalid subject_type")
    return chain_status(db, st, subject_id)
