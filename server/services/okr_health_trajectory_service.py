"""
OKR Health, Trajectory, and Confidence Analysis Services
Computes health status, trend trajectories, risk levels, and confidence scores
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from server.okr_models import OKR, KeyResult, KRProgressUpdate, HealthStatus as HealthStatusEnum, RiskLevel as RiskLevelEnum, TrendStatus as TrendStatusEnum
from server.okr_utils import (
    calculate_trajectory_score,
    determine_trend_status,
    calculate_health_status,
    calculate_risk_level,
    calculate_confidence_score,
    calculate_update_freshness_days,
    calculate_historical_consistency,
    calculate_expected_progress
)


class OKRHealthService:
    """
    Service for calculating OKR health status.
    
    Health status is derived from:
    - Progress percentage
    - Update freshness
    - Trajectory
    - Confidence score
    """

    def __init__(self, db: Session, scoring_service: 'OKRScoringService'):
        self.db = db
        self.scoring_service = scoring_service

    def calculate_okr_health(
        self,
        okr_id: str
    ) -> Dict:
        """
        Calculate comprehensive health status for an OKR.
        
        Returns:
            {
                'health_status': 'healthy'|'needs_attention'|'critical'|'blocked',
                'risk_level': 'low'|'medium'|'high'|'critical',
                'progress': float,
                'days_since_update': int,
                'trajectory_score': float,
                'confidence_score': float,
                'calculation_timestamp': datetime
            }
        """
        okr = self.db.query(OKR).filter_by(id=okr_id).first()
        if not okr:
            return None
        
        # Get current progress
        progress = self.scoring_service.calculate_okr_progress_from_krs_only(okr_id)
        
        # Get update freshness
        days_since_update = calculate_update_freshness_days(okr.last_progress_update)
        
        # Get trajectory
        expected_progress = calculate_expected_progress(okr.start_date, okr.end_date)
        trajectory_score = calculate_trajectory_score(progress, expected_progress)
        
        # Get confidence
        confidence = self.calculate_okr_confidence_score(okr_id)
        
        # Calculate days until deadline
        days_until_deadline = (okr.end_date - datetime.utcnow()).days
        
        # Determine health status
        health_status = calculate_health_status(
            progress=progress,
            days_since_update=days_since_update,
            trajectory_score=trajectory_score,
            confidence_score=confidence,
            days_until_deadline=days_until_deadline
        )
        
        # Determine risk level
        risk_level = calculate_risk_level(
            health_status=health_status,
            confidence_score=confidence,
            trajectory_score=trajectory_score,
            progress=progress,
            days_until_deadline=days_until_deadline
        )
        
        return {
            "okr_id": okr_id,
            "health_status": health_status.value,
            "risk_level": risk_level.value,
            "progress": progress,
            "expected_progress": expected_progress,
            "days_since_update": days_since_update,
            "trajectory_score": trajectory_score,
            "confidence_score": confidence,
            "days_until_deadline": days_until_deadline,
            "calculation_timestamp": datetime.utcnow()
        }

    def batch_calculate_health(
        self,
        okr_ids: List[str]
    ) -> Dict[str, Dict]:
        """
        Calculate health for multiple OKRs.
        
        Returns:
            Dict mapping okr_id -> health_data
        """
        results = {}
        for okr_id in okr_ids:
            health = self.calculate_okr_health(okr_id)
            if health:
                results[okr_id] = health
        
        return results

    def get_okrs_by_health_status(
        self,
        org_id: str,
        health_status: str
    ) -> List[Dict]:
        """
        Get all OKRs in a specific health status.
        
        Args:
            org_id: Organization ID
            health_status: 'healthy'|'needs_attention'|'critical'|'blocked'
        
        Returns:
            List of OKRs with their health data
        """
        okrs = self.db.query(OKR).filter_by(org_id=org_id).all()
        
        results = []
        for okr in okrs:
            health = self.calculate_okr_health(okr.id)
            if health and health["health_status"] == health_status:
                results.append(health)
        
        return results

    def get_health_summary(
        self,
        org_id: str
    ) -> Dict:
        """
        Get health summary for entire organization.
        
        Returns:
            {
                'total_okrs': int,
                'healthy': int,
                'needs_attention': int,
                'critical': int,
                'blocked': int,
                'avg_progress': float,
                'avg_confidence': float
            }
        """
        okrs = self.db.query(OKR).filter_by(org_id=org_id).all()
        
        if not okrs:
            return {
                "total_okrs": 0,
                "healthy": 0,
                "needs_attention": 0,
                "critical": 0,
                "blocked": 0,
                "avg_progress": 0.0,
                "avg_confidence": 0.0
            }
        
        healths = []
        progresses = []
        confidences = []
        
        counts = {"healthy": 0, "needs_attention": 0, "critical": 0, "blocked": 0}
        
        for okr in okrs:
            health = self.calculate_okr_health(okr.id)
            if health:
                healths.append(health)
                progresses.append(health["progress"])
                confidences.append(health["confidence_score"])
                counts[health["health_status"]] += 1
        
        avg_progress = sum(progresses) / len(progresses) if progresses else 0.0
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        return {
            "total_okrs": len(okrs),
            "healthy": counts["healthy"],
            "needs_attention": counts["needs_attention"],
            "critical": counts["critical"],
            "blocked": counts["blocked"],
            "avg_progress": avg_progress,
            "avg_confidence": avg_confidence
        }


class OKRTrajectoryService:
    """
    Service for analyzing OKR trajectory and trend analysis.
    
    Computes expected progress, velocity, and trend status.
    """

    def __init__(self, db: Session, scoring_service: 'OKRScoringService'):
        self.db = db
        self.scoring_service = scoring_service

    def calculate_trajectory(
        self,
        okr_id: str
    ) -> Dict:
        """
        Calculate trajectory analysis for an OKR.
        
        Returns:
            {
                'current_progress': float,
                'expected_progress': float,
                'trajectory_score': float,
                'trend_status': str,
                'velocity': float (progress per day),
                'projected_completion_date': datetime,
                'days_until_deadline': int
            }
        """
        okr = self.db.query(OKR).filter_by(id=okr_id).first()
        if not okr:
            return None
        
        # Get current progress
        current_progress = self.scoring_service.calculate_okr_progress_from_krs_only(okr_id)
        
        # Get expected progress
        expected_progress = calculate_expected_progress(okr.start_date, okr.end_date)
        
        # Calculate trajectory score
        trajectory_score = calculate_trajectory_score(current_progress, expected_progress)
        
        # Get velocity
        velocity = self._calculate_okr_velocity(okr_id)
        
        # Project completion
        projected_date = self._project_completion_date(okr_id, okr.end_date)
        
        # Determine trend
        days_until = (okr.end_date - datetime.utcnow()).days
        trend = determine_trend_status(trajectory_score, current_progress, days_until)
        
        return {
            "okr_id": okr_id,
            "current_progress": current_progress,
            "expected_progress": expected_progress,
            "trajectory_score": trajectory_score,
            "trend_status": trend.value,
            "velocity": velocity,
            "projected_completion_date": projected_date,
            "days_until_deadline": days_until,
            "is_ahead": trajectory_score > 110,
            "is_on_track": 90 <= trajectory_score <= 110,
            "is_behind": trajectory_score < 90
        }

    def _calculate_okr_velocity(
        self,
        okr_id: str,
        days_back: int = 30
    ) -> Optional[float]:
        """
        Calculate velocity (progress per day) for an OKR.
        
        Average of all KR velocities.
        """
        krs = self.db.query(KeyResult).filter_by(okr_id=okr_id).all()
        
        velocities = []
        for kr in krs:
            velocity = self.scoring_service.calculate_kr_velocity(kr.id, days_back)
            if velocity is not None:
                velocities.append(velocity)
        
        if not velocities:
            return None
        
        return sum(velocities) / len(velocities)

    def _project_completion_date(
        self,
        okr_id: str,
        deadline: datetime
    ) -> Optional[datetime]:
        """
        Project when OKR will be 100% complete based on velocity.
        """
        velocity = self._calculate_okr_velocity(okr_id)
        if not velocity or velocity <= 0:
            return None
        
        current_progress = self.scoring_service.calculate_okr_progress_from_krs_only(okr_id)
        remaining_progress = 100.0 - current_progress
        
        days_remaining = remaining_progress / velocity
        projected = datetime.utcnow() + timedelta(days=days_remaining)
        
        return projected

    def get_trajectory_for_region(
        self,
        region_id: str
    ) -> List[Dict]:
        """
        Get trajectory for all OKRs in a region.
        """
        okrs = self.db.query(OKR).filter_by(region_id=region_id).all()
        
        trajectories = []
        for okr in okrs:
            traj = self.calculate_trajectory(okr.id)
            if traj:
                trajectories.append(traj)
        
        return trajectories

    def get_at_risk_okrs(
        self,
        org_id: str,
        trajectory_threshold: float = 70
    ) -> List[Dict]:
        """
        Get OKRs that are at risk (trajectory < threshold).
        """
        okrs = self.db.query(OKR).filter_by(org_id=org_id).all()
        
        at_risk = []
        for okr in okrs:
            traj = self.calculate_trajectory(okr.id)
            if traj and traj["trajectory_score"] < trajectory_threshold:
                at_risk.append(traj)
        
        return sorted(at_risk, key=lambda x: x["trajectory_score"])


class OKRConfidenceService:
    """
    Service for calculating OKR confidence scores.
    
    Confidence is based on:
    - Update frequency and freshness
    - Historical consistency
    - KR count and diversity
    - Completion velocity
    """

    def __init__(self, db: Session, scoring_service: 'OKRScoringService'):
        self.db = db
        self.scoring_service = scoring_service

    def calculate_okr_confidence_score(
        self,
        okr_id: str
    ) -> float:
        """
        Calculate confidence score for an OKR.
        
        Returns:
            Confidence score 0-100
        """
        # Get update freshness
        okr = self.db.query(OKR).filter_by(id=okr_id).first()
        if not okr:
            return 0.0
        
        days_since_update = calculate_update_freshness_days(okr.last_progress_update)
        
        # Get historical consistency from KRs
        consistency = self.scoring_service.calculate_update_consistency(okr_id)
        consistency_score = consistency.get("consistency_score", 0.5)
        
        # Get KR count
        kr_count = self.db.query(func.count(KeyResult.id)).filter_by(
            okr_id=okr_id
        ).scalar()
        
        # Get velocity
        velocity = self._calculate_okr_velocity(okr_id)
        
        # Calculate confidence
        confidence = calculate_confidence_score(
            update_frequency_days=days_since_update,
            historical_consistency=consistency_score,
            kr_count=kr_count or 0,
            completion_velocity=velocity or 0.0
        )
        
        return confidence

    def _calculate_okr_velocity(
        self,
        okr_id: str,
        days_back: int = 30
    ) -> Optional[float]:
        """Calculate OKR velocity"""
        krs = self.db.query(KeyResult).filter_by(okr_id=okr_id).all()
        
        velocities = []
        for kr in krs:
            velocity = self.scoring_service.calculate_kr_velocity(kr.id, days_back)
            if velocity is not None:
                velocities.append(velocity)
        
        if not velocities:
            return None
        
        return sum(velocities) / len(velocities)

    def batch_calculate_confidence(
        self,
        okr_ids: List[str]
    ) -> Dict[str, float]:
        """
        Calculate confidence for multiple OKRs.
        
        Returns:
            Dict mapping okr_id -> confidence_score
        """
        return {
            okr_id: self.calculate_okr_confidence_score(okr_id)
            for okr_id in okr_ids
        }

    def get_low_confidence_okrs(
        self,
        org_id: str,
        threshold: float = 40.0
    ) -> List[Dict]:
        """
        Get OKRs with low confidence scores.
        """
        okrs = self.db.query(OKR).filter_by(org_id=org_id).all()
        
        low_confidence = []
        for okr in okrs:
            confidence = self.calculate_okr_confidence_score(okr.id)
            if confidence < threshold:
                low_confidence.append({
                    "okr_id": okr.id,
                    "objective": okr.objective,
                    "owner_id": okr.owner_id,
                    "confidence_score": confidence,
                    "reason": self._get_low_confidence_reason(okr.id)
                })
        
        return sorted(low_confidence, key=lambda x: x["confidence_score"])

    def _get_low_confidence_reason(
        self,
        okr_id: str
    ) -> str:
        """Determine why confidence is low"""
        consistency = self.scoring_service.calculate_update_consistency(okr_id)
        
        if consistency["update_frequency"] == "low":
            return "Low update frequency"
        elif consistency["consistency_score"] < 0.3:
            return "Inconsistent progress tracking"
        else:
            return "Insufficient data"
