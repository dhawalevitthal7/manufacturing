"""
Continuous check-in coaching workflow.

NOT an approval chain — employee → immediate manager only.
Exception escalation to department head for severe cases only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import or_

from server.models import User
from server.performance_review_models import (
    ContinuousCheckin,
    CheckinComment,
    CheckinEscalation,
    CheckinNotification,
    CheckinWorkflowStatus,
    CheckinEscalationReason,
)
from server.services.manager_resolution import (
    resolve_immediate_manager_for_checkin,
    resolve_dept_head_for_employee,
    get_subordinate_employee_ids,
    can_coach_employee,
)

# Manager inbox: needs attention
INBOX_STATUSES = (
    CheckinWorkflowStatus.SUBMITTED.value,
    CheckinWorkflowStatus.UNDER_REVIEW.value,
    CheckinWorkflowStatus.ACTION_REQUIRED.value,
    CheckinWorkflowStatus.ESCALATED.value,
)

LEADERSHIP_ROLES = {"MANAGER", "TEAM_LEAD", "SUPERVISOR", "DEPT_HEAD"}


def _sync_status_fields(checkin: ContinuousCheckin, workflow_status: str) -> None:
    checkin.workflow_status = workflow_status
    checkin.status = workflow_status


def _notify(
    db: Session,
    org_id: str,
    checkin_id: str,
    recipient_id: str,
    actor_id: Optional[str],
    event_type: str,
    title: str,
    body: Optional[str] = None,
) -> None:
    db.add(
        CheckinNotification(
            org_id=org_id,
            checkin_id=checkin_id,
            recipient_user_id=recipient_id,
            actor_user_id=actor_id,
            event_type=event_type,
            title=title,
            body=body,
        )
    )


def _add_comment(
    db: Session,
    checkin_id: str,
    user_id: str,
    comment: str,
    comment_type: str = "COACHING",
    parent_comment_id: Optional[str] = None,
    is_system: bool = False,
) -> CheckinComment:
    c = CheckinComment(
        checkin_id=checkin_id,
        commented_by_user_id=user_id,
        comment=comment,
        comment_type=comment_type,
        parent_comment_id=parent_comment_id,
        is_system_event=is_system,
    )
    db.add(c)
    return c


class CheckinCoachingService:
    def __init__(self, db: Session):
        self.db = db

    def submit_checkin(
        self,
        employee_id: str,
        org_id: str,
        checkin_week: int,
        achievements: str,
        blockers: str,
        confidence_score: float,
        engagement_score: int,
        employee_mood: str,
        key_wins: Optional[List[str]] = None,
        risks: Optional[List[dict]] = None,
        support_needed: Optional[str] = None,
        okr_progress_snapshot: Optional[dict] = None,
        progress_notes: Optional[str] = None,
    ) -> ContinuousCheckin:
        manager_id, _ = resolve_immediate_manager_for_checkin(
            self.db, employee_id, org_id
        )
        if not manager_id:
            raise ValueError(
                "No immediate manager found for check-in. Assign reporting relationship or team lead."
            )

        existing = (
            self.db.query(ContinuousCheckin)
            .filter(
                ContinuousCheckin.employee_id == employee_id,
                ContinuousCheckin.checkin_week == checkin_week,
                ContinuousCheckin.is_latest == True,
            )
            .first()
        )
        if existing:
            existing.is_latest = False

        checkin = ContinuousCheckin(
            org_id=org_id,
            employee_id=employee_id,
            manager_id=manager_id,
            checkin_week=checkin_week,
            checkin_date=datetime.utcnow(),
            submitted_by_user_id=employee_id,
            submitted_at=datetime.utcnow(),
            achievements=achievements,
            key_wins=key_wins or [],
            blockers=blockers,
            risks=risks or [],
            support_needed=support_needed,
            confidence_score=confidence_score,
            engagement_score=engagement_score,
            employee_mood=employee_mood,
            okr_progress_snapshot=okr_progress_snapshot,
            progress_notes=progress_notes,
            is_latest=True,
        )
        _sync_status_fields(checkin, CheckinWorkflowStatus.SUBMITTED.value)
        self.db.add(checkin)
        self.db.flush()

        _add_comment(
            self.db,
            checkin.id,
            employee_id,
            "Weekly check-in submitted.",
            comment_type="ACKNOWLEDGEMENT",
            is_system=True,
        )
        _notify(
            self.db,
            org_id,
            checkin.id,
            manager_id,
            employee_id,
            "SUBMITTED",
            "New team check-in",
            f"Week {checkin_week}: review and coach your direct report.",
        )
        employee = self.db.query(User).filter(User.id == employee_id).first()
        if employee and str(employee.system_role or "") in LEADERSHIP_ROLES:
            _notify(
                self.db,
                org_id,
                checkin.id,
                manager_id,
                employee_id,
                "LEADERSHIP_CHECKIN",
                "Leadership check-in submitted",
                f"{employee.name} ({employee.system_role}) submitted a check-in for your review.",
            )
        self.db.commit()
        self.db.refresh(checkin)
        return checkin

    def get_manager_inbox(
        self,
        manager_id: str,
        include_resolved: bool = False,
        limit: int = 50,
    ) -> List[ContinuousCheckin]:
        statuses = list(INBOX_STATUSES)
        if include_resolved:
            statuses.extend(
                [CheckinWorkflowStatus.RESOLVED.value, CheckinWorkflowStatus.CLOSED.value]
            )
        subordinate_ids = get_subordinate_employee_ids(self.db, manager_id)
        scope_filter = ContinuousCheckin.manager_id == manager_id
        if subordinate_ids:
            scope_filter = or_(
                ContinuousCheckin.manager_id == manager_id,
                ContinuousCheckin.employee_id.in_(subordinate_ids),
            )
        return (
            self.db.query(ContinuousCheckin)
            .filter(
                ContinuousCheckin.is_latest == True,
                ContinuousCheckin.workflow_status.in_(statuses),
                scope_filter,
            )
            .order_by(ContinuousCheckin.submitted_at.desc())
            .limit(limit)
            .all()
        )

    def get_employee_timeline(
        self, employee_id: str, limit: int = 24
    ) -> List[ContinuousCheckin]:
        return (
            self.db.query(ContinuousCheckin)
            .filter(
                ContinuousCheckin.employee_id == employee_id,
                ContinuousCheckin.is_latest == True,
            )
            .order_by(ContinuousCheckin.checkin_date.desc())
            .limit(limit)
            .all()
        )

    def get_comments(self, checkin_id: str) -> List[CheckinComment]:
        return (
            self.db.query(CheckinComment)
            .filter(CheckinComment.checkin_id == checkin_id)
            .order_by(CheckinComment.commented_at.asc())
            .all()
        )

    def acknowledge(self, checkin_id: str, manager_id: str) -> ContinuousCheckin:
        checkin = self._get_and_validate_manager(checkin_id, manager_id)
        if checkin.workflow_status not in (
            CheckinWorkflowStatus.SUBMITTED.value,
            CheckinWorkflowStatus.ACTION_REQUIRED.value,
        ):
            raise ValueError(f"Cannot acknowledge in state {checkin.workflow_status}")

        checkin.acknowledged_at = datetime.utcnow()
        checkin.acknowledged_by_user_id = manager_id
        _sync_status_fields(checkin, CheckinWorkflowStatus.UNDER_REVIEW.value)
        _add_comment(
            self.db, checkin_id, manager_id, "Acknowledged — under review.", "ACKNOWLEDGEMENT", is_system=True
        )
        _notify(
            self.db,
            checkin.org_id,
            checkin_id,
            checkin.employee_id,
            manager_id,
            "ACKNOWLEDGED",
            "Manager acknowledged your check-in",
        )
        self.db.commit()
        self.db.refresh(checkin)
        return checkin

    def add_coaching_comment(
        self,
        checkin_id: str,
        user_id: str,
        comment: str,
        parent_comment_id: Optional[str] = None,
    ) -> CheckinComment:
        checkin = self.db.query(ContinuousCheckin).filter(ContinuousCheckin.id == checkin_id).first()
        if not checkin:
            raise ValueError("Check-in not found")
        if user_id not in (checkin.employee_id, checkin.escalation_target_user_id) and not can_coach_employee(
            self.db, user_id, checkin.employee_id, checkin.manager_id
        ):
            raise ValueError("Not authorized to comment on this check-in")

        c = _add_comment(
            self.db, checkin_id, user_id, comment, "COACHING", parent_comment_id
        )
        if user_id == checkin.employee_id:
            recipient = checkin.manager_id
        elif can_coach_employee(
            self.db, user_id, checkin.employee_id, checkin.manager_id
        ):
            recipient = checkin.employee_id
        else:
            recipient = checkin.manager_id
        _notify(
            self.db,
            checkin.org_id,
            checkin_id,
            recipient,
            user_id,
            "COMMENT",
            "New comment on check-in",
            comment[:200],
        )
        if checkin.workflow_status == CheckinWorkflowStatus.SUBMITTED.value:
            _sync_status_fields(checkin, CheckinWorkflowStatus.UNDER_REVIEW.value)
        self.db.commit()
        self.db.refresh(c)
        return c

    def assign_action_items(
        self,
        checkin_id: str,
        manager_id: str,
        action_items: List[Dict[str, Any]],
        coaching_notes: Optional[str] = None,
    ) -> ContinuousCheckin:
        checkin = self._get_and_validate_manager(checkin_id, manager_id)
        checkin.action_items = action_items
        if coaching_notes:
            checkin.coaching_notes = coaching_notes
        _sync_status_fields(checkin, CheckinWorkflowStatus.ACTION_REQUIRED.value)
        _add_comment(
            self.db,
            checkin_id,
            manager_id,
            f"Action items assigned ({len(action_items)}).",
            "ACTION",
            is_system=True,
        )
        _notify(
            self.db,
            checkin.org_id,
            checkin_id,
            checkin.employee_id,
            manager_id,
            "ACTION",
            "Action required on your check-in",
            coaching_notes,
        )
        self.db.commit()
        self.db.refresh(checkin)
        return checkin

    def flag_performance_concern(
        self,
        checkin_id: str,
        manager_id: str,
        concern_notes: str,
    ) -> ContinuousCheckin:
        checkin = self._get_and_validate_manager(checkin_id, manager_id)
        checkin.performance_concern_flag = True
        checkin.concern_notes = concern_notes
        _add_comment(self.db, checkin_id, manager_id, concern_notes, "CONCERN")
        _notify(
            self.db,
            checkin.org_id,
            checkin_id,
            checkin.employee_id,
            manager_id,
            "CONCERN",
            "Performance concern flagged",
            concern_notes,
        )
        self.db.commit()
        self.db.refresh(checkin)
        return checkin

    def escalate(
        self,
        checkin_id: str,
        manager_id: str,
        reason: str,
        notes: Optional[str] = None,
    ) -> ContinuousCheckin:
        allowed = {e.value for e in CheckinEscalationReason}
        if reason not in allowed:
            reason = CheckinEscalationReason.OTHER.value

        checkin = self._get_and_validate_manager(checkin_id, manager_id)
        dept_head_id = resolve_dept_head_for_employee(
            self.db, checkin.employee_id, checkin.org_id
        )
        if not dept_head_id:
            raise ValueError("No department head available for escalation")

        checkin.escalated_at = datetime.utcnow()
        checkin.escalated_by_user_id = manager_id
        checkin.escalation_target_user_id = dept_head_id
        checkin.escalation_reason = reason
        _sync_status_fields(checkin, CheckinWorkflowStatus.ESCALATED.value)

        self.db.add(
            CheckinEscalation(
                checkin_id=checkin_id,
                org_id=checkin.org_id,
                escalated_by_user_id=manager_id,
                escalated_to_user_id=dept_head_id,
                reason=reason,
                notes=notes,
            )
        )
        _add_comment(
            self.db,
            checkin_id,
            manager_id,
            f"Escalated to department head: {reason}. {notes or ''}",
            "ESCALATION",
            is_system=True,
        )
        _notify(
            self.db,
            checkin.org_id,
            checkin_id,
            dept_head_id,
            manager_id,
            "ESCALATED",
            "Check-in escalated for your attention",
            notes,
        )
        self.db.commit()
        self.db.refresh(checkin)
        return checkin

    def resolve(self, checkin_id: str, actor_id: str, resolution_notes: Optional[str] = None) -> ContinuousCheckin:
        checkin = self.db.query(ContinuousCheckin).filter(ContinuousCheckin.id == checkin_id).first()
        if not checkin:
            raise ValueError("Check-in not found")
        if actor_id != checkin.escalation_target_user_id and not can_coach_employee(
            self.db, actor_id, checkin.employee_id, checkin.manager_id
        ):
            raise ValueError("Not authorized to resolve")

        checkin.resolved_at = datetime.utcnow()
        _sync_status_fields(checkin, CheckinWorkflowStatus.RESOLVED.value)
        if resolution_notes:
            _add_comment(self.db, checkin_id, actor_id, resolution_notes, "COACHING")
        _notify(
            self.db,
            checkin.org_id,
            checkin_id,
            checkin.employee_id,
            actor_id,
            "RESOLVED",
            "Your check-in has been resolved",
            resolution_notes,
        )
        esc = (
            self.db.query(CheckinEscalation)
            .filter(CheckinEscalation.checkin_id == checkin_id, CheckinEscalation.status == "OPEN")
            .first()
        )
        if esc:
            esc.status = "RESOLVED"
            esc.resolved_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(checkin)
        return checkin

    def approve_checkin(
        self,
        checkin_id: str,
        approver_id: str,
        approval_notes: Optional[str] = None,
    ) -> ContinuousCheckin:
        """Dept head / manager approves a submitted check-in (e.g. manager leadership check-in)."""
        checkin = self._get_and_validate_manager(checkin_id, approver_id)
        if checkin.workflow_status not in (
            CheckinWorkflowStatus.SUBMITTED.value,
            CheckinWorkflowStatus.UNDER_REVIEW.value,
            CheckinWorkflowStatus.ACTION_REQUIRED.value,
        ):
            raise ValueError(f"Cannot approve check-in in state {checkin.workflow_status}")

        if not checkin.acknowledged_at:
            checkin.acknowledged_at = datetime.utcnow()
            checkin.acknowledged_by_user_id = approver_id

        note = approval_notes or "Check-in reviewed and approved."
        _add_comment(self.db, checkin_id, approver_id, note, "APPROVAL")
        checkin.resolved_at = datetime.utcnow()
        _sync_status_fields(checkin, CheckinWorkflowStatus.RESOLVED.value)
        _notify(
            self.db,
            checkin.org_id,
            checkin_id,
            checkin.employee_id,
            approver_id,
            "APPROVED",
            "Your check-in was approved",
            note,
        )
        self.db.commit()
        self.db.refresh(checkin)
        return checkin

    def close(self, checkin_id: str, manager_id: str) -> ContinuousCheckin:
        checkin = self._get_and_validate_manager(checkin_id, manager_id)
        checkin.closed_at = datetime.utcnow()
        _sync_status_fields(checkin, CheckinWorkflowStatus.CLOSED.value)
        _add_comment(
            self.db, checkin_id, manager_id, "Check-in thread closed.", "ACKNOWLEDGEMENT", is_system=True
        )
        self.db.commit()
        self.db.refresh(checkin)
        return checkin

    def list_notifications(self, user_id: str, unread_only: bool = True, limit: int = 30) -> List[CheckinNotification]:
        q = self.db.query(CheckinNotification).filter(
            CheckinNotification.recipient_user_id == user_id
        )
        if unread_only:
            q = q.filter(CheckinNotification.is_read == False)
        return q.order_by(CheckinNotification.created_at.desc()).limit(limit).all()

    def mark_notifications_read(self, user_id: str, notification_ids: Optional[List[str]] = None) -> int:
        q = self.db.query(CheckinNotification).filter(
            CheckinNotification.recipient_user_id == user_id,
            CheckinNotification.is_read == False,
        )
        if notification_ids:
            q = q.filter(CheckinNotification.id.in_(notification_ids))
        count = 0
        for n in q.all():
            n.is_read = True
            count += 1
        self.db.commit()
        return count

    def _get_and_validate_manager(self, checkin_id: str, manager_id: str) -> ContinuousCheckin:
        checkin = self.db.query(ContinuousCheckin).filter(ContinuousCheckin.id == checkin_id).first()
        if not checkin:
            raise ValueError("Check-in not found")
        if not can_coach_employee(
            self.db, manager_id, checkin.employee_id, checkin.manager_id
        ):
            raise ValueError("Not authorized to coach on this check-in")
        return checkin
