"""
Leader-initiated performance reviews for direct and indirect reports.

Any higher-level role can initiate and run the AI review agent for employees
in their reporting subtree (manager, team lead, supervisor, dept head, etc.).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from server.models import User, ProgressSubmission, Objective, KeyResult
from server.performance_review_models import (
    ContinuousCheckin,
    EmployeePerformanceReview,
    PerformanceReviewCycle,
    ReviewState,
)
from server.services.employee_review_service import EmployeeReviewService, _state_str
from server.services.manager_resolution import (
    can_coach_employee,
    get_subordinate_employee_ids,
)
from server.services.okr_review_integration import (
    attach_okr_context_to_review,
    build_okr_progress_snapshot,
)


LEADER_ROLES_FOR_TEAM_REVIEWS = {
    "MANAGER",
    "TEAM_LEAD",
    "SUPERVISOR",
    "DEPT_HEAD",
    "PLANT_HEAD",
    "VP_OPERATIONS",
    "REGIONAL_HEAD",
    "HR_HEAD",
    "SUPER_ADMIN",
    "CEO",
    "CRO",
    "COO",
}


class PerformanceReviewTeamService:
    def __init__(self, db: Session):
        self.db = db

    def list_reviewable_team(
        self,
        actor_id: str,
        org_id: str,
        cycle_id: str,
    ) -> List[Dict[str, Any]]:
        """Employees below actor in the org tree with review status for a cycle."""
        subordinate_ids = get_subordinate_employee_ids(self.db, actor_id)
        if not subordinate_ids:
            return []

        employees = (
            self.db.query(User)
            .filter(
                User.id.in_(subordinate_ids),
                User.org_id == org_id,
                User.is_active == True,
            )
            .order_by(User.name.asc())
            .all()
        )

        cycle = (
            self.db.query(PerformanceReviewCycle)
            .filter(PerformanceReviewCycle.id == cycle_id)
            .first()
        )
        period_start = cycle.start_date if cycle else None
        period_end = cycle.end_date if cycle else None

        rows: List[Dict[str, Any]] = []
        for emp in employees:
            review = (
                self.db.query(EmployeePerformanceReview)
                .filter(
                    EmployeePerformanceReview.employee_id == emp.id,
                    EmployeePerformanceReview.review_cycle_id == cycle_id,
                )
                .first()
            )
            okr_snapshot = build_okr_progress_snapshot(self.db, emp.id, org_id)
            checkin_count = self._checkin_count(emp.id, period_start, period_end)
            progress_count = self._progress_count(emp.id, period_start, period_end)

            state = _state_str(review.current_state) if review else None
            ai_status = (review.ai_review_status or "NONE") if review else "NONE"

            rows.append(
                {
                    "employee_id": emp.id,
                    "employee_name": emp.name,
                    "employee_role": emp.system_role,
                    "employee_email": emp.email,
                    "review_id": review.id if review else None,
                    "review_state": state,
                    "ai_review_status": ai_status,
                    "manager_id": review.manager_id if review else None,
                    "manager_name": self._name(review.manager_id) if review else None,
                    "can_initiate": review is None,
                    "can_generate_ai": review is not None
                    and state in (ReviewState.DRAFT.value, ReviewState.SELF_SUBMITTED.value)
                    and ai_status != "SUBMITTED",
                    "can_open": review is not None,
                    "okr_count": okr_snapshot.get("objective_count", 0),
                    "okr_avg_progress": okr_snapshot.get("avg_progress", 0),
                    "checkin_count": checkin_count,
                    "progress_submission_count": progress_count,
                }
            )
        return rows

    def initiate_review(
        self,
        actor_id: str,
        org_id: str,
        employee_id: str,
        cycle_id: str,
    ) -> EmployeePerformanceReview:
        if not can_coach_employee(self.db, actor_id, employee_id):
            raise ValueError("You can only initiate reviews for members in your team")

        cycle = (
            self.db.query(PerformanceReviewCycle)
            .filter(PerformanceReviewCycle.id == cycle_id)
            .first()
        )
        if not cycle:
            raise ValueError("Review cycle not found")

        existing = (
            self.db.query(EmployeePerformanceReview)
            .filter(
                EmployeePerformanceReview.employee_id == employee_id,
                EmployeePerformanceReview.review_cycle_id == cycle_id,
            )
            .first()
        )
        if existing:
            return existing

        review_svc = EmployeeReviewService(self.db)
        review = review_svc.create_performance_review(
            org_id=org_id,
            employee_id=employee_id,
            manager_id=actor_id,
            review_cycle_id=cycle_id,
            review_period_start=cycle.start_date,
            review_period_end=cycle.end_date,
        )
        attach_okr_context_to_review(self.db, review)

        review_svc._log_action(
            performance_review_id=review.id,
            action="MANAGER_INITIATED",
            actor_user_id=actor_id,
            new_state=ReviewState.DRAFT.value,
        )
        return review

    def _checkin_count(
        self,
        employee_id: str,
        start: Optional[datetime],
        end: Optional[datetime],
    ) -> int:
        q = self.db.query(ContinuousCheckin).filter(
            ContinuousCheckin.employee_id == employee_id,
            ContinuousCheckin.is_latest == True,
        )
        if start:
            q = q.filter(ContinuousCheckin.checkin_date >= start)
        if end:
            q = q.filter(ContinuousCheckin.checkin_date <= end)
        return q.count()

    def _progress_count(
        self,
        employee_id: str,
        start: Optional[datetime],
        end: Optional[datetime],
    ) -> int:
        q = self.db.query(ProgressSubmission).filter(
            ProgressSubmission.submitted_by_id == employee_id
        )
        if start:
            q = q.filter(ProgressSubmission.created_at >= start)
        if end:
            q = q.filter(ProgressSubmission.created_at <= end)
        return q.count()

    def _name(self, user_id: Optional[str]) -> Optional[str]:
        if not user_id:
            return None
        u = self.db.query(User).filter(User.id == user_id).first()
        return u.name if u else None
