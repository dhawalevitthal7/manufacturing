"""
Drive the full AI cascade through every adjacent hierarchy stage.

For each level transition (REGION -> PLANT -> DEPARTMENT -> TEAM -> INDIVIDUAL):
  1. Each child-level owner (head) reviews and submits their AI_DRAFT.
  2. The parent OKR owner (head one level up) approves -> ACTIVE.
  3. Newly-active OKRs generate AI_DRAFT children for the next level (synchronous).

Governance is preserved: AI never auto-activates; every OKR is submitted + approved.
"""
import sys

sys.path.insert(0, r"C:\Users\Girish\OneDrive\Desktop\Vitthal\manufacturing")

# Speed: skip Azure retry sleeps (rule-based fallback only in local dev).
import server.services.cascade_ai_service as ai_svc
ai_svc.MAX_RETRIES = 1

import server.services.ai_cascade_engine as engine_mod
# Take full synchronous control: disable background scheduling.
engine_mod.schedule_cascade_for_active_okr = lambda *a, **k: None
# Avoid a second DB writer (audit uses its own session -> SQLite lock contention).
engine_mod.record_audit_event = lambda *a, **k: None

from server.database import SessionLocal
from server.models import Objective, User
from server.services.ai_cascade_engine import AICascadeEngine
from server.services.okr_lifecycle_service import (
    OKR_STATUS_ACTIVE,
    OKR_STATUS_AI_DRAFT,
)

ORG = "781357f0-7ef1-4077-a414-a2d53b318188"
CHAIN = ["REGION", "PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"]

db = SessionLocal()
engine = AICascadeEngine(db)


def user(uid):
    return db.query(User).filter(User.id == uid).first()


def process_level(level):
    drafts = (
        db.query(Objective)
        .filter(
            Objective.org_id == ORG,
            Objective.level == level,
            Objective.okr_status == OKR_STATUS_AI_DRAFT,
        )
        .all()
    )
    print(f"\n=== {level}: {len(drafts)} AI drafts to process ===")
    activated = []
    for d in drafts:
        owner = user(d.owner_id)
        parent = (
            db.query(Objective)
            .filter(Objective.id == d.ai_generated_from_objective_id)
            .first()
        )
        if not owner or not parent:
            print(f"  skip {d.id[:8]} (missing owner/parent)")
            continue
        approver = user(parent.owner_id)
        try:
            engine.start_review(d, owner)
            engine.submit_for_parent_approval(d, owner)
            engine.approve_by_parent(d, approver)
            db.commit()
            activated.append(d)
        except Exception as exc:
            db.rollback()
            print(f"  ERROR {d.id[:8]}: {exc}")
    print(f"  -> {len(activated)} now ACTIVE")
    return activated


def active_parents_at(level):
    return (
        db.query(Objective)
        .filter(
            Objective.org_id == ORG,
            Objective.level == level,
            Objective.okr_status == OKR_STATUS_ACTIVE,
        )
        .all()
    )


def generate_children(child_level, parent_level):
    parents = active_parents_at(parent_level)
    total = 0
    for p in parents:
        try:
            ids = engine.generate_cascade_for_parent(p.id, ORG)
            db.commit()
            total += len(ids)
        except Exception as exc:
            db.rollback()
            print(f"  gen ERROR for {p.id[:8]}: {exc}")
    print(f"  -> generated {total} {child_level} AI drafts (from {len(parents)} {parent_level})")
    return total


try:
    for i, level in enumerate(CHAIN):
        # Ensure drafts exist at this level from any already-active parents.
        if i > 0:
            generate_children(level, CHAIN[i - 1])
        process_level(level)

    print("\n=== FINAL TALLY (ACTIVE AI-cascaded OKRs by level) ===")
    for level in CHAIN:
        cnt = (
            db.query(Objective)
            .filter(
                Objective.org_id == ORG,
                Objective.level == level,
                Objective.ai_generated == True,
                Objective.okr_status == OKR_STATUS_ACTIVE,
            )
            .count()
        )
        print(f"  {level}: {cnt} ACTIVE")
finally:
    db.close()
