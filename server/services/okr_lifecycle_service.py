"""
OKR lifecycle (Phase 6): draft → pending approval → active.

State machine on ``Objective.okr_status``:
  DRAFT → PENDING_APPROVAL → ACTIVE → (ACHIEVED | MISSED | ARCHIVED)
  REJECTED is terminal until owner edits and resubmits (back to DRAFT).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from server.models import Objective, User, ReportingRelationship, KeyResult, ProgressUpdate, ProgressSubmission
from server.okr_hierarchy_workflow import OKRHierarchyWorkflow
from server.roles import (
    SystemRole,
    get_business_level,
    normalize_role,
    can_create_okr_at_level,
    OBJECTIVE_LEVEL_ORDER,
)
from server.services.audit_service import audit_super_admin_action, record_audit_event
from server.services.dual_approval_service import (
    SUBJECT_OKR_CREATION,
    build_chain,
)

OKR_STATUS_DRAFT = "DRAFT"
OKR_STATUS_PENDING = "PENDING_APPROVAL"
OKR_STATUS_ACTIVE = "ACTIVE"
OKR_STATUS_REJECTED = "REJECTED"
OKR_STATUS_ACHIEVED = "ACHIEVED"
OKR_STATUS_MISSED = "MISSED"
OKR_STATUS_ARCHIVED = "ARCHIVED"

# AI-assisted hierarchical cascade lifecycle (extends manual lifecycle)
OKR_STATUS_AI_DRAFT = "AI_DRAFT"
OKR_STATUS_UNDER_REVIEW = "UNDER_REVIEW"
OKR_STATUS_PENDING_PARENT = "PENDING_PARENT_APPROVAL"
OKR_STATUS_AI_REJECTED = "AI_REJECTED"

AUDIT_OKR_PUBLISH = "OKR_CEO_PUBLISH"
AUDIT_OKR_ADMIN_APPROVE = "OKR_ADMIN_APPROVE"
AUDIT_OKR_ADMIN_REJECT = "OKR_ADMIN_REJECT"

# Map Objective.level to business hierarchy level (ROLE_TO_BUSINESS_LEVEL scale).
OBJECTIVE_LEVEL_TO_BUSINESS: Dict[str, int] = {
    "ORGANIZATION": 0,
    "REGION": 1,
    "PLANT": 2,
    "DEPARTMENT": 3,
    "TEAM": 4,
    "INDIVIDUAL": 6,
}


def objective_level_to_business_level(level: str) -> Optional[int]:
    return OBJECTIVE_LEVEL_TO_BUSINESS.get((level or "").strip().upper())


def has_business_role(user: User) -> bool:
    role = normalize_role(user.system_role)
    if role == SystemRole.SUPER_ADMIN:
        return False
    return get_business_level(role) is not None


def is_super_admin_only(user: User) -> bool:
    return normalize_role(user.system_role) == SystemRole.SUPER_ADMIN


def can_user_draft_objective(
    actor: User,
    objective_level: str,
    owner_id: str,
) -> Tuple[bool, str]:
    """
  Whether ``actor`` may create a draft OKR at ``objective_level`` for ``owner_id``.

  Self-draft: allowed at own business level or one step below (same rule as
  ``can_create_okr_at_level``). Creating for someone else uses executive / manager
  rules via ``can_create_objective_at_level``.
    """
    lvl = (objective_level or "").strip().upper()
    if lvl not in OBJECTIVE_LEVEL_ORDER:
        return False, f"Invalid objective level: {objective_level}"

    role = normalize_role(actor.system_role)
    if owner_id == actor.id and role == SystemRole.EMPLOYEE:
        return False, "Employees cannot create their own OKRs; ask your manager to assign one"

    if owner_id != actor.id:
        from server.roles import can_create_objective_at_level

        if not can_create_objective_at_level(role, lvl):
            return False, f"Role {actor.system_role} cannot create {lvl} OKRs for others"
        return True, ""

    if role == SystemRole.SUPER_ADMIN:
        return True, ""

    user_bl = get_business_level(role)
    if user_bl is None:
        return False, "User has no business role; assign one before drafting OKRs"

    target_bl = objective_level_to_business_level(lvl)
    if target_bl is None:
        return False, f"Unknown level mapping for {lvl}"

    if not can_create_okr_at_level(role, user_bl, target_bl):
        return False, (
            f"Cannot draft a {lvl} OKR at your role level; "
            "choose an objective level aligned with your position"
        )
    return True, ""


def ceo_may_self_publish(okr: Objective, owner: User) -> bool:
    return (
        okr.level.upper() == "ORGANIZATION"
        and normalize_role(owner.system_role) == SystemRole.CEO
        and okr.owner_id == owner.id
    )


def _is_valid_business_approver(
    db: Session,
    approver: User,
    okr: Objective,
    org_id: str,
) -> bool:
    if is_super_admin_only(approver):
        return False
    if not has_business_role(approver):
        return False
    wf = OKRHierarchyWorkflow(db)
    ok, _ = wf.can_approve_okr(approver, okr, org_id)
    return ok


def resolve_business_approver(
    db: Session,
    okr: Objective,
    org_id: str,
    creator_id: Optional[str] = None,
) -> Tuple[Optional[User], str]:
    """
    Resolve the business approver for ``okr`` creation approval.

    Primary: walk the reporting chain upward from the **creator** (not owner).
    Creator = ``assigned_by_id`` when present, else ``owner_id``.
    First manager on the chain authorized per ``APPROVAL_ROLES_BY_LEVEL`` wins.
    Fallback: scoped matrix lookup, then CEO.
    """
    creator_id = creator_id or okr.assigned_by_id or okr.owner_id
    creator = db.query(User).filter(User.id == creator_id).first()
    if not creator:
        return None, "Creator not found"

    owner = db.query(User).filter(User.id == okr.owner_id).first()
    if not owner:
        return None, "Owner not found"

    if (
        ceo_may_self_publish(okr, owner)
        and creator_id == owner.id
        and normalize_role(creator.system_role) == SystemRole.CEO
    ):
        return None, "CEO org-level OKR: use publish endpoint"

    if not has_business_role(creator) and normalize_role(creator.system_role) != SystemRole.CEO:
        return None, "Creator has no business role; assign one before creating OKRs"

    # Walk reporting chain from creator upward
    current_id = creator_id
    visited: set[str] = set()
    while current_id and current_id not in visited:
        visited.add(current_id)
        rel = (
            db.query(ReportingRelationship)
            .filter(
                ReportingRelationship.employee_id == current_id,
                ReportingRelationship.relationship_type == "DIRECT",
                ReportingRelationship.is_active == True,
            )
            .first()
        )
        if not rel:
            break
        mgr = db.query(User).filter(User.id == rel.manager_id).first()
        if not mgr:
            break
        if mgr.id != creator_id and _is_valid_business_approver(db, mgr, okr, org_id):
            return mgr, ""
        current_id = mgr.id

    # Scoped role from approval matrix (fallback)
    wf = OKRHierarchyWorkflow(db)
    roles = wf.APPROVAL_ROLES_BY_LEVEL.get(okr.level.upper(), [])
    for role_name in roles:
        q = db.query(User).filter(
            User.org_id == org_id,
            User.system_role == role_name,
            User.is_active == True,
            User.id != creator_id,
        )
        if okr.team_id:
            q = q.filter(User.team_id == okr.team_id)
        elif okr.department_id:
            q = q.filter(User.department_id == okr.department_id)
        elif okr.plant_id:
            q = q.filter(User.plant_id == okr.plant_id)
        elif okr.region_id:
            q = q.filter(User.org_node_id == okr.region_id)
        candidate = q.first()
        if candidate and _is_valid_business_approver(db, candidate, okr, org_id):
            return candidate, ""

    # Escalate to CEO
    ceo = (
        db.query(User)
        .filter(
            User.org_id == org_id,
            User.system_role == SystemRole.CEO.value,
            User.is_active == True,
        )
        .first()
    )
    if ceo and ceo.id != creator_id and _is_valid_business_approver(db, ceo, okr, org_id):
        return ceo, ""

    return None, "No business approver found; contact your administrator"


def enqueue_okr_creation_approval(
    db: Session,
    okr: Objective,
    org_id: str,
    creator: User,
) -> Optional[Dict[str, Any]]:
    """
    On create: enter PENDING_APPROVAL queue unless CEO is self-publishing org OKR.
    """
    owner = db.query(User).filter(User.id == okr.owner_id).first()
    if not owner:
        raise ValueError("Owner not found")

    if ceo_may_self_publish(okr, owner) and creator.id == owner.id:
        okr.okr_status = OKR_STATUS_DRAFT
        okr.creation_approval_status = "PENDING"
        okr.pending_approver_user_id = None
        okr.pending_approver_role = None
        return None

    okr.okr_status = OKR_STATUS_PENDING
    okr.creation_approval_status = "PENDING"
    okr.rejection_reason = None
    okr.creation_primary_approved_at = None
    okr.creation_primary_approved_by_id = None
    okr.creation_functional_approved_at = None
    okr.creation_functional_approved_by_id = None

    try:
        chain = build_chain(db, org_id, SUBJECT_OKR_CREATION, okr.id, creator.id)
    except Exception as exc:
        raise ValueError(str(exc)) from exc
    _sync_pending_from_chain(db, okr, chain)

    pending_name = None
    for step in chain.get("steps") or []:
        if step.get("status") == "PENDING":
            pending_name = step.get("approver_name")
            break

    return {
        "okr_status": okr.okr_status,
        "pending_approver_user_id": okr.pending_approver_user_id,
        "pending_approver_name": pending_name,
        "pending_approver_role": okr.pending_approver_role,
        "approval_chain_status": chain,
    }


def _sync_pending_from_chain(db: Session, okr: Objective, chain: dict) -> None:
    """Set pending approver from the first pending step in chain status."""
    for step in chain.get("steps") or []:
        if step.get("status") == "PENDING" and step.get("approver_id"):
            okr.pending_approver_user_id = step["approver_id"]
            okr.pending_approver_role = step.get("approver_role")
            return
    okr.pending_approver_user_id = None
    okr.pending_approver_role = None


def activate_okr(okr: Objective, db: Session) -> None:
    """Mark OKR active and lock KR baselines (targets/weights)."""
    okr.okr_status = OKR_STATUS_ACTIVE
    okr.status = "ACTIVE"
    okr.creation_approval_status = "APPROVED"
    okr.kr_baseline_locked = True
    okr.pending_approver_user_id = None
    okr.pending_approver_role = None
    okr.rejection_reason = None
    now = datetime.utcnow()
    if not okr.creation_approved_at:
        okr.creation_approved_at = now

    # Schedule AI cascade to next hierarchy level (non-blocking; never auto-activates children).
    try:
        from server.services.ai_cascade_engine import schedule_cascade_for_active_okr

        schedule_cascade_for_active_okr(okr.id, okr.org_id)
    except Exception:
        pass  # Cascade failure must not block parent activation


def submit_for_approval(
    db: Session,
    okr: Objective,
    org_id: str,
    actor: User,
) -> Dict[str, Any]:
    if okr.okr_status not in (OKR_STATUS_DRAFT, OKR_STATUS_REJECTED):
        raise ValueError(f"Cannot submit OKR in status {okr.okr_status}")

    owner = db.query(User).filter(User.id == okr.owner_id).first()
    if not owner:
        raise ValueError("Owner not found")
    if okr.owner_id != actor.id and normalize_role(actor.system_role) not in (
        SystemRole.SUPER_ADMIN,
        SystemRole.CEO,
    ):
        raise ValueError("Only the owner may submit this OKR for approval")

    if ceo_may_self_publish(okr, owner):
        raise ValueError("CEO org-level OKR: use POST /api/okrs/{id}/publish instead")

    # Require that the owner actually entered progress (supports both legacy ProgressUpdate and new ProgressSubmission).
    pending_updates = (
        db.query(ProgressUpdate)
        .join(KeyResult, ProgressUpdate.key_result_id == KeyResult.id)
        .filter(
            KeyResult.objective_id == okr.id,
            ProgressUpdate.status == "PENDING",
        )
        .count()
    )
    pending_submissions = (
        db.query(ProgressSubmission.id)
        .join(KeyResult, ProgressSubmission.key_result_id == KeyResult.id)
        .filter(
            KeyResult.objective_id == okr.id,
            ProgressSubmission.status == "PENDING",
        )
        .count()
    )
    pending_count = pending_updates + pending_submissions

    if pending_count <= 0:
        raise ValueError("Update KR progress first (no pending progress found).")

    okr.okr_status = OKR_STATUS_PENDING
    okr.creation_approval_status = "PENDING"
    okr.rejection_reason = None
    okr.creation_primary_approved_at = None
    okr.creation_primary_approved_by_id = None
    okr.creation_functional_approved_at = None
    okr.creation_functional_approved_by_id = None

    try:
        chain = build_chain(db, org_id, SUBJECT_OKR_CREATION, okr.id, actor.id)
    except Exception as exc:
        raise ValueError(str(exc)) from exc
    _sync_pending_from_chain(db, okr, chain)
    db.flush()

    pending_name = None
    for step in chain.get("steps") or []:
        if step.get("status") == "PENDING":
            pending_name = step.get("approver_name")
            break

    return {
        "okr_status": okr.okr_status,
        "pending_approver_user_id": okr.pending_approver_user_id,
        "pending_approver_name": pending_name,
        "pending_approver_role": okr.pending_approver_role,
        "approval_chain_status": chain,
    }


def publish_ceo_okr(
    db: Session,
    okr: Objective,
    owner: User,
    org_id: str,
    actor_user_id: str,
) -> None:
    if not ceo_may_self_publish(okr, owner):
        raise ValueError("Only the CEO may self-publish org-level OKRs they own")
    if okr.owner_id != actor_user_id:
        raise ValueError("Only the owner may publish this OKR")
    if okr.okr_status not in (OKR_STATUS_DRAFT, OKR_STATUS_REJECTED):
        raise ValueError(f"Cannot publish OKR in status {okr.okr_status}")

    activate_okr(okr, db)
    record_audit_event(
        org_id=org_id,
        actor_user_id=actor_user_id,
        action=AUDIT_OKR_PUBLISH,
        entity_type="OBJECTIVE",
        entity_id=okr.id,
        details={
            "message": "self-published by CEO, no higher approver",
            "okr_status": OKR_STATUS_ACTIVE,
        },
    )


def reject_okr(
    okr: Objective,
    reason: str,
    *,
    clear_approver: bool = True,
) -> None:
    okr.okr_status = OKR_STATUS_REJECTED
    okr.creation_approval_status = "REJECTED"
    okr.rejection_reason = reason
    okr.creation_approval_notes = reason
    if clear_approver:
        okr.pending_approver_user_id = None
        okr.pending_approver_role = None


def assert_okr_allows_progress(okr: Objective) -> None:
    st = (okr.okr_status or "").strip().upper()
    # Legacy rows without lifecycle set: allow progress (pre–Phase 6 data).
    if not st or st == OKR_STATUS_ACTIVE:
        return
    if st == OKR_STATUS_PENDING:
        raise ValueError(
            "OKR is awaiting creation approval; progress submission is disabled until approved."
        )
    raise ValueError(
        f"OKR must be ACTIVE to record progress (current: {okr.okr_status})"
    )


def assert_okr_allows_kr_edit(okr: Objective) -> None:
    if okr.kr_baseline_locked:
        raise ValueError(
            "Key results are locked after approval; targets and weights cannot change"
        )
    if (okr.okr_status or OKR_STATUS_ACTIVE) not in (
        OKR_STATUS_DRAFT,
        OKR_STATUS_REJECTED,
        OKR_STATUS_PENDING,
    ):
        raise ValueError(f"Cannot edit key results while OKR status is {okr.okr_status}")


def admin_approve_okr(
    db: Session,
    okr: Objective,
    org_id: str,
    actor_user_id: str,
    override_reason: str,
) -> None:
    activate_okr(okr, db)
    audit_super_admin_action(
        org_id=org_id,
        actor_user_id=actor_user_id,
        action=AUDIT_OKR_ADMIN_APPROVE,
        entity_type="OBJECTIVE",
        entity_id=okr.id,
        details={"override_reason": override_reason, "is_admin_override": True},
    )


def admin_reject_okr(
    db: Session,
    okr: Objective,
    org_id: str,
    actor_user_id: str,
    override_reason: str,
    rejection_reason: str,
) -> None:
    reject_okr(okr, rejection_reason or override_reason)
    audit_super_admin_action(
        org_id=org_id,
        actor_user_id=actor_user_id,
        action=AUDIT_OKR_ADMIN_REJECT,
        entity_type="OBJECTIVE",
        entity_id=okr.id,
        details={
            "override_reason": override_reason,
            "rejection_reason": rejection_reason,
            "is_admin_override": True,
        },
    )
