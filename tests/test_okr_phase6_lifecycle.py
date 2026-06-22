"""Phase 6: employee draft OKR lifecycle."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import server.models  # noqa: F401
from server.models import (
    Base,
    Organization,
    User,
    Objective,
    UserPermissionProfile,
    ReportingRelationship,
)
from server.services.okr_lifecycle_service import (
    OKR_STATUS_ACTIVE,
    OKR_STATUS_DRAFT,
    OKR_STATUS_PENDING,
    OKR_STATUS_REJECTED,
    activate_okr,
    can_user_draft_objective,
    publish_ceo_okr,
    submit_for_approval,
    admin_approve_okr,
    admin_reject_okr,
)
from server.roles import SystemRole


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


def _perm(s, user_id, org_id, role: str):
    s.add(
        UserPermissionProfile(
            id=str(uuid.uuid4()),
            org_id=org_id,
            user_id=user_id,
            system_role=role,
            scope_type="ORGANIZATION" if role == "CEO" else "TEAM",
        )
    )


def test_employee_can_draft_individual_okr(db_session):
    s = db_session
    org = Organization(id=str(uuid.uuid4()), name="O6")
    emp = User(
        id=str(uuid.uuid4()),
        org_id=org.id,
        email="e@t.com",
        password_hash="x",
        name="Emp",
        system_role="EMPLOYEE",
    )
    s.add_all([org, emp])
    _perm(s, emp.id, org.id, "EMPLOYEE")
    s.commit()
    ok, _ = can_user_draft_objective(emp, "INDIVIDUAL", emp.id)
    assert ok is True


def test_submit_and_activate_flow(db_session):
    s = db_session
    org = Organization(id=str(uuid.uuid4()), name="O6b")
    mgr = User(
        id=str(uuid.uuid4()),
        org_id=org.id,
        email="m@t.com",
        password_hash="x",
        name="Mgr",
        system_role="MANAGER",
        team_id="team-1",
    )
    emp = User(
        id=str(uuid.uuid4()),
        org_id=org.id,
        email="e2@t.com",
        password_hash="x",
        name="Emp2",
        system_role="EMPLOYEE",
        team_id="team-1",
    )
    s.add_all([org, mgr, emp])
    _perm(s, mgr.id, org.id, "MANAGER")
    _perm(s, emp.id, org.id, "EMPLOYEE")
    s.add(
        ReportingRelationship(
            id=str(uuid.uuid4()),
            org_id=org.id,
            employee_id=emp.id,
            manager_id=mgr.id,
            relationship_type="DIRECT",
            is_active=True,
        )
    )
    team_okr = Objective(
        id=str(uuid.uuid4()),
        org_id=org.id,
        owner_id=mgr.id,
        title="Team OKR",
        level="TEAM",
        team_id="team-1",
        okr_status=OKR_STATUS_ACTIVE,
    )
    ind = Objective(
        id=str(uuid.uuid4()),
        org_id=org.id,
        owner_id=emp.id,
        title="My OKR",
        level="INDIVIDUAL",
        team_id="team-1",
        parent_id=team_okr.id,
        okr_status=OKR_STATUS_DRAFT,
    )
    s.add_all([team_okr, ind])
    s.commit()

    result = submit_for_approval(s, ind, org.id, emp)
    s.commit()
    s.refresh(ind)
    assert ind.okr_status == OKR_STATUS_PENDING
    assert ind.pending_approver_user_id == mgr.id

    activate_okr(ind, s)
    s.commit()
    s.refresh(ind)
    assert ind.okr_status == OKR_STATUS_ACTIVE
    assert ind.kr_baseline_locked is True


def test_ceo_self_publish(db_session):
    s = db_session
    org = Organization(id=str(uuid.uuid4()), name="O6c")
    ceo = User(
        id=str(uuid.uuid4()),
        org_id=org.id,
        email="ceo@t.com",
        password_hash="x",
        name="CEO",
        system_role="CEO",
    )
    s.add_all([org, ceo])
    _perm(s, ceo.id, org.id, "CEO")
    okr = Objective(
        id=str(uuid.uuid4()),
        org_id=org.id,
        owner_id=ceo.id,
        title="Org strat",
        level="ORGANIZATION",
        okr_status=OKR_STATUS_DRAFT,
    )
    s.add(okr)
    s.commit()
    publish_ceo_okr(s, okr, ceo, org.id, ceo.id)
    s.commit()
    s.refresh(okr)
    assert okr.okr_status == OKR_STATUS_ACTIVE


def test_admin_approve_requires_override_reason_in_service(db_session):
    s = db_session
    org = Organization(id=str(uuid.uuid4()), name="O6d")
    sa = User(
        id=str(uuid.uuid4()),
        org_id=org.id,
        email="sa@t.com",
        password_hash="x",
        name="SA",
        system_role="SUPER_ADMIN",
    )
    okr = Objective(
        id=str(uuid.uuid4()),
        org_id=org.id,
        owner_id=sa.id,
        title="Draft",
        level="INDIVIDUAL",
        okr_status=OKR_STATUS_PENDING,
    )
    s.add_all([org, sa, okr])
    s.commit()
    admin_approve_okr(s, okr, org.id, sa.id, "support ticket #1")
    s.commit()
    s.refresh(okr)
    assert okr.okr_status == OKR_STATUS_ACTIVE


def test_admin_reject_sets_rejected(db_session):
    s = db_session
    org = Organization(id=str(uuid.uuid4()), name="O6e")
    sa = User(
        id=str(uuid.uuid4()),
        org_id=org.id,
        email="sa2@t.com",
        password_hash="x",
        name="SA2",
        system_role="SUPER_ADMIN",
    )
    okr = Objective(
        id=str(uuid.uuid4()),
        org_id=org.id,
        owner_id=sa.id,
        title="Pending",
        level="INDIVIDUAL",
        okr_status=OKR_STATUS_PENDING,
    )
    s.add_all([org, sa, okr])
    s.commit()
    admin_reject_okr(s, okr, org.id, sa.id, "data fix", "invalid scope")
    s.commit()
    s.refresh(okr)
    assert okr.okr_status == OKR_STATUS_REJECTED
