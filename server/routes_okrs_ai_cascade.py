"""API routes for AI-assisted hierarchical OKR cascading."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from server.auth import get_jwt_payload
from server.database import get_db
from server.models import Objective, OkrCascadeNotification, ObjectiveVersion, User
from server.roles import SystemRole, normalize_role
from server.services.ai_cascade_engine import (
    AICascadeEngine,
    ai_draft_to_dict,
    schedule_cascade_for_active_okr,
)
from server.services.objective_version_service import (
    build_alignment_preview,
    build_diff_view,
    versions_to_dicts,
)
from server.services.okr_lifecycle_service import (
    OKR_STATUS_AI_DRAFT,
    OKR_STATUS_PENDING_PARENT,
    OKR_STATUS_UNDER_REVIEW,
)

router = APIRouter(prefix="/api/okrs", tags=["okrs-ai-cascade"])


class ReviewUpdateBody(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    key_results: Optional[List[Dict[str, Any]]] = None


class RejectBody(BaseModel):
    reason: str = Field(..., min_length=1)


def _actor(db: Session, payload: dict) -> User:
    user_id = payload.get("sub", "")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    return user


def _get_okr(db: Session, obj_id: str, org_id: str) -> Objective:
    obj = db.query(Objective).filter(Objective.id == obj_id, Objective.org_id == org_id).first()
    if not obj:
        raise HTTPException(404, "Objective not found")
    return obj


@router.get("/cascade-notifications")
def list_cascade_notifications(
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
    unread_only: bool = False,
):
    """In-app notifications for AI cascade workflow."""
    org_id = payload.get("org_id", "")
    user_id = payload.get("sub", "")

    q = db.query(OkrCascadeNotification).filter(
        OkrCascadeNotification.org_id == org_id,
        OkrCascadeNotification.recipient_user_id == user_id,
    )
    if unread_only:
        q = q.filter(OkrCascadeNotification.is_read == False)

    rows = q.order_by(OkrCascadeNotification.created_at.desc()).limit(50).all()
    return [
        {
            "id": n.id,
            "objective_id": n.objective_id,
            "event_type": n.event_type,
            "title": n.title,
            "body": n.body,
            "is_read": n.is_read,
            "actor_user_id": n.actor_user_id,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in rows
    ]


@router.patch("/cascade-notifications/{notif_id}/read")
def mark_notification_read(
    notif_id: str,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    org_id = payload.get("org_id", "")
    user_id = payload.get("sub", "")
    notif = (
        db.query(OkrCascadeNotification)
        .filter(
            OkrCascadeNotification.id == notif_id,
            OkrCascadeNotification.org_id == org_id,
            OkrCascadeNotification.recipient_user_id == user_id,
        )
        .first()
    )
    if not notif:
        raise HTTPException(404, "Notification not found")
    notif.is_read = True
    db.commit()
    return {"id": notif.id, "is_read": True}


@router.get("/{obj_id}/versions")
def list_objective_versions(
    obj_id: str,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    """Version history for an AI cascade OKR."""
    org_id = payload.get("org_id", "")
    obj = _get_okr(db, obj_id, org_id)
    versions = (
        db.query(ObjectiveVersion)
        .filter(ObjectiveVersion.objective_id == obj.id)
        .order_by(ObjectiveVersion.version.desc())
        .all()
    )
    return versions_to_dicts(versions)


@router.get("/{obj_id}/alignment-preview")
def alignment_preview(
    obj_id: str,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    """Compare child AI draft with its parent objective."""
    org_id = payload.get("org_id", "")
    obj = _get_okr(db, obj_id, org_id)
    parent_id = obj.ai_generated_from_objective_id or obj.parent_id
    if not parent_id:
        raise HTTPException(400, "No parent objective linked")
    parent = _get_okr(db, parent_id, org_id)
    return build_alignment_preview(db, child=obj, parent=parent)


@router.get("/{obj_id}/diff")
def objective_diff(
    obj_id: str,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
    version: int = 0,
):
    """Diff current OKR against a prior version."""
    org_id = payload.get("org_id", "")
    obj = _get_okr(db, obj_id, org_id)
    q = db.query(ObjectiveVersion).filter(ObjectiveVersion.objective_id == obj.id)
    if version:
        q = q.filter(ObjectiveVersion.version == version)
    else:
        q = q.filter(ObjectiveVersion.version < (obj.ai_generation_version or 1))
    prev = q.order_by(ObjectiveVersion.version.desc()).first()
    if not prev:
        raise HTTPException(404, "No prior version found")
    return build_diff_view(db, current=obj, previous_version=prev)


@router.post("/{obj_id}/cascade")
def trigger_cascade(
    obj_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    """Manually trigger AI cascade for an ACTIVE parent OKR (owner or admin)."""
    org_id = payload.get("org_id", "")
    user = _actor(db, payload)
    role = normalize_role(user.system_role)

    obj = _get_okr(db, obj_id, org_id)
    if (obj.okr_status or "").upper() != "ACTIVE":
        raise HTTPException(400, "Parent OKR must be ACTIVE")
    if role not in (SystemRole.SUPER_ADMIN, SystemRole.CEO) and obj.owner_id != user.id:
        raise HTTPException(403, "Only the parent OKR owner or admin may trigger cascade")

    background_tasks.add_task(schedule_cascade_for_active_okr, obj.id, org_id)
    return {"message": "Cascade generation scheduled", "parent_id": obj.id}


@router.get("/ai-drafts")
def list_ai_drafts(
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
    status: str = "",
):
    """List AI-generated draft OKRs visible to the current user."""
    org_id = payload.get("org_id", "")
    user = _actor(db, payload)
    role = normalize_role(user.system_role)

    q = db.query(Objective).filter(
        Objective.org_id == org_id,
        Objective.ai_generated == True,
    )

    statuses = [
        OKR_STATUS_AI_DRAFT,
        OKR_STATUS_UNDER_REVIEW,
        OKR_STATUS_PENDING_PARENT,
        "AI_REJECTED",
    ]
    if status:
        q = q.filter(Objective.okr_status == status.upper())
    else:
        q = q.filter(Objective.okr_status.in_(statuses))

    if role not in (SystemRole.SUPER_ADMIN, SystemRole.CEO):
        q = q.filter(Objective.owner_id == user.id)

    objs = q.order_by(Objective.created_at.desc()).all()
    return [ai_draft_to_dict(o, db) for o in objs]


@router.get("/parent-approval-queue")
def parent_approval_queue(
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    """OKRs pending parent approval after child-level review."""
    org_id = payload.get("org_id", "")
    user_id = payload.get("sub", "")

    objs = (
        db.query(Objective)
        .filter(
            Objective.org_id == org_id,
            Objective.okr_status == OKR_STATUS_PENDING_PARENT,
            Objective.pending_approver_user_id == user_id,
        )
        .order_by(Objective.submitted_for_parent_approval_at.desc())
        .all()
    )
    return [ai_draft_to_dict(o, db) for o in objs]


@router.put("/{obj_id}/review")
def review_ai_draft(
    obj_id: str,
    body: ReviewUpdateBody,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    """Child OKR owner edits an AI draft (starts UNDER_REVIEW)."""
    org_id = payload.get("org_id", "")
    user = _actor(db, payload)
    obj = _get_okr(db, obj_id, org_id)
    engine = AICascadeEngine(db)
    try:
        if body.title or body.description or body.key_results is not None:
            engine.update_ai_draft(
                obj,
                user,
                title=body.title,
                description=body.description,
                key_results=body.key_results,
            )
        else:
            engine.start_review(obj, user)
        db.commit()
        db.refresh(obj)
        return ai_draft_to_dict(obj, db)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/{obj_id}/submit-parent")
def submit_for_parent_approval(
    obj_id: str,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    org_id = payload.get("org_id", "")
    user = _actor(db, payload)
    obj = _get_okr(db, obj_id, org_id)
    engine = AICascadeEngine(db)
    try:
        engine.submit_for_parent_approval(obj, user)
        db.commit()
        db.refresh(obj)
        return ai_draft_to_dict(obj, db)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/{obj_id}/approve-parent")
def approve_parent_okr(
    obj_id: str,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    org_id = payload.get("org_id", "")
    user = _actor(db, payload)
    obj = _get_okr(db, obj_id, org_id)
    engine = AICascadeEngine(db)
    try:
        engine.approve_by_parent(obj, user)
        db.commit()
        db.refresh(obj)
        return ai_draft_to_dict(obj, db)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/{obj_id}/reject-parent")
def reject_parent_okr(
    obj_id: str,
    body: RejectBody,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    org_id = payload.get("org_id", "")
    user = _actor(db, payload)
    obj = _get_okr(db, obj_id, org_id)
    engine = AICascadeEngine(db)
    try:
        engine.reject_by_parent(obj, user, body.reason)
        db.commit()
        db.refresh(obj)
        return ai_draft_to_dict(obj, db)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/{obj_id}/reject-ai")
def reject_ai_draft(
    obj_id: str,
    body: RejectBody,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    org_id = payload.get("org_id", "")
    user = _actor(db, payload)
    obj = _get_okr(db, obj_id, org_id)
    engine = AICascadeEngine(db)
    try:
        engine.reject_ai_draft(obj, user, body.reason)
        db.commit()
        db.refresh(obj)
        return ai_draft_to_dict(obj, db)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/{obj_id}/regenerate")
def regenerate_ai_draft(
    obj_id: str,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    org_id = payload.get("org_id", "")
    user = _actor(db, payload)
    obj = _get_okr(db, obj_id, org_id)
    engine = AICascadeEngine(db)
    try:
        engine.regenerate(obj, user)
        db.commit()
        db.refresh(obj)
        return ai_draft_to_dict(obj, db)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
