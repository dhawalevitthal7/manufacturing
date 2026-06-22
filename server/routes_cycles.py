from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from server.database import get_db
from server.models import Cycle, CycleStatus
from server.schemas import CycleCreate
from server.auth import require_super_admin

router = APIRouter(prefix="/api/cycles", tags=["cycles"])

@router.get("")
def list_cycles(
    db: Session = Depends(get_db),
    org_id: str = "",
    status: Optional[str] = None
):
    q = db.query(Cycle).filter(Cycle.org_id == org_id)
    if status:
        q = q.filter(Cycle.status == status.upper())
    
    cycles = q.order_by(Cycle.start_date.desc()).all()
    
    return [
        {
            "id": c.id,
            "name": c.name,
            "cycle_type": c.cycle_type,
            "start_date": c.start_date,
            "end_date": c.end_date,
            "freeze_date": c.freeze_date,
            "status": c.status,
            "applies_to_levels": c.applies_to_levels,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in cycles
    ]

@router.post("")
def create_cycle(
    req: CycleCreate,
    db: Session = Depends(get_db),
    org_id: str = "",
    _auth: dict = Depends(require_super_admin)
):
    cycle = Cycle(
        org_id=org_id,
        name=req.name,
        cycle_type=req.cycle_type,
        start_date=req.start_date,
        end_date=req.end_date,
        freeze_date=req.freeze_date,
        applies_to_levels=req.applies_to_levels or []
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return {
        "id": cycle.id,
        "name": cycle.name,
        "cycle_type": cycle.cycle_type,
        "start_date": cycle.start_date,
        "end_date": cycle.end_date,
        "freeze_date": cycle.freeze_date,
        "status": cycle.status,
        "applies_to_levels": cycle.applies_to_levels,
        "created_at": cycle.created_at.isoformat() if cycle.created_at else None,
    }

@router.patch("/{cycle_id}/freeze")
def freeze_cycle(
    cycle_id: str,
    db: Session = Depends(get_db),
    org_id: str = "",
    _auth: dict = Depends(require_super_admin)
):
    cycle = db.query(Cycle).filter(Cycle.id == cycle_id, Cycle.org_id == org_id).first()
    if not cycle:
        raise HTTPException(404, "Cycle not found")
    
    cycle.status = CycleStatus.FROZEN.value
    db.commit()
    db.refresh(cycle)
    
    return {"status": "success", "cycle_status": cycle.status}

@router.patch("/{cycle_id}/close")
def close_cycle(
    cycle_id: str,
    db: Session = Depends(get_db),
    org_id: str = "",
    _auth: dict = Depends(require_super_admin)
):
    cycle = db.query(Cycle).filter(Cycle.id == cycle_id, Cycle.org_id == org_id).first()
    if not cycle:
        raise HTTPException(404, "Cycle not found")
    
    cycle.status = CycleStatus.CLOSED.value
    db.commit()
    db.refresh(cycle)
    
    return {"status": "success", "cycle_status": cycle.status}
