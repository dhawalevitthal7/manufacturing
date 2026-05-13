"""
AI-Assisted OKR Routes for Manufacturing
Endpoints for AI-powered OKR creation, validation, and progress tracking.
Includes conversational chat-based OKR creation matching currentreview pattern.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
import json
from datetime import datetime

from server.database import get_db
from server.models import Objective, KeyResult, ProgressUpdate, User, Organization
from server.services.okr_ai_agent import get_okr_ai_agent
from server.services.progress_ai_agent import get_progress_ai_agent

router = APIRouter(prefix="/api/okrs/ai", tags=["okrs_ai"])


# ── Request / Response schemas (matching currentreview) ───────────────────────

class ConversationMessage(BaseModel):
    """A single message in the conversation history."""
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class GenerateOKRChatRequest(BaseModel):
    """Payload for conversational OKR creation via AI chat."""
    message: str = Field(..., min_length=1, max_length=2000)
    department_name: str = Field(..., min_length=1)
    hierarchy_level: str = Field(default="DEPARTMENT")
    conversation_history: List[ConversationMessage] = Field(default_factory=list)
    quarter: str = Field(default="Q2")
    year: int = Field(default=2026)


class CascadeOKRChatRequest(BaseModel):
    """Payload for cascading OKR personalization via AI chat."""
    message: str = Field(..., min_length=1, max_length=2000)
    department_name: str = Field(..., min_length=1)
    parent_objective_id: str = Field(..., min_length=1)
    conversation_history: List[ConversationMessage] = Field(default_factory=list)
    quarter: str = Field(default="Q2")
    year: int = Field(default=2026)


class AIKeyResult(BaseModel):
    """A single measurable key result from the AI suggestion."""
    title: str
    target: float
    unit: str
    due_date: str = ""


class AIOKRSuggestion(BaseModel):
    """Structured OKR data ready to populate the creation form."""
    objective: str
    quarter: str = ""
    year: int = 2026
    due_date: str = ""
    key_results: List[AIKeyResult] = []


class GenerateOKRChatResponse(BaseModel):
    """Response from the AI chat — always includes a reply, optionally an OKR suggestion."""
    reply: str
    has_suggestion: bool = False
    okr_suggestion: Optional[AIOKRSuggestion] = None


# ──────────────────────────────────────────────────────────────────────────────
# CONVERSATIONAL AI CHAT ENDPOINTS (matching currentreview pattern)
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/generate-okr-chat", response_model=GenerateOKRChatResponse)
def generate_okr_chat(
    request: GenerateOKRChatRequest,
    db: Session = Depends(get_db),
    org_id: str = Query(""),
    user_id: str = Query(""),
):
    """
    Conversational AI endpoint for creating OKRs through chat.
    
    Accepts a natural language message and optional conversation history.
    Uses Azure OpenAI (GPT-4o) to parse intent and produce an OKR suggestion.
    The suggestion can be applied directly to the creation form fields.
    """
    try:
        from server.services.azure_openai_service import get_azure_openai_service
        service = get_azure_openai_service()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    history = [{"role": m.role, "content": m.content} for m in request.conversation_history]

    try:
        raw = service.generate_okr_suggestion(
            department_name=request.department_name,
            hierarchy_level=request.hierarchy_level,
            message=request.message,
            conversation_history=history,
            quarter=request.quarter,
            year=request.year,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(exc)}")

    # Parse the structured suggestion if the AI decided to include one
    suggestion = None
    if raw.get("has_suggestion") and raw.get("okr_suggestion"):
        raw_okr = raw["okr_suggestion"]
        try:
            suggestion = AIOKRSuggestion(
                objective=raw_okr.get("objective", ""),
                quarter=raw_okr.get("quarter", request.quarter),
                year=raw_okr.get("year", request.year),
                due_date=raw_okr.get("due_date", ""),
                key_results=[
                    AIKeyResult(
                        title=kr.get("title", ""),
                        target=float(kr.get("target", 0)),
                        unit=kr.get("unit", ""),
                        due_date=kr.get("due_date", ""),
                    )
                    for kr in raw_okr.get("key_results", [])
                ],
            )
        except Exception:
            suggestion = None

    return GenerateOKRChatResponse(
        reply=raw.get("reply", "I understand! Let me help you build that OKR."),
        has_suggestion=bool(suggestion),
        okr_suggestion=suggestion,
    )


@router.post("/cascade-okr-chat", response_model=GenerateOKRChatResponse)
def cascade_okr_chat(
    request: CascadeOKRChatRequest,
    db: Session = Depends(get_db),
    org_id: str = Query(""),
    user_id: str = Query(""),
):
    """
    AI endpoint for employees cascading a parent OKR.
    Uses the parent OKR context to help the employee personalise
    the objective and key results to their individual role.
    """
    # Get parent OKR
    parent_okr = db.query(Objective).filter(
        Objective.id == request.parent_objective_id,
        Objective.org_id == org_id,
    ).first()
    if not parent_okr:
        raise HTTPException(status_code=404, detail="Parent OKR not found")

    parent_krs = db.query(KeyResult).filter(
        KeyResult.objective_id == request.parent_objective_id
    ).all()
    parent_kr_list = [
        {"title": kr.title, "target": kr.target_value, "unit": kr.unit}
        for kr in parent_krs
    ]

    try:
        from server.services.azure_openai_service import get_azure_openai_service
        service = get_azure_openai_service()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    history = [{"role": m.role, "content": m.content} for m in request.conversation_history]

    try:
        raw = service.cascade_okr_suggestion(
            department_name=request.department_name,
            parent_objective=parent_okr.title,
            parent_key_results=parent_kr_list,
            message=request.message,
            conversation_history=history,
            quarter=request.quarter,
            year=request.year,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(exc)}")

    suggestion = None
    if raw.get("has_suggestion") and raw.get("okr_suggestion"):
        raw_okr = raw["okr_suggestion"]
        try:
            okr_due = raw_okr.get("due_date", "")
            suggestion = AIOKRSuggestion(
                objective=raw_okr.get("objective", ""),
                quarter=raw_okr.get("quarter", request.quarter),
                year=raw_okr.get("year", request.year),
                due_date=okr_due,
                key_results=[
                    AIKeyResult(
                        title=kr.get("title", ""),
                        target=float(kr.get("target", 0)),
                        unit=kr.get("unit", ""),
                        due_date=kr.get("due_date", "") or okr_due,
                    )
                    for kr in raw_okr.get("key_results", [])
                ],
            )
        except Exception:
            suggestion = None

    return GenerateOKRChatResponse(
        reply=raw.get("reply", "Let me help you personalise this goal!"),
        has_suggestion=bool(suggestion),
        okr_suggestion=suggestion,
    )


# ──────────────────────────────────────────────────────────────────────────────
# AUTO-CREATE OKR FROM AI SUGGESTION (New: implements AI suggestions instantly)
# ──────────────────────────────────────────────────────────────────────────────

class CreateOKRFromAISuggestionRequest(BaseModel):
    """Request to auto-create OKR from AI suggestion with all key results."""
    objective_title: str = Field(..., min_length=1)
    objective_description: Optional[str] = None
    hierarchy_level: str = Field(default="INDIVIDUAL")
    quarter: str = Field(default="Q2")
    year: int = Field(default=2026)
    plant_id: Optional[str] = None
    department_id: Optional[str] = None
    team_id: Optional[str] = None
    owner_id: Optional[str] = None  # If assigning to someone else
    key_results: List[dict] = Field(default_factory=list)  # [{"title": str, "target": float, "unit": str}, ...]
    parent_objective_id: Optional[str] = None


class CreateOKRFromAISuggestionResponse(BaseModel):
    """Response when OKR is auto-created from AI suggestion."""
    status: str
    objective_id: str
    objective_title: str
    key_results_count: int
    message: str


@router.post("/auto-implement-suggestion", response_model=CreateOKRFromAISuggestionResponse)
def auto_implement_ai_okr_suggestion(
    request: CreateOKRFromAISuggestionRequest,
    db: Session = Depends(get_db),
    org_id: str = Query(""),
    user_id: str = Query(""),
):
    """
    Auto-create an OKR directly from AI suggestion with all key results.
    
    Called when user approves AI suggestion and clicks "Implement" button.
    Creates the objective and all key results in a single transaction.
    
    Args:
        objective_title: AI-suggested objective title
        objective_description: AI-suggested description (optional)
        hierarchy_level: ORGANIZATION, PLANT, DEPARTMENT, TEAM, INDIVIDUAL
        quarter: Target quarter (Q1-Q4)
        year: Target year
        plant_id: Plant scope (if applicable)
        department_id: Department scope (if applicable)
        team_id: Team scope (if applicable)
        owner_id: If assigning to someone else (optional)
        key_results: List of KRs with title, target, unit
        parent_objective_id: If cascading from parent (optional)
        
    Returns:
        Created objective ID, KR count, and success message
    """
    try:
        from server.models import User
        
        # Validate hierarchy level
        effective_level = request.hierarchy_level.upper()
        if effective_level == "EMPLOYEE":
            effective_level = "INDIVIDUAL"
        
        # Get effective owner
        effective_owner_id = request.owner_id or user_id
        owner_user = db.query(User).filter(
            User.id == effective_owner_id,
            User.org_id == org_id
        ).first()
        
        if not owner_user:
            raise HTTPException(status_code=404, detail="Owner user not found")
        
        # Auto-populate scope from owner's hierarchy if not provided
        effective_plant_id = request.plant_id or owner_user.plant_id
        effective_dept_id = request.department_id or owner_user.department_id
        effective_team_id = request.team_id or owner_user.team_id
        
        # If team_id not set, try to get from TeamMember
        if not effective_team_id and effective_level in ("TEAM", "INDIVIDUAL"):
            from server.models import TeamMember
            tm = db.query(TeamMember).filter(
                TeamMember.user_id == owner_user.id,
                TeamMember.is_active == True,
            ).first()
            if tm:
                effective_team_id = tm.team_id
        
        # Create objective
        obj = Objective(
            org_id=org_id,
            owner_id=effective_owner_id,
            assigned_by_id=user_id if request.owner_id and request.owner_id != user_id else None,
            parent_id=request.parent_objective_id,
            title=request.objective_title.strip(),
            description=request.objective_description.strip() if request.objective_description else None,
            level=effective_level,
            plant_id=effective_plant_id,
            department_id=effective_dept_id,
            team_id=effective_team_id,
            quarter=request.quarter,
            year=request.year,
            ai_generated=True,
            ai_metadata=json.dumps({
                "created_via": "ai_chat_suggestion",
                "auto_implemented": True,
                "created_at": datetime.utcnow().isoformat(),
            }),
            okr_status="ACTIVE",
        )
        db.add(obj)
        db.flush()  # Flush to get the ID
        db.commit()
        db.refresh(obj)
        
        # Create key results
        kr_count = 0
        for kr_data in request.key_results:
            if not kr_data.get("title", "").strip():
                continue
            
            kr = KeyResult(
                objective_id=obj.id,
                title=kr_data.get("title", "").strip(),
                target_value=float(kr_data.get("target", 100)),
                unit=kr_data.get("unit", "%"),
                weight=float(kr_data.get("weight", 1.0)),
                status="NOT_STARTED",
            )
            db.add(kr)
            kr_count += 1
        
        db.commit()
        
        return CreateOKRFromAISuggestionResponse(
            status="success",
            objective_id=obj.id,
            objective_title=obj.title,
            key_results_count=kr_count,
            message=f"✓ OKR '{obj.title}' created with {kr_count} key results and set to ACTIVE status.",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create OKR from AI suggestion: {str(e)}"
        )


# ──────────────────────────────────────────────────────────────────────────────
# LEGACY: OKR Creation with AI Assistance (query-param based)
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/create-with-suggestion")
def create_okr_with_ai_suggestion(
    session_id: str = Query(...),
    user_message: str = Query(...),
    department_name: str = Query(...),
    hierarchy_level: str = Query(...),
    quarter: str = Query("Q2"),
    year: int = Query(2026),
    db: Session = Depends(get_db),
    org_id: str = Query(""),
    user_id: str = Query(""),
):
    """Legacy query-param based AI OKR creation. Use /generate-okr-chat instead."""
    try:
        agent = get_okr_ai_agent()
        response = agent.suggest_okr(
            session_id=session_id,
            user_message=user_message,
            department_name=department_name,
            hierarchy_level=hierarchy_level,
            quarter=quarter,
            year=year,
        )
        return {
            "status": "success",
            "session_id": session_id,
            "reply": response.get("reply", ""),
            "has_suggestion": response.get("has_suggestion", False),
            "okr_suggestion": response.get("okr_suggestion"),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/personalize-cascaded")
def personalize_cascaded_okr(
    session_id: str = Query(...),
    user_message: str = Query(...),
    department_name: str = Query(...),
    parent_objective_id: str = Query(...),
    quarter: str = Query("Q2"),
    year: int = Query(2026),
    db: Session = Depends(get_db),
    org_id: str = Query(""),
    user_id: str = Query(""),
):
    """
    Personalize a cascaded OKR from parent goal
    
    Args:
        session_id: Unique conversation session ID
        user_message: Employee's personalization request
        department_name: Department/team name
        parent_objective_id: ID of parent OKR
        quarter: Target quarter
        year: Target year
        
    Returns:
        Personalized OKR suggestions
    """
    try:
        # Get parent OKR
        parent_okr = db.query(Objective).filter(
            Objective.id == parent_objective_id,
            Objective.org_id == org_id,
        ).first()
        
        if not parent_okr:
            raise HTTPException(status_code=404, detail="Parent OKR not found")
        
        # Get parent key results
        parent_krs = db.query(KeyResult).filter(
            KeyResult.objective_id == parent_objective_id
        ).all()
        
        parent_kr_list = [
            {
                "title": kr.title,
                "target": kr.target_value,
                "unit": kr.unit,
            }
            for kr in parent_krs
        ]
        
        agent = get_okr_ai_agent()
        
        response = agent.personalize_cascaded_okr(
            session_id=session_id,
            user_message=user_message,
            department_name=department_name,
            parent_objective=parent_okr.title,
            parent_key_results=parent_kr_list,
            quarter=quarter,
            year=year,
        )
        
        return {
            "status": "success",
            "session_id": session_id,
            "parent_okr_id": parent_objective_id,
            "reply": response.get("reply", ""),
            "has_suggestion": response.get("has_suggestion", False),
            "okr_suggestion": response.get("okr_suggestion"),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────────────────────────────────────
# OKR Validation & Alignment
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/validate-alignment")
def validate_okr_alignment(
    org_okr_id: str = Query(...),
    dept_okr_id: str = Query(...),
    db: Session = Depends(get_db),
    org_id: str = Query(""),
    user_id: str = Query(""),
):
    """
    Validate alignment between organization and department OKRs
    
    Args:
        org_okr_id: Organization OKR ID
        dept_okr_id: Department OKR ID
        
    Returns:
        Alignment report
    """
    try:
        # Get org OKR
        org_okr = db.query(Objective).filter(
            Objective.id == org_okr_id,
            Objective.org_id == org_id,
        ).first()
        
        if not org_okr:
            raise HTTPException(status_code=404, detail="Organization OKR not found")
        
        # Get dept OKR
        dept_okr = db.query(Objective).filter(
            Objective.id == dept_okr_id,
            Objective.org_id == org_id,
        ).first()
        
        if not dept_okr:
            raise HTTPException(status_code=404, detail="Department OKR not found")
        
        # Get key results
        org_krs = db.query(KeyResult).filter(KeyResult.objective_id == org_okr_id).all()
        dept_krs = db.query(KeyResult).filter(KeyResult.objective_id == dept_okr_id).all()
        
        org_kr_list = [
            {"title": kr.title, "target": kr.target_value, "unit": kr.unit}
            for kr in org_krs
        ]
        dept_kr_list = [
            {"title": kr.title, "target": kr.target_value, "unit": kr.unit}
            for kr in dept_krs
        ]
        
        agent = get_okr_ai_agent()
        
        alignment_report = agent.validate_alignment(
            org_objective=org_okr.title,
            org_key_results=org_kr_list,
            department_objective=dept_okr.title,
            department_key_results=dept_kr_list,
        )
        
        return {
            "status": "success",
            "org_okr_id": org_okr_id,
            "dept_okr_id": dept_okr_id,
            "aligned": alignment_report.get("aligned", False),
            "gaps": alignment_report.get("gaps", []),
            "recommendation": alignment_report.get("recommendation", ""),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────────────────────────────────────
# Progress Tracking with AI
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/auto-track-progress/{key_result_id}")
def auto_track_progress(
    key_result_id: str,
    db: Session = Depends(get_db),
    org_id: str = Query(""),
    user_id: str = Query(""),
):
    """
    Auto-track progress for a key result using AI
    
    Args:
        key_result_id: ID of key result to track
        
    Returns:
        Auto-tracked progress with predictions
    """
    try:
        # Get key result
        kr = db.query(KeyResult).join(
            Objective, KeyResult.objective_id == Objective.id
        ).filter(
            KeyResult.id == key_result_id,
            Objective.org_id == org_id,
        ).first()
        
        if not kr:
            raise HTTPException(status_code=404, detail="Key result not found")
        
        # Get objective
        objective = db.query(Objective).filter(Objective.id == kr.objective_id).first()
        
        # Get historical progress
        historical_progress = db.query(ProgressUpdate).filter(
            ProgressUpdate.key_result_id == key_result_id
        ).order_by(ProgressUpdate.created_at).all()
        
        history = [
            {
                "date": p.created_at.isoformat(),
                "value": p.new_value,
            }
            for p in historical_progress[-10:]  # Last 10 updates
        ]
        
        agent = get_progress_ai_agent()
        
        auto_data = agent.auto_track_progress(
            objective_title=objective.title,
            key_result_title=kr.title,
            current_value=kr.current_value,
            target_value=kr.target_value,
            unit=kr.unit,
            historical_progress=history,
        )
        
        return {
            "status": "success",
            "key_result_id": key_result_id,
            "current_value": kr.current_value,
            "target_value": kr.target_value,
            "unit": kr.unit,
            "auto_tracking": auto_data,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suggest-coaching/{progress_update_id}")
def suggest_coaching(
    progress_update_id: str,
    db: Session = Depends(get_db),
    org_id: str = Query(""),
    user_id: str = Query(""),
):
    """
    Get AI coaching suggestions for a progress update
    
    Args:
        progress_update_id: ID of progress update
        
    Returns:
        Coaching suggestions
    """
    try:
        # Get progress update
        progress = db.query(ProgressUpdate).join(
            KeyResult, ProgressUpdate.key_result_id == KeyResult.id
        ).join(
            Objective, KeyResult.objective_id == Objective.id
        ).filter(
            ProgressUpdate.id == progress_update_id,
            Objective.org_id == org_id,
        ).first()
        
        if not progress:
            raise HTTPException(status_code=404, detail="Progress update not found")
        
        # Get KR and objective
        kr = db.query(KeyResult).filter(KeyResult.id == progress.key_result_id).first()
        objective = db.query(Objective).filter(Objective.id == kr.objective_id).first()
        
        agent = get_progress_ai_agent()
        
        coaching = agent.suggest_coaching(
            objective_title=objective.title,
            progress_value=progress.new_value,
            target_value=kr.target_value,
            blockers=progress.blockers,
            notes=progress.notes,
        )
        
        return {
            "status": "success",
            "progress_update_id": progress_update_id,
            "coaching_note": coaching.get("coaching_note", ""),
            "suggested_actions": coaching.get("suggested_actions", []),
            "sentiment": coaching.get("sentiment", "NEUTRAL"),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────────────────────────────────────
# Quarter-based OKR Filtering
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/by-quarter/{quarter}/{year}")
def get_okrs_by_quarter(
    quarter: str,
    year: int,
    db: Session = Depends(get_db),
    org_id: str = Query(""),
    user_id: str = Query(""),
    level: str = Query(None),
):
    """
    Get all OKRs for a specific quarter and year
    
    Args:
        quarter: Q1, Q2, Q3, or Q4
        year: Year (2025, 2026, etc.)
        level: Filter by level (ORGANIZATION, PLANT, DEPARTMENT, TEAM, INDIVIDUAL)
        
    Returns:
        List of OKRs for the quarter
    """
    try:
        if quarter not in ["Q1", "Q2", "Q3", "Q4"]:
            raise HTTPException(status_code=400, detail="Invalid quarter. Use Q1-Q4")
        
        query = db.query(Objective).filter(
            Objective.org_id == org_id,
            Objective.quarter == quarter,
            Objective.year == year,
        )
        
        if level:
            query = query.filter(Objective.level == level)
        
        okrs = query.all()
        
        return {
            "status": "success",
            "quarter": f"{quarter}-{year}",
            "count": len(okrs),
            "okrs": [
                {
                    "id": o.id,
                    "title": o.title,
                    "level": o.level,
                    "status": o.status,
                    "progress": o.progress,
                    "ai_generated": o.ai_generated,
                }
                for o in okrs
            ],
            "timestamp": datetime.utcnow().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quarters-available")
def get_available_quarters():
    """
    Get available quarters for selection
    
    Returns:
        List of quarters and years
    """
    quarters = ["Q1", "Q2", "Q3", "Q4"]
    years = [2024, 2025, 2026, 2027]
    
    return {
        "status": "success",
        "quarters": quarters,
        "years": years,
        "current_quarter": "Q2",
        "current_year": 2026,
        "available_periods": [
            f"{q}-{y}" for y in years for q in quarters
        ],
    }


# ──────────────────────────────────────────────────────────────────────────────
# Batch Auto-Progress Tracking
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/batch-auto-track")
def batch_auto_track_progress(
    key_result_ids: list = Query(...),
    db: Session = Depends(get_db),
    org_id: str = Query(""),
    user_id: str = Query(""),
):
    """
    Auto-track multiple key results in batch
    
    Args:
        key_result_ids: List of key result IDs to track
        
    Returns:
        Batch tracking results
    """
    try:
        agent = get_progress_ai_agent()
        
        # Get all key results
        key_results = db.query(KeyResult).filter(
            KeyResult.id.in_(key_result_ids)
        ).all()
        
        if not key_results:
            raise HTTPException(status_code=404, detail="No key results found")
        
        # Prepare data for batch tracking
        krs_data = []
        for kr in key_results:
            objective = db.query(Objective).filter(Objective.id == kr.objective_id).first()
            krs_data.append({
                "id": kr.id,
                "title": kr.title,
                "objective_title": objective.title if objective else "",
                "current_value": kr.current_value,
                "target_value": kr.target_value,
                "unit": kr.unit,
            })
        
        # Batch process
        results = agent.batch_auto_track(krs_data)
        
        return {
            "status": "success",
            "total_tracked": len(results),
            "results": results,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
