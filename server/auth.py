from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, Depends, Request
from server.models import User
from sqlalchemy.orm import Session

SECRET_KEY = "mfg-perf-os-secret-key-change-in-production-2024"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def require_super_admin(current_user: dict = Depends(lambda: None)) -> dict:
    """
    FastAPI dependency that enforces SUPER_ADMIN role.
    
    Raises HTTP 403 if the current user does not have system_role == "SUPER_ADMIN".
    This is a minimal Phase 1 implementation; Phase 3 will replace with SystemRole enum check.
    
    Args:
        current_user: User dict from JWT payload (injected by FastAPI middleware)
    
    Returns:
        The current_user dict if authorized
    
    Raises:
        HTTPException 403 if not authorized
    """
    if not current_user:
        raise HTTPException(401, "Not authenticated")
    
    system_role = current_user.get("system_role") or current_user.get("role")
    if system_role != "SUPER_ADMIN":
        raise HTTPException(403, "SUPER_ADMIN role required for this operation")
    
    return current_user
