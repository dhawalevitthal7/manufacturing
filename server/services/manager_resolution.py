"""
Resolve an employee's manager for reviews and check-ins.

Primary source: reporting_relationships (DIRECT).
Falls back to team lead, shift supervisor, org-node head chain, then
scoped role holders — matching how manufacturing orgs are usually seeded.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from server.models import (
    User,
    ReportingRelationship,
    Team,
    TeamMember,
    Shift,
    OrgNode,
)
from server.roles import SystemRole, normalize_role, FUNCTIONAL_APPROVER_ROLES

logger = logging.getLogger(__name__)

# Closest operational manager first
_ROLE_PRIORITY = {
    SystemRole.SUPERVISOR.value: 0,
    SystemRole.TEAM_LEAD.value: 1,
    SystemRole.MANAGER.value: 2,
    SystemRole.DEPT_HEAD.value: 3,
    SystemRole.PLANT_HEAD.value: 4,
    SystemRole.REGIONAL_HEAD.value: 5,
    SystemRole.VP_OPERATIONS.value: 6,
}

_ESCALATION_ROLES = (
    SystemRole.HR_HEAD.value,
    SystemRole.SUPER_ADMIN.value,
    SystemRole.CEO.value,
)


def _valid_manager(db: Session, manager_id: str, employee_id: str) -> Optional[str]:
    if not manager_id or manager_id == employee_id:
        return None
    mgr = db.query(User).filter(User.id == manager_id, User.is_active == True).first()
    return mgr.id if mgr else None


def _from_reporting(
    db: Session, employee_id: str, relationship_type: str
) -> Optional[str]:
    rel = (
        db.query(ReportingRelationship)
        .filter(
            ReportingRelationship.employee_id == employee_id,
            ReportingRelationship.relationship_type == relationship_type,
            ReportingRelationship.is_active == True,
        )
        .first()
    )
    if rel:
        return _valid_manager(db, rel.manager_id, employee_id)
    return None


def _from_team(db: Session, employee: User) -> Optional[str]:
    team_id = employee.team_id
    if not team_id:
        tm = (
            db.query(TeamMember)
            .filter(TeamMember.user_id == employee.id, TeamMember.is_active == True)
            .first()
        )
        if tm:
            team_id = tm.team_id

    if not team_id:
        return None

    team = db.query(Team).filter(Team.id == team_id, Team.is_active == True).first()
    if not team:
        return None

    if team.lead_id:
        found = _valid_manager(db, team.lead_id, employee.id)
        if found:
            return found

    lead_member = (
        db.query(TeamMember)
        .filter(
            TeamMember.team_id == team_id,
            TeamMember.is_team_lead == True,
            TeamMember.is_active == True,
        )
        .first()
    )
    if lead_member:
        return _valid_manager(db, lead_member.user_id, employee.id)
    return None


def _from_shift(db: Session, employee: User) -> Optional[str]:
    if not employee.shift_id:
        return None
    shift = db.query(Shift).filter(Shift.id == employee.shift_id).first()
    if shift and shift.supervisor_id:
        return _valid_manager(db, shift.supervisor_id, employee.id)
    return None


def _from_org_node_chain(db: Session, employee: User) -> Optional[str]:
    """
    Walk up the org tree from the employee's node parent.
    Skips the employee's own node first — they may be listed as head_user_id on their team.
    """
    if not employee.org_node_id:
        return None
    start = db.query(OrgNode).filter(OrgNode.id == employee.org_node_id).first()
    if not start:
        return None

    # Prefer ancestors from materialized path (root → parent), excluding self
    if start.path:
        ancestor_ids = [a for a in start.path.split(".") if a and a != start.id]
        for aid in reversed(ancestor_ids):
            anc = db.query(OrgNode).filter(OrgNode.id == aid).first()
            if anc and anc.head_user_id:
                found = _valid_manager(db, anc.head_user_id, employee.id)
                if found:
                    return found

    # Fallback: parent chain
    node = None
    if start.parent_id:
        node = db.query(OrgNode).filter(OrgNode.id == start.parent_id).first()
    visited = set()
    while node and node.id not in visited:
        visited.add(node.id)
        if node.head_user_id:
            found = _valid_manager(db, node.head_user_id, employee.id)
            if found:
                return found
        if not node.parent_id:
            break
        node = db.query(OrgNode).filter(OrgNode.id == node.parent_id).first()
    return None


def _from_department_role(db: Session, employee: User) -> Optional[str]:
    if not employee.department_id:
        return None
    candidates = (
        db.query(User)
        .filter(
            User.org_id == employee.org_id,
            User.department_id == employee.department_id,
            User.is_active == True,
            User.id != employee.id,
        )
        .all()
    )
    best_id = None
    best_rank = 999
    for u in candidates:
        role = normalize_role(u.system_role).value
        rank = _ROLE_PRIORITY.get(role)
        if rank is not None and rank < best_rank:
            best_rank = rank
            best_id = u.id
    return best_id


def _hr_escalation(db: Session, org_id: str, employee_id: str) -> Optional[str]:
    for role in (SystemRole.HR_HEAD.value, SystemRole.SUPER_ADMIN.value):
        hr = (
            db.query(User)
            .filter(
                User.org_id == org_id,
                User.system_role == role,
                User.is_active == True,
                User.id != employee_id,
            )
            .first()
        )
        if hr:
            return hr.id
    return None


def ensure_direct_reporting(
    db: Session,
    org_id: str,
    employee_id: str,
    manager_id: str,
    source: str,
) -> None:
    """Persist inferred manager as DIRECT relationship for future API calls."""
    existing = (
        db.query(ReportingRelationship)
        .filter(
            ReportingRelationship.employee_id == employee_id,
            ReportingRelationship.relationship_type == "DIRECT",
            ReportingRelationship.is_active == True,
        )
        .first()
    )
    if existing:
        if existing.manager_id == manager_id:
            return
        # Replace stale inferred link only if it was never manually set — always update for now
        existing.manager_id = manager_id
        existing.is_active = True
    else:
        db.add(
            ReportingRelationship(
                org_id=org_id,
                employee_id=employee_id,
                manager_id=manager_id,
                relationship_type="DIRECT",
                is_active=True,
            )
        )
    db.commit()
    logger.info(
        "Ensured DIRECT reporting %s -> %s (source=%s)",
        employee_id,
        manager_id,
        source,
    )


def resolve_manager_for_employee(
    db: Session,
    employee_id: str,
    org_id: Optional[str] = None,
    *,
    persist_if_missing: bool = True,
) -> Tuple[Optional[str], str]:
    """
    Returns (manager_id, resolution_source).
    source is one of: DIRECT, DOTTED_LINE, TEAM_LEAD, SHIFT_SUPERVISOR,
    ORG_NODE_HEAD, DEPARTMENT_ROLE, HR_ESCALATION, NONE
    """
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        return None, "NONE"

    oid = org_id or employee.org_id

    resolvers = [
        ("DIRECT", lambda: _from_reporting(db, employee_id, "DIRECT")),
        ("DOTTED_LINE", lambda: _from_reporting(db, employee_id, "DOTTED_LINE")),
        ("TEAM_LEAD", lambda: _from_team(db, employee)),
        ("SHIFT_SUPERVISOR", lambda: _from_shift(db, employee)),
        ("ORG_NODE_HEAD", lambda: _from_org_node_chain(db, employee)),
        ("DEPARTMENT_ROLE", lambda: _from_department_role(db, employee)),
    ]

    for source, fn in resolvers:
        manager_id = fn()
        if manager_id:
            if source != "DIRECT" and persist_if_missing:
                ensure_direct_reporting(db, oid, employee_id, manager_id, source)
            return manager_id, source

    # Top of chain / HR-only employees
    if normalize_role(employee.system_role).value in _ESCALATION_ROLES:
        return None, "NONE"

    hr = _hr_escalation(db, oid, employee_id)
    if hr:
        if persist_if_missing:
            ensure_direct_reporting(db, oid, employee_id, hr, "HR_ESCALATION")
        return hr, "HR_ESCALATION"

    return None, "NONE"


def get_manager_id(
    db: Session,
    employee_id: str,
    org_id: Optional[str] = None,
    *,
    persist_if_missing: bool = True,
) -> Optional[str]:
    manager_id, _ = resolve_manager_for_employee(
        db, employee_id, org_id, persist_if_missing=persist_if_missing
    )
    return manager_id


def _from_department_role_priority(
    db: Session, employee: User, role_order: list
) -> Optional[str]:
    """First matching role in employee's department (closest operational manager)."""
    if not employee.department_id:
        return None
    for role in role_order:
        u = (
            db.query(User)
            .filter(
                User.org_id == employee.org_id,
                User.department_id == employee.department_id,
                User.system_role == role,
                User.is_active == True,
                User.id != employee.id,
            )
            .first()
        )
        if u:
            return u.id
    return None


def get_subordinate_employee_ids(
    db: Session,
    manager_id: str,
    *,
    include_indirect: bool = True,
) -> set[str]:
    """
    Employee IDs that report to manager_id (directly, or full subtree when include_indirect).
    Used for manager inbox / review queue visibility across leadership levels.
    """
    subordinates: set[str] = set()
    if not include_indirect:
        rows = (
            db.query(ReportingRelationship.employee_id)
            .filter(
                ReportingRelationship.manager_id == manager_id,
                ReportingRelationship.is_active == True,
            )
            .all()
        )
        return {r[0] for r in rows if r[0] != manager_id}

    managers_in_tree = {manager_id}
    while True:
        rows = (
            db.query(ReportingRelationship.employee_id)
            .filter(
                ReportingRelationship.manager_id.in_(managers_in_tree),
                ReportingRelationship.is_active == True,
            )
            .all()
        )
        new_ids = {r[0] for r in rows if r[0] not in subordinates and r[0] != manager_id}
        if not new_ids:
            break
        subordinates.update(new_ids)
        managers_in_tree.update(new_ids)
    return subordinates


def can_coach_employee(
    db: Session,
    actor_id: str,
    employee_id: str,
    assigned_coach_id: Optional[str] = None,
) -> bool:
    """True when actor is the assigned coach or a leader above the employee in the reporting tree."""
    if not actor_id or not employee_id:
        return False
    if assigned_coach_id and actor_id == assigned_coach_id:
        return True
    if actor_id == employee_id:
        return False
    return employee_id in get_subordinate_employee_ids(db, actor_id)


def resolve_line_manager_for_review(
    db: Session,
    employee_id: str,
    org_id: Optional[str] = None,
    *,
    persist_if_missing: bool = True,
) -> Tuple[Optional[str], str]:
    """
    Formal quarterly review routing: line manager (MANAGER / DEPT_HEAD),
    not shift-level coach (TEAM_LEAD / SUPERVISOR).
    """
    immediate_id, immediate_src = resolve_immediate_manager_for_checkin(
        db, employee_id, org_id, persist_if_missing=persist_if_missing
    )
    if not immediate_id:
        return None, "NONE"

    immediate = db.query(User).filter(User.id == immediate_id).first()
    if not immediate:
        return None, "NONE"

    imm_role = normalize_role(immediate.system_role).value
    if imm_role in (
        SystemRole.MANAGER.value,
        SystemRole.DEPT_HEAD.value,
        SystemRole.PLANT_HEAD.value,
    ):
        return immediate_id, immediate_src

    current_id = immediate_id
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
        mgr_role = normalize_role(mgr.system_role).value
        if mgr_role in (
            SystemRole.MANAGER.value,
            SystemRole.DEPT_HEAD.value,
            SystemRole.PLANT_HEAD.value,
        ):
            return mgr.id, "LINE_MANAGER"
        current_id = mgr.id

    employee = db.query(User).filter(User.id == employee_id).first()
    if employee:
        dept_mgr = _from_department_role_priority(
            db, employee, [SystemRole.MANAGER.value, SystemRole.DEPT_HEAD.value]
        )
        if dept_mgr:
            return dept_mgr, "DEPARTMENT_ROLE"

    return immediate_id, immediate_src


def resolve_immediate_manager_for_checkin(
    db: Session,
    employee_id: str,
    org_id: Optional[str] = None,
    *,
    persist_if_missing: bool = True,
) -> Tuple[Optional[str], str]:
    """
    Weekly check-in routing: employee → immediate manager ONLY.
    Priority (manufacturing):
      1. reporting_relationships (DIRECT)
      2. Supervisor / Team Lead (same team or department)
      3. Manager (department)
      4. Department Head (fallback — not full escalation chain)
    Does NOT walk Regional → Plant → CEO.
    """
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        return None, "NONE"
    oid = org_id or employee.org_id

    direct = _from_reporting(db, employee_id, "DIRECT")
    if direct:
        return direct, "DIRECT"

    team_lead = _from_team(db, employee)
    if team_lead:
        if persist_if_missing:
            ensure_direct_reporting(db, oid, employee_id, team_lead, "TEAM_LEAD")
        return team_lead, "TEAM_LEAD"

    supervisor = _from_department_role_priority(
        db, employee, [SystemRole.SUPERVISOR.value, SystemRole.TEAM_LEAD.value]
    )
    if supervisor:
        if persist_if_missing:
            ensure_direct_reporting(db, oid, employee_id, supervisor, "SUPERVISOR")
        return supervisor, "SUPERVISOR"

    manager = _from_department_role_priority(db, employee, [SystemRole.MANAGER.value])
    if manager:
        if persist_if_missing:
            ensure_direct_reporting(db, oid, employee_id, manager, "MANAGER")
        return manager, "MANAGER"

    dept_head = _from_department_role_priority(db, employee, [SystemRole.DEPT_HEAD.value])
    if dept_head:
        if persist_if_missing:
            ensure_direct_reporting(db, oid, employee_id, dept_head, "DEPT_HEAD_FALLBACK")
        return dept_head, "DEPT_HEAD_FALLBACK"

    return None, "NONE"


def resolve_dept_head_for_employee(
    db: Session, employee_id: str, org_id: Optional[str] = None
) -> Optional[str]:
    """Department head for exception escalation (not CEO/Regional)."""
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        return None
    oid = org_id or employee.org_id
    if employee.department_id:
        dh = (
            db.query(User)
            .filter(
                User.org_id == oid,
                User.department_id == employee.department_id,
                User.system_role == SystemRole.DEPT_HEAD.value,
                User.is_active == True,
                User.id != employee_id,
            )
            .first()
        )
        if dh:
            return dh.id
    # Org node department head
    if employee.org_node_id:
        from server.models import OrgNode

        node = db.query(OrgNode).filter(OrgNode.id == employee.org_node_id).first()
        if node and node.path:
            for nid in reversed(node.path.split(".")):
                anc = db.query(OrgNode).filter(OrgNode.id == nid).first()
                if anc and anc.node_type == "DEPARTMENT" and anc.head_user_id:
                    found = _valid_manager(db, anc.head_user_id, employee_id)
                    if found:
                        return found
    return None


def resolve_dept_head_for_quarterly_moderation(
    db: Session, employee_id: str, org_id: str
) -> Optional[str]:
    """Optional dept-head moderation step in quarterly reviews."""
    return resolve_dept_head_for_employee(db, employee_id, org_id)


def resolve_line_manager(
    db: Session,
    user_id: str,
    org_id: Optional[str] = None,
    *,
    persist_if_missing: bool = True,
) -> Tuple[Optional[str], str]:
    """
    Line manager via DIRECT reporting chain and operational fallbacks.
    Does not use DOTTED_LINE / REVIEWER relationships.
    """
    employee = db.query(User).filter(User.id == user_id).first()
    if not employee:
        return None, "NONE"
    oid = org_id or employee.org_id

    direct = _from_reporting(db, user_id, "DIRECT")
    if direct:
        return direct, "DIRECT"

    team_lead = _from_team(db, employee)
    if team_lead:
        if persist_if_missing:
            ensure_direct_reporting(db, oid, user_id, team_lead, "TEAM_LEAD")
        return team_lead, "TEAM_LEAD"

    supervisor = _from_department_role_priority(
        db, employee, [SystemRole.SUPERVISOR.value, SystemRole.TEAM_LEAD.value]
    )
    if supervisor:
        if persist_if_missing:
            ensure_direct_reporting(db, oid, user_id, supervisor, "SUPERVISOR")
        return supervisor, "SUPERVISOR"

    manager = _from_department_role_priority(db, employee, [SystemRole.MANAGER.value])
    if manager:
        if persist_if_missing:
            ensure_direct_reporting(db, oid, user_id, manager, "MANAGER")
        return manager, "MANAGER"

    org_head = _from_org_node_chain(db, employee)
    if org_head:
        return org_head, "ORG_NODE_HEAD"

    dept_head = _from_department_role_priority(db, employee, [SystemRole.DEPT_HEAD.value])
    if dept_head:
        return dept_head, "DEPT_HEAD"

    dept_role = _from_department_role(db, employee)
    if dept_role:
        return dept_role, "DEPARTMENT_ROLE"

    return None, "NONE"


def resolve_functional_manager(
    db: Session,
    user_id: str,
    org_id: Optional[str] = None,
) -> Tuple[Optional[str], str]:
    """
    Functional (dotted-line) manager for dual approval stage 2.

    When multiple DOTTED_LINE / REVIEWER links exist (e.g. dept head + CMO),
    prefer executive committee roles (CMO, CFO, …) over operational dept heads.
    """
    employee = db.query(User).filter(User.id == user_id).first()
    if not employee:
        return None, "NONE"

    rels = (
        db.query(ReportingRelationship)
        .filter(
            ReportingRelationship.employee_id == user_id,
            ReportingRelationship.relationship_type.in_(("DOTTED_LINE", "REVIEWER")),
            ReportingRelationship.is_active == True,
        )
        .all()
    )

    exec_id: Optional[str] = None
    exec_source = "NONE"
    fallback_id: Optional[str] = None
    fallback_source = "NONE"

    for rel in rels:
        mgr = db.query(User).filter(User.id == rel.manager_id, User.is_active == True).first()
        if not mgr or mgr.id == user_id:
            continue
        source = rel.relationship_type
        role = normalize_role(mgr.system_role)
        if role in FUNCTIONAL_APPROVER_ROLES:
            exec_id = mgr.id
            exec_source = source
            break
        if not fallback_id:
            fallback_id = mgr.id
            fallback_source = source

    if exec_id:
        return exec_id, exec_source
    if fallback_id:
        return fallback_id, fallback_source
    return None, "NONE"


def resolve_approvers(
    db: Session,
    user_id: str,
    org_id: Optional[str] = None,
    *,
    persist_if_missing: bool = True,
) -> dict[str, Optional[str]]:
    """
    Dual-approval chain anchors: line (Plant Head) and functional head.
    Falls back to line-only when functional manager is unresolved.
    """
    line_id, _ = resolve_line_manager(
        db, user_id, org_id, persist_if_missing=persist_if_missing
    )
    functional_id, _ = resolve_functional_manager(db, user_id, org_id)

    if not functional_id:
        logger.warning(
            "No functional manager for user %s; dual approval will use line-only.",
            user_id,
        )

    return {"line": line_id, "functional": functional_id}
