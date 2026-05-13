import random
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from server.database import get_db
from server.models import Organization, User
from server.schemas import RegisterRequest, LoginRequest, TokenResponse
from server.auth import get_password_hash, verify_password, create_access_token, decode_access_token
from server.permissions_service import initialize_user_permissions, get_user_permission_profile
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/auth", tags=["auth"])

AVATAR_COLORS = ["#6366f1","#8b5cf6","#ec4899","#f43f5e","#f97316","#eab308","#22c55e","#14b8a6","#0ea5e9","#3b82f6"]


class OnboardEmployeeRequest(BaseModel):
    """Request to onboard a new employee with direct account creation."""
    email: str
    name: str
    password: str
    system_role: str = "EMPLOYEE"
    plant_id: str | None = None
    department_id: str | None = None
    team_id: str | None = None


@router.post("/onboard-employee", response_model=TokenResponse)
def onboard_employee(
    req: OnboardEmployeeRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Onboard a new employee directly into an existing organization.
    Only SUPER_ADMIN or HR_HEAD can call this endpoint.
    """
    # Extract and validate token
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid authorization header")
    
    token = authorization.replace("Bearer ", "")
    payload = decode_access_token(token)
    
    if not payload:
        raise HTTPException(401, "Invalid token")
    
    admin_user_id = payload.get("sub")
    admin_user = db.query(User).filter(User.id == admin_user_id).first()
    
    if not admin_user:
        raise HTTPException(401, "User not found")
    
    # Verify admin has permission
    if admin_user.system_role not in ["SUPER_ADMIN", "HR_HEAD"]:
        raise HTTPException(403, "Only admins can onboard employees")
    
    # Check email not already registered
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(400, "Email already registered")
    
    # Create new user in the same organization
    user = User(
        org_id=admin_user.org_id,
        email=req.email,
        password_hash=get_password_hash(req.password),
        name=req.name,
        system_role=req.system_role,
        is_active=True,
        avatar_color=random.choice(AVATAR_COLORS),
        plant_id=req.plant_id,
        department_id=req.department_id,
    )
    db.add(user)
    db.flush()
    db.commit()
    db.refresh(user)
    
    # Initialize permission profile with the assigned role
    initialize_user_permissions(user, db)
    
    org = db.query(Organization).filter(Organization.id == user.org_id).first()
    token = create_access_token({"sub": user.id, "org_id": user.org_id, "role": user.system_role})
    
    return TokenResponse(
        access_token=token,
        user=_user_dict(user, org, db),
    )


@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == req.admin_email).first()
    if existing:
        raise HTTPException(400, "Email already registered")

    org = Organization(
        name=req.company_name,
        domain=req.domain,
        size=req.org_size,
        setup_completed=False,
    )
    db.add(org)
    db.flush()

    user = User(
        org_id=org.id,
        email=req.admin_email,
        password_hash=get_password_hash(req.password),
        name=req.admin_name,
        system_role="SUPER_ADMIN",
        is_org_creator=True,
        avatar_color=random.choice(AVATAR_COLORS),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.refresh(org)

    # Initialize permission profile for SUPER_ADMIN
    initialize_user_permissions(user, db)

    token = create_access_token({"sub": user.id, "org_id": org.id, "role": user.system_role})
    return TokenResponse(
        access_token=token,
        user=_user_dict(user, org, db),
    )


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    if not user.is_active:
        raise HTTPException(403, "Account deactivated")

    org = db.query(Organization).filter(Organization.id == user.org_id).first()
    
    # Ensure permission profile exists and is up-to-date
    initialize_user_permissions(user, db)
    
    token = create_access_token({"sub": user.id, "org_id": user.org_id, "role": user.system_role})
    return TokenResponse(
        access_token=token,
        user=_user_dict(user, org, db),
    )


@router.get("/me")
def get_me(db: Session = Depends(get_db), authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid authorization header")
    
    token = authorization.replace("Bearer ", "")
    payload = decode_access_token(token)
    
    if not payload:
        raise HTTPException(401, "Invalid or expired token")
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(401, "Token missing user ID")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    org = db.query(Organization).filter(Organization.id == user.org_id).first()
    return _user_dict(user, org, db)



def _user_dict(user, org, db):
    """Build user response dict with permissions."""
    perm_profile = get_user_permission_profile(user.id, db)
    
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "employee_id": user.employee_id,
        "system_role": user.system_role,
        "is_org_creator": user.is_org_creator,
        "avatar_color": user.avatar_color,
        "org_id": user.org_id,
        "org_name": org.name if org else None,
        "org_setup_completed": org.setup_completed if org else False,
        "plant_id": user.plant_id,
        "department_id": user.department_id,
        "designation_id": user.designation_id,
        "shift_id": user.shift_id,
        "permissions": perm_profile,
    }
