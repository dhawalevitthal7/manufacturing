"""
Shared team membership enrollment (used by org team creation and /api/teams member routes).
Keeps roster, User.team_id, and individual OKR linking consistent in one transaction.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from server.models import Department, Objective, Team, TeamMember, User


def user_eligible_for_team_at_plant(
    user: User,
    plant_id: str,
    department_ids_in_plant: set[str],
) -> bool:
    """Employee is considered at this plant if assigned to the plant or any department in it."""
    if user.plant_id and user.plant_id == plant_id:
        return True
    if user.department_id and user.department_id in department_ids_in_plant:
        return True
    return False


def enroll_team_member(
    db: Session,
    org_id: str,
    team: Team,
    user_id: str,
    is_team_lead: bool,
) -> TeamMember:
    """
    Add or reactivate a team member, set User.team_id, optional OKR links.
    Caller commits. Raises ValueError for business-rule failures.
    """
    user = db.query(User).filter(User.id == user_id, User.org_id == org_id).first()
    if not user:
        raise ValueError("User not found")

    dept = db.query(Department).filter(Department.id == team.department_id).first()
    if not dept:
        raise ValueError("Department not found")

    plant_id = dept.plant_id
    plant_dept_ids = {
        d.id
        for d in db.query(Department)
        .filter(Department.plant_id == plant_id, Department.org_id == org_id)
        .all()
    }

    if not user_eligible_for_team_at_plant(user, plant_id, plant_dept_ids):
        raise ValueError("User is not assigned to this team's plant")

    existing = (
        db.query(TeamMember)
        .filter(TeamMember.team_id == team.id, TeamMember.user_id == user_id)
        .first()
    )

    if existing and existing.is_active:
        raise ValueError("already_active_member")

    if existing and not existing.is_active:
        existing.is_active = True
        existing.is_team_lead = is_team_lead
        existing.role_in_team = "LEAD" if is_team_lead else "MEMBER"
        db.flush()
        user.team_id = team.id
        db.flush()
        team_member = existing
    else:
        team_member = TeamMember(
            org_id=org_id,
            team_id=team.id,
            user_id=user_id,
            is_team_lead=is_team_lead,
            role_in_team="LEAD" if is_team_lead else "MEMBER",
        )
        db.add(team_member)
        db.flush()
        user.team_id = team.id
        db.flush()

    if is_team_lead:
        team.lead_id = user_id
        db.flush()

    team_okrs = (
        db.query(Objective)
        .filter(
            Objective.team_id == team.id,
            Objective.level == "TEAM",
            Objective.status == "ACTIVE",
            Objective.org_id == org_id,
        )
        .all()
    )
    employee_individual_okrs = (
        db.query(Objective)
        .filter(
            Objective.owner_id == user_id,
            Objective.level == "INDIVIDUAL",
            Objective.status == "ACTIVE",
            Objective.team_id.is_(None),
            Objective.org_id == org_id,
        )
        .all()
    )
    for emp_okr in employee_individual_okrs:
        if team_okrs:
            emp_okr.parent_id = team_okrs[0].id
        emp_okr.team_id = team.id
        db.add(emp_okr)

    db.flush()
    return team_member
