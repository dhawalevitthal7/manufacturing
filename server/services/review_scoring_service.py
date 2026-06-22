"""
Review Scoring Engine Service
Calculates component scores and final performance ratings.
Implements bias detection and score normalization.
"""

from datetime import datetime
from sqlalchemy.orm import Session
from typing import Optional, Dict, List, Tuple
import logging

from server.performance_review_models import (
    EmployeePerformanceReview, ReviewCalculation, ReviewRating,
    ReviewSection, SectionType, ScoringConfiguration, CompetencyAssessment,
    Competency, ReviewAdjustment, AdjustmentReason, FeedbackSynthesis,
    PerformanceReviewCycle,
)
from server.models import User
from server.services.okr_review_integration import (
    build_okr_progress_snapshot,
    calculate_okr_achievement_score,
)

logger = logging.getLogger(__name__)

BEHAVIORAL_KEYS = ("collaboration", "ownership", "execution", "accountability")
MANAGER_FEEDBACK_KEYS = ("collaboration", "ownership", "accountability")

_RATING_TO_SCORE = {
    "EXCEEDS_EXPECTATIONS": 92.0,
    "MEETS_EXPECTATIONS": 75.0,
    "BELOW_EXPECTATIONS": 55.0,
    "NEEDS_IMPROVEMENT": 38.0,
}


def _scale_1_to_5(score: float) -> float:
    return round(max(0.0, min(100.0, (score / 5.0) * 100.0)), 1)


def _avg_behavioral_scores(scores: dict, keys: tuple) -> Optional[float]:
    values = [scores[k] for k in keys if k in scores and scores[k] is not None]
    if not values:
        return None
    return _scale_1_to_5(sum(values) / len(values))


def _weighted_final_score(
    components: Dict[str, Tuple[Optional[float], float]],
) -> Tuple[float, float, Dict[str, float]]:
    """
    Combine available component scores, redistributing weights when data is missing.
    Returns (final_score, confidence_pct, resolved_component_scores).
    """
    all_components: Dict[str, Optional[float]] = {}
    weighted_sum = 0.0
    active_weight = 0.0
    configured_weight = sum(weight for _, weight in components.values())

    for name, (score, weight) in components.items():
        all_components[name] = score
        if score is None:
            continue
        weighted_sum += score * weight
        active_weight += weight

    if active_weight <= 0:
        return 0.0, 0.0, all_components

    final_score = round(weighted_sum / active_weight, 1)
    confidence = round((active_weight / configured_weight) * 100, 1) if configured_weight else 0.0
    return final_score, confidence, all_components


class ReviewScoringService:
    """
    Calculates performance review scores and ratings.
    
    Scoring formula:
    FINAL_SCORE = (
        OKR_ACHIEVEMENT_SCORE × 0.40 +
        KR_QUALITY_SCORE × 0.20 +
        MANAGER_FEEDBACK_SCORE × 0.15 +
        BEHAVIORAL_COMPETENCY_SCORE × 0.10 +
        PEER_FEEDBACK_SCORE × 0.10 +
        CONTINUOUS_CHECKIN_SCORE × 0.05
    )
    """

    def __init__(self, db: Session):
        self.db = db

    # ─────────────────────────────────────────────────────────────────────────
    # SCORE CALCULATION
    # ─────────────────────────────────────────────────────────────────────────

    def calculate_final_score(
        self,
        performance_review_id: str
    ) -> Tuple[float, ReviewRating, Dict[str, float]]:
        """
        Calculate final performance score and rating.
        
        Returns:
            (final_score: 0-100, rating: EXCEEDS/MEETS/BELOW/NEEDS_IMPROVEMENT, component_scores: dict)
        """
        review = self.db.query(EmployeePerformanceReview).filter(
            EmployeePerformanceReview.id == performance_review_id
        ).first()
        
        if not review:
            raise ValueError(f"Review not found: {performance_review_id}")
        
        config = self._get_scoring_config(review.org_id, review.employee_id)

        weighted_components = {
            "okr_achievement": (
                self._calculate_okr_achievement_score(review),
                config.okr_achievement_weight,
            ),
            "kr_quality": (
                self._calculate_kr_quality_score(review),
                config.kr_quality_weight,
            ),
            "manager_feedback": (
                self._calculate_manager_feedback_score(review),
                config.manager_feedback_weight,
            ),
            "behavioral_competency": (
                self._calculate_behavioral_competency_score(review),
                config.behavioral_competency_weight,
            ),
            "peer_feedback": (
                self._calculate_peer_feedback_score(review),
                config.peer_feedback_weight,
            ),
            "continuous_checkin": (
                self._calculate_continuous_checkin_score(review),
                config.continuous_checkin_weight,
            ),
        }

        final_score, confidence, component_scores = _weighted_final_score(weighted_components)
        rating = self._score_to_rating(final_score, config)

        self._store_calculation(
            performance_review_id=performance_review_id,
            okr_score=component_scores.get("okr_achievement"),
            kr_quality_score=component_scores.get("kr_quality"),
            manager_feedback_score=component_scores.get("manager_feedback"),
            competency_score=component_scores.get("behavioral_competency"),
            peer_feedback_score=component_scores.get("peer_feedback"),
            checkin_score=component_scores.get("continuous_checkin"),
            final_score=final_score,
            final_rating=rating,
            confidence_score=confidence,
        )

        return final_score, rating, component_scores

    # ─────────────────────────────────────────────────────────────────────────
    # COMPONENT SCORE CALCULATIONS
    # ─────────────────────────────────────────────────────────────────────────

    def _get_review_period(self, review: EmployeePerformanceReview) -> Tuple[Optional[datetime], Optional[datetime]]:
        start = review.review_period_start
        end = review.review_period_end
        if start and end:
            return start, end
        cycle = self.db.query(PerformanceReviewCycle).filter(
            PerformanceReviewCycle.id == review.review_cycle_id
        ).first()
        if cycle:
            return cycle.start_date, cycle.end_date
        return None, None

    def _get_manager_section(self, review: EmployeePerformanceReview) -> Optional[ReviewSection]:
        return self.db.query(ReviewSection).filter(
            ReviewSection.performance_review_id == review.id,
            ReviewSection.section_type == SectionType.MANAGER,
        ).first()

    def _get_self_section(self, review: EmployeePerformanceReview) -> Optional[ReviewSection]:
        return self.db.query(ReviewSection).filter(
            ReviewSection.performance_review_id == review.id,
            ReviewSection.section_type == SectionType.SELF,
        ).first()

    def _calculate_okr_achievement_score(self, review: EmployeePerformanceReview) -> Optional[float]:
        """Live OKR/KR progress weighted average."""
        score, okr_ids = calculate_okr_achievement_score(
            self.db,
            review.employee_id,
            review.org_id,
            review.okr_ids or None,
        )
        if not okr_ids:
            return None
        review.okr_achievement_score = score
        review.okr_ids = okr_ids
        self.db.commit()
        return score

    def _derive_kr_quality_from_okr_data(self, review: EmployeePerformanceReview) -> Optional[float]:
        """KR consistency and progress from live objective/KR records."""
        snapshot = build_okr_progress_snapshot(self.db, review.employee_id, review.org_id)
        kr_progresses = [
            kr["progress_pct"]
            for obj in snapshot.get("objectives", [])
            for kr in obj.get("key_results", [])
        ]
        if not kr_progresses:
            return None

        avg_progress = sum(kr_progresses) / len(kr_progresses)
        if len(kr_progresses) > 1:
            variance = sum((p - avg_progress) ** 2 for p in kr_progresses) / len(kr_progresses)
            consistency_bonus = max(0.0, 10.0 - (variance / 10.0))
        else:
            consistency_bonus = 0.0
        return round(min(100.0, avg_progress + consistency_bonus), 1)

    def _derive_kr_quality_from_self_review(self, review: EmployeePerformanceReview) -> Optional[float]:
        """Self-assessed completion vs actual OKR progress alignment."""
        self_section = self._get_self_section(review)
        if not self_section or not self_section.self_okr_assessment:
            return None

        actual_score, _ = calculate_okr_achievement_score(
            self.db, review.employee_id, review.org_id, review.okr_ids or None
        )
        self_scores = [
            item.get("self_assessed_completion")
            for item in self_section.self_okr_assessment
            if item.get("self_assessed_completion") is not None
        ]
        if not self_scores:
            return None

        self_avg = sum(self_scores) / len(self_scores)
        alignment_penalty = min(30.0, abs(self_avg - actual_score) * 0.5)
        return round(max(0.0, min(100.0, self_avg - alignment_penalty)), 1)

    def _calculate_kr_quality_score(self, review: EmployeePerformanceReview) -> Optional[float]:
        """
        KR execution quality from manager execution rating, self-assessment alignment,
        or KR progress consistency.
        """
        manager_section = self._get_manager_section(review)
        if manager_section and manager_section.manager_behavioral_scores:
            scores = manager_section.manager_behavioral_scores
            execution = scores.get("execution")
            if execution is not None:
                return _scale_1_to_5(float(execution))

        self_quality = self._derive_kr_quality_from_self_review(review)
        if self_quality is not None:
            return self_quality

        return self._derive_kr_quality_from_okr_data(review)

    def _score_from_ai_payload(self, review: EmployeePerformanceReview) -> Optional[float]:
        """Use AI agent recommended rating when formal manager section is not submitted yet."""
        payload = review.ai_review_payload or {}
        rating = payload.get("recommended_rating")
        if not rating:
            return None
        return _RATING_TO_SCORE.get(str(rating).upper())

    def _behavioral_from_ai_payload(self, review: EmployeePerformanceReview) -> Optional[float]:
        """Behavioral preview from AI agent or stored behavioral scores on the payload."""
        payload = review.ai_review_payload or {}
        behavioral = payload.get("behavioral_competency_scores") or payload.get("behavioral_scores")
        if isinstance(behavioral, dict) and behavioral:
            return _avg_behavioral_scores(behavioral, BEHAVIORAL_KEYS)
        base = self._score_from_ai_payload(review)
        if base is not None:
            return round(max(0.0, min(100.0, base * 0.97)), 1)
        return None

    def _calculate_manager_feedback_score(self, review: EmployeePerformanceReview) -> Optional[float]:
        """Manager behavioral ratings for collaboration, ownership, accountability."""
        manager_section = self._get_manager_section(review)
        if manager_section and manager_section.manager_behavioral_scores:
            score = _avg_behavioral_scores(
                manager_section.manager_behavioral_scores,
                MANAGER_FEEDBACK_KEYS,
            )
            if score is not None:
                return score
        return self._score_from_ai_payload(review)

    def _calculate_behavioral_competency_score(self, review: EmployeePerformanceReview) -> Optional[float]:
        """Formal competency framework assessments, or full manager behavioral average."""
        manager_section = self._get_manager_section(review)
        if manager_section:
            assessments = self.db.query(CompetencyAssessment).filter(
                CompetencyAssessment.review_section_id == manager_section.id
            ).all()
            if assessments:
                total_weighted_score = 0.0
                total_weight = 0.0
                for assessment in assessments:
                    competency = self.db.query(Competency).filter(
                        Competency.id == assessment.competency_id
                    ).first()
                    if competency and competency.weight:
                        score = (assessment.proficiency_level / 5) * 100
                        total_weighted_score += score * competency.weight
                        total_weight += competency.weight
                if total_weight > 0:
                    return round(total_weighted_score / total_weight, 1)

            if manager_section.manager_behavioral_scores:
                score = _avg_behavioral_scores(
                    manager_section.manager_behavioral_scores,
                    BEHAVIORAL_KEYS,
                )
                if score is not None:
                    return score
        return self._behavioral_from_ai_payload(review)

    def _calculate_peer_feedback_score(self, review: EmployeePerformanceReview) -> Optional[float]:
        """360 feedback synthesis when peer/subordinate responses exist."""
        synthesis = self.db.query(FeedbackSynthesis).filter(
            FeedbackSynthesis.performance_review_id == review.id
        ).first()
        if not synthesis:
            return None

        if synthesis.overall_external_perception_score is not None:
            return round(float(synthesis.overall_external_perception_score), 1)

        weighted_scores: List[Tuple[float, int]] = []
        for score, count in (
            (synthesis.peer_feedback_score, synthesis.peer_feedback_count or 0),
            (synthesis.subordinate_feedback_score, synthesis.subordinate_feedback_count or 0),
            (synthesis.cross_functional_score, synthesis.cross_functional_count or 0),
        ):
            if score is not None and count > 0:
                weighted_scores.append((float(score), count))

        if not weighted_scores:
            return None

        total_count = sum(count for _, count in weighted_scores)
        blended = sum(score * count for score, count in weighted_scores) / total_count
        return round(blended, 1)

    def _calculate_continuous_checkin_score(self, review: EmployeePerformanceReview) -> Optional[float]:
        """Weekly check-in engagement and coaching data for the review period."""
        from server.services.review_cycle_service import ContinuousCheckinService

        period_start, period_end = self._get_review_period(review)
        return ContinuousCheckinService(self.db).calculate_checkin_quality_score(
            employee_id=review.employee_id,
            review_cycle_start=period_start,
            review_cycle_end=period_end,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # RATING DETERMINATION
    # ─────────────────────────────────────────────────────────────────────────

    def _score_to_rating(
        self,
        score: float,
        config: ScoringConfiguration
    ) -> ReviewRating:
        """Convert numeric score (0-100) to rating"""
        if score >= config.exceeds_expectations_threshold:
            return ReviewRating.EXCEEDS_EXPECTATIONS
        elif score >= config.meets_expectations_threshold:
            return ReviewRating.MEETS_EXPECTATIONS
        elif score >= config.below_expectations_threshold:
            return ReviewRating.BELOW_EXPECTATIONS
        else:
            return ReviewRating.NEEDS_IMPROVEMENT

    # ─────────────────────────────────────────────────────────────────────────
    # BIAS DETECTION & MITIGATION
    # ─────────────────────────────────────────────────────────────────────────

    def detect_bias_flags(
        self,
        performance_review_id: str,
        component_scores: Dict[str, float]
    ) -> List[str]:
        """
        Detect potential bias in review scoring.
        
        Flags:
        1. Halo effect: Manager feedback aligns too closely with OKR score
        2. Inflated self-view: Self-assessment vs peer feedback gap
        3. Recency bias: Recent check-ins weighted more
        4. Consistency bias: Similar scores across all dimensions
        """
        flags = []
        
        # 1. Halo effect detection
        okr_score = component_scores.get("okr_achievement", 0)
        manager_score = component_scores.get("manager_feedback", 0)
        
        if abs(manager_score - okr_score) > 20:
            flags.append("HALO_EFFECT: Manager feedback aligns too closely with metrics")
        
        # 2. Inflated self-view (would need access to self-review)
        # if self_score - peer_score > 15:
        #     flags.append("INFLATED_SELF_VIEW")
        
        # 3. All scores suspiciously similar (possible lack of rigor)
        scores = list(component_scores.values())
        avg_score = sum(scores) / len(scores) if scores else 0
        variance = sum((s - avg_score) ** 2 for s in scores) / len(scores) if scores else 0
        
        if variance < 50:  # Very little variation
            flags.append("LOW_SCORE_VARIANCE: Review may lack rigor")
        
        return flags

    def check_outlier_scores(
        self,
        review: EmployeePerformanceReview,
        final_score: float,
        peer_scores: List[float]
    ) -> List[str]:
        """
        Flag if this review is statistical outlier vs peers.
        """
        flags = []
        
        if not peer_scores:
            return flags
        
        peer_avg = sum(peer_scores) / len(peer_scores)
        peer_stdev = (sum((s - peer_avg) ** 2 for s in peer_scores) / len(peer_scores)) ** 0.5
        
        # Flag if >2 standard deviations from peer average
        if abs(final_score - peer_avg) > (2 * peer_stdev):
            if final_score > peer_avg:
                flags.append("OUTLIER_HIGH: Score significantly higher than peer group")
            else:
                flags.append("OUTLIER_LOW: Score significantly lower than peer group")
        
        return flags

    # ─────────────────────────────────────────────────────────────────────────
    # SCORING CONFIGURATION
    # ─────────────────────────────────────────────────────────────────────────

    def _get_scoring_config(
        self,
        org_id: str,
        employee_id: str
    ) -> ScoringConfiguration:
        """
        Get scoring configuration for this organization/employee.
        Checks for role-specific config first, then defaults.
        """
        # In full implementation: get employee's role, then fetch role-specific config
        # For now, get organization default
        config = self.db.query(ScoringConfiguration).filter(
            ScoringConfiguration.org_id == org_id,
            ScoringConfiguration.role_type == None
        ).first()
        
        if not config:
            # Create default if doesn't exist
            config = ScoringConfiguration(
                org_id=org_id,
                okr_achievement_weight=40.0,
                kr_quality_weight=20.0,
                manager_feedback_weight=15.0,
                behavioral_competency_weight=10.0,
                peer_feedback_weight=10.0,
                continuous_checkin_weight=5.0,
                exceeds_expectations_threshold=85.0,
                meets_expectations_threshold=65.0,
                below_expectations_threshold=50.0
            )
            self.db.add(config)
            self.db.commit()
        
        return config

    def update_scoring_config(
        self,
        org_id: str,
        role_type: Optional[str] = None,
        **kwargs
    ) -> ScoringConfiguration:
        """Update scoring weights"""
        config = self.db.query(ScoringConfiguration).filter(
            ScoringConfiguration.org_id == org_id,
            ScoringConfiguration.role_type == role_type
        ).first()
        
        if not config:
            config = ScoringConfiguration(org_id=org_id, role_type=role_type)
        
        # Update fields
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        config.updated_at = datetime.utcnow()
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        
        return config

    # ─────────────────────────────────────────────────────────────────────────
    # AUDIT TRAIL
    # ─────────────────────────────────────────────────────────────────────────

    def _store_calculation(
        self,
        performance_review_id: str,
        okr_score: Optional[float],
        kr_quality_score: Optional[float],
        manager_feedback_score: Optional[float],
        competency_score: Optional[float],
        peer_feedback_score: Optional[float],
        checkin_score: Optional[float],
        final_score: float,
        final_rating: ReviewRating,
        confidence_score: float,
    ):
        """Store calculation for audit trail"""
        calculation = ReviewCalculation(
            performance_review_id=performance_review_id,
            okr_achievement_score=okr_score,
            kr_quality_score=kr_quality_score,
            manager_feedback_score=manager_feedback_score,
            behavioral_competency_score=competency_score,
            peer_feedback_score=peer_feedback_score,
            continuous_checkin_score=checkin_score,
            calculated_final_score=final_score,
            final_rating=final_rating.value,
            confidence_score=confidence_score,
            calculation_timestamp=datetime.utcnow()
        )
        
        self.db.add(calculation)
        self.db.commit()

    # ─────────────────────────────────────────────────────────────────────────
    # CALIBRATION & NORMALIZATION
    # ─────────────────────────────────────────────────────────────────────────

    def normalize_scores_within_group(
        self,
        calibration_group_id: str,
        adjustments: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Apply score adjustments during calibration.
        Ensures fair relative ratings within peer group.
        
        adjustments: {review_id: adjustment_value}
        """
        applied_adjustments = {}
        
        for review_id, adjustment in adjustments.items():
            review = self.db.query(EmployeePerformanceReview).filter(
                EmployeePerformanceReview.id == review_id
            ).first()
            
            if not review:
                continue
            
            old_score = review.final_score
            new_score = max(0, min(100, old_score + adjustment))
            
            # Create adjustment record
            adj_record = ReviewAdjustment(
                performance_review_id=review_id,
                adjustment_reason=AdjustmentReason.CALIBRATION.value,
                previous_score=old_score,
                new_score=new_score,
                adjustment_notes=f"Calibration adjustment: {adjustment:+.1f} points"
            )
            
            review.final_score = new_score
            review.final_rating = self._score_to_rating(
                new_score,
                self._get_scoring_config(review.org_id, review.employee_id)
            ).value
            
            self.db.add(adj_record)
            self.db.add(review)
            
            applied_adjustments[review_id] = {
                "old_score": old_score,
                "new_score": new_score,
                "adjustment": adjustment
            }
        
        self.db.commit()
        logger.info(f"Applied calibration adjustments: {len(applied_adjustments)}")
        
        return applied_adjustments
