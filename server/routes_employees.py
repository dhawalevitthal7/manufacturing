import random
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from server.database import get_db
from sqlalchemy import or_
from server.models import User, Plant, Department, Team, Designation, Shift, ReportingRelationship, TeamMember
from server.schemas import EmployeeCreate, EmployeeUpdate, EmployeeBulkCreate
from server.auth import get_password_hash, require_super_admin_or_hr_head
from server.roles import SystemRole, normalize_role
from server.services.audit_service import (
    audit_super_admin_action,
    record_audit_event,
    STRUCTURE_CREATE,
    STRUCTURE_UPDATE,
    ROLE_ASSIGN,
)

router = APIRouter(prefix="/api/employees", tags=["employees"])
AVATAR_COLORS = ["#6366f1","#8b5cf6","#ec4899","#f43f5e","#f97316","#eab308","#22c55e","#14b8a6","#0ea5e9","#3b82f6"]


@router.get("")
def list_employees(db: Session = Depends(get_db), org_id: str = "", search: str = "",
                   plant_id: str = "", department_id: str = "", team_id: str = "",
                   system_role: str = "", is_active: str = "true"):
    """List employees with filters. Scoped to org."""
    q = db.query(User).filter(User.org_id == org_id)
    if is_active.lower() == "true":
        q = q.filter(User.is_active == True)
    if search:
        q = q.filter((User.name.ilike(f"%{search}%")) | (User.email.ilike(f"%{search}%")) | (User.employee_id.ilike(f"%{search}%")))
    # Department implies plant; prefer department filter alone so users with valid
    # department_id but missing plant_id still appear (common data-entry gap).
    if department_id:
        q = q.filter(User.department_id == department_id)
    elif plant_id:
        q = q.filter(User.plant_id == plant_id)
    if team_id:
        # Primary assignment OR membership via team_members (roster may not set User.team_id)
        member_ids = [
            row[0]
            for row in db.query(TeamMember.user_id)
            .filter(TeamMember.team_id == team_id, TeamMember.is_active == True)
            .all()
        ]
        if member_ids:
            q = q.filter(or_(User.team_id == team_id, User.id.in_(member_ids)))
        else:
            q = q.filter(User.team_id == team_id)
    if system_role:
        q = q.filter(User.system_role == system_role)
    users = q.order_by(User.created_at.desc()).all()
    return [_emp_dict(u, db) for u in users]


@router.post("")
def create_employee(
    req: EmployeeCreate,
    db: Session = Depends(get_db),
    org_id: str = "",
    _auth: dict = Depends(require_super_admin_or_hr_head),
):
    """Directly create an employee in DB. No invitation flow.
    Employee can immediately login with the provided email/password."""
    actor_sub = str(_auth.get("sub") or "")
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(400, "Email already exists")

    user = User(
        org_id=org_id, email=req.email,
        password_hash=get_password_hash(req.password),
        name=req.name, employee_id=req.employee_id,
        system_role=req.system_role,
        plant_id=req.plant_id, department_id=req.department_id,
        team_id=req.team_id, designation_id=req.designation_id,
        shift_id=req.shift_id,
        avatar_color=random.choice(AVATAR_COLORS),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    audit_super_admin_action(
        org_id=org_id,
        actor_user_id=actor_sub,
        action=STRUCTURE_CREATE,
        entity_type="USER",
        entity_id=user.id,
        details={"name": req.name, "email": req.email, "system_role": req.system_role},
    )
    return _emp_dict(user, db)


@router.post("/bulk")
def bulk_create_employees(
    req: EmployeeBulkCreate,
    db: Session = Depends(get_db),
    org_id: str = "",
    _auth: dict = Depends(require_super_admin_or_hr_head),
):
    """Bulk create employees. Skips duplicates."""
    actor_sub = str(_auth.get("sub") or "")
    created, skipped = [], []
    for emp in req.employees:
        existing = db.query(User).filter(User.email == emp.email).first()
        if existing:
            skipped.append(emp.email)
            continue
        u = User(
            org_id=org_id, email=emp.email,
            password_hash=get_password_hash(emp.password),
            name=emp.name, employee_id=emp.employee_id,
            system_role=emp.system_role,
            plant_id=emp.plant_id, department_id=emp.department_id,
            team_id=emp.team_id, designation_id=emp.designation_id,
            shift_id=emp.shift_id,
            avatar_color=random.choice(AVATAR_COLORS),
        )
        db.add(u)
        created.append(emp.email)
    db.commit()
    audit_super_admin_action(
        org_id=org_id,
        actor_user_id=actor_sub,
        action=STRUCTURE_CREATE,
        entity_type="USER",
        entity_id=None,
        details={"bulk_count": len(created), "skipped": len(skipped)},
    )
    return {"created": len(created), "skipped": len(skipped), "skipped_emails": skipped}


@router.get("/{uid}")
def get_employee(uid: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(404, "Employee not found")
    result = _emp_dict(user, db)
    # Include reporting relationships
    rels = db.query(ReportingRelationship).filter(
        ReportingRelationship.employee_id == uid, ReportingRelationship.is_active == True
    ).all()
    result["reporting_to"] = [
        {"manager_id": r.manager_id, "type": r.relationship_type,
         "manager_name": _get_name(db, r.manager_id)} for r in rels
    ]
    # Direct reports
    direct = db.query(ReportingRelationship).filter(
        ReportingRelationship.manager_id == uid, ReportingRelationship.is_active == True,
        ReportingRelationship.relationship_type == "DIRECT"
    ).all()
    result["direct_reports"] = [
        {"employee_id": r.employee_id, "name": _get_name(db, r.employee_id)} for r in direct
    ]
    return result


@router.put("/{uid}")
def update_employee(
    uid: str,
    req: EmployeeUpdate,
    db: Session = Depends(get_db),
    org_id: str = "",
    _auth: dict = Depends(require_super_admin_or_hr_head),
):
    actor_sub = str(_auth.get("sub") or "")
    actor_role = normalize_role(str(_auth.get("system_role") or _auth.get("role") or ""))

    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(404, "Employee not found")
    if user.org_id != org_id:
        raise HTTPException(404, "Employee not found")

    updates = req.model_dump(exclude_unset=True)
    if "system_role" in updates:
        new_norm = normalize_role(str(updates["system_role"])).value
        old_norm = normalize_role(str(user.system_role)).value
        if new_norm != old_norm and actor_role != SystemRole.SUPER_ADMIN:
            raise HTTPException(
                403,
                "Only SUPER_ADMIN may change a user's system_role; HR_HEAD may update other profile fields.",
            )

    original_role_norm = normalize_role(str(user.system_role)).value

    changes = {}
    for field, value in updates.items():
        old = getattr(user, field)
        setattr(user, field, value)
        changes[field] = {"old": old, "new": value}

    db.commit()
    db.refresh(user)

    new_role_norm = normalize_role(str(user.system_role)).value
    if new_role_norm != original_role_norm:
        audit_super_admin_action(
            org_id=org_id,
            actor_user_id=actor_sub,
            action=ROLE_ASSIGN,
            entity_type="USER",
            entity_id=uid,
            details={"system_role": {"from": original_role_norm, "to": new_role_norm}},
        )
    elif changes:
        record_audit_event(
            org_id=org_id,
            actor_user_id=actor_sub,
            action=STRUCTURE_UPDATE,
            entity_type="USER",
            entity_id=uid,
            details=changes,
        )

    return _emp_dict(user, db)


@router.delete("/{uid}")
def deactivate_employee(
    uid: str,
    db: Session = Depends(get_db),
    org_id: str = "",
    _auth: dict = Depends(require_super_admin_or_hr_head),
):
    """Soft-delete: deactivate employee."""
    actor_sub = str(_auth.get("sub") or "")
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(404)
    if user.org_id != org_id:
        raise HTTPException(404)
    user.is_active = False
    db.commit()
    record_audit_event(
        org_id=org_id,
        actor_user_id=actor_sub,
        action=STRUCTURE_UPDATE,
        entity_type="USER",
        entity_id=uid,
        details={"deactivated": True},
    )
    return {"status": "deactivated"}


@router.get("/tree/org-chart")
def get_org_tree(db: Session = Depends(get_db), org_id: str = ""):
    """Build org tree from DIRECT reporting relationships."""
    users = db.query(User).filter(User.org_id == org_id, User.is_active == True).all()
    rels = db.query(ReportingRelationship).filter(
        ReportingRelationship.org_id == org_id,
        ReportingRelationship.relationship_type == "DIRECT",
        ReportingRelationship.is_active == True,
    ).all()
    # Build parent map
    parent_map = {r.employee_id: r.manager_id for r in rels}
    children_map = {}
    for r in rels:
        children_map.setdefault(r.manager_id, []).append(r.employee_id)

    user_map = {u.id: _emp_dict(u, db) for u in users}
    managed = set(parent_map.keys())

    def build_tree(uid):
        node = user_map.get(uid, {})
        node["children"] = [build_tree(cid) for cid in children_map.get(uid, []) if cid in user_map]
        return node

    roots = [uid for uid in user_map if uid not in managed]
    return [build_tree(r) for r in roots]


def _get_name(db, uid):
    u = db.query(User).filter(User.id == uid).first()
    return u.name if u else None

def _emp_dict(user, db):
    plant = db.query(Plant).filter(Plant.id == user.plant_id).first() if user.plant_id else None
    dept = db.query(Department).filter(Department.id == user.department_id).first() if user.department_id else None
    team = db.query(Team).filter(Team.id == user.team_id).first() if user.team_id else None
    desig = db.query(Designation).filter(Designation.id == user.designation_id).first() if user.designation_id else None
    shift = db.query(Shift).filter(Shift.id == user.shift_id).first() if user.shift_id else None
    return {
        "id": user.id, "email": user.email, "name": user.name,
        "employee_id": user.employee_id, "system_role": user.system_role,
        "is_org_creator": user.is_org_creator, "avatar_color": user.avatar_color,
        "is_active": user.is_active,
        "plant_id": user.plant_id, "plant_name": plant.name if plant else None,
        "department_id": user.department_id, "department_name": dept.name if dept else None,
        "team_id": user.team_id, "team_name": team.name if team else None,
        "designation_id": user.designation_id, "designation_name": desig.name if desig else None,
        "shift_id": user.shift_id, "shift_name": shift.name if shift else None,
    }
