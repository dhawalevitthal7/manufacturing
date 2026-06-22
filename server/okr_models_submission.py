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
