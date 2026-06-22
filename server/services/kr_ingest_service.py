"""Phase 8: KR value ingest from external systems (SCADA / MES / SAP)."""

from __future__ import annotations

import ast
import hashlib
import operator
import secrets
from collections import defaultdict, deque
from datetime import datetime
from time import time
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from server.models import KeyResult, KRIngestSource, Objective, ProgressUpdate
from server.services.audit_service import record_audit_event

_RATE_BUCKETS: dict[str, deque] = defaultdict(deque)
_RATE_LIMIT_PER_MINUTE = 60

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_UNARY_OPS = {ast.USub: operator.neg}


def hash_ingest_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_ingest_token() -> tuple[str, str]:
    """Return (plaintext token for client, stored hash)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_ingest_token(raw)


def verify_ingest_token(raw_token: str, stored_hash: str) -> bool:
    if not raw_token or not stored_hash:
        return False
    return hash_ingest_token(raw_token) == stored_hash


def _check_rate_limit(source_id: str) -> None:
    now = time()
    bucket = _RATE_BUCKETS[source_id]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= _RATE_LIMIT_PER_MINUTE:
        raise HTTPException(429, "Rate limit exceeded for this ingest source (60/min)")
    bucket.append(now)


def apply_transform(expr: Optional[str], value: float) -> float:
    """Apply a simple transform expression with variable x (or value)."""
    if not expr or not str(expr).strip():
        return value
    cleaned = str(expr).strip()
    if cleaned in ("x", "value"):
        return value
    try:
        tree = ast.parse(cleaned, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Invalid transform expression: {exc}") from exc

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name) and node.id in ("x", "value"):
            return float(value)
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            return _BIN_OPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
            return _UNARY_OPS[type(node.op)](_eval(node.operand))
        raise ValueError("Transform may only use x, numbers, and + - * /")

    return float(_eval(tree))


def ingest_source_dict(src: KRIngestSource, *, include_tag: bool = True) -> dict[str, Any]:
    return {
        "id": src.id,
        "key_result_id": src.key_result_id,
        "source_system": src.source_system,
        "source_metric_tag": src.source_metric_tag if include_tag else None,
        "transform_expr": src.transform_expr,
        "is_active": bool(src.is_active),
        "last_ingest_at": src.last_ingest_at.isoformat() if src.last_ingest_at else None,
        "last_ingest_value": src.last_ingest_value,
        "created_at": src.created_at.isoformat() if src.created_at else None,
    }


def process_kr_ingest(
    db: Session,
    *,
    source_metric_tag: str,
    value: float,
    raw_token: str,
    timestamp: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> dict[str, Any]:
    """Match tag + token, update KR, write ProgressUpdate and audit row."""
    tag = (source_metric_tag or "").strip()
    if not tag:
        raise HTTPException(400, "source_metric_tag is required")

    sources = (
        db.query(KRIngestSource)
        .filter(
            KRIngestSource.source_metric_tag == tag,
            KRIngestSource.is_active == True,
        )
        .all()
    )
    matched: Optional[KRIngestSource] = None
    for src in sources:
        if verify_ingest_token(raw_token, src.api_token_hash):
            matched = src
            break
    if not matched:
        raise HTTPException(401, "Invalid ingest token or unknown metric tag")

    _check_rate_limit(matched.id)

    kr = db.query(KeyResult).filter(KeyResult.id == matched.key_result_id).first()
    if not kr:
        raise HTTPException(404, "Key result not found")

    try:
        new_value = apply_transform(matched.transform_expr, float(value))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    previous = kr.current_value or 0.0
    kr.current_value = new_value
    if kr.status == "NOT_STARTED":
        kr.status = "IN_PROGRESS"

    update = ProgressUpdate(
        key_result_id=kr.id,
        submitted_by_id="system:kr-ingest",
        previous_value=previous,
        new_value=new_value,
        notes=f"Auto-ingest from {matched.source_system}"
        + (f" at {timestamp}" if timestamp else ""),
        status="APPROVED",
        progress_source="AUTO_INGEST",
        is_manual_override=False,
        auto_tracked=True,
        approved_at=datetime.utcnow(),
        validated_at=datetime.utcnow(),
    )
    db.add(update)

    matched.last_ingest_at = datetime.utcnow()
    matched.last_ingest_value = new_value

    obj_id = kr.objective_id
    db.commit()
    db.refresh(kr)

    from server.okr_cascade_service import OKRCascadeService

    OKRCascadeService(db).propagate_progress_upward(obj_id)

    record_audit_event(
        org_id=matched.org_id,
        actor_user_id="system:kr-ingest",
        action="KR_INGEST",
        entity_type="KEY_RESULT",
        entity_id=kr.id,
        details={
            "source_system": matched.source_system,
            "source_metric_tag": tag,
            "value": value,
            "transformed_value": new_value,
            "ip_address": ip_address,
        },
    )

    return {
        "status": "ok",
        "key_result_id": kr.id,
        "previous_value": previous,
        "current_value": new_value,
        "source_system": matched.source_system,
    }
