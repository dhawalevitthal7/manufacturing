"""
OKR Progress and Alignment Engine Models
Production-grade SQLAlchemy models for enterprise OKR management
"""

from datetime import datetime
from enum import Enum
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, ForeignKey,
    Text, Enum as SQLEnum, UniqueConstraint, Index, CheckConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from server.database import Base


# ============================================================================
# ENUMS
# ============================================================================

class OKRLevelType(str, Enum):
    """Hierarchy levels for OKRs"""
    ORGANIZATION = "organization"
    REGION = "region"
    PLANT = "plant"
    DEPARTMENT = "department"
    TEAM = "team"
    EMPLOYEE = "employee"


class OKRStatus(str, Enum):
    """OKR lifecycle status"""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class MetricType(str, Enum):
    """Types of Key Result metrics"""
    PERCENTAGE = "percentage"  # 0-100
    COUNT = "count"            # Integer
    AMOUNT = "amount"          # Numeric with unit
    RATIO = "ratio"            # Ratio-based
    DURATION = "duration"      # Time-based
    BINARY = "binary"          # True/False


class TrendStatus(str, Enum):
    """Trend direction"""
    AHEAD = "ahead"            # Ahead of schedule
    ON_TRACK = "on_track"      # On schedule
    BEHIND = "behind"          # Behind schedule
    CRITICAL_DELAY = "critical_delay"  # Severely behind


class HealthStatus(str, Enum):
    """OKR health state"""
    HEALTHY = "healthy"
    NEEDS_ATTENTION = "needs_attention"
    CRITICAL = "critical"
    BLOCKED = "blocked"


class RiskLevel(str, Enum):
    """Risk assessment"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlignmentType(str, Enum):
    """Types of OKR alignment relationships"""
    STRATEGIC = "strategic"    # Child directly supports parent strategy
    OPERATIONAL = "operational"  # Child operationalizes parent
    DEPENDENCY = "dependency"  # Child depends on parent
    SUPPORT = "support"        # Child provides supporting capability


class SubmissionStatus(str, Enum):
    """OKR progress submission workflow status"""
    DRAFT = "draft"             # Progress being edited
    SUBMITTED = "submitted"     # Awaiting approval
    APPROVED = "approved"       # Approved by validator
    REJECTED = "rejected"       # Rejected by validator
    REVISE_REQUESTED = "revise_requested"  # Changes requested


class ApprovalAction(str, Enum):
    """Actions taken during approval"""
    SUBMIT = "submit"           # Submit for approval
    APPROVE = "approve"         # Approve submission
    REJECT = "reject"           # Reject submission
    OVERRIDE = "override"       # Override previous approval
    REQUEST_REVISION = "request_revision"  # Request changes


# ============================================================================
# OKR MODELS
# ============================================================================

class OKR(Base):
    """
    Objective and Key Results entity.
    Every level (Organization, Region, Plant, Department, Team, Employee)
    can own OKRs with their own KRs.
    """
    __tablename__ = "okrs"
    __table_args__ = (
        Index("idx_okr_owner_level", "owner_id", "level_type"),
        Index("idx_okr_quarter_year", "quarter", "year"),
        Index("idx_okr_status", "status"),
    )

    id = Column(String(36), primary_key=True, index=True)
    objective = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    
    # Owner information
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    level_type = Column(SQLEnum(OKRLevelType), nullable=False)
    
    # Organization context
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    region_id = Column(String(36), ForeignKey("org_nodes.id"), nullable=True)
    plant_id = Column(String(36), ForeignKey("org_nodes.id"), nullable=True)
    department_id = Column(String(36), ForeignKey("org_nodes.id"), nullable=True)
    team_id = Column(String(36), ForeignKey("org_nodes.id"), nullable=True)
    
    # Weighting and importance
    weight = Column(Integer, default=3, nullable=False)  # 1-5 importance
    
    # Timeline
    quarter = Column(Integer, nullable=False)  # Q1-Q4
    year = Column(Integer, nullable=False)
    start_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=False)
    
    # Status and scoring
    status = Column(SQLEnum(OKRStatus), default=OKRStatus.DRAFT, nullable=False)
    confidence_score = Column(Float, default=50.0)  # 0-100
    risk_level = Column(SQLEnum(RiskLevel), default=RiskLevel.MEDIUM)
    
    # Submission and approval tracking
    submission_status = Column(SQLEnum(SubmissionStatus), default=SubmissionStatus.DRAFT, nullable=False)
    submitted_at = Column(DateTime, nullable=True)  # When submitted for approval
    submitted_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)  # Who submitted
    approved_at = Column(DateTime, nullable=True)  # When approved
    approved_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)  # Who approved
    approval_comments = Column(Text, nullable=True)  # Reviewer comments
    
    # Computed fields (cached, not permanent)
    progress = Column(Float, default=0.0)  # Computed dynamically
    trend_status = Column(SQLEnum(TrendStatus), default=TrendStatus.ON_TRACK)
    health_status = Column(SQLEnum(HealthStatus), default=HealthStatus.HEALTHY)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_progress_update = Column(DateTime, nullable=True)
    
    # Relationships
    key_results = relationship("KeyResult", back_populates="okr", cascade="all, delete-orphan")
    owner = relationship("User", foreign_keys=[owner_id])
    submitted_by = relationship("User", foreign_keys=[submitted_by_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    organization = relationship("Organization", foreign_keys=[org_id])
    alignment_children = relationship(
        "OKRAlignment",
        foreign_keys="OKRAlignment.parent_okr_id",
        back_populates="parent_okr"
    )
    alignment_parents = relationship(
        "OKRAlignment",
        foreign_keys="OKRAlignment.child_okr_id",
        back_populates="child_okr"
    )
    submissions = relationship("OKRSubmission", foreign_keys="OKRSubmission.okr_id", back_populates="okr")
    approvals = relationship("OKRApproval", foreign_keys="OKRApproval.okr_id", back_populates="okr")


class KeyResult(Base):
    """
    Key Results that measure progress toward an Objective.
    Each KR has independent measurable progress.
    """
    __tablename__ = "key_results"
    __table_args__ = (
        Index("idx_kr_okr_id", "okr_id"),
        CheckConstraint("weight >= 1 AND weight <= 5", name="valid_kr_weight"),
    )

    id = Column(String(36), primary_key=True, index=True)
    okr_id = Column(String(36), ForeignKey("okrs.id"), nullable=False)
    
    title = Column(String(300), nullable=False)
    metric_type = Column(SQLEnum(MetricType), nullable=False)
    
    # Progress tracking values
    start_value = Column(Float, nullable=False, default=0.0)
    current_value = Column(Float, nullable=False, default=0.0)
    target_value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=True)  # %, units, $, hours, etc.
    
    # Importance weighting
    weight = Column(Integer, default=3, nullable=False)  # 1-5 importance
    
    # Direction of progress
    is_lower_better = Column(Boolean, default=False)
    # True for: downtime, defects, accidents, failures, wastage
    # False for: output, throughput, completion, efficiency, sales
    
    # Progress tracking
    progress = Column(Float, default=0.0)  # 0-100 percentage
    expected_progress = Column(Float, default=0.0)  # Based on elapsed time
    trend = Column(SQLEnum(TrendStatus), default=TrendStatus.ON_TRACK)
    
    # Submission and approval tracking
    submission_status = Column(SQLEnum(SubmissionStatus), default=SubmissionStatus.DRAFT, nullable=False)
    submitted_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    
    # Status and health
    is_completed = Column(Boolean, default=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    okr = relationship("OKR", back_populates="key_results")
    progress_updates = relationship("KRProgressUpdate", back_populates="key_result", cascade="all, delete-orphan")


class KRProgressUpdate(Base):
    """
    Historical progress updates for Key Results.
    Tracks changes over time for trajectory and confidence calculations.
    """
    __tablename__ = "kr_progress_updates"
    __table_args__ = (
        Index("idx_kr_progress_date", "key_result_id", "update_date"),
    )

    id = Column(String(36), primary_key=True, index=True)
    key_result_id = Column(String(36), ForeignKey("key_results.id"), nullable=False)
    
    # Update values
    current_value = Column(Float, nullable=False)
    progress_percentage = Column(Float, nullable=False)  # 0-100
    
    # Metadata
    update_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    notes = Column(Text, nullable=True)
    updated_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    # Relationships
    key_result = relationship("KeyResult", back_populates="progress_updates")
    updated_by = relationship("User")


# ============================================================================
# ALIGNMENT MODELS
# ============================================================================

class OKRAlignment(Base):
    """
    Many-to-many alignment relationships between parent and child OKRs.
    Supports strategic, operational, dependency, and support relationships.
    """
    __tablename__ = "okr_alignments"
    __table_args__ = (
        Index("idx_alignment_parent_child", "parent_okr_id", "child_okr_id"),
        UniqueConstraint("parent_okr_id", "child_okr_id", name="unique_okr_alignment"),
    )

    id = Column(String(36), primary_key=True, index=True)
    parent_okr_id = Column(String(36), ForeignKey("okrs.id"), nullable=False)
    child_okr_id = Column(String(36), ForeignKey("okrs.id"), nullable=False)
    
    # Contribution weight (1-5) - how much child contributes to parent
    contribution_weight = Column(Integer, default=3, nullable=False)
    
    # Type of alignment
    alignment_type = Column(SQLEnum(AlignmentType), default=AlignmentType.OPERATIONAL)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    parent_okr = relationship(
        "OKR",
        foreign_keys=[parent_okr_id],
        back_populates="alignment_children"
    )
    child_okr = relationship(
        "OKR",
        foreign_keys=[child_okr_id],
        back_populates="alignment_parents"
    )


# ============================================================================
# ANALYTICS CACHE MODELS
# ============================================================================

class OKRAnalyticsSnapshot(Base):
    """
    Cached analytics snapshots for performance optimization.
    Recomputed periodically (not persistent source of truth).
    """
    __tablename__ = "okr_analytics_snapshots"
    __table_args__ = (
        Index("idx_snapshot_org_date", "org_id", "snapshot_date"),
    )

    id = Column(String(36), primary_key=True, index=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    
    # Snapshot data
    total_okrs = Column(Integer, default=0)
    total_key_results = Column(Integer, default=0)
    avg_progress = Column(Float, default=0.0)
    okrs_on_track = Column(Integer, default=0)
    okrs_at_risk = Column(Integer, default=0)
    okrs_blocked = Column(Integer, default=0)
    
    # Timeline
    snapshot_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Cache metadata
    is_stale = Column(Boolean, default=False)


# ============================================================================
# HEALTH CHECK AUDIT MODEL
# ============================================================================

class OKRHealthAudit(Base):
    """
    Audit trail of OKR health state changes.
    Used to detect stale updates and inform confidence calculations.
    """
    __tablename__ = "okr_health_audits"
    __table_args__ = (
        Index("idx_audit_okr_date", "okr_id", "audit_date"),
    )

    id = Column(String(36), primary_key=True, index=True)
    okr_id = Column(String(36), ForeignKey("okrs.id"), nullable=False)
    
    # Health state
    health_status = Column(SQLEnum(HealthStatus), nullable=False)
    risk_level = Column(SQLEnum(RiskLevel), nullable=False)
    progress = Column(Float, nullable=False)
    
    # Reason for state change
    reason = Column(Text, nullable=True)
    days_since_update = Column(Integer, nullable=True)
    
    # Audit metadata
    audit_date = Column(DateTime, default=datetime.utcnow, nullable=False)


# ============================================================================
# SUBMISSION AND APPROVAL MODELS
# ============================================================================

class OKRSubmission(Base):
    """
    Tracks OKR progress submissions in the approval workflow.
    Each submission can be approved, rejected, or require revision.
    """
    __tablename__ = "okr_submissions"
    __table_args__ = (
        Index("idx_submission_okr_date", "okr_id", "submitted_at"),
        Index("idx_submission_status", "submission_status"),
    )

    id = Column(String(36), primary_key=True, index=True)
    okr_id = Column(String(36), ForeignKey("okrs.id"), nullable=False)
    
    # Submission metadata
    submitted_by_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Submission data snapshot
    progress_snapshot = Column(JSONB, nullable=True)  # Progress values at submission time
    submission_notes = Column(Text, nullable=True)
    
    # Status
    submission_status = Column(SQLEnum(SubmissionStatus), default=SubmissionStatus.SUBMITTED, nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    okr = relationship("OKR", foreign_keys=[okr_id], back_populates="submissions")
    submitted_by = relationship("User", foreign_keys=[submitted_by_id])


class OKRApproval(Base):
    """
    Tracks OKR submission approvals and rejections.
    Maintains audit trail of all approval actions.
    """
    __tablename__ = "okr_approvals"
    __table_args__ = (
        Index("idx_approval_okr_date", "okr_id", "approval_date"),
        Index("idx_approval_status", "approval_status"),
        Index("idx_approval_approver", "approved_by_id"),
    )

    id = Column(String(36), primary_key=True, index=True)
    okr_id = Column(String(36), ForeignKey("okrs.id"), nullable=False)
    
    # Approval metadata
    approved_by_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    approval_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Approval action and details
    action = Column(SQLEnum(ApprovalAction), nullable=False)
    approval_comments = Column(Text, nullable=True)
    approval_status = Column(SQLEnum(SubmissionStatus), nullable=False)  # Status after approval
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    okr = relationship("OKR", foreign_keys=[okr_id], back_populates="approvals")
    approved_by = relationship("User", foreign_keys=[approved_by_id])
