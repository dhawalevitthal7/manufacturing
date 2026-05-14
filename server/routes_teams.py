"""
Team Management Routes
=======================

Endpoints for managing team membership, team leads, and team operations.
Managers can add/remove members, designate team leads, and manage team OKRs.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from server.database import get_db
from server.models import (
    Team, TeamMember, User, Department, Plant, Objective, KeyResult,
    OrgNode,
)
from server.schemas import TeamCreate, TeamUpdate
from server.team_membership_service import enroll_team_member
from server.auth import require_super_admin, require_super_admin_or_hr_head
from server.services.org_tree_service import sync_org_node_for
from server.services.audit_service import (
    audit_super_admin_action,
    STRUCTURE_CREATE,
    STRUCTURE_UPDATE,
    STRUCTURE_DELETE,
)

router = APIRouter(prefix="/api/teams", tags=["teams"])


# ──────────────────────────────────────────────────────────────────────────────
# LIST TEAMS
# ──────────────────────────────────────────────────────────────────────────────

@router.get("")
def list_teams(
    db: Session = Depends(get_db),
    org_id: str = "",
    department_id: Optional[str] = Query(None),
    plant_id: Optional[str] = Query(None),
    include_members: bool = Query(False),
):
    """
    List all teams, optionally filtered by department or plant.
    
    Args:
        org_id: Organization ID
        department_id: Filter by department
        plant_id: Filter by plant (will resolve to departments)
        include_members: Include full member details (default: count only)
    """
    q = db.query(Team).filter(Team.org_id == org_id)
    
    if department_id:
        q = q.filter(Team.department_id == department_id)
    elif plant_id:
        # Filter teams by their department's plant
        q = q.join(Department).filter(Department.plant_id == plant_id)
    
    teams = q.all()
    
    result = []
    for team in teams:
        dept = db.query(Department).filter(Department.id == team.department_id).first()
        plant = db.query(Plant).filter(Plant.id == dept.plant_id).first() if dept else None
        lead = db.query(User).filter(User.id == team.lead_id).first() if team.lead_id else None
        
        # Get members
        members_query = db.query(TeamMember).filter(
            TeamMember.team_id == team.id,
            TeamMember.is_active == True
        ).all()
        
        member_count = len(members_query)
        members_list = []
        
        if include_members:
            for tm in members_query:
                user = db.query(User).filter(User.id == tm.user_id).first()
                if user:
                    # Get user's OKRs
                    user_okrs = db.query(Objective).filter(
                        Objective.owner_id == user.id,
                        Objective.team_id == team.id,
                        Objective.status.in_(["ACTIVE", "IN_PROGRESS"])
                    ).count()
                    
                    members_list.append({
                        "id": user.id,
                        "name": user.name,
                        "email": user.email,
                        "employee_id": user.employee_id,
                        "is_team_lead": tm.is_team_lead,
                        "role_in_team": tm.role_in_team,
                        "active_okrs": user_okrs,
                        "joined_at": tm.joined_at.isoformat() if tm.joined_at else None,
                    })
        
        # Calculate team OKR progress
        team_okrs = db.query(Objective).filter(
            Objective.team_id == team.id,
            Objective.level == "TEAM",
            Objective.status == "ACTIVE"
        ).all()
        
        avg_progress = 0.0
        if team_okrs:
            total_progress = sum(o.progress for o in team_okrs)
            avg_progress = round(total_progress / len(team_okrs), 1)
        
        team_data = {
            "id": team.id,
            "name": team.name,
            "department_id": team.department_id,
            "department_name": dept.name if dept else None,
            "plant_id": plant.id if plant else None,
            "plant_name": plant.name if plant else None,
            "lead_id": team.lead_id,
            "lead_name": lead.name if lead else None,
            "member_count": member_count,
            "okr_count": len(team_okrs),
            "average_progress": avg_progress,
            "is_active": team.is_active,
            "created_at": team.created_at.isoformat() if team.created_at else None,
        }
        
        if include_members:
            team_data["members"] = members_list
        
        result.append(team_data)
    
    return result


# ──────────────────────────────────────────────────────────────────────────────
# GET TEAM DETAILS
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/{team_id}")
def get_team(
    team_id: str,
    db: Session = Depends(get_db),
    org_id: str = "",
):
    """
    Get detailed information about a specific team including members, their OKRs, and team OKRs.
    
    Response includes:
    - Team basic info
    - All active members with their OKRs
    - Team OKRs with progress
    - Member contribution metrics
    """
    team = db.query(Team).filter(
        Team.id == team_id,
        Team.org_id == org_id
    ).first()
    
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    dept = db.query(Department).filter(Department.id == team.department_id).first()
    plant = db.query(Plant).filter(Plant.id == dept.plant_id).first() if dept else None
    lead = db.query(User).filter(User.id == team.lead_id).first() if team.lead_id else None
    
    # Get team members with OKR information
    members_query = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.is_active == True
    ).all()
    
    members = []
    total_member_okrs = 0
    total_member_progress = 0.0
    
    for tm in members_query:
        user = db.query(User).filter(User.id == tm.user_id).first()
        if user:
            # Get user's OKRs scoped to this team
            user_okrs = db.query(Objective).filter(
                Objective.owner_id == user.id,
                Objective.team_id == team_id,
                Objective.status.in_(["ACTIVE", "IN_PROGRESS"])
            ).all()
            
            user_progress = 0.0
            if user_okrs:
                total_progress = sum(o.progress for o in user_okrs)
                user_progress = round(total_progress / len(user_okrs), 1)
            
            total_member_okrs += len(user_okrs)
            total_member_progress += user_progress
            
            members.append({
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "employee_id": user.employee_id,
                "system_role": user.system_role,
                "designation": user.designation_id,
                "team_member_id": tm.id,
                "is_team_lead": tm.is_team_lead,
                "role_in_team": tm.role_in_team,
                "joined_at": tm.joined_at.isoformat() if tm.joined_at else None,
                "active_okrs": len(user_okrs),
                "average_progress": user_progress,
            })
    
    # Get team OKRs with progress details
    team_okrs = db.query(Objective).filter(
        Objective.team_id == team_id,
        Objective.level == "TEAM",
        Objective.status == "ACTIVE"
    ).all()
    
    okrs = []
    team_avg_progress = 0.0
    
    for okr in team_okrs:
        krs = db.query(KeyResult).filter(KeyResult.objective_id == okr.id).all()
        
        okrs.append({
            "id": okr.id,
            "title": okr.title,
            "description": okr.description,
            "status": okr.status,
            "progress": okr.progress,
            "key_results_count": len(krs),
            "owner_name": db.query(User).filter(User.id == okr.owner_id).first().name if okr.owner_id else None,
            "created_at": okr.created_at.isoformat() if okr.created_at else None,
        })
    
    if okrs:
        team_avg_progress = round(sum(o["progress"] for o in okrs) / len(okrs), 1)
    
    return {
        "id": team.id,
        "name": team.name,
        "department_id": team.department_id,
        "department_name": dept.name if dept else None,
        "plant_id": plant.id if plant else None,
        "plant_name": plant.name if plant else None,
        "lead_id": team.lead_id,
        "lead_name": lead.name if lead else None,
        "is_active": team.is_active,
        "members": members,
        "member_count": len(members),
        "members_stats": {
            "total_okrs": total_member_okrs,
            "average_progress": round(total_member_progress / len(members), 1) if members else 0.0,
        },
        "okrs": okrs,
        "okr_count": len(okrs),
        "team_average_progress": team_avg_progress,
        "created_at": team.created_at.isoformat() if team.created_at else None,
    }


@router.put("/{team_id}")
def update_team(
    team_id: str,
    req: TeamUpdate,
    db: Session = Depends(get_db),
    org_id: str = "",
    _auth: dict = Depends(require_super_admin),
):
    """Update team name, department, or lead (SUPER_ADMIN). Syncs OrgNode when possible."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    if team.org_id != org_id:
        raise HTTPException(status_code=404, detail="Not found")

    body = req.model_dump(exclude_unset=True)

    if "name" in body and body["name"] is not None:
        team.name = body["name"]
    if "lead_id" in body:
        team.lead_id = body["lead_id"]
    if "department_id" in body and body["department_id"] is not None:
        new_dept_id = body["department_id"]
        dept = db.query(Department).filter(
            Department.id == new_dept_id,
            Department.org_id == org_id,
        ).first()
        if not dept:
            raise HTTPException(status_code=404, detail="Department not found")
        team.department_id = new_dept_id

    dept_node = (
        db.query(OrgNode).filter(
            OrgNode.node_type == "DEPARTMENT",
            OrgNode.org_id == org_id,
            OrgNode.id == team.department_id,
        ).first()
    )
    if dept_node:
        try:
            sync_org_node_for(
                entity_type="TEAM",
                entity_id=team.id,
                org_id=org_id,
                name=team.name,
                parent_id=dept_node.id,
                code=None,
                head_user_id=team.lead_id,
                db=db,
            )
        except HTTPException:
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to sync org node: {exc}") from exc

    db.commit()
    db.refresh(team)
    audit_super_admin_action(
        org_id=org_id,
        actor_user_id=str(_auth.get("sub") or ""),
        action=STRUCTURE_UPDATE,
        entity_type="TEAM",
        entity_id=team_id,
        details=body,
    )
    return {
        "id": team.id,
        "name": team.name,
        "department_id": team.department_id,
        "lead_id": team.lead_id,
    }


@router.delete("/{team_id}")
def delete_team(
    team_id: str,
    db: Session = Depends(get_db),
    org_id: str = "",
    _auth: dict = Depends(require_super_admin),
):
    """Soft-delete a team and its roster rows (SUPER_ADMIN)."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    if team.org_id != org_id:
        raise HTTPException(status_code=404, detail="Not found")

    team.is_active = False
    for tm in (
        db.query(TeamMember)
        .filter(TeamMember.team_id == team_id, TeamMember.org_id == org_id)
        .all()
    ):
        tm.is_active = False

    node = (
        db.query(OrgNode)
        .filter(OrgNode.id == team_id, OrgNode.org_id == org_id, OrgNode.node_type == "TEAM")
        .first()
    )
    if node:
        node.is_active = False

    db.commit()
    audit_super_admin_action(
        org_id=org_id,
        actor_user_id=str(_auth.get("sub") or ""),
        action=STRUCTURE_DELETE,
        entity_type="TEAM",
        entity_id=team_id,
        details={"name": team.name},
    )
    return {"status": "deleted", "id": team_id}


# ──────────────────────────────────────────────────────────────────────────────
# CREATE TEAM
# ──────────────────────────────────────────────────────────────────────────────

@router.post("")
def create_team(
    req: TeamCreate,
    db: Session = Depends(get_db),
    org_id: str = "",
    _auth: dict = Depends(require_super_admin),
):
    """Create a new team in a department, optionally with roster and lead."""
    dept = db.query(Department).filter(
        Department.id == req.department_id,
        Department.org_id == org_id
    ).first()

    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    team = Team(
        org_id=org_id,
        department_id=req.department_id,
        name=req.name,
        lead_id=req.lead_id,
    )

    db.add(team)
    db.flush()

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
                raise HTTPException(status_code=409, detail="User is already on this team")
            raise HTTPException(status_code=400, detail=msg)

    if req.lead_id:
        team.lead_id = req.lead_id
        db.flush()

    db.commit()
    db.refresh(team)

    audit_super_admin_action(
        org_id=org_id,
        actor_user_id=str(_auth.get("sub") or ""),
        action=STRUCTURE_CREATE,
        entity_type="TEAM",
        entity_id=team.id,
        details={
            "name": team.name,
            "department_id": team.department_id,
            "lead_id": team.lead_id,
            "member_count": len(ordered),
        },
    )

    return {
        "id": team.id,
        "name": team.name,
        "department_id": team.department_id,
        "lead_id": team.lead_id,
        "created_at": team.created_at.isoformat() if team.created_at else None,
    }


# ──────────────────────────────────────────────────────────────────────────────
# ADD TEAM MEMBER
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/{team_id}/members")
def add_team_member(
    team_id: str,
    member_user_id: str = Query(..., description="User id to add to the team"),
    is_team_lead: bool = Query(False),
    db: Session = Depends(get_db),
    org_id: str = "",
    _auth: dict = Depends(require_super_admin_or_hr_head),
):
    """
    Add a member to a team with automatic OKR hierarchy connection.
    
    When an existing employee is added to a team:
    1. Create TeamMember record
    2. Link employee's INDIVIDUAL OKRs to team OKRs
    3. Update employee hierarchy scope (team_id)
    """
    # Verify team exists
    team = db.query(Team).filter(
        Team.id == team_id,
        Team.org_id == org_id
    ).first()
    
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Verify user exists
    user = db.query(User).filter(
        User.id == member_user_id,
        User.org_id == org_id
    ).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if already a member
    existing = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == member_user_id
    ).first()
    
    if existing:
        if not existing.is_active:
            try:
                team_member = enroll_team_member(db, org_id, team, member_user_id, is_team_lead)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            db.commit()
            db.refresh(team_member)
            return {
                "status": "reactivated",
                "team_member_id": team_member.id,
                "user_id": member_user_id,
                "is_team_lead": team_member.is_team_lead,
                "okr_connections": "existing connections retained"
            }
        raise HTTPException(status_code=409, detail="User is already a member of this team")
    
    try:
        team_member = enroll_team_member(db, org_id, team, member_user_id, is_team_lead)
    except ValueError as e:
        if str(e) == "already_active_member":
            raise HTTPException(status_code=409, detail="User is already a member of this team")
        raise HTTPException(status_code=400, detail=str(e))
    
    db.commit()
    db.refresh(team_member)
    
    return {
        "status": "added",
        "team_member_id": team_member.id,
        "user_id": member_user_id,
        "is_team_lead": team_member.is_team_lead,
        "joined_at": team_member.joined_at.isoformat() if team_member.joined_at else None,
        "okr_connections": "Member enrolled and individual OKRs linked where applicable",
    }


# ──────────────────────────────────────────────────────────────────────────────
# REMOVE TEAM MEMBER
# ──────────────────────────────────────────────────────────────────────────────

@router.delete("/{team_id}/members/{user_id}")
def remove_team_member(
    team_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    org_id: str = "",
    _auth: dict = Depends(require_super_admin_or_hr_head),
):
    """Remove a member from a team."""
    team_member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == user_id,
        TeamMember.org_id == org_id
    ).first()
    
    if not team_member:
        raise HTTPException(status_code=404, detail="Team member not found")
    
    # Soft delete
    team_member.is_active = False
    db.commit()
    
    return {"status": "removed", "user_id": user_id}


# ──────────────────────────────────────────────────────────────────────────────
# UPDATE TEAM LEAD STATUS
# ──────────────────────────────────────────────────────────────────────────────

@router.put("/{team_id}/members/{user_id}/lead-status")
def update_team_lead_status(
    team_id: str,
    user_id: str,
    is_team_lead: bool = Query(...),
    db: Session = Depends(get_db),
    org_id: str = "",
    _auth: dict = Depends(require_super_admin),
):
    """Update team lead designation for a team member."""
    team_member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == user_id,
        TeamMember.org_id == org_id
    ).first()
    
    if not team_member:
        raise HTTPException(status_code=404, detail="Team member not found")
    
    team_member.is_team_lead = is_team_lead
    team_member.role_in_team = "LEAD" if is_team_lead else "MEMBER"
    db.commit()
    db.refresh(team_member)
    
    # If making someone a lead, update team's lead_id
    if is_team_lead:
        team = db.query(Team).filter(Team.id == team_id, Team.org_id == org_id).first()
        if team:
            team.lead_id = user_id
            db.commit()

    audit_super_admin_action(
        org_id=org_id,
        actor_user_id=str(_auth.get("sub") or ""),
        action=STRUCTURE_UPDATE,
        entity_type="TEAM",
        entity_id=team_id,
        details={"member_user_id": user_id, "is_team_lead": is_team_lead},
    )

    return {
        "status": "updated",
        "user_id": user_id,
        "is_team_lead": team_member.is_team_lead,
        "role_in_team": team_member.role_in_team,
    }


# ──────────────────────────────────────────────────────────────────────────────
# GET TEAM MEMBERS
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/{team_id}/members")
def get_team_members(
    team_id: str,
    db: Session = Depends(get_db),
    org_id: str = "",
):
    """Get all members of a team."""
    team = db.query(Team).filter(
        Team.id == team_id,
        Team.org_id == org_id
    ).first()
    
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    team_members = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.is_active == True
    ).all()
    
    members = []
    for tm in team_members:
        user = db.query(User).filter(User.id == tm.user_id).first()
        if user:
            members.append({
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "employee_id": user.employee_id,
                "system_role": user.system_role,
                "designation": user.designation_id,
                "team_member_id": tm.id,
                "is_team_lead": tm.is_team_lead,
                "role_in_team": tm.role_in_team,
                "joined_at": tm.joined_at.isoformat() if tm.joined_at else None,
            })
    
    return members
