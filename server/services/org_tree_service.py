"""
Organization Tree Service
========================

Centralized business logic for the OrgNode hierarchy:
  - Path computation (materialized dotted-string paths)
  - Ancestor/descendant queries
  - Node creation/movement
  - Sync between OrgNode and legacy Plant/Department/Team tables

Path and depth follow the invariants documented on the OrgNode model in server/models.py.
"""

from typing import Optional, List, Tuple
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from server.models import OrgNode, User, Plant, Department, Team, Organization


def org_node_depth_from_path(path: str) -> int:
    """Depth from materialized path. Invariant: depth == path.count('.') (see OrgNode in models.py)."""
    return path.count(".")


def _new_non_legacy_node_id() -> str:
    """Fresh UUID for nodes that are not legacy Plant/Department/Team (e.g. future REGION)."""
    return str(uuid.uuid4())


def get_descendants(node_id: str, db: Session) -> List[OrgNode]:
    """
    Get all descendants of a node using path LIKE query.
    
    Args:
        node_id: The node ID to find descendants for
        db: Database session
    
    Returns:
        List of OrgNode descendants (ordered by path)
    """
    node = db.query(OrgNode).filter(OrgNode.id == node_id).first()
    if not node:
        return []
    
    # Find all nodes whose path starts with this node's path + a dot
    descendants = db.query(OrgNode).filter(
        OrgNode.path.like(f"{node.path}.%")
    ).order_by(OrgNode.path).all()
    
    return descendants


def get_ancestors(node_id: str, db: Session) -> List[OrgNode]:
    """
    Get all ancestors of a node by parsing the path string.
    
    Args:
        node_id: The node ID to find ancestors for
        db: Database session
    
    Returns:
        List of OrgNode ancestors (ordered from root to immediate parent)
    """
    node = db.query(OrgNode).filter(OrgNode.id == node_id).first()
    if not node:
        return []
    
    # Parse path and fetch each ancestor
    path_segments = node.path.split(".")
    ancestors = []
    
    for i in range(len(path_segments) - 1):
        partial_path = ".".join(path_segments[:i + 1])
        ancestor = db.query(OrgNode).filter(
            OrgNode.path == partial_path
        ).first()
        if ancestor:
            ancestors.append(ancestor)
    
    return ancestors


def is_descendant_of(child_id: str, ancestor_id: str, db: Session) -> bool:
    """
    Check if child_id is a descendant of ancestor_id.
    
    Args:
        child_id: Potential child node ID
        ancestor_id: Potential ancestor node ID
        db: Database session
    
    Returns:
        True if child_id is a descendant of ancestor_id
    """
    child = db.query(OrgNode).filter(OrgNode.id == child_id).first()
    ancestor = db.query(OrgNode).filter(OrgNode.id == ancestor_id).first()
    
    if not child or not ancestor:
        return False
    
    return child.path.startswith(f"{ancestor.path}.")


def create_child_node(
    parent_id: Optional[str],
    node_type: str,
    name: str,
    org_id: str,
    code: Optional[str] = None,
    head_user_id: Optional[str] = None,
    node_metadata: Optional[dict] = None,
    db: Session = None,
    node_id: Optional[str] = None,
) -> OrgNode:
    """
    Create a new node. Path/depth follow OrgNode invariants in server/models.py.

    - ORGANIZATION root: parent_id must be None, node_id must be the org primary key,
      path = node_id, depth = 0.
    - Any other node: parent_id required; path = parent.path + '.' + this.id,
      depth = path.count('.'). Pass node_id for PLANT/DEPARTMENT/TEAM (= legacy id);
      if node_id is omitted, a new UUID is generated (Phase 2+ non-legacy nodes).
    """
    if node_metadata is None:
        node_metadata = {}

    if parent_id is None:
        if node_type != "ORGANIZATION":
            raise ValueError("Only ORGANIZATION may have parent_id=None")
        if not node_id:
            raise ValueError("ORGANIZATION root requires node_id (= organizations.id)")
        path = node_id
        depth = org_node_depth_from_path(path)
        final_id = node_id
    else:
        parent = db.query(OrgNode).filter(OrgNode.id == parent_id).first()
        if not parent:
            raise ValueError(f"Parent node {parent_id} not found")
        child_id = node_id if node_id else _new_non_legacy_node_id()
        path = f"{parent.path}.{child_id}"
        depth = org_node_depth_from_path(path)
        final_id = child_id

    return OrgNode(
        id=final_id,
        org_id=org_id,
        parent_id=parent_id,
        node_type=node_type,
        name=name,
        code=code,
        head_user_id=head_user_id,
        path=path,
        depth=depth,
        node_metadata=node_metadata,
        is_active=True,
    )


def move_node(node_id: str, new_parent_id: Optional[str], db: Session) -> None:
    """
    Move a node to a new parent, updating path for the node and ALL descendants.
    Path/depth follow OrgNode invariants (server/models.py).
    """
    node = db.query(OrgNode).filter(OrgNode.id == node_id).first()
    if not node:
        raise ValueError(f"Node {node_id} not found")

    if new_parent_id is None:
        new_path = node.org_id
    else:
        new_parent = db.query(OrgNode).filter(OrgNode.id == new_parent_id).first()
        if not new_parent:
            raise ValueError(f"New parent {new_parent_id} not found")
        new_path = f"{new_parent.path}.{node.id}"

    new_depth = org_node_depth_from_path(new_path)
    old_path = node.path

    node.parent_id = new_parent_id
    node.path = new_path
    node.depth = new_depth

    descendants = db.query(OrgNode).filter(
        OrgNode.path.like(f"{old_path}.%")
    ).all()

    for desc in descendants:
        relative_path = desc.path[len(old_path):]
        desc.path = new_path + relative_path
        desc.depth = org_node_depth_from_path(desc.path)


def sync_org_node_for(
    entity_type: str,
    entity_id: str,
    org_id: str,
    name: str,
    parent_id: Optional[str],
    code: Optional[str] = None,
    head_user_id: Optional[str] = None,
    db: Session = None,
) -> Optional[OrgNode]:
    """
    Sync an OrgNode with a Plant/Department/Team entity.

    OrgNode.id always equals the legacy row id for PLANT, DEPARTMENT, TEAM (see models.py).
    Upsert by primary key entity_id.
    """
    node_type_map = {
        "PLANT": "PLANT",
        "DEPARTMENT": "DEPARTMENT",
        "TEAM": "TEAM",
    }
    node_type = node_type_map.get(entity_type)
    if not node_type:
        raise ValueError(f"Unknown entity_type: {entity_type}")

    if entity_type == "PLANT" and not parent_id:
        raise ValueError("PLANT sync requires parent_id = organization root id (organizations.id)")

    existing = db.query(OrgNode).filter(OrgNode.id == entity_id).first()

    if existing:
        existing.name = name
        existing.parent_id = parent_id
        existing.code = code if code is not None else existing.code
        if head_user_id is not None:
            existing.head_user_id = head_user_id
        parent = db.query(OrgNode).filter(OrgNode.id == parent_id).first() if parent_id else None
        if parent_id and parent:
            existing.path = f"{parent.path}.{entity_id}"
            existing.depth = org_node_depth_from_path(existing.path)
        db.flush()
        return existing

    node = create_child_node(
        parent_id=parent_id,
        node_type=node_type,
        name=name,
        org_id=org_id,
        code=code,
        head_user_id=head_user_id,
        node_metadata={},
        db=db,
        node_id=entity_id,
    )
    db.add(node)
    return node


def get_node_by_entity(
    entity_type: str,
    entity_id: str,
    org_id: str,
    db: Session,
) -> Optional[OrgNode]:
    """Find OrgNode by legacy primary key (same id). See OrgNode invariants in server/models.py."""
    if entity_type not in ("PLANT", "DEPARTMENT", "TEAM"):
        return None
    return (
        db.query(OrgNode)
        .filter(OrgNode.id == entity_id, OrgNode.org_id == org_id)
        .first()
    )


def build_tree_response(nodes: List[OrgNode], node_map: dict = None) -> dict:
    """
    Convert a flat list of OrgNodes into a nested tree response.
    
    Args:
        nodes: List of OrgNode objects (should include root)
        node_map: Optional pre-built map of node_id -> node for efficiency
    
    Returns:
        Dict representation of the tree with 'children' nesting
    """
    if node_map is None:
        node_map = {n.id: n for n in nodes}
    
    # Build parent->children index
    children_by_parent = {}
    for node in nodes:
        parent_id = node.parent_id
        if parent_id not in children_by_parent:
            children_by_parent[parent_id] = []
        children_by_parent[parent_id].append(node)
    
    # Find root nodes (parent_id = None)
    roots = children_by_parent.get(None, [])
    
    def node_to_dict(node):
        """Recursively convert node to dict with children."""
        children = children_by_parent.get(node.id, [])
        return {
            "id": node.id,
            "org_id": node.org_id,
            "parent_id": node.parent_id,
            "node_type": node.node_type,
            "name": node.name,
            "code": node.code,
            "head_user_id": node.head_user_id,
            "path": node.path,
            "depth": node.depth,
            "node_metadata": node.node_metadata or {},
            "is_active": node.is_active,
            "children": [node_to_dict(child) for child in sorted(children, key=lambda c: c.name)],
            "created_at": node.created_at.isoformat(),
            "updated_at": node.updated_at.isoformat(),
        }
    
    # Return root if single org, or list if multiple orgs
    if len(roots) == 1:
        return node_to_dict(roots[0])
    else:
        return {
            "roots": [node_to_dict(root) for root in sorted(roots, key=lambda r: r.name)]
        }
