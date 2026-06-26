"""Version history for AI cascade OKR edits."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from server.models import KeyResult, Objective, ObjectiveVersion


def _kr_snapshot(krs: List[KeyResult]) -> str:
    payload = [
        {
            "title": kr.title,
            "target_value": kr.target_value,
            "current_value": kr.current_value,
            "unit": kr.unit,
            "weight": kr.weight,
        }
        for kr in krs
    ]
    return json.dumps(payload)


def record_objective_version(
    db: Session,
    *,
    okr: Objective,
    change_type: str,
    changed_by_id: Optional[str] = None,
) -> ObjectiveVersion:
    krs = db.query(KeyResult).filter(KeyResult.objective_id == okr.id).all()
    version = ObjectiveVersion(
        id=str(uuid.uuid4()),
        objective_id=okr.id,
        org_id=okr.org_id,
        version=okr.ai_generation_version or 1,
        change_type=change_type,
        title=okr.title,
        description=okr.description,
        key_results_snapshot=_kr_snapshot(krs),
        ai_metadata_snapshot=okr.ai_metadata,
        changed_by_id=changed_by_id,
    )
    db.add(version)
    db.flush()
    return version


def versions_to_dicts(versions: List[ObjectiveVersion]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for v in versions:
        krs: List[Dict[str, Any]] = []
        if v.key_results_snapshot:
            try:
                krs = json.loads(v.key_results_snapshot)
            except json.JSONDecodeError:
                krs = []
        meta: Dict[str, Any] = {}
        if v.ai_metadata_snapshot:
            try:
                meta = json.loads(v.ai_metadata_snapshot)
            except json.JSONDecodeError:
                meta = {}
        result.append(
            {
                "id": v.id,
                "objective_id": v.objective_id,
                "version": v.version,
                "change_type": v.change_type,
                "title": v.title,
                "description": v.description,
                "key_results": krs,
                "ai_metadata": meta,
                "changed_by_id": v.changed_by_id,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
        )
    return result


def build_alignment_preview(
    db: Session, *, child: Objective, parent: Objective
) -> Dict[str, Any]:
    child_krs = db.query(KeyResult).filter(KeyResult.objective_id == child.id).all()
    parent_krs = db.query(KeyResult).filter(KeyResult.objective_id == parent.id).all()
    meta: Dict[str, Any] = {}
    if child.ai_metadata:
        try:
            meta = json.loads(child.ai_metadata)
        except json.JSONDecodeError:
            meta = {}

    return {
        "child_id": child.id,
        "child_title": child.title,
        "child_description": child.description,
        "child_level": child.level,
        "parent_id": parent.id,
        "parent_title": parent.title,
        "parent_description": parent.description,
        "parent_level": parent.level,
        "alignment_score": meta.get("alignment_score") or child.ai_confidence,
        "confidence": child.ai_confidence,
        "reasoning": child.ai_generation_reason or meta.get("reasoning"),
        "child_key_results": [
            {"title": kr.title, "target_value": kr.target_value, "unit": kr.unit}
            for kr in child_krs
        ],
        "parent_key_results": [
            {"title": kr.title, "target_value": kr.target_value, "unit": kr.unit}
            for kr in parent_krs
        ],
    }


def build_diff_view(
    db: Session, *, current: Objective, previous_version: ObjectiveVersion
) -> Dict[str, Any]:
    current_krs = db.query(KeyResult).filter(KeyResult.objective_id == current.id).all()
    prev_krs: List[Dict[str, Any]] = []
    if previous_version.key_results_snapshot:
        try:
            prev_krs = json.loads(previous_version.key_results_snapshot)
        except json.JSONDecodeError:
            prev_krs = []

    return {
        "current": {
            "title": current.title,
            "description": current.description,
            "version": current.ai_generation_version,
            "key_results": [
                {"title": kr.title, "target_value": kr.target_value, "unit": kr.unit}
                for kr in current_krs
            ],
        },
        "previous": {
            "title": previous_version.title,
            "description": previous_version.description,
            "version": previous_version.version,
            "key_results": prev_krs,
        },
        "title_changed": current.title != previous_version.title,
        "description_changed": current.description != previous_version.description,
    }
