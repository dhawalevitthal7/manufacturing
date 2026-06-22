#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.database import SessionLocal
from server.models import (
    Organization, User, Objective, KeyResult, ProgressUpdate,
    Review, ReportingRelationship, Plant, Department, Cycle,
)

db = SessionLocal()
orgs = db.query(Organization).filter(
    Organization.domain.in_(["align360.com", "cementokr.com"])
).all()

print("=== INGESTION VERIFICATION ===\n")
for o in orgs:
    oid = o.id
    users = db.query(User).filter(User.org_id == oid).count()
    emps = db.query(User).filter(User.org_id == oid, User.system_role == "EMPLOYEE").count()
    mgrs = users - emps
    plants = db.query(Plant).filter(Plant.org_id == oid).count()
    depts = db.query(Department).filter(Department.org_id == oid).count()
    cycles = db.query(Cycle).filter(Cycle.org_id == oid).all()
    objs = db.query(Objective).filter(Objective.org_id == oid)
    org_okrs = objs.filter(Objective.level == "ORGANIZATION").count()
    dept_okrs = objs.filter(Objective.level == "DEPARTMENT").count()
    ind_okrs = objs.filter(Objective.level == "INDIVIDUAL").count()
    krs = db.query(KeyResult).join(Objective).filter(Objective.org_id == oid).count()
    pus = db.query(ProgressUpdate).join(KeyResult).join(Objective).filter(Objective.org_id == oid).count()
    reviews = db.query(Review).filter(Review.org_id == oid).count()
    reports = db.query(ReportingRelationship).filter(ReportingRelationship.org_id == oid).count()

    print(f"Org: {o.name} ({o.domain})")
    print(f"  Users: {users} total ({emps} employees, {mgrs} leaders/managers)")
    print(f"  Plants: {plants}, Departments: {depts}, Reporting lines: {reports}")
    print(f"  Cycles: {[c.name for c in cycles]}")
    print(f"  OKRs: org={org_okrs}, dept={dept_okrs}, individual={ind_okrs}")
    print(f"  Key Results: {krs}, Progress Updates: {pus}, Reviews: {reviews}")

    sample = db.query(User).filter(User.org_id == oid, User.employee_id == "BC-1").first()
    if sample:
        ind = db.query(Objective).filter(
            Objective.owner_id == sample.id, Objective.level == "INDIVIDUAL"
        ).all()
        print(f"  Sample BC-1 ({sample.name}): {len(ind)} individual OKRs")
        for obj in ind[:2]:
            kr = db.query(KeyResult).filter(KeyResult.objective_id == obj.id).first()
            updates = (
                db.query(ProgressUpdate)
                .filter(ProgressUpdate.key_result_id == kr.id)
                .order_by(ProgressUpdate.created_at)
                .all()
            )
            title = obj.title[:60] + ("..." if len(obj.title) > 60 else "")
            print(f'    - "{title}" progress={obj.progress}%')
            for u in updates:
                print(f"      {u.notes}: {u.previous_value}% -> {u.new_value}% ({u.status})")
    print()

db.close()
