from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session
from typing import Optional, List
import uuid
from server.database import get_db
from server.models import (
    Objective, KeyResult, ProgressUpdate, User, ReviewCycle,
    Team, Department, Plant, TeamMember,
)
from server.schemas import (
    ObjectiveCreate, ObjectiveAssignCreate, KeyResultCreate, ProgressUpdateCreate,
    ProgressValidation,
)
from server.okr_cascade_service import (
    OKRCascadeService,
    calculate_objective_progress,
    calculate_kr_progress,
    score_to_rating,
)

router = APIRouter(prefix="/api/okrs", tags=["okrs"])


# ── Helper: serialize objective ──────────────────────────────────────────────

def _obj_dict(obj, db):
    owner = db.query(User).filter(User.id == obj.owner_id).first()
    krs = db.query(KeyResult).filter(KeyResult.objective_id == obj.id).all()
    parent = (
        db.query(Objective).filter(Objective.id == obj.parent_id).first()
        if obj.parent_id
        else None
    )
    cycle = (
        db.query(ReviewCycle).filter(ReviewCycle.id == obj.cycle_id).first()
        if obj.cycle_id
        else None
    )

    pending_count = 0
    for kr in krs:
        pc = (
            db.query(ProgressUpdate)
            .filter(
                ProgressUpdate.key_result_id == kr.id,
                ProgressUpdate.status == "PENDING",
            )
            .count()
        )
        pending_count += pc

    assigned_by = (
        db.query(User).filter(User.id == obj.assigned_by_id).first()
        if obj.assigned_by_id
        else None
    )

    # Resolve scope names
    plant = db.query(Plant).filter(Plant.id == obj.plant_id).first() if obj.plant_id else None
    dept = db.query(Department).filter(Department.id == obj.department_id).first() if obj.department_id else None
    team = db.query(Team).filter(Team.id == obj.team_id).first() if obj.team_id else None

    # Children count
    children_count = db.query(Objective).filter(Objective.parent_id == obj.id).count()

    return {
        "id": obj.id,
        "title": obj.title,
        "description": obj.description,
        "level": obj.level,
        "status": obj.status,
        "progress": obj.progress,
        "owner_id": obj.owner_id,
        "owner_name": owner.name if owner else None,
        "assigned_by_id": obj.assigned_by_id,
        "assigned_by_name": assigned_by.name if assigned_by else None,
        "parent_id": obj.parent_id,
        "parent_title": parent.title if parent else None,
        "parent_level": parent.level if parent else None,
        "cycle_id": obj.cycle_id,
        "cycle_name": cycle.name if cycle else None,
        "plant_id": obj.plant_id,
        "plant_name": plant.name if plant else None,
        "department_id": obj.department_id,
        "department_name": dept.name if dept else None,
        "team_id": obj.team_id,
        "team_name": team.name if team else None,
        "pending_validations": pending_count,
        "children_count": children_count,
        "created_at": obj.created_at.isoformat() if obj.created_at else None,
        "key_results": [_kr_dict(kr, db) for kr in krs],
    }


def _kr_dict(kr, db):
    pct = calculate_kr_progress(kr)
    # Get pending updates count
    pending = (
        db.query(ProgressUpdate)
        .filter(
            ProgressUpdate.key_result_id == kr.id,
            ProgressUpdate.status == "PENDING",
        )
        .count()
    )
    return {
        "id": kr.id,
        "title": kr.title,
        "target_value": kr.target_value,
        "current_value": kr.current_value,
        "unit": kr.unit,
        "weight": kr.weight,
        "status": kr.status,
        "progress_pct": round(pct, 1),
        "pending_updates": pending,
    }


# ══════════════════════════════════════════════════════════════════════════════
# LIST / FILTER OBJECTIVES
# ══════════════════════════════════════════════════════════════════════════════

@router.get("")
def list_objectives(
    db: Session = Depends(get_db),
    org_id: str = "",
    owner_id: str = "",
    level: str = "",
    cycle_id: str = "",
    plant_id: str = "",
    department_id: str = "",
    team_id: str = "",
    parent_id: str = "",
):
    q = db.query(Objective).filter(Objective.org_id == org_id)
    if owner_id:
        q = q.filter(Objective.owner_id == owner_id)
    if level:
        # Handle "employee" as "INDIVIDUAL"
        resolved_level = level.upper()
        if resolved_level == "EMPLOYEE":
            resolved_level = "INDIVIDUAL"
        q = q.filter(Objective.level == resolved_level)
    if cycle_id:
        q = q.filter(Objective.cycle_id == cycle_id)
    if plant_id:
        level_upper = (level or "").upper()
        if level_upper == "EMPLOYEE":
            level_upper = "INDIVIDUAL"
        # When browsing all OKRs or org/plant levels, keep company-wide (CEO) OKRs visible
        # alongside plant-scoped rows. For dept/team/individual tabs, scope strictly by plant.
        if not level or level_upper in ("ORGANIZATION", "PLANT"):
            q = q.filter(
                or_(
                    Objective.plant_id == plant_id,
                    Objective.level == "ORGANIZATION",
                )
            )
        else:
            q = q.filter(Objective.plant_id == plant_id)
    if department_id:
        q = q.filter(Objective.department_id == department_id)
    if team_id:
        q = q.filter(Objective.team_id == team_id)
    if parent_id:
        q = q.filter(Objective.parent_id == parent_id)

    objs = q.order_by(Objective.created_at.desc()).all()
    return [_obj_dict(o, db) for o in objs]


# ══════════════════════════════════════════════════════════════════════════════
# MY OKRS - filtered by current user
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/my")
def my_objectives(
    db: Session = Depends(get_db),
    org_id: str = "",
    user_id: str = "",
):
    """Get OKRs owned by or assigned to the current user."""
    objs = (
        db.query(Objective)
        .filter(
            Objective.org_id == org_id,
            or_(
                Objective.owner_id == user_id,
                Objective.assigned_by_id == user_id,
            ),
        )
        .order_by(Objective.created_at.desc())
        .all()
    )
    return [_obj_dict(o, db) for o in objs]


# ══════════════════════════════════════════════════════════════════════════════
# CREATE OBJECTIVE (with role-based validation)
# ══════════════════════════════════════════════════════════════════════════════

@router.post("")
def create_objective(
    req: ObjectiveCreate,
    db: Session = Depends(get_db),
    org_id: str = "",
    user_id: str = "",
    role: str = "",
):
    cascade = OKRCascadeService(db)

    # Validate role can create at this level
    if role and not cascade.can_create_at_level(role, req.level.upper()):
        raise HTTPException(
            403,
            f"Role {role} cannot create {req.level} OKRs. "
            f"Allowed levels: {cascade.ROLE_CREATE_LEVELS.get(role, [])}"
        )

    # Validate parent exists if specified
    if req.parent_id:
        parent = db.query(Objective).filter(Objective.id == req.parent_id).first()
        if not parent:
            raise HTTPException(404, "Parent objective not found")

    # Auto-populate scope from assignment when not provided.
    # For INDIVIDUAL OKRs assigned to someone else, use the owner's plant/dept/team.
    creator = db.query(User).filter(User.id == user_id).first()
    effective_owner_id = req.owner_id or user_id
    scope_user = db.query(User).filter(User.id == effective_owner_id).first() or creator

    plant_id = req.plant_id
    department_id = req.department_id
    team_id = req.team_id

    if scope_user and not plant_id and req.level.upper() not in ("ORGANIZATION",):
        plant_id = scope_user.plant_id
    if scope_user and not department_id and req.level.upper() in ("DEPARTMENT", "TEAM", "INDIVIDUAL"):
        department_id = scope_user.department_id
    if scope_user and not team_id and req.level.upper() in ("TEAM", "INDIVIDUAL"):
        team_id = scope_user.team_id
    # Team roster may use team_members while User.team_id is unset
    if (
        scope_user
        and not team_id
        and req.level.upper() == "INDIVIDUAL"
    ):
        tm = (
            db.query(TeamMember)
            .filter(
                TeamMember.user_id == scope_user.id,
                TeamMember.is_active == True,
            )
            .first()
        )
        if tm:
            team_id = tm.team_id

    obj = Objective(
        org_id=org_id,
        owner_id=req.owner_id or user_id,
        assigned_by_id=user_id if req.owner_id and req.owner_id != user_id else None,
        parent_id=req.parent_id,
        cycle_id=req.cycle_id,
        title=req.title,
        description=req.description,
        level=req.level.upper(),
        plant_id=plant_id,
        department_id=department_id,
        team_id=team_id,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return _obj_dict(obj, db)


# ══════════════════════════════════════════════════════════════════════════════
# ASSIGN OBJECTIVE TO EMPLOYEE (Manager/Admin Assignment)
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/assign")
def assign_okr_to_employee(
    req: ObjectiveAssignCreate,
    db: Session = Depends(get_db),
    org_id: str = "",
    user_id: str = "",
    role: str = "",
):
    """
    Manager/Admin/CEO assigns an OKR to an employee.
    - Only users with MANAGER, DEPT_HEAD, PLANT_HEAD, or higher roles can assign
    - Can only assign to users they have authority over
    - Creates INDIVIDUAL-level OKR for the target employee
    """
    # Verify actor has permission to assign
    allowed_roles = ["CEO", "SUPER_ADMIN", "PLANT_HEAD", "DEPT_HEAD", "MANAGER"]
    if role not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail=f"Role {role} cannot assign OKRs. Allowed: {', '.join(allowed_roles)}"
        )
    
    # Get the target employee
    target_employee = db.query(User).filter(User.id == req.employee_user_id).first()
    if not target_employee:
        raise HTTPException(status_code=404, detail="Target employee not found")
    
    # Get the assigning manager
    manager = db.query(User).filter(User.id == user_id).first()
    if not manager:
        raise HTTPException(status_code=404, detail="Manager not found")
    
    # Verify they're in the same organization
    if target_employee.org_id != manager.org_id:
        raise HTTPException(status_code=403, detail="Employee not in your organization")
    
    # Role-based scope validation
    if role == "DEPT_HEAD":
        # DEPT_HEAD can only assign to employees in their department
        if target_employee.department_id != manager.department_id:
            raise HTTPException(
                status_code=403,
                detail="Can only assign OKRs to employees in your department"
            )
    elif role == "MANAGER":
        # MANAGER can only assign to employees in their team/department
        if target_employee.team_id and target_employee.team_id != manager.team_id:
            raise HTTPException(
                status_code=403,
                detail="Can only assign OKRs to employees in your team"
            )
        if not target_employee.team_id and target_employee.department_id != manager.department_id:
            raise HTTPException(
                status_code=403,
                detail="Can only assign OKRs to employees in your department"
            )
    # CEO and SUPER_ADMIN can assign to anyone
    
    # Validate parent exists if specified
    if req.parent_id:
        parent = db.query(Objective).filter(Objective.id == req.parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent objective not found")
    
    # Use employee's location/dept/team for scoping
    plant_id = req.plant_id or target_employee.plant_id
    department_id = req.department_id or target_employee.department_id
    team_id = req.team_id or target_employee.team_id
    
    # If team_id not in user record, try team_members
    if not team_id:
        tm = db.query(TeamMember).filter(
            TeamMember.user_id == target_employee.id,
            TeamMember.is_active == True
        ).first()
        if tm:
            team_id = tm.team_id
    
    # Create the OKR as INDIVIDUAL level
    obj = Objective(
        id=str(uuid.uuid4()),
        org_id=org_id,
        owner_id=req.employee_user_id,  # The OKR belongs to the employee
        assigned_by_id=user_id,  # Assigned by this manager
        parent_id=req.parent_id,
        cycle_id=req.cycle_id,
        title=req.title,
        description=req.description,
        level="INDIVIDUAL",  # Always INDIVIDUAL for assignments
        plant_id=plant_id,
        department_id=department_id,
        team_id=team_id,
    )
    db.add(obj)
    db.flush()
    
    # Add key results if provided
    if req.key_results:
        for kr_data in req.key_results:
            kr = KeyResult(
                id=str(uuid.uuid4()),
                objective_id=obj.id,
                title=kr_data.title,
                target_value=kr_data.target_value or 100.0,
                unit=kr_data.unit or "%",
                weight=kr_data.weight or 1.0,
            )
            db.add(kr)
    
    db.commit()
    db.refresh(obj)
    return _obj_dict(obj, db)


# ══════════════════════════════════════════════════════════════════════════════
# ALIGNMENT TREE
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/alignment-tree")
def get_alignment_tree(
    db: Session = Depends(get_db),
    org_id: str = "",
    plant_id: str = "",
):
    cascade = OKRCascadeService(db)
    return cascade.get_cascade_tree(org_id, plant_id or None)


# ══════════════════════════════════════════════════════════════════════════════
# PROGRESS SUMMARY (dashboard)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/progress-summary")
def get_progress_summary(
    db: Session = Depends(get_db),
    org_id: str = "",
    plant_id: str = "",
):
    cascade = OKRCascadeService(db)
    return cascade.get_progress_summary(org_id, plant_id or None)


# ══════════════════════════════════════════════════════════════════════════════
# ALLOWED LEVELS FOR ROLE
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/allowed-levels")
def get_allowed_levels(role: str = ""):
    """Return which OKR levels the given role can create."""
    levels = OKRCascadeService.ROLE_CREATE_LEVELS.get(role, [])
    return {"role": role, "allowed_levels": levels}


# ══════════════════════════════════════════════════════════════════════════════
# PARENT OPTIONS - get possible parent objectives for cascading
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/parent-options")
def get_parent_options(
    level: str = "",
    db: Session = Depends(get_db),
    org_id: str = "",
    plant_id: str = "",
    department_id: str = "",
):
    """
    Get possible parent objectives for a given level.
    - PLANT OKR → parent can be ORGANIZATION
    - DEPARTMENT OKR → parent can be PLANT
    - TEAM OKR → parent can be DEPARTMENT
    - INDIVIDUAL OKR → parent can be TEAM or DEPARTMENT
    """
    level = level.upper()
    parent_levels = {
        "PLANT": ["ORGANIZATION"],
        "DEPARTMENT": ["PLANT"],
        "TEAM": ["DEPARTMENT"],
        "INDIVIDUAL": ["TEAM", "DEPARTMENT"],
    }

    allowed_parent_levels = parent_levels.get(level, [])
    if not allowed_parent_levels:
        return []

    q = db.query(Objective).filter(
        Objective.org_id == org_id,
        Objective.level.in_(allowed_parent_levels),
    )

    # Scope filtering
    if plant_id:
        from sqlalchemy import or_
        q = q.filter(
            or_(
                Objective.plant_id == plant_id,
                Objective.level == "ORGANIZATION",
            )
        )
    if department_id and "DEPARTMENT" in allowed_parent_levels:
        q = q.filter(Objective.department_id == department_id)

    parents = q.order_by(Objective.level, Objective.title).all()
    return [
        {
            "id": p.id,
            "title": p.title,
            "level": p.level,
            "progress": p.progress,
        }
        for p in parents
    ]


# ══════════════════════════════════════════════════════════════════════════════
# GET / UPDATE / DELETE OBJECTIVE
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/{obj_id}")
def get_objective(obj_id: str, db: Session = Depends(get_db)):
    obj = db.query(Objective).filter(Objective.id == obj_id).first()
    if not obj:
        raise HTTPException(404, "Objective not found")
    return _obj_dict(obj, db)


@router.put("/{obj_id}")
def update_objective(obj_id: str, req: ObjectiveCreate, db: Session = Depends(get_db)):
    obj = db.query(Objective).filter(Objective.id == obj_id).first()
    if not obj:
        raise HTTPException(404, "Objective not found")
    obj.title = req.title
    if req.description is not None:
        obj.description = req.description
    if req.level:
        obj.level = req.level.upper()
    if req.parent_id is not None:
        obj.parent_id = req.parent_id
    if req.plant_id is not None:
        obj.plant_id = req.plant_id
    if req.department_id is not None:
        obj.department_id = req.department_id
    if req.team_id is not None:
        obj.team_id = req.team_id
    db.commit()
    db.refresh(obj)
    return _obj_dict(obj, db)


@router.delete("/{obj_id}")
def delete_objective(obj_id: str, db: Session = Depends(get_db)):
    obj = db.query(Objective).filter(Objective.id == obj_id).first()
    if not obj:
        raise HTTPException(404)
    # Also delete children recursively
    _delete_children(obj_id, db)
    db.delete(obj)
    db.commit()
    return {"status": "deleted"}


def _delete_children(parent_id: str, db: Session):
    """Recursively delete child objectives."""
    children = db.query(Objective).filter(Objective.parent_id == parent_id).all()
    for child in children:
        _delete_children(child.id, db)
        db.delete(child)


# ══════════════════════════════════════════════════════════════════════════════
# KEY RESULTS CRUD
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/{obj_id}/key-results")
def add_key_result(obj_id: str, req: KeyResultCreate, db: Session = Depends(get_db)):
    obj = db.query(Objective).filter(Objective.id == obj_id).first()
    if not obj:
        raise HTTPException(404, "Objective not found")
    kr = KeyResult(
        objective_id=obj_id,
        title=req.title,
        target_value=req.target_value,
        unit=req.unit,
        weight=req.weight,
    )
    db.add(kr)
    db.commit()
    db.refresh(kr)
    _recalc_and_cascade(obj_id, db)
    return _kr_dict(kr, db)


@router.put("/key-results/{kr_id}")
def update_key_result(kr_id: str, req: KeyResultCreate, db: Session = Depends(get_db)):
    kr = db.query(KeyResult).filter(KeyResult.id == kr_id).first()
    if not kr:
        raise HTTPException(404)
    kr.title = req.title
    kr.target_value = req.target_value
    kr.unit = req.unit
    kr.weight = req.weight
    db.commit()
    db.refresh(kr)
    _recalc_and_cascade(kr.objective_id, db)
    return _kr_dict(kr, db)


@router.delete("/key-results/{kr_id}")
def delete_key_result(kr_id: str, db: Session = Depends(get_db)):
    kr = db.query(KeyResult).filter(KeyResult.id == kr_id).first()
    if not kr:
        raise HTTPException(404)
    obj_id = kr.objective_id
    db.delete(kr)
    db.commit()
    _recalc_and_cascade(obj_id, db)
    return {"status": "deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# PROGRESS SUBMISSION + VALIDATION (with cascade propagation)
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/key-results/{kr_id}/progress")
def submit_progress(
    kr_id: str,
    req: ProgressUpdateCreate,
    db: Session = Depends(get_db),
    user_id: str = "",
):
    kr = db.query(KeyResult).filter(KeyResult.id == kr_id).first()
    if not kr:
        raise HTTPException(404, "Key Result not found")

    update = ProgressUpdate(
        key_result_id=kr_id,
        submitted_by_id=user_id,
        previous_value=kr.current_value,
        new_value=req.new_value,
        notes=req.notes,
        blockers=req.blockers,
        evidence_url=req.evidence_url,
        status="PENDING",
    )
    db.add(update)

    # Update KR value immediately (can be reverted if rejected)
    kr.current_value = req.new_value
    pct = min((kr.current_value / kr.target_value * 100) if kr.target_value > 0 else 0, 100)
    kr.status = "COMPLETED" if pct >= 100 else "IN_PROGRESS" if pct > 0 else "NOT_STARTED"
    db.commit()

    # Recalculate and cascade
    _recalc_and_cascade(kr.objective_id, db)

    return {
        "id": update.id,
        "status": update.status,
        "new_value": req.new_value,
        "progress_pct": round(pct, 1),
    }


@router.put("/progress/{update_id}/validate")
def validate_progress(
    update_id: str,
    req: ProgressValidation,
    db: Session = Depends(get_db),
    user_id: str = "",
):
    update = db.query(ProgressUpdate).filter(ProgressUpdate.id == update_id).first()
    if not update:
        raise HTTPException(404)

    update.status = req.status
    update.validated_by_id = user_id
    update.validation_notes = req.validation_notes
    update.validated_at = __import__('datetime').datetime.utcnow()

    if req.status == "REJECTED":
        # Revert the KR value
        kr = db.query(KeyResult).filter(KeyResult.id == update.key_result_id).first()
        if kr:
            kr.current_value = update.previous_value
            pct = min((kr.current_value / kr.target_value * 100) if kr.target_value > 0 else 0, 100)
            kr.status = "COMPLETED" if pct >= 100 else "IN_PROGRESS" if pct > 0 else "NOT_STARTED"
            db.commit()
            _recalc_and_cascade(kr.objective_id, db)
    elif req.status == "APPROVED":
        # Progress stands, cascade upward
        kr = db.query(KeyResult).filter(KeyResult.id == update.key_result_id).first()
        if kr:
            db.commit()
            _recalc_and_cascade(kr.objective_id, db)
    else:
        db.commit()

    return {"status": update.status}


@router.get("/key-results/{kr_id}/progress-history")
def get_progress_history(kr_id: str, db: Session = Depends(get_db)):
    updates = (
        db.query(ProgressUpdate)
        .filter(ProgressUpdate.key_result_id == kr_id)
        .order_by(ProgressUpdate.created_at.desc())
        .all()
    )
    result = []
    for u in updates:
        submitter = db.query(User).filter(User.id == u.submitted_by_id).first()
        validator = (
            db.query(User).filter(User.id == u.validated_by_id).first()
            if u.validated_by_id
            else None
        )
        result.append({
            "id": u.id,
            "previous_value": u.previous_value,
            "new_value": u.new_value,
            "notes": u.notes,
            "blockers": u.blockers,
            "status": u.status,
            "validation_notes": u.validation_notes,
            "submitted_by": submitter.name if submitter else None,
            "submitted_by_id": u.submitted_by_id,
            "validated_by": validator.name if validator else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "validated_at": u.validated_at.isoformat() if u.validated_at else None,
        })
    return result


# ══════════════════════════════════════════════════════════════════════════════
# PENDING VALIDATIONS (for managers)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/pending-validations")
def get_pending_validations(
    db: Session = Depends(get_db),
    org_id: str = "",
    user_id: str = "",
    role: str = "",
    plant_id: str = "",
):
    """Get all pending progress validations that the current user should review."""
    from sqlalchemy import and_

    # Get objectives the user manages (directly assigned or in their scope)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return []

    # Find OKRs in scope
    q = db.query(Objective).filter(Objective.org_id == org_id)

    if role in ("SUPER_ADMIN", "CEO"):
        pass  # See all
    elif role in ("PLANT_HEAD", "PLANT_MANAGER", "VP_OPERATIONS"):
        if user.plant_id:
            q = q.filter(Objective.plant_id == user.plant_id)
    elif role == "DEPT_HEAD":
        if user.department_id:
            q = q.filter(Objective.department_id == user.department_id)
    elif role in ("MANAGER", "TEAM_LEAD"):
        if user.team_id:
            q = q.filter(Objective.team_id == user.team_id)
    else:
        # Regular employees don't validate
        return []

    if plant_id:
        q = q.filter(Objective.plant_id == plant_id)

    obj_ids = [o.id for o in q.all()]
    if not obj_ids:
        return []

    # Get KRs for those objectives
    kr_ids = [
        kr.id
        for kr in db.query(KeyResult)
        .filter(KeyResult.objective_id.in_(obj_ids))
        .all()
    ]
    if not kr_ids:
        return []

    # Get pending updates
    pending = (
        db.query(ProgressUpdate)
        .filter(
            ProgressUpdate.key_result_id.in_(kr_ids),
            ProgressUpdate.status == "PENDING",
        )
        .order_by(ProgressUpdate.created_at.desc())
        .all()
    )

    result = []
    for p in pending:
        kr = db.query(KeyResult).filter(KeyResult.id == p.key_result_id).first()
        obj = db.query(Objective).filter(Objective.id == kr.objective_id).first() if kr else None
        submitter = db.query(User).filter(User.id == p.submitted_by_id).first()
        result.append({
            "id": p.id,
            "key_result_id": p.key_result_id,
            "key_result_title": kr.title if kr else None,
            "objective_id": obj.id if obj else None,
            "objective_title": obj.title if obj else None,
            "objective_level": obj.level if obj else None,
            "previous_value": p.previous_value,
            "new_value": p.new_value,
            "notes": p.notes,
            "submitted_by": submitter.name if submitter else None,
            "submitted_by_id": p.submitted_by_id,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })

    return result


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _recalc_and_cascade(obj_id: str, db: Session):
    """Recalculate objective progress and cascade upward."""
    cascade = OKRCascadeService(db)
    cascade.propagate_progress_upward(obj_id)
