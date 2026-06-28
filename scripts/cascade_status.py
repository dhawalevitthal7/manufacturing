"""Quick status of production efficiency cascade tree."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collections import defaultdict
from server.database import SessionLocal
from server.models import Objective

db = SessionLocal()
root = (
    db.query(Objective)
    .filter(Objective.title.ilike("%Production efficiency%"), Objective.level == "ORGANIZATION")
    .order_by(Objective.created_at.desc())
    .first()
)
if not root:
    print("No root found")
    sys.exit(0)

print(f"Root: {root.title} [{root.okr_status}] id={root.id[:8]}…\n")

def walk(pid, depth=0):
    kids = db.query(Objective).filter(Objective.ai_generated_from_objective_id == pid).all()
    for k in kids:
        print(f"{'  '*depth}{k.level:12} {k.okr_status:22} {k.title[:55]}")
        walk(k.id, depth + 1)

walk(root.id)

by = defaultdict(lambda: defaultdict(int))
all_ids = {root.id}
stack = [root.id]
while stack:
    pid = stack.pop()
    for k in db.query(Objective).filter(Objective.ai_generated_from_objective_id == pid).all():
        by[k.level][k.okr_status] += 1
        all_ids.add(k.id)
        stack.append(k.id)

print("\n=== Counts ===")
for lvl in ["REGION", "PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"]:
    if lvl in by:
        print(f"  {lvl}: {dict(by[lvl])}")
    else:
        print(f"  {lvl}: —")
db.close()
