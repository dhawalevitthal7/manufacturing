from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
import uuid
from server.database import get_db
from server.models import (
    Objective, KeyResult, ProgressUpdate, ProgressSubmission, User, ReviewCycle, KRIngestSource,
    Team, Department, Plant, TeamMember, Cycle,
)
from server.auth import require_super_admin, get_jwt_payload
from server.schemas import (
    ObjectiveCreate,
    ObjectiveAssignCreate,
    ObjectiveFunctionalParentPatch,
    KeyResultCreate,
    KRIngestSourceConfigure,
    ProgressUpdateCreate,
    ProgressValidation,
)
from server.services.objective_functional_validation import (
    reject_functional_parent_obj_id_in_create_body,
    validate_functional_parent_objective,
)
from server.services.okr_progress_permissions import (
    actor_may_assign_okr_to_user,
    can_submit_okr_progress,
    resolve_team_okr_owner_id,
)
from server.okr_cascade_service import (
    OKRCascadeService,
    calculate_objective_progress,
    calculate_kr_progress,
    score_to_rating,
)
from server.roles import allowed_objective_levels_for, normalize_role, SystemRole
from server.services.okr_visibility_service import (
    apply_okr_visibility_filter,
    apply_optional_scope_narrowing,
    get_user_okr_scope,
    visibility_scope_response,
    get_functional_okrs,
    get_function_structure,
)
from server.services.function_area_service import (
    FUNCTION_AREAS,
    FUNCTION_AREA_LABELS,
    normalize_function_area,
    resolve_function_area_on_create,
    inherit_function_area_from_parent,
)
from server.services.okr_lifecycle_service import (
    OKR_STATUS_ACTIVE,
    OKR_STATUS_DRAFT,
    activate_okr,
    admin_approve_okr,
    admin_reject_okr,
    assert_okr_allows_kr_edit,
    assert_okr_allows_progress,
    can_user_draft_objective,
    ceo_may_self_publish,
    enqueue_okr_creation_approval,
    publish_ceo_okr,
    reject_okr,
    submit_for_approval,
)
from server.services.dual_approval_service import (
    SUBJECT_OKR_CREATION,
    chain_status,
    pending_subject_ids_for_approver,
)

router = APIRouter(prefix="/api/okrs", tags=["okrs"])


def _resolve_cycle_id(db: Session, org_id: str, cycle_id: Optional[str]) -> Optional[str]:
    """Use explicit cycle_id when provided; otherwise attach the org's active/frozen cycle."""
    if cycle_id:
        cycle = db.query(Cycle).filter(Cycle.id == cycle_id, Cycle.org_id == org_id).first()
        if not cycle:
            raise HTTPException(404, "Cycle not found")
        return cycle_id
    active = (
        db.query(Cycle)
        .filter(
            Cycle.org_id == org_id,
            Cycle.status.in_(("ACTIVE", "FROZEN")),
        )
        .order_by(Cycle.start_date.desc())
        .first()
    )
    return active.id if active else None


def _apply_objective_period_filter(
    q,
    *,
    year: Optional[int] = None,
    quarter: Optional[str] = None,
    cycle_id: Optional[str] = None,
):
    """Filter OKRs by explicit year/quarter; fall back to cycle_id when period not set."""
    if year is not None:
        q = q.filter(Objective.year == year)
    if quarter:
        q = q.filter(Objective.quarter == quarter.upper())
    elif cycle_id:
        q = q.filter(Objective.cycle_id == cycle_id)
    return q


def _derive_quarter_year_from_cycle(db: Session, cycle_id: Optional[str]) -> tuple[Optional[str], Optional[int]]:
    """Derive objective quarter/year from associated cycle start date."""
    if not cycle_id:
        return None, None
    cycle = db.query(Cycle).filter(Cycle.id == cycle_id).first()
    if not cycle:
        return None, None
    try:
        start_dt = datetime.fromisoformat(cycle.start_date)
    except ValueError:
        return None, None
    quarter = f"Q{((start_dt.month - 1) // 3) + 1}"
    return quarter, start_dt.year


def _lifecycle_error(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


# ── Helper: serialize objective ──────────────────────────────────────────────

def _obj_dict(obj, db):
    owner = db.query(User).filter(User.id == obj.owner_id).first()
    krs = db.query(KeyResult).filter(KeyResult.objective_id == obj.id).all()
    parent = (
        db.query(Objective).filter(Objective.id == obj.parent_id).first()
        if obj.parent_id
        else None
    )
    functional_parent = (
        db.query(Objective).filter(Objective.id == obj.functional_parent_obj_id).first()
        if obj.functional_parent_obj_id
        else None
    )
    cycle = (
        db.query(ReviewCycle).filter(ReviewCycle.id == obj.cycle_id).first()
        if obj.cycle_id
        else None
    )

    pending_count = 0
    for kr in krs:
        pending_updates = (
            db.query(ProgressUpdate)
            .filter(
                ProgressUpdate.key_result_id == kr.id,
                ProgressUpdate.status == "PENDING",
            )
            .count()
        )
        pending_submissions = (
            db.query(ProgressSubmission.id)
            .filter(
                ProgressSubmission.key_result_id == kr.id,
                ProgressSubmission.status == "PENDING",
            )
            .count()
        )
        pending_count += pending_updates + pending_submissions

    assigned_by = (
        db.query(User).filter(User.id == obj.assigned_by_id).first()
        if obj.assigned_by_id
        else None
    )
    pending_approver = (
        db.query(User).filter(User.id == obj.pending_approver_user_id).first()
        if obj.pending_approver_user_id
        else None
    )
    creation_approved_by = (
        db.query(User).filter(User.id == obj.creation_approved_by_id).first()
        if obj.creation_approved_by_id
        else None
    )

    # Resolve scope names
    from server.models import OrgNode

    region = (
        db.query(OrgNode).filter(OrgNode.id == obj.region_id).first()
        if obj.region_id
        else None
    )
    plant = db.query(Plant).filter(Plant.id == obj.plant_id).first() if obj.plant_id else None
    dept = db.query(Department).filter(Department.id == obj.department_id).first() if obj.department_id else None
    team = db.query(Team).filter(Team.id == obj.team_id).first() if obj.team_id else None

    # Children count
    children_count = db.query(Objective).filter(Objective.parent_id == obj.id).count()

    payload = {
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
        "functional_parent_obj_id": obj.functional_parent_obj_id,
        "parent_title": parent.title if parent else None,
        "parent_level": parent.level if parent else None,
        "functional_parent_title": functional_parent.title if functional_parent else None,
        "functional_parent_level": functional_parent.level if functional_parent else None,
        "cycle_id": obj.cycle_id,
        "cycle_name": cycle.name if cycle else None,
        "region_id": obj.region_id,
        "region_name": region.name if region else None,
        "plant_id": obj.plant_id,
        "plant_name": plant.name if plant else None,
        "department_id": obj.department_id,
        "department_name": dept.name if dept else None,
        "team_id": obj.team_id,
        "team_name": team.name if team else None,
        "pending_validations": pending_count,
        "children_count": children_count,
        "creation_primary_approved_at": obj.creation_primary_approved_at.isoformat() if obj.creation_primary_approved_at else None,
        "creation_functional_approved_at": obj.creation_functional_approved_at.isoformat() if obj.creation_functional_approved_at else None,
        "okr_status": getattr(obj, "okr_status", None) or OKR_STATUS_DRAFT,
        "creation_approval_status": obj.creation_approval_status,
        "rejection_reason": obj.rejection_reason,
        "pending_approver_user_id": obj.pending_approver_user_id,
        "pending_approver_role": obj.pending_approver_role,
        "pending_approver_name": pending_approver.name if pending_approver else None,
        "creation_approved_by_id": obj.creation_approved_by_id,
        "creation_approved_by_name": creation_approved_by.name if creation_approved_by else None,
        "creation_approved_at": obj.creation_approved_at.isoformat() if obj.creation_approved_at else None,
        "kr_baseline_locked": bool(getattr(obj, "kr_baseline_locked", False)),
        "function_area": obj.function_area,
        "function_area_label": FUNCTION_AREA_LABELS.get(obj.function_area or "", None),
        "function_node_id": obj.function_node_id,
        "can_publish_as_ceo": bool(owner and ceo_may_self_publish(obj, owner)),
        "ai_generated": bool(getattr(obj, "ai_generated", False)),
        "ai_confidence": getattr(obj, "ai_confidence", None),
        "ai_generation_reason": getattr(obj, "ai_generation_reason", None),
        "ai_generated_from_objective_id": getattr(obj, "ai_generated_from_objective_id", None),
        "cascade_generation_status": getattr(obj, "cascade_generation_status", None),
        "review_status": getattr(obj, "review_status", None),
        "submitted_for_parent_approval_at": (
            obj.submitted_for_parent_approval_at.isoformat()
            if getattr(obj, "submitted_for_parent_approval_at", None)
            else None
        ),
        "created_at": obj.created_at.isoformat() if obj.created_at else None,
        "key_results": [_kr_dict(kr, db) for kr in krs],
    }
    if (obj.okr_status or "").upper() in ("PENDING_APPROVAL", "DRAFT", "REJECTED", "ACTIVE"):
        payload["approval_chain_status"] = chain_status(db, SUBJECT_OKR_CREATION, obj.id)
    return payload


def _kr_dict(kr, db):
    pct = calculate_kr_progress(kr)
    # Get pending updates count
    pending_updates = (
        db.query(ProgressUpdate)
        .filter(
            ProgressUpdate.key_result_id == kr.id,
            ProgressUpdate.status == "PENDING",
        )
        .count()
    )
    pending_submissions = (
        db.query(ProgressSubmission.id)
        .filter(
            ProgressSubmission.key_result_id == kr.id,
            ProgressSubmission.status == "PENDING",
        )
        .count()
    )
    pending = pending_updates + pending_submissions
    pending_submitted_value = None
    pending_submitted_note = None
    if pending > 0:
        latest_sub = (
            db.query(ProgressSubmission)
            .filter(
                ProgressSubmission.key_result_id == kr.id,
                ProgressSubmission.status == "PENDING",
            )
            .order_by(ProgressSubmission.created_at.desc())
            .first()
        )
        if latest_sub:
            pending_submitted_value = latest_sub.employee_value
            pending_submitted_note = latest_sub.employee_note
        else:
            latest_upd = (
                db.query(ProgressUpdate)
                .filter(
                    ProgressUpdate.key_result_id == kr.id,
                    ProgressUpdate.status == "PENDING",
                )
                .order_by(ProgressUpdate.created_at.desc())
                .first()
            )
            if latest_upd:
                pending_submitted_value = latest_upd.new_value
                pending_submitted_note = latest_upd.notes
    ingest = db.query(KRIngestSource).filter(KRIngestSource.key_result_id == kr.id).first()
    ingest_info = None
    if ingest:
        from server.services.kr_ingest_service import ingest_source_dict

        ingest_info = ingest_source_dict(ingest)
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
        "pending_submitted_value": pending_submitted_value,
        "pending_submitted_note": pending_submitted_note,
        "ingest_source": ingest_info,
        "auto_ingest_active": bool(ingest and ingest.is_active),
    }


# ══════════════════════════════════════════════════════════════════════════════
# LIST / FILTER OBJECTIVES
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/visibility-scope")
def get_visibility_scope(
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    """Role-based OKR visibility metadata for UI tabs and plant filter."""
    user_id = payload.get("sub", "")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    return visibility_scope_response(user, db)


@router.get("")
def list_objectives(
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
    owner_id: str = Query(""),
    level: str = Query(""),
    cycle_id: str = Query(""),
    year: Optional[int] = Query(None),
    quarter: str = Query(""),
    region_id: str = Query(""),
    plant_id: str = Query(""),
    department_id: str = Query(""),
    team_id: str = Query(""),
    parent_id: str = Query(""),
    function_area: str = Query(""),
):
    org_id = payload.get("org_id", "")
    user_id = payload.get("sub", "")
    if not org_id:
        raise HTTPException(400, "org_id not found in token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    q = db.query(Objective).filter(Objective.org_id == org_id)
    q = apply_okr_visibility_filter(q, user, db, org_id)

    okr_scope = get_user_okr_scope(user, db)
    q = apply_optional_scope_narrowing(
        q,
        okr_scope,
        plant_id=plant_id or None,
        department_id=department_id or None,
        team_id=team_id or None,
        db=db,
        org_id=org_id,
    )

    if owner_id:
        q = q.filter(Objective.owner_id == owner_id)
    if level:
        resolved_level = level.upper()
        if resolved_level == "EMPLOYEE":
            resolved_level = "INDIVIDUAL"
        q = q.filter(Objective.level == resolved_level)
    q = _apply_objective_period_filter(
        q,
        year=year,
        quarter=quarter or None,
        cycle_id=cycle_id or None,
    )
    if parent_id:
        q = q.filter(Objective.parent_id == parent_id)
    if function_area:
        fa = normalize_function_area(function_area)
        if fa:
            q = q.filter(Objective.function_area == fa)

    objs = q.order_by(Objective.created_at.desc()).all()
    return [_obj_dict(o, db) for o in objs]


# ══════════════════════════════════════════════════════════════════════════════
# MY OKRS - filtered by current user
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/my")
def my_objectives(
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    """Get OKRs owned by or assigned to the current user."""
    org_id = payload.get("org_id", "")
    user_id = payload.get("sub", "")
    
    if not org_id or not user_id:
        raise HTTPException(400, "org_id or user_id not found in token")
    
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
    body: dict = Body(...),
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    """Create an objective as DRAFT (Phase 6). Rejects ``functional_parent_obj_id`` in JSON (use PATCH)."""
    org_id = payload.get("org_id", "")
    user_id = payload.get("sub", "")
    role = payload.get("role", "")
    
    if not org_id or not user_id:
        raise HTTPException(400, "org_id or user_id not found in token")
    
    reject_functional_parent_obj_id_in_create_body(body)
    req = ObjectiveCreate.model_validate(body)

    creator = db.query(User).filter(User.id == user_id).first()
    if not creator:
        raise HTTPException(404, "User not found")

    plant_id = req.plant_id
    department_id = req.department_id
    team_id = req.team_id
    region_id = req.region_id
    scope_user = db.query(User).filter(User.id == (req.owner_id or user_id)).first() or creator

    if scope_user and not plant_id and req.level.upper() not in ("ORGANIZATION", "REGION"):
        plant_id = scope_user.plant_id
    if scope_user and not department_id and req.level.upper() in ("DEPARTMENT", "TEAM", "INDIVIDUAL"):
        department_id = scope_user.department_id
    if scope_user and not team_id and req.level.upper() in ("TEAM", "INDIVIDUAL"):
        team_id = scope_user.team_id
    if scope_user and not team_id and req.level.upper() == "INDIVIDUAL":
        tm = (
            db.query(TeamMember)
            .filter(TeamMember.user_id == scope_user.id, TeamMember.is_active == True)
            .first()
        )
        if tm:
            team_id = tm.team_id

    effective_owner_id = req.owner_id or user_id
    if req.level.upper() == "TEAM":
        if not team_id:
            raise HTTPException(400, "Team OKRs require a team to be selected")
        effective_owner_id = resolve_team_okr_owner_id(team_id, creator, req.owner_id, db)
    elif req.level.upper() == "INDIVIDUAL" and not req.owner_id:
        raise HTTPException(
            400,
            "Individual OKRs must be assigned to an employee; select Assign To",
        )

    owner_user = db.query(User).filter(User.id == effective_owner_id).first()
    if not owner_user:
        raise HTTPException(404, "OKR owner not found")
    if effective_owner_id != user_id:
        ok_assign, assign_reason = actor_may_assign_okr_to_user(
            creator, owner_user, req.level.upper(), db
        )
        if not ok_assign:
            raise HTTPException(403, assign_reason)

    can_draft, draft_reason = can_user_draft_objective(
        creator, req.level.upper(), effective_owner_id
    )
    if not can_draft:
        raise HTTPException(403, draft_reason)

    # Validate parent exists if specified
    if req.parent_id:
        parent = db.query(Objective).filter(Objective.id == req.parent_id).first()
        if not parent:
            raise HTTPException(404, "Parent objective not found")

    scope_user = owner_user or creator

    # Auto-populate region_id for REGION level OKRs from user's org_node if it's a region
    if not region_id and req.level.upper() in ("REGION", "PLANT", "DEPARTMENT"):
        if scope_user and scope_user.org_node_id:
            from server.models import OrgNode
            org_node = db.query(OrgNode).filter(OrgNode.id == scope_user.org_node_id).first()
            if org_node and org_node.node_type == "REGION":
                region_id = org_node.id

    if scope_user and not plant_id and req.level.upper() not in ("ORGANIZATION", "REGION"):
        plant_id = scope_user.plant_id
    if scope_user and not department_id and req.level.upper() in ("DEPARTMENT", "TEAM", "INDIVIDUAL"):
        department_id = scope_user.department_id
    if scope_user and not team_id and req.level.upper() in ("TEAM", "INDIVIDUAL"):
        team_id = scope_user.team_id
    if scope_user and not team_id and req.level.upper() == "INDIVIDUAL":
        tm = (
            db.query(TeamMember)
            .filter(TeamMember.user_id == scope_user.id, TeamMember.is_active == True)
            .first()
        )
        if tm:
            team_id = tm.team_id

    resolved_cycle_id = _resolve_cycle_id(db, org_id, req.cycle_id)

    derived_quarter, derived_year = _derive_quarter_year_from_cycle(db, resolved_cycle_id)

    fa, fn_id = resolve_function_area_on_create(
        db,
        creator,
        level=req.level,
        explicit_area=req.function_area,
        org_id=org_id,
    )

    obj = Objective(
        org_id=org_id,
        owner_id=effective_owner_id,
        assigned_by_id=user_id if effective_owner_id != user_id else None,
        parent_id=req.parent_id,
        cycle_id=resolved_cycle_id,
        title=req.title,
        description=req.description,
        level=req.level.upper(),
        region_id=region_id,
        plant_id=plant_id,
        department_id=department_id,
        team_id=team_id,
        okr_status=OKR_STATUS_DRAFT,
        creation_approval_status="PENDING",
        status="ACTIVE",
        quarter=derived_quarter,
        year=derived_year,
        function_area=fa,
        function_node_id=fn_id,
    )
    db.add(obj)
    db.flush()
    try:
        enqueue_okr_creation_approval(db, obj, org_id, creator)
    except ValueError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    db.commit()
    db.refresh(obj)
    return _obj_dict(obj, db)


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION-SCOPED OKR VIEWS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/functional-overview")
def functional_overview(
    function_area: str = Query(""),
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    """CEO: all functions' vertical OKRs. Functional head: own function only."""
    org_id = payload.get("org_id", "")
    user_id = payload.get("sub", "")
    if not org_id or not user_id:
        raise HTTPException(400, "org_id or user_id not found in token")
    viewer = db.query(User).filter(User.id == user_id).first()
    if not viewer:
        raise HTTPException(404, "User not found")
    return get_functional_okrs(
        db,
        org_id,
        viewer,
        function_area=function_area or None,
    )


@router.get("/function-structure")
def function_structure(
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    """Functional head: vertical → sub-heads → plant department OKRs for their function."""
    org_id = payload.get("org_id", "")
    user_id = payload.get("sub", "")
    if not org_id or not user_id:
        raise HTTPException(400, "org_id or user_id not found in token")
    viewer = db.query(User).filter(User.id == user_id).first()
    if not viewer:
        raise HTTPException(404, "User not found")
    try:
        return get_function_structure(db, org_id, viewer)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/function-areas")
def list_function_areas():
    """Catalog of valid function_area values for create dialogs and filters."""
    return {
        "areas": [
            {"value": a, "label": FUNCTION_AREA_LABELS.get(a, a)} for a in FUNCTION_AREAS
        ]
    }


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 6 — OKR LIFECYCLE (draft / submit / publish / admin override)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/lifecycle-approval-queue")
def list_lifecycle_approval_queue(
    status: str = Query("pending"),
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    """
    OKR creation approval queue with history.

    status: pending | approved | rejected
    """
    org_id = payload.get("org_id", "")
    user_id = payload.get("sub", "")
    role = payload.get("role", "")

    if not org_id or not user_id:
        raise HTTPException(400, "org_id or user_id not found in token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    st = (status or "pending").strip().lower()
    q = db.query(Objective).filter(Objective.org_id == org_id)
    is_exec = normalize_role(role) in (SystemRole.SUPER_ADMIN, SystemRole.CEO)

    if st == "pending":
        q = q.filter(Objective.okr_status == "PENDING_APPROVAL")
        if not is_exec:
            pending_ids = pending_subject_ids_for_approver(
                db, org_id, user_id, SUBJECT_OKR_CREATION
            )
            if pending_ids:
                q = q.filter(Objective.id.in_(pending_ids))
            else:
                q = q.filter(Objective.pending_approver_user_id == user_id)
    elif st == "approved":
        q = q.filter(
            Objective.okr_status == "ACTIVE",
            Objective.creation_approval_status == "APPROVED",
        )
        if not is_exec:
            q = q.filter(
                or_(
                    Objective.creation_approved_by_id == user_id,
                    Objective.creation_primary_approved_by_id == user_id,
                )
            )
    elif st == "rejected":
        q = q.filter(Objective.okr_status == "REJECTED")
        q = apply_okr_visibility_filter(q, user, db, org_id)
    else:
        raise HTTPException(400, "status must be pending, approved, or rejected")

    if st == "approved":
        objs = q.order_by(
            Objective.creation_approved_at.desc(),
            Objective.created_at.desc(),
        ).all()
    else:
        objs = q.order_by(Objective.created_at.desc()).all()
    return [_obj_dict(o, db) for o in objs]


@router.get("/pending-lifecycle-approval")
def list_pending_lifecycle_approval(
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    """OKRs awaiting this user's approval (``okr_status=PENDING_APPROVAL``)."""
    org_id = payload.get("org_id", "")
    user_id = payload.get("sub", "")
    role = payload.get("role", "")
    
    if not org_id or not user_id:
        raise HTTPException(400, "org_id or user_id not found in token")
    
    q = (
        db.query(Objective)
        .filter(
            Objective.org_id == org_id,
            Objective.okr_status == "PENDING_APPROVAL",
        )
    )
    if normalize_role(role) not in (SystemRole.SUPER_ADMIN, SystemRole.CEO):
        pending_ids = pending_subject_ids_for_approver(
            db, org_id, user_id, SUBJECT_OKR_CREATION
        )
        if pending_ids:
            q = q.filter(Objective.id.in_(pending_ids))
        else:
            q = q.filter(Objective.pending_approver_user_id == user_id)

    objs = q.order_by(Objective.created_at.desc()).all()
    return [_obj_dict(o, db) for o in objs]


@router.get("/admin/lifecycle-overrides")
def list_admin_lifecycle_overrides(
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    """In-flight OKRs for SUPER_ADMIN override UI (not the business approval queue)."""
    org_id = payload.get("org_id", "")
    role = payload.get("role", "")
    
    if not org_id:
        raise HTTPException(400, "org_id not found in token")
    
    if normalize_role(role) != SystemRole.SUPER_ADMIN:
        raise HTTPException(403, "SUPER_ADMIN required")
    objs = (
        db.query(Objective)
        .filter(
            Objective.org_id == org_id,
            Objective.okr_status.in_(["DRAFT", "PENDING_APPROVAL", "REJECTED"]),
        )
        .order_by(Objective.created_at.desc())
        .all()
    )
    return [_obj_dict(o, db) for o in objs]


@router.post("/{obj_id}/submit-for-approval")
def submit_objective_for_approval(
    obj_id: str,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    org_id = payload.get("org_id", "")
    user_id = payload.get("sub", "")
    
    if not org_id or not user_id:
        raise HTTPException(400, "org_id or user_id not found in token")
    
    obj = db.query(Objective).filter(Objective.id == obj_id).first()
    if not obj:
        raise HTTPException(404, "Objective not found")
    actor = db.query(User).filter(User.id == user_id).first()
    if not actor:
        raise HTTPException(404, "User not found")
    try:
        result = submit_for_approval(db, obj, org_id, actor)
        db.commit()
        db.refresh(obj)
        return {"objective": _obj_dict(obj, db), **result}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{obj_id}/publish")
def publish_objective_as_ceo(
    obj_id: str,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    """CEO self-publish org-level OKR (DRAFT -> ACTIVE, skips approval queue)."""
    org_id = payload.get("org_id", "")
    user_id = payload.get("sub", "")
    
    if not org_id or not user_id:
        raise HTTPException(400, "org_id or user_id not found in token")
    
    obj = db.query(Objective).filter(Objective.id == obj_id).first()
    if not obj:
        raise HTTPException(404, "Objective not found")
    owner = db.query(User).filter(User.id == obj.owner_id).first()
    if not owner:
        raise HTTPException(404, "Owner not found")
    try:
        publish_ceo_okr(db, obj, owner, org_id, user_id)
        db.commit()
        db.refresh(obj)
        return _obj_dict(obj, db)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{obj_id}/admin-approve")
def admin_approve_objective(
    obj_id: str,
    body: dict = Body(...),
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    org_id = payload.get("org_id", "")
    user_id = payload.get("sub", "")
    role = payload.get("role", "")
    
    if not org_id or not user_id:
        raise HTTPException(400, "org_id or user_id not found in token")
    
    if normalize_role(role) != SystemRole.SUPER_ADMIN:
        raise HTTPException(403, "SUPER_ADMIN required")
    override_reason = (body.get("override_reason") or "").strip()
    if not override_reason:
        raise HTTPException(400, "override_reason is required")
    obj = db.query(Objective).filter(Objective.id == obj_id).first()
    if not obj:
        raise HTTPException(404, "Objective not found")
    admin_approve_okr(db, obj, org_id, user_id, override_reason)
    db.commit()
    db.refresh(obj)
    return _obj_dict(obj, db)


@router.post("/{obj_id}/admin-reject")
def admin_reject_objective(
    obj_id: str,
    body: dict = Body(...),
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    org_id = payload.get("org_id", "")
    user_id = payload.get("sub", "")
    role = payload.get("role", "")
    
    if not org_id or not user_id:
        raise HTTPException(400, "org_id or user_id not found in token")
    
    if normalize_role(role) != SystemRole.SUPER_ADMIN:
        raise HTTPException(403, "SUPER_ADMIN required")
    override_reason = (body.get("override_reason") or "").strip()
    if not override_reason:
        raise HTTPException(400, "override_reason is required")
    rejection_reason = (body.get("rejection_reason") or override_reason).strip()
    obj = db.query(Objective).filter(Objective.id == obj_id).first()
    if not obj:
        raise HTTPException(404, "Objective not found")
    admin_reject_okr(db, obj, org_id, user_id, override_reason, rejection_reason)
    db.commit()
    db.refresh(obj)
    return _obj_dict(obj, db)


# ══════════════════════════════════════════════════════════════════════════════
# ASSIGN OBJECTIVE TO EMPLOYEE (Manager/Admin Assignment)
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/assign")
def assign_okr_to_employee(
    body: dict = Body(...),
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    """
    Manager/Admin/CEO assigns an OKR to an employee.
    - Only users with MANAGER, DEPT_HEAD, PLANT_HEAD, or higher roles can assign
    - Can only assign to users they have authority over
    - Creates INDIVIDUAL-level OKR for the target employee
    """
    org_id = payload.get("org_id", "")
    user_id = payload.get("sub", "")
    role = payload.get("role", "")
    
    if not org_id or not user_id:
        raise HTTPException(400, "org_id or user_id not found in token")
    
    reject_functional_parent_obj_id_in_create_body(body)
    req = ObjectiveAssignCreate.model_validate(body)
    # Verify actor has permission to assign
    allowed_roles = ["CEO", "SUPER_ADMIN", "PLANT_HEAD", "DEPT_HEAD", "MANAGER", "TEAM_LEAD", "SUPERVISOR"]
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
    
    resolved_cycle_id = _resolve_cycle_id(db, org_id, req.cycle_id)

    # Create the OKR as INDIVIDUAL level
    derived_quarter, derived_year = _derive_quarter_year_from_cycle(db, resolved_cycle_id)

    obj = Objective(
        id=str(uuid.uuid4()),
        org_id=org_id,
        owner_id=req.employee_user_id,  # The OKR belongs to the employee
        assigned_by_id=user_id,  # Assigned by this manager
        parent_id=req.parent_id,
        cycle_id=resolved_cycle_id,
        title=req.title,
        description=req.description,
        level="INDIVIDUAL",  # Always INDIVIDUAL for assignments
        plant_id=plant_id,
        department_id=department_id,
        team_id=team_id,
        okr_status=OKR_STATUS_DRAFT,
        creation_approval_status="PENDING",
        quarter=derived_quarter,
        year=derived_year,
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

    try:
        enqueue_okr_creation_approval(db, obj, org_id, manager)
    except ValueError as e:
        db.rollback()
        raise HTTPException(400, str(e))

    db.commit()
    db.refresh(obj)
    return _obj_dict(obj, db)


# ══════════════════════════════════════════════════════════════════════════════
# ALIGNMENT TREE
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/alignment-tree")
def get_alignment_tree(
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
    plant_id: str = Query(""),
    cycle_id: str = Query(""),
):
    org_id = payload.get("org_id", "")
    if not org_id:
        raise HTTPException(400, "org_id not found in token")
    
    cascade = OKRCascadeService(db)
    return cascade.get_cascade_tree(org_id, plant_id or None, cycle_id or None)


# ══════════════════════════════════════════════════════════════════════════════
# PROGRESS SUMMARY (dashboard)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/progress-summary")
def get_progress_summary(
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
    plant_id: str = Query(""),
    cycle_id: str = Query(""),
    year: Optional[int] = Query(None),
    quarter: str = Query(""),
):
    org_id = payload.get("org_id", "")
    user_id = payload.get("sub", "")
    if not org_id:
        raise HTTPException(400, "org_id not found in token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    okr_scope = get_user_okr_scope(user, db)
    levels = ["ORGANIZATION", "REGION", "PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"]
    summary = {}
    for level in levels:
        q = db.query(Objective).filter(Objective.org_id == org_id, Objective.level == level)
        q = apply_okr_visibility_filter(q, user, db, org_id)
        q = apply_optional_scope_narrowing(
            q, okr_scope, plant_id=plant_id or None, db=db, org_id=org_id
        )
        q = _apply_objective_period_filter(
            q,
            year=year,
            quarter=quarter or None,
            cycle_id=cycle_id or None,
        )
        objs = q.all()
        on_track = sum(1 for o in objs if (o.progress or 0) >= 75)
        at_risk = sum(1 for o in objs if 60 <= (o.progress or 0) < 75)
        off_track = sum(1 for o in objs if (o.progress or 0) < 60)
        avg_progress = (
            round(sum(o.progress or 0 for o in objs) / len(objs), 1) if objs else 0
        )
        summary[level] = {
            "total": len(objs),
            "on_track": on_track,
            "at_risk": at_risk,
            "off_track": off_track,
            "avg_progress": avg_progress,
        }
    return summary


# ══════════════════════════════════════════════════════════════════════════════
# ALLOWED LEVELS FOR ROLE
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/allowed-levels")
def get_allowed_levels(
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    """Return which OKR levels the user may create or draft (Phase 6 includes self-draft levels)."""
    from server.roles import (
        ROLE_TO_BUSINESS_LEVEL,
        OBJECTIVE_LEVEL_ORDER,
        objective_level_to_business_level,
        get_business_level,
    )
    
    role = payload.get("role", "")
    user_id = payload.get("sub", "")

    from server.roles import can_create_objective_at_level

    role_n = normalize_role(role)
    levels_set = set(allowed_objective_levels_for(role_n))

    user = db.query(User).filter(User.id == user_id).first() if user_id else None
    if user:
        bl = get_business_level(role_n)
        if role_n == SystemRole.SUPER_ADMIN:
            for lvl in OBJECTIVE_LEVEL_ORDER:
                levels_set.add(lvl)
        elif bl is not None:
            max_bl = max(ROLE_TO_BUSINESS_LEVEL.values())
            for lvl in OBJECTIVE_LEVEL_ORDER:
                if not can_create_objective_at_level(role_n, lvl):
                    continue
                target_bl = objective_level_to_business_level(lvl)
                if target_bl is not None and target_bl in (bl, min(bl + 1, max_bl)):
                    levels_set.add(lvl)

    levels = [lvl for lvl in OBJECTIVE_LEVEL_ORDER if lvl in levels_set]
    return {"role": role, "allowed_levels": levels}


# ══════════════════════════════════════════════════════════════════════════════
# PARENT OPTIONS - get possible parent objectives for cascading
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/parent-options")
def get_parent_options(
    level: str = Query(""),
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
    plant_id: str = Query(""),
    department_id: str = Query(""),
    cycle_id: str = Query(""),
):
    """
    Get possible parent objectives for a given level.
    - PLANT OKR -> parent can be ORGANIZATION
    - DEPARTMENT OKR -> parent can be PLANT
    - TEAM OKR -> parent can be DEPARTMENT
    - INDIVIDUAL OKR -> parent can be TEAM or DEPARTMENT
    """
    org_id = payload.get("org_id", "")
    if not org_id:
        raise HTTPException(400, "org_id not found in token")
    
    level = level.upper()
    parent_levels = {
        "REGION": ["ORGANIZATION"],
        "PLANT": ["ORGANIZATION", "REGION"],
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
    if cycle_id:
        q = q.filter(Objective.cycle_id == cycle_id)

    # Scope filtering
    if plant_id:
        from sqlalchemy import or_
        q = q.filter(
            or_(
                Objective.plant_id == plant_id,
                Objective.level.in_(("ORGANIZATION", "REGION")),
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
def get_objective(
    obj_id: str,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    org_id = payload.get("org_id", "")
    if not org_id:
        raise HTTPException(400, "org_id not found in token")
    
    obj = db.query(Objective).filter(Objective.id == obj_id).first()
    if not obj:
        raise HTTPException(404, "Objective not found")
    
    # Verify the OKR belongs to this org
    if obj.org_id != org_id:
        raise HTTPException(403, "Unauthorized")
    
    return _obj_dict(obj, db)


@router.patch("/{obj_id}")
def patch_objective_functional_parent(
    obj_id: str,
    req: ObjectiveFunctionalParentPatch,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    """
    Set or clear ``functional_parent_obj_id`` (SUPER_ADMIN, Bearer JWT).
    Omitted field = no change; explicit null clears.
    """
    org_id = payload.get("org_id", "")
    if not org_id:
        raise HTTPException(400, "org_id not found in token")
    
    obj = db.query(Objective).filter(Objective.id == obj_id, Objective.org_id == org_id).first()
    if not obj:
        raise HTTPException(404, "Objective not found")
    payload = req.model_dump(exclude_unset=True)
    if "functional_parent_obj_id" not in payload:
        return _obj_dict(obj, db)
    validate_functional_parent_objective(obj, payload["functional_parent_obj_id"], db)
    obj.functional_parent_obj_id = payload["functional_parent_obj_id"]
    if not obj.function_area and payload["functional_parent_obj_id"]:
        inherited = inherit_function_area_from_parent(db, payload["functional_parent_obj_id"])
        if inherited:
            obj.function_area = inherited
            owner = db.query(User).filter(User.id == obj.owner_id).first()
            if owner:
                _, fn_id = resolve_function_area_on_create(
                    db,
                    owner,
                    level=obj.level,
                    explicit_area=inherited,
                    org_id=obj.org_id,
                )
                if fn_id:
                    obj.function_node_id = fn_id
    db.commit()
    db.refresh(obj)
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
    if req.function_area is not None:
        fa = normalize_function_area(req.function_area)
        obj.function_area = fa
        if fa:
            owner = db.query(User).filter(User.id == obj.owner_id).first()
            if owner:
                _, fn_id = resolve_function_area_on_create(
                    db, owner, level=obj.level, explicit_area=fa, org_id=obj.org_id
                )
                obj.function_node_id = fn_id
    db.commit()
    db.refresh(obj)
    return _obj_dict(obj, db)


@router.delete("/{obj_id}")
def delete_objective(
    obj_id: str,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    org_id = payload.get("org_id", "")
    if not org_id:
        raise HTTPException(400, "org_id not found in token")
    
    obj = db.query(Objective).filter(Objective.id == obj_id).first()
    if not obj:
        raise HTTPException(404)
    
    # Verify the OKR belongs to this org
    if obj.org_id != org_id:
        raise HTTPException(403, "Unauthorized")
    
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
    try:
        assert_okr_allows_kr_edit(obj)
    except ValueError as e:
        raise _lifecycle_error(e)
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
    obj = db.query(Objective).filter(Objective.id == kr.objective_id).first()
    if obj:
        try:
            assert_okr_allows_kr_edit(obj)
        except ValueError as e:
            raise _lifecycle_error(e)
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
    db.query(KRIngestSource).filter(KRIngestSource.key_result_id == kr_id).delete()
    db.delete(kr)
    db.commit()
    _recalc_and_cascade(obj_id, db)
    return {"status": "deleted"}


@router.get("/key-results/{kr_id}/ingest-source")
def get_kr_ingest_source(kr_id: str, db: Session = Depends(get_db)):
    kr = db.query(KeyResult).filter(KeyResult.id == kr_id).first()
    if not kr:
        raise HTTPException(404, "Key result not found")
    src = db.query(KRIngestSource).filter(KRIngestSource.key_result_id == kr_id).first()
    if not src:
        return {"configured": False}
    from server.services.kr_ingest_service import ingest_source_dict

    return {"configured": True, "ingest_source": ingest_source_dict(src)}


@router.put("/key-results/{kr_id}/ingest-source")
def configure_kr_ingest_source(
    kr_id: str,
    req: KRIngestSourceConfigure,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_payload),
):
    """Configure or update auto-ingest for a KR. Returns api_token once when created or rotated."""
    org_id = payload.get("org_id", "")
    user_id = payload.get("sub", "")
    
    if not org_id or not user_id:
        raise HTTPException(400, "org_id or user_id not found in token")
    
    kr = db.query(KeyResult).filter(KeyResult.id == kr_id).first()
    if not kr:
        raise HTTPException(404, "Key result not found")
    obj = db.query(Objective).filter(Objective.id == kr.objective_id).first()
    if not obj or obj.org_id != org_id:
        raise HTTPException(404, "Objective not found")

    tag = (req.source_metric_tag or "").strip()
    if not tag:
        raise HTTPException(400, "source_metric_tag is required")

    from server.services.kr_ingest_service import (
        generate_ingest_token,
        ingest_source_dict,
    )

    src = db.query(KRIngestSource).filter(KRIngestSource.key_result_id == kr_id).first()
    api_token_plain: str | None = None

    if src:
        src.source_system = req.source_system.strip()
        src.source_metric_tag = tag
        src.transform_expr = req.transform_expr
        src.is_active = req.is_active
        if req.rotate_token:
            api_token_plain, token_hash = generate_ingest_token()
            src.api_token_hash = token_hash
    else:
        api_token_plain, token_hash = generate_ingest_token()
        src = KRIngestSource(
            org_id=org_id,
            key_result_id=kr_id,
            source_system=req.source_system.strip(),
            source_metric_tag=tag,
            transform_expr=req.transform_expr,
            api_token_hash=token_hash,
            is_active=req.is_active,
        )
        db.add(src)

    db.commit()
    db.refresh(src)

    from server.services.audit_service import record_audit_event

    record_audit_event(
        org_id=org_id,
        actor_user_id=user_id,
        action="KR_INGEST_CONFIGURE",
        entity_type="KEY_RESULT",
        entity_id=kr_id,
        details={
            "source_system": src.source_system,
            "source_metric_tag": src.source_metric_tag,
            "is_active": src.is_active,
            "rotated": req.rotate_token or api_token_plain is not None,
        },
    )

    out = {"configured": True, "ingest_source": ingest_source_dict(src)}
    if api_token_plain:
        out["api_token"] = api_token_plain
    return out


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
    obj = db.query(Objective).filter(Objective.id == kr.objective_id).first()
    if obj:
        try:
            assert_okr_allows_progress(obj)
        except ValueError as e:
            raise _lifecycle_error(e)

    ingest = db.query(KRIngestSource).filter(
        KRIngestSource.key_result_id == kr_id, KRIngestSource.is_active == True
    ).first()
    is_override = ingest is not None

    update = ProgressUpdate(
        key_result_id=kr_id,
        submitted_by_id=user_id,
        previous_value=kr.current_value,
        new_value=req.new_value,
        notes=req.notes,
        blockers=req.blockers,
        evidence_url=req.evidence_url,
        progress_source="MANUAL",
        is_manual_override=is_override,
        status="PENDING",
    )
    db.add(update)

    if is_override and obj:
        from server.services.audit_service import record_audit_event

        record_audit_event(
            org_id=obj.org_id,
            actor_user_id=user_id,
            action="KR_MANUAL_OVERRIDE",
            entity_type="KEY_RESULT",
            entity_id=kr_id,
            details={"new_value": req.new_value, "notes": req.notes},
        )

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
        "is_manual_override": is_override,
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
    payload: dict = Depends(get_jwt_payload),
    plant_id: str = Query(""),
):
    """Get all pending progress validations that the current user should review."""
    org_id = payload.get("org_id", "")
    user_id = payload.get("sub", "")
    role = payload.get("role", "")
    
    if not org_id or not user_id:
        raise HTTPException(400, "org_id or user_id not found in token")
    
    from sqlalchemy import and_

    # Get objectives the user manages (directly assigned or in their scope)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return []

    if role not in (
        "SUPER_ADMIN",
        "CEO",
        "VP_OPERATIONS",
        "REGIONAL_HEAD",
        "PLANT_HEAD",
        "PLANT_MANAGER",
        "VP_MANUFACTURING",
        "DEPT_HEAD",
        "MANAGER",
        "TEAM_LEAD",
        "SUPERVISOR",
    ):
        return []

    q = db.query(Objective).filter(Objective.org_id == org_id)
    q = apply_okr_visibility_filter(q, user, db, org_id)
    okr_scope = get_user_okr_scope(user, db)
    q = apply_optional_scope_narrowing(
        q, okr_scope, plant_id=plant_id or None, db=db, org_id=org_id
    )

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
