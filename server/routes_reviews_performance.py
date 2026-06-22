"""
Enhanced performance review API — continuous check-ins, employee reviews,
scoring, competencies, 360 feedback, and dashboards.

Extends legacy routes_reviews.py without replacing it.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from server.database import get_db
from server.models import User, ReportingRelationship, Objective
from server.services.manager_resolution import (
    get_manager_id,
    resolve_manager_for_employee,
    resolve_immediate_manager_for_checkin,
    resolve_line_manager_for_review,
    get_subordinate_employee_ids,
    can_coach_employee,
)
from server.performance_review_models import (
    PerformanceReviewCycle,
    ContinuousCheckin,
    EmployeePerformanceReview,
    ReviewSection,
    ReviewAuditLog,
    ReviewCalculation,
    ScoringConfiguration,
    FeedbackTemplate,
    FeedbackResponse,
    FeedbackSynthesis,
    CompetencyFramework,
    Competency,
    CompetencyAssessment,
    ReviewState,
    ReviewRating,
    SectionType,
)
from server.performance_review_schemas import (
    ManagerCheckinResponse,
    SelfReviewSubmit,
    ManagerReviewSubmit,
    SkipLevelReviewSubmit,
    ReviewCycleCreate,
)
from server.services.review_cycle_service import ReviewCycleService, ContinuousCheckinService
from server.services.employee_review_service import EmployeeReviewService, _state_str
from server.services.review_scoring_service import ReviewScoringService
from server.services.performance_review_agent_service import PerformanceReviewAgentService
from server.services.performance_review_team_service import PerformanceReviewTeamService
from server.services.okr_review_integration import (
    build_okr_progress_snapshot,
    attach_okr_context_to_review,
)
from server.roles import SystemRole, normalize_role

router = APIRouter(prefix="/api/reviews", tags=["reviews-performance"])

HR_ROLES = {
    SystemRole.SUPER_ADMIN.value,
    SystemRole.HR_HEAD.value,
    SystemRole.CEO.value,
}
LEADER_ROLES = HR_ROLES | {
    SystemRole.VP_OPERATIONS.value,
    SystemRole.REGIONAL_HEAD.value,
    SystemRole.PLANT_HEAD.value,
    SystemRole.DEPT_HEAD.value,
    SystemRole.MANAGER.value,
    SystemRole.TEAM_LEAD.value,
    SystemRole.SUPERVISOR.value,
}


def _get_skip_manager_id(db: Session, employee_id: str) -> Optional[str]:
    rel = (
        db.query(ReportingRelationship)
        .filter(
            ReportingRelationship.employee_id == employee_id,
            ReportingRelationship.relationship_type == "REVIEWER",
            ReportingRelationship.is_active == True,
        )
        .first()
    )
    return rel.manager_id if rel else None


def _user_name(db: Session, user_id: Optional[str]) -> Optional[str]:
    if not user_id:
        return None
    u = db.query(User).filter(User.id == user_id).first()
    return u.name if u else None


def _calculation_payload(
    *,
    review_id: str,
    components: Dict[str, Optional[float]],
    final_score: float,
    rating: Any,
    confidence_score: float,
    calc_id: Optional[str] = None,
    bias_flags: Optional[List[str]] = None,
    override_applied: Optional[bool] = None,
    override_reason: Optional[str] = None,
    calculation_timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Expose component scores with frontend-aligned availability flags."""
    _KEY_TO_API = {
        "okr_achievement": "okr_achievement_score",
        "kr_quality": "kr_quality_score",
        "manager_feedback": "manager_feedback_score",
        "behavioral_competency": "behavioral_competency_score",
        "peer_feedback": "peer_feedback_score",
        "continuous_checkin": "continuous_checkin_score",
    }
    component_available = {
        _KEY_TO_API[key]: value is not None for key, value in components.items()
    }
    return {
        "id": calc_id,
        "performance_review_id": review_id,
        "okr_achievement_score": components.get("okr_achievement"),
        "kr_quality_score": components.get("kr_quality"),
        "manager_feedback_score": components.get("manager_feedback"),
        "behavioral_competency_score": components.get("behavioral_competency"),
        "peer_feedback_score": components.get("peer_feedback"),
        "continuous_checkin_score": components.get("continuous_checkin"),
        "calculated_final_score": final_score,
        "final_rating": rating,
        "confidence_score": confidence_score,
        "component_available": component_available,
        "bias_flags": bias_flags or [],
        "override_applied": override_applied,
        "override_reason": override_reason,
        "calculation_timestamp": calculation_timestamp,
    }


def _checkin_dict(c: ContinuousCheckin, db: Session) -> Dict[str, Any]:
    return {
        "id": c.id,
        "employee_id": c.employee_id,
        "employee_name": _user_name(db, c.employee_id),
        "manager_id": c.manager_id,
        "manager_name": _user_name(db, c.manager_id),
        "checkin_week": c.checkin_week,
        "checkin_month": c.checkin_month,
        "achievements": c.achievements or "",
        "key_wins": c.key_wins or [],
        "blockers": c.blockers or "",
        "risks": c.risks or [],
        "support_needed": c.support_needed,
        "confidence_score": c.confidence_score,
        "engagement_score": c.engagement_score,
        "employee_mood": c.employee_mood.value if hasattr(c.employee_mood, "value") else c.employee_mood,
        "okr_progress_snapshot": c.okr_progress_snapshot,
        "progress_notes": c.progress_notes,
        "manager_feedback": c.manager_feedback,
        "manager_response_quality": c.manager_response_quality,
        "action_items": c.action_items or [],
        "corrective_actions": c.corrective_actions or [],
        "coaching_notes": c.coaching_notes,
        "status": c.status,
        "is_latest": c.is_latest,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        "manager_responded_at": c.manager_responded_at.isoformat() if c.manager_responded_at else None,
    }


def _review_dict(r: EmployeePerformanceReview, db: Session) -> Dict[str, Any]:
    cycle = db.query(PerformanceReviewCycle).filter(PerformanceReviewCycle.id == r.review_cycle_id).first()
    rating = r.final_rating.value if hasattr(r.final_rating, "value") else r.final_rating
    return {
        "id": r.id,
        "employee_id": r.employee_id,
        "employee_name": _user_name(db, r.employee_id),
        "manager_id": r.manager_id,
        "manager_name": _user_name(db, r.manager_id),
        "skip_level_manager_id": r.skip_level_manager_id,
        "dept_head_reviewer_id": r.dept_head_reviewer_id,
        "requires_dept_moderation": r.requires_dept_moderation,
        "hr_reviewer_id": r.hr_reviewer_id,
        "review_cycle_id": r.review_cycle_id,
        "cycle_name": cycle.name if cycle else None,
        "current_state": _state_str(r.current_state),
        "final_rating": rating,
        "final_score": r.final_score,
        "rating_locked": r.rating_locked,
        "okr_achievement_score": r.okr_achievement_score,
        "okr_ids": r.okr_ids or [],
        "promotion_eligible": r.promotion_eligible,
        "attrition_risk": r.attrition_risk,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        "finalized_at": r.finalized_at.isoformat() if r.finalized_at else None,
        "published_at": r.published_at.isoformat() if r.published_at else None,
        "ai_review_status": getattr(r, "ai_review_status", None) or "NONE",
        "promotion_recommendation": getattr(r, "promotion_recommendation", None),
        "promotion_rationale": getattr(r, "promotion_rationale", None),
        "employee_performance_narrative": getattr(r, "employee_performance_narrative", None),
        "shared_with_employee_at": (
            r.shared_with_employee_at.isoformat()
            if getattr(r, "shared_with_employee_at", None)
            else None
        ),
        "submitted_to_dept_head_at": (
            r.submitted_to_dept_head_at.isoformat()
            if getattr(r, "submitted_to_dept_head_at", None)
            else None
        ),
        "dept_head_name": _user_name(db, r.dept_head_reviewer_id),
    }


def _can_view_review(db: Session, review: EmployeePerformanceReview, user_id: str, role: str) -> bool:
    role = normalize_role(role) or role
    if role in HR_ROLES:
        return True
    if review.employee_id == user_id or review.manager_id == user_id:
        return True
    if review.dept_head_reviewer_id == user_id:
        return True
    if review.skip_level_manager_id == user_id:
        return True
    if role in LEADER_ROLES:
        return True
    return False


def _ensure_scoring_config(db: Session, org_id: str) -> None:
    existing = db.query(ScoringConfiguration).filter(
        ScoringConfiguration.org_id == org_id,
        ScoringConfiguration.role_type == None,
    ).first()
    if not existing:
        db.add(ScoringConfiguration(org_id=org_id))
        db.commit()


def _seed_competency_frameworks(db: Session, org_id: str) -> None:
    if db.query(CompetencyFramework).filter(CompetencyFramework.org_id == org_id).first():
        return
    defaults = [
        ("MANAGER", "Manufacturing Manager", [
            ("Leadership", "Leads team through operational change", 1.2),
            ("Ownership", "Owns outcomes across shifts", 1.0),
            ("Execution", "Delivers production targets reliably", 1.1),
            ("Mentoring", "Develops supervisors and operators", 0.9),
        ]),
        ("SUPERVISOR", "Shift Supervisor", [
            ("Operational Excellence", "Meets shift KPIs", 1.2),
            ("Team Management", "Coordinates crew effectively", 1.0),
            ("Safety", "Zero tolerance for safety gaps", 1.3),
        ]),
        ("EMPLOYEE", "Operations Individual Contributor", [
            ("Technical Quality", "Work meets specification", 1.0),
            ("Reliability", "Consistent attendance and output", 1.0),
            ("Collaboration", "Supports cross-functional handoffs", 0.9),
            ("Delivery", "Completes assigned work on time", 1.1),
        ]),
    ]
    for role_type, name, comps in defaults:
        fw = CompetencyFramework(org_id=org_id, role_type=role_type, name=name)
        db.add(fw)
        db.flush()
        for i, (cname, desc, weight) in enumerate(comps):
            db.add(
                Competency(
                    framework_id=fw.id,
                    name=cname,
                    description=desc,
                    weight=weight,
                    proficiency_levels=[
                        {"level": 1, "name": "Developing", "description": "Needs guidance"},
                        {"level": 3, "name": "Proficient", "description": "Meets expectations"},
                        {"level": 5, "name": "Exemplary", "description": "Role model"},
                    ],
                    display_order=i,
                )
            )
    db.commit()


# ---------------------------------------------------------------------------
# Performance review cycles (enhanced)
# ---------------------------------------------------------------------------

@router.get("/performance-cycles")
def list_performance_cycles(db: Session = Depends(get_db), org_id: str = ""):
    cycles = (
        db.query(PerformanceReviewCycle)
        .filter(PerformanceReviewCycle.org_id == org_id)
        .order_by(PerformanceReviewCycle.created_at.desc())
        .all()
    )
    return [
        {
            "id": c.id,
            "org_id": c.org_id,
            "cycle_type": c.cycle_type.value if hasattr(c.cycle_type, "value") else c.cycle_type,
            "name": c.name,
            "status": c.status.value if hasattr(c.status, "value") else c.status,
            "start_date": c.start_date.isoformat() if c.start_date else None,
            "end_date": c.end_date.isoformat() if c.end_date else None,
        }
        for c in cycles
    ]


@router.post("/performance-cycles")
def create_performance_cycle(
    req: ReviewCycleCreate,
    db: Session = Depends(get_db),
    org_id: str = "",
    user_id: str = "",
):
    role = normalize_role("")  # role injected via query in middleware — read from req body not available
    svc = ReviewCycleService(db)
    cycle = svc.create_review_cycle(
        org_id=org_id,
        cycle_type=req.cycle_type,
        name=req.name,
        start_date=req.start_date,
        end_date=req.end_date,
        submission_start=req.submission_start,
        submission_end=req.submission_end,
        description=req.description,
        eligible_plant_ids=req.eligible_plant_ids,
        eligible_dept_ids=req.eligible_dept_ids,
        auto_lock_date=req.auto_lock_date,
        auto_publish_date=req.auto_publish_date,
    )
    from server.performance_review_models import ReviewCycleStatus

    cycle.status = ReviewCycleStatus.ACTIVE
    cycle.created_by_user_id = user_id
    db.commit()
    db.refresh(cycle)
    return {"id": cycle.id, "name": cycle.name, "status": _state_str(cycle.status) if hasattr(cycle, "status") else cycle.status}


class InitiateBulkBody(BaseModel):
    cycle_id: str


class InitiateEmployeeReviewBody(BaseModel):
    employee_id: str
    cycle_id: str


@router.get("/performance/reviewable-team")
def list_reviewable_team(
    cycle_id: str,
    db: Session = Depends(get_db),
    org_id: str = "",
    user_id: str = "",
    role: str = "",
):
    norm = normalize_role(role)
    if norm not in LEADER_ROLES | HR_ROLES:
        raise HTTPException(403, "Only leaders can view team review queue")
    if not cycle_id:
        raise HTTPException(400, "cycle_id is required")
    return PerformanceReviewTeamService(db).list_reviewable_team(user_id, org_id, cycle_id)


@router.post("/performance/initiate-for-employee")
def initiate_employee_review(
    body: InitiateEmployeeReviewBody,
    db: Session = Depends(get_db),
    org_id: str = "",
    user_id: str = "",
    role: str = "",
):
    norm = normalize_role(role)
    if norm not in LEADER_ROLES | HR_ROLES:
        raise HTTPException(403, "Only leaders can initiate employee reviews")
    try:
        review = PerformanceReviewTeamService(db).initiate_review(
            user_id, org_id, body.employee_id, body.cycle_id
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _review_dict(review, db)


@router.post("/performance/initiate-bulk")
def initiate_bulk_performance_reviews(
    body: InitiateBulkBody,
    db: Session = Depends(get_db),
    org_id: str = "",
):
    cycle = db.query(PerformanceReviewCycle).filter(PerformanceReviewCycle.id == body.cycle_id).first()
    if not cycle:
        raise HTTPException(404, "Performance review cycle not found")

    review_svc = EmployeeReviewService(db)
    employees = db.query(User).filter(User.org_id == org_id, User.is_active == True).all()
    created = 0
    for emp in employees:
        manager_id, _ = resolve_line_manager_for_review(db, emp.id, org_id)
        if not manager_id:
            continue
        try:
            review_svc.create_performance_review(
                org_id=org_id,
                employee_id=emp.id,
                manager_id=manager_id,
                review_cycle_id=body.cycle_id,
                review_period_start=cycle.start_date,
                review_period_end=cycle.end_date,
                requires_dept_moderation=None,
            )
            rev = (
                db.query(EmployeePerformanceReview)
                .filter(
                    EmployeePerformanceReview.employee_id == emp.id,
                    EmployeePerformanceReview.review_cycle_id == body.cycle_id,
                )
                .first()
            )
            if rev:
                attach_okr_context_to_review(db, rev)
            created += 1
        except ValueError:
            continue
    return {"created": created, "cycle_id": body.cycle_id}


# ---------------------------------------------------------------------------
# Continuous check-ins
# ---------------------------------------------------------------------------

class CheckinCreateBody(BaseModel):
    employee_id: Optional[str] = None
    checkin_week: int
    checkin_month: Optional[int] = None
    checkin_date: Optional[datetime] = None
    achievements: str
    key_wins: List[str] = []
    blockers: str
    risks: List[Dict[str, Any]] = []
    support_needed: Optional[str] = None
    confidence_score: Optional[float] = None
    engagement_score: Optional[int] = None
    employee_mood: Optional[str] = "NEUTRAL"
    okr_progress_snapshot: Optional[Dict[str, Any]] = None
    progress_notes: Optional[str] = None


# POST /checkins → routes_checkins_coaching.py (coaching workflow, not approval)

@router.get("/checkins/{checkin_id}")
def get_checkin(checkin_id: str, db: Session = Depends(get_db), user_id: str = "", role: str = ""):
    c = db.query(ContinuousCheckin).filter(ContinuousCheckin.id == checkin_id).first()
    if not c:
        raise HTTPException(404)
    if c.employee_id != user_id and c.manager_id != user_id and normalize_role(role) not in LEADER_ROLES | HR_ROLES:
        raise HTTPException(403)
    return _checkin_dict(c, db)


@router.get("/checkins/employee/{employee_id}")
def list_employee_checkins(
    employee_id: str,
    db: Session = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
    user_id: str = "",
    role: str = "",
):
    if employee_id != user_id and normalize_role(role) not in LEADER_ROLES | HR_ROLES:
        raise HTTPException(403)
    svc = ContinuousCheckinService(db)
    checkins, _ = svc.get_employee_checkins(employee_id, limit=limit, offset=offset)
    return [_checkin_dict(c, db) for c in checkins]


@router.post("/checkins/{checkin_id}/manager-response")
def manager_checkin_response(
    checkin_id: str,
    body: ManagerCheckinResponse,
    db: Session = Depends(get_db),
    user_id: str = "",
):
    c = db.query(ContinuousCheckin).filter(ContinuousCheckin.id == checkin_id).first()
    if not c:
        raise HTTPException(404)
    if c.manager_id != user_id:
        raise HTTPException(403, "Only assigned manager can respond")
    svc = ContinuousCheckinService(db)
    updated = svc.provide_manager_response(
        checkin_id=checkin_id,
        manager_feedback=body.manager_feedback,
        manager_response_quality=body.manager_response_quality or 4,
        action_items=body.action_items,
        corrective_actions=body.corrective_actions,
        coaching_notes=body.coaching_notes,
    )
    return _checkin_dict(updated, db)


@router.get("/checkins/manager/{manager_id}")
def list_team_checkins(
    manager_id: str,
    db: Session = Depends(get_db),
    week: Optional[int] = None,
    user_id: str = "",
    role: str = "",
):
    if manager_id != user_id and normalize_role(role) not in HR_ROLES:
        raise HTTPException(403)
    q = db.query(ContinuousCheckin).filter(
        ContinuousCheckin.manager_id == manager_id,
        ContinuousCheckin.is_latest == True,
    )
    if week:
        q = q.filter(ContinuousCheckin.checkin_week == week)
    checkins = q.order_by(ContinuousCheckin.checkin_date.desc()).limit(50).all()
    return [_checkin_dict(c, db) for c in checkins]


# ---------------------------------------------------------------------------
# Employee performance reviews
# ---------------------------------------------------------------------------

class PerformanceReviewCreateBody(BaseModel):
    employee_id: str
    cycle_id: str


@router.post("/performance")
def create_performance_review(
    body: PerformanceReviewCreateBody,
    db: Session = Depends(get_db),
    org_id: str = "",
    user_id: str = "",
    role: str = "",
):
    if normalize_role(role) not in LEADER_ROLES | HR_ROLES and body.employee_id != user_id:
        raise HTTPException(403)

    cycle = db.query(PerformanceReviewCycle).filter(PerformanceReviewCycle.id == body.cycle_id).first()
    if not cycle:
        raise HTTPException(404, "Review cycle not found")

    manager_id, _ = resolve_line_manager_for_review(db, body.employee_id, org_id)
    if not manager_id:
        raise HTTPException(400, "Employee has no resolvable immediate manager")

    svc = EmployeeReviewService(db)
    try:
        review = svc.create_performance_review(
            org_id=org_id,
            employee_id=body.employee_id,
            manager_id=manager_id,
            review_cycle_id=body.cycle_id,
            review_period_start=cycle.start_date,
            review_period_end=cycle.end_date,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    attach_okr_context_to_review(db, review)
    return _review_dict(review, db)


@router.get("/performance")
def list_performance_reviews(
    db: Session = Depends(get_db),
    org_id: str = "",
    user_id: str = "",
    role: str = "",
    cycle_id: str = "",
    status: str = "",
    employee_id: str = "",
):
    q = db.query(EmployeePerformanceReview).filter(EmployeePerformanceReview.org_id == org_id)
    if cycle_id:
        q = q.filter(EmployeePerformanceReview.review_cycle_id == cycle_id)
    if status:
        q = q.filter(EmployeePerformanceReview.current_state == status)
    if employee_id:
        q = q.filter(EmployeePerformanceReview.employee_id == employee_id)

    norm = normalize_role(role)
    if norm in (SystemRole.EMPLOYEE.value, SystemRole.SUPERVISOR.value):
        q = q.filter(
            (EmployeePerformanceReview.employee_id == user_id)
            | (EmployeePerformanceReview.manager_id == user_id)
        )
    elif norm == SystemRole.DEPT_HEAD.value:
        # Dept head moderates quarterly reviews assigned via dept_head_reviewer_id
        q = q.filter(
            (EmployeePerformanceReview.dept_head_reviewer_id == user_id)
            | (EmployeePerformanceReview.manager_id == user_id)
            | (EmployeePerformanceReview.employee_id == user_id)
        )
    elif norm not in HR_ROLES and norm in LEADER_ROLES:
        subordinate_ids = get_subordinate_employee_ids(db, user_id)
        from sqlalchemy import or_

        leader_filters = [
            EmployeePerformanceReview.manager_id == user_id,
            EmployeePerformanceReview.skip_level_manager_id == user_id,
            EmployeePerformanceReview.employee_id == user_id,
        ]
        if subordinate_ids:
            leader_filters.append(EmployeePerformanceReview.employee_id.in_(subordinate_ids))
        q = q.filter(or_(*leader_filters))

    reviews = q.order_by(EmployeePerformanceReview.created_at.desc()).all()
    return [_review_dict(r, db) for r in reviews]


@router.get("/performance/{review_id}")
def get_performance_review(
    review_id: str,
    db: Session = Depends(get_db),
    user_id: str = "",
    role: str = "",
):
    r = db.query(EmployeePerformanceReview).filter(EmployeePerformanceReview.id == review_id).first()
    if not r:
        raise HTTPException(404)
    if not _can_view_review(db, r, user_id, role):
        raise HTTPException(403)
    result = _review_dict(r, db)
    objs = db.query(Objective).filter(Objective.owner_id == r.employee_id, Objective.org_id == r.org_id).all()
    result["okr_context"] = [
        {"id": o.id, "title": o.title, "progress": o.progress, "level": o.level}
        for o in objs
    ]
    return result


@router.post("/performance/{review_id}/self-review")
def post_self_review(
    review_id: str,
    body: SelfReviewSubmit,
    db: Session = Depends(get_db),
    user_id: str = "",
):
    svc = EmployeeReviewService(db)
    try:
        review = svc.submit_self_review(
            review_id=review_id,
            user_id=user_id,
            achievements=body.achievements,
            okr_self_assessment=body.okr_self_assessment,
            strengths=body.strengths,
            challenges=body.challenges,
            growth_areas=body.growth_areas,
            evidence=body.evidence,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    attach_okr_context_to_review(db, review)
    return _review_dict(review, db)


class AIReviewEditBody(BaseModel):
    executive_summary: Optional[str] = None
    okr_performance_analysis: Optional[str] = None
    self_review_synthesis: Optional[str] = None
    checkin_insights: Optional[str] = None
    strengths: Optional[List[str]] = None
    development_areas: Optional[List[str]] = None
    promotion_recommendation: Optional[str] = None
    promotion_rationale: Optional[str] = None
    recommended_rating: Optional[str] = None
    behavioral_competency_scores: Optional[Dict[str, int]] = None
    coaching_actions: Optional[List[str]] = None
    risk_flags: Optional[List[str]] = None


class ManagerAIReviewSubmitBody(BaseModel):
    behavioral_competency_scores: Dict[str, int] = {}
    manager_notes: Optional[str] = None
    promotion_eligible: bool = False
    attrition_risk: Optional[str] = None


@router.get("/performance/{review_id}/ai-review/context")
def get_ai_review_context(
    review_id: str,
    db: Session = Depends(get_db),
    user_id: str = "",
    role: str = "",
):
    review = db.query(EmployeePerformanceReview).filter(EmployeePerformanceReview.id == review_id).first()
    if not review:
        raise HTTPException(404)
    if not _can_view_review(db, review, user_id, role):
        raise HTTPException(403)
    try:
        return PerformanceReviewAgentService(db).gather_context(review_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/performance/{review_id}/ai-review")
def get_ai_review(
    review_id: str,
    db: Session = Depends(get_db),
    user_id: str = "",
    role: str = "",
):
    review = db.query(EmployeePerformanceReview).filter(EmployeePerformanceReview.id == review_id).first()
    if not review:
        raise HTTPException(404)
    if not _can_view_review(db, review, user_id, role):
        raise HTTPException(403)
    if review.employee_id == user_id and not review.shared_with_employee_at:
        raise HTTPException(403, "Performance narrative not yet shared by manager")
    return PerformanceReviewAgentService(db).get_ai_review(review_id)


@router.post("/performance/{review_id}/ai-review/generate")
def generate_ai_review(
    review_id: str,
    db: Session = Depends(get_db),
    user_id: str = "",
):
    try:
        return PerformanceReviewAgentService(db).generate_ai_review(review_id, user_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/performance/{review_id}/ai-review")
def update_ai_review(
    review_id: str,
    body: AIReviewEditBody,
    db: Session = Depends(get_db),
    user_id: str = "",
):
    try:
        return PerformanceReviewAgentService(db).update_manager_edits(
            review_id, user_id, body.model_dump(exclude_none=True)
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/performance/{review_id}/ai-review/submit")
def submit_ai_manager_review(
    review_id: str,
    body: ManagerAIReviewSubmitBody,
    db: Session = Depends(get_db),
    user_id: str = "",
):
    try:
        review = PerformanceReviewAgentService(db).submit_manager_review_with_agent(
            review_id=review_id,
            manager_id=user_id,
            behavioral_scores=body.behavioral_competency_scores,
            manager_notes=body.manager_notes,
            promotion_eligible=body.promotion_eligible,
            attrition_risk=body.attrition_risk,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _review_dict(review, db)


@router.post("/performance/{review_id}/manager-review")
def post_manager_review(
    review_id: str,
    body: ManagerReviewSubmit,
    db: Session = Depends(get_db),
    user_id: str = "",
):
    behavioral = body.behavioral_competency_scores or {}
    svc = EmployeeReviewService(db)
    try:
        review = svc.submit_manager_review(
            review_id=review_id,
            manager_id=user_id,
            okr_outcomes_assessment=body.okr_outcomes_assessment,
            behavioral_scores=behavioral,
            collaboration_assessment=body.collaboration_assessment,
            ownership_assessment=body.ownership_assessment,
            accountability_assessment=body.accountability_assessment,
            execution_quality_assessment=body.execution_quality_assessment or body.kr_quality_assessment,
            manager_feedback=body.manager_feedback,
            promotion_eligible=body.promotion_eligible or False,
            promotion_recommended=body.promotion_recommended or False,
            pip_needed=body.performance_improvement_plan_needed or False,
            attrition_risk=body.attrition_risk,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _review_dict(review, db)


class DeptHeadModerationBody(BaseModel):
    moderation_notes: Optional[str] = None
    endorse_manager_rating: bool = True


@router.post("/performance/{review_id}/dept-head-moderation")
def post_dept_head_moderation(
    review_id: str,
    body: DeptHeadModerationBody,
    db: Session = Depends(get_db),
    user_id: str = "",
):
    svc = EmployeeReviewService(db)
    try:
        review = svc.submit_dept_head_moderation(
            review_id=review_id,
            dept_head_id=user_id,
            moderation_notes=body.moderation_notes,
            endorse_manager_rating=body.endorse_manager_rating,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _review_dict(review, db)


@router.post("/performance/{review_id}/skip-level-review")
def post_skip_level_review(
    review_id: str,
    body: SkipLevelReviewSubmit,
    db: Session = Depends(get_db),
    user_id: str = "",
):
    svc = EmployeeReviewService(db)
    try:
        review = svc.submit_skip_level_review(
            review_id=review_id,
            skip_level_manager_id=user_id,
            executive_perspective=body.executive_perspective,
            strategic_impact_assessment=body.strategic_impact_assessment,
            leadership_potential=body.leadership_potential or False,
            succession_ready=body.succession_ready or False,
            recommended_development=body.recommended_development,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _review_dict(review, db)


@router.post("/performance/{review_id}/finalize")
def finalize_performance_review(review_id: str, db: Session = Depends(get_db), user_id: str = "", role: str = ""):
    if normalize_role(role) not in HR_ROLES | {SystemRole.MANAGER.value, SystemRole.DEPT_HEAD.value}:
        pass  # managers can finalize for their team in manufacturing workflows

    review = db.query(EmployeePerformanceReview).filter(EmployeePerformanceReview.id == review_id).first()
    if not review:
        raise HTTPException(404)

    scoring = ReviewScoringService(db)
    _ensure_scoring_config(db, review.org_id)
    final_score, rating, _ = scoring.calculate_final_score(review_id)
    review.final_score = final_score
    review.final_rating = rating.value if hasattr(rating, "value") else rating
    db.commit()

    svc = EmployeeReviewService(db)
    try:
        review = svc.finalize_review(review_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _review_dict(review, db)


@router.post("/performance/{review_id}/publish")
def publish_performance_review(review_id: str, db: Session = Depends(get_db), role: str = ""):
    if normalize_role(role) not in HR_ROLES:
        raise HTTPException(403, "HR or admin required to publish reviews")
    svc = EmployeeReviewService(db)
    try:
        review = svc.publish_review(review_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _review_dict(review, db)


@router.get("/performance/{review_id}/audit-trail")
def get_audit_trail(review_id: str, db: Session = Depends(get_db), user_id: str = "", role: str = ""):
    review = db.query(EmployeePerformanceReview).filter(EmployeePerformanceReview.id == review_id).first()
    if not review:
        raise HTTPException(404)
    if not _can_view_review(db, review, user_id, role):
        raise HTTPException(403)
    logs = EmployeeReviewService(db).get_audit_trail(review_id)
    return [
        {
            "id": log.id,
            "action": log.action,
            "actor_user_id": log.actor_user_id,
            "actor_name": _user_name(db, log.actor_user_id),
            "old_state": log.old_state,
            "new_state": log.new_state,
            "changes": log.changes,
            "action_timestamp": log.action_timestamp.isoformat() if log.action_timestamp else None,
            "notes": log.notes,
        }
        for log in logs
    ]


@router.get("/performance/{review_id}/calculation")
def get_review_calculation(review_id: str, db: Session = Depends(get_db), user_id: str = "", role: str = ""):
    review = db.query(EmployeePerformanceReview).filter(EmployeePerformanceReview.id == review_id).first()
    if not review:
        raise HTTPException(404)
    if not _can_view_review(db, review, user_id, role):
        raise HTTPException(403)

    scoring = ReviewScoringService(db)
    _ensure_scoring_config(db, review.org_id)
    if _state_str(review.current_state) not in (
        ReviewState.FINALIZED.value,
        ReviewState.PUBLISHED.value,
        ReviewState.LOCKED.value,
    ):
        scoring.calculate_final_score(review_id)

    calc = (
        db.query(ReviewCalculation)
        .filter(ReviewCalculation.performance_review_id == review_id)
        .order_by(ReviewCalculation.calculation_timestamp.desc())
        .first()
    )
    if not calc:
        final_score, rating, components = scoring.calculate_final_score(review_id)
        calc = (
            db.query(ReviewCalculation)
            .filter(ReviewCalculation.performance_review_id == review_id)
            .order_by(ReviewCalculation.calculation_timestamp.desc())
            .first()
        )
        if not calc:
            return _calculation_payload(
                review_id=review_id,
                components=components,
                final_score=final_score,
                rating=rating.value if hasattr(rating, "value") else rating,
                confidence_score=round(
                    sum(1 for v in components.values() if v is not None) / max(len(components), 1) * 100,
                    1,
                ),
            )

    rating = calc.final_rating.value if hasattr(calc.final_rating, "value") else calc.final_rating
    components = {
        "okr_achievement": calc.okr_achievement_score,
        "kr_quality": calc.kr_quality_score,
        "manager_feedback": calc.manager_feedback_score,
        "behavioral_competency": calc.behavioral_competency_score,
        "peer_feedback": calc.peer_feedback_score,
        "continuous_checkin": calc.continuous_checkin_score,
    }
    return _calculation_payload(
        review_id=review_id,
        calc_id=calc.id,
        components=components,
        final_score=calc.calculated_final_score or 0,
        rating=rating,
        confidence_score=calc.confidence_score or 0,
        bias_flags=calc.bias_flags or [],
        override_applied=calc.override_applied,
        override_reason=calc.override_reason,
        calculation_timestamp=calc.calculation_timestamp.isoformat() if calc.calculation_timestamp else None,
    )


# ---------------------------------------------------------------------------
# 360 feedback (basic)
# ---------------------------------------------------------------------------

@router.get("/feedback-templates")
def list_feedback_templates(db: Session = Depends(get_db), org_id: str = "", feedback_type: str = ""):
    q = db.query(FeedbackTemplate).filter(FeedbackTemplate.org_id == org_id, FeedbackTemplate.enabled == True)
    if feedback_type:
        q = q.filter(FeedbackTemplate.feedback_type == feedback_type)
    templates = q.all()
    return [
        {
            "id": t.id,
            "org_id": t.org_id,
            "feedback_type": t.feedback_type.value if hasattr(t.feedback_type, "value") else t.feedback_type,
            "role_type": t.role_type,
            "name": t.name,
            "questions": t.questions,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in templates
    ]


@router.post("/feedback-responses")
def submit_feedback_response(
    body: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    user_id: str = "",
):
    resp = FeedbackResponse(
        performance_review_id=body["performance_review_id"],
        feedback_template_id=body.get("feedback_template_id") or body.get("template_id"),
        feedback_giver_user_id=user_id,
        feedback_type=body.get("feedback_type", "PEER"),
        is_anonymous=body.get("is_anonymous", True),
        responses=body.get("responses", {}),
        overall_feedback=body.get("overall_feedback"),
        sentiment_score=body.get("sentiment_score"),
    )
    db.add(resp)
    db.commit()
    db.refresh(resp)
    return {"id": resp.id, "performance_review_id": resp.performance_review_id, "submitted_at": resp.submitted_at.isoformat()}


@router.get("/performance/{review_id}/feedback-responses")
def list_feedback_responses(review_id: str, db: Session = Depends(get_db)):
    rows = db.query(FeedbackResponse).filter(FeedbackResponse.performance_review_id == review_id).all()
    return [{"id": r.id, "feedback_type": str(r.feedback_type), "sentiment_score": r.sentiment_score} for r in rows]


@router.get("/performance/{review_id}/feedback-synthesis")
def get_feedback_synthesis(review_id: str, db: Session = Depends(get_db)):
    syn = db.query(FeedbackSynthesis).filter(FeedbackSynthesis.performance_review_id == review_id).first()
    if not syn:
        return {
            "performance_review_id": review_id,
            "peer_feedback_score": 50.0,
            "peer_feedback_count": 0,
            "overall_external_perception_score": 50.0,
        }
    return {
        "performance_review_id": review_id,
        "peer_feedback_score": syn.peer_feedback_score,
        "peer_feedback_count": syn.peer_feedback_count,
        "overall_external_perception_score": syn.overall_external_perception_score,
    }


# ---------------------------------------------------------------------------
# Competency frameworks
# ---------------------------------------------------------------------------

@router.get("/competency-frameworks")
def list_competency_frameworks(db: Session = Depends(get_db), org_id: str = "", role_type: str = ""):
    _seed_competency_frameworks(db, org_id)
    q = db.query(CompetencyFramework).filter(CompetencyFramework.org_id == org_id, CompetencyFramework.enabled == True)
    if role_type:
        q = q.filter(CompetencyFramework.role_type == role_type)
    return [
        {"id": f.id, "org_id": f.org_id, "role_type": f.role_type, "name": f.name, "department_id": f.department_id}
        for f in q.all()
    ]


@router.get("/competency-frameworks/{framework_id}/competencies")
def list_competencies(framework_id: str, db: Session = Depends(get_db)):
    comps = db.query(Competency).filter(Competency.framework_id == framework_id, Competency.enabled == True).all()
    return [
        {
            "id": c.id,
            "framework_id": c.framework_id,
            "name": c.name,
            "description": c.description,
            "weight": c.weight,
            "proficiency_levels": c.proficiency_levels,
            "display_order": c.display_order,
        }
        for c in comps
    ]


@router.post("/performance/{review_id}/competency-assessments")
def submit_competency_assessments(
    review_id: str,
    body: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    user_id: str = "",
):
    review = db.query(EmployeePerformanceReview).filter(EmployeePerformanceReview.id == review_id).first()
    if not review:
        raise HTTPException(404)
    manager_section = (
        db.query(ReviewSection)
        .filter(
            ReviewSection.performance_review_id == review_id,
            ReviewSection.section_type == SectionType.MANAGER,
        )
        .first()
    )
    if not manager_section:
        manager_section = ReviewSection(
            performance_review_id=review_id,
            section_type=SectionType.MANAGER,
            submitted_by_user_id=user_id,
        )
        db.add(manager_section)
        db.flush()

    results = []
    for item in body.get("assessments", []):
        a = CompetencyAssessment(
            review_section_id=manager_section.id,
            competency_id=item["competency_id"],
            proficiency_level=item.get("proficiency_level", item.get("rating", 3)),
            assessor_comments=item.get("assessor_comments"),
        )
        db.add(a)
        results.append(a)
    db.commit()
    return [
        {"id": a.id, "competency_id": a.competency_id, "proficiency_level": a.proficiency_level}
        for a in results
    ]


# ---------------------------------------------------------------------------
# Dashboards
# ---------------------------------------------------------------------------

@router.get("/dashboards/employee")
def employee_dashboard(
    db: Session = Depends(get_db),
    org_id: str = "",
    user_id: str = "",
    employee_id: str = "",
):
    eid = employee_id or user_id
    reviews = db.query(EmployeePerformanceReview).filter(
        EmployeePerformanceReview.org_id == org_id,
        EmployeePerformanceReview.employee_id == eid,
    ).all()
    checkins = (
        db.query(ContinuousCheckin)
        .filter(ContinuousCheckin.employee_id == eid, ContinuousCheckin.is_latest == True)
        .count()
    )
    pending_self = sum(1 for r in reviews if _state_str(r.current_state) == ReviewState.DRAFT.value)
    snapshot = build_okr_progress_snapshot(db, eid, org_id)
    return {
        "employee_id": eid,
        "pending_self_reviews": pending_self,
        "total_reviews": len(reviews),
        "checkin_count": checkins,
        "okr_avg_progress": snapshot["avg_progress"],
        "reviews": [_review_dict(r, db) for r in reviews[:5]],
    }


@router.get("/dashboards/manager")
def manager_dashboard(
    db: Session = Depends(get_db),
    org_id: str = "",
    user_id: str = "",
    manager_id: str = "",
):
    mid = manager_id or user_id
    team_reviews = db.query(EmployeePerformanceReview).filter(
        EmployeePerformanceReview.org_id == org_id,
        EmployeePerformanceReview.manager_id == mid,
    ).all()
    pending = sum(
        1
        for r in team_reviews
        if _state_str(r.current_state) in (ReviewState.SELF_SUBMITTED.value, ReviewState.SKIP_LEVEL_REVIEW.value)
    )
    from server.services.checkin_coaching_service import INBOX_STATUSES

    checkins_pending = (
        db.query(ContinuousCheckin)
        .filter(
            ContinuousCheckin.manager_id == mid,
            ContinuousCheckin.workflow_status.in_(list(INBOX_STATUSES)),
            ContinuousCheckin.is_latest == True,
        )
        .count()
    )
    return {
        "manager_id": mid,
        "team_review_count": len(team_reviews),
        "pending_manager_reviews": pending,
        "checkins_awaiting_response": checkins_pending,
        "completion_pct": round(
            sum(1 for r in team_reviews if _state_str(r.current_state) in (ReviewState.FINALIZED.value, ReviewState.PUBLISHED.value))
            / max(len(team_reviews), 1)
            * 100,
            1,
        ),
    }


@router.get("/dashboards/department/{department_id}")
def department_dashboard(department_id: str, db: Session = Depends(get_db), org_id: str = ""):
    users = db.query(User).filter(User.org_id == org_id, User.department == department_id).all()
    user_ids = [u.id for u in users]
    reviews = (
        db.query(EmployeePerformanceReview)
        .filter(EmployeePerformanceReview.org_id == org_id, EmployeePerformanceReview.employee_id.in_(user_ids))
        .all()
        if user_ids
        else []
    )
    avg_score = (
        round(sum(r.final_score or 0 for r in reviews) / len(reviews), 1) if reviews else 0
    )
    return {
        "department_id": department_id,
        "headcount": len(users),
        "review_count": len(reviews),
        "avg_final_score": avg_score,
    }


@router.get("/dashboards/organization")
def organization_dashboard(db: Session = Depends(get_db), org_id: str = ""):
    reviews = db.query(EmployeePerformanceReview).filter(EmployeePerformanceReview.org_id == org_id).all()
    finalized = [r for r in reviews if _state_str(r.current_state) in (ReviewState.FINALIZED.value, ReviewState.PUBLISHED.value)]
    high = sum(1 for r in finalized if (r.final_score or 0) >= 85)
    low = sum(1 for r in finalized if (r.final_score or 0) < 50)
    return {
        "org_id": org_id,
        "total_reviews": len(reviews),
        "finalized_count": len(finalized),
        "high_performers": high,
        "low_performers": low,
        "completion_pct": round(len(finalized) / max(len(reviews), 1) * 100, 1),
        "overdue_reviews": sum(
            1
            for r in reviews
            if _state_str(r.current_state)
            not in (ReviewState.FINALIZED.value, ReviewState.PUBLISHED.value, ReviewState.LOCKED.value)
        ),
    }
