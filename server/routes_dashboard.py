from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from server.database import get_db
from server.models import (User, Plant, Department, Team, Objective, KeyResult,
                           ProgressUpdate, Review, ReviewCycle, ReportingRelationship, AuditLog)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def get_dashboard(db: Session = Depends(get_db), org_id: str = "", user_id: str = "", role: str = ""):
    """Role-scoped dashboard data using reporting hierarchy."""
    return {
        "stats": _get_stats(db, org_id, user_id, role),
        "recent_updates": _get_recent_updates(db, org_id, user_id, role),
        "okr_summary": _get_okr_summary(db, org_id, user_id, role),
        "pending_actions": _get_pending_actions(db, org_id, user_id, role),
        "department_progress": _get_dept_progress(db, org_id),
        "top_objectives": _get_top_objectives(db, org_id, user_id, role),
        "department_health": _get_department_health(db, org_id),
        "execution_trend": _get_execution_trend(db, org_id),
    }


def _get_subordinate_ids(db, user_id):
    """Get all direct and indirect report IDs using reporting relationships."""
    result = []
    queue = [user_id]
    visited = set()
    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        directs = db.query(ReportingRelationship).filter(
            ReportingRelationship.manager_id == current,
            ReportingRelationship.relationship_type == "DIRECT",
            ReportingRelationship.is_active == True,
        ).all()
        for r in directs:
            result.append(r.employee_id)
            queue.append(r.employee_id)
    return result


def _get_stats(db, org_id, user_id, role):
    """Return structured stats with label, value, delta, trend for dashboard cards."""
    if role in ("SUPER_ADMIN", "HR_ADMIN", "CEO", "VP_OPERATIONS"):
        total_emp = db.query(User).filter(User.org_id == org_id, User.is_active == True).count()
        total_plants = db.query(Plant).filter(Plant.org_id == org_id, Plant.is_active == True).count()
        total_teams = db.query(Team).filter(Team.org_id == org_id, Team.is_active == True).count()
        total_depts = db.query(Department).filter(Department.org_id == org_id, Department.is_active == True).count()
        total_okrs = db.query(Objective).filter(Objective.org_id == org_id, Objective.status == "ACTIVE").count()
        active_reviews = db.query(Review).join(ReviewCycle).filter(
            ReviewCycle.org_id == org_id, Review.status != "COMPLETED"
        ).count()
        avg_progress = db.query(func.avg(Objective.progress)).filter(
            Objective.org_id == org_id, Objective.status == "ACTIVE"
        ).scalar() or 0
        completed_reviews = db.query(Review).join(ReviewCycle).filter(
            ReviewCycle.org_id == org_id, Review.status == "COMPLETED"
        ).count()
        return {
            "total_employees": {
                "label": "Total Employees", "value": total_emp,
                "delta": 0, "trend": "flat", "hint": "active employees"
            },
            "total_plants": {
                "label": "Total Plants", "value": total_plants,
                "delta": 0, "trend": "flat", "hint": "manufacturing facilities"
            },
            "total_departments": {
                "label": "Total Departments", "value": total_depts,
                "delta": 0, "trend": "flat", "hint": "across all plants"
            },
            "total_teams": {
                "label": "Total Teams", "value": total_teams,
                "delta": 0, "trend": "flat", "hint": "operational teams"
            },
            "total_objectives": {
                "label": "Active Objectives", "value": total_okrs,
                "delta": 0, "trend": "flat", "hint": "currently active"
            },
            "active_reviews": {
                "label": "Active Reviews", "value": active_reviews,
                "delta": 0, "trend": "flat", "hint": "in progress"
            },
            "avg_progress": {
                "label": "Avg. Progress", "value": f"{round(avg_progress, 1)}%",
                "delta": round(avg_progress, 1), "trend": "up" if avg_progress >= 50 else "down",
                "hint": "across all OKRs"
            },
            "completed_reviews": {
                "label": "Completed Reviews", "value": completed_reviews,
                "delta": 0, "trend": "flat", "hint": "this cycle"
            },
        }
    elif role in ("PLANT_HEAD", "PLANT_MANAGER"):
        user = db.query(User).filter(User.id == user_id).first()
        plant_id = user.plant_id if user else None
        sub_ids = _get_subordinate_ids(db, user_id)
        scope_ids = sub_ids + [user_id]
        plant_emp = db.query(User).filter(User.plant_id == plant_id, User.is_active == True).count() if plant_id else len(scope_ids)
        team_okrs = db.query(Objective).filter(Objective.owner_id.in_(scope_ids)).count() if scope_ids else 0
        avg_progress = db.query(func.avg(Objective.progress)).filter(
            Objective.owner_id.in_(scope_ids), Objective.status == "ACTIVE"
        ).scalar() or 0
        pending_reviews = db.query(Review).filter(
            Review.reviewer_id == user_id, Review.status == "MANAGER_REVIEW_PENDING"
        ).count()
        return {
            "plant_employees": {
                "label": "Plant Employees", "value": plant_emp,
                "delta": 0, "trend": "flat", "hint": "in your plant"
            },
            "plant_objectives": {
                "label": "Plant Objectives", "value": team_okrs,
                "delta": 0, "trend": "flat", "hint": "in scope"
            },
            "avg_progress": {
                "label": "Avg. Progress", "value": f"{round(avg_progress, 1)}%",
                "delta": round(avg_progress, 1), "trend": "up" if avg_progress >= 50 else "down",
                "hint": "plant OKRs"
            },
            "pending_reviews": {
                "label": "Pending Reviews", "value": pending_reviews,
                "delta": 0, "trend": "flat", "hint": "awaiting action"
            },
        }
    elif role in ("MANAGER", "DEPT_HEAD", "SUPERVISOR", "TEAM_LEAD"):
        sub_ids = _get_subordinate_ids(db, user_id)
        scope_ids = sub_ids + [user_id]
        team_okrs = db.query(Objective).filter(Objective.owner_id.in_(scope_ids)).count() if scope_ids else 0
        avg_progress = db.query(func.avg(Objective.progress)).filter(
            Objective.owner_id.in_(scope_ids), Objective.status == "ACTIVE"
        ).scalar() or 0
        pending_val = 0
        for uid in sub_ids:
            objs = db.query(Objective).filter(Objective.owner_id == uid).all()
            for o in objs:
                krs = db.query(KeyResult).filter(KeyResult.objective_id == o.id).all()
                for kr in krs:
                    pending_val += db.query(ProgressUpdate).filter(
                        ProgressUpdate.key_result_id == kr.id, ProgressUpdate.status == "PENDING"
                    ).count()
        pending_reviews = db.query(Review).filter(
            Review.reviewer_id == user_id, Review.status == "MANAGER_REVIEW_PENDING"
        ).count()
        return {
            "direct_reports": {
                "label": "Direct Reports", "value": len(sub_ids),
                "delta": 0, "trend": "flat", "hint": "team members"
            },
            "team_objectives": {
                "label": "Team Objectives", "value": team_okrs,
                "delta": 0, "trend": "flat", "hint": "in scope"
            },
            "avg_team_progress": {
                "label": "Avg. Team Progress", "value": f"{round(avg_progress, 1)}%",
                "delta": round(avg_progress, 1), "trend": "up" if avg_progress >= 50 else "down",
                "hint": "team OKRs"
            },
            "pending_validations": {
                "label": "Pending Validations", "value": pending_val,
                "delta": 0, "trend": "flat", "hint": "awaiting approval"
            },
        }
    else:
        my_okrs = db.query(Objective).filter(
            Objective.owner_id == user_id, Objective.status == "ACTIVE"
        ).count()
        avg_progress = db.query(func.avg(Objective.progress)).filter(
            Objective.owner_id == user_id, Objective.status == "ACTIVE"
        ).scalar() or 0
        my_reviews = db.query(Review).filter(
            Review.reviewee_id == user_id, Review.status == "SELF_REVIEW_PENDING"
        ).count()
        return {
            "my_objectives": {
                "label": "My Objectives", "value": my_okrs,
                "delta": 0, "trend": "flat", "hint": "active OKRs"
            },
            "avg_progress": {
                "label": "My Progress", "value": f"{round(avg_progress, 1)}%",
                "delta": round(avg_progress, 1), "trend": "up" if avg_progress >= 50 else "down",
                "hint": "across all OKRs"
            },
            "pending_self_reviews": {
                "label": "Pending Reviews", "value": my_reviews,
                "delta": 0, "trend": "flat", "hint": "self-reviews due"
            },
        }


def _get_top_objectives(db, org_id, user_id, role):
    """Return top objectives grouped by hierarchy scope for dashboard display."""
    if role in ("SUPER_ADMIN", "HR_ADMIN", "CEO", "VP_OPERATIONS"):
        objs = db.query(Objective).filter(
            Objective.org_id == org_id, Objective.status == "ACTIVE"
        ).order_by(Objective.progress.desc()).limit(10).all()
    elif role in ("MANAGER", "DEPT_HEAD", "PLANT_HEAD", "PLANT_MANAGER", "SUPERVISOR", "TEAM_LEAD"):
        sub_ids = _get_subordinate_ids(db, user_id)
        scope_ids = sub_ids + [user_id]
        objs = db.query(Objective).filter(
            Objective.owner_id.in_(scope_ids), Objective.status == "ACTIVE"
        ).order_by(Objective.progress.desc()).limit(10).all()
    else:
        objs = db.query(Objective).filter(
            Objective.owner_id == user_id, Objective.status == "ACTIVE"
        ).order_by(Objective.progress.desc()).limit(10).all()

    result = []
    for o in objs:
        owner = db.query(User).filter(User.id == o.owner_id).first()
        # Determine scope label
        scope = o.level or "INDIVIDUAL"
        scope_label = scope.replace("_", " ").title()
        if o.plant_id:
            plant = db.query(Plant).filter(Plant.id == o.plant_id).first()
            if plant:
                scope_label = f"Plant · {plant.name}"
        if o.department_id:
            dept = db.query(Department).filter(Department.id == o.department_id).first()
            if dept:
                scope_label = f"Department · {dept.name}"
        if o.team_id:
            team = db.query(Team).filter(Team.id == o.team_id).first()
            if team:
                scope_label = f"Team · {team.name}"
        # Determine status
        progress = o.progress or 0
        if progress >= 100:
            status = "completed"
        elif progress >= 60:
            status = "on_track"
        elif progress >= 30:
            status = "at_risk"
        else:
            status = "off_track"
        # Get parent objective title if exists
        parent_title = None
        if o.parent_id:
            parent = db.query(Objective).filter(Objective.id == o.parent_id).first()
            if parent:
                parent_title = parent.title
        # Get key results
        krs = db.query(KeyResult).filter(KeyResult.objective_id == o.id).all()
        result.append({
            "id": o.id,
            "objective": o.title,
            "owner": owner.name if owner else "Unassigned",
            "scope": scope_label,
            "level": o.level,
            "progress": round(progress, 1),
            "status": status,
            "parent_objective": parent_title,
            "key_results": [
                {"title": kr.title, "progress": round((kr.current_value / kr.target_value * 100) if kr.target_value else 0, 1)}
                for kr in krs
            ],
        })
    return result


def _get_department_health(db, org_id):
    """Aggregate department execution data for health chart."""
    departments = db.query(Department).filter(
        Department.org_id == org_id, Department.is_active == True
    ).all()
    result = []
    for dept in departments:
        user_ids = [u.id for u in db.query(User).filter(
            User.department_id == dept.id, User.is_active == True
        ).all()]
        # Also include objectives scoped directly to the department
        dept_objs = db.query(Objective).filter(
            Objective.org_id == org_id,
            Objective.status == "ACTIVE",
            (Objective.department_id == dept.id) | (Objective.owner_id.in_(user_ids) if user_ids else False)
        ).all() if user_ids else db.query(Objective).filter(
            Objective.org_id == org_id,
            Objective.department_id == dept.id,
            Objective.status == "ACTIVE"
        ).all()
        on_track = 0
        at_risk = 0
        off_track = 0
        total_progress = 0
        for o in dept_objs:
            p = o.progress or 0
            total_progress += p
            if p >= 60:
                on_track += 1
            elif p >= 30:
                at_risk += 1
            else:
                off_track += 1
        avg_progress = round(total_progress / max(len(dept_objs), 1), 1)
        # Get plant name for context
        plant = db.query(Plant).filter(Plant.id == dept.plant_id).first()
        result.append({
            "dept": dept.name,
            "plant_name": plant.name if plant else "",
            "onTrack": on_track,
            "atRisk": at_risk,
            "offTrack": off_track,
            "avg_progress": avg_progress,
            "objective_count": len(dept_objs),
            "employee_count": len(user_ids),
        })
    return result


def _get_execution_trend(db, org_id):
    """Get execution trend data from actual objective progress.
    Since we don't track weekly snapshots, compute from current data."""
    # Return current aggregate data for now
    active_objs = db.query(Objective).filter(
        Objective.org_id == org_id, Objective.status == "ACTIVE"
    ).all()
    if not active_objs:
        return []
    avg_progress = sum(o.progress or 0 for o in active_objs) / len(active_objs)
    # Return single current data point; full weekly tracking requires a scheduled job
    return [
        {"week": "Current", "planned": 100, "actual": round(avg_progress, 1)},
    ]


def _get_recent_updates(db, org_id, user_id, role):
    if role in ("SUPER_ADMIN", "HR_ADMIN"):
        updates = db.query(ProgressUpdate).join(KeyResult).join(Objective).filter(Objective.org_id == org_id).order_by(ProgressUpdate.created_at.desc()).limit(10).all()
    elif role in ("MANAGER", "DEPT_HEAD", "PLANT_MANAGER", "SUPERVISOR"):
        sub_ids = _get_subordinate_ids(db, user_id)
        updates = db.query(ProgressUpdate).filter(ProgressUpdate.submitted_by_id.in_(sub_ids + [user_id])).order_by(ProgressUpdate.created_at.desc()).limit(10).all()
    else:
        updates = db.query(ProgressUpdate).filter(ProgressUpdate.submitted_by_id == user_id).order_by(ProgressUpdate.created_at.desc()).limit(10).all()

    result = []
    for u in updates:
        kr = db.query(KeyResult).filter(KeyResult.id == u.key_result_id).first()
        submitter = db.query(User).filter(User.id == u.submitted_by_id).first()
        result.append({
            "id": u.id, "key_result": kr.title if kr else "",
            "submitted_by": submitter.name if submitter else "",
            "avatar_color": submitter.avatar_color if submitter else "#6366f1",
            "previous_value": u.previous_value, "new_value": u.new_value,
            "notes": u.notes, "blockers": u.blockers, "status": u.status,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        })
    return result


def _get_okr_summary(db, org_id, user_id, role):
    if role in ("SUPER_ADMIN", "HR_ADMIN"):
        objs = db.query(Objective).filter(Objective.org_id == org_id).all()
    elif role in ("MANAGER", "DEPT_HEAD", "PLANT_MANAGER", "SUPERVISOR"):
        sub_ids = _get_subordinate_ids(db, user_id)
        objs = db.query(Objective).filter(Objective.owner_id.in_(sub_ids + [user_id])).all()
    else:
        objs = db.query(Objective).filter(Objective.owner_id == user_id).all()

    by_level = {}
    for o in objs:
        lvl = o.level or "INDIVIDUAL"
        if lvl not in by_level:
            by_level[lvl] = {"count": 0, "avg_progress": 0, "total_progress": 0}
        by_level[lvl]["count"] += 1
        by_level[lvl]["total_progress"] += o.progress
    for lvl in by_level:
        c = by_level[lvl]["count"]
        by_level[lvl]["avg_progress"] = round(by_level[lvl]["total_progress"] / c, 1) if c else 0
        del by_level[lvl]["total_progress"]
    return by_level


def _get_pending_actions(db, org_id, user_id, role):
    actions = []
    if role in ("MANAGER", "DEPT_HEAD", "PLANT_MANAGER", "SUPERVISOR", "SUPER_ADMIN"):
        sub_ids = _get_subordinate_ids(db, user_id)
        for uid in sub_ids:
            objs = db.query(Objective).filter(Objective.owner_id == uid).all()
            for o in objs:
                krs = db.query(KeyResult).filter(KeyResult.objective_id == o.id).all()
                for kr in krs:
                    pending = db.query(ProgressUpdate).filter(ProgressUpdate.key_result_id == kr.id, ProgressUpdate.status == "PENDING").all()
                    for p in pending:
                        sub = db.query(User).filter(User.id == p.submitted_by_id).first()
                        actions.append({
                            "type": "PROGRESS_VALIDATION", "id": p.id, "kr_id": kr.id,
                            "title": f"Validate: {kr.title}",
                            "description": f"{sub.name if sub else 'Someone'} updated '{kr.title}' to {p.new_value}{kr.unit}",
                            "actor_name": sub.name if sub else "Unknown",
                            "created_at": p.created_at.isoformat() if p.created_at else None,
                            "priority": "high",
                        })
        # Manager reviews
        pending_reviews = db.query(Review).filter(Review.reviewer_id == user_id, Review.status == "MANAGER_REVIEW_PENDING").all()
        for r in pending_reviews:
            reviewee = db.query(User).filter(User.id == r.reviewee_id).first()
            actions.append({
                "type": "MANAGER_REVIEW", "id": r.id,
                "title": f"Manager Review: {reviewee.name if reviewee else 'employee'}",
                "description": f"Review pending for {reviewee.name if reviewee else 'employee'}",
                "actor_name": reviewee.name if reviewee else "Unknown",
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "priority": "medium",
            })
        # Skip-level reviews
        skip_reviews = db.query(Review).filter(Review.skip_level_reviewer_id == user_id, Review.status == "SKIP_LEVEL_PENDING").all()
        for r in skip_reviews:
            reviewee = db.query(User).filter(User.id == r.reviewee_id).first()
            actions.append({
                "type": "SKIP_LEVEL_REVIEW", "id": r.id,
                "title": f"Skip-level: {reviewee.name if reviewee else 'employee'}",
                "description": f"Skip-level review for {reviewee.name if reviewee else 'employee'}",
                "actor_name": reviewee.name if reviewee else "Unknown",
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "priority": "medium",
            })
        # Calibration (HR_ADMIN / SUPER_ADMIN)
        if role in ("HR_ADMIN", "SUPER_ADMIN"):
            cal_reviews = db.query(Review).join(ReviewCycle).filter(ReviewCycle.org_id == org_id, Review.status == "CALIBRATION_PENDING").all()
            for r in cal_reviews:
                reviewee = db.query(User).filter(User.id == r.reviewee_id).first()
                actions.append({
                    "type": "CALIBRATION_REVIEW", "id": r.id,
                    "title": f"Calibrate: {reviewee.name if reviewee else 'employee'}",
                    "description": f"Calibrate review for {reviewee.name if reviewee else 'employee'}",
                    "actor_name": reviewee.name if reviewee else "Unknown",
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "priority": "low",
                })

    # Self reviews for current user
    self_reviews = db.query(Review).filter(Review.reviewee_id == user_id, Review.status == "SELF_REVIEW_PENDING").all()
    for r in self_reviews:
        actions.append({
            "type": "SELF_REVIEW", "id": r.id,
            "title": "Submit Self-Review",
            "description": "Submit your self-review",
            "actor_name": "You",
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "priority": "high",
        })
    return actions[:30]


def _get_dept_progress(db, org_id):
    departments = db.query(Department).filter(Department.org_id == org_id, Department.is_active == True).all()
    result = []
    for dept in departments:
        users = db.query(User).filter(User.department_id == dept.id, User.is_active == True).all()
        user_ids = [u.id for u in users]
        if not user_ids:
            # Still include department even without employees
            result.append({
                "department": dept.name, "avg_progress": 0,
                "employee_count": 0, "objective_count": 0
            })
            continue
        objs = db.query(Objective).filter(Objective.owner_id.in_(user_ids)).all()
        avg = round(sum(o.progress for o in objs) / max(len(objs), 1), 1) if objs else 0
        result.append({
            "department": dept.name, "avg_progress": avg,
            "employee_count": len(users), "objective_count": len(objs)
        })
    return result


# ===== AUDIT =====
@router.get("/audit-log")
def get_audit_log(db: Session = Depends(get_db), org_id: str = "", limit: int = 50):
    logs = db.query(AuditLog).filter(AuditLog.org_id == org_id).order_by(AuditLog.created_at.desc()).limit(limit).all()
    result = []
    for l in logs:
        u = db.query(User).filter(User.id == l.user_id).first()
        result.append({
            "id": l.id, "action": l.action, "entity_type": l.entity_type,
            "entity_id": l.entity_id, "details": l.details,
            "user_name": u.name if u else None,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        })
    return result
