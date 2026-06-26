"""Manually trigger AI cascade for an ACTIVE org OKR."""
import sys
from server.database import SessionLocal
from server.services.ai_cascade_engine import AICascadeEngine

OKR_ID = sys.argv[1] if len(sys.argv) > 1 else "3288553b-2a6f-4d01-9851-be34abcaddca"
ORG_ID = sys.argv[2] if len(sys.argv) > 2 else "781357f0-7ef1-4077-a414-a2d53b318188"

db = SessionLocal()
try:
    engine = AICascadeEngine(db)
    created = engine.generate_cascade_for_parent(OKR_ID, ORG_ID)
    db.commit()
    print(f"Created {len(created)} AI draft(s): {created}")
finally:
    db.close()
