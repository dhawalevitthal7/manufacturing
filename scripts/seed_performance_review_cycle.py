"""
Seed an active performance review cycle and bulk-initiate reviews for all employees with managers.
Run once: python scripts/seed_performance_review_cycle.py [--org-id ORG_ID]
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from server.database import SessionLocal
from server.models import Organization, User, ReportingRelationship
from server.performance_review_models import (
    PerformanceReviewCycle,
    ReviewCycleType,
    ReviewCycleStatus,
    EmployeePerformanceReview,
)
from server.services.employee_review_service import EmployeeReviewService
from server.services.okr_review_integration import attach_okr_context_to_review
from server.services.manager_resolution import get_manager_id


def _get_skip_manager_id(db, employee_id: str):
    rel = (
        db.query(ReportingRelationship)
        .filter(
            ReportingRelationship.employee_id == employee_id,
            ReportingRelationship.relationship_type == "REVIEWER",
            ReportingRelationship.is_active == True,
        )
        .first()
    )
    return rel.manager_id if rel else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--org-id", default=None)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        org = None
        if args.org_id:
            org = db.query(Organization).filter(Organization.id == args.org_id).first()
        if not org:
            org = db.query(Organization).first()
        if not org:
            print("No organization found.")
            return 1

        existing = (
            db.query(PerformanceReviewCycle)
            .filter(PerformanceReviewCycle.org_id == org.id, PerformanceReviewCycle.status == ReviewCycleStatus.ACTIVE)
            .first()
        )
        if existing:
            cycle = existing
            print(f"Using existing cycle: {cycle.name} ({cycle.id})")
        else:
            now = datetime.utcnow()
            cycle = PerformanceReviewCycle(
                org_id=org.id,
                cycle_type=ReviewCycleType.QUARTERLY,
                name=f"Q{((now.month - 1) // 3) + 1}-{now.year} Performance Review",
                start_date=now - timedelta(days=90),
                end_date=now + timedelta(days=30),
                submission_start=now - timedelta(days=7),
                submission_end=now + timedelta(days=21),
                status=ReviewCycleStatus.ACTIVE,
            )
            db.add(cycle)
            db.commit()
            db.refresh(cycle)
            print(f"Created cycle: {cycle.name} ({cycle.id})")

        review_svc = EmployeeReviewService(db)
        created = 0
        for emp in db.query(User).filter(User.org_id == org.id, User.is_active == True).all():
            manager_id = get_manager_id(db, emp.id, org.id)
            if not manager_id:
                continue
            try:
                review_svc.create_performance_review(
                    org_id=org.id,
                    employee_id=emp.id,
                    manager_id=manager_id,
                    review_cycle_id=cycle.id,
                    review_period_start=cycle.start_date,
                    review_period_end=cycle.end_date,
                )
                rev = (
                    db.query(EmployeePerformanceReview)
                    .filter(
                        EmployeePerformanceReview.employee_id == emp.id,
                        EmployeePerformanceReview.review_cycle_id == cycle.id,
                    )
                    .first()
                )
                if rev:
                    attach_okr_context_to_review(db, rev)
                created += 1
            except ValueError:
                pass

        print(f"Reviews ready: {created}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
