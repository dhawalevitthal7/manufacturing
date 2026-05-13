import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from server.database import get_db
from server.models import Review, ReviewCycle, User, Objective, KeyResult, ProgressUpdate, ReportingRelationship, AuditLog
from server.schemas import (ReviewCycleCreate, ReviewCreate, SelfReviewSubmit,
                            ManagerReviewSubmit, SkipLevelReviewSubmit, CalibrationSubmit)

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


# ===== CYCLES =====
@router.get("/cycles")
def list_cycles(db: Session = Depends(get_db), org_id: str = ""):
    cycles = db.query(ReviewCycle).filter(ReviewCycle.org_id == org_id).order_by(ReviewCycle.created_at.desc()).all()
    result = []
    for c in cycles:
        total = db.query(Review).filter(Review.cycle_id == c.id).count()
        completed = db.query(Review).filter(Review.cycle_id == c.id, Review.status == "COMPLETED").count()
        result.append({
            "id": c.id, "name": c.name, "cycle_type": c.cycle_type,
            "start_date": c.start_date, "end_date": c.end_date, "status": c.status,
            "total_reviews": total, "completed_reviews": completed,
        })
    return result


@router.post("/cycles")
def create_cycle(req: ReviewCycleCreate, db: Session = Depends(get_db), org_id: str = "", user_id: str = ""):
    cycle = ReviewCycle(org_id=org_id, name=req.name, cycle_type=req.cycle_type,
                        start_date=req.start_date, end_date=req.end_date)
    db.add(cycle)
    db.add(AuditLog(org_id=org_id, user_id=user_id, action="CREATE", entity_type="REVIEW_CYCLE"))
    db.commit()
    db.refresh(cycle)
    return {"id": cycle.id, "name": cycle.name}


@router.put("/cycles/{cycle_id}/close")
def close_cycle(cycle_id: str, db: Session = Depends(get_db)):
    c = db.query(ReviewCycle).filter(ReviewCycle.id == cycle_id).first()
    if not c: raise HTTPException(404)
    c.status = "CLOSED"
    db.commit()
    return {"status": "closed"}


# ===== REVIEWS =====
@router.get("")
def list_reviews(db: Session = Depends(get_db), org_id: str = "", user_id: str = "",
                 role: str = "", cycle_id: str = "", status: str = ""):
    q = db.query(Review).filter(Review.org_id == org_id)
    if cycle_id:
        q = q.filter(Review.cycle_id == cycle_id)
    if status:
        q = q.filter(Review.status == status)
    # Scope by role
    if role in ("EMPLOYEE", "SUPERVISOR"):
        q = q.filter((Review.reviewee_id == user_id) | (Review.reviewer_id == user_id))
    elif role in ("MANAGER", "DEPT_HEAD"):
        q = q.filter((Review.reviewer_id == user_id) | (Review.reviewee_id == user_id) | (Review.skip_level_reviewer_id == user_id))
    reviews = q.order_by(Review.created_at.desc()).all()
    return [_review_dict(r, db) for r in reviews]


@router.post("")
def create_review(req: ReviewCreate, db: Session = Depends(get_db), org_id: str = ""):
    review = Review(org_id=org_id, cycle_id=req.cycle_id, reviewee_id=req.reviewee_id,
                    reviewer_id=req.reviewer_id, skip_level_reviewer_id=req.skip_level_reviewer_id,
                    status="SELF_REVIEW_PENDING")
    db.add(review)
    db.commit()
    db.refresh(review)
    return _review_dict(review, db)


@router.post("/initiate-bulk")
def initiate_bulk_reviews(cycle_id: str, db: Session = Depends(get_db), org_id: str = ""):
    """Auto-create reviews using DIRECT reporting relationships as reviewer,
    and REVIEWER relationships for skip-level."""
    employees = db.query(User).filter(User.org_id == org_id, User.is_active == True).all()
    created = 0
    for emp in employees:
        # Find direct manager (DIRECT relationship)
        direct = db.query(ReportingRelationship).filter(
            ReportingRelationship.employee_id == emp.id,
            ReportingRelationship.relationship_type == "DIRECT",
            ReportingRelationship.is_active == True,
        ).first()
        if not direct:
            continue  # skip employees without a direct manager
        # Find skip-level reviewer if exists
        skip = db.query(ReportingRelationship).filter(
            ReportingRelationship.employee_id == emp.id,
            ReportingRelationship.relationship_type == "REVIEWER",
            ReportingRelationship.is_active == True,
        ).first()
        # Check no duplicate
        existing = db.query(Review).filter(Review.cycle_id == cycle_id, Review.reviewee_id == emp.id).first()
        if existing:
            continue
        review = Review(
            org_id=org_id, cycle_id=cycle_id,
            reviewee_id=emp.id, reviewer_id=direct.manager_id,
            skip_level_reviewer_id=skip.manager_id if skip else None,
            status="SELF_REVIEW_PENDING",
        )
        db.add(review)
        created += 1
    db.commit()
    return {"created": created}


@router.get("/{review_id}")
def get_review(review_id: str, db: Session = Depends(get_db)):
    r = db.query(Review).filter(Review.id == review_id).first()
    if not r: raise HTTPException(404)
    result = _review_dict(r, db)
    # Include OKR execution summary for context
    objs = db.query(Objective).filter(Objective.owner_id == r.reviewee_id).all()
    result["okr_summary"] = {
        "total": len(objs),
        "completed": sum(1 for o in objs if o.progress >= 100),
        "avg_progress": round(sum(o.progress for o in objs) / max(len(objs), 1), 1),
        "objectives": [{"title": o.title, "progress": o.progress, "level": o.level} for o in objs],
    }
    return result


# ===== REVIEW STAGES =====
@router.put("/{review_id}/self-review")
def submit_self_review(review_id: str, req: SelfReviewSubmit, db: Session = Depends(get_db)):
    r = db.query(Review).filter(Review.id == review_id).first()
    if not r: raise HTTPException(404)
    if r.status != "SELF_REVIEW_PENDING":
        raise HTTPException(400, "Self-review not pending")
    r.self_rating = req.self_rating
    r.self_review_text = req.self_review_text
    r.self_submitted_at = datetime.utcnow()
    r.status = "MANAGER_REVIEW_PENDING"
    db.commit()
    return _review_dict(r, db)


@router.put("/{review_id}/manager-review")
def submit_manager_review(review_id: str, req: ManagerReviewSubmit, db: Session = Depends(get_db)):
    r = db.query(Review).filter(Review.id == review_id).first()
    if not r: raise HTTPException(404)
    if r.status != "MANAGER_REVIEW_PENDING":
        raise HTTPException(400, "Manager review not pending")
    r.manager_rating = req.manager_rating
    r.manager_review_text = req.manager_review_text
    r.strengths = req.strengths
    r.improvements = req.improvements
    r.manager_submitted_at = datetime.utcnow()
    # Move to skip-level if reviewer exists, otherwise calibration
    if r.skip_level_reviewer_id:
        r.status = "SKIP_LEVEL_PENDING"
    else:
        r.status = "CALIBRATION_PENDING"
    db.commit()
    return _review_dict(r, db)


@router.put("/{review_id}/skip-level-review")
def submit_skip_level_review(review_id: str, req: SkipLevelReviewSubmit, db: Session = Depends(get_db)):
    r = db.query(Review).filter(Review.id == review_id).first()
    if not r: raise HTTPException(404)
    if r.status != "SKIP_LEVEL_PENDING":
        raise HTTPException(400, "Skip-level review not pending")
    r.skip_level_rating = req.skip_level_rating
    r.skip_level_review_text = req.skip_level_review_text
    r.skip_level_submitted_at = datetime.utcnow()
    r.status = "CALIBRATION_PENDING"
    db.commit()
    return _review_dict(r, db)


@router.put("/{review_id}/calibrate")
def calibrate_review(review_id: str, req: CalibrationSubmit, db: Session = Depends(get_db), user_id: str = ""):
    r = db.query(Review).filter(Review.id == review_id).first()
    if not r: raise HTTPException(404)
    if r.status != "CALIBRATION_PENDING":
        raise HTTPException(400, "Not pending calibration")
    r.calibrated_rating = req.calibrated_rating
    r.calibration_notes = req.calibration_notes
    r.calibrated_by_id = user_id
    r.calibrated_at = datetime.utcnow()
    r.final_rating = req.final_rating
    r.status = "COMPLETED"
    r.completed_at = datetime.utcnow()
    db.commit()
    return _review_dict(r, db)


# ===== AI INTELLIGENCE =====
@router.post("/{review_id}/generate-ai")
def generate_ai_review(review_id: str, db: Session = Depends(get_db)):
    """Generate AI performance summary from OKR execution data."""
    r = db.query(Review).filter(Review.id == review_id).first()
    if not r: raise HTTPException(404)

    reviewee = db.query(User).filter(User.id == r.reviewee_id).first()
    objs = db.query(Objective).filter(Objective.owner_id == r.reviewee_id).all()
    name = reviewee.name if reviewee else "Employee"

    total = len(objs)
    completed = sum(1 for o in objs if o.progress >= 100)
    avg = round(sum(o.progress for o in objs) / max(total, 1), 1)

    # Analyze progress updates
    total_updates, approved, rejected = 0, 0, 0
    all_krs = []
    for o in objs:
        krs = db.query(KeyResult).filter(KeyResult.objective_id == o.id).all()
        all_krs.extend(krs)
        for kr in krs:
            updates = db.query(ProgressUpdate).filter(ProgressUpdate.key_result_id == kr.id).all()
            total_updates += len(updates)
            approved += sum(1 for u in updates if u.status == "APPROVED")
            rejected += sum(1 for u in updates if u.status == "REJECTED")

    high = [o.title for o in objs if o.progress >= 80]
    at_risk = [o.title for o in objs if 0 < o.progress < 40]
    stalled = [o.title for o in objs if o.progress == 0 and db.query(KeyResult).filter(KeyResult.objective_id == o.id).count() > 0]

    # Determine assessment
    if avg >= 80: assessment, emoji = "Exceptional Performer", "⭐"
    elif avg >= 60: assessment, emoji = "Strong Performer", "✅"
    elif avg >= 40: assessment, emoji = "Developing", "📈"
    else: assessment, emoji = "Needs Improvement", "⚠️"

    consistency = "High" if total_updates > total * 2 else "Medium" if total_updates > total else "Low"
    approval_rate = round(approved / max(total_updates, 1) * 100)

    summary = f"""## Performance Summary: {name}

### Overall: {assessment} {emoji} ({avg}% avg completion)

**Metrics:** {total} objectives | {completed} completed | {len(all_krs)} key results
**Execution:** {total_updates} updates | {consistency} consistency | {approval_rate}% approval rate

### Achievements
{chr(10).join('- ✅ ' + h for h in high) if high else '- No objectives above 80%'}

### Risks
{chr(10).join('- ⚠️ ' + a + ' (below 40%)' for a in at_risk) if at_risk else '- No at-risk objectives'}

### Stalled
{chr(10).join('- 🔴 ' + s for s in stalled) if stalled else '- None'}

### Recommendations
{('- Consider expanded responsibilities and leadership development' if avg >= 70 else '- Schedule focused check-ins and identify skill gaps') if avg >= 40 else '- Conduct root cause analysis and assign peer mentor'}"""

    r.ai_summary = summary
    r.ai_strengths = ", ".join(high) if high else "No standout objectives"
    r.ai_improvements = ", ".join(at_risk + stalled) if (at_risk or stalled) else "All objectives on track"
    r.ai_risk_flags = json.dumps({
        "low_consistency": consistency == "Low",
        "high_rejection_rate": rejected > approved if total_updates > 0 else False,
        "stalled_objectives": len(stalled),
        "overall_below_threshold": avg < 40,
    })
    db.commit()
    return {"ai_summary": summary, "strengths": r.ai_strengths, "improvements": r.ai_improvements, "risk_flags": r.ai_risk_flags}


def _review_dict(r, db):
    reviewee = db.query(User).filter(User.id == r.reviewee_id).first()
    reviewer = db.query(User).filter(User.id == r.reviewer_id).first()
    cycle = db.query(ReviewCycle).filter(ReviewCycle.id == r.cycle_id).first()
    skip_reviewer = db.query(User).filter(User.id == r.skip_level_reviewer_id).first() if r.skip_level_reviewer_id else None
    calibrator = db.query(User).filter(User.id == r.calibrated_by_id).first() if r.calibrated_by_id else None
    return {
        "id": r.id, "cycle_id": r.cycle_id, "cycle_name": cycle.name if cycle else None,
        "reviewee_id": r.reviewee_id, "reviewee_name": reviewee.name if reviewee else None,
        "reviewer_id": r.reviewer_id, "reviewer_name": reviewer.name if reviewer else None,
        "skip_level_reviewer_id": r.skip_level_reviewer_id,
        "skip_level_reviewer_name": skip_reviewer.name if skip_reviewer else None,
        "status": r.status,
        "self_rating": r.self_rating, "self_review_text": r.self_review_text,
        "manager_rating": r.manager_rating, "manager_review_text": r.manager_review_text,
        "skip_level_rating": r.skip_level_rating, "skip_level_review_text": r.skip_level_review_text,
        "calibrated_rating": r.calibrated_rating, "calibration_notes": r.calibration_notes,
        "calibrated_by": calibrator.name if calibrator else None,
        "ai_summary": r.ai_summary, "ai_strengths": r.ai_strengths,
        "ai_improvements": r.ai_improvements, "ai_risk_flags": r.ai_risk_flags,
        "final_rating": r.final_rating, "strengths": r.strengths, "improvements": r.improvements,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
    }
