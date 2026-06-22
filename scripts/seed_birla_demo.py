#!/usr/bin/env python3
"""
Idempotent Birla Cement demo seed (~550 users, full OKR hierarchy, cascade progress).

Usage:
  python scripts/seed_birla_demo.py           # skip if org already exists
  python scripts/seed_birla_demo.py --reset   # wipe @birlacement.test org, re-seed

Password for all users: Test@1234
"""

from __future__ import annotations

import argparse
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.orm import Session

from server.auth import get_password_hash
from server.database import SessionLocal, engine, Base
from server.models import (
    Cycle,
    Department,
    Designation,
    KeyResult,
    Objective,
    ObjectiveConnection,
    OrgNode,
    Organization,
    Plant,
    ProgressUpdate,
    ReportingRelationship,
    Team,
    TeamMember,
    User,
    UserPermissionProfile,
)
from server.okr_cascade_service import OKRCascadeService, calculate_objective_progress
from server.permissions_service import initialize_user_permissions
from server.schema_migrations import apply_sqlite_schema_migrations

Base.metadata.create_all(bind=engine)
apply_sqlite_schema_migrations(engine)

DOMAIN = "birlacement.test"
ORG_NAME = "Birla Cement"
PASSWORD = "Test@1234"
RNG = random.Random(42)

FIRST_NAMES = [
    "Aarav", "Priya", "Rajesh", "Sneha", "Vikram", "Meera", "Arjun", "Kavita",
    "Sanjay", "Ananya", "Rahul", "Deepa", "Manish", "Lakshmi", "Suresh", "Neha",
    "Kiran", "Pooja", "Amit", "Divya", "Rohan", "Shreya", "Naveen", "Anjali",
]
LAST_NAMES = [
    "Sharma", "Nair", "Iyer", "Patel", "Reddy", "Joshi", "Gupta", "Menon",
    "Singh", "Desai", "Kumar", "Pillai", "Chatterjee", "Rao", "Verma", "Shah",
]

REGIONS = [
    ("North", "NORTH", ["Hirmi (Chhattisgarh)", "Roorkee (Uttarakhand)", "Kotputli (Rajasthan)"]),
    ("West", "WEST", ["Rajashree (Maharashtra)", "Awarpur (Maharashtra)", "Dhar (Gujarat)"]),
    ("South", "SOUTH", ["Reddipalayam (Tamil Nadu)", "Sewagram (Karnataka)", "Arakkonam (Tamil Nadu)"]),
    ("East", "EAST", ["Dalla (Uttar Pradesh)", "Bela (Madhya Pradesh)", "Bara (Jharkhand)"]),
]

DEPT_SPECS = [
    ("Production", "PRODUCTION", [("Kiln Shift A", "TEAM_LEAD"), ("Kiln Shift B", "SUPERVISOR")]),
    ("Quality", "QUALITY", [("QC Lab", "TEAM_LEAD"), ("Field QC", "SUPERVISOR")]),
    ("Mechanical Maintenance", "MECHANICAL_MAINTENANCE", [("Mech Crew A", "MANAGER"), ("Mech Crew B", "SUPERVISOR")]),
    ("E&I", "ELECTRICAL_INSTRUMENTATION", [("Electrical Crew", "TEAM_LEAD"), ("Instrumentation", "SUPERVISOR")]),
    ("Mining", "MINING", [("Limestone Bench", "MANAGER"), ("Drilling Crew", "SUPERVISOR")]),
    ("HSE", "HSE", [("Safety Patrol", "TEAM_LEAD"), ("Environment", "SUPERVISOR")]),
]

IC_ROLES = [
    ("CCR Operator", "EMPLOYEE"),
    ("Field Operator", "EMPLOYEE"),
    ("Technician", "EMPLOYEE"),
    ("Lab Analyst", "EMPLOYEE"),
    ("Graduate Engineer Trainee", "EMPLOYEE"),
    ("Fitter", "EMPLOYEE"),
    ("Electrician", "EMPLOYEE"),
]

NAMED_ACCOUNTS = {
    "superadmin@birlacement.test": ("System Admin", "SUPER_ADMIN", {}),
    "ceo@birlacement.test": ("Vikram Mehta", "CEO", {}),
    "coo@birlacement.test": ("Arjun Malhotra", "COO", {}),
    "cro@birlacement.test": ("Kavita Rao", "CRO", {}),
    "vp.manufacturing.west@birlacement.test": ("Rahul Desai", "VP_OPERATIONS", {"region_slug": "west"}),
    "regionalhead.west@birlacement.test": ("Ananya Desai", "REGIONAL_HEAD", {"region_slug": "west"}),
    "regionalhead.north@birlacement.test": ("Meera Singh", "REGIONAL_HEAD", {"region_slug": "north"}),
    "planthead.west2@birlacement.test": ("Rajesh Iyer", "PLANT_HEAD", {"plant_key": "west-2"}),
    "planthead.north1@birlacement.test": ("Suresh Kumar", "PLANT_HEAD", {"plant_key": "north-1"}),
    "hod.production.west2@birlacement.test": ("Sanjay Kumar", "DEPT_HEAD", {"dept_key": "west-2-production"}),
    "manager.kiln.west2@birlacement.test": ("Priya Nair", "MANAGER", {"team_key": "west-2-production-kiln-shift-a"}),
    "teamlead.shiftA.west2@birlacement.test": ("Aarav Sharma", "TEAM_LEAD", {"team_key": "west-2-production-kiln-shift-a"}),
    "supervisor.shiftB.west2@birlacement.test": ("Rohan Verma", "SUPERVISOR", {"team_key": "west-2-production-kiln-shift-b"}),
    "employee.ccr1.west2@birlacement.test": ("Sneha Patel", "EMPLOYEE", {"team_key": "west-2-production-kiln-shift-a", "ic_title": "CCR Operator"}),
    "employee.field1.west2@birlacement.test": ("Deepa Joshi", "EMPLOYEE", {"team_key": "west-2-production-kiln-shift-b", "ic_title": "Field Operator"}),
}


def gen_id() -> str:
    return str(uuid.uuid4())


def wipe_table(db: Session, table: str) -> None:
    try:
        db.execute(text(f"DELETE FROM {table} WHERE 1=1"))
    except Exception:
        pass


def reset_birla_org(db: Session) -> None:
    org = (
        db.query(Organization)
        .filter(Organization.domain == DOMAIN)
        .first()
    )
    if not org:
        org = db.query(Organization).filter(Organization.name == ORG_NAME).first()
    if not org:
        print("[reset] No Birla Cement org found")
        return

    org_id = org.id
    user_ids = [u.id for u in db.query(User).filter(User.email.like(f"%@{DOMAIN}")).all()]
    obj_ids = [o.id for o in db.query(Objective).filter(Objective.org_id == org_id).all()]

    if user_ids:
        uid_in = ",".join(f"'{u}'" for u in user_ids)
        for tbl, col in [
            ("progress_updates", "submitted_by_id"),
            ("progress_submissions", "submitted_by_id"),
            ("reporting_relationships", "employee_id"),
            ("team_members", "user_id"),
            ("user_permission_profiles", "user_id"),
        ]:
            try:
                db.execute(text(f"DELETE FROM {tbl} WHERE {col} IN ({uid_in})"))
            except Exception:
                pass

    if obj_ids:
        oid_in = ",".join(f"'{o}'" for o in obj_ids)
        for tbl in ("objective_connections", "key_results", "progress_updates", "progress_submissions"):
            try:
                db.execute(text(f"DELETE FROM {tbl} WHERE objective_id IN ({oid_in}) OR key_result_id IN (SELECT id FROM key_results WHERE objective_id IN ({oid_in}))"))
            except Exception:
                pass
        try:
            db.execute(text(f"DELETE FROM key_results WHERE objective_id IN ({oid_in})"))
        except Exception:
            pass
        db.query(Objective).filter(Objective.org_id == org_id).delete(synchronize_session=False)

    db.query(Cycle).filter(Cycle.org_id == org_id).delete(synchronize_session=False)
    db.query(TeamMember).filter(TeamMember.org_id == org_id).delete(synchronize_session=False)
    db.query(ReportingRelationship).filter(ReportingRelationship.org_id == org_id).delete(synchronize_session=False)
    db.query(UserPermissionProfile).filter(UserPermissionProfile.org_id == org_id).delete(synchronize_session=False)
    db.query(User).filter(User.org_id == org_id).delete(synchronize_session=False)
    db.query(Team).filter(Team.org_id == org_id).delete(synchronize_session=False)
    db.query(Department).filter(Department.org_id == org_id).delete(synchronize_session=False)
    db.query(Plant).filter(Plant.org_id == org_id).delete(synchronize_session=False)
    db.query(OrgNode).filter(OrgNode.org_id == org_id).delete(synchronize_session=False)
    db.query(Designation).filter(Designation.org_id == org_id).delete(synchronize_session=False)
    db.query(Organization).filter(Organization.id == org_id).delete(synchronize_session=False)
    db.commit()
    print(f"[reset] Removed org {ORG_NAME} and all related data")


def _pick_name(i: int) -> str:
    return f"{FIRST_NAMES[i % len(FIRST_NAMES)]} {LAST_NAMES[(i // len(FIRST_NAMES)) % len(LAST_NAMES)]}"


def _slug(s: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in s).strip("-")


def add_reporting(db: Session, org_id: str, employee_id: str, manager_id: str) -> None:
    db.add(
        ReportingRelationship(
            org_id=org_id,
            employee_id=employee_id,
            manager_id=manager_id,
            relationship_type="DIRECT",
            is_active=True,
        )
    )


def create_user(
    db: Session,
    org_id: str,
    email: str,
    name: str,
    system_role: str,
    designation_id: str | None,
    *,
    plant_id: str | None = None,
    department_id: str | None = None,
    team_id: str | None = None,
    org_node_id: str | None = None,
    employee_id: str | None = None,
) -> User:
    u = User(
        id=gen_id(),
        org_id=org_id,
        email=email,
        password_hash=get_password_hash(PASSWORD),
        name=name,
        employee_id=employee_id or f"BC-{email.split('@')[0][:12]}",
        system_role=system_role,
        is_active=True,
        plant_id=plant_id,
        department_id=department_id,
        team_id=team_id,
        designation_id=designation_id,
        org_node_id=org_node_id,
    )
    db.add(u)
    db.flush()
    initialize_user_permissions(u, db, commit=False)
    return u


def create_krs(
    db: Session,
    objective_id: str,
    specs: list[tuple[str, float, float, str]],
    owner_id: str,
) -> list[KeyResult]:
    krs: list[KeyResult] = []
    for title, target, current, unit in specs:
        kr = KeyResult(
            id=gen_id(),
            objective_id=objective_id,
            title=title,
            target_value=target,
            current_value=current,
            unit=unit,
            status="COMPLETED" if current >= target else "IN_PROGRESS",
            weight=1.0,
        )
        db.add(kr)
        db.flush()
        db.add(
            ProgressUpdate(
                id=gen_id(),
                key_result_id=kr.id,
                submitted_by_id=owner_id,
                previous_value=0.0,
                new_value=current,
                notes="Birla demo seed",
                status="APPROVED",
                progress_source="MANUAL",
            )
        )
        krs.append(kr)
    return krs


def create_objective(
    db: Session,
    org_id: str,
    owner: User,
    level: str,
    title: str,
    kr_specs: list[tuple[str, float, float, str]],
    cycle_id: str,
    *,
    parent_id: str | None = None,
    region_id: str | None = None,
    plant_id: str | None = None,
    department_id: str | None = None,
    team_id: str | None = None,
) -> Objective:
    now = datetime.now(timezone.utc)
    obj = Objective(
        id=gen_id(),
        org_id=org_id,
        owner_id=owner.id,
        parent_id=parent_id,
        title=title,
        level=level,
        region_id=region_id,
        plant_id=plant_id,
        department_id=department_id,
        team_id=team_id,
        cycle_id=cycle_id,
        creation_approval_status="APPROVED",
        creation_approved_at=now,
        okr_status="ACTIVE",
        status="ACTIVE",
        kr_baseline_locked=True,
        progress=0.0,
        quarter="Q2",
        year=2026,
        allows_cascade=True,
    )
    db.add(obj)
    db.flush()
    create_krs(db, obj.id, kr_specs, owner.id)
    return obj


def target_progress(seed_key: str, *, blocked: bool = False) -> float:
    if blocked:
        return 35.0
    h = sum(ord(c) for c in seed_key)
    return round(60 + (h % 31) + RNG.uniform(0, 4), 1)


def kr_values_for_progress(progress_pct: float, specs: list[tuple[str, float, str]]) -> list[tuple[str, float, float, str]]:
    out = []
    for title, target, unit in specs:
        current = round(target * progress_pct / 100.0, 2)
        out.append((title, target, current, unit))
    return out


def rollup_all(db: Session, objectives: list[Objective]) -> None:
    cascade = OKRCascadeService(db)
    for level in ("INDIVIDUAL", "TEAM", "DEPARTMENT", "PLANT", "REGION", "ORGANIZATION"):
        for obj in [o for o in objectives if o.level == level]:
            cascade.refresh_objective_progress_for_session(obj.id)
    db.flush()


def seed_birla(db: Session) -> dict[str, Any]:
    existing = db.query(Organization).filter(Organization.domain == DOMAIN).first()
    if existing:
        return {"skipped": True, "org_id": existing.id}

    now = datetime.now(timezone.utc)
    cycle_start = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    cycle_end = (now + timedelta(days=60)).strftime("%Y-%m-%d")
    freeze = (now + timedelta(days=55)).strftime("%Y-%m-%d")

    org = Organization(
        id=gen_id(),
        name=ORG_NAME,
        domain=DOMAIN,
        industry="Manufacturing - Cement",
        size="LARGE",
        setup_completed=True,
    )
    db.add(org)
    db.flush()
    org_id = org.id

    root = OrgNode(
        id=org_id,
        org_id=org_id,
        parent_id=None,
        node_type="ORGANIZATION",
        name=ORG_NAME,
        path=org_id,
        depth=0,
        is_active=True,
    )
    db.add(root)

    designations: dict[str, Designation] = {}
    for dname, level, category in [
        ("Chief Executive Officer", 0, "LEADERSHIP"),
        ("Chief Operating Officer", 1, "LEADERSHIP"),
        ("Chief Regional Officer", 1, "LEADERSHIP"),
        ("Regional CEO", 1, "LEADERSHIP"),
        ("VP Manufacturing", 1, "LEADERSHIP"),
        ("Plant Head", 2, "PLANT_LEADERSHIP"),
        ("Deputy Plant Head", 2, "PLANT_LEADERSHIP"),
        ("Head of Department", 3, "MANAGEMENT"),
        ("Manager", 4, "MANAGEMENT"),
        ("Team Lead", 5, "MANAGEMENT"),
        ("Supervisor", 5, "OPERATIONAL"),
        ("CCR Operator", 6, "OPERATIONAL"),
        ("Field Operator", 6, "OPERATIONAL"),
        ("Technician", 6, "OPERATIONAL"),
        ("Lab Analyst", 6, "OPERATIONAL"),
        ("Graduate Engineer Trainee", 6, "OPERATIONAL"),
        ("Fitter", 6, "OPERATIONAL"),
        ("Electrician", 6, "OPERATIONAL"),
    ]:
        d = Designation(id=gen_id(), org_id=org_id, name=dname, level=level, category=category, is_active=True)
        db.add(d)
        designations[dname] = d
    db.flush()

    cycle = Cycle(
        id=gen_id(),
        org_id=org_id,
        name="Q2-2026",
        cycle_type="QUARTERLY",
        start_date=cycle_start,
        end_date=cycle_end,
        freeze_date=freeze,
        status="ACTIVE",
        applies_to_levels=[0, 1, 2, 3, 4, 5],
    )
    db.add(cycle)
    db.flush()

    user_count = 0
    name_idx = 0
    refs: dict[str, Any] = {
        "regions": {},
        "plants": {},
        "departments": {},
        "teams": {},
        "users": {},
    }

    def next_email(prefix: str) -> str:
        return f"{prefix}@{DOMAIN}"

    # Named accounts first (CEO / superadmin)
    ceo = create_user(
        db, org_id, "ceo@birlacement.test", "Vikram Mehta", "CEO",
        designations["Chief Executive Officer"].id, org_node_id=org_id,
    )
    create_user(
        db, org_id, "superadmin@birlacement.test", "System Admin", "SUPER_ADMIN",
        None, org_node_id=org_id,
    )
    root.head_user_id = ceo.id
    user_count += 2

    # Corporate Committee layer (COO + CRO report to CEO)
    cc = OrgNode(
        id=gen_id(),
        org_id=org_id,
        parent_id=org_id,
        node_type="CORPORATE_COMMITTEE",
        name="Corporate Committee",
        code="CORP-COMM",
        path=f"{org_id}.{gen_id()}",
        depth=1,
        is_active=True,
    )
    db.add(cc)
    db.flush()
    cc.path = f"{org_id}.{cc.id}"

    coo = create_user(
        db, org_id, "coo@birlacement.test", "Arjun Malhotra", "COO",
        designations["Chief Operating Officer"].id, org_node_id=cc.id,
    )
    cro = create_user(
        db, org_id, "cro@birlacement.test", "Kavita Rao", "CRO",
        designations["Chief Regional Officer"].id, org_node_id=cc.id,
    )
    cc.head_user_id = coo.id
    add_reporting(db, org_id, coo.id, ceo.id)
    add_reporting(db, org_id, cro.id, ceo.id)
    user_count += 2
    refs["coo"] = coo
    refs["cro"] = cro
    refs["corporate_committee"] = cc

    for rname, rcode, plant_names in REGIONS:
        rslug = rcode.lower()
        rn = OrgNode(
            id=gen_id(),
            org_id=org_id,
            parent_id=org_id,
            node_type="REGION",
            name=f"{rname} Region",
            code=rcode,
            path=f"{org_id}.{gen_id()}",
            depth=1,
            is_active=True,
            node_metadata={"unit_type": "region"},
        )
        db.add(rn)
        db.flush()
        rn.path = f"{org_id}.{rn.id}"

        rh_email = (
            "regionalhead.west@birlacement.test"
            if rslug == "west"
            else "regionalhead.north@birlacement.test"
            if rslug == "north"
            else next_email(f"regionalhead.{rslug}")
        )
        rh_name = NAMED_ACCOUNTS.get(rh_email, (_pick_name(name_idx),))[0]
        name_idx += 1
        rh = create_user(
            db, org_id, rh_email, rh_name, "REGIONAL_HEAD",
            designations["Regional CEO"].id, org_node_id=rn.id,
        )
        rn.head_user_id = rh.id
        add_reporting(db, org_id, rh.id, cro.id)
        user_count += 1

        vp_email = (
            "vp.manufacturing.west@birlacement.test"
            if rslug == "west"
            else next_email(f"vp.manufacturing.{rslug}")
        )
        vp_name = NAMED_ACCOUNTS.get(vp_email, (_pick_name(name_idx),))[0]
        vp = create_user(
            db, org_id, vp_email, vp_name,
            "VP_OPERATIONS", designations["VP Manufacturing"].id, org_node_id=rn.id,
        )
        name_idx += 1
        add_reporting(db, org_id, vp.id, ceo.id)
        user_count += 1

        refs["regions"][rslug] = {"node": rn, "head": rh, "vp": vp}

        for pi, pname in enumerate(plant_names, start=1):
            pkey = f"{rslug}-{pi}"
            pcode = f"{rcode}-P{pi}"
            unit_type = "Grinding Unit" if "Dhar" in pname or "Kotputli" in pname else "Integrated Unit"
            plant = Plant(
                id=gen_id(),
                org_id=org_id,
                name=pname,
                code=pcode,
                location=pname,
                is_active=True,
            )
            db.add(plant)
            db.flush()
            pn = OrgNode(
                id=plant.id,
                org_id=org_id,
                parent_id=rn.id,
                node_type="PLANT",
                name=pname,
                code=pcode,
                path=f"{rn.path}.{plant.id}",
                depth=2,
                is_active=True,
                node_metadata={"unit_type": unit_type},
            )
            db.add(pn)
            db.flush()

            ph_email = (
                "planthead.west2@birlacement.test"
                if pkey == "west-2"
                else "planthead.north1@birlacement.test"
                if pkey == "north-1"
                else next_email(f"planthead.{pkey}")
            )
            ph_name = NAMED_ACCOUNTS.get(ph_email, (_pick_name(name_idx),))[0]
            name_idx += 1
            ph = create_user(
                db, org_id, ph_email, ph_name, "PLANT_HEAD",
                designations["Plant Head"].id,
                plant_id=plant.id, org_node_id=pn.id,
            )
            pn.head_user_id = ph.id
            add_reporting(db, org_id, ph.id, coo.id)
            user_count += 1

            dep = create_user(
                db, org_id, next_email(f"deputy.planthead.{pkey}"), _pick_name(name_idx),
                "PLANT_HEAD", designations["Deputy Plant Head"].id,
                plant_id=plant.id, org_node_id=pn.id,
            )
            name_idx += 1
            add_reporting(db, org_id, dep.id, ph.id)
            user_count += 1

            refs["plants"][pkey] = {"plant": plant, "node": pn, "head": ph, "region": rn}

            for dname, dtype, team_specs in DEPT_SPECS:
                dkey = f"{pkey}-{_slug(dname)}"
                dept = Department(
                    id=gen_id(),
                    org_id=org_id,
                    plant_id=plant.id,
                    name=dname,
                    dept_type=dtype,
                    is_active=True,
                )
                db.add(dept)
                db.flush()
                dn = OrgNode(
                    id=dept.id,
                    org_id=org_id,
                    parent_id=plant.id,
                    node_type="DEPARTMENT",
                    name=dname,
                    path=f"{pn.path}.{dept.id}",
                    depth=3,
                    is_active=True,
                    node_metadata={"dept_type": dtype},
                )
                db.add(dn)
                db.flush()

                hod_email = (
                    "hod.production.west2@birlacement.test"
                    if dkey == "west-2-production"
                    else next_email(f"hod.{dkey}")
                )
                hod_name = NAMED_ACCOUNTS.get(hod_email, (_pick_name(name_idx),))[0]
                name_idx += 1
                hod = create_user(
                    db, org_id, hod_email, hod_name, "DEPT_HEAD",
                    designations["Head of Department"].id,
                    plant_id=plant.id, department_id=dept.id, org_node_id=dn.id,
                )
                dn.head_user_id = hod.id
                add_reporting(db, org_id, hod.id, ph.id)
                user_count += 1
                refs["departments"][dkey] = {"dept": dept, "node": dn, "head": hod, "plant_key": pkey}

                for tname, lead_role in team_specs:
                    tkey = f"{dkey}-{_slug(tname)}"
                    team = Team(id=gen_id(), org_id=org_id, department_id=dept.id, name=tname, is_active=True)
                    db.add(team)
                    db.flush()
                    tn = OrgNode(
                        id=team.id,
                        org_id=org_id,
                        parent_id=dept.id,
                        node_type="TEAM",
                        name=tname,
                        path=f"{dn.path}.{team.id}",
                        depth=4,
                        is_active=True,
                    )
                    db.add(tn)
                    db.flush()

                    # West-2 Kiln Shift A: named manager + team lead (demo accounts)
                    if tkey == "west-2-production-kiln-shift-a":
                        mgr = create_user(
                            db, org_id, "manager.kiln.west2@birlacement.test",
                            NAMED_ACCOUNTS["manager.kiln.west2@birlacement.test"][0],
                            "MANAGER", designations["Manager"].id,
                            plant_id=plant.id, department_id=dept.id, team_id=team.id, org_node_id=tn.id,
                        )
                        add_reporting(db, org_id, mgr.id, hod.id)
                        user_count += 1
                        lead = create_user(
                            db, org_id, "teamlead.shiftA.west2@birlacement.test",
                            NAMED_ACCOUNTS["teamlead.shiftA.west2@birlacement.test"][0],
                            "TEAM_LEAD", designations["Team Lead"].id,
                            plant_id=plant.id, department_id=dept.id, team_id=team.id, org_node_id=tn.id,
                        )
                        team.lead_id = lead.id
                        tn.head_user_id = lead.id
                        add_reporting(db, org_id, lead.id, mgr.id)
                        user_count += 1
                        db.add(TeamMember(org_id=org_id, team_id=team.id, user_id=mgr.id, is_active=True))
                        db.add(TeamMember(org_id=org_id, team_id=team.id, user_id=lead.id, is_team_lead=True, role_in_team="LEAD", is_active=True))
                        shift_supervisor = lead
                    elif tkey == "west-2-production-kiln-shift-b":
                        lead = create_user(
                            db, org_id, "supervisor.shiftB.west2@birlacement.test",
                            NAMED_ACCOUNTS["supervisor.shiftB.west2@birlacement.test"][0],
                            "SUPERVISOR", designations["Supervisor"].id,
                            plant_id=plant.id, department_id=dept.id, team_id=team.id, org_node_id=tn.id,
                        )
                        team.lead_id = lead.id
                        tn.head_user_id = lead.id
                        add_reporting(db, org_id, lead.id, hod.id)
                        user_count += 1
                        db.add(TeamMember(org_id=org_id, team_id=team.id, user_id=lead.id, is_team_lead=True, role_in_team="LEAD", is_active=True))
                        shift_supervisor = lead
                    else:
                        lead_desig = designations[
                            "Manager" if lead_role == "MANAGER"
                            else "Team Lead" if lead_role == "TEAM_LEAD"
                            else "Supervisor"
                        ]
                        lead = create_user(
                            db, org_id, next_email(f"lead.{tkey}"), _pick_name(name_idx),
                            lead_role, lead_desig.id,
                            plant_id=plant.id, department_id=dept.id, team_id=team.id, org_node_id=tn.id,
                        )
                        name_idx += 1
                        team.lead_id = lead.id
                        tn.head_user_id = lead.id
                        add_reporting(db, org_id, lead.id, hod.id)
                        user_count += 1
                        db.add(TeamMember(org_id=org_id, team_id=team.id, user_id=lead.id, is_team_lead=True, role_in_team="LEAD", is_active=True))
                        shift_supervisor = lead

                    refs["teams"][tkey] = {
                        "team": team, "node": tn, "lead": shift_supervisor, "dept_key": dkey, "plant_key": pkey,
                    }

                    # ~2 ICs/team with ~11 teams at 3 ICs → ~550 total users
                    ic_count = 3 if (abs(hash(tkey)) % 144) < 11 else 2
                    for ic_i in range(ic_count):
                        ic_title, ic_role = IC_ROLES[(name_idx + ic_i) % len(IC_ROLES)]
                        ic_email = (
                            "employee.ccr1.west2@birlacement.test"
                            if tkey == "west-2-production-kiln-shift-a" and ic_i == 0
                            else "employee.field1.west2@birlacement.test"
                            if tkey == "west-2-production-kiln-shift-b" and ic_i == 0
                            else next_email(f"ic.{tkey}.{ic_i + 1}")
                        )
                        ic_name = NAMED_ACCOUNTS.get(ic_email, (_pick_name(name_idx),))[0]
                        name_idx += 1
                        ic_desig = designations.get(ic_title, designations["Field Operator"])
                        ic = create_user(
                            db, org_id, ic_email, ic_name, ic_role,
                            ic_desig.id,
                            plant_id=plant.id, department_id=dept.id, team_id=team.id, org_node_id=tn.id,
                        )
                        add_reporting(db, org_id, ic.id, shift_supervisor.id)
                        db.add(TeamMember(org_id=org_id, team_id=team.id, user_id=ic.id, is_active=True))
                        user_count += 1

    db.flush()

    # ── OKRs ────────────────────────────────────────────────────────────────
    objectives: list[Objective] = []
    obj_by_key: dict[str, Objective] = {}

    org_prog = target_progress("org")
    org_okr = create_objective(
        db, org_id, ceo, "ORGANIZATION",
        "Improve EBITDA & accelerate decarbonisation",
        kr_values_for_progress(org_prog, [
            ("Reduce cost per tonne (%)", 4, "%"),
            ("Reduce CO₂ per tonne (%)", 3, "%"),
            ("Capacity utilisation (%)", 92, "%"),
        ]),
        cycle.id,
    )
    objectives.append(org_okr)

    # COO / CRO oversight OKRs (active with approved progress for manual demo)
    west_plant_data = refs["plants"]["west-2"]
    west_region_node = refs["regions"]["west"]["node"]
    coo_prog = target_progress("coo-ops")
    coo_okr = create_objective(
        db, org_id, coo, "PLANT",
        "Pan-India operational excellence — COO oversight",
        kr_values_for_progress(coo_prog, [
            ("Group OEE (%)", 82, "%"),
            ("Energy intensity reduction (%)", 5, "%"),
            ("Zero-harm plants (count)", 12, "count"),
        ]),
        cycle.id,
        parent_id=org_okr.id,
        region_id=west_region_node.id,
        plant_id=west_plant_data["plant"].id,
    )
    objectives.append(coo_okr)

    cro_prog = target_progress("cro-regions")
    cro_okr = create_objective(
        db, org_id, cro, "REGION",
        "All-region EBITDA & market share — CRO oversight",
        kr_values_for_progress(cro_prog, [
            ("Group EBITDA vs plan (%)", 100, "%"),
            ("Market share gain (pts)", 1.5, "pts"),
            ("Regional capacity utilisation (%)", 90, "%"),
        ]),
        cycle.id,
        parent_id=org_okr.id,
        region_id=west_region_node.id,
    )
    objectives.append(cro_okr)

    for rslug, rdata in refs["regions"].items():
        rn = rdata["node"]
        rh = rdata["head"]
        rp = target_progress(f"region-{rslug}")
        ro = create_objective(
            db, org_id, rh, "REGION",
            f"{rn.name} — regional EBITDA & logistics",
            kr_values_for_progress(rp, [
                ("Regional EBITDA vs plan (%)", 100, "%"),
                ("Logistics cost index", 100, "index"),
                ("Capacity utilisation (%)", 92, "%"),
            ]),
            cycle.id,
            parent_id=org_okr.id,
            region_id=rn.id,
        )
        objectives.append(ro)
        obj_by_key[f"region-{rslug}"] = ro

    for pkey, pdata in refs["plants"].items():
        plant = pdata["plant"]
        ph = pdata["head"]
        rslug = pkey.split("-")[0]
        ro = obj_by_key[f"region-{rslug}"]
        pp = target_progress(f"plant-{pkey}")
        po = create_objective(
            db, org_id, ph, "PLANT",
            f"{plant.name} — operational excellence",
            kr_values_for_progress(pp, [
                ("OEE (%)", 85, "%"),
                ("Specific power (kWh/t)", 68, "kWh/t"),
                ("Specific heat (kcal/kg clinker)", 730, "kcal/kg"),
                ("TSR / alt fuel (%)", 18, "%"),
                ("Clinker factor reduction (pts)", 2, "pts"),
            ]),
            cycle.id,
            parent_id=ro.id,
            region_id=pdata["region"].id,
            plant_id=plant.id,
        )
        objectives.append(po)
        obj_by_key[f"plant-{pkey}"] = po

    dept_kr_templates: dict[str, list[tuple[str, float, str]]] = {
        "production": [("Kiln run factor (%)", 92, "%"), ("Daily clinker output (t)", 10000, "t")],
        "quality": [("28-day strength consistency (%)", 95, "%"), ("% batches within spec", 98, "%")],
        "mechanical-maintenance": [("MTBF increase (%)", 15, "%"), ("Breakdown hours (hrs)", 40, "hrs")],
        "e-i": [("PM compliance (%)", 95, "%"), ("Downtime from E&I (hrs)", 20, "hrs")],
        "mining": [("Limestone blending quality index", 100, "index"), ("Stripping ratio", 1.8, "ratio")],
        "hse": [("LTIFR reduction (%)", 20, "%"), ("Near-miss reporting (count)", 50, "count")],
    }

    for dkey, ddata in refs["departments"].items():
        dept = ddata["dept"]
        hod = ddata["head"]
        pkey = ddata["plant_key"]
        po = obj_by_key[f"plant-{pkey}"]
        slug = dkey.split("-", 2)[-1] if dkey.count("-") >= 2 else _slug(dept.name)
        blocked = dkey == "west-2-mechanical-maintenance"
        dp = target_progress(f"dept-{dkey}", blocked=blocked)
        template = dept_kr_templates.get(slug.replace("_", "-"), dept_kr_templates["production"])
        do = create_objective(
            db, org_id, hod, "DEPARTMENT",
            f"{dept.name} — {dept.dept_type.replace('_', ' ').title()} OKR",
            kr_values_for_progress(dp, template),
            cycle.id,
            parent_id=po.id,
            region_id=refs["plants"][pkey]["region"].id,
            plant_id=dept.plant_id,
            department_id=dept.id,
        )
        objectives.append(do)
        obj_by_key[f"dept-{dkey}"] = do

    for tkey, tdata in refs["teams"].items():
        team = tdata["team"]
        lead = tdata["lead"]
        dkey = tdata["dept_key"]
        pkey = tdata["plant_key"]
        do = obj_by_key[f"dept-{dkey}"]
        plant_id = refs["plants"][pkey]["plant"].id
        dept_id = refs["departments"][dkey]["dept"].id
        blocked = dkey == "west-2-mechanical-maintenance"
        tp = target_progress(f"team-{tkey}", blocked=blocked)
        to = create_objective(
            db, org_id, lead, "TEAM",
            f"{team.name} — execution targets",
            kr_values_for_progress(tp, [
                ("Shift output vs target (%)", 100, "%"),
                ("Maintenance closure SLA (%)", 90, "%"),
                ("Safety observations (count)", 20, "count"),
            ]),
            cycle.id,
            parent_id=do.id,
            region_id=refs["plants"][pkey]["region"].id,
            plant_id=plant_id,
            department_id=dept_id,
            team_id=team.id,
        )
        objectives.append(to)
        obj_by_key[f"team-{tkey}"] = to

        members = (
            db.query(User)
            .join(TeamMember, TeamMember.user_id == User.id)
            .filter(TeamMember.team_id == team.id, TeamMember.is_team_lead == False)
            .all()
        )
        for mem in members:
            ip = target_progress(f"ind-{mem.id}", blocked=blocked)
            io = create_objective(
                db, org_id, mem, "INDIVIDUAL",
                f"{mem.name} — individual contribution",
                kr_values_for_progress(ip, [
                    ("Personal output vs target (%)", 100, "%"),
                    ("Quality / compliance score (%)", 95, "%"),
                ]),
                cycle.id,
                parent_id=to.id,
                region_id=refs["plants"][pkey]["region"].id,
                plant_id=plant_id,
                department_id=dept_id,
                team_id=team.id,
            )
            objectives.append(io)

    # Demo: orphans
    west_plant = refs["plants"]["west-2"]["plant"]
    west_ph = refs["plants"]["west-2"]["head"]
    orphan1 = create_objective(
        db, org_id, west_ph, "PLANT",
        "Ad-hoc energy audit initiative (orphan)",
        kr_values_for_progress(55, [("Audit completion (%)", 100, "%")]),
        cycle.id,
        parent_id=None,
        plant_id=west_plant.id,
    )
    mining_hod = refs["departments"]["west-2-mining"]["head"]
    mining_dept = refs["departments"]["west-2-mining"]["dept"]
    orphan2 = create_objective(
        db, org_id, mining_hod, "DEPARTMENT",
        "Pilot digital twin — unaligned (orphan)",
        kr_values_for_progress(18, [("Pilot milestones (%)", 100, "%")]),
        cycle.id,
        parent_id=None,
        plant_id=west_plant.id,
        department_id=mining_dept.id,
    )
    objectives.extend([orphan1, orphan2])

    rollup_all(db, objectives)

    # Cross-functional connections
    prod_w2 = obj_by_key.get("dept-west-2-production")
    mech_w2 = obj_by_key.get("dept-west-2-mechanical-maintenance")
    org_okr_ref = org_okr
    connections = [
        (prod_w2, org_okr_ref, "SUPPORTS"),
        (prod_w2, obj_by_key.get("plant-west-2"), "DEPENDS_ON"),
        (prod_w2, mech_w2, "DEPENDS_ON"),
        (orphan2, mech_w2, "DEPENDS_ON"),
        (obj_by_key.get("dept-west-2-quality"), prod_w2, "RELATED_TO"),
        (obj_by_key.get("dept-west-2-hse"), prod_w2, "SUPPORTS"),
        (obj_by_key.get("dept-north-1-production"), obj_by_key.get("dept-south-1-production"), "RELATED_TO"),
    ]
    for o1, o2, ctype in connections:
        if o1 and o2:
            db.add(ObjectiveConnection(
                org_id=org_id,
                objective_id_1=o1.id,
                objective_id_2=o2.id,
                connection_type=ctype,
                cycle_id=cycle.id,
                created_by_id=ceo.id,
            ))

    db.commit()

    level_counts: dict[str, int] = {}
    for o in objectives:
        level_counts[o.level] = level_counts.get(o.level, 0) + 1

    return {
        "skipped": False,
        "org_id": org_id,
        "user_count": user_count,
        "okr_count": len(objectives),
        "level_counts": level_counts,
        "cycle_id": cycle.id,
        "orphans": 2,
        "blocked_dept": "west-2-mechanical-maintenance",
    }


def print_demo_credentials(result: dict[str, Any]) -> None:
    """Print and write demo login table for manual testing."""
    role_order = [
        ("SUPER_ADMIN", "Platform admin — override stuck OKRs, all orgs"),
        ("CEO", "Org OKR, publish org-level OKRs, sees all creation approvals"),
        ("COO", "Plant OKR approval queue, plant KR progress validation (Plant Heads)"),
        ("CRO", "Region OKR approval queue, region KR progress validation (Regional Heads)"),
        ("VP_OPERATIONS", "Cross-plant ops view (West region)"),
        ("REGIONAL_HEAD", "Region OKRs + cascade (West / North named accounts)"),
        ("PLANT_HEAD", "Plant OKRs + dept approval queue (Awarpur / Hirmi named)"),
        ("DEPT_HEAD", "Department OKRs, team/individual creation approvals"),
        ("MANAGER", "Team/individual OKRs, progress validation, creation approvals"),
        ("TEAM_LEAD", "Individual OKR creation, progress validation"),
        ("SUPERVISOR", "Individual OKR assignment (Kiln Shift B)"),
        ("EMPLOYEE", "Own OKRs, submit KR progress (after OKR approved)"),
    ]
    lines = [
        "# Birla Cement — Demo Login Credentials",
        "",
        f"**Organization:** {ORG_NAME}  ",
        f"**Domain:** `{DOMAIN}`  ",
        f"**Password (all users):** `{PASSWORD}`  ",
        f"**Cycle:** Q2-2026  ",
        f"**Users seeded:** {result.get('user_count', '?')}  ",
        f"**OKRs seeded:** {result.get('okr_count', '?')} (all ACTIVE with approved KR progress)  ",
        "",
        "## Primary demo accounts (one per hierarchy level)",
        "",
        "| Role | Email | Name | Demo focus |",
        "|------|-------|------|------------|",
    ]
    by_role: dict[str, list[tuple[str, str, str]]] = {}
    for email, (name, role, _meta) in NAMED_ACCOUNTS.items():
        by_role.setdefault(role, []).append((email, name, role))

    focus_map = {
        "superadmin@birlacement.test": "Admin panel, SUPER_ADMIN lifecycle override",
        "ceo@birlacement.test": "Org OKR, constellation center, approve COO/CRO OKRs",
        "coo@birlacement.test": "Approve Plant Head plant OKRs; validate plant KR progress",
        "cro@birlacement.test": "Approve Regional Head region OKRs; validate region KR progress",
        "vp.manufacturing.west@birlacement.test": "West region cross-plant dashboard",
        "regionalhead.west@birlacement.test": "West region OKR (Awarpur, Rajashree, Dhar plants)",
        "regionalhead.north@birlacement.test": "North region OKR (Hirmi, Roorkee, Kotputli)",
        "planthead.west2@birlacement.test": "Awarpur plant — full dept/team/individual OKR tree",
        "planthead.north1@birlacement.test": "Hirmi plant head view",
        "hod.production.west2@birlacement.test": "Production dept OKR, approve manager OKRs",
        "manager.kiln.west2@birlacement.test": "Kiln Shift A team, assign individual OKRs",
        "teamlead.shiftA.west2@birlacement.test": "Shift A team OKR, validate employee progress",
        "supervisor.shiftB.west2@birlacement.test": "Kiln Shift B supervisor, individual OKRs",
        "employee.ccr1.west2@birlacement.test": "CCR operator — individual OKR + progress submit",
        "employee.field1.west2@birlacement.test": "Field operator — Shift B individual OKR",
    }

    for role_key, blurb in role_order:
        for email, name, _ in by_role.get(role_key, []):
            focus = focus_map.get(email, blurb)
            lines.append(f"| {role_key} | `{email}` | {name} | {focus} |")

    lines.extend([
        "",
        "## OKR data summary",
        "",
        "| Level | Count |",
        "|-------|-------|",
    ])
    for lvl in ("ORGANIZATION", "REGION", "PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"):
        lines.append(f"| {lvl} | {result.get('level_counts', {}).get(lvl, 0)} |")

    lines.extend([
        "",
        "## Reporting chain (approval routing)",
        "",
        "```",
        "CEO",
        " ├── COO → all Plant Heads → HODs → Managers/Team Leads/Supervisors → Employees",
        " └── CRO → all Regional Heads",
        "```",
        "",
        "## Re-seed command",
        "",
        "```bash",
        "python scripts/seed_birla_demo.py --reset",
        "```",
        "",
    ])

    cred_path = Path(__file__).parent.parent / "BIRLA_DEMO_CREDENTIALS.md"
    cred_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nCredentials written to: {cred_path}")
    print("\n=== Demo login accounts (password Test@1234 for all) ===")
    for email, (name, role, _) in NAMED_ACCOUNTS.items():
        print(f"  [{role:14}] {email:45} {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Birla Cement demo data")
    parser.add_argument("--reset", action="store_true", help="Remove existing Birla org then re-seed")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.reset:
            reset_birla_org(db)
        result = seed_birla(db)
        if result.get("skipped"):
            print(f"[skip] {ORG_NAME} already exists (domain={DOMAIN}). Use --reset to re-seed.")
            return 0

        print("\n=== Birla Cement Demo Seed Complete ===")
        print(f"Organization: {ORG_NAME} ({result['org_id']})")
        print(f"Cycle: Q2-2026 ({result['cycle_id']})")
        print(f"Total users: {result['user_count']}")
        print(f"Total OKRs: {result['okr_count']}")
        print("OKRs by level:")
        for lvl in ("ORGANIZATION", "REGION", "PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"):
            print(f"  {lvl}: {result['level_counts'].get(lvl, 0)}")
        print(f"Demo orphans: {result['orphans']}")
        print(f"Blocked dept key: {result['blocked_dept']} (~35% progress)")
        print_demo_credentials(result)
        return 0
    except Exception as exc:
        db.rollback()
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

