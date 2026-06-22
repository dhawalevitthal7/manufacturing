"""
Phase 4.3: rollup includes solid parent_id and functional_parent_obj_id edges.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import server.models  # noqa: F401 — register ORM mappers
from server.models import Base, Organization, User, Objective, KeyResult
from server.okr_cascade_service import OKRCascadeService


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


def _org_user(s):
    org = Organization(id=str(uuid.uuid4()), name="V43 Org")
    s.add(org)
    uid = str(uuid.uuid4())
    u = User(
        id=uid,
        org_id=org.id,
        email=f"v43-{uid[:8]}@test.com",
        password_hash="x",
        name="Tester",
    )
    s.add(u)
    s.commit()
    return org, u


def test_v43_functional_only_child_included_in_parent_rollup(db_session):
    """V4.3a: child only aligned via functional_parent_obj_id still rolls into P."""
    s = db_session
    org, u = _org_user(s)
    pid, cid = str(uuid.uuid4()), str(uuid.uuid4())
    p = Objective(
        id=pid,
        org_id=org.id,
        owner_id=u.id,
        title="Parent",
        level="ORGANIZATION",
    )
    c = Objective(
        id=cid,
        org_id=org.id,
        owner_id=u.id,
        title="Child",
        level="INDIVIDUAL",
        parent_id=None,
        functional_parent_obj_id=pid,
    )
    s.add_all([p, c])
    s.commit()
    s.add(
        KeyResult(
            objective_id=cid,
            title="KR",
            target_value=100.0,
            current_value=100.0,
            weight=1.0,
        )
    )
    s.commit()

    OKRCascadeService(s).propagate_progress_upward(cid)
    s.refresh(p)
    assert abs((p.progress or 0) - 100.0) < 0.05


def test_v43_parent_id_only_tree_unchanged(db_session):
    """V4.3b: classic parent_id-only link still aggregates into parent."""
    s = db_session
    org, u = _org_user(s)
    pid, cid = str(uuid.uuid4()), str(uuid.uuid4())
    p = Objective(
        id=pid,
        org_id=org.id,
        owner_id=u.id,
        title="Parent",
        level="ORGANIZATION",
    )
    c = Objective(
        id=cid,
        org_id=org.id,
        owner_id=u.id,
        title="Child",
        level="INDIVIDUAL",
        parent_id=pid,
        functional_parent_obj_id=None,
    )
    s.add_all([p, c])
    s.commit()
    s.add(
        KeyResult(
            objective_id=cid,
            title="KR",
            target_value=100.0,
            current_value=100.0,
            weight=1.0,
        )
    )
    s.commit()

    OKRCascadeService(s).propagate_progress_upward(cid)
    s.refresh(p)
    assert abs((p.progress or 0) - 100.0) < 0.05


def test_v43_dual_edge_same_parent_weights_child_twice_in_average(db_session):
    """
    V4.3c: both parent_id and functional_parent_obj_id -> P: child list is [C, C, …];
    weighted average differs from deduped single edge when another sibling exists.
    """
    s = db_session
    org, u = _org_user(s)
    pid, cid, oid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    p = Objective(
        id=pid,
        org_id=org.id,
        owner_id=u.id,
        title="Parent",
        level="ORGANIZATION",
    )
    o = Objective(
        id=oid,
        org_id=org.id,
        owner_id=u.id,
        title="Sibling",
        level="INDIVIDUAL",
        parent_id=pid,
    )
    c = Objective(
        id=cid,
        org_id=org.id,
        owner_id=u.id,
        title="Dual-linked",
        level="INDIVIDUAL",
        parent_id=pid,
        functional_parent_obj_id=pid,
    )
    s.add_all([p, o, c])
    s.commit()
    s.add_all(
        [
            KeyResult(
                objective_id=cid,
                title="KR-C",
                target_value=100.0,
                current_value=100.0,
                weight=1.0,
            ),
            KeyResult(
                objective_id=oid,
                title="KR-O",
                target_value=100.0,
                current_value=0.0,
                weight=1.0,
            ),
        ]
    )
    s.commit()

    OKRCascadeService(s).propagate_progress_upward(cid)
    s.refresh(p)
    # (0 + 100 + 100) / 3 ≈ 66.7; deduped (0 + 100) / 2 would be 50
    assert abs((p.progress or 0) - 66.7) < 0.15


def test_v43_get_cascade_tree_appends_same_node_twice_for_dual_edges(db_session):
    """Tree builder mirrors dual edges: same child dict may appear twice under one parent."""
    s = db_session
    org, u = _org_user(s)
    pid, cid = str(uuid.uuid4()), str(uuid.uuid4())
    p = Objective(
        id=pid,
        org_id=org.id,
        owner_id=u.id,
        title="Parent",
        level="ORGANIZATION",
    )
    c = Objective(
        id=cid,
        org_id=org.id,
        owner_id=u.id,
        title="Dual",
        level="INDIVIDUAL",
        parent_id=pid,
        functional_parent_obj_id=pid,
    )
    s.add_all([p, c])
    s.commit()

    roots = OKRCascadeService(s).get_cascade_tree(org.id)
    assert len(roots) == 1
    kids = roots[0]["children"]
    assert sum(1 for n in kids if n["id"] == cid) == 2
