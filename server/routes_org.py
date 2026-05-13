from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from server.database import get_db
from server.models import Organization, Plant, Department, Shift, Designation, Team, User, TeamMember, OrgNode
from server.team_membership_service import enroll_team_member
from server.schemas import PlantCreate, DepartmentCreate, ShiftCreate, DesignationCreate, TeamCreate
from server.services.org_tree_service import sync_org_node_for

router = APIRouter(prefix="/api/org", tags=["organization"])

DEFAULT_DEPARTMENTS = [
    {"name": "Production", "dept_type": "PRODUCTION"},
    {"name": "Quality", "dept_type": "QUALITY"},
    {"name": "Maintenance", "dept_type": "MAINTENANCE"},
    {"name": "Warehouse", "dept_type": "WAREHOUSE"},
    {"name": "Safety", "dept_type": "SAFETY"},
    {"name": "HR", "dept_type": "HR"},
    {"name": "Planning", "dept_type": "PLANNING"},
    {"name": "Finance", "dept_type": "FINANCE"},
    {"name": "Supply Chain", "dept_type": "SUPPLY_CHAIN"},
]

DEFAULT_DESIGNATIONS = [
    {"name": "CEO", "level": 1, "category": "LEADERSHIP"},
    {"name": "COO", "level": 1, "category": "LEADERSHIP"},
    {"name": "CFO", "level": 1, "category": "LEADERSHIP"},
    {"name": "CHRO", "level": 1, "category": "LEADERSHIP"},
    {"name": "VP Manufacturing", "level": 2, "category": "LEADERSHIP"},
    {"name": "VP Supply Chain", "level": 2, "category": "LEADERSHIP"},
    {"name": "Plant Head", "level": 3, "category": "PLANT_LEADERSHIP"},
    {"name": "Factory Director", "level": 3, "category": "PLANT_LEADERSHIP"},
    {"name": "Operations Head", "level": 3, "category": "PLANT_LEADERSHIP"},
    {"name": "Department Head", "level": 4, "category": "MANAGEMENT"},
    {"name": "Production Head", "level": 4, "category": "MANAGEMENT"},
    {"name": "Quality Head", "level": 4, "category": "MANAGEMENT"},
    {"name": "Maintenance Head", "level": 4, "category": "MANAGEMENT"},
    {"name": "Safety Head", "level": 4, "category": "MANAGEMENT"},
    {"name": "HR Head", "level": 4, "category": "MANAGEMENT"},
    {"name": "Warehouse Head", "level": 4, "category": "MANAGEMENT"},
    {"name": "Production Manager", "level": 5, "category": "MANAGEMENT"},
    {"name": "Shift Incharge", "level": 6, "category": "OPERATIONAL"},
    {"name": "Line Supervisor", "level": 7, "category": "OPERATIONAL"},
    {"name": "Team Lead", "level": 8, "category": "OPERATIONAL"},
    {"name": "Senior Engineer", "level": 9, "category": "OPERATIONAL"},
    {"name": "Engineer", "level": 9, "category": "OPERATIONAL"},
    {"name": "Technician", "level": 10, "category": "OPERATIONAL"},
    {"name": "Operator", "level": 10, "category": "OPERATIONAL"},
    {"name": "Inspector", "level": 10, "category": "OPERATIONAL"},
]


# ===== ORG =====
@router.get("")
def get_org(db: Session = Depends(get_db), org_id: str = ""):
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(404, "Organization not found")
    return {"id": org.id, "name": org.name, "domain": org.domain, "industry": org.industry,
            "size": org.size, "setup_completed": org.setup_completed}


@router.put("")
def update_org(name: str = None, domain: str = None, db: Session = Depends(get_db), org_id: str = ""):
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(404)
    if name: org.name = name
    if domain: org.domain = domain
    db.commit()
    return {"status": "updated"}


@router.post("/complete-setup")
def complete_setup(db: Session = Depends(get_db), org_id: str = ""):
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(404)
    org.setup_completed = True
    db.commit()
    return {"status": "ok", "setup_completed": True}


# ===== PLANTS =====
@router.post("/plants")
def create_plant(req: PlantCreate, db: Session = Depends(get_db), org_id: str = ""):
    plant = Plant(org_id=org_id, name=req.name, location=req.location, code=req.code)
    db.add(plant)
    db.flush()
    
    # Sync OrgNode: PLANT shares id with plants.id; parent is ORGANIZATION root (= org_id)
    try:
        sync_org_node_for(
            entity_type="PLANT",
            entity_id=plant.id,
            org_id=org_id,
            name=req.name,
            parent_id=org_id,
            code=req.code,
            db=db,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Failed to create org node: {str(e)}")
    
    db.commit()
    db.refresh(plant)
    return {"id": plant.id, "name": plant.name, "location": plant.location, "code": plant.code}


@router.get("/plants")
def list_plants(db: Session = Depends(get_db), org_id: str = ""):
    plants = db.query(Plant).filter(Plant.org_id == org_id, Plant.is_active == True).all()
    result = []
    for p in plants:
        depts = db.query(Department).filter(Department.plant_id == p.id, Department.is_active == True).all()
        shifts = db.query(Shift).filter(Shift.plant_id == p.id, Shift.is_active == True).all()
        emp_count = db.query(User).filter(User.plant_id == p.id, User.is_active == True).count()
        result.append({
            "id": p.id, "name": p.name, "location": p.location, "code": p.code,
            "employee_count": emp_count,
            "departments": [{"id": d.id, "name": d.name, "dept_type": d.dept_type} for d in depts],
            "shifts": [{"id": s.id, "name": s.name, "start_time": s.start_time, "end_time": s.end_time} for s in shifts],
        })
    return result


@router.put("/plants/{plant_id}")
def update_plant(plant_id: str, req: PlantCreate, db: Session = Depends(get_db)):
    p = db.query(Plant).filter(Plant.id == plant_id).first()
    if not p: raise HTTPException(404)
    
    old_name = p.name
    p.name = req.name
    if req.location: p.location = req.location
    if req.code: p.code = req.code
    
    # Sync OrgNode if name changed (same id as plant)
    if old_name != req.name:
        org_node = db.query(OrgNode).filter(
            OrgNode.node_type == "PLANT",
            OrgNode.org_id == p.org_id,
            OrgNode.id == plant_id,
        ).first()
        if org_node:
            org_node.name = req.name
    
    db.commit()
    return {"status": "updated"}


# ===== DEPARTMENTS =====
@router.post("/departments")
def create_department(req: DepartmentCreate, db: Session = Depends(get_db), org_id: str = ""):
    dept = Department(org_id=org_id, plant_id=req.plant_id, name=req.name, dept_type=req.dept_type)
    db.add(dept)
    db.flush()
    
    plant_row = db.query(Plant).filter(Plant.id == req.plant_id).first()
    plant_node = (
        db.query(OrgNode).filter(
            OrgNode.node_type == "PLANT",
            OrgNode.org_id == org_id,
            OrgNode.id == req.plant_id,
        ).first()
        if plant_row
        else None
    )
    
    if not plant_node:
        db.rollback()
        raise HTTPException(500, "Plant has no OrgNode; run migrations or sync plant first")

    try:
        sync_org_node_for(
            entity_type="DEPARTMENT",
            entity_id=dept.id,
            org_id=org_id,
            name=req.name,
            parent_id=plant_node.id,
            code=None,
            db=db,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Failed to create org node: {str(e)}")

    db.commit()
    db.refresh(dept)
    return {"id": dept.id, "name": dept.name, "dept_type": dept.dept_type}


@router.get("/departments")
def list_departments(db: Session = Depends(get_db), org_id: str = "", plant_id: str = ""):
    q = db.query(Department).filter(Department.org_id == org_id, Department.is_active == True)
    if plant_id:
        q = q.filter(Department.plant_id == plant_id)
    depts = q.all()
    return [{"id": d.id, "plant_id": d.plant_id, "name": d.name, "dept_type": d.dept_type} for d in depts]


@router.post("/departments/seed-defaults")
def seed_default_departments(plant_id: str, db: Session = Depends(get_db), org_id: str = ""):
    created = []
    for d in DEFAULT_DEPARTMENTS:
        existing = db.query(Department).filter(Department.plant_id == plant_id, Department.name == d["name"]).first()
        if not existing:
            dept = Department(org_id=org_id, plant_id=plant_id, name=d["name"], dept_type=d["dept_type"])
            db.add(dept)
            created.append(d["name"])
    db.commit()
    return {"created": created}


# ===== TEAMS =====
@router.post("/teams")
def create_team(req: TeamCreate, db: Session = Depends(get_db), org_id: str = ""):
    dept = db.query(Department).filter(
        Department.id == req.department_id,
        Department.org_id == org_id,
    ).first()
    if not dept:
        raise HTTPException(404, "Department not found")

    team = Team(org_id=org_id, department_id=req.department_id, name=req.name, lead_id=req.lead_id)
    db.add(team)
    db.flush()

    dept_node = (
        db.query(OrgNode).filter(
            OrgNode.node_type == "DEPARTMENT",
            OrgNode.org_id == org_id,
            OrgNode.id == req.department_id,
        ).first()
    )
    
    if not dept_node:
        db.rollback()
        raise HTTPException(500, "Department has no OrgNode; run migrations or sync department first")

    try:
        sync_org_node_for(
            entity_type="TEAM",
            entity_id=team.id,
            org_id=org_id,
            name=req.name,
            parent_id=dept_node.id,
            code=None,
            head_user_id=req.lead_id,
            db=db,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Failed to create org node: {str(e)}")

    ordered: list[str] = []
    seen: set[str] = set()
    for uid in (req.member_user_ids or []):
        if uid and uid not in seen:
            seen.add(uid)
            ordered.append(uid)
    if req.lead_id and req.lead_id not in seen:
        ordered.insert(0, req.lead_id)

    for uid in ordered:
        try:
            enroll_team_member(
                db,
                org_id,
                team,
                uid,
                is_team_lead=bool(req.lead_id and uid == req.lead_id),
            )
        except ValueError as e:
            db.rollback()
            msg = str(e)
            if msg == "already_active_member":
                raise HTTPException(409, "User is already on this team")
            raise HTTPException(400, msg)

    if req.lead_id:
        team.lead_id = req.lead_id
        db.flush()

    db.commit()
    db.refresh(team)
    return {"id": team.id, "name": team.name, "department_id": team.department_id, "lead_id": team.lead_id}


@router.get("/teams")
def list_teams(db: Session = Depends(get_db), org_id: str = "", department_id: str = ""):
    q = db.query(Team).filter(Team.org_id == org_id, Team.is_active == True)
    if department_id:
        q = q.filter(Team.department_id == department_id)
    teams = q.all()
    result = []
    for t in teams:
        lead = db.query(User).filter(User.id == t.lead_id).first() if t.lead_id else None
        roster_count = db.query(TeamMember).filter(
            TeamMember.team_id == t.id,
            TeamMember.is_active == True,
        ).count()
        legacy_count = db.query(User).filter(User.team_id == t.id, User.is_active == True).count()
        member_count = max(roster_count, legacy_count)
        result.append({
            "id": t.id, "name": t.name, "department_id": t.department_id,
            "lead_id": t.lead_id, "lead_name": lead.name if lead else None,
            "member_count": member_count,
        })
    return result


# ===== SHIFTS =====
@router.post("/shifts")
def create_shift(req: ShiftCreate, db: Session = Depends(get_db), org_id: str = ""):
    shift = Shift(org_id=org_id, plant_id=req.plant_id, name=req.name,
                  start_time=req.start_time, end_time=req.end_time, supervisor_id=req.supervisor_id)
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return {"id": shift.id, "name": shift.name}


@router.get("/shifts")
def list_shifts(db: Session = Depends(get_db), org_id: str = "", plant_id: str = ""):
    q = db.query(Shift).filter(Shift.org_id == org_id, Shift.is_active == True)
    if plant_id:
        q = q.filter(Shift.plant_id == plant_id)
    shifts = q.all()
    return [{"id": s.id, "plant_id": s.plant_id, "name": s.name,
             "start_time": s.start_time, "end_time": s.end_time, "supervisor_id": s.supervisor_id} for s in shifts]


# ===== DESIGNATIONS =====
@router.get("/designations")
def list_designations(db: Session = Depends(get_db), org_id: str = ""):
    desigs = db.query(Designation).filter(Designation.org_id == org_id, Designation.is_active == True).order_by(Designation.level).all()
    return [{"id": d.id, "name": d.name, "level": d.level, "category": d.category} for d in desigs]


@router.post("/designations")
def create_designation(req: DesignationCreate, db: Session = Depends(get_db), org_id: str = ""):
    d = Designation(org_id=org_id, name=req.name, level=req.level, category=req.category)
    db.add(d)
    db.commit()
    db.refresh(d)
    return {"id": d.id, "name": d.name, "level": d.level, "category": d.category}


@router.post("/designations/seed-defaults")
def seed_default_designations(db: Session = Depends(get_db), org_id: str = ""):
    created = []
    for d in DEFAULT_DESIGNATIONS:
        existing = db.query(Designation).filter(Designation.org_id == org_id, Designation.name == d["name"]).first()
        if not existing:
            des = Designation(org_id=org_id, name=d["name"], level=d["level"], category=d["category"])
            db.add(des)
            created.append(d["name"])
    db.commit()
    return {"created": created}


@router.put("/designations/{desig_id}")
def update_designation(desig_id: str, req: DesignationCreate, db: Session = Depends(get_db)):
    d = db.query(Designation).filter(Designation.id == desig_id).first()
    if not d: raise HTTPException(404)
    d.name = req.name
    d.level = req.level
    if req.category: d.category = req.category
    db.commit()
    return {"status": "updated"}
