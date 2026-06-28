"""
Run full AI cascade governance across all hierarchy levels (sync, fast).

Stop the API server first to avoid SQLite lock contention.

Usage:
  python scripts/run_full_cascade_workflow.py
"""
from __future__ import annotations

import sys
import uuid
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.database import SessionLocal
from server.models import Objective, User
from server.services.ai_cascade_engine import AICascadeEngine
from server.services.okr_lifecycle_service import (
    OKR_STATUS_ACTIVE,
    OKR_STATUS_AI_DRAFT,
    OKR_STATUS_PENDING_PARENT,
    OKR_STATUS_UNDER_REVIEW,
)

PARENT_TITLE_HINT = "Increase Production efficiency"
DRAFT_STATUSES = (OKR_STATUS_AI_DRAFT, OKR_STATUS_UNDER_REVIEW, OKR_STATUS_PENDING_PARENT)


def descendants_of(db, root_id: str) -> set[str]:
    ids = {root_id}
    q = deque([root_id])
    while q:
        pid = q.popleft()
        for (cid,) in db.query(Objective.id).filter(
            Objective.ai_generated_from_objective_id == pid
        ):
            if cid not in ids:
                ids.add(cid)
                q.append(cid)
    return ids


def find_root(db) -> Objective | None:
    return (
        db.query(Objective)
        .filter(
            Objective.level == "ORGANIZATION",
            Objective.okr_status == OKR_STATUS_ACTIVE,
            Objective.title.ilike(f"%{PARENT_TITLE_HINT}%"),
        )
        .order_by(Objective.created_at.desc())
        .first()
    )


def approve_one(db, engine: AICascadeEngine, draft: Objective) -> bool:
    owner = db.query(User).filter(User.id == draft.owner_id).first()
    if not owner:
        return False

    st = (draft.okr_status or "").upper()
    if st == OKR_STATUS_AI_DRAFT:
        engine.start_review(draft, owner)
    if draft.okr_status in (OKR_STATUS_AI_DRAFT, OKR_STATUS_UNDER_REVIEW):
        engine.submit_for_parent_approval(draft, owner)

    parent = engine._parent_objective(draft)
    if not parent or draft.okr_status != OKR_STATUS_PENDING_PARENT:
        return False

    approver = db.query(User).filter(User.id == parent.owner_id).first()
    if not approver:
        return False

    engine.approve_by_parent(draft, approver, schedule_next_cascade=False)
    db.commit()
    db.refresh(draft)

    # Synchronous cascade to next level (Team → Individual, etc.)
    if (draft.okr_status or "").upper() == OKR_STATUS_ACTIVE and draft.allows_cascade:
        try:
            engine.generate_cascade_for_parent(draft.id, draft.org_id)
            db.commit()
        except Exception as exc:
            print(f"    cascade warning: {exc}")
            db.rollback()

    return True


def main() -> None:
    db = SessionLocal()
    engine = AICascadeEngine(db)
    root = find_root(db)
    if not root:
        print("Root org OKR not found.")
        return

    print(f"Root: {root.title}\n")

    # Ensure org-level cascade exists
    if not db.query(Objective).filter(
        Objective.ai_generated_from_objective_id == root.id
    ).count():
        ids = engine.generate_cascade_for_parent(root.id, root.org_id)
        db.commit()
        print(f"Generated {len(ids)} regional draft(s)\n")

    tree_ids = descendants_of(db, root.id)
    max_passes = 500
    total_approved = 0

    for pass_num in range(1, max_passes + 1):
        drafts = (
            db.query(Objective)
            .filter(
                Objective.id.in_(tree_ids),
                Objective.okr_status.in_(DRAFT_STATUSES),
            )
            .order_by(Objective.level, Objective.created_at)
            .all()
        )
        if not drafts:
            break

        d = drafts[0]
        print(f"[{pass_num}] {d.level} — {d.title[:60]}… ({d.okr_status})")
        if approve_one(db, engine, d):
            total_approved += 1
            print(f"    → ACTIVE")
            tree_ids = descendants_of(db, root.id)
        else:
            print(f"    → skipped")
            db.rollback()
            break

    # Summary
    print(f"\n=== Done: {total_approved} OKRs approved ===\n")
    by_level: dict[str, dict[str, int]] = {}
    for obj in db.query(Objective).filter(Objective.id.in_(tree_ids)).all():
        lvl = obj.level or "?"
        st = obj.okr_status or "?"
        by_level.setdefault(lvl, {})
        by_level[lvl][st] = by_level[lvl].get(st, 0) + 1

    for lvl in ["ORGANIZATION", "REGION", "PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"]:
        if lvl in by_level:
            print(f"  {lvl}: {by_level[lvl]}")
        else:
            print(f"  {lvl}: —")

    pending = db.query(Objective).filter(
        Objective.id.in_(tree_ids),
        Objective.okr_status.in_(DRAFT_STATUSES),
    ).count()
    if pending:
        print(f"\n  {pending} draft(s) still pending — re-run script or approve in UI.")
    db.close()


if __name__ == "__main__":
    main()
