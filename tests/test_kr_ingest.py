"""Phase 8: KR auto-ingest webhook tests."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server.database import Base
from server.models import KeyResult, KRIngestSource, Objective, Organization, User
from server.services.kr_ingest_service import (
    apply_transform,
    generate_ingest_token,
    process_kr_ingest,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    org = Organization(id="org-1", name="Test Org", domain="test.local")
    session.add(org)
    session.add(
        User(
            id="u1",
            org_id="org-1",
            email="a@test.local",
            name="Alice",
            password_hash="x",
            system_role="MANAGER",
        )
    )
    obj = Objective(
        id="obj-1",
        org_id="org-1",
        title="Plant OKR",
        level="PLANT",
        owner_id="u1",
        okr_status="ACTIVE",
    )
    session.add(obj)
    kr = KeyResult(id="kr-1", objective_id="obj-1", title="TPD", target_value=10000, unit="t")
    session.add(kr)
    session.commit()
    yield session
    session.close()


def test_apply_transform():
    assert apply_transform(None, 100) == 100
    assert apply_transform("x / 1000", 5000) == 5.0


def test_ingest_updates_kr(db):
    raw, hashed = generate_ingest_token()
    src = KRIngestSource(
        org_id="org-1",
        key_result_id="kr-1",
        source_system="SAP",
        source_metric_tag="RAJ1.KILN1.TPD",
        api_token_hash=hashed,
        is_active=True,
    )
    db.add(src)
    db.commit()

    result = process_kr_ingest(
        db,
        source_metric_tag="RAJ1.KILN1.TPD",
        value=8432.5,
        raw_token=raw,
    )
    assert result["current_value"] == 8432.5
    kr = db.query(KeyResult).filter(KeyResult.id == "kr-1").first()
    assert kr.current_value == 8432.5


def test_ingest_rejects_bad_token(db):
    _, hashed = generate_ingest_token()
    db.add(
        KRIngestSource(
            org_id="org-1",
            key_result_id="kr-1",
            source_system="MES",
            source_metric_tag="TAG.A",
            api_token_hash=hashed,
        )
    )
    db.commit()
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        process_kr_ingest(db, source_metric_tag="TAG.A", value=1, raw_token="wrong")
    assert exc.value.status_code == 401
