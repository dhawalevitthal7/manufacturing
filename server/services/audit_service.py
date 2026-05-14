"""
Best-effort audit logging for privileged mutations (Phase 3.5).

Uses a short-lived Session so audit commits never interfere with the caller's
transaction lifecycle.

Distinct from ROLE_NORMALIZATION audits in server.auth — use only the action
constants defined here for structure / permission / role assignment events.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from server.database import SessionLocal
from server.models import AuditLog

logger = logging.getLogger(__name__)

# Canonical audit actions (permission matrix / dashboards; do not reuse ROLE_NORMALIZATION)
STRUCTURE_CREATE = "STRUCTURE_CREATE"
STRUCTURE_UPDATE = "STRUCTURE_UPDATE"
STRUCTURE_DELETE = "STRUCTURE_DELETE"
PERMISSION_SEED = "PERMISSION_SEED"
MODULE_ACCESS_WRITE = "MODULE_ACCESS_WRITE"
ROLE_MATRIX_WRITE = "ROLE_MATRIX_WRITE"
ROLE_ASSIGN = "ROLE_ASSIGN"


def audit_super_admin_action(
    *,
    org_id: str,
    actor_user_id: str,
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> None:
    """
    Append an AuditLog row after a successful privileged mutation.

    Never affects the caller's SQLAlchemy session — failures are logged only.
    """
    db = SessionLocal()
    try:
        row = AuditLog(
            org_id=org_id or "",
            user_id=actor_user_id or "",
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=json.dumps(details) if details is not None else None,
        )
        db.add(row)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("audit_super_admin_action failed (non-blocking): %s", exc)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


def record_audit_event(
    *,
    org_id: str,
    actor_user_id: str,
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> None:
    """Same as audit_super_admin_action; use for HR_HEAD trails (e.g. employee profile)."""
    audit_super_admin_action(
        org_id=org_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
