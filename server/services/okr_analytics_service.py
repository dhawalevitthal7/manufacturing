"""
OKR Analytics Service
Provides comprehensive analytics, reporting, and dashboard data
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from server.okr_models import OKR, KeyResult, OKRAlignment, OKRLevelType


class OKRAnalyticsService:
    """
    Service for OKR analytics, reporting, and dashboards.
    
    Compiles data from scoring, alignment, health, and trajectory services
    into actionable insights for different user roles.
    """

    def __init__(
        self,
        db: Session,
        scoring_service: 'OKRScoringService',
        alignment_service: 'OKRAlignmentService',
        health_service: 'OKRHealthService',
        trajectory_service: 'OKRTrajectoryService',
        confidence_service: 'OKRConfidenceService'
    ):
        self.db = db
        self.scoring_service = scoring_service
        self.alignment_service = alignment_service
        self.health_service = health_service
        self.trajectory_service = trajectory_service
        self.confidence_service = confidence_service

    # ========================================================================
    # AGGREGATED METRICS
    # ========================================================================

    def get_organization_metrics(
        self,
        org_id: str
    ) -> Dict:
        """
        Get aggregated metrics for entire organization.
        
        Returns:
            {
                'total_okrs': int,
                'total_key_results': int,
                'avg_progress': float,
                'okrs_on_track': int,
                'okrs_at_risk': int,
                'okrs_blocked': int,
                'health_breakdown': {...},
                'avg_confidence': float,
                'quarters_tracked': [...],
                'top_performers': [...],
                'at_risk_count': int
            }
        """
        # Count totals
        total_okrs = self.db.query(func.count(OKR.id)).filter_by(
            org_id=org_id
        ).scalar()
        
        total_krs = self.db.query(func.count(KeyResult.id)).join(
            OKR
        ).filter(OKR.org_id == org_id).scalar()
        
        # Get all OKRs for detailed analysis
        okrs = self.db.query(OKR).filter_by(org_id=org_id).all()
        
        progresses = []
        confidences = []
        health_counts = {
            "healthy": 0,
            "needs_attention": 0,
            "critical": 0,
            "blocked": 0
        }
        
        on_track = 0
        at_risk = 0
        blocked = 0
        
        for okr in okrs:
            score = self.scoring_service.calculate_okr_comprehensive_score(okr.id)
            if score:
                progresses.append(score["final_score"])
            
            health = self.health_service.calculate_okr_health(okr.id)
            if health:
                confidences.append(health["confidence_score"])
                health_counts[health["health_status"]] += 1
                
                if health["progress"] >= 75:
                    on_track += 1
                elif health["progress"] >= 40:
                    at_risk += 1
                else:
                    blocked += 1
        
        avg_progress = sum(progresses) / len(progresses) if progresses else 0.0
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # Get unique quarters
        quarters = self.db.query(
            OKR.quarter,
            OKR.year
        ).filter_by(org_id=org_id).distinct().all()
        
        quarters_tracked = sorted([
            f"Q{q[0]} {q[1]}" for q in quarters
        ])
        
        return {
            "total_okrs": total_okrs or 0,
            "total_key_results": total_krs or 0,
            "avg_progress": avg_progress,
            "okrs_on_track": on_track,
            "okrs_at_risk": at_risk,
            "okrs_blocked": blocked,
            "health_breakdown": health_counts,
            "avg_confidence": avg_confidence,
            "quarters_tracked": quarters_tracked,
            "calculation_timestamp": datetime.utcnow()
        }

    def get_level_metrics(
        self,
        org_id: str,
        level_type: str
    ) -> Dict:
        """
        Get metrics for a specific OKR level.
        
        Args:
            org_id: Organization ID
            level_type: 'organization'|'region'|'plant'|'department'|'team'|'employee'
        """
        okrs = self.db.query(OKR).filter(
            OKR.org_id == org_id,
            OKR.level_type == level_type
        ).all()
        
        if not okrs:
            return {"count": 0, "avg_progress": 0.0, "details": []}
        
        level_data = []
        progresses = []
        
        for okr in okrs:
            score = self.scoring_service.calculate_okr_comprehensive_score(okr.id)
            health = self.health_service.calculate_okr_health(okr.id)
            
            if score and health:
                progresses.append(score["final_score"])
                level_data.append({
                    "okr_id": okr.id,
                    "objective": okr.objective,
                    "owner_id": okr.owner_id,
                    "progress": score["final_score"],
                    "health": health["health_status"],
                    "risk": health["risk_level"]
                })
        
        avg_progress = sum(progresses) / len(progresses) if progresses else 0.0
        
        return {
            "level": level_type,
            "count": len(okrs),
            "avg_progress": avg_progress,
            "details": sorted(level_data, key=lambda x: x["progress"], reverse=True)
        }

    # ========================================================================
    # ROLE-BASED DASHBOARDS
    # ========================================================================

    def get_ceo_dashboard(
        self,
        org_id: str
    ) -> Dict:
        """
        Get CEO-level dashboard.
        
        Shows:
        - Organization-wide metrics
        - Regional performance
        - At-risk OKRs
        - Top contributors
        """
        metrics = self.get_organization_metrics(org_id)
        
        # Get regional performance
        regions = self.db.query(OKR).filter(
            OKR.org_id == org_id,
            OKR.level_type == OKRLevelType.REGION
        ).all()
        
        regional_data = []
        for region_okr in regions:
            score = self.scoring_service.calculate_okr_comprehensive_score(region_okr.id)
            health = self.health_service.calculate_okr_health(region_okr.id)
            
            if score and health:
                regional_data.append({
                    "region_okr_id": region_okr.id,
                    "owner_id": region_okr.owner_id,
                    "progress": score["final_score"],
                    "health": health["health_status"],
                    "trajectory": health["trajectory_score"]
                })
        
        # At-risk OKRs
        at_risk = self.trajectory_service.get_at_risk_okrs(org_id)[:10]
        
        return {
            "organization_metrics": metrics,
            "regional_performance": regional_data,
            "at_risk_okrs": at_risk,
            "dashboard_type": "CEO",
            "generated_at": datetime.utcnow()
        }

    def get_region_head_dashboard(
        self,
        owner_id: str,
        org_id: str
    ) -> Dict:
        """
        Get Region Head dashboard.
        """
        # Get region OKRs for this owner
        region_okrs = self.db.query(OKR).filter(
            OKR.owner_id == owner_id,
            OKR.level_type == OKRLevelType.REGION
        ).all()
        
        # Get plants in this region
        plant_okrs = self.db.query(OKR).filter(
            OKR.region_id == region_okrs[0].id if region_okrs else None,
            OKR.level_type == OKRLevelType.PLANT
        ).all() if region_okrs else []
        
        region_data = []
        for okr in region_okrs:
            score = self.scoring_service.calculate_okr_comprehensive_score(okr.id)
            health = self.health_service.calculate_okr_health(okr.id)
            
            if score and health:
                region_data.append({
                    "okr_id": okr.id,
                    "progress": score["final_score"],
                    "health": health["health_status"],
                    "key_results": len(okr.key_results)
                })
        
        plant_performance = []
        for plant_okr in plant_okrs:
            score = self.scoring_service.calculate_okr_comprehensive_score(plant_okr.id)
            if score:
                plant_performance.append({
                    "plant_id": plant_okr.id,
                    "owner_id": plant_okr.owner_id,
                    "progress": score["final_score"]
                })
        
        return {
            "region_okrs": region_data,
            "plant_performance": plant_performance,
            "dashboard_type": "REGION_HEAD",
            "generated_at": datetime.utcnow()
        }

    def get_plant_head_dashboard(
        self,
        owner_id: str
    ) -> Dict:
        """
        Get Plant Head dashboard.
        """
        plant_okrs = self.db.query(OKR).filter_by(
            owner_id=owner_id,
            level_type=OKRLevelType.PLANT
        ).all()
        
        plant_data = []
        critical_krs = []
        
        for okr in plant_okrs:
            score = self.scoring_service.calculate_okr_comprehensive_score(okr.id)
            health = self.health_service.calculate_okr_health(okr.id)
            
            if score and health:
                plant_data.append({
                    "okr_id": okr.id,
                    "objective": okr.objective,
                    "progress": score["final_score"],
                    "health": health["health_status"],
                    "kr_count": len(okr.key_results)
                })
            
            # Collect critical KRs
            for kr in okr.key_results:
                progress = self.scoring_service.calculate_kr_progress(kr)
                if progress < 50:
                    critical_krs.append({
                        "kr_id": kr.id,
                        "title": kr.title,
                        "progress": progress,
                        "target_value": kr.target_value,
                        "current_value": kr.current_value
                    })
        
        return {
            "plant_okrs": plant_data,
            "critical_key_results": sorted(critical_krs, key=lambda x: x["progress"]),
            "dashboard_type": "PLANT_HEAD",
            "generated_at": datetime.utcnow()
        }

    def get_employee_dashboard(
        self,
        owner_id: str
    ) -> Dict:
        """
        Get Employee dashboard.
        """
        employee_okrs = self.db.query(OKR).filter_by(
            owner_id=owner_id,
            level_type=OKRLevelType.EMPLOYEE
        ).all()
        
        okr_data = []
        total_progress = []
        
        for okr in employee_okrs:
            score = self.scoring_service.calculate_okr_comprehensive_score(okr.id)
            trajectory = self.trajectory_service.calculate_trajectory(okr.id)
            
            if score and trajectory:
                total_progress.append(score["final_score"])
                okr_data.append({
                    "okr_id": okr.id,
                    "objective": okr.objective,
                    "progress": score["final_score"],
                    "trend": trajectory["trend_status"],
                    "key_results": [
                        {
                            "kr_id": kr.id,
                            "title": kr.title,
                            "progress": self.scoring_service.calculate_kr_progress(kr)
                        }
                        for kr in okr.key_results
                    ]
                })
        
        # Get alignment info
        alignments = self.db.query(OKRAlignment).filter(
            OKRAlignment.child_okr_id.in_([o.id for o in employee_okrs])
        ).all()
        
        return {
            "personal_okrs": okr_data,
            "overall_progress": sum(total_progress) / len(total_progress) if total_progress else 0.0,
            "alignment_count": len(alignments),
            "dashboard_type": "EMPLOYEE",
            "generated_at": datetime.utcnow()
        }

    # ========================================================================
    # ANALYTICS REPORTS
    # ========================================================================

    def get_progress_trends(
        self,
        okr_id: str,
        days_back: int = 90
    ) -> Dict:
        """
        Get progress trends for an OKR over time.
        """
        updates = self.scoring_service.get_kr_progress_history(okr_id, days_back)
        
        # Aggregate by date
        timeline = {}
        for update in updates:
            date_key = update["update_date"].date().isoformat()
            if date_key not in timeline:
                timeline[date_key] = []
            timeline[date_key].append(update["progress_percentage"])
        
        # Average by date
        daily_progress = [
            {
                "date": date,
                "progress": sum(values) / len(values)
            }
            for date, values in sorted(timeline.items())
        ]
        
        return {
            "okr_id": okr_id,
            "timeline": daily_progress,
            "days_tracked": len(daily_progress),
            "current_progress": daily_progress[-1]["progress"] if daily_progress else 0.0
        }

    def get_okr_comparison(
        self,
        okr_ids: List[str]
    ) -> Dict:
        """
        Compare multiple OKRs side-by-side.
        """
        comparisons = []
        
        for okr_id in okr_ids:
            okr = self.db.query(OKR).filter_by(id=okr_id).first()
            if not okr:
                continue
            
            score = self.scoring_service.calculate_okr_comprehensive_score(okr_id)
            health = self.health_service.calculate_okr_health(okr_id)
            trajectory = self.trajectory_service.calculate_trajectory(okr_id)
            
            if score and health and trajectory:
                comparisons.append({
                    "okr_id": okr_id,
                    "objective": okr.objective,
                    "owner_id": okr.owner_id,
                    "level": okr.level_type.value,
                    "progress": score["final_score"],
                    "health": health["health_status"],
                    "trajectory": trajectory["trajectory_score"],
                    "confidence": health["confidence_score"],
                    "trend": trajectory["trend_status"]
                })
        
        return {
            "comparisons": comparisons,
            "count": len(comparisons)
        }

    def get_executive_summary(
        self,
        org_id: str
    ) -> Dict:
        """
        Get executive summary for leadership review.
        """
        metrics = self.get_organization_metrics(org_id)
        
        # Top 5 OKRs by progress
        okrs = self.db.query(OKR).filter_by(org_id=org_id).all()
        scored_okrs = []
        
        for okr in okrs:
            score = self.scoring_service.calculate_okr_comprehensive_score(okr.id)
            if score:
                scored_okrs.append({
                    "okr_id": okr.id,
                    "objective": okr.objective,
                    "owner_id": okr.owner_id,
                    "level": okr.level_type.value,
                    "progress": score["final_score"]
                })
        
        top_okrs = sorted(scored_okrs, key=lambda x: x["progress"], reverse=True)[:5]
        bottom_okrs = sorted(scored_okrs, key=lambda x: x["progress"])[:5]
        
        return {
            "organization_metrics": metrics,
            "top_performing_okrs": top_okrs,
            "bottom_performing_okrs": bottom_okrs,
            "summary_timestamp": datetime.utcnow()
        }
