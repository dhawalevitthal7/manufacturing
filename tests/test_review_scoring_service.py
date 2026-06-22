"""Review scoring uses live data — no synthetic 50.0 placeholders for missing inputs."""

from datetime import datetime, timedelta

import pytest

from server.database import SessionLocal
from server.models import User, Objective, KeyResult, Organization
from server.performance_review_models import (
    EmployeePerformanceReview,
    PerformanceReviewCycle,
    ReviewCycleType,
    ReviewCycleStatus,
    ReviewState,
    ReviewSection,
    SectionType,
    ScoringConfiguration,
    ContinuousCheckin,
)
from server.services.review_scoring_service import ReviewScoringService, _weighted_final_score


def test_weighted_final_redistributes_missing_components():
  final, confidence, resolved = _weighted_final_score({
      "okr_achievement": (80.0, 40.0),
      "kr_quality": (None, 20.0),
      "manager_feedback": (None, 15.0),
      "behavioral_competency": (None, 10.0),
      "peer_feedback": (None, 10.0),
      "continuous_checkin": (90.0, 5.0),
  })
  assert final == pytest.approx(81.2, abs=0.2)
  assert confidence == pytest.approx(45.0, abs=0.1)
  assert resolved["okr_achievement"] == 80.0
  assert resolved["continuous_checkin"] == 90.0
  assert resolved["manager_feedback"] is None


@pytest.fixture
def scoring_db():
    db = SessionLocal()
    try:
        org = db.query(Organization).first()
        if not org:
            pytest.skip("No organization in database")
        employee = (
            db.query(User)
            .filter(User.org_id == org.id, User.system_role == "EMPLOYEE")
            .first()
        )
        if not employee:
            pytest.skip("No employee user in database")

        cycle = PerformanceReviewCycle(
            org_id=org.id,
            cycle_type=ReviewCycleType.QUARTERLY,
            name="Test Scoring Cycle",
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow() + timedelta(days=30),
            submission_start=datetime.utcnow() - timedelta(days=7),
            submission_end=datetime.utcnow() + timedelta(days=14),
            status=ReviewCycleStatus.ACTIVE,
        )
        db.add(cycle)
        db.flush()

        manager = (
            db.query(User)
            .filter(User.org_id == org.id, User.system_role == "MANAGER")
            .first()
        )
        if not manager:
            pytest.skip("No manager user in database")

        review = EmployeePerformanceReview(
            org_id=org.id,
            employee_id=employee.id,
            manager_id=manager.id,
            review_cycle_id=cycle.id,
            review_period_start=cycle.start_date,
            review_period_end=cycle.end_date,
            current_state=ReviewState.DRAFT.value,
        )
        db.add(review)
        db.flush()

        if not db.query(ScoringConfiguration).filter(ScoringConfiguration.org_id == org.id).first():
            db.add(ScoringConfiguration(org_id=org.id))

        objective = (
            db.query(Objective)
            .filter(Objective.owner_id == employee.id, Objective.org_id == org.id)
            .first()
        )
        if objective:
            review.okr_ids = [objective.id]

        checkin = ContinuousCheckin(
            org_id=org.id,
            employee_id=employee.id,
            manager_id=manager.id,
            checkin_week=10,
            checkin_date=datetime.utcnow(),
            submitted_at=datetime.utcnow(),
            achievements="Shipped output",
            blockers="None",
            confidence_score=85.0,
            engagement_score=8,
            workflow_status="SUBMITTED",
            status="SUBMITTED",
        )
        db.add(checkin)
        db.commit()
        db.refresh(review)
        yield db, review
    finally:
        db.close()


def test_calculate_final_score_uses_okr_and_checkin_not_placeholders(scoring_db):
    db, review = scoring_db
    service = ReviewScoringService(db)
    final_score, rating, components = service.calculate_final_score(review.id)

    assert components["okr_achievement"] is not None
    assert components["okr_achievement"] != 50.0 or review.okr_achievement_score == 50.0
    assert components["continuous_checkin"] is not None
    assert components["manager_feedback"] is None
    assert components["peer_feedback"] is None
    assert final_score > 0
    assert rating is not None


def test_manager_behavioral_scores_drive_feedback_components(scoring_db):
    db, review = scoring_db
    section = ReviewSection(
        performance_review_id=review.id,
        section_type=SectionType.MANAGER,
        submitted_by_user_id=review.manager_id,
        manager_behavioral_scores={
            "collaboration": 4,
            "ownership": 5,
            "execution": 4,
            "accountability": 4,
        },
        submitted_at=datetime.utcnow(),
    )
    db.add(section)
    db.commit()

    service = ReviewScoringService(db)
    _, _, components = service.calculate_final_score(review.id)

    assert components["manager_feedback"] == pytest.approx(86.7, abs=0.2)
    assert components["kr_quality"] == pytest.approx(80.0, abs=0.1)
    assert components["behavioral_competency"] == pytest.approx(85.0, abs=0.1)
