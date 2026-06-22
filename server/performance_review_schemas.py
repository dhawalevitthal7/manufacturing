"""
Performance Review System Schemas
Pydantic models for request/response validation and API contracts.
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ============================================================================
# REVIEW CYCLE SCHEMAS
# ============================================================================

class ReviewCycleCreate(BaseModel):
    """Create a new review cycle"""
    cycle_type: str  # WEEKLY, MONTHLY, QUARTERLY, HALF_YEARLY, ANNUAL
    name: str
    description: Optional[str] = None
    start_date: datetime
    end_date: datetime
    submission_start: datetime
    submission_end: datetime
    
    # Auto-management
    auto_lock_enabled: bool = False
    auto_lock_date: Optional[datetime] = None
    auto_publish_enabled: bool = False
    auto_publish_date: Optional[datetime] = None
    
    # Scope
    applies_to_levels: List[int] = [0, 1, 2, 3, 4, 5]
    eligible_plant_ids: Optional[List[str]] = None
    eligible_dept_ids: Optional[List[str]] = None
    eligible_role_types: Optional[List[str]] = None


class ReviewCycleUpdate(BaseModel):
    """Update review cycle"""
    name: Optional[str] = None
    description: Optional[str] = None
    submission_start: Optional[datetime] = None
    submission_end: Optional[datetime] = None
    auto_lock_enabled: Optional[bool] = None
    auto_lock_date: Optional[datetime] = None
    status: Optional[str] = None  # PLANNED, ACTIVE, LOCKED, CLOSED


class ReviewCycleResponse(BaseModel):
    """Review cycle response"""
    id: str
    org_id: str
    cycle_type: str
    name: str
    description: Optional[str]
    start_date: datetime
    end_date: datetime
    submission_start: datetime
    submission_end: datetime
    status: str
    applies_to_levels: List[int]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# CONTINUOUS CHECK-IN SCHEMAS
# ============================================================================

class ContinuousCheckinSubmit(BaseModel):
    """Employee submits weekly/monthly check-in"""
    checkin_week: int
    checkin_month: Optional[int] = None
    checkin_date: datetime
    
    # Achievements
    achievements: str
    key_wins: List[str] = []
    
    # Challenges
    blockers: str
    risks: List[Dict[str, Any]] = []  # [{risk, severity, mitigation}]
    support_needed: Optional[str] = None
    
    # Confidence & metrics
    confidence_score: Optional[float] = Field(None, ge=0, le=100)
    engagement_score: Optional[int] = Field(None, ge=1, le=10)
    employee_mood: Optional[str] = None  # VERY_POSITIVE, POSITIVE, NEUTRAL, CONCERNING, CRITICAL
    
    # OKR snapshot
    okr_progress_snapshot: Optional[Dict[str, Any]] = None
    progress_notes: Optional[str] = None


class ManagerCheckinResponse(BaseModel):
    """Manager provides feedback on check-in"""
    manager_feedback: str
    manager_response_quality: int = Field(ge=1, le=5)
    action_items: List[Dict[str, Any]] = []
    corrective_actions: Optional[List[Dict[str, Any]]] = None
    coaching_notes: Optional[str] = None


class ContinuousCheckinResponse(BaseModel):
    """Continuous check-in response"""
    id: str
    employee_id: str
    manager_id: str
    checkin_week: int
    checkin_date: datetime
    achievements: Optional[str]
    key_wins: List[str]
    blockers: Optional[str]
    confidence_score: Optional[float]
    engagement_score: Optional[int]
    employee_mood: Optional[str]
    status: str
    submitted_at: Optional[datetime]
    manager_feedback: Optional[str]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# PERFORMANCE REVIEW SCHEMAS
# ============================================================================

class SelfReviewSubmit(BaseModel):
    """Employee self-review submission"""
    achievements: str
    major_wins: List[str] = []
    
    okr_self_assessment: List[Dict[str, Any]] = []
    # [{okr_id, title, kr_id, kr_title, self_assessed_completion, quality_assessment, alignment_contribution}]
    
    strengths: Optional[str] = None
    challenges: Optional[str] = None
    growth_areas: List[str] = []
    evidence: Optional[str] = None


class ManagerReviewSubmit(BaseModel):
    """Manager review submission"""
    okr_outcomes_assessment: Optional[str] = None
    kr_completion_accuracy: Optional[float] = None
    kr_quality_assessment: Optional[str] = None
    
    # Competency scores
    behavioral_competency_scores: Dict[str, int] = {}
    
    # Assessments
    collaboration_assessment: Optional[str] = None
    ownership_assessment: Optional[str] = None
    accountability_assessment: Optional[str] = None
    execution_quality_assessment: Optional[str] = None
    
    # Feedback
    manager_feedback: Optional[str] = None
    strengths_observed: Optional[str] = None
    development_areas_observed: Optional[str] = None
    
    # Recommendations
    promotion_eligible: bool = False
    promotion_recommended: bool = False
    performance_improvement_plan_needed: bool = False
    
    # Risk
    attrition_risk: Optional[str] = None  # LOW, MEDIUM, HIGH


class SkipLevelReviewSubmit(BaseModel):
    """Skip-level manager review"""
    executive_perspective: Optional[str] = None
    strategic_impact_assessment: Optional[str] = None
    
    leadership_potential: bool = False
    next_level_readiness: bool = False
    succession_ready: bool = False
    
    recommended_development: Optional[str] = None
    recommended_next_role: Optional[str] = None


class PerformanceReviewResponse(BaseModel):
    """Performance review response"""
    id: str
    employee_id: str
    manager_id: str
    review_cycle_id: str
    current_state: str
    
    final_rating: Optional[str]
    final_score: Optional[float]
    rating_locked: bool
    
    okr_achievement_score: Optional[float]
    promotion_eligible: bool
    promotion_recommended: bool
    attrition_risk: Optional[str]
    
    created_at: datetime
    finalized_at: Optional[datetime]
    published_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# 360 FEEDBACK SCHEMAS
# ============================================================================

class FeedbackRequest(BaseModel):
    """Request to provide 360 feedback"""
    performance_review_id: str
    feedback_giver_user_id: str
    feedback_type: str  # PEER, SUBORDINATE, CROSS_FUNCTIONAL
    is_anonymous: bool = True


class FeedbackResponse(BaseModel):
    """Submit 360 feedback response"""
    responses: Dict[str, Any]  # {question_id: response}
    overall_feedback: Optional[str] = None
    strengths_observed: Optional[List[str]] = None
    development_areas: Optional[List[str]] = None


class FeedbackSynthesisResponse(BaseModel):
    """Aggregated 360 feedback"""
    id: str
    performance_review_id: str
    
    peer_feedback_score: Optional[float]
    peer_feedback_count: int
    
    subordinate_feedback_score: Optional[float]
    subordinate_feedback_count: int
    
    cross_functional_score: Optional[float]
    cross_functional_count: int
    
    strengths_consensus: List[Dict[str, Any]]
    development_areas_consensus: List[Dict[str, Any]]
    
    overall_external_perception_score: Optional[float]
    perception_vs_self_gap: Optional[float]
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# SCORING & CALCULATION SCHEMAS
# ============================================================================

class ScoringConfigurationUpdate(BaseModel):
    """Update scoring weights"""
    okr_achievement_weight: Optional[float] = None
    kr_quality_weight: Optional[float] = None
    manager_feedback_weight: Optional[float] = None
    behavioral_competency_weight: Optional[float] = None
    peer_feedback_weight: Optional[float] = None
    continuous_checkin_weight: Optional[float] = None
    
    exceeds_expectations_threshold: Optional[float] = None
    meets_expectations_threshold: Optional[float] = None
    below_expectations_threshold: Optional[float] = None


class ReviewCalculationResponse(BaseModel):
    """Score calculation breakdown"""
    id: str
    performance_review_id: str
    
    okr_achievement_score: Optional[float]
    kr_quality_score: Optional[float]
    manager_feedback_score: Optional[float]
    behavioral_competency_score: Optional[float]
    peer_feedback_score: Optional[float]
    continuous_checkin_score: Optional[float]
    
    calculated_final_score: Optional[float]
    final_rating: Optional[str]
    
    confidence_score: Optional[float]
    bias_flags: List[str]
    
    override_applied: bool
    override_reason: Optional[str]
    
    calculation_timestamp: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# COMPETENCY SCHEMAS
# ============================================================================

class CompetencyFrameworkCreate(BaseModel):
    """Create competency framework"""
    role_type: str
    name: str
    department_id: Optional[str] = None
    enabled: bool = True


class CompetencyCreate(BaseModel):
    """Add competency to framework"""
    name: str
    description: Optional[str] = None
    weight: float = 1.0
    proficiency_levels: List[Dict[str, Any]]  # [{level: 1, name: "...", description: "..."}]
    enabled: bool = True
    display_order: int = 0


class CompetencyResponse(BaseModel):
    """Competency with assessment info"""
    id: str
    framework_id: str
    name: str
    description: Optional[str]
    weight: float
    proficiency_levels: List[Dict[str, Any]]
    enabled: bool
    
    model_config = ConfigDict(from_attributes=True)


class CompetencyAssessmentSubmit(BaseModel):
    """Assess competency in review"""
    competency_id: str
    proficiency_level: int = Field(ge=1, le=5)
    assessor_comments: Optional[str] = None


# ============================================================================
# CALIBRATION SCHEMAS
# ============================================================================

class CalibrationGroupCreate(BaseModel):
    """Create calibration group"""
    review_cycle_id: str
    calibration_type: str  # DEPARTMENT, PLANT, FUNCTION, PEER_BAND
    scope_id: Optional[str] = None
    facilitator_user_id: Optional[str] = None
    employee_ids: List[str]


class CalibrationGroupUpdate(BaseModel):
    """Complete calibration"""
    calibration_completed: bool = True
    notes: Optional[str] = None
    adjustments: Dict[str, float] = {}  # {review_id: score_adjustment}


class CalibrationGroupResponse(BaseModel):
    """Calibration group response"""
    id: str
    review_cycle_id: str
    calibration_type: str
    employee_ids: List[str]
    total_headcount: int
    calibration_completed: bool
    calibration_completed_at: Optional[datetime]
    notes: Optional[str]
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# DASHBOARD SCHEMAS
# ============================================================================

class EmployeeDashboardResponse(BaseModel):
    """Employee performance dashboard"""
    current_reviews: List[PerformanceReviewResponse]
    latest_checkin: Optional[ContinuousCheckinResponse]
    
    okr_progress: Dict[str, Any]  # {okr_id: {...}}
    
    past_reviews: List[Dict[str, Any]]
    average_rating: Optional[float]
    
    engagement_trend: List[float]  # Last 4 weeks
    mood_trend: List[str]


class ManagerDashboardResponse(BaseModel):
    """Manager team performance dashboard"""
    team_size: int
    reviews_submitted: int
    reviews_total: int
    
    team_avg_performance: float
    high_performers: int
    at_risk_count: int
    
    team_member_summaries: List[Dict[str, Any]]
    
    coaching_needed: int
    outstanding_action_items: int


class DepartmentDashboardResponse(BaseModel):
    """Department analytics"""
    total_employees: int
    avg_performance: float
    org_avg_performance: float
    
    high_performers: int
    at_risk: int
    attrition_risk_high: int
    
    rating_distribution: Dict[str, int]
    okr_performance_correlation: float
    
    team_by_team: List[Dict[str, Any]]
    bias_analytics: Dict[str, Any]


class OrganizationDashboardResponse(BaseModel):
    """Organization talent analytics"""
    total_employees: int
    avg_performance: float
    reviews_completed: int
    reviews_total: int
    
    avg_engagement: float
    attrition_risk_count: int
    promotion_ready_count: int
    
    performance_by_level: List[Dict[str, Any]]
    performance_by_region: List[Dict[str, Any]]
    
    high_potentials: List[Dict[str, Any]]
    attrition_risks: List[Dict[str, Any]]
    
    performance_trend: List[float]  # QoQ trend


# ============================================================================
# AUDIT TRAIL
# ============================================================================

class AuditLogResponse(BaseModel):
    """Review audit trail entry"""
    id: str
    performance_review_id: str
    action: str
    actor_user_id: str
    
    old_state: Optional[str]
    new_state: Optional[str]
    changes: Optional[Dict[str, Any]]
    
    action_timestamp: datetime
    notes: Optional[str]
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# BULK OPERATIONS
# ============================================================================

class BulkReviewInitiation(BaseModel):
    """Bulk create reviews for cycle"""
    review_cycle_id: str
    employee_ids: Optional[List[str]] = None  # None = all eligible
    skip_existing: bool = True


class BulkCheckinReminder(BaseModel):
    """Bulk send check-in reminders"""
    checkin_week: int
    department_ids: Optional[List[str]] = None
    plant_ids: Optional[List[str]] = None


class BulkCalibrationInitiation(BaseModel):
    """Bulk create calibration groups"""
    review_cycle_id: str
    calibration_type: str  # DEPARTMENT, PLANT, etc.
    scope_ids: List[str]
    facilitator_user_id: Optional[str] = None
