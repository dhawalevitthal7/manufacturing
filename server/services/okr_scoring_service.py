"""
OKR Scoring Service
Computes OKR progress, KR progress, and applies scoring logic
All calculations are dynamic (not stored permanently)
"""

from typing import List, Optional, Tuple, Dict
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from server.okr_models import OKR, KeyResult, KRProgressUpdate
from server.okr_utils import (
    calculate_kr_progress,
    calculate_okr_progress_from_krs,
    get_level_weight_factors,
    calculate_parent_okr_score,
    calculate_alignment_contribution
)


class OKRScoringService:
    """
    Service for calculating OKR and KR progress scores.
    All calculations are dynamic - scores are computed on-demand.
    """

    def __init__(self, db: Session):
        self.db = db

    # ========================================================================
    # KEY RESULT SCORING
    # ========================================================================

    def calculate_kr_progress(
        self,
        kr: KeyResult,
        current_date: Optional[datetime] = None
    ) -> float:
        """
        Calculate progress percentage for a Key Result.
        
        Uses is_lower_better flag to determine calculation direction.
        
        Args:
            kr: KeyResult ORM object
            current_date: Optional date for consistent calculations
        
        Returns:
            Progress percentage (0-100)
        """
        return calculate_kr_progress(
            current_value=kr.current_value,
            target_value=kr.target_value,
            is_lower_better=kr.is_lower_better,
            start_value=kr.start_value
        )

    def get_kr_progress_with_update(
        self,
        kr_id: str,
        current_date: Optional[datetime] = None
    ) -> Dict:
        """
        Get KR progress and update timestamp.
        
        Returns:
            {
                'progress': float,
                'last_updated_at': datetime,
                'days_since_update': int or None
            }
        """
        kr = self.db.query(KeyResult).filter_by(id=kr_id).first()
        if not kr:
            return None
        
        progress = self.calculate_kr_progress(kr, current_date)
        days_since = None
        
        if kr.last_updated_at:
            days_since = (datetime.utcnow() - kr.last_updated_at).days
        
        return {
            "progress": progress,
            "last_updated_at": kr.last_updated_at,
            "days_since_update": days_since,
            "current_value": kr.current_value,
            "target_value": kr.target_value
        }

    def batch_calculate_kr_progress(
        self,
        kr_ids: List[str]
    ) -> Dict[str, float]:
        """
        Calculate progress for multiple KRs efficiently.
        
        Args:
            kr_ids: List of KR IDs
        
        Returns:
            Dict mapping kr_id -> progress
        """
        krs = self.db.query(KeyResult).filter(KeyResult.id.in_(kr_ids)).all()
        
        return {
            kr.id: self.calculate_kr_progress(kr)
            for kr in krs
        }

    # ========================================================================
    # OKR SCORING
    # ========================================================================

    def calculate_okr_progress_from_krs_only(
        self,
        okr_id: str
    ) -> float:
        """
        Calculate OKR progress from its own Key Results only (no alignment).
        
        This is the base score before alignment contribution.
        
        Args:
            okr_id: OKR ID
        
        Returns:
            Weighted average progress (0-100)
        """
        kr_query = self.db.query(KeyResult).filter_by(okr_id=okr_id).all()
        
        if not kr_query:
            return 0.0
        
        kr_progresses = [
            (self.calculate_kr_progress(kr), kr.weight)
            for kr in kr_query
        ]
        
        return calculate_okr_progress_from_krs(kr_progresses)

    def calculate_okr_comprehensive_score(
        self,
        okr_id: str,
        include_alignment: bool = True,
        alignment_contribution: Optional[float] = None
    ) -> Dict:
        """
        Calculate comprehensive OKR score including alignment.
        
        Returns computed score without modifying database.
        
        Args:
            okr_id: OKR ID
            include_alignment: Whether to include alignment in calculation
            alignment_contribution: Pre-calculated alignment score (optional)
        
        Returns:
            {
                'okr_id': str,
                'own_kr_score': float,
                'alignment_contribution': float,
                'final_score': float,
                'kr_count': int,
                'calculation_timestamp': datetime
            }
        """
        okr = self.db.query(OKR).filter_by(id=okr_id).first()
        if not okr:
            return None
        
        # Calculate own KR score
        own_kr_score = self.calculate_okr_progress_from_krs_only(okr_id)
        
        # Get weight factors for this level
        own_weight, alignment_weight = get_level_weight_factors(okr.level_type.value)
        
        # Use provided alignment or default to 0
        if not include_alignment:
            alignment_weight = 0.0
            alignment_contribution = 0.0
        elif alignment_contribution is None:
            alignment_contribution = 0.0
        
        # Calculate final score
        final_score = calculate_parent_okr_score(
            own_kr_score=own_kr_score,
            own_weight_factor=own_weight,
            alignment_contribution=alignment_contribution or 0.0,
            alignment_weight_factor=alignment_weight
        )
        
        kr_count = self.db.query(func.count(KeyResult.id)).filter_by(okr_id=okr_id).scalar()
        
        return {
            "okr_id": okr_id,
            "own_kr_score": own_kr_score,
            "alignment_contribution": alignment_contribution or 0.0,
            "final_score": final_score,
            "kr_count": kr_count,
            "own_weight_factor": own_weight,
            "alignment_weight_factor": alignment_weight,
            "calculation_timestamp": datetime.utcnow()
        }

    def get_okr_score_snapshot(
        self,
        okr_id: str
    ) -> Dict:
        """
        Get current snapshot of OKR score (comprehensive).
        
        This includes progress, KR breakdown, and metadata.
        """
        okr = self.db.query(OKR).filter_by(id=okr_id).first()
        if not okr:
            return None
        
        krs = self.db.query(KeyResult).filter_by(okr_id=okr_id).all()
        kr_data = []
        
        for kr in krs:
            progress = self.calculate_kr_progress(kr)
            kr_data.append({
                "id": kr.id,
                "title": kr.title,
                "progress": progress,
                "weight": kr.weight,
                "current_value": kr.current_value,
                "target_value": kr.target_value,
                "unit": kr.unit
            })
        
        own_score = calculate_okr_progress_from_krs([
            (self.calculate_kr_progress(kr), kr.weight) for kr in krs
        ])
        
        return {
            "okr_id": okr_id,
            "objective": okr.objective,
            "owner_id": okr.owner_id,
            "level_type": okr.level_type.value,
            "status": okr.status.value,
            "own_score": own_score,
            "key_results": kr_data,
            "kr_count": len(krs),
            "quarter": okr.quarter,
            "year": okr.year,
            "start_date": okr.start_date,
            "end_date": okr.end_date,
            "last_progress_update": okr.last_progress_update,
            "created_at": okr.created_at
        }

    # ========================================================================
    # BATCH OPERATIONS
    # ========================================================================

    def batch_calculate_okr_scores(
        self,
        okr_ids: List[str],
        include_alignment: bool = False
    ) -> Dict[str, Dict]:
        """
        Calculate scores for multiple OKRs.
        
        Args:
            okr_ids: List of OKR IDs
            include_alignment: Whether to include alignment (requires separate calculation)
        
        Returns:
            Dict mapping okr_id -> score_data
        """
        results = {}
        for okr_id in okr_ids:
            score = self.calculate_okr_comprehensive_score(
                okr_id,
                include_alignment=include_alignment
            )
            if score:
                results[okr_id] = score
        
        return results

    def get_organization_level_scores(
        self,
        org_id: str
    ) -> Dict:
        """
        Get all OKR scores for an entire organization.
        
        Useful for dashboard aggregations.
        """
        okrs = self.db.query(OKR).filter_by(org_id=org_id).all()
        
        scores = {}
        for okr in okrs:
            score = self.calculate_okr_comprehensive_score(okr.id)
            if score:
                scores[okr.id] = score
        
        return scores

    # ========================================================================
    # PROGRESS UPDATE HISTORY
    # ========================================================================

    def get_kr_progress_history(
        self,
        kr_id: str,
        days_back: int = 90
    ) -> List[Dict]:
        """
        Get historical progress updates for a KR.
        
        Args:
            kr_id: Key Result ID
            days_back: How many days of history to retrieve
        
        Returns:
            List of progress updates ordered by date
        """
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        
        updates = self.db.query(KRProgressUpdate).filter(
            KRProgressUpdate.key_result_id == kr_id,
            KRProgressUpdate.update_date >= cutoff_date
        ).order_by(KRProgressUpdate.update_date).all()
        
        return [{
            "id": u.id,
            "current_value": u.current_value,
            "progress_percentage": u.progress_percentage,
            "update_date": u.update_date,
            "notes": u.notes,
            "updated_by_id": u.updated_by_id
        } for u in updates]

    def calculate_kr_velocity(
        self,
        kr_id: str,
        days_back: int = 30
    ) -> Optional[float]:
        """
        Calculate velocity of progress (progress per day).
        
        Args:
            kr_id: Key Result ID
            days_back: Period for calculation
        
        Returns:
            Progress points per day, or None if insufficient data
        """
        from datetime import timedelta
        
        history = self.get_kr_progress_history(kr_id, days_back)
        
        if len(history) < 2:
            return None
        
        first_progress = history[0]["progress_percentage"]
        last_progress = history[-1]["progress_percentage"]
        
        first_date = history[0]["update_date"]
        last_date = history[-1]["update_date"]
        
        days_elapsed = (last_date - first_date).days
        if days_elapsed <= 0:
            return None
        
        velocity = (last_progress - first_progress) / days_elapsed
        return velocity

    # ========================================================================
    # CONSISTENCY CALCULATIONS
    # ========================================================================

    def calculate_update_consistency(
        self,
        okr_id: str,
        days_back: int = 30
    ) -> Dict:
        """
        Calculate consistency of updates for an OKR's KRs.
        
        Returns:
            {
                'avg_days_between_updates': float,
                'update_frequency': 'high'|'medium'|'low',
                'consistency_score': 0-1,
                'last_update_days_ago': int
            }
        """
        from datetime import timedelta
        
        krs = self.db.query(KeyResult).filter_by(okr_id=okr_id).all()
        
        if not krs:
            return {
                "avg_days_between_updates": 0,
                "update_frequency": "low",
                "consistency_score": 0.0,
                "last_update_days_ago": None
            }
        
        all_updates = []
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        
        for kr in krs:
            updates = self.db.query(KRProgressUpdate).filter(
                KRProgressUpdate.key_result_id == kr.id,
                KRProgressUpdate.update_date >= cutoff_date
            ).order_by(KRProgressUpdate.update_date).all()
            all_updates.extend(updates)
        
        if not all_updates:
            return {
                "avg_days_between_updates": float('inf'),
                "update_frequency": "low",
                "consistency_score": 0.0,
                "last_update_days_ago": None
            }
        
        # Calculate days between updates
        dates = sorted([u.update_date for u in all_updates])
        if len(dates) < 2:
            days_between = float('inf')
        else:
            deltas = [(dates[i] - dates[i-1]).days for i in range(1, len(dates))]
            days_between = sum(deltas) / len(deltas) if deltas else float('inf')
        
        # Determine frequency
        if days_between <= 3:
            frequency = "high"
            consistency = 0.9
        elif days_between <= 7:
            frequency = "medium"
            consistency = 0.7
        else:
            frequency = "low"
            consistency = 0.3
        
        last_update = dates[-1] if dates else None
        days_ago = (datetime.utcnow() - last_update).days if last_update else None
        
        return {
            "avg_days_between_updates": days_between,
            "update_frequency": frequency,
            "consistency_score": consistency,
            "last_update_days_ago": days_ago
        }

    # ========================================================================
    # PERFORMANCE METRICS
    # ========================================================================

    def get_performance_metrics_for_owner(
        self,
        owner_id: str,
        level_type: Optional[str] = None
    ) -> Dict:
        """
        Get aggregated performance metrics for a user.
        
        Args:
            owner_id: User ID
            level_type: Optional filter by level
        
        Returns:
            {
                'total_okrs': int,
                'avg_progress': float,
                'okrs_on_track': int,
                'okrs_at_risk': int,
                'okrs_blocked': int
            }
        """
        query = self.db.query(OKR).filter_by(owner_id=owner_id)
        
        if level_type:
            query = query.filter_by(level_type=level_type)
        
        okrs = query.all()
        
        if not okrs:
            return {
                "total_okrs": 0,
                "avg_progress": 0.0,
                "okrs_on_track": 0,
                "okrs_at_risk": 0,
                "okrs_blocked": 0
            }
        
        scores = []
        on_track = 0
        at_risk = 0
        blocked = 0
        
        for okr in okrs:
            score = self.calculate_okr_comprehensive_score(okr.id)
            if score:
                scores.append(score["final_score"])
                
                # Simple categorization
                if score["final_score"] >= 75:
                    on_track += 1
                elif score["final_score"] >= 40:
                    at_risk += 1
                else:
                    blocked += 1
        
        avg_progress = sum(scores) / len(scores) if scores else 0.0
        
        return {
            "total_okrs": len(okrs),
            "avg_progress": avg_progress,
            "okrs_on_track": on_track,
            "okrs_at_risk": at_risk,
            "okrs_blocked": blocked
        }
