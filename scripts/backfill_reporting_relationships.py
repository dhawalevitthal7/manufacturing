"""Backfill DIRECT reporting relationships from team/org/department structure."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from server.database import SessionLocal
from server.models import Organization, User
from server.services.manager_resolution import resolve_manager_for_employee


def main():
    db = SessionLocal()
    try:
        orgs = db.query(Organization).all()
        created = 0
        skipped = 0
        for org in orgs:
            for emp in db.query(User).filter(User.org_id == org.id, User.is_active == True).all():
                mid, source = resolve_manager_for_employee(
                    db, emp.id, org.id, persist_if_missing=True
                )
                if mid:
                    created += 1
                    print(f"  {emp.name} -> {source}")
                else:
                    skipped += 1
        print(f"Done. Resolved: {created}, no manager: {skipped}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
