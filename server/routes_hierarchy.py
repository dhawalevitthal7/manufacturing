import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from server.database import get_db
from server.models import ReportingRelationship, User, AuditLog
from server.schemas import ReportingRelCreate, ReportingRelBulkCreate

router = APIRouter(prefix="/api/hierarchy", tags=["hierarchy"])


@router.post("/relationships")
def create_relationship(req: ReportingRelCreate, db: Session = Depends(get_db), org_id: str = "", user_id: str = ""):
    """Create a reporting relationship: DIRECT, DOTTED_LINE, REVIEWER, APPROVER."""
    if req.employee_id == req.manager_id:
        raise HTTPException(400, "Cannot create self-relationship")
    # Check both users exist in org
    emp = db.query(User).filter(User.id == req.employee_id, User.org_id == org_id).first()
    mgr = db.query(User).filter(User.id == req.manager_id, User.org_id == org_id).first()
    if not emp or not mgr:
        raise HTTPException(404, "Employee or manager not found in this organization")
    # Check duplicate
    existing = db.query(ReportingRelationship).filter(
        ReportingRelationship.employee_id == req.employee_id,
        ReportingRelationship.manager_id == req.manager_id,
        ReportingRelationship.relationship_type == req.relationship_type,
    ).first()
    if existing:
        raise HTTPException(400, "Relationship already exists")
    # Prevent circular DIRECT reporting
    if req.relationship_type == "DIRECT":
        if _is_circular(db, org_id, req.manager_id, req.employee_id):
            raise HTTPException(400, "Circular reporting chain detected")

    rel = ReportingRelationship(
        org_id=org_id, employee_id=req.employee_id,
        manager_id=req.manager_id, relationship_type=req.relationship_type,
    )
    db.add(rel)
    db.add(AuditLog(org_id=org_id, user_id=user_id, action="CREATE",
                    entity_type="REPORTING_REL", entity_id=rel.id,
                    details=json.dumps({"employee": emp.name, "manager": mgr.name, "type": req.relationship_type})))
    db.commit()
    db.refresh(rel)
    return {"id": rel.id, "employee_id": rel.employee_id, "employee_name": emp.name,
            "manager_id": rel.manager_id, "manager_name": mgr.name,
            "relationship_type": rel.relationship_type}


@router.post("/relationships/bulk")
def bulk_create_relationships(req: ReportingRelBulkCreate, db: Session = Depends(get_db), org_id: str = "", user_id: str = ""):
    """Bulk create reporting relationships."""
    created, errors = 0, []
    for r in req.relationships:
        try:
            if r.employee_id == r.manager_id:
                errors.append(f"Self-relationship for {r.employee_id}")
                continue
            existing = db.query(ReportingRelationship).filter(
                ReportingRelationship.employee_id == r.employee_id,
                ReportingRelationship.manager_id == r.manager_id,
                ReportingRelationship.relationship_type == r.relationship_type,
            ).first()
            if existing:
                errors.append(f"Duplicate: {r.employee_id} -> {r.manager_id} ({r.relationship_type})")
                continue
            rel = ReportingRelationship(
                org_id=org_id, employee_id=r.employee_id,
                manager_id=r.manager_id, relationship_type=r.relationship_type,
            )
            db.add(rel)
            created += 1
        except Exception as e:
            errors.append(str(e))
    db.commit()
    return {"created": created, "errors": errors}


@router.get("/relationships")
def list_relationships(db: Session = Depends(get_db), org_id: str = "",
                       employee_id: str = "", manager_id: str = "",
                       relationship_type: str = ""):
    """List all reporting relationships with filters."""
    q = db.query(ReportingRelationship).filter(
        ReportingRelationship.org_id == org_id, ReportingRelationship.is_active == True)
    if employee_id:
        q = q.filter(ReportingRelationship.employee_id == employee_id)
    if manager_id:
        q = q.filter(ReportingRelationship.manager_id == manager_id)
    if relationship_type:
        q = q.filter(ReportingRelationship.relationship_type == relationship_type)
    rels = q.all()
    return [_rel_dict(r, db) for r in rels]


@router.delete("/relationships/{rel_id}")
def delete_relationship(rel_id: str, db: Session = Depends(get_db), user_id: str = "", org_id: str = ""):
    rel = db.query(ReportingRelationship).filter(ReportingRelationship.id == rel_id).first()
    if not rel:
        raise HTTPException(404)
    rel.is_active = False
    db.add(AuditLog(org_id=org_id, user_id=user_id, action="DELETE",
                    entity_type="REPORTING_REL", entity_id=rel_id))
    db.commit()
    return {"status": "deactivated"}


@router.get("/chain/{uid}")
def get_reporting_chain(uid: str, db: Session = Depends(get_db), org_id: str = ""):
    """Walk upward through DIRECT reporting chain from employee to top."""
    chain = []
    current = uid
    visited = set()
    while current and current not in visited:
        visited.add(current)
        user = db.query(User).filter(User.id == current).first()
        if not user:
            break
        chain.append({"id": user.id, "name": user.name, "system_role": user.system_role,
                       "designation": _get_designation(db, user.designation_id)})
        rel = db.query(ReportingRelationship).filter(
            ReportingRelationship.employee_id == current,
            ReportingRelationship.relationship_type == "DIRECT",
            ReportingRelationship.is_active == True,
        ).first()
        current = rel.manager_id if rel else None
    return chain


@router.get("/subtree/{uid}")
def get_subtree(uid: str, db: Session = Depends(get_db), org_id: str = ""):
    """Get all direct and indirect reports under a manager."""
    result = []
    queue = [uid]
    visited = set()
    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        direct = db.query(ReportingRelationship).filter(
            ReportingRelationship.manager_id == current,
            ReportingRelationship.relationship_type == "DIRECT",
            ReportingRelationship.is_active == True,
        ).all()
        for r in direct:
            emp = db.query(User).filter(User.id == r.employee_id).first()
            if emp:
                result.append({"id": emp.id, "name": emp.name, "system_role": emp.system_role,
                               "reports_to": current})
                queue.append(emp.id)
    return result


@router.get("/reviewers/{uid}")
def get_reviewers(uid: str, db: Session = Depends(get_db)):
    """Get all REVIEWER-type relationships for an employee."""
    rels = db.query(ReportingRelationship).filter(
        ReportingRelationship.employee_id == uid,
        ReportingRelationship.relationship_type == "REVIEWER",
        ReportingRelationship.is_active == True,
    ).all()
    return [{"manager_id": r.manager_id, "name": _get_name(db, r.manager_id)} for r in rels]


@router.get("/approvers/{uid}")
def get_approvers(uid: str, db: Session = Depends(get_db)):
    """Get all APPROVER-type relationships for an employee."""
    rels = db.query(ReportingRelationship).filter(
        ReportingRelationship.employee_id == uid,
        ReportingRelationship.relationship_type == "APPROVER",
        ReportingRelationship.is_active == True,
    ).all()
    return [{"manager_id": r.manager_id, "name": _get_name(db, r.manager_id)} for r in rels]


def _is_circular(db, org_id, start_id, target_id):
    """Check if making target_id report to start_id creates a circular chain."""
    current = start_id
    visited = set()
    while current and current not in visited:
        if current == target_id:
            return True
        visited.add(current)
        rel = db.query(ReportingRelationship).filter(
            ReportingRelationship.employee_id == current,
            ReportingRelationship.relationship_type == "DIRECT",
            ReportingRelationship.is_active == True,
        ).first()
        current = rel.manager_id if rel else None
    return False

def _get_name(db, uid):
    u = db.query(User).filter(User.id == uid).first()
    return u.name if u else None

def _get_designation(db, did):
    from server.models import Designation
    d = db.query(Designation).filter(Designation.id == did).first() if did else None
    return d.name if d else None

def _rel_dict(r, db):
    return {
        "id": r.id, "employee_id": r.employee_id, "manager_id": r.manager_id,
        "employee_name": _get_name(db, r.employee_id),
        "manager_name": _get_name(db, r.manager_id),
        "relationship_type": r.relationship_type, "is_active": r.is_active,
    }
