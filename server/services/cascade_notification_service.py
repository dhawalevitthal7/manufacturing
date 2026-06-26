"""Notifications for AI cascade OKR workflow."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from server.models import OkrCascadeNotification, Objective, User

EVENT_AI_DRAFT_READY = "AI_DRAFT_READY"
EVENT_REVIEW_PENDING = "REVIEW_PENDING"
EVENT_SUBMITTED = "SUBMITTED"
EVENT_APPROVED = "APPROVED"
EVENT_REJECTED = "REJECTED"
EVENT_REGENERATED = "REGENERATED"


def notify_cascade_event(
    db: Session,
    *,
    org_id: str,
    objective_id: str,
    recipient_user_id: str,
    event_type: str,
    title: str,
    body: Optional[str] = None,
    actor_user_id: Optional[str] = None,
) -> OkrCascadeNotification:
    notif = OkrCascadeNotification(
        id=str(uuid.uuid4()),
        org_id=org_id,
        objective_id=objective_id,
        recipient_user_id=recipient_user_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        title=title,
        body=body,
        is_read=False,
    )
    db.add(notif)
    db.flush()
    return notif


def notify_ai_draft_ready(
    db: Session, *, okr: Objective, parent: Objective, owner: User
) -> None:
    notify_cascade_event(
        db,
        org_id=okr.org_id,
        objective_id=okr.id,
        recipient_user_id=owner.id,
        actor_user_id=parent.owner_id,
        event_type=EVENT_AI_DRAFT_READY,
        title=f"AI suggested OKR ready: {okr.title[:80]}",
        body=(
            f"A new AI-suggested {okr.level} OKR was generated from "
            f"«{parent.title}». Review and submit for parent approval."
        ),
    )


def notify_submitted_for_parent(
    db: Session, *, okr: Objective, parent: Objective, actor: User
) -> None:
    notify_cascade_event(
        db,
        org_id=okr.org_id,
        objective_id=okr.id,
        recipient_user_id=parent.owner_id,
        actor_user_id=actor.id,
        event_type=EVENT_SUBMITTED,
        title=f"OKR pending your approval: {okr.title[:80]}",
        body=f"{actor.name} submitted an AI-reviewed {okr.level} OKR for your approval.",
    )


def notify_parent_decision(
    db: Session,
    *,
    okr: Objective,
    actor: User,
    approved: bool,
    reason: Optional[str] = None,
) -> None:
    notify_cascade_event(
        db,
        org_id=okr.org_id,
        objective_id=okr.id,
        recipient_user_id=okr.owner_id,
        actor_user_id=actor.id,
        event_type=EVENT_APPROVED if approved else EVENT_REJECTED,
        title=(
            f"OKR approved: {okr.title[:60]}"
            if approved
            else f"OKR rejected: {okr.title[:60]}"
        ),
        body=reason if not approved else "Your OKR was approved and is now ACTIVE.",
    )


def notify_regenerated(
    db: Session, *, okr: Objective, actor: User
) -> None:
    notify_cascade_event(
        db,
        org_id=okr.org_id,
        objective_id=okr.id,
        recipient_user_id=okr.owner_id,
        actor_user_id=actor.id,
        event_type=EVENT_REGENERATED,
        title=f"OKR regenerated: {okr.title[:80]}",
        body="A new AI suggestion replaced the previous draft. Please review again.",
    )
