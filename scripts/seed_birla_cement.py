#!/usr/bin/env python3
"""
Idempotent Birla Cement org seed — corporate functions, regions/plants, dual-approval
reporting (DIRECT + DOTTED_LINE), optional demo OKRs.

Usage:
  python scripts/seed_birla_cement.py
  python scripts/seed_birla_cement.py --reset
  python scripts/seed_birla_cement.py --with-okrs
  python scripts/seed_birla_cement.py --reset --with-okrs

Password for all users: Birla@123
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.orm import Session

from server.auth import get_password_hash
from server.database import SessionLocal, engine, Base
from server.models import (
    ApprovalStep,
    Cycle,
    Department,
    Designation,
    KeyResult,
    Objective,
    OrgNode,
    Organization,
    Plant,
    ProgressSubmission,
    ReportingRelationship,
    Team,
    TeamMember,
    User,
    UserPermissionProfile,
)
from server.okr_cascade_service import OKRCascadeService
from server.permissions_service import initialize_user_permissions
from server.schema_migrations import apply_sqlite_schema_migrations
from server.services.dual_approval_service import (
    SUBJECT_OKR_CREATION,
    SUBJECT_PROGRESS_SUBMISSION,
    approve,
    build_chain,
    current_step,
)
from server.services.function_area_service import FUNCTION_AREA_LABELS
from server.services.manager_resolution import resolve_approvers
from server.services.okr_lifecycle_service import (
    OKR_STATUS_DRAFT,
    activate_okr,
    enqueue_okr_creation_approval,
    publish_ceo_okr,
)
from server.services.org_tree_service import create_child_node, ensure_organization_root

Base.metadata.create_all(bind=engine)
apply_sqlite_schema_migrations(engine)

# ── Configurable volume ───────────────────────────────────────────────────────
NUM_REGIONS = 4
PLANTS_PER_REGION = 3
MANAGERS_PER_DEPT = 1
EMPLOYEES_PER_MANAGER = 2
TEAMS_PER_DEPT = 1

ORG_NAME = "Birla Cement"
DOMAIN = "birlacement.com"
PASSWORD = "Birla@123"
SEED_TAG = "birla_cement_v1"

# ── Stable upsert keys: email (users), code (org nodes) ───────────────────────

FUNCTION_VERTICALS: List[Tuple[str, str, str]] = [
    ("OPERATIONS", "Operations", "COO"),
    ("FINANCE", "Finance", "CFO"),
    ("HR", "HR & IR", "CHRO"),
    ("SALES_MARKETING", "Sales & Marketing", "CMO"),
    ("PROCUREMENT", "Procurement & SCM", "CPO"),
    ("TECHNICAL", "Technical / Quality / HSE", "CSO"),
    ("REGIONS", "Regions", "CRO"),
]

FUNCTIONAL_HEAD_EMAILS = {
    "COO": "coo@birlacement.com",
    "CFO": "cfo@birlacement.com",
    "CHRO": "chro@birlacement.com",
    "CMO": "cmo@birlacement.com",
    "CPO": "cpo@birlacement.com",
    "CSO": "cso@birlacement.com",
    "CRO": "cro@birlacement.com",
}

SUB_HEADS: Dict[str, List[Tuple[str, str]]] = {
    "CFO": [
        ("Head Accounts", "head.accounts@birlacement.com"),
        ("Head Taxation", "head.taxation@birlacement.com"),
        ("Head Treasury", "head.treasury@birlacement.com"),
        ("Head Costing", "head.costing@birlacement.com"),
        ("Head Internal Audit", "head.audit@birlacement.com"),
    ],
    "CHRO": [
        ("Head Talent Acquisition", "head.ta@birlacement.com"),
        ("Head L&D", "head.ld@birlacement.com"),
        ("Head IR", "head.ir@birlacement.com"),
        ("Head Comp & Benefits", "head.comp@birlacement.com"),
    ],
    "CPO": [
        ("Head Strategic Sourcing", "head.sourcing@birlacement.com"),
        ("Head Logistics", "head.logistics@birlacement.com"),
        ("Head Stores", "head.stores@birlacement.com"),
    ],
    "CSO": [
        ("Head Process", "head.process@birlacement.com"),
        ("Head AFR", "head.afr@birlacement.com"),
        ("Head R&D", "head.rnd@birlacement.com"),
        ("Head Environment", "head.environment@birlacement.com"),
    ],
    "CMO": [
        ("Head Brand", "head.brand@birlacement.com"),
        ("Head RMC", "head.rmc@birlacement.com"),
    ],
}

# (display name, code slug, function_area, dotted_line functional head role)
DEPT_SPECS: List[Tuple[str, str, str, str]] = [
    ("Production / Process", "PRODUCTION", "OPERATIONS", "COO"),
    ("Quality Control (QC)", "QC", "TECHNICAL", "CSO"),
    ("Mechanical Maintenance", "MECH_MAINT", "TECHNICAL", "CSO"),
    ("Electrical & Instr.", "EI", "TECHNICAL", "CSO"),
    ("Mining / Limestone", "MINING", "TECHNICAL", "CSO"),
    ("Plant Finance", "PLANT_FIN", "FINANCE", "CFO"),
    ("Plant HR / IR", "PLANT_HR", "HR", "CHRO"),
    ("Stores / Procurement", "STORES", "PROCUREMENT", "CPO"),
    ("HSE", "HSE", "TECHNICAL", "CSO"),
]

REGION_CONFIG: List[Tuple[str, str, List[str]]] = [
    ("North", "NORTH", ["Hirmi (Chhattisgarh)", "Roorkee (Uttarakhand)", "Kotputli (Rajasthan)", "Sukinda (Odisha)"]),
    ("West", "WEST", ["Rajashree (Maharashtra)", "Awarpur (Maharashtra)", "Dhar (Gujarat)", "Marwar (Rajasthan)"]),
    ("South", "SOUTH", ["Reddipalayam (Tamil Nadu)", "Sewagram (Karnataka)", "Arakkonam (Tamil Nadu)", "Malkhed (Karnataka)"]),
    ("East", "EAST", ["Dalla (Uttar Pradesh)", "Bela (Madhya Pradesh)", "Bara (Jharkhand)", "Chittorgarh (Rajasthan)"]),
]

FIRST_NAMES = [
    "Aarav", "Priya", "Rajesh", "Sneha", "Vikram", "Meera", "Arjun", "Kavita",
    "Sanjay", "Ananya", "Rahul", "Deepa", "Manish", "Lakshmi", "Suresh", "Neha",
]
LAST_NAMES = [
    "Sharma", "Nair", "Iyer", "Patel", "Reddy", "Joshi", "Gupta", "Menon",
    "Singh", "Desai", "Kumar", "Pillai", "Chatterjee", "Rao", "Verma", "Shah",
]

NAMED_CREDENTIALS: Dict[str, Tuple[str, str, str]] = {
    "superadmin@birlacement.com": ("Ravi Admin", "SUPER_ADMIN", "Platform admin"),
    "ceo@birlacement.com": ("Vikram Mehta", "CEO", "Org OKR owner, functional overview"),
    "coo@birlacement.com": ("Arjun Malhotra", "COO", "Operations vertical, plant line approver"),
    "cro@birlacement.com": ("Kavita Rao", "CRO", "Regions vertical, regional heads"),
    "cfo@birlacement.com": ("Neha Sharma", "CFO", "Finance vertical + plant finance dotted-line"),
    "cmo@birlacement.com": ("Rahul Desai", "CMO", "Sales & marketing vertical"),
    "chro@birlacement.com": ("Ananya Singh", "CHRO", "HR vertical"),
    "cpo@birlacement.com": ("Suresh Kumar", "CPO", "Procurement vertical"),
    "cso@birlacement.com": ("Deepa Joshi", "CSO", "Technical vertical dotted-line for QC/HSE/etc"),
    "regional.north@birlacement.com": ("Meera Patel", "REGIONAL_HEAD", "North region"),
    "regional.west@birlacement.com": ("Sanjay Reddy", "REGIONAL_HEAD", "West region"),
    "sales.west@birlacement.com": ("Pooja Menon", "AREA_SALES_MANAGER", "West area sales"),
    "planthead.west1@birlacement.com": ("Rajesh Iyer", "PLANT_HEAD", "Rajashree plant — line approver for HODs"),
    "hod.production.west1@birlacement.com": ("Manish Gupta", "DEPT_HEAD", "Production HOD — dotted to COO"),
    "hod.finance.west1@birlacement.com": ("Lakshmi Rao", "DEPT_HEAD", "Plant Finance HOD — dotted to CFO"),
    "manager.production.west1@birlacement.com": ("Kiran Verma", "MANAGER", "Production manager"),
    "employee.prod.west1@birlacement.com": ("Sneha Nair", "EMPLOYEE", "Production operator"),
}


def gen_id() -> str:
    return str(uuid.uuid4())


def _pick_name(i: int) -> str:
    return f"{FIRST_NAMES[i % len(FIRST_NAMES)]} {LAST_NAMES[(i // len(FIRST_NAMES)) % len(LAST_NAMES)]}"


def _slug(s: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in s).strip("-")


# ── Reset ─────────────────────────────────────────────────────────────────────

def reset_birla_org(db: Session) -> None:
    org = db.query(Organization).filter(Organization.domain == DOMAIN).first()
    if not org:
        org = db.query(Organization).filter(Organization.name == ORG_NAME).first()
    if not org:
        print("[reset] No Birla Cement org found")
        return

    org_id = org.id
    user_ids = [u.id for u in db.query(User).filter(User.org_id == org_id).all()]
    obj_ids = [o.id for o in db.query(Objective).filter(Objective.org_id == org_id).all()]

    if obj_ids:
        oid_in = ",".join(f"'{o}'" for o in obj_ids)
        for tbl in ("approval_steps", "objective_connections"):
            try:
                db.execute(text(f"DELETE FROM {tbl} WHERE subject_id IN ({oid_in}) OR objective_id IN ({oid_in})"))
            except Exception:
                pass
        for tbl in ("key_results", "progress_submissions", "progress_updates"):
            try:
                db.execute(text(f"DELETE FROM {tbl} WHERE objective_id IN ({oid_in})"))
            except Exception:
                pass
        try:
            db.execute(text(f"DELETE FROM key_results WHERE objective_id IN ({oid_in})"))
        except Exception:
            pass
        db.query(Objective).filter(Objective.org_id == org_id).delete(synchronize_session=False)

    if user_ids:
        uid_in = ",".join(f"'{u}'" for u in user_ids)
        for tbl, col in [
            ("approval_steps", "approver_id"),
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
    print(f"[reset] Removed {ORG_NAME} and all related data")


# ── Upsert helpers ───────────────────────────────────────────────────────────

def upsert_org(db: Session) -> Organization:
    org = db.query(Organization).filter(Organization.domain == DOMAIN).first()
    if org:
        org.name = ORG_NAME
        org.setup_completed = True
        return org
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
    return org


def upsert_org_node(
    db: Session,
    org_id: str,
    code: str,
    node_type: str,
    name: str,
    parent_id: Optional[str],
    *,
    head_user_id: Optional[str] = None,
    functional_parent_id: Optional[str] = None,
    node_metadata: Optional[dict] = None,
    legacy_id: Optional[str] = None,
) -> OrgNode:
    node = (
        db.query(OrgNode)
        .filter(OrgNode.org_id == org_id, OrgNode.code == code, OrgNode.is_active == True)
        .first()
    )
    if node:
        node.name = name
        node.head_user_id = head_user_id or node.head_user_id
        node.functional_parent_id = functional_parent_id
        if node_metadata:
            node.node_metadata = {**(node.node_metadata or {}), **node_metadata}
        return node

    created = create_child_node(
        parent_id=parent_id,
        node_type=node_type,
        name=name,
        org_id=org_id,
        code=code,
        head_user_id=head_user_id,
        node_metadata=node_metadata or {},
        db=db,
        node_id=legacy_id,
    )
    created.functional_parent_id = functional_parent_id
    db.add(created)
    db.flush()
    return created


def upsert_user(
    db: Session,
    org_id: str,
    email: str,
    name: str,
    system_role: str,
    designation_id: Optional[str],
    *,
    plant_id: Optional[str] = None,
    department_id: Optional[str] = None,
    team_id: Optional[str] = None,
    org_node_id: Optional[str] = None,
) -> User:
    u = db.query(User).filter(User.email == email.lower()).first()
    if u:
        u.name = name
        u.system_role = system_role
        u.plant_id = plant_id
        u.department_id = department_id
        u.team_id = team_id
        u.org_node_id = org_node_id
        u.designation_id = designation_id
        u.is_active = True
        return u

    u = User(
        id=gen_id(),
        org_id=org_id,
        email=email.lower(),
        password_hash=get_password_hash(PASSWORD),
        name=name,
        employee_id=f"BC-{email.split('@')[0][:20]}",
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


def ensure_reporting(
    db: Session,
    org_id: str,
    employee_id: str,
    manager_id: str,
    relationship_type: str = "DIRECT",
) -> None:
    if relationship_type == "DIRECT":
        for rel in (
            db.query(ReportingRelationship)
            .filter(
                ReportingRelationship.employee_id == employee_id,
                ReportingRelationship.relationship_type == "DIRECT",
                ReportingRelationship.is_active == True,
            )
            .all()
        ):
            if rel.manager_id != manager_id:
                rel.is_active = False

    existing = (
        db.query(ReportingRelationship)
        .filter(
            ReportingRelationship.org_id == org_id,
            ReportingRelationship.employee_id == employee_id,
            ReportingRelationship.manager_id == manager_id,
            ReportingRelationship.relationship_type == relationship_type,
        )
        .first()
    )
    if existing:
        existing.is_active = True
        return

    db.add(
        ReportingRelationship(
            org_id=org_id,
            employee_id=employee_id,
            manager_id=manager_id,
            relationship_type=relationship_type,
            is_active=True,
        )
    )


def upsert_cycle(
    db: Session,
    org_id: str,
    name: str,
    cycle_type: str,
    start: str,
    end: str,
    freeze: str,
) -> Cycle:
    c = db.query(Cycle).filter(Cycle.org_id == org_id, Cycle.name == name).first()
    if c:
        c.status = "ACTIVE"
        return c
    c = Cycle(
        id=gen_id(),
        org_id=org_id,
        name=name,
        cycle_type=cycle_type,
        start_date=start,
        end_date=end,
        freeze_date=freeze,
        status="ACTIVE",
        applies_to_levels=[0, 1, 2, 3, 4, 5],
    )
    db.add(c)
    db.flush()
    return c


# ── OKR helpers (services — not raw ACTIVE inserts) ───────────────────────────

def add_key_results(
    db: Session,
    objective_id: str,
    specs: List[Tuple[str, float, str]],
) -> List[KeyResult]:
    krs: List[KeyResult] = []
    for title, target, unit in specs:
        kr = KeyResult(
            id=gen_id(),
            objective_id=objective_id,
            title=title,
            target_value=target,
            current_value=0.0,
            unit=unit,
            status="NOT_STARTED",
            weight=1.0,
        )
        db.add(kr)
        krs.append(kr)
    db.flush()
    return krs


def create_draft_objective(
    db: Session,
    org_id: str,
    owner: User,
    level: str,
    title: str,
    cycle_id: str,
    kr_specs: List[Tuple[str, float, str]],
    *,
    parent_id: Optional[str] = None,
    functional_parent_obj_id: Optional[str] = None,
    function_area: Optional[str] = None,
    region_id: Optional[str] = None,
    plant_id: Optional[str] = None,
    department_id: Optional[str] = None,
    team_id: Optional[str] = None,
) -> Objective:
    obj = Objective(
        id=gen_id(),
        org_id=org_id,
        owner_id=owner.id,
        parent_id=parent_id,
        functional_parent_obj_id=functional_parent_obj_id,
        title=title,
        level=level,
        region_id=region_id,
        plant_id=plant_id,
        department_id=department_id,
        team_id=team_id,
        cycle_id=cycle_id,
        function_area=function_area,
        okr_status=OKR_STATUS_DRAFT,
        creation_approval_status="PENDING",
        status="ACTIVE",
        quarter="Q2",
        year=2026,
        allows_cascade=True,
    )
    db.add(obj)
    db.flush()
    add_key_results(db, obj.id, kr_specs)
    return obj


def fully_approve_okr(db: Session, org_id: str, okr: Objective, creator: User) -> None:
    enqueue_okr_creation_approval(db, okr, org_id, creator)
    db.flush()
    while True:
        step = current_step(db, SUBJECT_OKR_CREATION, okr.id)
        if not step or not step.approver_id:
            break
        approve(db, step.id, step.approver_id, comment="Birla seed approval")
    db.flush()


def seed_progress_submission(
    db: Session,
    org_id: str,
    kr: KeyResult,
    submitter: User,
    value: float,
    *,
    approve_line: bool = False,
    approve_functional: bool = False,
) -> ProgressSubmission:
    sub = ProgressSubmission(
        id=gen_id(),
        key_result_id=kr.id,
        objective_id=kr.objective_id,
        submitted_by_id=submitter.id,
        employee_value=value,
        employee_note="Birla seed progress",
        status="PENDING",
    )
    db.add(sub)
    db.flush()
    build_chain(db, org_id, SUBJECT_PROGRESS_SUBMISSION, sub.id, submitter.id)
    db.flush()
    if approve_line:
        step = current_step(db, SUBJECT_PROGRESS_SUBMISSION, sub.id)
        if step and step.approver_id:
            approve(db, step.id, step.approver_id)
    if approve_functional:
        step = current_step(db, SUBJECT_PROGRESS_SUBMISSION, sub.id)
        if step and step.approver_id:
            approve(db, step.id, step.approver_id)
    db.flush()
    return sub


# ── Main seed ─────────────────────────────────────────────────────────────────

def seed_birla_cement(db: Session, *, with_okrs: bool = False) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    cycle_start = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    cycle_end = (now + timedelta(days=335)).strftime("%Y-%m-%d")
    freeze = (now + timedelta(days=300)).strftime("%Y-%m-%d")
    q_end = (now + timedelta(days=60)).strftime("%Y-%m-%d")
    q_freeze = (now + timedelta(days=55)).strftime("%Y-%m-%d")

    org = upsert_org(db)
    org_id = org.id
    ensure_organization_root(db, org_id, ORG_NAME)

    designations: Dict[str, Designation] = {}
    for dname, level, category in [
        ("Chief Executive Officer", 0, "LEADERSHIP"),
        ("Chief Operating Officer", 1, "LEADERSHIP"),
        ("Chief Financial Officer", 1, "LEADERSHIP"),
        ("Chief Marketing Officer", 1, "LEADERSHIP"),
        ("Chief HR Officer", 1, "LEADERSHIP"),
        ("Chief Procurement Officer", 1, "LEADERSHIP"),
        ("Chief Technical Officer", 1, "LEADERSHIP"),
        ("Chief Regional Officer", 1, "LEADERSHIP"),
        ("Regional Head", 2, "LEADERSHIP"),
        ("Plant Head", 2, "PLANT_LEADERSHIP"),
        ("Head of Department", 3, "MANAGEMENT"),
        ("Manager", 4, "MANAGEMENT"),
        ("Team Lead", 5, "MANAGEMENT"),
        ("Supervisor", 5, "OPERATIONAL"),
        ("Functional Sub Head", 3, "MANAGEMENT"),
        ("Area Sales Manager", 4, "MANAGEMENT"),
        ("Sales Officer", 6, "OPERATIONAL"),
        ("Operator", 6, "OPERATIONAL"),
    ]:
        existing = (
            db.query(Designation)
            .filter(Designation.org_id == org_id, Designation.name == dname)
            .first()
        )
        if not existing:
            existing = Designation(
                id=gen_id(), org_id=org_id, name=dname, level=level, category=category, is_active=True
            )
            db.add(existing)
            db.flush()
        designations[dname] = existing

    annual_cycle = upsert_cycle(db, org_id, "FY26 Annual", "ANNUAL", cycle_start, cycle_end, freeze)
    quarterly_cycle = upsert_cycle(
        db, org_id, "Q2-2026", "QUARTERLY", cycle_start, q_end, q_freeze
    )
    active_cycle = quarterly_cycle

    refs: Dict[str, Any] = {
        "users": {},
        "functional_heads": {},
        "vertical_nodes": {},
        "regions": {},
        "plants": {},
        "departments": {},
        "teams": {},
    }
    user_count = 0
    name_idx = 0

    def named_or_generated(email_key: str, role: str, desig: str, **kwargs) -> User:
        nonlocal user_count, name_idx
        if email_key in NAMED_CREDENTIALS:
            name, r, _ = NAMED_CREDENTIALS[email_key]
            role = r
        else:
            name = _pick_name(name_idx)
            name_idx += 1
        u = upsert_user(
            db, org_id, email_key, name, role, designations[desig].id, **kwargs
        )
        refs["users"][email_key] = u
        user_count += 1
        return u

    # CEO + super admin
    ceo = named_or_generated(
        "ceo@birlacement.com", "CEO", "Chief Executive Officer", org_node_id=org_id
    )
    named_or_generated("superadmin@birlacement.com", "SUPER_ADMIN", "Chief Executive Officer", org_node_id=org_id)
    root = db.query(OrgNode).filter(OrgNode.id == org_id).first()
    if root:
        root.head_user_id = ceo.id

    # Corporate function verticals
    for fa_code, fa_label, head_role in FUNCTION_VERTICALS:
        cf_code = f"CF-{fa_code}"
        cf_node = upsert_org_node(
            db, org_id, cf_code, "CORPORATE_FUNCTION", fa_label, org_id,
            node_metadata={"function_area": fa_code, "seed_tag": SEED_TAG},
        )
        vert_code = f"VERT-{fa_code}"
        vert_node = upsert_org_node(
            db, org_id, vert_code, "VERTICAL", fa_label, cf_node.id,
            node_metadata={"function_area": fa_code, "seed_tag": SEED_TAG},
        )
        refs["vertical_nodes"][fa_code] = vert_node

        head_email = FUNCTIONAL_HEAD_EMAILS[head_role]
        head_name = NAMED_CREDENTIALS.get(head_email, (_pick_name(name_idx), head_role, ""))[0]
        role_desig = {
            "COO": "Chief Operating Officer",
            "CFO": "Chief Financial Officer",
            "CMO": "Chief Marketing Officer",
            "CHRO": "Chief HR Officer",
            "CPO": "Chief Procurement Officer",
            "CSO": "Chief Technical Officer",
            "CRO": "Chief Regional Officer",
        }
        head = upsert_user(
            db, org_id, head_email, head_name, head_role,
            designations[role_desig[head_role]].id,
            org_node_id=vert_node.id,
        )
        cf_node.head_user_id = head.id
        vert_node.head_user_id = head.id
        refs["functional_heads"][head_role] = head
        refs["users"][head_email] = head
        ensure_reporting(db, org_id, head.id, ceo.id, "DIRECT")
        user_count += 1

        for sub_name, sub_email in SUB_HEADS.get(head_role, []):
            sub = upsert_user(
                db, org_id, sub_email, sub_name, "FUNCTIONAL_SUB_HEAD",
                designations["Functional Sub Head"].id, org_node_id=vert_node.id,
            )
            ensure_reporting(db, org_id, sub.id, head.id, "DIRECT")
            refs["users"][sub_email] = sub
            user_count += 1

    # Regions → plants → departments → teams
    regions_to_seed = REGION_CONFIG[:NUM_REGIONS]
    cro = refs["functional_heads"]["CRO"]

    for rname, rcode, plant_names in regions_to_seed:
        rslug = rcode.lower()
        rn = upsert_org_node(
            db, org_id, f"REGION-{rcode}", "REGION", f"{rname} Region", org_id,
            node_metadata={"seed_tag": SEED_TAG},
        )

        rh_email = (
            "regional.north@birlacement.com" if rcode == "NORTH"
            else "regional.west@birlacement.com" if rcode == "WEST"
            else f"regional.{rslug}@birlacement.com"
        )
        rh_name = NAMED_CREDENTIALS.get(rh_email, (_pick_name(name_idx),))[0]
        name_idx += 1
        rh = upsert_user(
            db, org_id, rh_email, rh_name, "REGIONAL_HEAD",
            designations["Regional Head"].id, org_node_id=rn.id,
        )
        rn.head_user_id = rh.id
        ensure_reporting(db, org_id, rh.id, cro.id, "DIRECT")
        refs["users"][rh_email] = rh
        user_count += 1

        # Regional sales under CMO
        cmo = refs["functional_heads"]["CMO"]
        rsh = upsert_user(
            db, org_id, f"saleshead.{rslug}@birlacement.com",
            f"{rname} Sales Head", "MANAGER",
            designations["Regional Head"].id, org_node_id=rn.id,
        )
        ensure_reporting(db, org_id, rsh.id, cmo.id, "DIRECT")
        user_count += 1

        asm_email = "sales.west@birlacement.com" if rcode == "WEST" else f"sales.asm.{rslug}@birlacement.com"
        asm = upsert_user(
            db, org_id, asm_email, NAMED_CREDENTIALS.get(asm_email, (_pick_name(name_idx),))[0],
            "AREA_SALES_MANAGER", designations["Area Sales Manager"].id, org_node_id=rn.id,
        )
        name_idx += 1
        ensure_reporting(db, org_id, asm.id, rsh.id, "DIRECT")
        refs["users"][asm_email] = asm
        user_count += 1

        for si in range(2):
            so = upsert_user(
                db, org_id, f"sales.officer.{rslug}.{si + 1}@birlacement.com",
                _pick_name(name_idx), "EMPLOYEE", designations["Sales Officer"].id, org_node_id=rn.id,
            )
            name_idx += 1
            ensure_reporting(db, org_id, so.id, asm.id, "DIRECT")
            user_count += 1

        refs["regions"][rslug] = {"node": rn, "head": rh}

        for pi in range(1, PLANTS_PER_REGION + 1):
            pname = plant_names[pi - 1] if pi - 1 < len(plant_names) else f"{rname} Plant {pi}"
            pkey = f"{rslug}-{pi}"
            pcode = f"{rcode}-P{pi}"

            plant = db.query(Plant).filter(Plant.org_id == org_id, Plant.code == pcode).first()
            if not plant:
                plant = Plant(
                    id=gen_id(), org_id=org_id, name=pname, code=pcode,
                    location=pname, is_active=True,
                )
                db.add(plant)
                db.flush()

            pn = upsert_org_node(
                db, org_id, f"PLANT-{pcode}", "PLANT", pname, rn.id,
                node_metadata={"seed_tag": SEED_TAG}, legacy_id=plant.id,
            )

            ph_email = (
                "planthead.west1@birlacement.com" if pkey == "west-1"
                else f"planthead.{pkey}@birlacement.com"
            )
            ph_name = NAMED_CREDENTIALS.get(ph_email, (_pick_name(name_idx),))[0]
            name_idx += 1
            ph = upsert_user(
                db, org_id, ph_email, ph_name, "PLANT_HEAD",
                designations["Plant Head"].id, plant_id=plant.id, org_node_id=pn.id,
            )
            pn.head_user_id = ph.id
            coo = refs["functional_heads"]["COO"]
            ensure_reporting(db, org_id, ph.id, coo.id, "DIRECT")
            refs["users"][ph_email] = ph
            user_count += 1
            refs["plants"][pkey] = {"plant": plant, "node": pn, "head": ph, "region": rn}

            for dname, dcode, fa, dotted_role in DEPT_SPECS:
                dkey = f"{pkey}-{_slug(dcode)}"
                dept = db.query(Department).filter(
                    Department.org_id == org_id, Department.plant_id == plant.id, Department.dept_type == dcode
                ).first()
                if not dept:
                    dept = Department(
                        id=gen_id(), org_id=org_id, plant_id=plant.id,
                        name=dname, dept_type=dcode, is_active=True,
                    )
                    db.add(dept)
                    db.flush()

                vert = refs["vertical_nodes"].get(fa)
                dn = upsert_org_node(
                    db, org_id, f"DEPT-{pcode}-{dcode}", "DEPARTMENT", dname, pn.id,
                    functional_parent_id=vert.id if vert else None,
                    node_metadata={"function_area": fa, "dept_type": dcode, "seed_tag": SEED_TAG},
                    legacy_id=dept.id,
                )

                hod_email = (
                    "hod.production.west1@birlacement.com" if dkey.endswith("production") and pkey == "west-1"
                    else "hod.finance.west1@birlacement.com" if dkey.endswith("plant-fin") and pkey == "west-1"
                    else f"hod.{dkey}@birlacement.com"
                )
                hod_name = NAMED_CREDENTIALS.get(hod_email, (_pick_name(name_idx),))[0]
                name_idx += 1
                hod = upsert_user(
                    db, org_id, hod_email, hod_name, "DEPT_HEAD",
                    designations["Head of Department"].id,
                    plant_id=plant.id, department_id=dept.id, org_node_id=dn.id,
                )
                dn.head_user_id = hod.id
                ensure_reporting(db, org_id, hod.id, ph.id, "DIRECT")
                func_head = refs["functional_heads"][dotted_role]
                ensure_reporting(db, org_id, hod.id, func_head.id, "DOTTED_LINE")
                refs["users"][hod_email] = hod
                user_count += 1
                refs["departments"][dkey] = {
                    "dept": dept, "node": dn, "head": hod, "plant_key": pkey,
                    "dotted_role": dotted_role, "function_area": fa,
                }

                for mi in range(MANAGERS_PER_DEPT):
                    mgr_email = (
                        "manager.production.west1@birlacement.com"
                        if dkey.endswith("production") and pkey == "west-1" and mi == 0
                        else f"mgr.{dkey}.{mi + 1}@birlacement.com"
                    )
                    mgr_name = NAMED_CREDENTIALS.get(mgr_email, (_pick_name(name_idx),))[0]
                    name_idx += 1
                    mgr = upsert_user(
                        db, org_id, mgr_email, mgr_name, "MANAGER",
                        designations["Manager"].id,
                        plant_id=plant.id, department_id=dept.id, org_node_id=dn.id,
                    )
                    ensure_reporting(db, org_id, mgr.id, hod.id, "DIRECT")
                    refs["users"][mgr_email] = mgr
                    user_count += 1

                    for ti in range(TEAMS_PER_DEPT):
                        tname = f"{dname} Team {ti + 1}"
                        tcode = f"{dcode}-T{ti + 1}"
                        team = db.query(Team).filter(
                            Team.org_id == org_id, Team.department_id == dept.id, Team.name == tname
                        ).first()
                        if not team:
                            team = Team(id=gen_id(), org_id=org_id, department_id=dept.id, name=tname, is_active=True)
                            db.add(team)
                            db.flush()

                        tn = upsert_org_node(
                            db, org_id, f"TEAM-{pcode}-{tcode}", "TEAM", tname, dn.id,
                            legacy_id=team.id,
                        )
                        lead = upsert_user(
                            db, org_id, f"lead.{dkey}.t{ti + 1}@birlacement.com",
                            _pick_name(name_idx), "TEAM_LEAD", designations["Team Lead"].id,
                            plant_id=plant.id, department_id=dept.id, team_id=team.id, org_node_id=tn.id,
                        )
                        name_idx += 1
                        team.lead_id = lead.id
                        tn.head_user_id = lead.id
                        ensure_reporting(db, org_id, lead.id, mgr.id, "DIRECT")
                        existing_tm = (
                            db.query(TeamMember)
                            .filter(TeamMember.team_id == team.id, TeamMember.user_id == lead.id)
                            .first()
                        )
                        if not existing_tm:
                            db.add(TeamMember(
                                org_id=org_id, team_id=team.id, user_id=lead.id,
                                is_team_lead=True, role_in_team="LEAD", is_active=True,
                            ))
                        user_count += 1
                        refs["teams"][f"{dkey}-t{ti + 1}"] = {"team": team, "lead": lead}

                        for ei in range(EMPLOYEES_PER_MANAGER):
                            emp_email = (
                                "employee.prod.west1@birlacement.com"
                                if dkey.endswith("production") and pkey == "west-1" and ei == 0
                                else f"emp.{dkey}.t{ti + 1}.{ei + 1}@birlacement.com"
                            )
                            emp_name = NAMED_CREDENTIALS.get(emp_email, (_pick_name(name_idx),))[0]
                            name_idx += 1
                            emp = upsert_user(
                                db, org_id, emp_email, emp_name, "EMPLOYEE",
                                designations["Operator"].id,
                                plant_id=plant.id, department_id=dept.id, team_id=team.id, org_node_id=tn.id,
                            )
                            ensure_reporting(db, org_id, emp.id, lead.id, "DIRECT")
                            existing_tm = (
                                db.query(TeamMember)
                                .filter(TeamMember.team_id == team.id, TeamMember.user_id == emp.id)
                                .first()
                            )
                            if not existing_tm:
                                db.add(TeamMember(org_id=org_id, team_id=team.id, user_id=emp.id, is_active=True))
                            refs["users"][emp_email] = emp
                            user_count += 1

    db.flush()

    # Optional OKRs
    okr_stats: Dict[str, Any] = {}
    if with_okrs:
        okr_stats = _seed_demo_okrs(db, org_id, ceo, refs, active_cycle.id, annual_cycle.id)

    db.commit()

    # Verify approver resolution for demo HOD
    demo_hod = refs["users"].get("hod.production.west1@birlacement.com")
    approver_check = None
    if demo_hod:
        raw = resolve_approvers(db, demo_hod.id, org_id, persist_if_missing=False)
        approver_check = {}
        for k, uid in raw.items():
            if uid:
                u = db.query(User).filter(User.id == uid).first()
                approver_check[k] = {"id": uid, "email": u.email if u else None, "name": u.name if u else None}
            else:
                approver_check[k] = None

    return {
        "org_id": org_id,
        "user_count": user_count,
        "plant_count": len(refs["plants"]),
        "dept_count": len(refs["departments"]),
        "annual_cycle_id": annual_cycle.id,
        "quarterly_cycle_id": quarterly_cycle.id,
        "okr_stats": okr_stats,
        "approver_check_hod_production": approver_check,
    }


def _seed_demo_okrs(
    db: Session,
    org_id: str,
    ceo: User,
    refs: Dict[str, Any],
    cycle_id: str,
    annual_cycle_id: str,
) -> Dict[str, Any]:
    existing = db.query(Objective).filter(
        Objective.org_id == org_id,
        Objective.title.like("Accelerate profitable growth%"),
    ).first()
    if existing:
        return {"skipped": True, "reason": "demo OKRs already present"}

    objectives: List[Objective] = []
    vertical_okrs: Dict[str, Objective] = {}

    org_okr = create_draft_objective(
        db, org_id, ceo, "ORGANIZATION",
        "Accelerate profitable growth and decarbonise operations",
        annual_cycle_id,
        [("EBITDA improvement (%)", 8, "%"), ("CO₂ intensity reduction (%)", 5, "%")],
    )
    publish_ceo_okr(db, org_okr, ceo, org_id, ceo.id)
    objectives.append(org_okr)

    org_okr2 = create_draft_objective(
        db, org_id, ceo, "ORGANIZATION",
        "Strengthen market leadership across all regions",
        cycle_id,
        [("Market share gain (pts)", 1.5, "pts"), ("Brand NPS", 70, "score")],
        parent_id=org_okr.id,
    )
    publish_ceo_okr(db, org_okr2, ceo, org_id, ceo.id)
    objectives.append(org_okr2)

    fa_role_map = {
        "OPERATIONS": "COO", "FINANCE": "CFO", "HR": "CHRO",
        "SALES_MARKETING": "CMO", "PROCUREMENT": "CPO", "TECHNICAL": "CSO", "REGIONS": "CRO",
    }
    for fa_code, _label, head_role in FUNCTION_VERTICALS:
        head = refs["functional_heads"][head_role]
        vo = create_draft_objective(
            db, org_id, head, "VERTICAL",
            f"{FUNCTION_AREA_LABELS.get(fa_code, fa_code)} — FY26 priorities",
            cycle_id,
            [("Vertical KPI attainment (%)", 90, "%"), ("Initiative on-track (%)", 85, "%")],
            parent_id=org_okr.id,
            function_area=fa_code,
        )
        fully_approve_okr(db, org_id, vo, head)
        vertical_okrs[fa_code] = vo
        objectives.append(vo)

    plant_okrs: Dict[str, Objective] = {}
    for pkey in ("west-1", "north-1", "south-1", "east-1"):
        pdata = refs["plants"].get(pkey)
        if not pdata:
            continue
        ph = pdata["head"]
        po = create_draft_objective(
            db, org_id, ph, "PLANT",
            f"{pdata['plant'].name} — operational excellence",
            cycle_id,
            [("OEE (%)", 85, "%"), ("Specific power (kWh/t)", 68, "kWh/t")],
            parent_id=org_okr.id,
            region_id=pdata["region"].id,
            plant_id=pdata["plant"].id,
        )
        fully_approve_okr(db, org_id, po, ph)
        plant_okrs[pkey] = po
        objectives.append(po)

    pending_count = 0
    active_count = 0
    for i, (dkey, ddata) in enumerate(list(refs["departments"].items())):
        pkey = ddata["plant_key"]
        if pkey not in ("west-1", "north-1"):
            continue
        hod = ddata["head"]
        po = plant_okrs.get(pkey) or plant_okrs.get("west-1")
        if not po:
            continue
        fa = ddata["function_area"]
        v_okr = vertical_okrs.get(fa)
        do = create_draft_objective(
            db, org_id, hod, "DEPARTMENT",
            f"{ddata['dept'].name} — department OKR",
            cycle_id,
            [("Dept target attainment (%)", 92, "%"), ("Safety incidents", 0, "count")],
            parent_id=po.id,
            functional_parent_obj_id=v_okr.id if v_okr else None,
            function_area=fa,
            region_id=refs["plants"][pkey]["region"].id,
            plant_id=ddata["dept"].plant_id,
            department_id=ddata["dept"].id,
        )
        if i % 3 == 0 and not dkey.endswith("production"):
            enqueue_okr_creation_approval(db, do, org_id, hod)
            pending_count += 1
        else:
            fully_approve_okr(db, org_id, do, hod)
            active_count += 1
        objectives.append(do)

    # Progress submissions on production HOD active OKR
    prod_hod = refs["users"].get("hod.production.west1@birlacement.com")
    progress_stats = {"pending_s1": 0, "pending_s2": 0, "approved": 0}
    if prod_hod:
        active_dept = (
            db.query(Objective)
            .filter(
                Objective.owner_id == prod_hod.id,
                Objective.okr_status == "ACTIVE",
                Objective.department_id.isnot(None),
            )
            .first()
        )
        if not active_dept:
            # Ensure at least one active production dept OKR for progress demo
            ddata = refs["departments"].get("west-1-production")
            if ddata:
                po = plant_okrs.get("west-1")
                v_okr = vertical_okrs.get("OPERATIONS")
                active_dept = create_draft_objective(
                    db, org_id, prod_hod, "DEPARTMENT",
                    "Production / Process — department OKR (progress demo)",
                    cycle_id,
                    [("Kiln run factor (%)", 92, "%"), ("Daily output (t)", 10000, "t")],
                    parent_id=po.id if po else org_okr.id,
                    functional_parent_obj_id=v_okr.id if v_okr else None,
                    function_area="OPERATIONS",
                    plant_id=ddata["dept"].plant_id,
                    department_id=ddata["dept"].id,
                )
                fully_approve_okr(db, org_id, active_dept, prod_hod)
                objectives.append(active_dept)
                active_count += 1
        if active_dept:
            kr = db.query(KeyResult).filter(KeyResult.objective_id == active_dept.id).first()
            if kr:
                seed_progress_submission(db, org_id, kr, prod_hod, 45.0)
                progress_stats["pending_s1"] += 1
                seed_progress_submission(db, org_id, kr, prod_hod, 55.0, approve_line=True)
                progress_stats["pending_s2"] += 1
                seed_progress_submission(db, org_id, kr, prod_hod, 60.0, approve_line=True, approve_functional=True)
                progress_stats["approved"] += 1

    cascade = OKRCascadeService(db)
    for obj in objectives:
        if obj.okr_status == "ACTIVE":
            cascade.refresh_objective_progress_for_session(obj.id)

    return {
        "total": len(objectives),
        "pending_dept": pending_count,
        "active_dept": active_count,
        "vertical": len(vertical_okrs),
        "progress": progress_stats,
    }


def write_credentials(result: Dict[str, Any]) -> Path:
    lines = [
        "# Birla Cement — Login Credentials",
        "",
        f"**Organization:** {ORG_NAME}  ",
        f"**Domain:** `{DOMAIN}`  ",
        f"**Password (all users):** `{PASSWORD}`  ",
        f"**Users seeded:** {result.get('user_count', '?')}  ",
        f"**Plants:** {result.get('plant_count', '?')}  ",
        "",
        "## Demo accounts (one per role)",
        "",
        "| Role | Email | Name | Notes |",
        "|------|-------|------|-------|",
    ]
    for email, (name, role, note) in NAMED_CREDENTIALS.items():
        lines.append(f"| {role} | `{email}` | {name} | {note} |")

    lines.extend([
        "",
        "## Reporting chain (approval routing)",
        "",
        "```",
        "CEO",
        " ├── COO, CFO, CMO, CHRO, CPO, CSO, CRO (DIRECT)",
        " │     └── Functional sub-heads (DIRECT to their head)",
        " ├── CRO → Regional Heads (DIRECT)",
        " ├── CMO → Regional Sales Heads → ASM → Sales Officers",
        " └── COO → Plant Heads (DIRECT) → HODs (DIRECT)",
        "       └── HODs → DOTTED_LINE → functional head (QC→CSO, Finance→CFO, etc.)",
        "```",
        "",
        "## Commands",
        "",
        "```bash",
        "python scripts/seed_birla_cement.py --reset --with-okrs",
        "```",
        "",
    ])
    if result.get("approver_check_hod_production"):
        ac = result["approver_check_hod_production"]
        lines.append("**HOD production approver resolution:**")
        for stage in ("line", "functional"):
            info = ac.get(stage)
            if info:
                lines.append(f"- {stage}: `{info.get('email')}` ({info.get('name')})")
        lines.append("")

    path = Path(__file__).parent.parent / "BIRLA_CEMENT_CREDENTIALS.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Birla Cement org with dual-approval reporting")
    parser.add_argument("--reset", action="store_true", help="Remove existing Birla Cement org data first")
    parser.add_argument("--with-okrs", action="store_true", help="Seed demonstration OKRs and progress queues")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.reset:
            reset_birla_org(db)
        result = seed_birla_cement(db, with_okrs=args.with_okrs)
        cred_path = write_credentials(result)

        print("\n=== Birla Cement Seed Complete ===")
        print(f"Organization: {ORG_NAME} ({result['org_id']})")
        print(f"Users: {result['user_count']}")
        print(f"Plants: {result['plant_count']}")
        print(f"Departments: {result['dept_count']}")
        print(f"Cycles: FY26 Annual + Q2-2026")
        if args.with_okrs:
            print(f"OKRs: {result.get('okr_stats')}")
        if result.get("approver_check_hod_production"):
            ac = result["approver_check_hod_production"]
            line = ac.get("line") or {}
            func = ac.get("functional") or {}
            print(f"HOD production approvers: line={line.get('email')} functional={func.get('email')}")
        print(f"\nCredentials: {cred_path}")
        print(f"\nPassword for all users: {PASSWORD}")
        for email, (name, role, _) in NAMED_CREDENTIALS.items():
            print(f"  [{role:18}] {email}")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
