"""Tests for AI-assisted hierarchical OKR cascading."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import server.models  # noqa: F401
from server.models import Base, KeyResult, Objective, OrgNode, Organization, User
from server.auth import get_password_hash, create_access_token
from server.services.ai_cascade_engine import AICascadeEngine
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
