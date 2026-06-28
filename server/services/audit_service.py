"""
Best-effort audit logging for privileged mutations (Phase 3.5).

When ``db`` is passed, the row is added to the caller's session (no extra commit).
Otherwise a short-lived session is used with retry on SQLite lock.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from server.database import SessionLocal
from server.models import AuditLog

logger = logging.getLogger(__name__)

STRUCTURE_CREATE = "STRUCTURE_CREATE"
STRUCTURE_UPDATE = "STRUCTURE_UPDATE"
STRUCTURE_DELETE = "STRUCTURE_DELETE"
PERMISSION_SEED = "PERMISSION_SEED"
MODULE_ACCESS_WRITE = "MODULE_ACCESS_WRITE"
ROLE_MATRIX_WRITE = "ROLE_MATRIX_WRITE"
ROLE_ASSIGN = "ROLE_ASSIGN"


def _append_audit_row(
    db: Session,
    *,
    org_id: str,
    actor_user_id: str,
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> None:
    db.add(
        AuditLog(
            org_id=org_id or "",
            user_id=actor_user_id or "",
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=json.dumps(details) if details is not None else None,
        )
    )


def audit_super_admin_action(
    *,
    org_id: str,
    actor_user_id: str,
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    db: Optional[Session] = None,
) -> None:
    if db is not None:
        try:
            _append_audit_row(
                db,
                org_id=org_id,
                actor_user_id=actor_user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                details=details,
            )
        except Exception as exc:
            logger.warning("audit append failed (non-blocking): %s", exc)
        return

    for attempt in range(1, 6):
        session = SessionLocal()
        try:
            _append_audit_row(
                session,
                org_id=org_id,
                actor_user_id=actor_user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                details=details,
            )
            session.commit()
            return
        except OperationalError as exc:
            session.rollback()
            if "locked" not in str(exc).lower() or attempt == 5:
                logger.warning("audit_super_admin_action failed (non-blocking): %s", exc)
                return
            time.sleep(0.2 * attempt)
        except Exception as exc:
            logger.warning("audit_super_admin_action failed (non-blocking): %s", exc)
            return
        finally:
            session.close()


def record_audit_event(
    *,
    org_id: str,
    actor_user_id: str,
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    db: Optional[Session] = None,
) -> None:
    audit_super_admin_action(
        org_id=org_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        db=db,
    )
