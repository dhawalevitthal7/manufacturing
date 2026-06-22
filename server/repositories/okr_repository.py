"""
OKR Repository Pattern
Data access layer with clean separation of concerns
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from server.okr_models import (
    OKR, KeyResult, KRProgressUpdate, OKRAlignment,
    OKRLevelType, OKRStatus
)


class OKRRepository:
    """Repository for OKR data access"""

    def __init__(self, db: Session):
        self.db = db

    # Create operations
    def create_okr(self, okr: OKR) -> OKR:
        """Create a new OKR"""
        self.db.add(okr)
        self.db.commit()
        self.db.refresh(okr)
        return okr

    def create_key_result(self, kr: KeyResult) -> KeyResult:
        """Create a new Key Result"""
        self.db.add(kr)
        self.db.commit()
        self.db.refresh(kr)
        return kr

    # Read operations
    def get_okr_by_id(self, okr_id: str) -> Optional[OKR]:
        """Get OKR by ID"""
        return self.db.query(OKR).filter_by(id=okr_id).first()

    def get_okr_with_krs(self, okr_id: str) -> Optional[OKR]:
        """Get OKR with all its Key Results eager loaded"""
        okr = self.get_okr_by_id(okr_id)
        if okr:
            # Ensure KRs are loaded
            _ = okr.key_results
        return okr

    def get_okrs_by_owner(
        self,
        owner_id: str,
        level_type: Optional[OKRLevelType] = None,
        status: Optional[OKRStatus] = None
    ) -> List[OKR]:
        """Get OKRs owned by a user"""
        query = self.db.query(OKR).filter_by(owner_id=owner_id)
        
        if level_type:
            query = query.filter_by(level_type=level_type)
        
        if status:
            query = query.filter_by(status=status)
        
        return query.all()

    def get_okrs_by_organization(
        self,
        org_id: str,
        level_type: Optional[OKRLevelType] = None
    ) -> List[OKR]:
        """Get all OKRs in an organization"""
        query = self.db.query(OKR).filter_by(org_id=org_id)
        
        if level_type:
            query = query.filter_by(level_type=level_type)
        
        return query.all()

    def get_okrs_by_quarter(
        self,
        org_id: str,
        quarter: int,
        year: int
    ) -> List[OKR]:
        """Get OKRs for a specific quarter"""
        return self.db.query(OKR).filter(
            OKR.org_id == org_id,
            OKR.quarter == quarter,
            OKR.year == year
        ).all()

    def get_okr_by_region(
        self,
        region_id: str
    ) -> List[OKR]:
        """Get all OKRs for a region"""
        return self.db.query(OKR).filter_by(region_id=region_id).all()

    def get_okr_by_plant(
        self,
        plant_id: str
    ) -> List[OKR]:
        """Get all OKRs for a plant"""
        return self.db.query(OKR).filter_by(plant_id=plant_id).all()

    # Update operations
    def update_okr(self, okr_id: str, **kwargs) -> Optional[OKR]:
        """Update OKR fields"""
        okr = self.get_okr_by_id(okr_id)
        if not okr:
            return None
        
        for key, value in kwargs.items():
            if hasattr(okr, key):
                setattr(okr, key, value)
        
        self.db.commit()
        self.db.refresh(okr)
        return okr

    # Delete operations
    def delete_okr(self, okr_id: str) -> bool:
        """Delete an OKR and its KRs"""
        okr = self.get_okr_by_id(okr_id)
        if not okr:
            return False
        
        self.db.delete(okr)
        self.db.commit()
        return True


class KeyResultRepository:
    """Repository for Key Result data access"""

    def __init__(self, db: Session):
        self.db = db

    def get_kr_by_id(self, kr_id: str) -> Optional[KeyResult]:
        """Get KR by ID"""
        return self.db.query(KeyResult).filter_by(id=kr_id).first()

    def get_krs_by_okr(self, okr_id: str) -> List[KeyResult]:
        """Get all KRs for an OKR"""
        return self.db.query(KeyResult).filter_by(okr_id=okr_id).all()

    def create_kr(self, kr: KeyResult) -> KeyResult:
        """Create a new KR"""
        self.db.add(kr)
        self.db.commit()
        self.db.refresh(kr)
        return kr

    def update_kr(self, kr_id: str, **kwargs) -> Optional[KeyResult]:
        """Update KR"""
        kr = self.get_kr_by_id(kr_id)
        if not kr:
            return None
        
        for key, value in kwargs.items():
            if hasattr(kr, key):
                setattr(kr, key, value)
        
        self.db.commit()
        self.db.refresh(kr)
        return kr

    def delete_kr(self, kr_id: str) -> bool:
        """Delete a KR"""
        kr = self.get_kr_by_id(kr_id)
        if not kr:
            return False
        
        self.db.delete(kr)
        self.db.commit()
        return True

    def add_progress_update(
        self,
        kr_id: str,
        current_value: float,
        progress_percentage: float,
        notes: Optional[str] = None,
        updated_by_id: Optional[str] = None
    ) -> Optional[KRProgressUpdate]:
        """Add a progress update for a KR"""
        update = KRProgressUpdate(
            id=self._generate_id(),
            key_result_id=kr_id,
            current_value=current_value,
            progress_percentage=progress_percentage,
            notes=notes,
            updated_by_id=updated_by_id
        )
        
        self.db.add(update)
        self.db.commit()
        self.db.refresh(update)
        return update

    def get_progress_history(
        self,
        kr_id: str,
        limit: int = 100
    ) -> List[KRProgressUpdate]:
        """Get progress history for a KR"""
        return self.db.query(KRProgressUpdate).filter_by(
            key_result_id=kr_id
        ).order_by(KRProgressUpdate.update_date.desc()).limit(limit).all()

    @staticmethod
    def _generate_id() -> str:
        """Generate a unique ID"""
        import uuid
        return str(uuid.uuid4())


class OKRAlignmentRepository:
    """Repository for OKR Alignment data access"""

    def __init__(self, db: Session):
        self.db = db

    def get_alignment_by_id(self, alignment_id: str) -> Optional[OKRAlignment]:
        """Get alignment by ID"""
        return self.db.query(OKRAlignment).filter_by(id=alignment_id).first()

    def get_alignments_for_okr(
        self,
        okr_id: str,
        direction: str = "both"
    ) -> List[OKRAlignment]:
        """Get alignments for an OKR"""
        if direction == "parent":
            return self.db.query(OKRAlignment).filter_by(
                child_okr_id=okr_id
            ).all()
        elif direction == "child":
            return self.db.query(OKRAlignment).filter_by(
                parent_okr_id=okr_id
            ).all()
        else:
            return self.db.query(OKRAlignment).filter(
                or_(
                    OKRAlignment.parent_okr_id == okr_id,
                    OKRAlignment.child_okr_id == okr_id
                )
            ).all()

    def get_child_alignments(self, parent_okr_id: str) -> List[OKRAlignment]:
        """Get all child alignments for a parent"""
        return self.db.query(OKRAlignment).filter_by(
            parent_okr_id=parent_okr_id
        ).all()

    def get_parent_alignments(self, child_okr_id: str) -> List[OKRAlignment]:
        """Get all parent alignments for a child"""
        return self.db.query(OKRAlignment).filter_by(
            child_okr_id=child_okr_id
        ).all()

    def create_alignment(self, alignment: OKRAlignment) -> OKRAlignment:
        """Create an alignment"""
        self.db.add(alignment)
        self.db.commit()
        self.db.refresh(alignment)
        return alignment

    def update_alignment(self, alignment_id: str, **kwargs) -> Optional[OKRAlignment]:
        """Update an alignment"""
        alignment = self.get_alignment_by_id(alignment_id)
        if not alignment:
            return None
        
        for key, value in kwargs.items():
            if hasattr(alignment, key):
                setattr(alignment, key, value)
        
        self.db.commit()
        self.db.refresh(alignment)
        return alignment

    def delete_alignment(self, alignment_id: str) -> bool:
        """Delete an alignment"""
        alignment = self.get_alignment_by_id(alignment_id)
        if not alignment:
            return False
        
        self.db.delete(alignment)
        self.db.commit()
        return True

    def check_alignment_exists(
        self,
        parent_okr_id: str,
        child_okr_id: str
    ) -> bool:
        """Check if an alignment already exists"""
        return self.db.query(OKRAlignment).filter(
            and_(
                OKRAlignment.parent_okr_id == parent_okr_id,
                OKRAlignment.child_okr_id == child_okr_id
            )
        ).first() is not None
