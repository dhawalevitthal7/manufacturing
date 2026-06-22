"""
OKR progress submission and assignment rules (team / individual hierarchy).

- Employees cannot create OKRs; managers assign individual OKRs.
- Team OKR progress: team lead (owner) submits only.
- Individual OKR progress: assigned employee (owner) submits only.
- Employees may view team OKRs but not submit team progress.
"""

from __future__ import annotations

from typing import Tuple

from sqlalchemy.orm import Session

from server.models import Objective, ReportingRelationship, Team, TeamMember, User
from server.roles import SystemRole, normalize_role

# Roles that may submit progress on TEAM-level OKRs they own.
_TEAM_PROGRESS_ROLES = frozenset(
    {SystemRole.TEAM_LEAD.value, SystemRole.SUPERVISOR.value}
)

# Roles that may submit on INDIVIDUAL OKRs they own (assigned employee).
_INDIVIDUAL_PROGRESS_ROLES = frozenset(
    {
        SystemRole.EMPLOYEE.value,
        SystemRole.TEAM_LEAD.value,
        SystemRole.SUPERVISOR.value,
        SystemRole.MANAGER.value,
    }
)

_HEAD_PROGRESS_BY_LEVEL = {
    "ORGANIZATION": frozenset({"CEO", "CFO", "CMO", "CTO"}),
    "REGION": frozenset({"REGIONAL_HEAD", "VP_OPERATIONS", "VP_MANUFACTURING", "CEO"}),
    "PLANT": frozenset({"PLANT_HEAD", "VP_OPERATIONS", "VP_MANUFACTURING", "CEO"}),
    "DEPARTMENT": frozenset({"DEPT_HEAD", "PLANT_HEAD", "MANAGER"}),
}


def can_submit_okr_progress(
    user: User,
    objective: Objective,
    db: Session,
) -> Tuple[bool, str]:
    """
    Whether ``user`` may submit KR progress on ``objective``.

    Owner-only at every level, with role constraints for TEAM / INDIVIDUAL.
    """
    if not user or not objective:
        return False, "Not authorized"

    if objective.owner_id != user.id:
        return False, "Only the OKR owner may submit progress for this objective"

    level = (objective.level or "").upper()
    role = user.system_role

    if role == "SUPER_ADMIN":
        return True, ""

    if level == "INDIVIDUAL":
        if role not in _INDIVIDUAL_PROGRESS_ROLES:
            return False, "Individual OKR progress is submitted by the assigned employee"
        return True, ""

    if level == "TEAM":
        if role not in _TEAM_PROGRESS_ROLES:
            return False, "Team OKR progress is submitted by the team lead (OKR owner)"
        return True, ""

    allowed_heads = _HEAD_PROGRESS_BY_LEVEL.get(level)
    if allowed_heads and role not in allowed_heads:
        return False, f"Role {role} cannot submit {level} OKR progress"
    if allowed_heads:
        return True, ""

    return False, f"Cannot submit progress for {level} OKRs"


def actor_may_assign_okr_to_user(
    actor: User,
    target: User,
    objective_level: str,
    db: Session,
) -> Tuple[bool, str]:
    """Whether ``actor`` may create/assign an OKR owned by ``target``."""
    if not actor or not target:
        return False, "User not found"
    if actor.org_id != target.org_id:
        return False, "User is not in your organization"

    lvl = (objective_level or "").upper()
    actor_role = normalize_role(actor.system_role)

    if actor_role == SystemRole.EMPLOYEE:
        return False, "Employees cannot assign OKRs"

    if target.id == actor.id:
        return True, ""

    if lvl == "INDIVIDUAL":
        if actor_role == SystemRole.MANAGER:
            if target.team_id and actor.team_id and target.team_id == actor.team_id:
                return True, ""
            rel = (
                db.query(ReportingRelationship)
                .filter(
                    ReportingRelationship.employee_id == target.id,
                    ReportingRelationship.manager_id == actor.id,
                    ReportingRelationship.is_active == True,
                )
                .first()
            )
            if rel:
                return True, ""
            return False, "Managers can only assign individual OKRs to direct reports in their team"
        if actor_role in (SystemRole.TEAM_LEAD, SystemRole.SUPERVISOR):
            if target.team_id and actor.team_id and target.team_id == actor.team_id:
                return True, ""
            tm_a = (
                db.query(TeamMember)
                .filter(
                    TeamMember.user_id == actor.id,
                    TeamMember.is_active == True,
                )
                .first()
            )
            tm_t = (
                db.query(TeamMember)
                .filter(
                    TeamMember.user_id == target.id,
                    TeamMember.is_active == True,
                )
                .first()
            )
            if tm_a and tm_t and tm_a.team_id == tm_t.team_id:
                return True, ""
            return False, "Team leads can only assign OKRs to members of their team"
        if actor_role in (
            SystemRole.DEPT_HEAD,
            SystemRole.PLANT_HEAD,
            SystemRole.CEO,
            SystemRole.SUPER_ADMIN,
        ):
            return True, ""
        return False, f"Role {actor.system_role} cannot assign individual OKRs to others"

    if lvl == "TEAM":
        if actor_role in (
            SystemRole.MANAGER,
            SystemRole.DEPT_HEAD,
            SystemRole.PLANT_HEAD,
            SystemRole.CEO,
            SystemRole.SUPER_ADMIN,
        ):
            return True, ""
        return False, "Only managers and above may create team OKRs for others"

    return True, ""


def resolve_team_okr_owner_id(
    team_id: str | None,
    creator: User,
    requested_owner_id: str | None,
    db: Session,
) -> str:
    """
    Team OKRs should be owned by the team lead so they submit team progress.
    Falls back to creator when no lead is configured.
    """
    if requested_owner_id:
        return requested_owner_id
    if team_id:
        team = db.query(Team).filter(Team.id == team_id).first()
        if team and team.lead_id:
            return team.lead_id
    return creator.id
