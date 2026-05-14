"""
OKR Cascade and Progress Propagation Service
==============================================

Adapted from the reference project's cascade service for the manufacturing
hierarchy:  Organization → Plant → Department → Team → Individual

Design Principles:
1. **Explicit Linking**: Each OKR knows its parent via parent_id
2. **Weight-Based Aggregation**: Progress is weighted at each level
3. **Cascade Rules**: Progress cascades upward when manager approves
4. **Plant-wise scoping**: All data is plant-aware
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from server.models import (
    Objective,
    KeyResult,
    ProgressUpdate,
    User,
    Team,
    Department,
    Plant,
)
from server.roles import can_create_objective_at_level, normalize_role


# ── Scoring Helpers ──────────────────────────────────────────────────────────

WEIGHT_MIN = 1.0
WEIGHT_MAX = 5.0


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp_weight(value: Any, default: float = 1.0) -> float:
    weight = _to_float(value, default)
    return round(min(WEIGHT_MAX, max(WEIGHT_MIN, weight)), 2)


def score_to_rating(score: float) -> str:
    """Map a 0-100 score to a performance band."""
    if score >= 90:
        return "Exceptional"
    if score >= 75:
        return "On Track"
    if score >= 60:
        return "At Risk"
    return "Off Track"


def weighted_average(items: List[Tuple[float, float]]) -> float:
    total_weight = 0.0
    weighted_score = 0.0
    for score, weight in items:
        safe_weight = max(_to_float(weight, 0.0), 0.0)
        if safe_weight <= 0:
            continue
        weighted_score += _to_float(score, 0.0) * safe_weight
        total_weight += safe_weight
    if total_weight <= 0:
        return 0.0
    return round(weighted_score / total_weight, 1)


def calculate_kr_progress(kr: KeyResult) -> float:
    """Return a normalized 0-100 progress score for a key result."""
    target = _to_float(kr.target_value, 0.0)
    current = _to_float(kr.current_value, 0.0)
    if target <= 0:
        return 0.0
    progress = (current / target) * 100.0
    return round(min(100.0, max(0.0, progress)), 1)


def calculate_objective_progress(krs: List[KeyResult]) -> Dict[str, Any]:
    """Compute weighted progress for a key-result collection."""
    if not krs:
        return {
            "progress": 0.0,
            "rating": "Off Track",
            "total_key_results": 0,
            "completed_key_results": 0,
        }

    weighted_pairs: List[Tuple[float, float]] = []
    completed = 0
    total = 0

    for kr in krs:
        total += 1
        progress = calculate_kr_progress(kr)
        weight = clamp_weight(kr.weight, 1.0)
        weighted_pairs.append((progress, weight))
        if progress >= 100.0:
            completed += 1

    wp = weighted_average(weighted_pairs)
    return {
        "progress": round(wp, 1),
        "rating": score_to_rating(wp),
        "total_key_results": total,
        "completed_key_results": completed,
    }


# ── Cascade Service ──────────────────────────────────────────────────────────

class OKRCascadeService:
    """Manages OKR hierarchy, linking, and progress propagation."""

    def __init__(self, db: Session):
        self.db = db

    # ── Role-based creation rules (delegate to server.roles) ─────────────────

    def can_create_at_level(self, role: str, level: str) -> bool:
        """Whether ``role`` may create an OKR at ``level`` (canonical policy)."""
        return can_create_objective_at_level(
            normalize_role(role), (level or "").strip().upper()
        )

    # ── Cascade Progress Calculation ─────────────────────────────────────

    def calculate_level_progress(
        self, level: str, scope_id: Optional[str] = None
    ) -> float:
        """
        Calculate aggregated progress for all OKRs at a given level,
        optionally scoped to a specific plant/department/team.
        """
        q = self.db.query(Objective).filter(Objective.level == level)
        if scope_id:
            if level == "PLANT":
                q = q.filter(Objective.plant_id == scope_id)
            elif level == "DEPARTMENT":
                q = q.filter(Objective.department_id == scope_id)
            elif level == "TEAM":
                q = q.filter(Objective.team_id == scope_id)
        objs = q.all()
        if not objs:
            return 0.0

        scores: List[Tuple[float, float]] = []
        for obj in objs:
            krs = (
                self.db.query(KeyResult)
                .filter(KeyResult.objective_id == obj.id)
                .all()
            )
            result = calculate_objective_progress(krs)
            if result["total_key_results"] > 0:
                scores.append((result["progress"], 1.0))

        return weighted_average(scores) if scores else 0.0

    def recalc_objective_progress(self, obj_id: str) -> float:
        """Recalculate a single objective's progress from its key results."""
        obj = self.db.query(Objective).filter(Objective.id == obj_id).first()
        if not obj:
            return 0.0
        krs = (
            self.db.query(KeyResult)
            .filter(KeyResult.objective_id == obj_id)
            .all()
        )
        result = calculate_objective_progress(krs)
        obj.progress = result["progress"]
        obj.status = "COMPLETED" if result["progress"] >= 100 else "ACTIVE"
        self.db.commit()
        return result["progress"]

    def propagate_progress_upward(self, obj_id: str) -> Dict[str, Any]:
        """
        When an objective's progress changes, cascade it upward through
        the parent chain:
            Individual → Team → Department → Plant → Organization

        Returns cascade summary.
        """
        obj = self.db.query(Objective).filter(Objective.id == obj_id).first()
        if not obj:
            return {"success": False, "message": "Objective not found"}

        propagated = []
        warnings = []

        # Recalc this objective first
        self.recalc_objective_progress(obj_id)
        propagated.append({
            "id": obj.id,
            "level": obj.level,
            "progress": obj.progress,
        })

        # Walk up the parent chain
        current = obj
        visited = {obj.id}
        while current.parent_id and current.parent_id not in visited:
            parent = (
                self.db.query(Objective)
                .filter(Objective.id == current.parent_id)
                .first()
            )
            if not parent:
                warnings.append(f"Parent {current.parent_id} not found")
                break

            visited.add(parent.id)

            # Recalculate parent from ALL its children + own KRs
            children = (
                self.db.query(Objective)
                .filter(Objective.parent_id == parent.id)
                .all()
            )

            # Collect child progress scores
            child_scores: List[Tuple[float, float]] = []
            for child in children:
                if child.progress is not None:
                    child_scores.append((child.progress, 1.0))

            # Also include parent's own KR progress if any
            parent_krs = (
                self.db.query(KeyResult)
                .filter(KeyResult.objective_id == parent.id)
                .all()
            )
            if parent_krs:
                kr_result = calculate_objective_progress(parent_krs)
                if kr_result["total_key_results"] > 0:
                    # Parent's own KRs contribute 50%, children contribute 50%
                    own_progress = kr_result["progress"]
                    children_progress = (
                        weighted_average(child_scores) if child_scores else 0.0
                    )
                    if child_scores:
                        parent.progress = round(
                            (own_progress * 0.5 + children_progress * 0.5), 1
                        )
                    else:
                        parent.progress = own_progress
                else:
                    parent.progress = (
                        weighted_average(child_scores) if child_scores else 0.0
                    )
            else:
                parent.progress = (
                    weighted_average(child_scores) if child_scores else 0.0
                )

            parent.status = "COMPLETED" if parent.progress >= 100 else "ACTIVE"
            self.db.commit()

            propagated.append({
                "id": parent.id,
                "level": parent.level,
                "progress": parent.progress,
            })

            current = parent

        return {
            "success": True,
            "propagated": propagated,
            "warnings": warnings,
        }

    def get_cascade_tree(
        self, org_id: str, plant_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Build the full OKR cascade tree for visualization.
        Returns nested structure: Org → Plant → Dept → Team → Individual
        """
        q = self.db.query(Objective).filter(Objective.org_id == org_id)
        if plant_id:
            # Include org-level (no plant) + plant-scoped
            from sqlalchemy import or_
            q = q.filter(
                or_(
                    Objective.plant_id == plant_id,
                    Objective.level == "ORGANIZATION",
                )
            )
        objs = q.all()

        # Build map
        obj_map = {}
        for o in objs:
            krs = (
                self.db.query(KeyResult)
                .filter(KeyResult.objective_id == o.id)
                .all()
            )
            owner = self.db.query(User).filter(User.id == o.owner_id).first()
            obj_map[o.id] = {
                "id": o.id,
                "title": o.title,
                "description": o.description,
                "level": o.level,
                "status": o.status,
                "progress": o.progress or 0,
                "rating": score_to_rating(o.progress or 0),
                "owner_id": o.owner_id,
                "owner_name": owner.name if owner else None,
                "parent_id": o.parent_id,
                "plant_id": o.plant_id,
                "department_id": o.department_id,
                "team_id": o.team_id,
                "key_results_count": len(krs),
                "children": [],
            }

        # Build tree
        roots = []
        for o in objs:
            node = obj_map[o.id]
            if o.parent_id and o.parent_id in obj_map:
                obj_map[o.parent_id]["children"].append(node)
            else:
                roots.append(node)

        return roots

    def get_progress_summary(
        self, org_id: str, plant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get aggregate progress summary by level for dashboard display.
        """
        levels = ["ORGANIZATION", "PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"]
        summary = {}

        for level in levels:
            q = self.db.query(Objective).filter(
                Objective.org_id == org_id,
                Objective.level == level,
            )
            if plant_id and level != "ORGANIZATION":
                q = q.filter(Objective.plant_id == plant_id)

            objs = q.all()
            on_track = sum(1 for o in objs if (o.progress or 0) >= 75)
            at_risk = sum(
                1 for o in objs if 60 <= (o.progress or 0) < 75
            )
            off_track = sum(1 for o in objs if (o.progress or 0) < 60)
            avg_progress = (
                round(sum(o.progress or 0 for o in objs) / len(objs), 1)
                if objs
                else 0
            )

            summary[level] = {
                "total": len(objs),
                "on_track": on_track,
                "at_risk": at_risk,
                "off_track": off_track,
                "avg_progress": avg_progress,
            }

        return summary
