"""
Reinitialize every UserPermissionProfile from DEFAULT_ROLE_CAPABILITIES.

Operator-run only — not invoked from app startup or Alembic.

Usage (from repository root):

  python scripts/backfill_permission_profiles.py

Each user is processed in its own savepoint: failure rolls back that user only.
Idempotent: a second run typically reports all profiles "unchanged" if the DB
already matches the current defaults.

Run after deploying Phase 3.4 (scoped_region_id migration applied) and before
V3.4 API verification.
"""

from __future__ import annotations

import argparse
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from sqlalchemy.orm import Session  # noqa: E402

from server.database import SessionLocal  # noqa: E402
from server.models import User, UserPermissionProfile  # noqa: E402
from server.permissions_service import (  # noqa: E402
    initialize_user_permissions,
    _profile_capability_signature,
)


def _run(db: Session, *, dry_run: bool) -> int:
    profiles = (
        db.query(UserPermissionProfile)
        .order_by(UserPermissionProfile.user_id)
        .all()
    )
    total = len(profiles)
    reinitialized = 0
    unchanged = 0
    failed = 0
    errors: list[str] = []

    if dry_run:
        print(f"Dry-run: would reinitialize {total} permission profile row(s).")
        return 0

    for perm in profiles:
        user = db.query(User).filter(User.id == perm.user_id).first()
        if not user:
            failed += 1
            errors.append(f"No user for profile user_id={perm.user_id}")
            continue

        before_sig = _profile_capability_signature(perm)

        try:
            with db.begin_nested():
                db.delete(perm)
                db.flush()
                new_profile = initialize_user_permissions(user, db, commit=False)
                after_sig = _profile_capability_signature(new_profile)
                if before_sig == after_sig:
                    unchanged += 1
                else:
                    reinitialized += 1
        except Exception as exc:  # noqa: BLE001 — operational script
            failed += 1
            errors.append(f"user_id={user.id} email={user.email!r}: {exc}")

    db.commit()

    print(
        f"Processed {total} permission profile row(s). "
        f"Reinitialized {reinitialized}. Unchanged {unchanged} (already on current defaults). "
        f"Failed {failed}."
    )
    for line in errors[:50]:
        print(f"  ERROR: {line}", file=sys.stderr)
    if len(errors) > 50:
        print(f"  ... and {len(errors) - 50} more errors", file=sys.stderr)

    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print counts only; do not modify the database.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        return _run(db, dry_run=args.dry_run)
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
