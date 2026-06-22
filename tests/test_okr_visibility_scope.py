"""Hierarchical OKR visibility: subtree + one-level parent peek."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import server.models  # noqa: F401
from server.models import Base, Department, Objective, OrgNode, Organization, Team, User
from server.services.okr_visibility_service import (
    apply_okr_visibility_filter,
    build_visibility_filter,
    get_user_okr_scope,
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    s = Session()
    try:
        yield s
    finally:
        s.close()


def _seed_hierarchy(s):
    org = Organization(id=str(uuid.uuid4()), name="Test Org")
    east = OrgNode(
        id="region-east",
        org_id=org.id,
        name="East",
        node_type="REGION",
        path="/region-east",
        depth=0,
        is_active=True,
    )
    west = OrgNode(
        id="region-west",
        org_id=org.id,
        name="West",
        node_type="REGION",
        path="/region-west",
        depth=0,
        is_active=True,
    )
    plant_e1 = OrgNode(
        id="plant-e1",
        org_id=org.id,
        name="East Plant 1",
        node_type="PLANT",
        parent_id=east.id,
        path="/region-east/plant-e1",
        depth=1,
        is_active=True,
    )
    dept_e1 = Department(
        id="dept-e1",
        org_id=org.id,
        name="Production",
        plant_id=plant_e1.id,
    )
    team_e1 = Team(id="team-e1", org_id=org.id, name="Shift A", department_id=dept_e1.id)

    cycle_id = str(uuid.uuid4())
    objs = [
        Objective(
            id="obj-org",
            org_id=org.id,
            title="Org OKR",
            level="ORGANIZATION",
            cycle_id=cycle_id,
            owner_id="ceo",
        ),
        Objective(
            id="obj-east",
            org_id=org.id,
            title="East Region",
            level="REGION",
            region_id=east.id,
            cycle_id=cycle_id,
            owner_id="east-head",
        ),
        Objective(
            id="obj-west",
            org_id=org.id,
            title="West Region",
            level="REGION",
            region_id=west.id,
            cycle_id=cycle_id,
            owner_id="west-head",
        ),
        Objective(
            id="obj-plant-e1",
            org_id=org.id,
            title="East Plant 1",
            level="PLANT",
            region_id=east.id,
            plant_id=plant_e1.id,
            cycle_id=cycle_id,
            owner_id="plant-head",
        ),
        Objective(
            id="obj-dept-e1",
            org_id=org.id,
            title="Production Dept",
            level="DEPARTMENT",
            plant_id=plant_e1.id,
            department_id=dept_e1.id,
            cycle_id=cycle_id,
            owner_id="dept-head",
        ),
    ]
    east_head = User(
        id="east-head",
        org_id=org.id,
        email="east@test.com",
        password_hash="x",
        name="East Head",
        system_role="VP_OPERATIONS",
        org_node_id=east.id,
    )
    plant_head = User(
        id="plant-head",
        org_id=org.id,
        email="plant@test.com",
        password_hash="x",
        name="Plant Head",
        system_role="PLANT_HEAD",
        plant_id=plant_e1.id,
        org_node_id=plant_e1.id,
    )
    s.add_all([org, east, west, plant_e1, dept_e1, team_e1, east_head, plant_head, *objs])
    s.commit()
    return org, east_head, plant_head


def test_regional_head_sees_east_subtree_and_org_parent_only(db_session):
    s = db_session
    org, east_head, _ = _seed_hierarchy(s)
    scope = get_user_okr_scope(east_head, s)
    assert scope["level"] == "REGION"
    assert scope["region_id"] == "region-east"

    q = s.query(Objective).filter(Objective.org_id == org.id)
    q = apply_okr_visibility_filter(q, east_head, s, org.id)
    ids = {o.id for o in q.all()}
    assert "obj-org" in ids
    assert "obj-east" in ids
    assert "obj-plant-e1" in ids
    assert "obj-dept-e1" in ids
    assert "obj-west" not in ids


def test_plant_head_sees_region_parent_and_plant_subtree_not_west(db_session):
    s = db_session
    org, _, plant_head = _seed_hierarchy(s)
    q = s.query(Objective).filter(Objective.org_id == org.id)
    q = apply_okr_visibility_filter(q, plant_head, s, org.id)
    ids = {o.id for o in q.all()}
    assert "obj-east" in ids
    assert "obj-plant-e1" in ids
    assert "obj-dept-e1" in ids
    assert "obj-org" not in ids
    assert "obj-west" not in ids


def test_ceo_unrestricted(db_session):
    s = db_session
    org, east_head, _ = _seed_hierarchy(s)
    ceo = User(
        id="ceo",
        org_id=org.id,
        email="ceo@test.com",
        password_hash="x",
        name="CEO",
        system_role="CEO",
    )
    s.add(ceo)
    s.commit()
    filt = build_visibility_filter(ceo, s, org.id)
    assert filt is None


def test_manager_without_team_sees_department_team_and_individual_okrs(db_session):
    """Managers are department-scoped; they must see OKRs they create for teams/employees."""
    s = db_session
    org, _, _ = _seed_hierarchy(s)
    cycle_id = str(uuid.uuid4())

    manager = User(
        id="mgr",
        org_id=org.id,
        email="mgr@test.com",
        password_hash="x",
        name="Production Manager",
        system_role="MANAGER",
        plant_id="plant-e1",
        department_id="dept-e1",
    )
    team_okr = Objective(
        id="obj-team",
        org_id=org.id,
        title="Team throughput",
        level="TEAM",
        plant_id="plant-e1",
        department_id="dept-e1",
        team_id="team-e1",
        cycle_id=cycle_id,
        owner_id="lead",
    )
    individual_okr = Objective(
        id="obj-ind",
        org_id=org.id,
        title="Individual safety",
        level="INDIVIDUAL",
        plant_id="plant-e1",
        department_id="dept-e1",
        team_id="team-e1",
        cycle_id=cycle_id,
        owner_id="emp",
        assigned_by_id="mgr",
    )
    s.add_all([manager, team_okr, individual_okr])
    s.commit()

    scope = get_user_okr_scope(manager, s)
    assert scope["level"] == "DEPARTMENT"
    assert scope["department_id"] == "dept-e1"

    q = s.query(Objective).filter(Objective.org_id == org.id)
    q = apply_okr_visibility_filter(q, manager, s, org.id)
    ids = {o.id for o in q.all()}
    assert "obj-dept-e1" in ids
    assert "obj-team" in ids
    assert "obj-ind" in ids
    assert "obj-plant-e1" in ids  # parent peek
