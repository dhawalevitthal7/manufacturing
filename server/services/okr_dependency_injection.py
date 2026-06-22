"""
OKR Dependency Injection Container
Sets up all services with proper dependencies
"""

from sqlalchemy.orm import Session
from typing import Dict

from server.repositories.okr_repository import (
    OKRRepository,
    KeyResultRepository,
    OKRAlignmentRepository
)
from server.services.okr_scoring_service import OKRScoringService
from server.services.okr_alignment_service import OKRAlignmentService
from server.services.okr_health_trajectory_service import (
    OKRHealthService,
    OKRTrajectoryService,
    OKRConfidenceService
)
from server.services.okr_analytics_service import OKRAnalyticsService


class OKRServiceContainer:
    """
    Dependency injection container for OKR services.
    
    Manages service lifecycle and dependencies.
    """

    def __init__(self, db: Session):
        """
        Initialize the service container.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self._services: Dict[str, any] = {}
        self._initialize_services()

    def _initialize_services(self):
        """Initialize all services with their dependencies"""
        
        # Initialize repositories
        self._services['okr_repo'] = OKRRepository(self.db)
        self._services['kr_repo'] = KeyResultRepository(self.db)
        self._services['alignment_repo'] = OKRAlignmentRepository(self.db)
        
        # Initialize core scoring service (no dependencies)
        scoring_service = OKRScoringService(self.db)
        self._services['scoring_service'] = scoring_service
        
        # Initialize alignment service (depends on scoring)
        alignment_service = OKRAlignmentService(self.db, scoring_service)
        self._services['alignment_service'] = alignment_service
        
        # Initialize health/trajectory/confidence services (depend on scoring)
        health_service = OKRHealthService(self.db, scoring_service)
        trajectory_service = OKRTrajectoryService(self.db, scoring_service)
        confidence_service = OKRConfidenceService(self.db, scoring_service)
        
        self._services['health_service'] = health_service
        self._services['trajectory_service'] = trajectory_service
        self._services['confidence_service'] = confidence_service
        
        # Initialize analytics service (depends on all others)
        analytics_service = OKRAnalyticsService(
            db=self.db,
            scoring_service=scoring_service,
            alignment_service=alignment_service,
            health_service=health_service,
            trajectory_service=trajectory_service,
            confidence_service=confidence_service
        )
        self._services['analytics_service'] = analytics_service

    # Service accessors
    def get_scoring_service(self) -> OKRScoringService:
        """Get the OKR scoring service"""
        return self._services['scoring_service']

    def get_alignment_service(self) -> OKRAlignmentService:
        """Get the OKR alignment service"""
        return self._services['alignment_service']

    def get_health_service(self) -> OKRHealthService:
        """Get the OKR health service"""
        return self._services['health_service']

    def get_trajectory_service(self) -> OKRTrajectoryService:
        """Get the OKR trajectory service"""
        return self._services['trajectory_service']

    def get_confidence_service(self) -> OKRConfidenceService:
        """Get the OKR confidence service"""
        return self._services['confidence_service']

    def get_analytics_service(self) -> OKRAnalyticsService:
        """Get the OKR analytics service"""
        return self._services['analytics_service']

    def get_okr_repo(self) -> OKRRepository:
        """Get the OKR repository"""
        return self._services['okr_repo']

    def get_kr_repo(self) -> KeyResultRepository:
        """Get the Key Result repository"""
        return self._services['kr_repo']

    def get_alignment_repo(self) -> OKRAlignmentRepository:
        """Get the OKR Alignment repository"""
        return self._services['alignment_repo']

    # Bulk accessors
    def get_all_services(self) -> Dict[str, any]:
        """Get all initialized services"""
        return self._services.copy()

    def get_repositories(self) -> Dict[str, any]:
        """Get all repositories"""
        return {
            'okr_repo': self._services['okr_repo'],
            'kr_repo': self._services['kr_repo'],
            'alignment_repo': self._services['alignment_repo']
        }


# ============================================================================
# FastAPI Dependency Injection
# ============================================================================

from fastapi import Depends
from server.database import SessionLocal


def get_db() -> Session:
    """
    Get database session.
    Used by FastAPI dependency injection.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_okr_container(db: Session = Depends(get_db)) -> OKRServiceContainer:
    """
    Get OKR service container.
    Used by FastAPI dependency injection.
    
    Usage in route handlers:
        @router.get("/okrs/{okr_id}")
        async def get_okr(okr_id: str, container: OKRServiceContainer = Depends(get_okr_container)):
            service = container.get_scoring_service()
            score = service.calculate_okr_comprehensive_score(okr_id)
            return score
    """
    return OKRServiceContainer(db)


# Convenience functions for simpler dependency patterns
def get_scoring_service(
    container: OKRServiceContainer = Depends(get_okr_container)
) -> OKRScoringService:
    """Get scoring service directly"""
    return container.get_scoring_service()


def get_alignment_service(
    container: OKRServiceContainer = Depends(get_okr_container)
) -> OKRAlignmentService:
    """Get alignment service directly"""
    return container.get_alignment_service()


def get_health_service(
    container: OKRServiceContainer = Depends(get_okr_container)
) -> OKRHealthService:
    """Get health service directly"""
    return container.get_health_service()


def get_analytics_service(
    container: OKRServiceContainer = Depends(get_okr_container)
) -> OKRAnalyticsService:
    """Get analytics service directly"""
    return container.get_analytics_service()
