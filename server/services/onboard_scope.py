"""Validate and apply hierarchy scope when onboarding employees."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from server.models import Department, OrgNode, Plant, Team, User
from server.roles import SystemRole, normalize_role


def _region_node(db: Session, org_id: str, region_id: str) -> OrgNode:
    node = (
        db.query(OrgNode)
        .filter(
            OrgNode.id == region_id,
            OrgNode.org_id == org_id,
            OrgNode.node_type == "REGION",
            OrgNode.is_active == True,
        )
        .first()
    )
    if not node:
        raise HTTPException(400, "Invalid region")
    return node


def _plant_node(db: Session, org_id: str, plant_id: str) -> OrgNode:
    node = (
        db.query(OrgNode)
        .filter(
            OrgNode.id == plant_id,
            OrgNode.org_id == org_id,
            OrgNode.node_type == "PLANT",
            OrgNode.is_active == True,
        )
        .first()
    )
    if not node:
        raise HTTPException(400, "Invalid plant")
    return node


def _assert_plant_under_region(db: Session, plant_node: OrgNode, region_id: str | None) -> None:
    if not region_id:
        return
    if plant_node.parent_id != region_id:
        raise HTTPException(400, "Plant does not belong to the selected region")


def apply_onboard_hierarchy_scope(
    user: User,
    *,
    org_id: str,
    system_role: str,
    region_id: str | None,
    plant_id: str | None,
    department_id: str | None,
    team_id: str | None,
    db: Session,
) -> None:
    """Set user hierarchy columns from onboarding payload; raises HTTPException(400) on mismatch."""
    role = normalize_role(system_role)

    user.plant_id = None
    user.department_id = None
    user.team_id = None
    user.org_node_id = None

    if role == SystemRole.REGIONAL_HEAD:
        if not region_id:
            raise HTTPException(400, "Region is required for Regional Head")
        region = _region_node(db, org_id, region_id)
        user.org_node_id = region.id
        return

    needs_plant = role in (
        SystemRole.PLANT_HEAD,
        SystemRole.DEPT_HEAD,
        SystemRole.MANAGER,
        SystemRole.TEAM_LEAD,
        SystemRole.SUPERVISOR,
        SystemRole.EMPLOYEE,
    )
    if needs_plant:
        if not plant_id:
            raise HTTPException(400, f"Plant is required for {role.value}")
        plant = db.query(Plant).filter(Plant.id == plant_id, Plant.org_id == org_id).first()
        if not plant:
            raise HTTPException(400, "Invalid plant")
        plant_node = _plant_node(db, org_id, plant_id)
        _assert_plant_under_region(db, plant_node, region_id)
        user.plant_id = plant_id
        user.org_node_id = plant_id

    if role == SystemRole.PLANT_HEAD:
        return

    needs_dept = role in (
        SystemRole.DEPT_HEAD,
        SystemRole.MANAGER,
        SystemRole.TEAM_LEAD,
        SystemRole.SUPERVISOR,
        SystemRole.EMPLOYEE,
    )
    if needs_dept:
        if not department_id:
            raise HTTPException(400, f"Department is required for {role.value}")
        dept = (
            db.query(Department)
            .filter(Department.id == department_id, Department.org_id == org_id)
            .first()
        )
        if not dept:
            raise HTTPException(400, "Invalid department")
        if plant_id and dept.plant_id != plant_id:
            raise HTTPException(400, "Department does not belong to the selected plant")
        user.department_id = department_id
        user.org_node_id = department_id

    if role == SystemRole.DEPT_HEAD:
        return

    needs_team = role in (SystemRole.TEAM_LEAD, SystemRole.EMPLOYEE)
    if needs_team:
        if not team_id:
            raise HTTPException(400, f"Team is required for {role.value}")
        team = db.query(Team).filter(Team.id == team_id, Team.org_id == org_id).first()
        if not team:
            raise HTTPException(400, "Invalid team")
        if department_id and team.department_id != department_id:
            raise HTTPException(400, "Team does not belong to the selected department")
        user.team_id = team_id
        user.org_node_id = team_id
