import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, Header, HTTPException
from jose import JWTError, jwt
from passlib.context import CryptContext

from server.database import SessionLocal
from server.models import AuditLog
from server.roles import SystemRole, normalize_role

logger = logging.getLogger(__name__)

SECRET_KEY = "mfg-perf-os-secret-key-change-in-production-2024"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Process-lifetime dedupe for ROLE_NORMALIZATION audit rows (not HTTP request scoped).
# Resets on worker restart; duplicate audit rows across restarts are acceptable.
_ROLE_NORMALIZATION_AUDIT_DEDUPE: set[tuple[str, str]] = set()

AUDIT_ACTION_ROLE_NORMALIZATION = "ROLE_NORMALIZATION"


def _canonical_role_for_token(role: str) -> str:
    """Defense-in-depth: canonical role string for JWT ``role`` claim."""
    return normalize_role(role).value


def _write_role_normalization_audit(
    *,
    user_id: str,
    org_id: str,
    raw: str,
    canonical: str,
) -> None:
    db = SessionLocal()
    try:
        db.add(
            AuditLog(
                org_id=org_id or "",
                user_id=user_id,
                action=AUDIT_ACTION_ROLE_NORMALIZATION,
                entity_type="USER",
                entity_id=user_id,
                details=json.dumps(
                    {
                        "raw_role": raw,
                        "canonical_role": canonical,
                        "source": "jwt_claim",
                    }
                ),
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _normalize_jwt_role_claim(payload: dict, claim_key: str) -> None:
    """Replace a single role claim with its canonical string; audit if mapping changed."""
    if claim_key not in payload:
        return
    raw_val = payload[claim_key]
    if raw_val is None:
        return
    raw_str = str(raw_val).strip()
    canonical = normalize_role(raw_str)
    canonical_str = canonical.value
    payload[claim_key] = canonical_str
    if raw_str == canonical_str:
        return
    user_id = str(payload.get("sub") or "")
    if not user_id:
        return
    dedupe_key = (user_id, raw_str)
    if dedupe_key in _ROLE_NORMALIZATION_AUDIT_DEDUPE:
        return
    _ROLE_NORMALIZATION_AUDIT_DEDUPE.add(dedupe_key)
    org_id = payload.get("org_id") or ""
    try:
        _write_role_normalization_audit(
            user_id=user_id,
            org_id=org_id,
            raw=raw_str,
            canonical=canonical_str,
        )
    except Exception as e:
        logger.warning("Audit write failed: %s", e)


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
        _normalize_jwt_role_claim(payload, "role")
        _normalize_jwt_role_claim(payload, "system_role")
        return payload
    except JWTError:
        return None


def get_jwt_payload(authorization: Optional[str] = Header(None)) -> dict:
    """
    Resolve the current JWT claims from the Authorization header.
    Same contract as routes_auth.get_me / onboard-employee: Bearer token, decode via decode_access_token.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid authorization header")
    token = authorization.replace("Bearer ", "", 1).strip()
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(401, "Invalid or expired token")
    return payload


def require_super_admin(payload: dict = Depends(get_jwt_payload)) -> dict:
    """
    Enforce SUPER_ADMIN using JWT from Authorization (not query params).

    Token is issued with claim ``role`` (= user.system_role); some callers may add system_role later.
    """
    system_role = payload.get("system_role") or payload.get("role")
    if normalize_role(str(system_role or "")).value != SystemRole.SUPER_ADMIN.value:
        raise HTTPException(403, "SUPER_ADMIN role required for this operation")
    return payload


def require_super_admin_or_hr_head(payload: dict = Depends(get_jwt_payload)) -> dict:
    """Bearer JWT; actor must be SUPER_ADMIN or HR_HEAD (onboarding / roster / HR flows)."""
    raw = str(payload.get("system_role") or payload.get("role") or "")
    role = normalize_role(raw)
    if role not in (SystemRole.SUPER_ADMIN, SystemRole.HR_HEAD):
        raise HTTPException(403, "SUPER_ADMIN or HR_HEAD role required for this operation")
    return payload
