"""
OKR Alignment Service
Manages many-to-many alignment relationships and alignment-based calculations
Handles circular dependency prevention and graph traversal
"""

from typing import List, Dict, Set, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from server.okr_models import OKR, OKRAlignment, AlignmentType
from server.okr_utils import (
    calculate_alignment_contribution,
    calculate_parent_okr_score,
    get_level_weight_factors,
    detect_circular_alignment
)


class OKRAlignmentService:
    """
    Service for managing OKR alignment relationships.
    
    Supports many-to-many alignment with:
    - Circular dependency detection
    - Contribution weight tracking
    - Multiple alignment types
    - Graph traversal algorithms
    """

    def __init__(self, db: Session, scoring_service: 'OKRScoringService'):
        """
        Initialize alignment service.
        
        Args:
            db: SQLAlchemy session
            scoring_service: OKRScoringService instance for score calculations
        """
        self.db = db
        self.scoring_service = scoring_service

    # ========================================================================
    # ALIGNMENT CREATION AND DELETION
    # ========================================================================

    def create_alignment(
        self,
        parent_okr_id: str,
        child_okr_id: str,
        contribution_weight: int = 3,
        alignment_type: AlignmentType = AlignmentType.OPERATIONAL
    ) -> Optional[OKRAlignment]:
        """
        Create a new OKR alignment relationship.
        
        Performs circular dependency detection before creation.
        
        Args:
            parent_okr_id: Parent OKR ID
            child_okr_id: Child OKR ID
            contribution_weight: How much child contributes (1-5)
            alignment_type: Type of alignment
        
        Returns:
            OKRAlignment object or None if validation fails
        
        Raises:
            ValueError: If circular dependency detected or other validation fails
        """
        # Validate OKRs exist
        parent = self.db.query(OKR).filter_by(id=parent_okr_id).first()
        child = self.db.query(OKR).filter_by(id=child_okr_id).first()
        
        if not parent or not child:
            raise ValueError("Parent or child OKR not found")
        
        if parent_okr_id == child_okr_id:
            raise ValueError("Cannot align OKR with itself")
        
        # Check if alignment already exists
        existing = self.db.query(OKRAlignment).filter(
            and_(
                OKRAlignment.parent_okr_id == parent_okr_id,
                OKRAlignment.child_okr_id == child_okr_id
            )
        ).first()
        
        if existing:
            raise ValueError("Alignment already exists")
        
        # Build graph for circular dependency check
        graph = self._build_alignment_graph()
        
        # Check for circular dependency
        if self._would_create_cycle(parent_okr_id, child_okr_id, graph):
            raise ValueError("Creating this alignment would form a circular dependency")
        
        # Create alignment
        alignment = OKRAlignment(
            id=self._generate_id(),
            parent_okr_id=parent_okr_id,
            child_okr_id=child_okr_id,
            contribution_weight=contribution_weight,
            alignment_type=alignment_type
        )
        
        self.db.add(alignment)
        self.db.commit()
        
        return alignment

    def delete_alignment(
        self,
        alignment_id: str
    ) -> bool:
        """
        Delete an OKR alignment.
        
        Args:
            alignment_id: Alignment ID
        
        Returns:
            True if deleted, False if not found
        """
        alignment = self.db.query(OKRAlignment).filter_by(id=alignment_id).first()
        
        if not alignment:
            return False
        
        self.db.delete(alignment)
        self.db.commit()
        return True

    def update_alignment(
        self,
        alignment_id: str,
        contribution_weight: Optional[int] = None,
        alignment_type: Optional[AlignmentType] = None
    ) -> Optional[OKRAlignment]:
        """
        Update an existing alignment.
        
        Args:
            alignment_id: Alignment ID
            contribution_weight: New weight (1-5)
            alignment_type: New alignment type
        
        Returns:
            Updated OKRAlignment or None if not found
        """
        alignment = self.db.query(OKRAlignment).filter_by(id=alignment_id).first()
        
        if not alignment:
            return None
        
        if contribution_weight is not None:
            alignment.contribution_weight = contribution_weight
        
        if alignment_type is not None:
            alignment.alignment_type = alignment_type
        
        alignment.updated_at = datetime.utcnow()
        self.db.commit()
        
        return alignment

    # ========================================================================
    # GRAPH TRAVERSAL
    # ========================================================================

    def _build_alignment_graph(self) -> Dict[str, List[str]]:
        """
        Build graph of all alignments.
        
        Returns:
            Dict mapping okr_id -> list of child okr_ids
        """
        alignments = self.db.query(OKRAlignment).all()
        
        graph = {}
        for alignment in alignments:
            if alignment.parent_okr_id not in graph:
                graph[alignment.parent_okr_id] = []
            graph[alignment.parent_okr_id].append(alignment.child_okr_id)
        
        return graph

    def _would_create_cycle(
        self,
        parent_id: str,
        child_id: str,
        graph: Dict[str, List[str]]
    ) -> bool:
        """
        Check if adding an alignment would create a cycle.
        
        Uses depth-first search from child_id to see if it can reach parent_id.
        """
        return detect_circular_alignment(parent_id, child_id, graph)

    def get_all_ancestors(
        self,
        okr_id: str,
        depth_limit: int = 10
    ) -> List[str]:
        """
        Get all ancestor OKRs (parents and parents of parents, etc.).
        
        Args:
            okr_id: OKR ID
            depth_limit: Maximum traversal depth to prevent issues
        
        Returns:
            List of ancestor OKR IDs
        """
        ancestors = []
        visited = set()
        
        def traverse(current_id: str, depth: int):
            if depth > depth_limit or current_id in visited:
                return
            
            visited.add(current_id)
            
            parents = self.db.query(OKRAlignment).filter_by(
                child_okr_id=current_id
            ).all()
            
            for alignment in parents:
                if alignment.parent_okr_id not in ancestors:
                    ancestors.append(alignment.parent_okr_id)
                traverse(alignment.parent_okr_id, depth + 1)
        
        traverse(okr_id, 0)
        return ancestors

    def get_all_descendants(
        self,
        okr_id: str,
        depth_limit: int = 10
    ) -> List[str]:
        """
        Get all descendant OKRs (children and children of children, etc.).
        
        Args:
            okr_id: OKR ID
            depth_limit: Maximum traversal depth
        
        Returns:
            List of descendant OKR IDs
        """
        descendants = []
        visited = set()
        
        def traverse(current_id: str, depth: int):
            if depth > depth_limit or current_id in visited:
                return
            
            visited.add(current_id)
            
            children = self.db.query(OKRAlignment).filter_by(
                parent_okr_id=current_id
            ).all()
            
            for alignment in children:
                if alignment.child_okr_id not in descendants:
                    descendants.append(alignment.child_okr_id)
                traverse(alignment.child_okr_id, depth + 1)
        
        traverse(okr_id, 0)
        return descendants

    def get_alignment_chain(
        self,
        child_okr_id: str
    ) -> List[Dict]:
        """
        Get the full alignment chain from child to root parent(s).
        
        Returns:
            List of {okr_id, level, progress, alignment_info}
        """
        chain = []
        visited = set()
        
        def traverse(current_id: str):
            if current_id in visited:
                return
            
            visited.add(current_id)
            
            okr = self.db.query(OKR).filter_by(id=current_id).first()
            if not okr:
                return
            
            score = self.scoring_service.calculate_okr_comprehensive_score(current_id)
            
            chain.append({
                "okr_id": current_id,
                "objective": okr.objective,
                "level": okr.level_type.value,
                "progress": score["final_score"] if score else 0.0
            })
            
            parents = self.db.query(OKRAlignment).filter_by(
                child_okr_id=current_id
            ).all()
            
            for alignment in parents:
                traverse(alignment.parent_okr_id)
        
        traverse(child_okr_id)
        return chain

    # ========================================================================
    # ALIGNMENT SCORING
    # ========================================================================

    def calculate_alignment_contribution_for_okr(
        self,
        parent_okr_id: str
    ) -> float:
        """
        Calculate the alignment contribution score for a parent OKR.
        
        Weighted average of all aligned children's progress.
        
        Args:
            parent_okr_id: Parent OKR ID
        
        Returns:
            Alignment contribution score (0-100)
        """
        # Get all alignments where this OKR is parent
        alignments = self.db.query(OKRAlignment).filter_by(
            parent_okr_id=parent_okr_id
        ).all()
        
        if not alignments:
            return 0.0
        
        # Get child progress and weights
        child_scores = []
        for alignment in alignments:
            child_score = self.scoring_service.calculate_okr_comprehensive_score(
                alignment.child_okr_id,
                include_alignment=False  # Use only child's own KRs
            )
            
            if child_score:
                child_scores.append((
                    child_score["final_score"],
                    alignment.contribution_weight
                ))
        
        return calculate_alignment_contribution(child_scores)

    def calculate_parent_okr_score_with_alignment(
        self,
        parent_okr_id: str
    ) -> Dict:
        """
        Calculate parent OKR score including alignment contribution.
        
        Args:
            parent_okr_id: Parent OKR ID
        
        Returns:
            {
                'own_kr_score': float,
                'alignment_contribution': float,
                'final_score': float,
                'components': {...}
            }
        """
        okr = self.db.query(OKR).filter_by(id=parent_okr_id).first()
        if not okr:
            return None
        
        # Get own KR score
        own_kr_score = self.scoring_service.calculate_okr_progress_from_krs_only(
            parent_okr_id
        )
        
        # Get alignment contribution
        alignment_contribution = self.calculate_alignment_contribution_for_okr(
            parent_okr_id
        )
        
        # Get weight factors
        own_weight, alignment_weight = get_level_weight_factors(okr.level_type.value)
        
        # Calculate final score
        final_score = calculate_parent_okr_score(
            own_kr_score=own_kr_score,
            own_weight_factor=own_weight,
            alignment_contribution=alignment_contribution,
            alignment_weight_factor=alignment_weight
        )
        
        return {
            "own_kr_score": own_kr_score,
            "alignment_contribution": alignment_contribution,
            "final_score": final_score,
            "own_weight_factor": own_weight,
            "alignment_weight_factor": alignment_weight,
            "okr_level": okr.level_type.value,
            "calculation_timestamp": datetime.utcnow()
        }

    # ========================================================================
    # ALIGNMENT QUERIES
    # ========================================================================

    def get_alignments_for_okr(
        self,
        okr_id: str,
        direction: str = "both"  # "parent", "child", "both"
    ) -> List[OKRAlignment]:
        """
        Get all alignments for an OKR.
        
        Args:
            okr_id: OKR ID
            direction: Which alignments to return
        
        Returns:
            List of OKRAlignment objects
        """
        if direction == "parent":
            return self.db.query(OKRAlignment).filter_by(
                child_okr_id=okr_id
            ).all()
        elif direction == "child":
            return self.db.query(OKRAlignment).filter_by(
                parent_okr_id=okr_id
            ).all()
        else:  # both
            return self.db.query(OKRAlignment).filter(
                or_(
                    OKRAlignment.parent_okr_id == okr_id,
                    OKRAlignment.child_okr_id == okr_id
                )
            ).all()

    def get_aligned_okrs_for_parent(
        self,
        parent_okr_id: str
    ) -> List[Dict]:
        """
        Get all child OKRs aligned to a parent.
        
        Returns:
            List of {okr_id, objective, progress, contribution_weight}
        """
        alignments = self.db.query(OKRAlignment).filter_by(
            parent_okr_id=parent_okr_id
        ).all()
        
        result = []
        for alignment in alignments:
            child_okr = self.db.query(OKR).filter_by(
                id=alignment.child_okr_id
            ).first()
            
            if child_okr:
                score = self.scoring_service.calculate_okr_comprehensive_score(
                    alignment.child_okr_id
                )
                
                result.append({
                    "okr_id": alignment.child_okr_id,
                    "objective": child_okr.objective,
                    "owner_id": child_okr.owner_id,
                    "level": child_okr.level_type.value,
                    "progress": score["final_score"] if score else 0.0,
                    "contribution_weight": alignment.contribution_weight,
                    "alignment_type": alignment.alignment_type.value
                })
        
        return result

    def get_alignment_report_for_okr(
        self,
        okr_id: str
    ) -> Dict:
        """
        Get comprehensive alignment report for an OKR.
        
        Shows parent alignment and child alignment info.
        """
        okr = self.db.query(OKR).filter_by(id=okr_id).first()
        if not okr:
            return None
        
        # Get parent alignments
        parent_alignments = self.db.query(OKRAlignment).filter_by(
            child_okr_id=okr_id
        ).all()
        
        parent_data = []
        for alignment in parent_alignments:
            parent_okr = self.db.query(OKR).filter_by(
                id=alignment.parent_okr_id
            ).first()
            if parent_okr:
                parent_data.append({
                    "parent_okr_id": alignment.parent_okr_id,
                    "objective": parent_okr.objective,
                    "contribution_weight": alignment.contribution_weight,
                    "alignment_type": alignment.alignment_type.value
                })
        
        # Get child alignments
        child_alignments = self.get_aligned_okrs_for_parent(okr_id)
        
        # Calculate contribution
        if parent_alignments:
            # This OKR contributes to parents
            contribution_to_parents = sum(
                a.contribution_weight for a in parent_alignments
            ) / len(parent_alignments)
        else:
            contribution_to_parents = 0.0
        
        return {
            "okr_id": okr_id,
            "objective": okr.objective,
            "level": okr.level_type.value,
            "parent_alignments": parent_data,
            "child_alignments": child_alignments,
            "is_aligned_to_parents": len(parent_alignments) > 0,
            "has_aligned_children": len(child_alignments) > 0,
            "avg_contribution_weight_to_parents": contribution_to_parents
        }

    # ========================================================================
    # UTILITY METHODS
    # ========================================================================

    def _generate_id(self) -> str:
        """Generate a unique ID"""
        import uuid
        return str(uuid.uuid4())

    def count_alignments(self, okr_id: str) -> Dict:
        """Get count of alignments for an OKR"""
        as_parent = self.db.query(OKRAlignment).filter_by(
            parent_okr_id=okr_id
        ).count()
        
        as_child = self.db.query(OKRAlignment).filter_by(
            child_okr_id=okr_id
        ).count()
        
        return {
            "as_parent": as_parent,
            "as_child": as_child,
            "total": as_parent + as_child
        }
