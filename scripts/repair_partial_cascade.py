"""
Repair partial AI cascades — re-generate missing child AI drafts.

Use when a parent OKR is ACTIVE but some sibling scopes (plants, depts, teams,
individuals) never received AI drafts due to the old region-only duplicate bug.

Usage:
  python scripts/repair_partial_cascade.py
  python scripts/repair_partial_cascade.py <parent_objective_id>
"""
from __future__ import annotations

import sys

from server.database import SessionLocal
from server.models import Objective
from server.roles import is_ai_cascade_enabled, next_cascade_child_level
from server.services.ai_cascade_engine import AICascadeEngine
from server.services.okr_lifecycle_service import OKR_STATUS_ACTIVE


def repair_parent(engine: AICascadeEngine, parent: Objective) -> int:
    created = engine.generate_cascade_for_parent(parent.id, parent.org_id)
    return len(created)


def main() -> None:
    parent_filter = sys.argv[1] if len(sys.argv) > 1 else None
    db = SessionLocal()
    try:
        q = db.query(Objective).filter(
            Objective.okr_status == OKR_STATUS_ACTIVE,
            Objective.allows_cascade == True,  # noqa: E712
            Objective.ai_generated == False,  # noqa: E712
        )
        if parent_filter:
            q = q.filter(Objective.id == parent_filter)

        parents = q.order_by(Objective.level, Objective.created_at).all()
        engine = AICascadeEngine(db)
        total_created = 0
        repaired = 0

        print(f"Checking {len(parents)} ACTIVE parent OKR(s) for missing child drafts...\n")

        for parent in parents:
            level = (parent.level or "").upper()
            if not is_ai_cascade_enabled(level):
                continue
            child_level = next_cascade_child_level(level)
            if not child_level:
                continue

            targets = engine._resolve_child_targets(  # noqa: SLF001
                parent.org_id, level, child_level, parent
            )
            if not targets:
                continue

            existing = (
                db.query(Objective)
                .filter(
                    Objective.ai_generated_from_objective_id == parent.id,
                    Objective.level == child_level,
                )
                .count()
            )
            missing = len(targets) - existing
            if missing <= 0:
                continue

            print(
                f"Repair: [{level}] {parent.title[:60]}… "
                f"→ expect {len(targets)} {child_level}, have {existing}, generating up to {missing} more"
            )
            created = repair_parent(engine, parent)
            db.commit()
            total_created += created
            if created:
                repaired += 1
                print(f"  ✓ Created {created} draft(s)")
            else:
                print("  · No new drafts (may already exist per-scope)")

        print(f"\nDone. Repaired {repaired} parent(s), {total_created} new draft(s) total.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
