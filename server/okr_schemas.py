"""
OKR Schemas and DTOs for API requests/responses
Pydantic models for validation and serialization
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator
from enum import Enum


# ============================================================================
# ENUMS (mirrored from models)
# ============================================================================

class OKRLevelType(str, Enum):
    ORGANIZATION = "organization"
    REGION = "region"
    PLANT = "plant"
    DEPARTMENT = "department"
    TEAM = "team"
    EMPLOYEE = "employee"


class OKRStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class MetricType(str, Enum):
    PERCENTAGE = "percentage"
    COUNT = "count"
    AMOUNT = "amount"
    RATIO = "ratio"
    DURATION = "duration"
    BINARY = "binary"


class TrendStatus(str, Enum):
    AHEAD = "ahead"
    ON_TRACK = "on_track"
    BEHIND = "behind"
    CRITICAL_DELAY = "critical_delay"


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    NEEDS_ATTENTION = "needs_attention"
    CRITICAL = "critical"
    BLOCKED = "blocked"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlignmentType(str, Enum):
    STRATEGIC = "strategic"
    OPERATIONAL = "operational"
    DEPENDENCY = "dependency"
    SUPPORT = "support"


# ============================================================================
# KEY RESULT SCHEMAS
# ============================================================================

class KeyResultCreateRequest(BaseModel):
    """Request to create a Key Result"""
    title: str = Field(..., min_length=5, max_length=300)
    metric_type: MetricType
    start_value: float = Field(default=0.0)
    target_value: float = Field(...)
    unit: Optional[str] = Field(None, max_length=50)
    weight: int = Field(default=3, ge=1, le=5)
    is_lower_better: bool = Field(default=False)


class KeyResultUpdateRequest(BaseModel):
    """Request to update a Key Result"""
    title: Optional[str] = Field(None, min_length=5, max_length=300)
    metric_type: Optional[MetricType] = None
    target_value: Optional[float] = None
    unit: Optional[str] = Field(None, max_length=50)
    weight: Optional[int] = Field(None, ge=1, le=5)
    is_lower_better: Optional[bool] = None


class KeyResultProgressUpdate(BaseModel):
    """Request to update KR progress"""
    current_value: float = Field(...)
    notes: Optional[str] = None


class KeyResultResponse(BaseModel):
    """Response DTO for Key Result"""
    id: str
    title: str
    metric_type: MetricType
    start_value: float
    current_value: float
    target_value: float
    unit: Optional[str]
    weight: int
    is_lower_better: bool
    progress: float  # 0-100
    expected_progress: float  # Based on elapsed time
    trend: TrendStatus
    is_completed: bool
    created_at: datetime
    updated_at: datetime
    last_updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# OKR SCHEMAS
# ============================================================================

class OKRCreateRequest(BaseModel):
    """Request to create an OKR"""
    objective: str = Field(..., min_length=10, max_length=500)
    description: Optional[str] = None
    level_type: OKRLevelType
    weight: int = Field(default=3, ge=1, le=5)
    quarter: int = Field(..., ge=1, le=4)
    year: int = Field(...)
    start_date: datetime
    end_date: datetime
    key_results: List[KeyResultCreateRequest] = Field(..., min_items=1, max_items=5)

    @validator("end_date")
    def validate_end_date(cls, v, values):
        if "start_date" in values and v <= values["start_date"]:
            raise ValueError("end_date must be after start_date")
        return v


class OKRUpdateRequest(BaseModel):
    """Request to update an OKR"""
    objective: Optional[str] = Field(None, min_length=10, max_length=500)
    description: Optional[str] = None
    weight: Optional[int] = Field(None, ge=1, le=5)
    status: Optional[OKRStatus] = None
    confidence_score: Optional[float] = Field(None, ge=0, le=100)


class OKRDetailResponse(BaseModel):
    """Detailed OKR response with all calculations"""
    id: str
    objective: str
    description: Optional[str]
    owner_id: str
    level_type: OKRLevelType
    weight: int
    quarter: int
    year: int
    status: OKRStatus
    
    # Progress and health
    progress: float  # Weighted average of KRs
    trend_status: TrendStatus
    health_status: HealthStatus
    risk_level: RiskLevel
    confidence_score: float
    
    # Key Results
    key_results: List[KeyResultResponse]
    
    # Timeline
    start_date: datetime
    end_date: datetime
    created_at: datetime
    updated_at: datetime
    last_progress_update: Optional[datetime]

    class Config:
        from_attributes = True


class OKRSummaryResponse(BaseModel):
    """Summary OKR response for list views"""
    id: str
    objective: str
    owner_id: str
    level_type: OKRLevelType
    progress: float
    trend_status: TrendStatus
    health_status: HealthStatus
    status: OKRStatus
    quarter: int
    year: int


# ============================================================================
# ALIGNMENT SCHEMAS
# ============================================================================

class OKRAlignmentCreateRequest(BaseModel):
    """Request to create OKR alignment"""
    parent_okr_id: str
    child_okr_id: str
    contribution_weight: int = Field(default=3, ge=1, le=5)
    alignment_type: AlignmentType = AlignmentType.OPERATIONAL


class OKRAlignmentResponse(BaseModel):
    """Response DTO for OKR Alignment"""
    id: str
    parent_okr_id: str
    child_okr_id: str
    contribution_weight: int
    alignment_type: AlignmentType
    parent_okr: OKRSummaryResponse
    child_okr: OKRSummaryResponse
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# DASHBOARD SCHEMAS
# ============================================================================

class DashboardOKRMetrics(BaseModel):
    """OKR metrics for dashboard"""
    total_okrs: int
    total_key_results: int
    avg_progress: float
    okrs_on_track: int
    okrs_at_risk: int
    okrs_blocked: int
    health_breakdown: dict  # {health_status: count}


class DashboardOKRTrend(BaseModel):
    """Trend information for dashboard"""
    okr_id: str
    objective: str
    current_progress: float
    previous_progress: float
    trend: TrendStatus
    days_until_deadline: int


class CEODashboardResponse(BaseModel):
    """CEO-level dashboard with organization-wide insights"""
    metrics: DashboardOKRMetrics
    organization_okrs: List[OKRDetailResponse]
    regional_alignment: List[dict]  # Region name + their progress
    at_risk_okrs: List[OKRSummaryResponse]
    top_contributors: List[dict]  # Users/teams with best progress
    trend_summary: List[DashboardOKRTrend]


class RegionHeadDashboardResponse(BaseModel):
    """Region Head dashboard"""
    region_okrs: List[OKRDetailResponse]
    region_metrics: DashboardOKRMetrics
    plant_performance: List[dict]
    team_alignment: List[OKRSummaryResponse]
    pending_alignments: int


class PlantHeadDashboardResponse(BaseModel):
    """Plant Head dashboard"""
    plant_okrs: List[OKRDetailResponse]
    plant_metrics: DashboardOKRMetrics
    department_performance: List[dict]
    critical_krs: List[KeyResultResponse]
    health_summary: dict


class DepartmentHeadDashboardResponse(BaseModel):
    """Department Head dashboard"""
    dept_okrs: List[OKRDetailResponse]
    dept_metrics: DashboardOKRMetrics
    team_krs: List[KeyResultResponse]
    active_alignments: List[OKRAlignmentResponse]


class TeamLeadDashboardResponse(BaseModel):
    """Team Lead dashboard"""
    team_okrs: List[OKRDetailResponse]
    team_metrics: DashboardOKRMetrics
    employee_progress: List[dict]
    team_health: HealthStatus


class EmployeeDashboardResponse(BaseModel):
    """Employee dashboard"""
    personal_okrs: List[OKRDetailResponse]
    personal_metrics: DashboardOKRMetrics
    alignment_visibility: List[OKRSummaryResponse]
    recent_updates: List[dict]


# ============================================================================
# ANALYTICS SCHEMAS
# ============================================================================

class OKRProgressAnalytics(BaseModel):
    """Analytics for OKR progress over time"""
    okr_id: str
    timeline: List[dict]  # {date: progress}
    velocity: float  # Progress per day
    projected_completion: Optional[datetime]
    confidence_trend: List[float]


class AlignmentGraphNode(BaseModel):
    """Node in alignment graph for visualization"""
    okr_id: str
    objective: str
    progress: float
    health: HealthStatus
    level: OKRLevelType


class AlignmentGraphEdge(BaseModel):
    """Edge in alignment graph"""
    parent_id: str
    child_id: str
    contribution_weight: int
    alignment_type: AlignmentType


class AlignmentGraphResponse(BaseModel):
    """Full alignment graph for visualization"""
    nodes: List[AlignmentGraphNode]
    edges: List[AlignmentGraphEdge]


# ============================================================================
# BULK OPERATION SCHEMAS
# ============================================================================

class BulkOKRProgressUpdate(BaseModel):
    """Bulk update for multiple KR progress values"""
    updates: List[dict]  # {kr_id: str, current_value: float, notes: Optional[str]}


class BulkOKRResponse(BaseModel):
    """Response for bulk operations"""
    success: int
    failed: int
    errors: Optional[List[dict]]
