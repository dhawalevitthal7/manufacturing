#!/usr/bin/env python3
"""Seed cross-functional objective connections for constellation demo."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.database import SessionLocal
from server.models import Objective, ObjectiveConnection, Organization


def _add(db, org_id: str, o1, o2, conn_type: str) -> bool:
    if not o1 or not o2 or o1.id == o2.id:
        return False
    exists = (
        db.query(ObjectiveConnection)
        .filter(
            ObjectiveConnection.org_id == org_id,
            ObjectiveConnection.objective_id_1.in_([o1.id, o2.id]),
            ObjectiveConnection.objective_id_2.in_([o1.id, o2.id]),
        )
        .first()
    )
    if exists:
        return False
    db.add(ObjectiveConnection(
        org_id=org_id,
        objective_id_1=o1.id,
        objective_id_2=o2.id,
        connection_type=conn_type,
        cycle_id=o1.cycle_id or o2.cycle_id,
    ))
    return True


def seed_connections(org_name: str = "Demo Manufacturing") -> int:
    db = SessionLocal()
    try:
        org = db.query(Organization).filter(Organization.name.ilike(f"%{org_name}%")).first()
        if not org:
            print(f"No org matching '{org_name}'")
            return 0

        org_okr = (
            db.query(Objective)
            .filter(Objective.org_id == org.id, Objective.level == "ORGANIZATION")
            .first()
        )
        north_plant = (
            db.query(Objective)
            .filter(Objective.org_id == org.id, Objective.level == "PLANT", Objective.title.ilike("%North%"))
            .first()
        )
        depts = (
            db.query(Objective)
            .filter(Objective.org_id == org.id, Objective.level == "DEPARTMENT", Objective.title.ilike("%Production%"))
            .all()
        )
        north_prod = depts[0] if depts else None
        south_prod = depts[1] if len(depts) > 1 else None

        created = 0
        specs = [
            (north_prod, org_okr, "SUPPORTS", "Production dept supports enterprise goal"),
            (north_prod, north_plant, "DEPENDS_ON", "Production depends on plant reliability"),
            (north_prod, south_prod, "RELATED_TO", "Cross-plant production coordination"),
        ]
        for o1, o2, ctype, label in specs:
            if _add(db, org.id, o1, o2, ctype):
                created += 1
                print(f"  + {ctype}: {label}")

        db.commit()
        print(f"Seeded {created} constellation connections for {org.name}")
        return created
    finally:
        db.close()


if __name__ == "__main__":
    seed_connections()
