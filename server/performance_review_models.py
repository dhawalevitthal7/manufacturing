"""
Performance Review System Models
Production-grade SQLAlchemy models for enterprise continuous performance management.
Tightly integrated with existing OKR platform.
"""

from datetime import datetime
from enum import Enum
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, ForeignKey,
    Text, Enum as SQLEnum, UniqueConstraint, Index, JSON
)
from sqlalchemy.orm import relationship
from server.database import Base
import uuid


def gen_uuid():
    return str(uuid.uuid4())


# ============================================================================
# ENUMS
# ============================================================================

class ReviewCycleType(str, Enum):
    """Types of review cycles"""
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    HALF_YEARLY = "HALF_YEARLY"
    ANNUAL = "ANNUAL"


class ReviewCycleStatus(str, Enum):
    """Review cycle lifecycle status"""
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    LOCKED = "LOCKED"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class ReviewState(str, Enum):
    """
    Quarterly / formal review — hierarchical approval-driven.
    Manufacturing: Employee → Manager → Dept Head (optional) → HR → Finalized → Published.
    Regional/CEO do not review individual employees (dashboards only).
    """
    DRAFT = "DRAFT"
    SELF_SUBMITTED = "SELF_SUBMITTED"
    MANAGER_REVIEW = "MANAGER_REVIEW"
    DEPT_HEAD_MODERATION = "DEPT_HEAD_MODERATION"
    PEER_REVIEW = "PEER_REVIEW"
    SKIP_LEVEL_REVIEW = "SKIP_LEVEL_REVIEW"  # legacy; not used for plant employee reviews
    HR_CALIBRATION = "HR_CALIBRATION"
    FINALIZED = "FINALIZED"
    PUBLISHED = "PUBLISHED"
    LOCKED = "LOCKED"
    ARCHIVED = "ARCHIVED"


class ReviewRating(str, Enum):
    """Final performance ratings"""
    EXCEEDS_EXPECTATIONS = "EXCEEDS_EXPECTATIONS"      # 85-100
    MEETS_EXPECTATIONS = "MEETS_EXPECTATIONS"          # 65-84
    BELOW_EXPECTATIONS = "BELOW_EXPECTATIONS"          # 50-64
    NEEDS_IMPROVEMENT = "NEEDS_IMPROVEMENT"            # <50


class EmployeeMood(str, Enum):
    """Employee mood/sentiment from check-ins"""
    VERY_POSITIVE = "VERY_POSITIVE"
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    CONCERNING = "CONCERNING"
    CRITICAL = "CRITICAL"


class CheckinWorkflowStatus(str, Enum):
    """
    Coaching/monitoring workflow — NOT an approval chain.
    Employee → immediate manager only; escalation is exception-based.
    """
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class CheckinEscalationReason(str, Enum):
    SEVERE_BLOCKER = "SEVERE_BLOCKER"
    REPEATED_LOW_PERFORMANCE = "REPEATED_LOW_PERFORMANCE"
    CROSS_FUNCTIONAL = "CROSS_FUNCTIONAL"
    SAFETY_COMPLIANCE = "SAFETY_COMPLIANCE"
    OTHER = "OTHER"


class FeedbackType(str, Enum):
    """Types of 360 feedback"""
    PEER = "PEER"
    SUBORDINATE = "SUBORDINATE"
    CROSS_FUNCTIONAL = "CROSS_FUNCTIONAL"
    MANAGER = "MANAGER"


class SectionType(str, Enum):
    """Review section types"""
    SELF = "SELF"
    MANAGER = "MANAGER"
    SKIP_LEVEL = "SKIP_LEVEL"
    HR_CALIBRATION = "HR_CALIBRATION"
    FINAL = "FINAL"


class CalibrationScope(str, Enum):
    """Scope for calibration groups"""
    DEPARTMENT = "DEPARTMENT"
    PLANT = "PLANT"
    FUNCTION = "FUNCTION"
    PEER_BAND = "PEER_BAND"
    ORGANIZATION = "ORGANIZATION"


class ApprovalStatus(str, Enum):
    """Submission approval status"""
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AdjustmentReason(str, Enum):
    """Reasons for review adjustments"""
    CALIBRATION = "CALIBRATION"
    BIAS_CORRECTION = "BIAS_CORRECTION"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"
    APPEAL = "APPEAL"


# ============================================================================
# REVIEW CYCLES
# ============================================================================

class PerformanceReviewCycle(Base):
    """
    Configurable review windows (weekly, monthly, quarterly, half-yearly, annual).
    Uses perf_review_cycles to avoid collision with legacy review_cycles table.
    """
    __tablename__ = "perf_review_cycles"
    __table_args__ = (
        Index("idx_org_status", "org_id", "status"),
        Index("idx_cycle_dates", "start_date", "end_date"),
        UniqueConstraint("org_id", "cycle_type", "start_date", name="uc_cycle_uniqueness"),
    )

    id = Column(String(36), primary_key=True, default=gen_uuid)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    
    cycle_type = Column(SQLEnum(ReviewCycleType), nullable=False)
    name = Column(String(255), nullable=False)  # "Q1-2026 Reviews"
    description = Column(Text, nullable=True)
    
    # Timeline
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    submission_start = Column(DateTime, nullable=False)
    submission_end = Column(DateTime, nullable=False)
    
    # Lock/unlock management
    editing_locked = Column(Boolean, default=False)
    lock_date = Column(DateTime, nullable=True)
    auto_lock_enabled = Column(Boolean, default=False)
    auto_lock_date = Column(DateTime, nullable=True)
    
    # Auto-publish
    auto_publish_enabled = Column(Boolean, default=False)
    auto_publish_date = Column(DateTime, nullable=True)
    
    # Scope configuration
    applies_to_levels = Column(JSON, default=list)  # [0, 1, 2, 3, 4, 5]
    eligible_plant_ids = Column(JSON, nullable=True)  # Null = all plants
    eligible_dept_ids = Column(JSON, nullable=True)   # Null = all depts
    eligible_role_types = Column(JSON, nullable=True)
    
    # Status
    status = Column(SQLEnum(ReviewCycleStatus), default=ReviewCycleStatus.PLANNED)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)


# ============================================================================
# CONTINUOUS CHECK-INS
# ============================================================================

class ContinuousCheckin(Base):
    """
    Weekly/monthly lightweight performance tracking.
    Feeds into formal performance reviews.
    """
    __tablename__ = "continuous_checkins"
    __table_args__ = (
        Index("idx_employee_week", "employee_id", "checkin_week"),
        Index("idx_manager_week", "manager_id", "checkin_week"),
        Index("idx_status", "status"),
        Index("idx_latest", "is_latest"),
    )

    id = Column(String(36), primary_key=True, default=gen_uuid)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    employee_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    manager_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    # Submission window
    checkin_week = Column(Integer, nullable=False)  # ISO week number
    checkin_month = Column(Integer, nullable=True)
    checkin_date = Column(DateTime, nullable=False)
    
    # Employee submission
    submitted_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    
    # Content: achievements and progress
    achievements = Column(Text, nullable=True)  # Weekly wins
    key_wins = Column(JSON, default=list)  # Structured list
    
    # Challenges
    blockers = Column(Text, nullable=True)  # Obstacles
    risks = Column(JSON, default=list)  # Risk assessment
    support_needed = Column(Text, nullable=True)
    
    # Metrics
    confidence_score = Column(Float, nullable=True)  # 0-100 self-assessed
    engagement_score = Column(Integer, nullable=True)  # 1-10
    employee_mood = Column(SQLEnum(EmployeeMood), nullable=True)
    
    # OKR snapshot
    okr_progress_snapshot = Column(JSON, nullable=True)  # Linked KRs and progress
    progress_notes = Column(Text, nullable=True)
    
    # Manager response
    manager_feedback = Column(Text, nullable=True)
    manager_responded_at = Column(DateTime, nullable=True)
    manager_response_quality = Column(Integer, nullable=True)  # 1-5 coaching quality
    
    # Action items
    action_items = Column(JSON, default=list)  # [{action, owner, due_date, status}]
    corrective_actions = Column(JSON, default=list)
    coaching_notes = Column(Text, nullable=True)
    
    # Threading
    is_latest = Column(Boolean, default=True)
    previous_checkin_id = Column(String(36), ForeignKey("continuous_checkins.id"), nullable=True)
    
    # Coaching workflow (not approval)
    workflow_status = Column(String(50), default=CheckinWorkflowStatus.DRAFT.value)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    performance_concern_flag = Column(Boolean, default=False)
    concern_notes = Column(Text, nullable=True)
    escalated_at = Column(DateTime, nullable=True)
    escalated_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    escalation_target_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    escalation_reason = Column(String(50), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    # Legacy alias — maps to workflow_status for backward compatibility
    status = Column(String(50), default=CheckinWorkflowStatus.DRAFT.value)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CheckinComment(Base):
    """Threaded comments on check-ins (coaching conversation)."""
    __tablename__ = "checkin_comments"
    __table_args__ = (Index("idx_checkin_comment_thread", "checkin_id", "parent_comment_id"),)
    
    id = Column(String(36), primary_key=True, default=gen_uuid)
    checkin_id = Column(String(36), ForeignKey("continuous_checkins.id"), nullable=False)
    commented_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    parent_comment_id = Column(String(36), ForeignKey("checkin_comments.id"), nullable=True)
    
    comment = Column(Text, nullable=False)
    comment_type = Column(String(50), nullable=True)  # COACHING, ACKNOWLEDGEMENT, ACTION, ESCALATION, CONCERN
    sentiment = Column(String(50), nullable=True)  # POSITIVE, NEUTRAL, CRITICAL
    is_system_event = Column(Boolean, default=False)
    
    commented_at = Column(DateTime, default=datetime.utcnow)


class CheckinEscalation(Base):
    """Exception-based escalation from manager to department head."""
    __tablename__ = "checkin_escalations"
    
    id = Column(String(36), primary_key=True, default=gen_uuid)
    checkin_id = Column(String(36), ForeignKey("continuous_checkins.id"), nullable=False)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    escalated_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    escalated_to_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    reason = Column(String(50), nullable=False)
    notes = Column(Text, nullable=True)
    status = Column(String(50), default="OPEN")  # OPEN, ACKNOWLEDGED, RESOLVED
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


class CheckinNotification(Base):
    """In-app notification queue for check-in coaching events."""
    __tablename__ = "checkin_notifications"
    __table_args__ = (Index("idx_checkin_notif_user", "recipient_user_id", "is_read"),)
    
    id = Column(String(36), primary_key=True, default=gen_uuid)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    checkin_id = Column(String(36), ForeignKey("continuous_checkins.id"), nullable=False)
    recipient_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    actor_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    event_type = Column(String(50), nullable=False)  # SUBMITTED, ACKNOWLEDGED, COMMENT, ACTION, ESCALATED, RESOLVED
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# EMPLOYEE PERFORMANCE REVIEWS
# ============================================================================

class EmployeePerformanceReview(Base):
    """
    Complete performance review lifecycle:
    Self → Manager → Skip-Level → HR Calibration → Final
    """
    __tablename__ = "employee_performance_reviews"
    __table_args__ = (
        Index("idx_employee_cycle", "employee_id", "review_cycle_id"),
        Index("idx_state", "current_state"),
        Index("idx_org_cycle", "org_id", "review_cycle_id"),
        UniqueConstraint("employee_id", "review_cycle_id", name="uc_one_review_per_cycle"),
    )

    id = Column(String(36), primary_key=True, default=gen_uuid)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    employee_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    # Review metadata
    review_cycle_id = Column(String(36), ForeignKey("perf_review_cycles.id"), nullable=False)
    review_period_start = Column(DateTime, nullable=True)
    review_period_end = Column(DateTime, nullable=True)
    
    # Hierarchy context
    manager_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    skip_level_manager_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    hr_reviewer_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    dept_head_reviewer_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    requires_dept_moderation = Column(Boolean, default=False)
    
    # Workflow state
    current_state = Column(SQLEnum(ReviewState), default=ReviewState.DRAFT)
    
    # Review sections
    self_review_id = Column(String(36), ForeignKey("review_sections.id"), nullable=True)
    self_submitted_at = Column(DateTime, nullable=True)
    
    manager_review_id = Column(String(36), ForeignKey("review_sections.id"), nullable=True)
    manager_review_submitted_at = Column(DateTime, nullable=True)
    
    skip_level_review_id = Column(String(36), ForeignKey("review_sections.id"), nullable=True)
    skip_level_submitted_at = Column(DateTime, nullable=True)
    skip_level_required = Column(Boolean, default=False)
    
    peer_feedback_ids = Column(JSON, default=list)  # Array of feedback response IDs
    
    hr_calibration_id = Column(String(36), ForeignKey("review_sections.id"), nullable=True)
    hr_calibration_submitted_at = Column(DateTime, nullable=True)
    calibration_notes = Column(Text, nullable=True)
    
    # Final rating
    final_rating = Column(SQLEnum(ReviewRating), nullable=True)
    final_score = Column(Float, nullable=True)  # 0-100
    rating_locked = Column(Boolean, default=False)
    finalized_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)
    
    # OKR integration
    okr_achievement_score = Column(Float, nullable=True)
    okr_ids = Column(JSON, default=list)  # List of OKR IDs reviewed
    
    # Metadata
    is_probation_review = Column(Boolean, default=False)
    promotion_eligible = Column(Boolean, default=False)
    promotion_recommended = Column(Boolean, default=False)
    attrition_risk = Column(String(50), nullable=True)  # LOW, MEDIUM, HIGH
    attrition_risk_reason = Column(Text, nullable=True)

    # AI review agent (manager-triggered after self-review)
    ai_review_status = Column(String(50), default="NONE")  # NONE, GENERATED, MANAGER_EDITED, SUBMITTED
    ai_review_payload = Column(JSON, nullable=True)
    ai_review_generated_at = Column(DateTime, nullable=True)
    ai_review_context_snapshot = Column(JSON, nullable=True)
    employee_performance_narrative = Column(Text, nullable=True)
    promotion_recommendation = Column(String(50), nullable=True)  # READY, NEEDS_DEVELOPMENT, NOT_READY
    promotion_rationale = Column(Text, nullable=True)
    shared_with_employee_at = Column(DateTime, nullable=True)
    submitted_to_dept_head_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================================================
# REVIEW CONTENT SECTIONS
# ============================================================================

class ReviewSection(Base):
    """
    Content for each review stage: self, manager, skip-level, HR calibration
    """
    __tablename__ = "review_sections"
    __table_args__ = (
        Index("idx_performance_review", "performance_review_id"),
        Index("idx_section_type", "section_type"),
    )

    id = Column(String(36), primary_key=True, default=gen_uuid)
    performance_review_id = Column(String(36), ForeignKey("employee_performance_reviews.id"), nullable=False)
    section_type = Column(SQLEnum(SectionType), nullable=False)
    submitted_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    # SELF REVIEW CONTENT
    self_achievements = Column(Text, nullable=True)
    self_okr_assessment = Column(JSON, nullable=True)  # [{okr_id, kr_progress, quality, alignment}]
    self_strengths = Column(Text, nullable=True)
    self_challenges = Column(Text, nullable=True)
    self_growth_areas = Column(JSON, default=list)
    self_evidence = Column(Text, nullable=True)
    
    # MANAGER REVIEW CONTENT
    manager_okr_outcomes = Column(Text, nullable=True)
    manager_behavioral_scores = Column(JSON, nullable=True)  # {competency_id: score}
    manager_collaboration = Column(Text, nullable=True)
    manager_ownership = Column(Text, nullable=True)
    manager_accountability = Column(Text, nullable=True)
    manager_execution_quality = Column(Text, nullable=True)
    manager_feedback = Column(Text, nullable=True)
    manager_promotion_eligible = Column(Boolean, nullable=True)
    manager_promotion_recommended = Column(Boolean, nullable=True)
    manager_pip_needed = Column(Boolean, nullable=True)
    
    # SKIP-LEVEL REVIEW CONTENT
    skip_level_perspective = Column(Text, nullable=True)
    skip_level_strategic_impact = Column(Text, nullable=True)
    skip_level_leadership_potential = Column(Boolean, nullable=True)
    skip_level_succession_ready = Column(Boolean, nullable=True)
    skip_level_recommended_development = Column(Text, nullable=True)
    
    # HR CALIBRATION CONTENT
    calibration_group_id = Column(String(36), ForeignKey("calibration_groups.id"), nullable=True)
    hr_relative_ranking = Column(Integer, nullable=True)
    hr_market_positioning = Column(String(50), nullable=True)  # BELOW, AT, ABOVE
    hr_salary_adjustment = Column(Float, nullable=True)
    
    # Status
    approval_status = Column(SQLEnum(ApprovalStatus), default=ApprovalStatus.DRAFT)
    
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================================================
# 360 FEEDBACK
# ============================================================================

class FeedbackTemplate(Base):
    """Configurable 360 feedback survey templates"""
    __tablename__ = "feedback_templates"
    
    id = Column(String(36), primary_key=True, default=gen_uuid)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    
    name = Column(String(255), nullable=False)
    feedback_type = Column(SQLEnum(FeedbackType), nullable=False)
    role_type = Column(String(50), nullable=True)  # Specific role or NULL=all
    
    # Questions
    questions = Column(JSON, nullable=False)  # [{id, question, scale, required}]
    
    enabled = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class FeedbackResponse(Base):
    """Submitted 360 feedback"""
    __tablename__ = "feedback_responses"
    __table_args__ = (
        Index("idx_review_feedback", "performance_review_id"),
        Index("idx_feedback_type", "feedback_type"),
    )
    
    id = Column(String(36), primary_key=True, default=gen_uuid)
    performance_review_id = Column(String(36), ForeignKey("employee_performance_reviews.id"), nullable=False)
    feedback_template_id = Column(String(36), ForeignKey("feedback_templates.id"), nullable=False)
    
    feedback_giver_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    feedback_type = Column(SQLEnum(FeedbackType), nullable=False)
    is_anonymous = Column(Boolean, default=True)
    
    # Responses
    responses = Column(JSON, nullable=False)  # {question_id: response}
    overall_feedback = Column(Text, nullable=True)
    sentiment_score = Column(Float, nullable=True)  # -1 to +1
    
    submitted_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class FeedbackSynthesis(Base):
    """Aggregated 360 feedback insights"""
    __tablename__ = "feedback_synthesis"
    
    id = Column(String(36), primary_key=True, default=gen_uuid)
    performance_review_id = Column(String(36), ForeignKey("employee_performance_reviews.id"), nullable=False)
    
    # Aggregated scores
    peer_feedback_score = Column(Float, nullable=True)
    peer_feedback_count = Column(Integer, default=0)
    
    subordinate_feedback_score = Column(Float, nullable=True)
    subordinate_feedback_count = Column(Integer, default=0)
    
    cross_functional_score = Column(Float, nullable=True)
    cross_functional_count = Column(Integer, default=0)
    
    # Themes
    strengths_consensus = Column(JSON, default=list)  # [{theme, count}]
    development_areas_consensus = Column(JSON, default=list)
    
    # Assessment
    overall_external_perception_score = Column(Float, nullable=True)
    perception_vs_self_gap = Column(Float, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# COMPETENCY FRAMEWORK
# ============================================================================

class CompetencyFramework(Base):
    """Role-based competency models"""
    __tablename__ = "competency_frameworks"
    __table_args__ = (
        UniqueConstraint("org_id", "role_type", "department_id", name="uc_framework_scope"),
    )
    
    id = Column(String(36), primary_key=True, default=gen_uuid)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    role_type = Column(String(50), nullable=False)  # MANAGER, ENGINEER, SUPERVISOR, etc.
    department_id = Column(String(36), ForeignKey("org_nodes.id"), nullable=True)  # NULL=all
    
    name = Column(String(255), nullable=False)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Competency(Base):
    """Individual competencies within a framework"""
    __tablename__ = "competencies"
    
    id = Column(String(36), primary_key=True, default=gen_uuid)
    framework_id = Column(String(36), ForeignKey("competency_frameworks.id"), nullable=False)
    
    name = Column(String(255), nullable=False)  # "Leadership", "Technical Excellence"
    description = Column(Text, nullable=True)
    weight = Column(Float, default=1.0)  # Relative importance
    proficiency_levels = Column(JSON, nullable=False)  # [{level, name, description}]
    enabled = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class CompetencyAssessment(Base):
    """Individual competency ratings in a review"""
    __tablename__ = "competency_assessments"
    
    id = Column(String(36), primary_key=True, default=gen_uuid)
    review_section_id = Column(String(36), ForeignKey("review_sections.id"), nullable=False)
    competency_id = Column(String(36), ForeignKey("competencies.id"), nullable=False)
    
    proficiency_level = Column(Integer, nullable=False)  # 1-5
    assessor_comments = Column(Text, nullable=True)
    assessed_at = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# SCORING & CALCULATION
# ============================================================================

class ScoringConfiguration(Base):
    """Configurable weightings for final rating calculation"""
    __tablename__ = "scoring_configurations"
    
    id = Column(String(36), primary_key=True, default=gen_uuid)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    role_type = Column(String(50), nullable=True)  # NULL=default for all roles
    
    # Weights (must sum to 100)
    okr_achievement_weight = Column(Float, default=40.0)
    kr_quality_weight = Column(Float, default=20.0)
    manager_feedback_weight = Column(Float, default=15.0)
    behavioral_competency_weight = Column(Float, default=10.0)
    peer_feedback_weight = Column(Float, default=10.0)
    continuous_checkin_weight = Column(Float, default=5.0)
    
    # Rating thresholds
    exceeds_expectations_threshold = Column(Float, default=85.0)
    meets_expectations_threshold = Column(Float, default=65.0)
    below_expectations_threshold = Column(Float, default=50.0)
    
    # Bias mitigation
    enable_calibration_review = Column(Boolean, default=True)
    enable_peer_consistency_check = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ReviewCalculation(Base):
    """Audit trail of score calculations"""
    __tablename__ = "review_calculations"
    
    id = Column(String(36), primary_key=True, default=gen_uuid)
    performance_review_id = Column(String(36), ForeignKey("employee_performance_reviews.id"), nullable=False)
    
    # Component scores
    okr_achievement_score = Column(Float, nullable=True)
    kr_quality_score = Column(Float, nullable=True)
    manager_feedback_score = Column(Float, nullable=True)
    behavioral_competency_score = Column(Float, nullable=True)
    peer_feedback_score = Column(Float, nullable=True)
    continuous_checkin_score = Column(Float, nullable=True)
    
    # Weighted sum
    calculated_final_score = Column(Float, nullable=True)
    final_rating = Column(SQLEnum(ReviewRating), nullable=True)
    
    # Confidence & flags
    confidence_score = Column(Float, nullable=True)
    bias_flags = Column(JSON, default=list)
    
    override_applied = Column(Boolean, default=False)
    override_reason = Column(Text, nullable=True)
    
    calculation_timestamp = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# CALIBRATION & MODERATION
# ============================================================================

class CalibrationGroup(Base):
    """Groups of peers for calibration/normalization"""
    __tablename__ = "calibration_groups"
    
    id = Column(String(36), primary_key=True, default=gen_uuid)
    review_cycle_id = Column(String(36), ForeignKey("perf_review_cycles.id"), nullable=False)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    
    calibration_type = Column(SQLEnum(CalibrationScope), nullable=False)
    scope_id = Column(String(36), nullable=True)  # department_id, plant_id, etc.
    facilitator_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    # Employee list
    employee_ids = Column(JSON, default=list)
    total_headcount = Column(Integer, default=0)
    
    # Results
    calibration_completed = Column(Boolean, default=False)
    calibration_completed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ReviewAdjustment(Base):
    """Adjustments made during calibration or appeal"""
    __tablename__ = "review_adjustments"
    
    id = Column(String(36), primary_key=True, default=gen_uuid)
    performance_review_id = Column(String(36), ForeignKey("employee_performance_reviews.id"), nullable=False)
    
    adjustment_reason = Column(SQLEnum(AdjustmentReason), nullable=False)
    previous_score = Column(Float, nullable=True)
    new_score = Column(Float, nullable=True)
    
    adjusted_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    adjustment_notes = Column(Text, nullable=True)
    
    applied_at = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# AUDIT TRAIL
# ============================================================================

class ReviewAuditLog(Base):
    """Audit trail for all review actions"""
    __tablename__ = "review_audit_logs"
    __table_args__ = (
        Index("idx_review_audit", "performance_review_id"),
        Index("idx_action_time", "action_timestamp"),
    )
    
    id = Column(String(36), primary_key=True, default=gen_uuid)
    performance_review_id = Column(String(36), ForeignKey("employee_performance_reviews.id"), nullable=False)
    
    action = Column(String(100), nullable=False)  # CREATED, SUBMITTED, APPROVED, FINALIZED
    actor_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    old_state = Column(String(50), nullable=True)
    new_state = Column(String(50), nullable=True)
    changes = Column(JSON, nullable=True)  # {field: {old, new}}
    
    action_timestamp = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String(45), nullable=True)
    notes = Column(Text, nullable=True)
