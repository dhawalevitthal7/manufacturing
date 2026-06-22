"""
OKR Progress and Alignment Engine API Routes
Production-grade endpoints for OKR management
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
import uuid
from datetime import datetime

from server.okr_schemas import (
    OKRCreateRequest, OKRUpdateRequest, OKRDetailResponse, OKRSummaryResponse,
    KeyResultCreateRequest, KeyResultProgressUpdate,
    OKRAlignmentCreateRequest, OKRAlignmentResponse,
    CEODashboardResponse, DashboardOKRMetrics
)
from server.okr_models import (
    OKR, KeyResult, OKRAlignment,
    OKRStatus, OKRLevelType
)
from server.services.okr_dependency_injection import (
    get_okr_container, OKRServiceContainer
)
from server.database import SessionLocal

router = APIRouter(prefix="/api/v1/okrs", tags=["OKRs"])


# ============================================================================
# OKR ENDPOINTS
# ============================================================================

@router.post("/", response_model=OKRDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_okr(
    request: OKRCreateRequest,
    owner_id: str,
    container: OKRServiceContainer = Depends(get_okr_container)
):
    """
    Create a new OKR with Key Results.
    
    Args:
        request: OKRCreateRequest with objective, description, KRs, etc.
        owner_id: User ID of OKR owner
    
    Returns:
        Created OKRDetailResponse
    """
    db = SessionLocal()
    try:
        # Generate IDs
        okr_id = str(uuid.uuid4())
        
        # Create OKR
        okr = OKR(
            id=okr_id,
            objective=request.objective,
            description=request.description,
            owner_id=owner_id,
            level_type=request.level_type,
            weight=request.weight,
            quarter=request.quarter,
            year=request.year,
            start_date=request.start_date,
            end_date=request.end_date,
            status=OKRStatus.ACTIVE,
            org_id="default_org_id"  # Should come from context
        )
        
        db.add(okr)
        db.flush()
        
        # Create Key Results
        for kr_req in request.key_results:
            kr = KeyResult(
                id=str(uuid.uuid4()),
                okr_id=okr_id,
                title=kr_req.title,
                metric_type=kr_req.metric_type,
                start_value=kr_req.start_value,
                target_value=kr_req.target_value,
                unit=kr_req.unit,
                weight=kr_req.weight,
                is_lower_better=kr_req.is_lower_better
            )
            db.add(kr)
        
        db.commit()
        db.refresh(okr)
        
        # Calculate and return detailed response
        score = container.get_scoring_service().calculate_okr_comprehensive_score(okr_id)
        health = container.get_health_service().calculate_okr_health(okr_id)
        
        return OKRDetailResponse(
            id=okr.id,
            objective=okr.objective,
            description=okr.description,
            owner_id=okr.owner_id,
            level_type=okr.level_type.value,
            weight=okr.weight,
            quarter=okr.quarter,
            year=okr.year,
            status=okr.status.value,
            progress=score["final_score"] if score else 0.0,
            trend_status=health["trajectory_score"] if health else 0.0,
            health_status=health["health_status"] if health else "HEALTHY",
            risk_level=health["risk_level"] if health else "LOW",
            confidence_score=health["confidence_score"] if health else 0.0,
            key_results=[],
            start_date=okr.start_date,
            end_date=okr.end_date,
            created_at=okr.created_at,
            updated_at=okr.updated_at,
            last_progress_update=okr.last_progress_update
        )
    finally:
        db.close()


@router.get("/{okr_id}", response_model=OKRDetailResponse)
async def get_okr(
    okr_id: str,
    container: OKRServiceContainer = Depends(get_okr_container)
):
    """Get detailed OKR information with scores and health"""
    
    repo = container.get_okr_repo()
    okr = repo.get_okr_with_krs(okr_id)
    
    if not okr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OKR not found"
        )
    
    scoring = container.get_scoring_service()
    health = container.get_health_service()
    
    score = scoring.calculate_okr_comprehensive_score(okr_id)
    health_data = health.calculate_okr_health(okr_id)
    
    return OKRDetailResponse(
        id=okr.id,
        objective=okr.objective,
        description=okr.description,
        owner_id=okr.owner_id,
        level_type=okr.level_type.value,
        weight=okr.weight,
        quarter=okr.quarter,
        year=okr.year,
        status=okr.status.value,
        progress=score["final_score"] if score else 0.0,
        trend_status=health_data["trajectory_score"] if health_data else 0.0,
        health_status=health_data["health_status"] if health_data else "HEALTHY",
        risk_level=health_data["risk_level"] if health_data else "LOW",
        confidence_score=health_data["confidence_score"] if health_data else 0.0,
        key_results=[],
        start_date=okr.start_date,
        end_date=okr.end_date,
        created_at=okr.created_at,
        updated_at=okr.updated_at,
        last_progress_update=okr.last_progress_update
    )


@router.put("/{okr_id}", response_model=OKRDetailResponse)
async def update_okr(
    okr_id: str,
    request: OKRUpdateRequest,
    container: OKRServiceContainer = Depends(get_okr_container)
):
    """Update OKR fields"""
    
    repo = container.get_okr_repo()
    okr = repo.update_okr(okr_id, **request.dict(exclude_unset=True))
    
    if not okr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OKR not found"
        )
    
    # Return updated OKR detail
    return await get_okr(okr_id, container)


# ============================================================================
# KEY RESULT ENDPOINTS
# ============================================================================

@router.post("/{okr_id}/key-results", status_code=status.HTTP_201_CREATED)
async def add_key_result(
    okr_id: str,
    request: KeyResultCreateRequest,
    container: OKRServiceContainer = Depends(get_okr_container)
):
    """Add a Key Result to an OKR"""
    
    db = SessionLocal()
    try:
        repo = container.get_okr_repo()
        okr = repo.get_okr_by_id(okr_id)
        
        if not okr:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="OKR not found"
            )
        
        kr = KeyResult(
            id=str(uuid.uuid4()),
            okr_id=okr_id,
            title=request.title,
            metric_type=request.metric_type,
            start_value=request.start_value,
            target_value=request.target_value,
            unit=request.unit,
            weight=request.weight,
            is_lower_better=request.is_lower_better
        )
        
        db.add(kr)
        db.commit()
        
        return {"id": kr.id, "okr_id": okr_id, "title": kr.title}
    finally:
        db.close()


@router.post("/{okr_id}/key-results/{kr_id}/progress")
async def update_kr_progress(
    okr_id: str,
    kr_id: str,
    request: KeyResultProgressUpdate,
    container: OKRServiceContainer = Depends(get_okr_container)
):
    """Update progress for a Key Result"""
    
    db = SessionLocal()
    try:
        kr_repo = container.get_kr_repo()
        kr = kr_repo.get_kr_by_id(kr_id)
        
        if not kr or kr.okr_id != okr_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Key Result not found"
            )
        
        # Update current value
        kr_repo.update_kr(kr_id, current_value=request.current_value, last_updated_at=datetime.utcnow())
        
        # Calculate progress
        scoring = container.get_scoring_service()
        progress = scoring.calculate_kr_progress(kr)
        
        # Add history
        kr_repo.add_progress_update(
            kr_id=kr_id,
            current_value=request.current_value,
            progress_percentage=progress,
            notes=request.notes
        )
        
        # Update OKR last update time
        container.get_okr_repo().update_okr(okr_id, last_progress_update=datetime.utcnow())
        
        return {
            "kr_id": kr_id,
            "progress": progress,
            "current_value": request.current_value,
            "target_value": kr.target_value,
            "updated_at": datetime.utcnow()
        }
    finally:
        db.close()


# ============================================================================
# ALIGNMENT ENDPOINTS
# ============================================================================

@router.post("/alignments", response_model=OKRAlignmentResponse, status_code=status.HTTP_201_CREATED)
async def create_alignment(
    request: OKRAlignmentCreateRequest,
    container: OKRServiceContainer = Depends(get_okr_container)
):
    """Create an OKR alignment relationship"""
    
    try:
        alignment_service = container.get_alignment_service()
        alignment = alignment_service.create_alignment(
            parent_okr_id=request.parent_okr_id,
            child_okr_id=request.child_okr_id,
            contribution_weight=request.contribution_weight,
            alignment_type=request.alignment_type
        )
        
        return OKRAlignmentResponse(
            id=alignment.id,
            parent_okr_id=alignment.parent_okr_id,
            child_okr_id=alignment.child_okr_id,
            contribution_weight=alignment.contribution_weight,
            alignment_type=alignment.alignment_type.value,
            parent_okr=OKRSummaryResponse(
                id="",
                objective="",
                owner_id="",
                level_type="organization",
                progress=0.0,
                trend_status="on_track",
                health_status="healthy",
                status="active",
                quarter=1,
                year=2026
            ),
            child_okr=OKRSummaryResponse(
                id="",
                objective="",
                owner_id="",
                level_type="organization",
                progress=0.0,
                trend_status="on_track",
                health_status="healthy",
                status="active",
                quarter=1,
                year=2026
            ),
            created_at=alignment.created_at
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ============================================================================
# DASHBOARD ENDPOINTS
# ============================================================================

@router.get("/dashboards/ceo")
async def get_ceo_dashboard(
    org_id: str,
    container: OKRServiceContainer = Depends(get_okr_container)
):
    """Get CEO-level dashboard"""
    
    analytics = container.get_analytics_service()
    dashboard = analytics.get_ceo_dashboard(org_id)
    return dashboard


@router.get("/dashboards/organization-metrics")
async def get_organization_metrics(
    org_id: str,
    container: OKRServiceContainer = Depends(get_okr_container)
):
    """Get organization-wide metrics"""
    
    analytics = container.get_analytics_service()
    metrics = analytics.get_organization_metrics(org_id)
    return metrics


@router.get("/dashboards/health-summary")
async def get_health_summary(
    org_id: str,
    container: OKRServiceContainer = Depends(get_okr_container)
):
    """Get health summary for organization"""
    
    health_service = container.get_health_service()
    summary = health_service.get_health_summary(org_id)
    return summary


# ============================================================================
# QUERY ENDPOINTS
# ============================================================================

@router.get("/by-owner/{owner_id}")
async def get_okrs_by_owner(
    owner_id: str,
    level_type: Optional[str] = None,
    status: Optional[str] = None,
    container: OKRServiceContainer = Depends(get_okr_container)
):
    """Get all OKRs for an owner"""
    
    repo = container.get_okr_repo()
    level = OKRLevelType(level_type) if level_type else None
    okr_status = OKRStatus(status) if status else None
    
    okrs = repo.get_okrs_by_owner(owner_id, level, okr_status)
    
    return [
        OKRSummaryResponse(
            id=okr.id,
            objective=okr.objective,
            owner_id=okr.owner_id,
            level_type=okr.level_type.value,
            progress=0.0,
            trend_status="on_track",
            health_status="healthy",
            status=okr.status.value,
            quarter=okr.quarter,
            year=okr.year
        )
        for okr in okrs
    ]


@router.get("/at-risk")
async def get_at_risk_okrs(
    org_id: str,
    container: OKRServiceContainer = Depends(get_okr_container)
):
    """Get at-risk OKRs"""
    
    trajectory_service = container.get_trajectory_service()
    at_risk = trajectory_service.get_at_risk_okrs(org_id)
    return at_risk


# ============================================================================
# ANALYTICS ENDPOINTS
# ============================================================================

@router.get("/analytics/comparison")
async def compare_okrs(
    okr_ids: List[str],
    container: OKRServiceContainer = Depends(get_okr_container)
):
    """Compare multiple OKRs side-by-side"""
    
    analytics = container.get_analytics_service()
    comparison = analytics.get_okr_comparison(okr_ids)
    return comparison


@router.get("/analytics/executive-summary")
async def get_executive_summary(
    org_id: str,
    container: OKRServiceContainer = Depends(get_okr_container)
):
    """Get executive summary"""
    
    analytics = container.get_analytics_service()
    summary = analytics.get_executive_summary(org_id)
    return summary
