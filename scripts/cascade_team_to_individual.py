"""Trigger Team→Individual cascade for ACTIVE team OKRs missing children."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.database import SessionLocal
from server.models import Objective, TeamMember
from server.services.ai_cascade_engine import AICascadeEngine

db = SessionLocal()
root = (
    db.query(Objective)
    .filter(Objective.title.ilike("%Production efficiency%"), Objective.level == "ORGANIZATION")
    .first()
)
if not root:
    print("No root")
    sys.exit(1)

# All ACTIVE team OKRs in this cascade tree
teams = (
    db.query(Objective)
    .filter(
        Objective.level == "TEAM",
        Objective.okr_status == "ACTIVE",
        Objective.ai_generated == True,
    )
    .all()
)
# Filter to tree under root
def in_tree(obj_id, root_id):
    o = db.query(Objective).filter(Objective.id == obj_id).first()
    while o:
        if o.ai_generated_from_objective_id == root_id:
            return True
        pid = o.ai_generated_from_objective_id
        if not pid:
            break
        o = db.query(Objective).filter(Objective.id == pid).first()
    return obj_id == root_id

engine = AICascadeEngine(db)
generated_total = 0

for t in teams:
    if not in_tree(t.id, root.id):
        continue
    existing = db.query(Objective).filter(Objective.ai_generated_from_objective_id == t.id).count()
    if existing:
        continue
    members = 0
    if t.team_id:
        members = db.query(TeamMember).filter(
            TeamMember.team_id == t.team_id, TeamMember.is_active == True
        ).count()
    print(f"TEAM {t.title[:50]} team_id={t.team_id} members={members}")
    ids = engine.generate_cascade_for_parent(t.id, t.org_id)
    db.commit()
    print(f"  → generated {len(ids)} individual draft(s)")
    generated_total += len(ids)

print(f"\nTotal individual drafts generated: {generated_total}")
db.close()
