#!/usr/bin/env python3
"""Simulate GET /api/okrs with the same filters the UI sends."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.database import SessionLocal
from server.models import User, Objective
from server.services.okr_visibility_service import apply_okr_visibility_filter
from server.routes_okrs import _apply_objective_period_filter

db = SessionLocal()

test_users = [
    ("ceo@align360.com", "CEO"),
    ("employee.1001@align360.com", "EMPLOYEE"),
    ("maintenance.manager@align360.com", "DEPT_HEAD"),
    ("ceo@cementokr.com", "CEO"),
    ("employee.1001@cementokr.com", "EMPLOYEE"),
]

print("Simulating UI query: year=2026, quarter=Q2\n")
for email, role_hint in test_users:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        print(f"{email}: NOT FOUND")
        continue
    q = db.query(Objective).filter(Objective.org_id == user.org_id)
    q = apply_okr_visibility_filter(q, user, db, user.org_id)
    q = _apply_objective_period_filter(q, year=2026, quarter="Q2")
    objs = q.all()
    by_level = {}
    for o in objs:
        by_level[o.level] = by_level.get(o.level, 0) + 1
    print(f"{email} ({user.system_role}): {len(objs)} OKRs -> {by_level}")

db.close()
