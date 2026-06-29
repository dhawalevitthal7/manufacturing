"""Tests for AI-assisted hierarchical OKR cascading."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import server.models  # noqa: F401
from server.models import Base, KeyResult, Objective, OrgNode, Organization, Team, TeamMember, User
from server.auth import get_password_hash, create_access_token
from server.services.ai_cascade_engine import AICascadeEngine, CascadeTarget
from server.services.cascade_ai_prompt import validate_cascade_response
from server.services.cascade_ai_service import CascadeAIService
from server.services.okr_lifecycle_service import (
    OKR_STATUS_ACTIVE,
    OKR_STATUS_AI_DRAFT,
    OKR_STATUS_PENDING_PARENT,
    OKR_STATUS_UNDER_REVIEW,
)
from server.roles import is_ai_cascade_enabled, next_cascade_child_level


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


@pytest.fixture
def org_and_ceo(db_session):
    org = Organization(id=str(uuid.uuid4()), name="Test Org", industry="Manufacturing")
    db_session.add(org)
    db_session.flush()
    ceo = User(
        id=str(uuid.uuid4()),
        org_id=org.id,
        email="ceo@test.local",
        password_hash=get_password_hash("x"),
        name="CEO",
        system_role="CEO",
        is_active=True,
    )
    db_session.add(ceo)
    db_session.commit()
    return org, ceo


def test_all_adjacent_levels_enabled():
    for parent in ("ORGANIZATION", "VERTICAL", "REGION", "PLANT", "DEPARTMENT", "SUB_DEPARTMENT", "TEAM"):
        assert is_ai_cascade_enabled(parent) is True
    assert next_cascade_child_level("TEAM") == "INDIVIDUAL"


def test_validate_cascade_response_requires_objective():
    with pytest.raises(ValueError):
        validate_cascade_response({"key_results": [{"title": "KR", "target": 10, "unit": "%"}]})


def test_validate_cascade_response_normalizes():
    result = validate_cascade_response(
        {
            "objective": "Improve dispatch",
            "description": "Regional plan",
            "key_results": [{"title": "Reduce delays", "target": 15, "unit": "%"}],
            "confidence": 0.8,
            "alignment_score": 85,
            "reasoning": "Supports parent",
        }
    )
    assert result["objective"] == "Improve dispatch"
    assert len(result["key_results"]) == 1


def test_next_cascade_child_level():
    assert next_cascade_child_level("ORGANIZATION") == "REGION"
    assert next_cascade_child_level("REGION") == "PLANT"
    assert next_cascade_child_level("PLANT") == "DEPARTMENT"
    assert next_cascade_child_level("DEPARTMENT") == "TEAM"
    assert next_cascade_child_level("TEAM") == "INDIVIDUAL"


def test_rule_based_cascade_suggestion():
    svc = CascadeAIService()
    result = svc._rule_based_suggestion(
        parent_objective="Increase Production efficiency by 20%",
        parent_description="Corporate efficiency target",
        parent_level="ORGANIZATION",
        child_level="PLANT",
        scope_name="Plant A",
        parent_key_results=[{"title": "Reduce energy use", "target_value": 10, "unit": "%"}],
    )
    assert "Plant A" in result["objective"]
    assert result["source"] == "rule_based"
    assert len(result["key_results"]) >= 3
    # KRs must be level. operational titles — not prefixed parent KR copy
    kr_titles = " ".join(kr["title"] for kr in result["key_results"])
    assert "Reduce energy use" not in kr_titles
    assert any("OEE" in kr["title"] or "clinker" in kr["title"].lower() for kr in result["key_results"])


def test_ai_draft_lifecycle(db_session, org_and_ceo):
    org, ceo = org_and_ceo
    region = OrgNode(
        id=str(uuid.uuid4()),
        org_id=org.id,
        parent_id=org.id,
        node_type="REGION",
        name="West",
        path=f"{org.id}.{uuid.uuid4()}",
        depth=1,
        is_active=True,
    )
    db_session.add(region)
    rh = User(
        id=str(uuid.uuid4()),
        org_id=org.id,
        email="rh@test.local",
        password_hash=get_password_hash("x"),
        name="Regional Head",
        system_role="REGIONAL_HEAD",
        org_node_id=region.id,
        is_active=True,
    )
    db_session.add(rh)
    region.head_user_id = rh.id

    parent = Objective(
        id=str(uuid.uuid4()),
        org_id=org.id,
        owner_id=ceo.id,
        title="Org OKR",
        level="ORGANIZATION",
        okr_status=OKR_STATUS_ACTIVE,
        status="ACTIVE",
        allows_cascade=True,
        ai_generated=False,
    )
    db_session.add(parent)
    db_session.add(
        KeyResult(
            id=str(uuid.uuid4()),
            objective_id=parent.id,
            title="KR1",
            target_value=100,
            current_value=0,
            unit="%",
        )
    )
    db_session.commit()

    engine = AICascadeEngine(db_session)
    created = engine.generate_cascade_for_parent(parent.id, org.id)
    assert len(created) >= 1

    draft = db_session.query(Objective).filter(Objective.id == created[0]).first()
    assert draft.okr_status == OKR_STATUS_AI_DRAFT
    assert draft.ai_generated is True
    assert draft.parent_id == parent.id

    engine.start_review(draft, rh)
    assert draft.okr_status == OKR_STATUS_UNDER_REVIEW

    engine.submit_for_parent_approval(draft, rh)
    assert draft.okr_status == OKR_STATUS_PENDING_PARENT
    assert draft.pending_approver_user_id == ceo.id

    engine.approve_by_parent(draft, ceo)
    assert draft.okr_status == OKR_STATUS_ACTIVE
    assert draft.approved_by_parent_id == ceo.id


def test_region_to_plant_cascade(db_session, org_and_ceo):
    org, ceo = org_and_ceo
    region_id = str(uuid.uuid4())
    region = OrgNode(
        id=region_id,
        org_id=org.id,
        parent_id=org.id,
        node_type="REGION",
        name="North",
        path=f"{org.id}.{region_id}",
        depth=1,
        is_active=True,
    )
    plant_id = str(uuid.uuid4())
    plant = OrgNode(
        id=plant_id,
        org_id=org.id,
        parent_id=region_id,
        node_type="PLANT",
        name="Plant 1",
        path=f"{org.id}.{region_id}.{plant_id}",
        depth=2,
        is_active=True,
    )
    ph = User(
        id=str(uuid.uuid4()),
        org_id=org.id,
        email="ph@test.local",
        password_hash=get_password_hash("x"),
        name="Plant Head",
        system_role="PLANT_HEAD",
        org_node_id=plant_id,
        is_active=True,
    )
    db_session.add_all([region, plant, ph])
    plant.head_user_id = ph.id

    regional_okr = Objective(
        id=str(uuid.uuid4()),
        org_id=org.id,
        owner_id=ceo.id,
        title="Regional OKR",
        level="REGION",
        region_id=region_id,
        okr_status=OKR_STATUS_ACTIVE,
        status="ACTIVE",
        allows_cascade=True,
    )
    db_session.add(regional_okr)
    db_session.commit()

    engine = AICascadeEngine(db_session)
    created = engine.generate_cascade_for_parent(regional_okr.id, org.id)
    assert len(created) == 1
    draft = db_session.query(Objective).filter(Objective.id == created[0]).first()
    assert draft.level == "PLANT"
    assert draft.plant_id == plant_id


def test_region_to_multiple_plants_cascade(db_session, org_and_ceo):
    """Each plant under a region gets its own AI draft (not one draft per region)."""
    org, ceo = org_and_ceo
    region_id = str(uuid.uuid4())
    region = OrgNode(
        id=region_id,
        org_id=org.id,
        parent_id=org.id,
        node_type="REGION",
        name="West",
        path=f"{org.id}.{region_id}",
        depth=1,
        is_active=True,
    )
    plant_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    plants = []
    heads = []
    for i, pid in enumerate(plant_ids):
        plants.append(
            OrgNode(
                id=pid,
                org_id=org.id,
                parent_id=region_id,
                node_type="PLANT",
                name=f"Plant {i + 1}",
                path=f"{org.id}.{region_id}.{pid}",
                depth=2,
                is_active=True,
            )
        )
        head = User(
            id=str(uuid.uuid4()),
            org_id=org.id,
            email=f"ph{i}@test.local",
            password_hash=get_password_hash("x"),
            name=f"Plant Head {i + 1}",
            system_role="PLANT_HEAD",
            org_node_id=pid,
            is_active=True,
        )
        heads.append(head)
        plants[i].head_user_id = head.id

    db_session.add(region)
    db_session.add_all(plants + heads)

    regional_okr = Objective(
        id=str(uuid.uuid4()),
        org_id=org.id,
        owner_id=ceo.id,
        title="Regional OKR multi-plant",
        level="REGION",
        region_id=region_id,
        okr_status=OKR_STATUS_ACTIVE,
        status="ACTIVE",
        allows_cascade=True,
    )
    db_session.add(regional_okr)
    db_session.commit()

    engine = AICascadeEngine(db_session)
    created = engine.generate_cascade_for_parent(regional_okr.id, org.id)
    assert len(created) == 2

    drafts = (
        db_session.query(Objective)
        .filter(Objective.ai_generated_from_objective_id == regional_okr.id)
        .all()
    )
    assert len(drafts) == 2
    assert {d.plant_id for d in drafts} == set(plant_ids)
    assert {d.owner_id for d in drafts} == {h.id for h in heads}


@pytest.mark.parametrize(
    "child_level,scope_field,scope_a,scope_b,collision_field",
    [
        ("PLANT", "plant_id", "plant-a", "plant-b", "region_id"),
        ("DEPARTMENT", "department_id", "dept-a", "dept-b", "plant_id"),
        ("TEAM", "team_id", "team-a", "team-b", "department_id"),
    ],
)
def test_draft_exists_scoped_per_sibling_not_ancestor(
    db_session, org_and_ceo, child_level, scope_field, scope_a, scope_b, collision_field
):
    """Sibling scopes must not block each other (regression for region-only duplicate bug)."""
    org, ceo = org_and_ceo
    parent_id = str(uuid.uuid4())
    shared_scope = {collision_field: "shared-ancestor-id"}

    existing_kwargs = {
        "id": str(uuid.uuid4()),
        "org_id": org.id,
        "owner_id": ceo.id,
        "title": f"Existing {child_level} draft",
        "level": child_level,
        "okr_status": OKR_STATUS_AI_DRAFT,
        "status": "ACTIVE",
        "ai_generated": True,
        "ai_generated_from_objective_id": parent_id,
        scope_field: scope_a,
        **shared_scope,
    }
    db_session.add(Objective(**existing_kwargs))
    db_session.commit()

    engine = AICascadeEngine(db_session)
    target_a = CascadeTarget(
        scope_id=scope_a,
        scope_name="Scope A",
        owner_id=ceo.id,
        scope_metadata={},
        **{scope_field: scope_a, **shared_scope},
    )
    target_b = CascadeTarget(
        scope_id=scope_b,
        scope_name="Scope B",
        owner_id=ceo.id,
        scope_metadata={},
        **{scope_field: scope_b, **shared_scope},
    )

    assert engine._draft_exists(parent_id, child_level, target_a) is True
    assert engine._draft_exists(parent_id, child_level, target_b) is False


def test_draft_exists_scoped_per_individual_owner(db_session, org_and_ceo):
    org, ceo = org_and_ceo
    parent_id = str(uuid.uuid4())
    team_id = str(uuid.uuid4())
    user_a = str(uuid.uuid4())
    user_b = str(uuid.uuid4())

    db_session.add(
        Objective(
            id=str(uuid.uuid4()),
            org_id=org.id,
            owner_id=user_a,
            title="Individual A",
            level="INDIVIDUAL",
            team_id=team_id,
            okr_status=OKR_STATUS_AI_DRAFT,
            status="ACTIVE",
            ai_generated=True,
            ai_generated_from_objective_id=parent_id,
        )
    )
    db_session.commit()

    engine = AICascadeEngine(db_session)
    assert engine._draft_exists(
        parent_id,
        "INDIVIDUAL",
        CascadeTarget(
            scope_id=user_a,
            scope_name="A",
            owner_id=user_a,
            scope_metadata={},
            team_id=team_id,
        ),
    )
    assert not engine._draft_exists(
        parent_id,
        "INDIVIDUAL",
        CascadeTarget(
            scope_id=user_b,
            scope_name="B",
            owner_id=user_b,
            scope_metadata={},
            team_id=team_id,
        ),
    )


def test_plant_to_multiple_departments_cascade(db_session, org_and_ceo):
    org, ceo = org_and_ceo
    region_id = str(uuid.uuid4())
    plant_id = str(uuid.uuid4())
    region = OrgNode(
        id=region_id,
        org_id=org.id,
        parent_id=org.id,
        node_type="REGION",
        name="West",
        path=f"{org.id}.{region_id}",
        depth=1,
        is_active=True,
    )
    plant = OrgNode(
        id=plant_id,
        org_id=org.id,
        parent_id=region_id,
        node_type="PLANT",
        name="Awarpur",
        path=f"{org.id}.{region_id}.{plant_id}",
        depth=2,
        is_active=True,
    )
    dept_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    depts = []
    heads = []
    for i, did in enumerate(dept_ids):
        depts.append(
            OrgNode(
                id=did,
                org_id=org.id,
                parent_id=plant_id,
                node_type="DEPARTMENT",
                name=f"Dept {i + 1}",
                path=f"{plant.path}.{did}",
                depth=3,
                is_active=True,
            )
        )
        head = User(
            id=str(uuid.uuid4()),
            org_id=org.id,
            email=f"hod{i}@test.local",
            password_hash=get_password_hash("x"),
            name=f"HOD {i + 1}",
            system_role="DEPT_HEAD",
            org_node_id=did,
            is_active=True,
        )
        heads.append(head)
        depts[i].head_user_id = head.id

    db_session.add(region)
    db_session.add(plant)
    db_session.add_all(depts + heads)

    plant_okr = Objective(
        id=str(uuid.uuid4()),
        org_id=org.id,
        owner_id=ceo.id,
        title="Plant OKR multi-dept",
        level="PLANT",
        region_id=region_id,
        plant_id=plant_id,
        okr_status=OKR_STATUS_ACTIVE,
        status="ACTIVE",
        allows_cascade=True,
    )
    db_session.add(plant_okr)
    db_session.commit()

    engine = AICascadeEngine(db_session)
    created = engine.generate_cascade_for_parent(plant_okr.id, org.id)
    assert len(created) == 2

    drafts = (
        db_session.query(Objective)
        .filter(Objective.ai_generated_from_objective_id == plant_okr.id)
        .all()
    )
    assert len(drafts) == 2
    assert {d.department_id for d in drafts} == set(dept_ids)


def test_department_to_multiple_teams_cascade(db_session, org_and_ceo):
    org, ceo = org_and_ceo
    region_id = str(uuid.uuid4())
    plant_id = str(uuid.uuid4())
    dept_id = str(uuid.uuid4())
    dept = OrgNode(
        id=dept_id,
        org_id=org.id,
        parent_id=plant_id,
        node_type="DEPARTMENT",
        name="Production",
        path=f"{org.id}.{region_id}.{plant_id}.{dept_id}",
        depth=3,
        is_active=True,
    )
    team_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    teams = []
    leads = []
    for i, tid in enumerate(team_ids):
        teams.append(
            OrgNode(
                id=tid,
                org_id=org.id,
                parent_id=dept_id,
                node_type="TEAM",
                name=f"Shift {i + 1}",
                path=f"{dept.path}.{tid}",
                depth=4,
                is_active=True,
            )
        )
        lead = User(
            id=str(uuid.uuid4()),
            org_id=org.id,
            email=f"lead{i}@test.local",
            password_hash=get_password_hash("x"),
            name=f"Lead {i + 1}",
            system_role="TEAM_LEAD",
            org_node_id=tid,
            is_active=True,
        )
        leads.append(lead)
        teams[i].head_user_id = lead.id

    db_session.add(dept)
    db_session.add_all(teams + leads)

    dept_okr = Objective(
        id=str(uuid.uuid4()),
        org_id=org.id,
        owner_id=ceo.id,
        title="Dept OKR multi-team",
        level="DEPARTMENT",
        region_id=region_id,
        plant_id=plant_id,
        department_id=dept_id,
        okr_status=OKR_STATUS_ACTIVE,
        status="ACTIVE",
        allows_cascade=True,
    )
    db_session.add(dept_okr)
    db_session.commit()

    engine = AICascadeEngine(db_session)
    created = engine.generate_cascade_for_parent(dept_okr.id, org.id)
    assert len(created) == 2

    drafts = (
        db_session.query(Objective)
        .filter(Objective.ai_generated_from_objective_id == dept_okr.id)
        .all()
    )
    assert {d.team_id for d in drafts} == set(team_ids)


def test_team_to_multiple_individuals_cascade(db_session, org_and_ceo):
    org, ceo = org_and_ceo
    team_id = str(uuid.uuid4())
    team = Team(
        id=team_id,
        org_id=org.id,
        department_id=str(uuid.uuid4()),
        name="Kiln Shift A",
        is_active=True,
    )
    db_session.add(team)

    employees = []
    for i in range(2):
        emp = User(
            id=str(uuid.uuid4()),
            org_id=org.id,
            email=f"emp{i}@test.local",
            password_hash=get_password_hash("x"),
            name=f"Employee {i + 1}",
            system_role="EMPLOYEE",
            is_active=True,
        )
        employees.append(emp)
        db_session.add(
            TeamMember(org_id=org.id, team_id=team_id, user_id=emp.id, is_active=True)
        )
    db_session.add_all(employees)

    team_okr = Objective(
        id=str(uuid.uuid4()),
        org_id=org.id,
        owner_id=ceo.id,
        title="Team OKR multi-individual",
        level="TEAM",
        team_id=team_id,
        okr_status=OKR_STATUS_ACTIVE,
        status="ACTIVE",
        allows_cascade=True,
    )
    db_session.add(team_okr)
    db_session.commit()

    engine = AICascadeEngine(db_session)
    created = engine.generate_cascade_for_parent(team_okr.id, org.id)
    assert len(created) == 2

    drafts = (
        db_session.query(Objective)
        .filter(Objective.ai_generated_from_objective_id == team_okr.id)
        .all()
    )
    assert {d.owner_id for d in drafts} == {e.id for e in employees}


def test_duplicate_prevention(db_session, org_and_ceo):
    org, ceo = org_and_ceo
    region = OrgNode(
        id=str(uuid.uuid4()),
        org_id=org.id,
        parent_id=org.id,
        node_type="REGION",
        name="North",
        path=str(uuid.uuid4()),
        depth=1,
        is_active=True,
    )
    db_session.add(region)
    rh = User(
        id=str(uuid.uuid4()),
        org_id=org.id,
        email="rh2@test.local",
        password_hash=get_password_hash("x"),
        name="RH2",
        system_role="REGIONAL_HEAD",
        org_node_id=region.id,
        is_active=True,
    )
    db_session.add(rh)
    region.head_user_id = rh.id

    parent = Objective(
        id=str(uuid.uuid4()),
        org_id=org.id,
        owner_id=ceo.id,
        title="Org OKR 2",
        level="ORGANIZATION",
        okr_status=OKR_STATUS_ACTIVE,
        status="ACTIVE",
        allows_cascade=True,
    )
    db_session.add(parent)
    db_session.commit()

    engine = AICascadeEngine(db_session)
    first = engine.generate_cascade_for_parent(parent.id, org.id)
    second = engine.generate_cascade_for_parent(parent.id, org.id)
    assert len(first) >= 1
    assert len(second) == 0


def test_api_ai_drafts_endpoint(db_session, org_and_ceo):
    from fastapi.testclient import TestClient
    from server.database import get_db
    from main import app

    org, ceo = org_and_ceo
    region = OrgNode(
        id=str(uuid.uuid4()),
        org_id=org.id,
        parent_id=org.id,
        node_type="REGION",
        name="East",
        path=str(uuid.uuid4()),
        depth=1,
        is_active=True,
    )
    db_session.add(region)
    rh = User(
        id=str(uuid.uuid4()),
        org_id=org.id,
        email="rh3@test.local",
        password_hash=get_password_hash("x"),
        name="RH3",
        system_role="REGIONAL_HEAD",
        org_node_id=region.id,
        is_active=True,
    )
    db_session.add(rh)
    region.head_user_id = rh.id

    parent = Objective(
        id=str(uuid.uuid4()),
        org_id=org.id,
        owner_id=ceo.id,
        title="Org OKR API",
        level="ORGANIZATION",
        okr_status=OKR_STATUS_ACTIVE,
        status="ACTIVE",
        allows_cascade=True,
    )
    db_session.add(parent)
    db_session.commit()

    AICascadeEngine(db_session).generate_cascade_for_parent(parent.id, org.id)
    db_session.commit()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    token = create_access_token(
        {"sub": rh.id, "org_id": org.id, "role": "REGIONAL_HEAD", "email": rh.email}
    )
    resp = client.get(
        "/api/okrs/ai-drafts",
        headers={"Authorization": f"Bearer {token}"},
    )
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["okr_status"] == "AI_DRAFT"
