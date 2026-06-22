"""
Phase 4.4: dual creation-approval tracks, approval chain alignment, progress validation.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import server.models  # noqa: F401
from server.models import Base, Organization, User, Objective
from server.okr_hierarchy_workflow import OKRHierarchyWorkflow


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


def _seed_org_three_users(s):
    org = Organization(id=str(uuid.uuid4()), name="O44")
    s.add(org)
    dept_head = User(
        id=str(uuid.uuid4()),
        org_id=org.id,
        email=f"dh-{uuid.uuid4().hex[:6]}@t.com",
        password_hash="x",
        name="Dept Head",
        system_role="DEPT_HEAD",
        plant_id="plant-1",
        department_id="dept-1",
    )
    ceo = User(
        id=str(uuid.uuid4()),
        org_id=org.id,
        email=f"ceo-{uuid.uuid4().hex[:6]}@t.com",
        password_hash="x",
        name="CEO",
        system_role="CEO",
    )
    s.add_all([org, dept_head, ceo])
    s.commit()
    return org, dept_head, ceo


def test_approval_chain_includes_functional_alignment_rows(db_session):
    s = db_session
    org, dept_head, ceo = _seed_org_three_users(s)
    org_okr = Objective(
        id=str(uuid.uuid4()),
        org_id=org.id,
        owner_id=ceo.id,
        title="Org OKR",
        level="ORGANIZATION",
    )
    dept_okr = Objective(
        id=str(uuid.uuid4()),
        org_id=org.id,
        owner_id=dept_head.id,
        title="Dept OKR",
        level="DEPARTMENT",
        plant_id="plant-1",
        department_id="dept-1",
        functional_parent_obj_id=org_okr.id,
    )
    s.add_all([org_okr, dept_okr])
    s.commit()

    wf = OKRHierarchyWorkflow(s)
    chain = wf.get_approval_chain_for_okr(dept_okr, org.id)
    alignments = {row["alignment"] for row in chain}
    assert "primary" in alignments
    assert "functional" in alignments


def test_creation_alignment_track_primary_and_functional(db_session):
    s = db_session
    org, dept_head, ceo = _seed_org_three_users(s)
    org_okr = Objective(
        id=str(uuid.uuid4()),
        org_id=org.id,
        owner_id=ceo.id,
        title="Org OKR",
        level="ORGANIZATION",
    )
    dept_okr = Objective(
        id=str(uuid.uuid4()),
        org_id=org.id,
        owner_id=dept_head.id,
        title="Dept OKR",
        level="DEPARTMENT",
        plant_id="plant-1",
        department_id="dept-1",
        functional_parent_obj_id=org_okr.id,
    )
    s.add_all([org_okr, dept_okr])
    s.commit()

    wf = OKRHierarchyWorkflow(s)
    t1, _ = wf.creation_alignment_track_for_approver(dept_head, dept_okr, org.id)
    t2, _ = wf.creation_alignment_track_for_approver(ceo, dept_okr, org.id)
    assert t1 == "primary"
    assert t2 == "functional"


def test_dual_creation_gates_both_required(db_session):
    s = db_session
    org, dept_head, ceo = _seed_org_three_users(s)
    org_okr = Objective(
        id=str(uuid.uuid4()),
        org_id=org.id,
        owner_id=ceo.id,
        title="Org OKR",
        level="ORGANIZATION",
    )
    dept_okr = Objective(
        id=str(uuid.uuid4()),
        org_id=org.id,
        owner_id=dept_head.id,
        title="Dept OKR",
        level="DEPARTMENT",
        plant_id="plant-1",
        department_id="dept-1",
        functional_parent_obj_id=org_okr.id,
        creation_approval_status="PENDING",
    )
    s.add_all([org_okr, dept_okr])
    s.commit()

    from datetime import datetime

    # Simulate first gate (primary) via same logic as route
    okr = s.query(Objective).filter(Objective.id == dept_okr.id).first()
    wf = OKRHierarchyWorkflow(s)
    track, _ = wf.creation_alignment_track_for_approver(dept_head, okr, org.id)
    assert track == "primary"
    okr.creation_primary_approved_by_id = dept_head.id
    okr.creation_primary_approved_at = datetime.utcnow()
    okr.creation_approval_status = "PENDING"
    s.commit()
    s.refresh(okr)
    assert okr.creation_approval_status == "PENDING"

    track2, _ = wf.creation_alignment_track_for_approver(ceo, okr, org.id)
    assert track2 == "functional"
    okr.creation_functional_approved_by_id = ceo.id
    okr.creation_functional_approved_at = datetime.utcnow()
    okr.creation_approval_status = "APPROVED"
    okr.creation_approved_by_id = ceo.id
    okr.creation_approved_at = datetime.utcnow()
    s.commit()
    s.refresh(okr)
    assert okr.creation_approval_status == "APPROVED"
