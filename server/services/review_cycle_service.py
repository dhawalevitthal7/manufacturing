"""
Review Cycle Service
Manages review cycle creation, lifecycle, and automation.
Integrates with existing OKR cycle system.
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional, Tuple
import logging

from server.performance_review_models import (
    PerformanceReviewCycle, ReviewCycleStatus, ReviewCycleType, EmployeePerformanceReview,
    ReviewState, ContinuousCheckin
)
from server.models import User, Organization, OrgNode
from server.roles import SystemRole, normalize_role

logger = logging.getLogger(__name__)


class ReviewCycleService:
    """
    Manages review cycle lifecycle:
    - Create cycles (weekly, monthly, quarterly, half-yearly, annual)
    - Auto-lock/unlock based on dates
    - Auto-publish reviews
    - Manage submission windows
    - Create performance reviews for employees in cycle scope
    """

    def __init__(self, db: Session):
        self.db = db

    # ─────────────────────────────────────────────────────────────────────────
    # CYCLE MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────────

    def create_review_cycle(
        self,
        org_id: str,
        cycle_type: str,
        name: str,
        start_date: datetime,
        end_date: datetime,
        submission_start: datetime,
        submission_end: datetime,
        applies_to_levels: List[int] = None,
        eligible_plant_ids: List[str] = None,
        eligible_dept_ids: List[str] = None,
        description: str = None,
        auto_lock_date: datetime = None,
        auto_publish_date: datetime = None,
    ) -> PerformanceReviewCycle:
        """
        Create a new review cycle.
        Validates dates and auto-management settings.
        """
        # Validation
        if submission_start < start_date or submission_end > end_date:
            raise ValueError("Submission dates must be within cycle dates")
        
        if submission_end < submission_start:
            raise ValueError("Submission end must be after submission start")
        
        # Default levels if not specified
        if applies_to_levels is None:
            applies_to_levels = [0, 1, 2, 3, 4, 5]
        
        cycle = PerformanceReviewCycle(
            org_id=org_id,
            cycle_type=cycle_type,
            name=name,
            description=description,
            start_date=start_date,
            end_date=end_date,
            submission_start=submission_start,
            submission_end=submission_end,
            applies_to_levels=applies_to_levels,
            eligible_plant_ids=eligible_plant_ids,
            eligible_dept_ids=eligible_dept_ids,
            status=ReviewCycleStatus.PLANNED.value,
            auto_lock_date=auto_lock_date,
            auto_lock_enabled=auto_lock_date is not None,
            auto_publish_date=auto_publish_date,
            auto_publish_enabled=auto_publish_date is not None,
        )
        
        self.db.add(cycle)
        self.db.commit()
        self.db.refresh(cycle)
        
        logger.info(f"Created review cycle: {cycle.id} ({cycle.name})")
        return cycle

    def get_active_cycles(self, org_id: str) -> List[PerformanceReviewCycle]:
        """Get currently active review cycles for organization"""
        return self.db.query(PerformanceReviewCycle).filter(
            PerformanceReviewCycle.org_id == org_id,
            PerformanceReviewCycle.status.in_([
                ReviewCycleStatus.ACTIVE.value,
                ReviewCycleStatus.LOCKED.value
            ])
        ).order_by(PerformanceReviewCycle.start_date.desc()).all()

    def get_cycle_by_id(self, cycle_id: str) -> Optional[PerformanceReviewCycle]:
        """Fetch review cycle by ID"""
        return self.db.query(PerformanceReviewCycle).filter(PerformanceReviewCycle.id == cycle_id).first()

    def update_cycle_status(
        self,
        cycle_id: str,
        new_status: str
    ) -> PerformanceReviewCycle:
        """Update cycle status (PLANNED → ACTIVE → LOCKED → CLOSED)"""
        cycle = self.get_cycle_by_id(cycle_id)
        if not cycle:
            raise ValueError(f"Cycle not found: {cycle_id}")
        
        # Validate transition
        valid_transitions = {
            "PLANNED": ["ACTIVE"],
            "ACTIVE": ["LOCKED"],
            "LOCKED": ["CLOSED"],
            "CLOSED": []
        }
        
        if new_status not in valid_transitions.get(cycle.status, []):
            raise ValueError(f"Cannot transition from {cycle.status} to {new_status}")
        
        cycle.status = new_status
        cycle.updated_at = datetime.utcnow()
        
        # Set lock date if transitioning to LOCKED
        if new_status == ReviewCycleStatus.LOCKED.value:
            cycle.lock_date = datetime.utcnow()
            cycle.editing_locked = True
        
        self.db.commit()
        self.db.refresh(cycle)
        
        logger.info(f"Cycle {cycle_id} status changed to {new_status}")
        return cycle

    def lock_cycle(self, cycle_id: str) -> PerformanceReviewCycle:
        """Lock cycle for new submissions"""
        return self.update_cycle_status(cycle_id, ReviewCycleStatus.LOCKED.value)

    def publish_cycle(self, cycle_id: str) -> PerformanceReviewCycle:
        """Publish all reviews in cycle (make visible to employees)"""
        cycle = self.get_cycle_by_id(cycle_id)
        if not cycle:
            raise ValueError(f"Cycle not found: {cycle_id}")
        
        # Mark all FINALIZED reviews as PUBLISHED
        reviews = self.db.query(EmployeePerformanceReview).filter(
            EmployeePerformanceReview.review_cycle_id == cycle_id,
            EmployeePerformanceReview.current_state == ReviewState.FINALIZED.value
        ).all()
        
        for review in reviews:
            review.current_state = ReviewState.PUBLISHED.value
            review.published_at = datetime.utcnow()
            self.db.add(review)
        
        self.db.commit()
        logger.info(f"Published {len(reviews)} reviews for cycle {cycle_id}")
        
        return cycle

    # ─────────────────────────────────────────────────────────────────────────
    # ELIGIBLE EMPLOYEES
    # ─────────────────────────────────────────────────────────────────────────

    def get_eligible_employees_for_cycle(
        self,
        cycle: PerformanceReviewCycle
    ) -> List[User]:
        """
        Get all employees eligible for this review cycle.
        Filters by:
        - Applies to levels (org depth)
        - Eligible plants
        - Eligible departments
        - Eligible roles
        """
        # Base query: get users whose org_node depth is in applies_to_levels
        eligible_users = self.db.query(User).filter(
            User.org_id == cycle.org_id
        ).all()
        
        filtered_users = []
        for user in eligible_users:
            # Check depth/level
            if user.org_node_id:
                node = self.db.query(OrgNode).filter(
                    OrgNode.id == user.org_node_id
                ).first()
                if node and node.depth in cycle.applies_to_levels:
                    filtered_users.append(user)
            else:
                # Users without org_node: check if org level (depth 0) is included
                if 0 in cycle.applies_to_levels:
                    filtered_users.append(user)
        
        # Filter by plant if specified
        if cycle.eligible_plant_ids:
            # More complex filtering needed here
            # For now, basic implementation
            pass
        
        return filtered_users

    # ─────────────────────────────────────────────────────────────────────────
    # AUTO-MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────────

    def process_auto_actions(self, cycle_id: str):
        """
        Process scheduled auto-actions:
        - Auto-lock reviews
        - Auto-publish reviews
        - Auto-close cycle
        """
        cycle = self.get_cycle_by_id(cycle_id)
        if not cycle:
            return
        
        now = datetime.utcnow()
        
        # Auto-lock
        if (cycle.auto_lock_enabled and 
            cycle.auto_lock_date and 
            now >= cycle.auto_lock_date and
            cycle.status == ReviewCycleStatus.ACTIVE.value):
            
            self.lock_cycle(cycle_id)
            logger.info(f"Auto-locked cycle {cycle_id}")
        
        # Auto-publish
        if (cycle.auto_publish_enabled and 
            cycle.auto_publish_date and 
            now >= cycle.auto_publish_date and
            cycle.status == ReviewCycleStatus.LOCKED.value):
            
            self.publish_cycle(cycle_id)
            cycle.status = ReviewCycleStatus.CLOSED.value
            self.db.commit()
            logger.info(f"Auto-published and closed cycle {cycle_id}")

    # ─────────────────────────────────────────────────────────────────────────
    # INTEGRATION WITH OKR CYCLES
    # ─────────────────────────────────────────────────────────────────────────

    def find_aligned_okr_cycle(self, review_cycle: PerformanceReviewCycle):
        """
        Find OKR cycle that aligns with this review cycle.
        Usually: Review cycle date range ⊆ OKR cycle date range
        
        Example:
        - Q1 Review (Jan 1 - Mar 31) aligns with Q1 OKR (Jan 1 - Mar 31)
        - Weekly Review (Mon - Sun) aligns with ongoing OKR cycle
        """
        # This will be implemented when integrating with OKR models
        # For now, placeholder
        pass

    def aggregate_checkins_for_review_cycle(
        self,
        employee_id: str,
        review_cycle: PerformanceReviewCycle
    ) -> List[ContinuousCheckin]:
        """
        Get all check-ins submitted during this review cycle.
        Used to populate continuous_checkin_score in reviews.
        """
        checkins = self.db.query(ContinuousCheckin).filter(
            ContinuousCheckin.employee_id == employee_id,
            ContinuousCheckin.checkin_date >= review_cycle.start_date,
            ContinuousCheckin.checkin_date <= review_cycle.end_date,
            ContinuousCheckin.status.in_(["SUBMITTED", "REVIEWED", "ARCHIVED"])
        ).order_by(ContinuousCheckin.checkin_date).all()
        
        return checkins


class ContinuousCheckinService:
    """
    Manages continuous weekly/monthly check-ins.
    Lightweight performance tracking that feeds into formal reviews.
    """

    def __init__(self, db: Session):
        self.db = db

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK-IN SUBMISSION
    # ─────────────────────────────────────────────────────────────────────────

    def submit_checkin(
        self,
        employee_id: str,
        manager_id: str,
        org_id: str,
        checkin_week: int,
        achievements: str,
        blockers: str,
        confidence_score: float,
        engagement_score: int,
        employee_mood: str,
        key_wins: List[str] = None,
        risks: List[dict] = None,
        support_needed: str = None,
        okr_progress_snapshot: dict = None,
        progress_notes: str = None,
    ) -> ContinuousCheckin:
        """
        Submit a weekly or monthly check-in.
        
        Validation:
        - Employee can only submit their own check-in
        - Cannot submit duplicate for same week
        """
        # Check for existing check-in for this week
        existing = self.db.query(ContinuousCheckin).filter(
            ContinuousCheckin.employee_id == employee_id,
            ContinuousCheckin.checkin_week == checkin_week,
            ContinuousCheckin.is_latest == True
        ).first()
        
        if existing:
            # Mark previous as not latest
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
            status="SUBMITTED",
            is_latest=True
        )
        
        self.db.add(checkin)
        self.db.commit()
        self.db.refresh(checkin)
        
        logger.info(f"Check-in submitted: {checkin.id} by {employee_id} for week {checkin_week}")
        return checkin

    def get_checkin(self, checkin_id: str) -> Optional[ContinuousCheckin]:
        """Fetch check-in by ID"""
        return self.db.query(ContinuousCheckin).filter(
            ContinuousCheckin.id == checkin_id
        ).first()

    def get_employee_checkins(
        self,
        employee_id: str,
        limit: int = 12,
        offset: int = 0
    ) -> Tuple[List[ContinuousCheckin], int]:
        """Get employee's check-in history (paginated)"""
        query = self.db.query(ContinuousCheckin).filter(
            ContinuousCheckin.employee_id == employee_id,
            ContinuousCheckin.is_latest == True
        ).order_by(ContinuousCheckin.checkin_date.desc())
        
        total = query.count()
        checkins = query.limit(limit).offset(offset).all()
        
        return checkins, total

    # ─────────────────────────────────────────────────────────────────────────
    # MANAGER RESPONSE
    # ─────────────────────────────────────────────────────────────────────────

    def provide_manager_response(
        self,
        checkin_id: str,
        manager_feedback: str,
        manager_response_quality: int,
        action_items: List[dict] = None,
        corrective_actions: List[dict] = None,
        coaching_notes: str = None
    ) -> ContinuousCheckin:
        """
        Manager provides feedback and coaching on check-in.
        """
        checkin = self.get_checkin(checkin_id)
        if not checkin:
            raise ValueError(f"Check-in not found: {checkin_id}")
        
        checkin.manager_feedback = manager_feedback
        checkin.manager_responded_at = datetime.utcnow()
        checkin.manager_response_quality = manager_response_quality
        checkin.action_items = action_items or []
        checkin.corrective_actions = corrective_actions or []
        checkin.coaching_notes = coaching_notes
        checkin.status = "REVIEWED"
        
        self.db.commit()
        self.db.refresh(checkin)
        
        logger.info(f"Manager provided feedback on check-in {checkin_id}")
        return checkin

    # ─────────────────────────────────────────────────────────────────────────
    # ANALYTICS
    # ─────────────────────────────────────────────────────────────────────────

    def calculate_checkin_quality_score(
        self,
        employee_id: str,
        review_cycle_start: datetime,
        review_cycle_end: datetime
    ) -> Optional[float]:
        """
        Calculate continuous check-in score (5% of final review score) from real check-in data.

        Factors:
        1. Submission consistency (40%)
        2. Employee engagement & confidence averages (35%)
        3. Manager coaching response quality when present (25%)
        """
        if not review_cycle_start or not review_cycle_end:
            return None

        active_statuses = [
            "SUBMITTED",
            "UNDER_REVIEW",
            "ACTION_REQUIRED",
            "ESCALATED",
            "RESOLVED",
            "CLOSED",
            "REVIEWED",
        ]
        checkins = (
            self.db.query(ContinuousCheckin)
            .filter(
                ContinuousCheckin.employee_id == employee_id,
                ContinuousCheckin.is_latest == True,
                ContinuousCheckin.checkin_date >= review_cycle_start,
                ContinuousCheckin.checkin_date <= review_cycle_end,
                ContinuousCheckin.workflow_status.in_(active_statuses),
            )
            .order_by(ContinuousCheckin.checkin_date.asc())
            .all()
        )

        if not checkins:
            checkins = (
                self.db.query(ContinuousCheckin)
                .filter(
                    ContinuousCheckin.employee_id == employee_id,
                    ContinuousCheckin.is_latest == True,
                    ContinuousCheckin.workflow_status.in_(active_statuses),
                )
                .order_by(ContinuousCheckin.checkin_date.desc())
                .limit(12)
                .all()
            )

        if not checkins:
            return None

        submitted = [c for c in checkins if c.submitted_at]
        submission_score = (len(submitted) / len(checkins)) * 100

        engagement_scores = [c.engagement_score for c in checkins if c.engagement_score is not None]
        confidence_scores = [c.confidence_score for c in checkins if c.confidence_score is not None]
        employee_signal_scores: List[float] = []
        if engagement_scores:
            employee_signal_scores.append((sum(engagement_scores) / len(engagement_scores) / 10) * 100)
        if confidence_scores:
            employee_signal_scores.append(sum(confidence_scores) / len(confidence_scores))
        employee_signal = (
            sum(employee_signal_scores) / len(employee_signal_scores) if employee_signal_scores else None
        )

        coaching_scores = [
            (c.manager_response_quality / 5) * 100
            for c in checkins
            if c.manager_response_quality is not None
        ]
        coaching_score = sum(coaching_scores) / len(coaching_scores) if coaching_scores else None

        if coaching_score is not None and employee_signal is not None:
            final_score = submission_score * 0.4 + employee_signal * 0.35 + coaching_score * 0.25
        elif employee_signal is not None:
            final_score = submission_score * 0.55 + employee_signal * 0.45
        else:
            final_score = submission_score

        return round(min(100, max(0, final_score)), 1)

    def detect_mood_trend_changes(
        self,
        employee_id: str,
        lookback_weeks: int = 4
    ) -> dict:
        """
        Detect significant mood changes that might indicate issues.
        Returns flag if mood dropped from POSITIVE to CONCERNING+
        """
        checkins = self.db.query(ContinuousCheckin).filter(
            ContinuousCheckin.employee_id == employee_id,
            ContinuousCheckin.is_latest == True
        ).order_by(ContinuousCheckin.checkin_date.desc()).limit(lookback_weeks).all()
        
        moods = [c.employee_mood for c in reversed(checkins) if c.employee_mood]
        
        flags = []
        if len(moods) >= 2:
            if moods[-2] in ["VERY_POSITIVE", "POSITIVE"] and \
               moods[-1] in ["CONCERNING", "CRITICAL"]:
                flags.append("MOOD_DECLINE")
        
        # Check for sustained low mood
        if all(m in ["CONCERNING", "CRITICAL"] for m in moods[-3:]):
            flags.append("SUSTAINED_LOW_MOOD")
        
        return {
            "mood_trend": moods,
            "flags": flags,
            "current_mood": moods[-1] if moods else None
        }

    def identify_recurring_blockers(
        self,
        employee_id: str,
        lookback_weeks: int = 8
    ) -> List[str]:
        """
        Identify recurring blockers across check-ins.
        Flags if same blocker mentioned multiple times.
        """
        checkins = self.db.query(ContinuousCheckin).filter(
            ContinuousCheckin.employee_id == employee_id
        ).order_by(ContinuousCheckin.checkin_date.desc()).limit(lookback_weeks).all()
        
        # Simple keyword extraction (could use NLP for better results)
        blocker_keywords = {}
        for checkin in checkins:
            if checkin.blockers:
                # Split by common delimiters
                words = checkin.blockers.lower().split()
                for word in words:
                    if len(word) > 4:  # Filter short words
                        blocker_keywords[word] = blocker_keywords.get(word, 0) + 1
        
        # Return keywords appearing 3+ times
        recurring = [word for word, count in blocker_keywords.items() if count >= 3]
        return recurring
