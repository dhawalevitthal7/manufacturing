#!/usr/bin/env python3
import sys
import os
import uuid
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to path to import server modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from server.database import SessionLocal, engine, Base
from server.auth import get_password_hash
from server.permissions_service import initialize_user_permissions
from server.okr_cascade_service import OKRCascadeService, calculate_objective_progress
from server.services.org_tree_service import create_child_node, ensure_organization_root
from server.models import (
    Organization,
    OrgNode,
    User,
    Designation,
    Cycle,
    Objective,
    KeyResult,
    ReportingRelationship,
    ProgressSubmission,
    ProgressUpdate,
    Team,
    TeamMember,
    Plant,
    Department,
    Review,
    ReviewCycle
)

PASSWORD = "Simulation@123"

def gen_uuid() -> str:
    return str(uuid.uuid4())

# Matches top-bar default period filter (Q2 2026) used by GET /api/okrs
PERIOD_YEAR = 2026
PERIOD_QUARTER = "Q2"

def okr_period_fields() -> dict:
    return {"year": PERIOD_YEAR, "quarter": PERIOD_QUARTER}

def _slug(value: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in value).strip("-")

def resolve_cement_excel_path() -> str:
    candidates = [
        Path(__file__).parent.parent / "Cement_1200_Employee_OKR_Planning.xlsx",
        Path(r"c:\Users\dhawa\Downloads\Cement_1200_Employee_OKR_Planning.xlsx"),
        Path(r"c:\Users\dhawa\Desktop\manufacturing\Cement_1200_Employee_OKR_Planning.xlsx"),
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    raise FileNotFoundError("Cement_1200_Employee_OKR_Planning.xlsx not found in project root or Downloads")

def add_reporting(
    db: Session,
    org_id: str,
    employee_id: str,
    manager_id: str,
    relationship_type: str = "DIRECT",
) -> None:
    existing = db.query(ReportingRelationship).filter(
        ReportingRelationship.org_id == org_id,
        ReportingRelationship.employee_id == employee_id,
        ReportingRelationship.manager_id == manager_id,
        ReportingRelationship.relationship_type == relationship_type,
    ).first()
    if existing:
        existing.is_active = True
        return
    db.add(ReportingRelationship(
        org_id=org_id,
        employee_id=employee_id,
        manager_id=manager_id,
        relationship_type=relationship_type,
        is_active=True,
    ))

# Cement simulation — region/plant mapping and department → executive committee
CEMENT_PLANT_REGION = {
    "Rajasthan Plant": ("West", "WEST"),
    "MP Plant": ("Central", "CENTRAL"),
    "Mumbai HQ": ("Corporate", "CORP"),
}

DEPT_FUNCTION_MAP = {
    "Sales": ("CMO", "SALES_MARKETING"),
    "HR": ("CHRO", "HR"),
    "Finance": ("CFO", "FINANCE"),
    "Procurement": ("CPO", "PROCUREMENT"),
    "IT": ("CTO", "TECHNICAL"),
    "Manufacturing": ("COO", "OPERATIONS"),
    "Maintenance": ("COO", "OPERATIONS"),
    "Quality": ("COO", "OPERATIONS"),
    "Safety": ("COO", "OPERATIONS"),
    "Supply Chain": ("COO", "OPERATIONS"),
}

CEMENT_EXEC_COMMITTEE = [
    ("COO", "Arjun Malhotra", "coo@cementokr.com"),
    ("CFO", "Neha Sharma", "cfo@cementokr.com"),
    ("CHRO", "Ananya Singh", "chro@cementokr.com"),
    ("CMO", "Rahul Desai", "cmo@cementokr.com"),
    ("CPO", "Suresh Kumar", "cpo@cementokr.com"),
    ("CTO", "Deepa Joshi", "cto@cementokr.com"),
    ("CRO", "Kavita Rao", "cro@cementokr.com"),
]

LINE_MANAGER_DESIGNATIONS = ("Manager", "Senior Manager", "Assistant Manager", "Senior Engineer")
MANAGEMENT_DESIGNATIONS = ("Manager", "Senior Manager", "Assistant Manager")

def pick_line_manager_ids(df: pd.DataFrame) -> dict:
    """First suitable manager per plant+department for line reporting."""
    picks: dict = {}
    for (loc, dept), group in df.groupby(["Location", "Department"]):
        for desig in LINE_MANAGER_DESIGNATIONS:
            subset = group[group["Designation"] == desig]
            if not subset.empty:
                picks[(loc, dept)] = int(subset.iloc[0]["Employee ID"])
                break
    return picks

def _progress_triplet(q1: float, q2: float, current: float) -> dict:
    return {"q1": round(float(q1), 1), "q2": round(float(q2), 1), "current": round(float(current), 1)}

def compute_cement_progress_aggregates(df: pd.DataFrame) -> dict:
    """Roll up Q1/Q2/current achievement % from employee rows."""
    dept_stats = {}
    for (loc, dept), group in df.groupby(["Location", "Department"]):
        dept_stats[(loc, dept)] = _progress_triplet(
            group["Q1 Achievement %"].mean(),
            group["Q2 Achievement %"].mean(),
            group["Achievement by Friday %"].mean(),
        )

    plant_stats = {}
    for loc, group in df.groupby("Location"):
        plant_stats[loc] = _progress_triplet(
            group["Q1 Achievement %"].mean(),
            group["Q2 Achievement %"].mean(),
            group["Achievement by Friday %"].mean(),
        )

    region_groups: dict = {}
    for loc, group in df.groupby("Location"):
        rcode = CEMENT_PLANT_REGION.get(loc, ("West", "WEST"))[1]
        region_groups.setdefault(rcode, []).append(group)
    region_stats = {}
    for rcode, groups in region_groups.items():
        merged = pd.concat(groups)
        region_stats[rcode] = _progress_triplet(
            merged["Q1 Achievement %"].mean(),
            merged["Q2 Achievement %"].mean(),
            merged["Achievement by Friday %"].mean(),
        )

    org_stats = _progress_triplet(
        df["Q1 Achievement %"].mean(),
        df["Q2 Achievement %"].mean(),
        df["Achievement by Friday %"].mean(),
    )
    return {
        "dept": dept_stats,
        "plant": plant_stats,
        "region": region_stats,
        "org": org_stats,
    }

def _kr_status(current_val: float, target_val: float) -> str:
    if target_val <= 0:
        return "NOT_STARTED"
    pct = (current_val / target_val) * 100.0
    if pct >= 100.0:
        return "COMPLETED"
    if pct > 0:
        return "IN_PROGRESS"
    return "NOT_STARTED"

def seed_krs_with_quarterly_progress(
    db: Session,
    obj: Objective,
    submitter_id: str,
    now: datetime,
    kr_specs: list,
    progress: dict,
    *,
    notes_prefix: str = "",
) -> None:
    """Add key results plus Q1/Q2/current progress updates; sync objective.progress."""
    q1_pct = progress["q1"]
    q2_pct = progress["q2"]
    current_pct = progress["current"]

    for title, target, unit, weight in kr_specs:
        q1_val = round(target * q1_pct / 100.0, 2)
        q2_val = round(target * q2_pct / 100.0, 2)
        current_val = round(target * current_pct / 100.0, 2)

        kr = KeyResult(
            id=gen_uuid(),
            objective_id=obj.id,
            title=title,
            target_value=target,
            current_value=current_val,
            unit=unit,
            status=_kr_status(current_val, target),
            weight=weight,
        )
        db.add(kr)
        db.flush()

        prefix = f"{notes_prefix}: " if notes_prefix else ""
        db.add(ProgressUpdate(
            id=gen_uuid(),
            key_result_id=kr.id,
            submitted_by_id=submitter_id,
            previous_value=0.0,
            new_value=q1_val,
            notes=f"{prefix}Q1 progress ({q1_pct}%)",
            status="APPROVED",
            created_at=now - pd.Timedelta(days=60),
            validated_at=now - pd.Timedelta(days=58),
        ))
        db.add(ProgressUpdate(
            id=gen_uuid(),
            key_result_id=kr.id,
            submitted_by_id=submitter_id,
            previous_value=q1_val,
            new_value=q2_val,
            notes=f"{prefix}Q2 progress ({q2_pct}%)",
            status="APPROVED",
            created_at=now - pd.Timedelta(days=20),
            validated_at=now - pd.Timedelta(days=19),
        ))
        db.add(ProgressUpdate(
            id=gen_uuid(),
            key_result_id=kr.id,
            submitted_by_id=submitter_id,
            previous_value=q2_val,
            new_value=current_val,
            notes=f"{prefix}Current progress ({current_pct}%)",
            status="APPROVED",
            created_at=now,
            validated_at=now,
        ))

    krs = db.query(KeyResult).filter(KeyResult.objective_id == obj.id).all()
    result = calculate_objective_progress(krs)
    obj.progress = result["progress"]
    obj.status = "COMPLETED" if result["progress"] >= 100.0 else "ACTIVE"

ORG_KR_SPECS = [
    ("EBITDA improvement", 12.0, "%", 1.0),
    ("Safety compliance", 100.0, "%", 1.0),
    ("Sustainability reduction", 10.0, "%", 1.0),
]
REGION_KR_SPECS = [
    ("Regional KPI attainment", 100.0, "%", 1.0),
    ("Safety score", 100.0, "%", 1.0),
]
PLANT_KR_SPECS = [
    ("Plant OEE", 85.0, "%", 1.0),
    ("Cost per tonne reduction", 5.0, "%", 1.0),
    ("Zero harm days", 365.0, "days", 1.0),
]
DEPT_KR_SPECS = [
    ("Department KPI attainment", 100.0, "%", 1.0),
    ("Quarterly initiative completion", 100.0, "%", 1.0),
]
TEAM_KR_SPECS = [
    ("Team deliverable attainment", 100.0, "%", 1.0),
    ("Weekly milestone completion", 100.0, "%", 1.0),
]
TEAMS_PER_DEPT = 2

def build_team_groups(df: pd.DataFrame, teams_per_dept: int = TEAMS_PER_DEPT) -> tuple:
    """Split each plant+department employee set into teams."""
    emp_team_key: dict = {}
    team_groups: dict = {}
    for (loc, dept), group in df.groupby(["Location", "Department"]):
        member_ids = group.sort_values("Employee ID")["Employee ID"].astype(int).tolist()
        n = len(member_ids)
        chunk = max(1, (n + teams_per_dept - 1) // teams_per_dept)
        for team_idx in range(teams_per_dept):
            start = team_idx * chunk
            end = min(start + chunk, n)
            if start >= end:
                continue
            ids = member_ids[start:end]
            key = (loc, dept, team_idx)
            team_groups[key] = ids
            for emp_id in ids:
                emp_team_key[emp_id] = key
    return emp_team_key, team_groups

def team_progress_from_df(df: pd.DataFrame, member_ids: list) -> dict:
    subset = df[df["Employee ID"].isin(member_ids)]
    if subset.empty:
        return {"q1": 0.0, "q2": 0.0, "current": 0.0}
    return _progress_triplet(
        subset["Q1 Achievement %"].mean(),
        subset["Q2 Achievement %"].mean(),
        subset["Achievement by Friday %"].mean(),
    )

def clear_existing_simulation_orgs(db: Session, domains: list[str]) -> None:
    """Removes previous simulation organizations to keep seeding idempotent."""
    for domain in domains:
        org = db.query(Organization).filter(Organization.domain == domain).first()
        if not org:
            continue
        org_id = org.id
        print(f"Clearing previous data for org: {org.name} ({org_id})")
        
        # Delete dependent tables first
        db.query(Review).filter(Review.org_id == org_id).delete()
        db.query(ReviewCycle).filter(ReviewCycle.org_id == org_id).delete()
        db.query(ProgressSubmission).filter(ProgressSubmission.key_result_id.in_(
            db.query(KeyResult.id).join(Objective).filter(Objective.org_id == org_id)
        )).delete(synchronize_session=False)
        db.query(ProgressUpdate).filter(ProgressUpdate.key_result_id.in_(
            db.query(KeyResult.id).join(Objective).filter(Objective.org_id == org_id)
        )).delete(synchronize_session=False)
        db.query(KeyResult).filter(KeyResult.objective_id.in_(
            db.query(Objective.id).filter(Objective.org_id == org_id)
        )).delete(synchronize_session=False)
        db.query(Objective).filter(Objective.org_id == org_id).delete()
        db.query(TeamMember).filter(TeamMember.org_id == org_id).delete()
        db.query(Team).filter(Team.org_id == org_id).delete()
        db.query(ReportingRelationship).filter(ReportingRelationship.org_id == org_id).delete()
        
        # Clear users and their profiles
        user_ids = [u.id for u in db.query(User).filter(User.org_id == org_id).all()]
        if user_ids:
            from server.models import UserPermissionProfile
            db.query(UserPermissionProfile).filter(UserPermissionProfile.user_id.in_(user_ids)).delete(synchronize_session=False)
            db.query(User).filter(User.org_id == org_id).delete()
            
        db.query(Department).filter(Department.org_id == org_id).delete()
        db.query(Plant).filter(Plant.org_id == org_id).delete()
        db.query(OrgNode).filter(OrgNode.org_id == org_id).delete()
        db.query(Designation).filter(Designation.org_id == org_id).delete()
        db.query(Cycle).filter(Cycle.org_id == org_id).delete()
        db.query(Organization).filter(Organization.id == org_id).delete()
        
        db.commit()

def get_or_create_designation(db: Session, org_id: str, name: str, level: int, category: str) -> Designation:
    des = db.query(Designation).filter(Designation.org_id == org_id, Designation.name == name).first()
    if not des:
        des = Designation(id=gen_uuid(), org_id=org_id, name=name, level=level, category=category, is_active=True)
        db.add(des)
        db.flush()
    return des

def ingest_align360_data(db: Session) -> None:
    excel_path = r'c:\Users\dhawa\Desktop\manufacturing\ALIGN360_Enterprise_Simulation_Workbook (1).xlsx'
    print(f"\n[ALIGN360] Ingesting Data from {excel_path}...")
    
    # 1. Read Excel sheets
    df_emp = pd.read_excel(excel_path, sheet_name='Employee_Master')
    df_okr = pd.read_excel(excel_path, sheet_name='Employee_OKRs')
    df_perf = pd.read_excel(excel_path, sheet_name='Performance')
    df_coach = pd.read_excel(excel_path, sheet_name='AI_Coaching')
    
    # 2. Setup organization
    org = Organization(
        id=gen_uuid(),
        name="ALIGN360 Simulation",
        domain="align360.com",
        industry="Simulation / Manufacturing",
        size="LARGE",
        setup_completed=True
    )
    db.add(org)
    db.flush()
    org_id = org.id
    
    # Create org root node
    root_node = ensure_organization_root(db, org_id, org.name)
    
    # 3. Setup Cycles
    now = datetime.now(timezone.utc)
    cycle_start = (now - pd.Timedelta(days=90)).strftime("%Y-%m-%d")
    cycle_end = (now + pd.Timedelta(days=270)).strftime("%Y-%m-%d")
    freeze = (now + pd.Timedelta(days=240)).strftime("%Y-%m-%d")
    
    annual_cycle = Cycle(
        id=gen_uuid(),
        org_id=org_id,
        name="FY26 Annual",
        cycle_type="ANNUAL",
        start_date=cycle_start,
        end_date=cycle_end,
        freeze_date=freeze,
        status="ACTIVE",
        applies_to_levels=[0, 1, 2, 3, 4, 5]
    )
    quarterly_cycle = Cycle(
        id=gen_uuid(),
        org_id=org_id,
        name="Q2-2026",
        cycle_type="QUARTERLY",
        start_date=cycle_start,
        end_date=(now + pd.Timedelta(days=30)).strftime("%Y-%m-%d"),
        freeze_date=(now + pd.Timedelta(days=25)).strftime("%Y-%m-%d"),
        status="ACTIVE",
        applies_to_levels=[0, 1, 2, 3, 4, 5]
    )
    db.add(annual_cycle)
    db.add(quarterly_cycle)
    db.flush()
    
    # 4. Designations mapping
    desig_map = {
        "CEO": get_or_create_designation(db, org_id, "CEO", 0, "LEADERSHIP"),
        "CXO": get_or_create_designation(db, org_id, "CXO", 1, "LEADERSHIP"),
        "Plant Heads": get_or_create_designation(db, org_id, "Plant Head", 2, "PLANT_LEADERSHIP"),
        "HODs": get_or_create_designation(db, org_id, "Head of Department", 3, "MANAGEMENT"),
        "Manager": get_or_create_designation(db, org_id, "Manager", 4, "MANAGEMENT"),
        "Sr Engineer": get_or_create_designation(db, org_id, "Senior Engineer", 5, "OPERATIONAL"),
        "Engineer": get_or_create_designation(db, org_id, "Engineer", 6, "OPERATIONAL"),
        "Executive": get_or_create_designation(db, org_id, "Executive", 6, "OPERATIONAL"),
    }
    
    # 5. Create CEO & functional managers
    ceo_user = User(
        id=gen_uuid(),
        org_id=org_id,
        email="ceo@align360.com",
        password_hash=get_password_hash(PASSWORD),
        name="Vikram Mehta",
        employee_id="BC-ceo",
        system_role="CEO",
        is_active=True,
        org_node_id=root_node.id,
        designation_id=desig_map["CEO"].id
    )
    db.add(ceo_user)
    db.flush()
    initialize_user_permissions(ceo_user, db, commit=False)
    root_node.head_user_id = ceo_user.id
    
    # Create the 10 departments and functional managers
    managers_dict = {}
    manager_names = df_emp['Manager'].dropna().unique()
    
    # Plants in ALIGN360
    plant_names = ["MP Plant", "Rajasthan Plant", "Mumbai HQ"]
    plants_dict = {}
    
    for pname in plant_names:
        # Create Plant entry
        pcode = pname.split(' ')[0].upper()
        p = Plant(id=gen_uuid(), org_id=org_id, name=pname, code=pcode, location=pname, is_active=True)
        db.add(p)
        db.flush()
        
        # Create Plant OrgNode
        pn = create_child_node(
            parent_id=root_node.id,
            node_type="PLANT",
            name=pname,
            org_id=org_id,
            code=f"PLANT-{pcode}",
            db=db,
            node_id=p.id
        )
        db.add(pn)
        db.flush()
        plants_dict[pname] = {"plant": p, "node": pn}
        
    # Standard functional departments
    dept_names = df_emp['Department'].dropna().unique()
    depts_dict = {}
    
    # Setup HOD/Managers
    for mname in manager_names:
        dept_name = mname.replace(" Manager", "")
        # Find a suitable email and system role for manager
        mgr_email = f"{dept_name.lower().replace(' ', '')}.manager@align360.com"
        
        # Assign manager to a default location (HQ or default plant)
        default_plant = plants_dict["Mumbai HQ"]["plant"]
        default_node = plants_dict["Mumbai HQ"]["node"]
        
        # Create Department OrgNode under Mumbai HQ
        dept_code = dept_name.upper().replace(' ', '_')
        dept_obj = Department(id=gen_uuid(), org_id=org_id, plant_id=default_plant.id, name=dept_name, dept_type=dept_code, is_active=True)
        db.add(dept_obj)
        db.flush()
        
        dept_node = create_child_node(
            parent_id=default_node.id,
            node_type="DEPARTMENT",
            name=dept_name,
            org_id=org_id,
            code=f"DEPT-HQ-{dept_code}",
            db=db,
            node_id=dept_obj.id
        )
        db.add(dept_node)
        db.flush()
        
        mgr_user = User(
            id=gen_uuid(),
            org_id=org_id,
            email=mgr_email,
            password_hash=get_password_hash(PASSWORD),
            name=mname,
            employee_id=f"BC-{dept_name.lower().replace(' ', '')}-mgr",
            system_role="DEPT_HEAD",
            is_active=True,
            plant_id=default_plant.id,
            department_id=dept_obj.id,
            org_node_id=dept_node.id,
            designation_id=desig_map["HODs"].id
        )
        db.add(mgr_user)
        db.flush()
        initialize_user_permissions(mgr_user, db, commit=False)
        
        # Reporting relationship
        db.add(ReportingRelationship(org_id=org_id, employee_id=mgr_user.id, manager_id=ceo_user.id, relationship_type="DIRECT", is_active=True))
        
        managers_dict[mname] = mgr_user
        depts_dict[dept_name] = {"dept": dept_obj, "node": dept_node}
        
    # 6. Ingest 1200 Employees
    employee_dict = {}
    print("Seeding 1200 employees...")
    for idx, row in df_emp.iterrows():
        emp_id = int(row['EmpID'])
        name = row['Name']
        loc = row['Location']
        dept = row['Department']
        desig = row['Designation']
        manager_name = row['Manager']
        role_dna = row['Role DNA']
        
        # Get plant/dept structure
        p_info = plants_dict.get(loc)
        if not p_info:
            p_info = plants_dict["MP Plant"] # fallback
            
        # Create department under this plant if not existing
        dept_code = dept.upper().replace(' ', '_')
        dept_db = db.query(Department).filter(
            Department.org_id == org_id,
            Department.plant_id == p_info["plant"].id,
            Department.name == dept
        ).first()
        if not dept_db:
            dept_db = Department(id=gen_uuid(), org_id=org_id, plant_id=p_info["plant"].id, name=dept, dept_type=dept_code, is_active=True)
            db.add(dept_db)
            db.flush()
            
            dept_node = create_child_node(
                parent_id=p_info["node"].id,
                node_type="DEPARTMENT",
                name=dept,
                org_id=org_id,
                code=f"DEPT-{p_info['plant'].code}-{dept_code}",
                db=db,
                node_id=dept_db.id
            )
            db.add(dept_node)
            db.flush()
        else:
            dept_node = db.query(OrgNode).filter(OrgNode.org_id == org_id, OrgNode.id == dept_db.id).first()
            if not dept_node:
                dept_node = create_child_node(
                    parent_id=p_info["node"].id,
                    node_type="DEPARTMENT",
                    name=dept,
                    org_id=org_id,
                    code=f"DEPT-{p_info['plant'].code}-{dept_code}",
                    db=db,
                    node_id=dept_db.id
                )
                db.add(dept_node)
                db.flush()
                
        # Resolve manager user
        mgr_user = managers_dict.get(manager_name)
        if not mgr_user:
            mgr_user = ceo_user # fallback
            
        # Resolve designation
        des_obj = desig_map.get(desig)
        if not des_obj:
            des_obj = desig_map["Engineer"] # fallback
            
        # Create user
        email = f"employee.{emp_id}@align360.com"
        u = User(
            id=gen_uuid(),
            org_id=org_id,
            email=email,
            password_hash=get_password_hash(PASSWORD),
            name=name,
            employee_id=f"BC-{emp_id}",
            system_role="EMPLOYEE",
            is_active=True,
            plant_id=p_info["plant"].id,
            department_id=dept_db.id,
            org_node_id=dept_node.id,
            designation_id=des_obj.id
        )
        db.add(u)
        db.flush()
        initialize_user_permissions(u, db, commit=False)
        
        # Reporting Relationship
        db.add(ReportingRelationship(org_id=org_id, employee_id=u.id, manager_id=mgr_user.id, relationship_type="DIRECT", is_active=True))
        
        employee_dict[emp_id] = u
        
    db.flush()
    print("Employee user accounts seeded.")
    
    # 7. Create OKRs
    # CEO/Org OKR
    org_okr = Objective(
        id=gen_uuid(),
        org_id=org_id,
        owner_id=ceo_user.id,
        title="Improve EBITDA 12%, Safety 100%, Sustainability 10%",
        level="ORGANIZATION",
        status="ACTIVE",
        cycle_id=annual_cycle.id,
        progress=0.0,
        okr_status="ACTIVE",
        creation_approval_status="APPROVED",
        allows_cascade=True,
        **okr_period_fields(),
    )
    db.add(org_okr)
    db.flush()
    
    # Dept OKRs
    dept_okrs_dict = {}
    unique_dept_okrs = df_okr['Dept OKR'].dropna().unique()
    for do_title in unique_dept_okrs:
        # Resolve department owner
        dept_name = do_title.replace("Achieve ", "").replace(" annual KPI targets", "").strip()
        mgr_user = None
        for mname, muser in managers_dict.items():
            if dept_name.lower() in mname.lower():
                mgr_user = muser
                break
        if not mgr_user:
            mgr_user = ceo_user
            
        dob = Objective(
            id=gen_uuid(),
            org_id=org_id,
            owner_id=mgr_user.id,
            parent_id=org_okr.id,
            title=do_title,
            level="DEPARTMENT",
            status="ACTIVE",
            cycle_id=annual_cycle.id,
            progress=0.0,
            okr_status="ACTIVE",
            creation_approval_status="APPROVED",
            allows_cascade=True,
            plant_id=mgr_user.plant_id,
            department_id=mgr_user.department_id,
            **okr_period_fields(),
        )
        db.add(dob)
        db.flush()
        dept_okrs_dict[do_title] = dob
        
    # Individual OKRs
    print("Seeding individual OKRs and progress logs...")
    for idx, row in df_okr.iterrows():
        emp_id = int(row['EmpID'])
        dept_okr_title = row['Dept OKR']
        okr1 = row['Individual OKR 1']
        okr2 = row['Individual OKR 2']
        okr3 = row['Individual OKR 3']
        
        u = employee_dict.get(emp_id)
        if not u:
            continue
            
        parent_obj = dept_okrs_dict.get(dept_okr_title)
        parent_id = parent_obj.id if parent_obj else None
        
        # Get performance data
        perf_row = df_perf[df_perf['EmpID'] == emp_id]
        q1_val = 0.0
        q2_val = 0.0
        friday_val = 0.0
        status_val = "Green"
        
        if not perf_row.empty:
            q1_val = float(perf_row.iloc[0]['Q1 %'])
            q2_val = float(perf_row.iloc[0]['Q2 %'])
            friday_val = float(perf_row.iloc[0]['Friday Target %'])
            status_val = perf_row.iloc[0]['Status']
            
        # Get AI Coaching recommendation
        coach_row = df_coach[df_coach['EmpID'] == emp_id]
        risk_val = "Low"
        recom_val = ""
        if not coach_row.empty:
            risk_val = coach_row.iloc[0]['Risk']
            recom_val = coach_row.iloc[0]['Recommendation']

        emp_row = df_emp[df_emp['EmpID'] == emp_id]
        alignment_score = int(emp_row.iloc[0]['Alignment Score']) if not emp_row.empty else 0
        reviewer = managers_dict.get(emp_row.iloc[0]['Manager'], ceo_user) if not emp_row.empty else ceo_user
            
        # Add up to 3 individual OKRs
        for okr_idx, okr_title in enumerate([okr1, okr2, okr3]):
            if pd.isna(okr_title) or not str(okr_title).strip():
                continue
                
            obj = Objective(
                id=gen_uuid(),
                org_id=org_id,
                owner_id=u.id,
                parent_id=parent_id,
                title=str(okr_title),
                level="INDIVIDUAL",
                status="ACTIVE",
                cycle_id=quarterly_cycle.id,
                progress=friday_val, # current progress
                okr_status="ACTIVE",
                creation_approval_status="APPROVED",
                allows_cascade=False,
                plant_id=u.plant_id,
                department_id=u.department_id,
                **okr_period_fields(),
            )
            db.add(obj)
            db.flush()
            
            kr = KeyResult(
                id=gen_uuid(),
                objective_id=obj.id,
                title=f"Track progress of: {okr_title[:50]}",
                target_value=100.0,
                current_value=friday_val,
                unit="%",
                status="IN_PROGRESS" if friday_val < 100.0 else "COMPLETED",
                weight=1.0
            )
            db.add(kr)
            db.flush()
            
            # Historical progress updates
            # Q1 Update (backdated 60 days)
            db.add(ProgressUpdate(
                id=gen_uuid(),
                key_result_id=kr.id,
                submitted_by_id=u.id,
                previous_value=0.0,
                new_value=q1_val,
                notes="Q1 Accomplishments",
                status="APPROVED",
                created_at=now - pd.Timedelta(days=60),
                validated_at=now - pd.Timedelta(days=58)
            ))
            
            # Q2 Update (backdated 20 days)
            db.add(ProgressUpdate(
                id=gen_uuid(),
                key_result_id=kr.id,
                submitted_by_id=u.id,
                previous_value=q1_val,
                new_value=q2_val,
                notes="Q2 Progress updates",
                status="APPROVED",
                created_at=now - pd.Timedelta(days=20),
                validated_at=now - pd.Timedelta(days=19)
            ))
            
            # Weekly Friday check-in (today)
            db.add(ProgressUpdate(
                id=gen_uuid(),
                key_result_id=kr.id,
                submitted_by_id=u.id,
                previous_value=q2_val,
                new_value=friday_val,
                notes=f"Weekly check-in. Current status: {status_val}",
                status="APPROVED",
                auto_tracked=True,
                ai_coaching_notes=recom_val,
                created_at=now,
                validated_at=now
            ))
            
        # Seed a completed Performance Review to show AI Coaching Risk/Recommendation
        db.add(Review(
            id=gen_uuid(),
            org_id=org_id,
            cycle_id=quarterly_cycle.id, # map to cycle
            reviewee_id=u.id,
            reviewer_id=reviewer.id,
            status="COMPLETED",
            self_rating=int(friday_val / 20) if friday_val > 0 else 3,
            manager_rating=int(friday_val / 20) if friday_val > 0 else 3,
            final_rating=int(friday_val / 20) if friday_val > 0 else 3,
            ai_summary=recom_val,
            ai_risk_flags=f"{risk_val} Risk Profile",
            strengths=f"Strong ownership in role execution (Alignment: {alignment_score}%)",
            improvements="Focus on scaling task completion and aligning key results with weekly sprints.",
            completed_at=now
        ))

    db.commit()
    print("ALIGN360 simulation data seeded successfully!")

def ingest_cement_okr_data(db: Session) -> None:
    excel_path = resolve_cement_excel_path()
    print(f"\n[Cement OKR] Ingesting Data from {excel_path}...")

    df = pd.read_excel(excel_path, sheet_name="1200_Employee_OKR_Master")
    org_okr_title = str(df["Org OKR"].dropna().iloc[0])
    line_manager_ids = pick_line_manager_ids(df)
    progress_agg = compute_cement_progress_aggregates(df)
    dept_okr_by_name = (
        df.groupby("Department")["Department OKR"]
        .first()
        .to_dict()
    )

    org = Organization(
        id=gen_uuid(),
        name="Cement OKR Simulation",
        domain="cementokr.com",
        industry="Cement Manufacturing",
        size="LARGE",
        setup_completed=True,
    )
    db.add(org)
    db.flush()
    org_id = org.id
    root_node = ensure_organization_root(db, org_id, org.name)

    now = datetime.now(timezone.utc)
    cycle_start = (now - pd.Timedelta(days=90)).strftime("%Y-%m-%d")
    cycle_end = (now + pd.Timedelta(days=270)).strftime("%Y-%m-%d")
    freeze = (now + pd.Timedelta(days=240)).strftime("%Y-%m-%d")

    annual_cycle = Cycle(
        id=gen_uuid(),
        org_id=org_id,
        name="FY26 Annual",
        cycle_type="ANNUAL",
        start_date=cycle_start,
        end_date=cycle_end,
        freeze_date=freeze,
        status="ACTIVE",
        applies_to_levels=[0, 1, 2, 3, 4, 5],
    )
    quarterly_cycle = Cycle(
        id=gen_uuid(),
        org_id=org_id,
        name="Q2-2026",
        cycle_type="QUARTERLY",
        start_date=cycle_start,
        end_date=(now + pd.Timedelta(days=30)).strftime("%Y-%m-%d"),
        freeze_date=(now + pd.Timedelta(days=25)).strftime("%Y-%m-%d"),
        status="ACTIVE",
        applies_to_levels=[0, 1, 2, 3, 4, 5],
    )
    db.add(annual_cycle)
    db.add(quarterly_cycle)
    db.flush()

    desig_map = {
        "CEO": get_or_create_designation(db, org_id, "CEO", 0, "LEADERSHIP"),
        "CXO": get_or_create_designation(db, org_id, "Chief Officer", 1, "LEADERSHIP"),
        "Regional Head": get_or_create_designation(db, org_id, "Regional Head", 2, "LEADERSHIP"),
        "Plant Head": get_or_create_designation(db, org_id, "Plant Head", 2, "PLANT_LEADERSHIP"),
        "Dept Head": get_or_create_designation(db, org_id, "Head of Department", 3, "MANAGEMENT"),
        "Team Lead": get_or_create_designation(db, org_id, "Team Lead", 5, "MANAGEMENT"),
        "Manager": get_or_create_designation(db, org_id, "Manager", 4, "MANAGEMENT"),
        "Assistant Manager": get_or_create_designation(db, org_id, "Assistant Manager", 4, "MANAGEMENT"),
        "Senior Manager": get_or_create_designation(db, org_id, "Senior Manager", 3, "MANAGEMENT"),
        "Senior Engineer": get_or_create_designation(db, org_id, "Senior Engineer", 5, "OPERATIONAL"),
        "Engineer": get_or_create_designation(db, org_id, "Engineer", 6, "OPERATIONAL"),
        "Executive": get_or_create_designation(db, org_id, "Executive", 6, "OPERATIONAL"),
    }

    ceo_user = User(
        id=gen_uuid(),
        org_id=org_id,
        email="ceo@cementokr.com",
        password_hash=get_password_hash(PASSWORD),
        name="Vikram Mehta",
        employee_id="BC-ceo",
        system_role="CEO",
        is_active=True,
        org_node_id=root_node.id,
        designation_id=desig_map["CEO"].id,
    )
    db.add(ceo_user)
    db.flush()
    initialize_user_permissions(ceo_user, db, commit=False)
    root_node.head_user_id = ceo_user.id

    # Executive committee + corporate function nodes
    exec_heads: dict = {}
    vertical_nodes: dict = {}
    for role_key, name, email in CEMENT_EXEC_COMMITTEE:
        vert_node = create_child_node(
            parent_id=root_node.id,
            node_type="CORPORATE_FUNCTION",
            name=f"{role_key} Office",
            org_id=org_id,
            code=f"FUNC-{role_key}",
            db=db,
            node_metadata={"function_role": role_key},
        )
        db.add(vert_node)
        db.flush()
        vertical_nodes[role_key] = vert_node

        head = User(
            id=gen_uuid(),
            org_id=org_id,
            email=email,
            password_hash=get_password_hash(PASSWORD),
            name=name,
            employee_id=f"BC-{role_key.lower()}",
            system_role=role_key,
            is_active=True,
            org_node_id=vert_node.id,
            designation_id=desig_map["CXO"].id,
        )
        db.add(head)
        db.flush()
        initialize_user_permissions(head, db, commit=False)
        vert_node.head_user_id = head.id
        exec_heads[role_key] = head
        add_reporting(db, org_id, head.id, ceo_user.id, "DIRECT")

    cro = exec_heads["CRO"]
    coo = exec_heads["COO"]

    # Regions
    regions_dict: dict = {}
    region_heads: dict = {}
    for loc_name, (rname, rcode) in CEMENT_PLANT_REGION.items():
        if rcode in regions_dict:
            continue
        rn = create_child_node(
            parent_id=root_node.id,
            node_type="REGION",
            name=f"{rname} Region",
            org_id=org_id,
            code=f"REGION-{rcode}",
            db=db,
            node_metadata={"region_code": rcode},
        )
        db.add(rn)
        db.flush()

        rh_email = f"regional.{rcode.lower()}@cementokr.com"
        rh = User(
            id=gen_uuid(),
            org_id=org_id,
            email=rh_email,
            password_hash=get_password_hash(PASSWORD),
            name=f"{rname} Regional Head",
            employee_id=f"BC-reg-{rcode.lower()}",
            system_role="REGIONAL_HEAD",
            is_active=True,
            org_node_id=rn.id,
            designation_id=desig_map["Regional Head"].id,
        )
        db.add(rh)
        db.flush()
        initialize_user_permissions(rh, db, commit=False)
        rn.head_user_id = rh.id
        region_heads[rcode] = rh
        regions_dict[rcode] = {"node": rn, "name": rname}
        if rcode == "CORP":
            add_reporting(db, org_id, rh.id, ceo_user.id, "DIRECT")
        else:
            add_reporting(db, org_id, rh.id, cro.id, "DIRECT")

    # Plants under regions
    locations_dict: dict = {}
    plant_heads: dict = {}
    for lname in df["Location"].dropna().unique():
        rname, rcode = CEMENT_PLANT_REGION.get(lname, ("West", "WEST"))
        region_info = regions_dict[rcode]
        pcode = _slug(lname).upper().replace("-", "_")[:12]
        plant = Plant(
            id=gen_uuid(),
            org_id=org_id,
            name=lname,
            code=pcode,
            location=lname,
            is_active=True,
        )
        db.add(plant)
        db.flush()

        pn = create_child_node(
            parent_id=region_info["node"].id,
            node_type="PLANT",
            name=lname,
            org_id=org_id,
            code=f"PLANT-{pcode}",
            db=db,
            node_id=plant.id,
            node_metadata={"region_code": rcode},
        )
        db.add(pn)
        db.flush()

        ph_email = f"planthead.{_slug(lname)}@cementokr.com"
        ph = User(
            id=gen_uuid(),
            org_id=org_id,
            email=ph_email,
            password_hash=get_password_hash(PASSWORD),
            name=f"{lname} Head",
            employee_id=f"BC-ph-{_slug(lname)}",
            system_role="PLANT_HEAD",
            is_active=True,
            plant_id=plant.id,
            org_node_id=pn.id,
            designation_id=desig_map["Plant Head"].id,
        )
        db.add(ph)
        db.flush()
        initialize_user_permissions(ph, db, commit=False)
        pn.head_user_id = ph.id
        plant_heads[lname] = ph
        locations_dict[lname] = {
            "plant": plant,
            "node": pn,
            "region_node": region_info["node"],
            "region_code": rcode,
        }
        if rcode == "CORP":
            add_reporting(db, org_id, ph.id, ceo_user.id, "DIRECT")
        else:
            add_reporting(db, org_id, ph.id, region_heads[rcode].id, "DIRECT")
            add_reporting(db, org_id, ph.id, coo.id, "DOTTED_LINE")

    # Department heads per plant + department
    dept_heads: dict = {}
    dept_struct: dict = {}
    for lname in locations_dict:
        p_info = locations_dict[lname]
        for dept in df["Department"].dropna().unique():
            dept_code = dept.upper().replace(" ", "_")
            dept_obj = Department(
                id=gen_uuid(),
                org_id=org_id,
                plant_id=p_info["plant"].id,
                name=dept,
                dept_type=dept_code,
                is_active=True,
            )
            db.add(dept_obj)
            db.flush()

            func_role, func_area = DEPT_FUNCTION_MAP.get(dept, ("COO", "OPERATIONS"))
            vert = vertical_nodes.get(func_role)
            dept_node = create_child_node(
                parent_id=p_info["node"].id,
                node_type="DEPARTMENT",
                name=dept,
                org_id=org_id,
                code=f"DEPT-{p_info['plant'].code}-{dept_code}",
                db=db,
                node_id=dept_obj.id,
                node_metadata={"function_area": func_area, "dept_type": dept_code},
            )
            dept_node.functional_parent_id = vert.id if vert else None
            db.add(dept_node)
            db.flush()

            head_name = f"{dept} Head"
            hod_email = f"head.{_slug(dept)}.{_slug(lname)}@cementokr.com"
            hod = User(
                id=gen_uuid(),
                org_id=org_id,
                email=hod_email,
                password_hash=get_password_hash(PASSWORD),
                name=head_name,
                employee_id=f"BC-hod-{_slug(dept)}-{_slug(lname)}",
                system_role="DEPT_HEAD",
                is_active=True,
                plant_id=p_info["plant"].id,
                department_id=dept_obj.id,
                org_node_id=dept_node.id,
                designation_id=desig_map["Dept Head"].id,
            )
            db.add(hod)
            db.flush()
            initialize_user_permissions(hod, db, commit=False)
            dept_node.head_user_id = hod.id

            func_head = exec_heads.get(func_role, ceo_user)
            if lname == "Mumbai HQ":
                add_reporting(db, org_id, hod.id, func_head.id, "DIRECT")
                add_reporting(db, org_id, hod.id, ceo_user.id, "DOTTED_LINE")
            else:
                add_reporting(db, org_id, hod.id, plant_heads[lname].id, "DIRECT")
                add_reporting(db, org_id, hod.id, func_head.id, "DOTTED_LINE")

            dept_heads[(lname, dept)] = hod
            dept_struct[(lname, dept)] = {
                "dept": dept_obj,
                "node": dept_node,
                "head": hod,
                "function_area": func_area,
                "func_role": func_role,
            }

    # Teams per plant+department (for constellation TEAM orbit + TEAM OKRs)
    emp_team_key, team_groups = build_team_groups(df)
    teams_dict: dict = {}
    for key, member_ids in team_groups.items():
        loc, dept, team_idx = key
        struct = dept_struct[(loc, dept)]
        p_info = locations_dict[loc]
        tname = f"{dept} Team {team_idx + 1}"
        team = Team(
            id=gen_uuid(),
            org_id=org_id,
            department_id=struct["dept"].id,
            name=tname,
            is_active=True,
        )
        db.add(team)
        db.flush()
        team_node = create_child_node(
            parent_id=struct["node"].id,
            node_type="TEAM",
            name=tname,
            org_id=org_id,
            code=f"TEAM-{p_info['plant'].code}-{dept.upper().replace(' ', '_')}-T{team_idx + 1}",
            db=db,
            node_id=team.id,
        )
        db.add(team_node)
        db.flush()
        teams_dict[key] = {
            "team": team,
            "node": team_node,
            "members": member_ids,
            "loc": loc,
            "dept": dept,
            "team_idx": team_idx,
        }

    # Seed 1200 employees — pass 1: create users
    employee_dict: dict = {}
    employee_rows: list = []
    print("Seeding 1200 employees for Cement OKR...")
    for _, row in df.iterrows():
        emp_id = int(row["Employee ID"])
        name = row["Employee Name"]
        loc = row["Location"]
        dept = row["Department"]
        desig = row["Designation"]

        struct = dept_struct.get((loc, dept))
        if not struct:
            continue

        des_obj = desig_map.get(desig, desig_map["Engineer"])
        is_management = desig in MANAGEMENT_DESIGNATIONS
        is_line_manager = line_manager_ids.get((loc, dept)) == emp_id
        system_role = "MANAGER" if is_management or is_line_manager else "EMPLOYEE"
        team_key = emp_team_key.get(emp_id)
        team_info = teams_dict.get(team_key)

        u = User(
            id=gen_uuid(),
            org_id=org_id,
            email=f"employee.{emp_id}@cementokr.com",
            password_hash=get_password_hash(PASSWORD),
            name=name,
            employee_id=f"BC-{emp_id}",
            system_role=system_role,
            is_active=True,
            plant_id=struct["dept"].plant_id,
            department_id=struct["dept"].id,
            team_id=team_info["team"].id if team_info else None,
            org_node_id=team_info["node"].id if team_info else struct["node"].id,
            designation_id=des_obj.id,
        )
        db.add(u)
        db.flush()
        initialize_user_permissions(u, db, commit=False)
        if team_info:
            db.add(TeamMember(
                org_id=org_id,
                team_id=team_info["team"].id,
                user_id=u.id,
                is_active=True,
            ))
        employee_dict[emp_id] = u
        employee_rows.append((emp_id, loc, dept, desig, is_management, is_line_manager))

    # Assign team leads before reporting + OKRs
    for key, tinfo in teams_dict.items():
        loc, dept = tinfo["loc"], tinfo["dept"]
        member_ids = tinfo["members"]
        lead_id = None
        line_mgr_id = line_manager_ids.get((loc, dept))
        if line_mgr_id in member_ids:
            lead_id = line_mgr_id
        if not lead_id:
            for mid in member_ids:
                row = df.loc[df["Employee ID"] == mid].iloc[0]
                if row["Designation"] in MANAGEMENT_DESIGNATIONS:
                    lead_id = mid
                    break
        if not lead_id:
            lead_id = member_ids[0]

        lead = employee_dict[lead_id]
        lead.system_role = "TEAM_LEAD"
        lead.designation_id = desig_map["Team Lead"].id
        tinfo["team"].lead_id = lead.id
        tinfo["node"].head_user_id = lead.id
        tinfo["lead"] = lead
        for mid in member_ids:
            tm = (
                db.query(TeamMember)
                .filter(TeamMember.team_id == tinfo["team"].id, TeamMember.user_id == employee_dict[mid].id)
                .first()
            )
            if tm:
                tm.is_team_lead = mid == lead_id
                tm.role_in_team = "LEAD" if mid == lead_id else "MEMBER"

    # Pass 2: reporting (team lead / manager, dept head, executive committee)
    for emp_id, loc, dept, desig, is_management, is_line_manager in employee_rows:
        u = employee_dict[emp_id]
        struct = dept_struct[(loc, dept)]
        hod = struct["head"]
        func_head = exec_heads.get(struct["func_role"], ceo_user)
        team_key = emp_team_key.get(emp_id)
        team_info = teams_dict.get(team_key)
        team_lead = team_info.get("lead") if team_info else None
        line_mgr_id = line_manager_ids.get((loc, dept))
        line_mgr = employee_dict.get(line_mgr_id) if line_mgr_id else None

        if u.system_role == "TEAM_LEAD":
            direct_mgr = line_mgr if line_mgr and line_mgr.id != u.id else hod
            add_reporting(db, org_id, u.id, direct_mgr.id, "DIRECT")
            if direct_mgr.id != hod.id:
                add_reporting(db, org_id, u.id, hod.id, "DOTTED_LINE")
        elif is_management:
            add_reporting(db, org_id, u.id, hod.id, "DIRECT")
        elif team_lead and team_lead.id != u.id:
            add_reporting(db, org_id, u.id, team_lead.id, "DIRECT")
            add_reporting(db, org_id, u.id, hod.id, "DOTTED_LINE")
        elif line_mgr and line_mgr.id != u.id:
            add_reporting(db, org_id, u.id, line_mgr.id, "DIRECT")
            add_reporting(db, org_id, u.id, hod.id, "DOTTED_LINE")
        else:
            add_reporting(db, org_id, u.id, hod.id, "DIRECT")

        add_reporting(db, org_id, u.id, func_head.id, "DOTTED_LINE")

    db.flush()
    print("Employee user accounts seeded.")

    # OKR cascade: Org → Region → Plant → Department → Team → Individual
    org_okr = Objective(
        id=gen_uuid(),
        org_id=org_id,
        owner_id=ceo_user.id,
        title=org_okr_title,
        level="ORGANIZATION",
        status="ACTIVE",
        cycle_id=annual_cycle.id,
        progress=0.0,
        okr_status="ACTIVE",
        creation_approval_status="APPROVED",
        allows_cascade=True,
        **okr_period_fields(),
    )
    db.add(org_okr)
    db.flush()
    seed_krs_with_quarterly_progress(
        db, org_okr, ceo_user.id, now, ORG_KR_SPECS, progress_agg["org"],
        notes_prefix="Organization",
    )

    region_okrs: dict = {}
    for rcode, info in regions_dict.items():
        rh = region_heads[rcode]
        rob = Objective(
            id=gen_uuid(),
            org_id=org_id,
            owner_id=rh.id,
            parent_id=org_okr.id,
            title=f"{info['name']} Region — {org_okr_title}",
            level="REGION",
            status="ACTIVE",
            cycle_id=annual_cycle.id,
            progress=0.0,
            okr_status="ACTIVE",
            creation_approval_status="APPROVED",
            allows_cascade=True,
            region_id=info["node"].id,
            **okr_period_fields(),
        )
        db.add(rob)
        db.flush()
        region_okrs[rcode] = rob
        seed_krs_with_quarterly_progress(
            db, rob, rh.id, now, REGION_KR_SPECS,
            progress_agg["region"].get(rcode, progress_agg["org"]),
            notes_prefix=f"{info['name']} Region",
        )

    plant_okrs: dict = {}
    for lname, p_info in locations_dict.items():
        ph = plant_heads[lname]
        rcode = p_info["region_code"]
        parent = region_okrs.get(rcode, org_okr)
        pob = Objective(
            id=gen_uuid(),
            org_id=org_id,
            owner_id=ph.id,
            parent_id=parent.id,
            title=f"{lname} — operational excellence & safety targets",
            level="PLANT",
            status="ACTIVE",
            cycle_id=annual_cycle.id,
            progress=0.0,
            okr_status="ACTIVE",
            creation_approval_status="APPROVED",
            allows_cascade=True,
            region_id=p_info["region_node"].id,
            plant_id=p_info["plant"].id,
            **okr_period_fields(),
        )
        db.add(pob)
        db.flush()
        plant_okrs[lname] = pob
        seed_krs_with_quarterly_progress(
            db, pob, ph.id, now, PLANT_KR_SPECS,
            progress_agg["plant"].get(lname, progress_agg["org"]),
            notes_prefix=lname,
        )

    dept_okrs_dict: dict = {}
    for (lname, dept), struct in dept_struct.items():
        do_title = dept_okr_by_name.get(dept, f"Achieve {dept} annual KPIs")
        hod = struct["head"]
        plant_parent = plant_okrs.get(lname, org_okr)
        dob = Objective(
            id=gen_uuid(),
            org_id=org_id,
            owner_id=hod.id,
            parent_id=plant_parent.id,
            title=do_title,
            level="DEPARTMENT",
            status="ACTIVE",
            cycle_id=annual_cycle.id,
            progress=0.0,
            okr_status="ACTIVE",
            creation_approval_status="APPROVED",
            allows_cascade=True,
            region_id=locations_dict[lname]["region_node"].id,
            plant_id=struct["dept"].plant_id,
            department_id=struct["dept"].id,
            function_area=struct["function_area"],
            **okr_period_fields(),
        )
        db.add(dob)
        db.flush()
        dept_okrs_dict[(lname, dept)] = dob
        seed_krs_with_quarterly_progress(
            db, dob, hod.id, now, DEPT_KR_SPECS,
            progress_agg["dept"].get((lname, dept), progress_agg["org"]),
            notes_prefix=f"{dept} @ {lname}",
        )

    team_okrs_dict: dict = {}
    for key, tinfo in teams_dict.items():
        loc, dept, team_idx = key
        lead = tinfo["lead"]
        dept_parent = dept_okrs_dict[(loc, dept)]
        tname = f"{dept} Team {team_idx + 1}"
        tob = Objective(
            id=gen_uuid(),
            org_id=org_id,
            owner_id=lead.id,
            parent_id=dept_parent.id,
            title=f"{tname} — execution & delivery targets",
            level="TEAM",
            status="ACTIVE",
            cycle_id=quarterly_cycle.id,
            progress=0.0,
            okr_status="ACTIVE",
            creation_approval_status="APPROVED",
            allows_cascade=True,
            region_id=locations_dict[loc]["region_node"].id,
            plant_id=locations_dict[loc]["plant"].id,
            department_id=dept_struct[(loc, dept)]["dept"].id,
            team_id=tinfo["team"].id,
            function_area=dept_struct[(loc, dept)]["function_area"],
            **okr_period_fields(),
        )
        db.add(tob)
        db.flush()
        team_okrs_dict[key] = tob
        seed_krs_with_quarterly_progress(
            db,
            tob,
            lead.id,
            now,
            TEAM_KR_SPECS,
            team_progress_from_df(df, tinfo["members"]),
            notes_prefix=f"{tname} @ {loc}",
        )

    print(
        f"OKR hierarchy seeded: 1 org, {len(region_okrs)} regional, "
        f"{len(plant_okrs)} plant, {len(dept_okrs_dict)} department, "
        f"{len(team_okrs_dict)} team"
    )

    print("Seeding individual OKRs and progress logs...")
    for _, row in df.iterrows():
        emp_id = int(row["Employee ID"])
        okr_title = row["Individual OKR"]
        u = employee_dict.get(emp_id)
        if not u or pd.isna(okr_title) or not str(okr_title).strip():
            continue

        loc = row["Location"]
        dept = row["Department"]
        team_key = emp_team_key.get(emp_id)
        parent_obj = team_okrs_dict.get(team_key) if team_key else dept_okrs_dict.get((loc, dept))
        parent_id = parent_obj.id if parent_obj else None
        team_info = teams_dict.get(team_key) if team_key else None

        q1_val = float(row["Q1 Achievement %"])
        q2_val = float(row["Q2 Achievement %"])
        friday_val = float(row["Achievement by Friday %"])
        status_val = row["Status"]
        weekly_target = row["This Week Planned Target"]

        obj = Objective(
            id=gen_uuid(),
            org_id=org_id,
            owner_id=u.id,
            parent_id=parent_id,
            title=str(okr_title),
            level="INDIVIDUAL",
            status="ACTIVE",
            cycle_id=quarterly_cycle.id,
            progress=friday_val,
            okr_status="ACTIVE",
            creation_approval_status="APPROVED",
            allows_cascade=False,
            region_id=locations_dict[loc]["region_node"].id if loc in locations_dict else None,
            plant_id=u.plant_id,
            department_id=u.department_id,
            team_id=team_info["team"].id if team_info else u.team_id,
            **okr_period_fields(),
        )
        db.add(obj)
        db.flush()

        seed_krs_with_quarterly_progress(
            db,
            obj,
            u.id,
            now,
            [(f"Track progress: {str(okr_title)[:50]}", 100.0, "%", 1.0)],
            _progress_triplet(q1_val, q2_val, friday_val),
            notes_prefix=f"{weekly_target} ({status_val})",
        )

        reviewer = (
            db.query(User)
            .join(ReportingRelationship, ReportingRelationship.manager_id == User.id)
            .filter(
                ReportingRelationship.employee_id == u.id,
                ReportingRelationship.relationship_type == "DIRECT",
                ReportingRelationship.is_active == True,
            )
            .first()
        ) or ceo_user

        db.add(Review(
            id=gen_uuid(),
            org_id=org_id,
            cycle_id=quarterly_cycle.id,
            reviewee_id=u.id,
            reviewer_id=reviewer.id,
            status="COMPLETED",
            self_rating=int(friday_val / 20) if friday_val > 0 else 3,
            manager_rating=int(friday_val / 20) if friday_val > 0 else 3,
            final_rating=int(friday_val / 20) if friday_val > 0 else 3,
            ai_summary=f"Weekly milestones successfully planned and executed: '{weekly_target}'",
            ai_risk_flags=f"{status_val} Progress Status",
            strengths=f"Execution alignment scored at {row['Alignment Score']}%",
            improvements="Review alignment with functional HOD quarterly goals.",
            completed_at=now,
        ))

    cascade = OKRCascadeService(db)
    for level in ("INDIVIDUAL", "TEAM", "DEPARTMENT", "PLANT", "REGION", "ORGANIZATION"):
        for obj in db.query(Objective).filter(Objective.org_id == org_id, Objective.level == level).all():
            cascade.refresh_objective_progress_for_session(obj.id)

    kr_count = (
        db.query(KeyResult)
        .join(Objective, KeyResult.objective_id == Objective.id)
        .filter(Objective.org_id == org_id)
        .count()
    )
    db.commit()
    print(f"Key results seeded: {kr_count} (with Q1/Q2/current progress updates)")
    print("Cement OKR simulation data seeded successfully!")

def main():
    db = SessionLocal()
    try:
        # 1. Clear previous simulation orgs if exist
        clear_existing_simulation_orgs(db, ["align360.com", "cementokr.com"])
        
        # 2. Seed Align360
        ingest_align360_data(db)
        
        # 3. Seed Cement OKR
        ingest_cement_okr_data(db)
        
        print("\nALL SIMULATION DATA INGESTED SUCCESSFULLY!")
    except Exception as e:
        db.rollback()
        print(f"Error during ingestion: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    main()
