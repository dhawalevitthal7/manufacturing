"""
Employee Review Service
Manages complete performance review lifecycle:
Self → Manager → Dept Head (optional) → HR Calibration → Finalized → Published
"""

from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import Optional, List
import logging

from server.performance_review_models import (
    EmployeePerformanceReview, ReviewState, ReviewSection, SectionType,
    ReviewAuditLog, ReviewRating
)
from server.models import User
from server.services.manager_resolution import resolve_dept_head_for_quarterly_moderation

logger = logging.getLogger(__name__)


def _state_str(state) -> str:
    if state is None:
        return ""
    return state.value if hasattr(state, "value") else str(state)


class EmployeeReviewService:
    """
    Manages complete employee performance review workflow.
    Handles state transitions, validation, and audit logging.
    """

    def __init__(self, db: Session):
        self.db = db

    # ─────────────────────────────────────────────────────────────────────────
    # REVIEW CREATION & INITIALIZATION
    # ─────────────────────────────────────────────────────────────────────────

    def create_performance_review(
        self,
        org_id: str,
        employee_id: str,
        manager_id: str,
        review_cycle_id: str,
        review_period_start: datetime = None,
        review_period_end: datetime = None,
        skip_level_manager_id: str = None,
        hr_reviewer_id: str = None,
        is_probation_review: bool = False,
        requires_dept_moderation: bool = None,
    ) -> EmployeePerformanceReview:
        """
        Create new performance review.
        Validates employee-manager relationship.
        """
        # Check for existing review (one per cycle)
        existing = self.db.query(EmployeePerformanceReview).filter(
            EmployeePerformanceReview.employee_id == employee_id,
            EmployeePerformanceReview.review_cycle_id == review_cycle_id
        ).first()
        
        if existing:
            raise ValueError(
                f"Review already exists for employee {employee_id} in cycle {review_cycle_id}"
            )
        
        dept_head_id = resolve_dept_head_for_quarterly_moderation(self.db, employee_id, org_id)
        if requires_dept_moderation is None:
            requires_dept_moderation = bool(dept_head_id)

        review = EmployeePerformanceReview(
            org_id=org_id,
            employee_id=employee_id,
            manager_id=manager_id,
            review_cycle_id=review_cycle_id,
            review_period_start=review_period_start,
            review_period_end=review_period_end,
            skip_level_manager_id=None,  # Regional/CEO do not review plant employees
            skip_level_required=False,
            hr_reviewer_id=hr_reviewer_id,
            dept_head_reviewer_id=dept_head_id,
            requires_dept_moderation=requires_dept_moderation,
            current_state=ReviewState.DRAFT.value,
            is_probation_review=is_probation_review
        )
        
        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)
        
        # Audit log
        self._log_action(
            performance_review_id=review.id,
            action="CREATED",
            actor_user_id="SYSTEM",
            new_state=ReviewState.DRAFT.value
        )
        
        logger.info(f"Created performance review: {review.id} for {employee_id}")
        return review

    # ─────────────────────────────────────────────────────────────────────────
    # SELF REVIEW STAGE
    # ─────────────────────────────────────────────────────────────────────────

    def submit_self_review(
        self,
        review_id: str,
        user_id: str,
        achievements: str,
        okr_self_assessment: list = None,
        strengths: str = None,
        challenges: str = None,
        growth_areas: list = None,
        evidence: str = None
    ) -> EmployeePerformanceReview:
        """
        Employee submits self-review.
        Validates state and user authorization.
        """
        review = self.db.query(EmployeePerformanceReview).filter(
            EmployeePerformanceReview.id == review_id
        ).first()
        
        if not review:
            raise ValueError(f"Review not found: {review_id}")
        
        # Validate state
        if _state_str(review.current_state) != ReviewState.DRAFT.value:
            raise ValueError(
                f"Cannot submit self-review in state {review.current_state}"
            )
        
        # Validate user is the employee
        if user_id != review.employee_id:
            raise ValueError("Only the employee can submit self-review")
        
        # Create or update self-review section
        self_section = self.db.query(ReviewSection).filter(
            ReviewSection.performance_review_id == review_id,
            ReviewSection.section_type == SectionType.SELF
        ).first()
        
        if not self_section:
            self_section = ReviewSection(
                performance_review_id=review_id,
                section_type=SectionType.SELF,
                submitted_by_user_id=user_id
            )
        
        self_section.self_achievements = achievements
        self_section.self_okr_assessment = okr_self_assessment or []
        self_section.self_strengths = strengths
        self_section.self_challenges = challenges
        self_section.self_growth_areas = growth_areas or []
        self_section.self_evidence = evidence
        self_section.submitted_at = datetime.utcnow()
        
        self.db.add(self_section)
        
        # Update review state
        old_state = review.current_state
        review.current_state = ReviewState.SELF_SUBMITTED.value
        review.self_review_id = self_section.id
        review.self_submitted_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(review)
        
        # Audit log
        self._log_action(
            performance_review_id=review_id,
            action="SELF_REVIEW_SUBMITTED",
            actor_user_id=user_id,
            old_state=old_state,
            new_state=review.current_state
        )
        
        logger.info(f"Self-review submitted for review {review_id}")
        return review

    # ─────────────────────────────────────────────────────────────────────────
    # MANAGER REVIEW STAGE
    # ─────────────────────────────────────────────────────────────────────────

    def submit_manager_review(
        self,
        review_id: str,
        manager_id: str,
        okr_outcomes_assessment: str = None,
        behavioral_scores: dict = None,
        collaboration_assessment: str = None,
        ownership_assessment: str = None,
        accountability_assessment: str = None,
        execution_quality_assessment: str = None,
        manager_feedback: str = None,
        promotion_eligible: bool = False,
        promotion_recommended: bool = False,
        pip_needed: bool = False,
        attrition_risk: str = None
    ) -> EmployeePerformanceReview:
        """
        Manager submits review assessment.
        Must be in SELF_SUBMITTED or PEER_REVIEW state.
        """
        review = self.db.query(EmployeePerformanceReview).filter(
            EmployeePerformanceReview.id == review_id
        ).first()
        
        if not review:
            raise ValueError(f"Review not found: {review_id}")
        
        # Validate state
        if _state_str(review.current_state) not in [
            ReviewState.SELF_SUBMITTED.value,
            ReviewState.PEER_REVIEW.value,
        ]:
            raise ValueError(
                f"Cannot submit manager review in state {review.current_state}"
            )
        
        # Validate manager authorization
        if manager_id != review.manager_id:
            from server.services.manager_resolution import can_coach_employee

            if not can_coach_employee(
                self.db, manager_id, review.employee_id, review.manager_id
            ):
                raise ValueError("Only the assigned manager can submit manager review")
        
        # Create or update manager section
        manager_section = self.db.query(ReviewSection).filter(
            ReviewSection.performance_review_id == review_id,
            ReviewSection.section_type == SectionType.MANAGER
        ).first()
        
        if not manager_section:
            manager_section = ReviewSection(
                performance_review_id=review_id,
                section_type=SectionType.MANAGER,
                submitted_by_user_id=manager_id
            )
        
        manager_section.manager_okr_outcomes = okr_outcomes_assessment
        manager_section.manager_behavioral_scores = behavioral_scores or {}
        manager_section.manager_collaboration = collaboration_assessment
        manager_section.manager_ownership = ownership_assessment
        manager_section.manager_accountability = accountability_assessment
        manager_section.manager_execution_quality = execution_quality_assessment
        manager_section.manager_feedback = manager_feedback
        manager_section.manager_promotion_eligible = promotion_eligible
        manager_section.manager_promotion_recommended = promotion_recommended
        manager_section.manager_pip_needed = pip_needed
        manager_section.submitted_at = datetime.utcnow()
        
        self.db.add(manager_section)
        
        # Update review
        old_state = review.current_state
        
        # Manufacturing quarterly: manager → dept head (optional) → HR — not regional/CEO
        if review.requires_dept_moderation and review.dept_head_reviewer_id:
            next_state = ReviewState.DEPT_HEAD_MODERATION.value
        else:
            next_state = ReviewState.HR_CALIBRATION.value

        review.current_state = next_state
        review.manager_review_id = manager_section.id
        review.manager_review_submitted_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(review)
        
        # Audit log
        self._log_action(
            performance_review_id=review_id,
            action="MANAGER_REVIEW_SUBMITTED",
            actor_user_id=manager_id,
            old_state=old_state,
            new_state=review.current_state
        )
        
        logger.info(f"Manager review submitted for review {review_id}")
        return review

    # ─────────────────────────────────────────────────────────────────────────
    # DEPARTMENT HEAD MODERATION (Optional — manufacturing quarterly)
    # ─────────────────────────────────────────────────────────────────────────

    def submit_dept_head_moderation(
        self,
        review_id: str,
        dept_head_id: str,
        moderation_notes: str = None,
        endorse_manager_rating: bool = True,
    ) -> EmployeePerformanceReview:
        """Department head moderates manager review before HR calibration."""
        review = self.db.query(EmployeePerformanceReview).filter(
            EmployeePerformanceReview.id == review_id
        ).first()
        if not review:
            raise ValueError(f"Review not found: {review_id}")
        if _state_str(review.current_state) != ReviewState.DEPT_HEAD_MODERATION.value:
            raise ValueError(f"Cannot moderate in state {review.current_state}")
        if dept_head_id != review.dept_head_reviewer_id:
            raise ValueError("Only assigned department head can moderate")

        section = ReviewSection(
            performance_review_id=review_id,
            section_type=SectionType.HR_CALIBRATION,
            submitted_by_user_id=dept_head_id,
        )
        section.submitted_at = datetime.utcnow()
        self.db.add(section)

        old_state = review.current_state
        review.current_state = ReviewState.HR_CALIBRATION.value
        review.calibration_notes = moderation_notes
        review.dept_head_reviewer_id = dept_head_id

        self.db.commit()
        self.db.refresh(review)
        self._log_action(
            performance_review_id=review_id,
            action="DEPT_HEAD_MODERATION",
            actor_user_id=dept_head_id,
            old_state=old_state,
            new_state=review.current_state,
            changes={"endorse_manager_rating": endorse_manager_rating},
        )
        return review

    # ─────────────────────────────────────────────────────────────────────────
    # SKIP-LEVEL REVIEW STAGE (Legacy — not used for plant employee reviews)
    # ─────────────────────────────────────────────────────────────────────────

    def submit_skip_level_review(
        self,
        review_id: str,
        skip_level_manager_id: str,
        executive_perspective: str = None,
        strategic_impact_assessment: str = None,
        leadership_potential: bool = False,
        succession_ready: bool = False,
        recommended_development: str = None
    ) -> EmployeePerformanceReview:
        """
        Skip-level manager submits review (optional, for leadership roles).
        """
        review = self.db.query(EmployeePerformanceReview).filter(
            EmployeePerformanceReview.id == review_id
        ).first()
        
        if not review:
            raise ValueError(f"Review not found: {review_id}")
        
        # Validate state
        if _state_str(review.current_state) != ReviewState.SKIP_LEVEL_REVIEW.value:
            raise ValueError(
                f"Cannot submit skip-level review in state {review.current_state}"
            )
        
        # Validate authorization
        if skip_level_manager_id != review.skip_level_manager_id:
            raise ValueError("Only the assigned skip-level manager can submit")
        
        # Create section
        skip_section = ReviewSection(
            performance_review_id=review_id,
            section_type=SectionType.SKIP_LEVEL,
            submitted_by_user_id=skip_level_manager_id
        )
        
        skip_section.skip_level_perspective = executive_perspective
        skip_section.skip_level_strategic_impact = strategic_impact_assessment
        skip_section.skip_level_leadership_potential = leadership_potential
        skip_section.skip_level_succession_ready = succession_ready
        skip_section.skip_level_recommended_development = recommended_development
        skip_section.submitted_at = datetime.utcnow()
        
        self.db.add(skip_section)
        
        # Update review
        old_state = review.current_state
        review.current_state = ReviewState.HR_CALIBRATION.value
        review.skip_level_review_id = skip_section.id
        review.skip_level_submitted_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(review)
        
        # Audit log
        self._log_action(
            performance_review_id=review_id,
            action="SKIP_LEVEL_REVIEW_SUBMITTED",
            actor_user_id=skip_level_manager_id,
            old_state=old_state,
            new_state=review.current_state
        )
        
        logger.info(f"Skip-level review submitted for review {review_id}")
        return review

    # ─────────────────────────────────────────────────────────────────────────
    # HR CALIBRATION STAGE
    # ─────────────────────────────────────────────────────────────────────────

    def submit_hr_calibration(
        self,
        review_id: str,
        hr_reviewer_id: str,
        calibration_notes: str = None,
        final_score: float = None,
        final_rating: str = None
    ) -> EmployeePerformanceReview:
        """
        HR submits final calibration and rating.
        """
        review = self.db.query(EmployeePerformanceReview).filter(
            EmployeePerformanceReview.id == review_id
        ).first()
        
        if not review:
            raise ValueError(f"Review not found: {review_id}")
        
        # Create HR calibration section
        hr_section = ReviewSection(
            performance_review_id=review_id,
            section_type=SectionType.HR_CALIBRATION,
            submitted_by_user_id=hr_reviewer_id
        )
        hr_section.submitted_at = datetime.utcnow()
        
        self.db.add(hr_section)
        
        # Update review with final ratings
        old_state = review.current_state
        review.current_state = ReviewState.HR_CALIBRATION.value
        review.hr_calibration_id = hr_section.id
        review.hr_calibration_submitted_at = datetime.utcnow()
        review.hr_reviewer_id = hr_reviewer_id
        review.calibration_notes = calibration_notes
        review.final_score = final_score or 50.0
        review.final_rating = final_rating
        
        self.db.commit()
        self.db.refresh(review)
        
        # Audit log
        self._log_action(
            performance_review_id=review_id,
            action="HR_CALIBRATION_SUBMITTED",
            actor_user_id=hr_reviewer_id,
            old_state=old_state,
            new_state=review.current_state,
            changes={"final_score": final_score, "final_rating": final_rating}
        )
        
        logger.info(f"HR calibration submitted for review {review_id}")
        return review

    # ─────────────────────────────────────────────────────────────────────────
    # FINALIZE & PUBLISH
    # ─────────────────────────────────────────────────────────────────────────

    def finalize_review(self, review_id: str) -> EmployeePerformanceReview:
        """
        Mark review as FINALIZED (ready for publication).
        Locks rating from further changes.
        """
        review = self.db.query(EmployeePerformanceReview).filter(
            EmployeePerformanceReview.id == review_id
        ).first()
        
        if not review:
            raise ValueError(f"Review not found: {review_id}")
        
        # Validate all sections completed
        if not review.final_score or not review.final_rating:
            raise ValueError("Review must have final score and rating before finalization")
        
        old_state = review.current_state
        review.current_state = ReviewState.FINALIZED.value
        review.finalized_at = datetime.utcnow()
        review.rating_locked = True
        
        self.db.commit()
        self.db.refresh(review)
        
        # Audit log
        self._log_action(
            performance_review_id=review_id,
            action="FINALIZED",
            actor_user_id=review.hr_reviewer_id,
            old_state=old_state,
            new_state=review.current_state
        )
        
        logger.info(f"Review {review_id} finalized")
        return review

    def publish_review(self, review_id: str) -> EmployeePerformanceReview:
        """
        Publish review (make visible to employee).
        """
        review = self.db.query(EmployeePerformanceReview).filter(
            EmployeePerformanceReview.id == review_id
        ).first()
        
        if not review:
            raise ValueError(f"Review not found: {review_id}")
        
        if review.current_state != ReviewState.FINALIZED.value:
            raise ValueError(f"Can only publish FINALIZED reviews")
        
        old_state = review.current_state
        review.current_state = ReviewState.PUBLISHED.value
        review.published_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(review)
        
        # Audit log
        self._log_action(
            performance_review_id=review_id,
            action="PUBLISHED",
            actor_user_id="SYSTEM",
            old_state=old_state,
            new_state=review.current_state
        )
        
        logger.info(f"Review {review_id} published to employee")
        return review

    # ─────────────────────────────────────────────────────────────────────────
    # AUDIT LOGGING
    # ─────────────────────────────────────────────────────────────────────────

    def _log_action(
        self,
        performance_review_id: str,
        action: str,
        actor_user_id: str,
        old_state: str = None,
        new_state: str = None,
        changes: dict = None,
        notes: str = None
    ):
        """Log review action for audit trail"""
        log = ReviewAuditLog(
            performance_review_id=performance_review_id,
            action=action,
            actor_user_id=actor_user_id,
            old_state=old_state,
            new_state=new_state,
            changes=changes,
            notes=notes
        )
        
        self.db.add(log)
        self.db.commit()

    def get_audit_trail(self, review_id: str) -> List[ReviewAuditLog]:
        """Get full audit trail for a review"""
        return self.db.query(ReviewAuditLog).filter(
            ReviewAuditLog.performance_review_id == review_id
        ).order_by(ReviewAuditLog.action_timestamp).all()
