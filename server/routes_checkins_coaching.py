"""
Coaching/monitoring check-in APIs — NOT approval workflows.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from server.database import get_db
from server.models import User
from server.performance_review_models import ContinuousCheckin, CheckinComment
from server.services.checkin_coaching_service import CheckinCoachingService
from server.services.okr_review_integration import build_okr_progress_snapshot
from server.services.manager_resolution import resolve_immediate_manager_for_checkin
from server.roles import normalize_role, SystemRole

router = APIRouter(prefix="/api/reviews/checkins", tags=["checkins-coaching"])


def _user_name(db: Session, uid: Optional[str]) -> Optional[str]:
    if not uid:
        return None
    u = db.query(User).filter(User.id == uid).first()
    return u.name if u else None


def _comment_dict(c: CheckinComment, db: Session) -> Dict[str, Any]:
    return {
        "id": c.id,
        "checkin_id": c.checkin_id,
        "commented_by_user_id": c.commented_by_user_id,
        "commented_by_name": _user_name(db, c.commented_by_user_id),
        "parent_comment_id": c.parent_comment_id,
        "comment": c.comment,
        "comment_type": c.comment_type,
        "sentiment": c.sentiment,
        "is_system_event": c.is_system_event,
        "commented_at": c.commented_at.isoformat() if c.commented_at else None,
    }


def _checkin_full(c: ContinuousCheckin, db: Session) -> Dict[str, Any]:
    ws = c.workflow_status or c.status
    employee = db.query(User).filter(User.id == c.employee_id).first()
    return {
        "id": c.id,
        "employee_id": c.employee_id,
        "employee_name": _user_name(db, c.employee_id),
        "employee_role": employee.system_role if employee else None,
        "manager_id": c.manager_id,
        "manager_name": _user_name(db, c.manager_id),
        "checkin_week": c.checkin_week,
        "achievements": c.achievements or "",
        "key_wins": c.key_wins or [],
        "blockers": c.blockers or "",
        "risks": c.risks or [],
        "support_needed": c.support_needed,
        "confidence_score": c.confidence_score,
        "engagement_score": c.engagement_score,
        "employee_mood": c.employee_mood.value if hasattr(c.employee_mood, "value") else c.employee_mood,
        "okr_progress_snapshot": c.okr_progress_snapshot,
        "progress_notes": c.progress_notes,
        "workflow_status": ws,
        "status": ws,
        "acknowledged_at": c.acknowledged_at.isoformat() if c.acknowledged_at else None,
        "performance_concern_flag": c.performance_concern_flag,
        "concern_notes": c.concern_notes,
        "escalation_reason": c.escalation_reason,
        "escalation_target_user_id": c.escalation_target_user_id,
        "escalation_target_name": _user_name(db, c.escalation_target_user_id),
        "action_items": c.action_items or [],
        "coaching_notes": c.coaching_notes,
        "manager_feedback": c.manager_feedback,
        "submitted_at": c.submitted_at.isoformat() if c.submitted_at else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


class CheckinCreateBody(BaseModel):
    employee_id: Optional[str] = None
    checkin_week: int
    achievements: str
    blockers: str = ""
    key_wins: List[str] = []
    risks: List[Dict[str, Any]] = []
    support_needed: Optional[str] = None
    confidence_score: Optional[float] = 75
    engagement_score: Optional[int] = 7
    employee_mood: Optional[str] = "NEUTRAL"
    progress_notes: Optional[str] = None


class CommentBody(BaseModel):
    comment: str
    parent_comment_id: Optional[str] = None


class ActionItemsBody(BaseModel):
    action_items: List[Dict[str, Any]]
    coaching_notes: Optional[str] = None


class EscalateBody(BaseModel):
    reason: str
    notes: Optional[str] = None


class ConcernBody(BaseModel):
    concern_notes: str


class ResolveBody(BaseModel):
    resolution_notes: Optional[str] = None


@router.post("")
def submit_checkin(
    body: CheckinCreateBody,
    db: Session = Depends(get_db),
    org_id: str = "",
    user_id: str = "",
    role: str = "",
):
    employee_id = body.employee_id or user_id
    if employee_id != user_id:
        role = normalize_role(role)
        leaders = {SystemRole.MANAGER.value, SystemRole.SUPERVISOR.value, SystemRole.TEAM_LEAD.value,
                   SystemRole.DEPT_HEAD.value, SystemRole.HR_HEAD.value, SystemRole.SUPER_ADMIN.value}
        if role not in leaders:
            raise HTTPException(403, "Cannot submit for another employee")

    snapshot = build_okr_progress_snapshot(db, employee_id, org_id)
    svc = CheckinCoachingService(db)
    try:
        checkin = svc.submit_checkin(
            employee_id=employee_id,
            org_id=org_id,
            checkin_week=body.checkin_week,
            achievements=body.achievements,
            blockers=body.blockers,
            confidence_score=body.confidence_score or 75,
            engagement_score=body.engagement_score or 7,
            employee_mood=body.employee_mood or "NEUTRAL",
            key_wins=body.key_wins,
            risks=body.risks,
            support_needed=body.support_needed,
            okr_progress_snapshot=snapshot,
            progress_notes=body.progress_notes,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    result = _checkin_full(checkin, db)
    result["comments"] = [_comment_dict(c, db) for c in svc.get_comments(checkin.id)]
    return result


@router.get("/inbox")
def manager_inbox(
    db: Session = Depends(get_db),
    user_id: str = "",
    include_resolved: bool = False,
):
    """Team check-in queue for immediate manager only."""
    svc = CheckinCoachingService(db)
    rows = svc.get_manager_inbox(user_id, include_resolved=include_resolved)
    return [_checkin_full(c, db) for c in rows]


@router.get("/timeline/{employee_id}")
def employee_timeline(employee_id: str, db: Session = Depends(get_db), user_id: str = "", limit: int = 24):
    svc = CheckinCoachingService(db)
    rows = svc.get_employee_timeline(employee_id, limit=limit)
    return [_checkin_full(c, db) for c in rows]


@router.get("/notifications")
def list_notifications(db: Session = Depends(get_db), user_id: str = "", unread_only: bool = True):
    svc = CheckinCoachingService(db)
    notes = svc.list_notifications(user_id, unread_only=unread_only)
    return [
        {
            "id": n.id,
            "checkin_id": n.checkin_id,
            "event_type": n.event_type,
            "title": n.title,
            "body": n.body,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notes
    ]


@router.post("/notifications/read")
def mark_read(
    db: Session = Depends(get_db),
    user_id: str = "",
    body: Dict[str, Any] = Body(default={}),
):
    ids = body.get("notification_ids")
    svc = CheckinCoachingService(db)
    count = svc.mark_notifications_read(user_id, ids)
    return {"marked_read": count}


@router.get("/{checkin_id}")
def get_checkin_detail(checkin_id: str, db: Session = Depends(get_db)):
    c = db.query(ContinuousCheckin).filter(ContinuousCheckin.id == checkin_id).first()
    if not c:
        raise HTTPException(404)
    svc = CheckinCoachingService(db)
    result = _checkin_full(c, db)
    result["comments"] = [_comment_dict(cm, db) for cm in svc.get_comments(checkin_id)]
    return result


@router.post("/{checkin_id}/acknowledge")
def acknowledge(checkin_id: str, db: Session = Depends(get_db), user_id: str = ""):
    try:
        c = CheckinCoachingService(db).acknowledge(checkin_id, user_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _checkin_full(c, db)


@router.post("/{checkin_id}/comments")
def add_comment(checkin_id: str, body: CommentBody, db: Session = Depends(get_db), user_id: str = ""):
    try:
        CheckinCoachingService(db).add_coaching_comment(
            checkin_id, user_id, body.comment, body.parent_comment_id
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return get_checkin_detail(checkin_id, db)


@router.post("/{checkin_id}/action-items")
def assign_actions(checkin_id: str, body: ActionItemsBody, db: Session = Depends(get_db), user_id: str = ""):
    try:
        c = CheckinCoachingService(db).assign_action_items(
            checkin_id, user_id, body.action_items, body.coaching_notes
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _checkin_full(c, db)


@router.post("/{checkin_id}/escalate")
def escalate(checkin_id: str, body: EscalateBody, db: Session = Depends(get_db), user_id: str = ""):
    try:
        c = CheckinCoachingService(db).escalate(checkin_id, user_id, body.reason, body.notes)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _checkin_full(c, db)


@router.post("/{checkin_id}/flag-concern")
def flag_concern(checkin_id: str, body: ConcernBody, db: Session = Depends(get_db), user_id: str = ""):
    try:
        c = CheckinCoachingService(db).flag_performance_concern(checkin_id, user_id, body.concern_notes)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _checkin_full(c, db)


@router.post("/{checkin_id}/resolve")
def resolve_checkin(checkin_id: str, body: ResolveBody, db: Session = Depends(get_db), user_id: str = ""):
    try:
        c = CheckinCoachingService(db).resolve(checkin_id, user_id, body.resolution_notes)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _checkin_full(c, db)


class ApproveBody(BaseModel):
    approval_notes: Optional[str] = None


@router.post("/{checkin_id}/approve")
def approve_checkin(
    checkin_id: str,
    body: ApproveBody,
    db: Session = Depends(get_db),
    user_id: str = "",
):
    try:
        c = CheckinCoachingService(db).approve_checkin(
            checkin_id, user_id, body.approval_notes
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _checkin_full(c, db)


@router.post("/{checkin_id}/close")
def close_checkin(checkin_id: str, db: Session = Depends(get_db), user_id: str = ""):
    try:
        c = CheckinCoachingService(db).close(checkin_id, user_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _checkin_full(c, db)
