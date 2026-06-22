"""
OKR data integration for performance reviews.
Reuses existing Objective / KeyResult models and hierarchy scope fields.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from server.models import Objective, KeyResult, User


def _kr_progress_pct(kr: KeyResult) -> float:
    if not kr.target_value:
        return 0.0
    return min(100.0, max(0.0, (kr.current_value / kr.target_value) * 100.0))


def get_employee_objectives(db: Session, employee_id: str, org_id: str) -> List[Objective]:
    return (
        db.query(Objective)
        .filter(
            Objective.owner_id == employee_id,
            Objective.org_id == org_id,
            Objective.status.in_(["ACTIVE", "COMPLETED"]),
        )
        .all()
    )


def build_okr_progress_snapshot(db: Session, employee_id: str, org_id: str) -> Dict[str, Any]:
    """Snapshot for check-ins and review context."""
    objectives = get_employee_objectives(db, employee_id, org_id)
    items: List[Dict[str, Any]] = []
    for obj in objectives:
        krs = db.query(KeyResult).filter(KeyResult.objective_id == obj.id).all()
        kr_rows = [
            {
                "kr_id": kr.id,
                "title": kr.title,
                "progress_pct": round(_kr_progress_pct(kr), 1),
                "weight": kr.weight or 1.0,
            }
            for kr in krs
        ]
        if kr_rows:
            weighted = sum(r["progress_pct"] * r["weight"] for r in kr_rows)
            total_w = sum(r["weight"] for r in kr_rows)
            obj_progress = round(weighted / total_w, 1) if total_w else obj.progress
        else:
            obj_progress = obj.progress or 0.0
        items.append(
            {
                "objective_id": obj.id,
                "title": obj.title,
                "level": obj.level,
                "progress": obj_progress,
                "key_results": kr_rows,
            }
        )
    avg_progress = (
        round(sum(i["progress"] for i in items) / len(items), 1) if items else 0.0
    )
    return {
        "objectives": items,
        "objective_count": len(items),
        "avg_progress": avg_progress,
        "okr_ids": [i["objective_id"] for i in items],
    }


def calculate_okr_achievement_score(
    db: Session,
    employee_id: str,
    org_id: str,
    okr_ids: Optional[List[str]] = None,
) -> Tuple[float, List[str]]:
    """
    Weighted average of objective progress (KR-weighted when KRs exist).
    Returns (score 0-100, okr_ids used).
    """
    q = db.query(Objective).filter(
        Objective.owner_id == employee_id,
        Objective.org_id == org_id,
        Objective.status.in_(["ACTIVE", "COMPLETED"]),
    )
    if okr_ids:
        q = q.filter(Objective.id.in_(okr_ids))
    objectives = q.all()
    if not objectives:
        return 50.0, []

    scores: List[float] = []
    ids: List[str] = []
    for obj in objectives:
        krs = db.query(KeyResult).filter(KeyResult.objective_id == obj.id).all()
        if krs:
            weighted = sum(_kr_progress_pct(kr) * (kr.weight or 1.0) for kr in krs)
            total_w = sum(kr.weight or 1.0 for kr in krs)
            scores.append(weighted / total_w if total_w else (obj.progress or 0.0))
        else:
            scores.append(obj.progress or 0.0)
        ids.append(obj.id)

    return round(sum(scores) / len(scores), 1), ids


def attach_okr_context_to_review(db: Session, review) -> None:
    """Populate review.okr_ids and okr_achievement_score from live OKR data."""
    score, okr_ids = calculate_okr_achievement_score(
        db, review.employee_id, review.org_id, review.okr_ids or None
    )
    review.okr_ids = okr_ids
    review.okr_achievement_score = score
    db.commit()
    db.refresh(review)
