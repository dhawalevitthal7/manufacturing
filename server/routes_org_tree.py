"""
Organization Tree Routes
========================

Endpoints for managing the unified OrgNode hierarchy:
- GET /api/org-tree — fetch scoped org tree for current user
- POST /api/org-tree/regions — create REGION under org root (SUPER_ADMIN, Bearer)
- POST /api/org-tree/corporate-functions — create CORPORATE_FUNCTION under org root (SUPER_ADMIN, Bearer)
- GET /api/org-tree/{node_id} — fetch single node with children
- POST /api/org-tree — create a new node (SUPER_ADMIN only)
- PATCH /api/org-tree/{node_id} — update node (SUPER_ADMIN only)
- DELETE /api/org-tree/{node_id} — soft-delete node (SUPER_ADMIN only)
"""

from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from server.database import get_db
from server.models import OrgNode, User, UserPermissionProfile, Organization, NodeType
from server.schemas import OrgNodeCreate, OrgNodeUpdate, OrgNodeResponse, OrgTreeNamedNodeCreate
from server.auth import require_super_admin
from server.services.org_node_validation import validate_parent_child, validate_functional_parent
from server.services.org_tree_service import (
    get_descendants,
    get_ancestors,
    create_child_node,
    build_tree_response,
    ensure_organization_root,
)

router = APIRouter(prefix="/api/org-tree", tags=["org-tree"])


def get_current_user_from_db(db: Session, user_payload: dict) -> User:
    """Fetch the current user from DB given JWT payload."""
    user_id = user_payload.get("user_id") or user_payload.get("id")
    if not user_id:
        raise HTTPException(401, "No user_id in token")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(401, "User not found")
    
    return user


def _node_visible_for_scope(N: OrgNode, scope_node_id: str, P_X: str) -> bool:
    """
    Visibility for user scoped to node X (path P_X). Exactly one of:
    (a) N.id == X
    (b) P_X.startswith(N.path + '.') — N is strict ancestor of X
    (c) N.path.startswith(P_X + '.') — N is strict descendant of X
    """
    if N.id == scope_node_id:
        return True
    if P_X.startswith(N.path + "."):
        return True
    if N.path.startswith(P_X + "."):
        return True
    return False


def get_user_scope(user: User, db: Session) -> tuple:
    """Returns (scope_type, scope_node_id). scope_node_id is OrgNode id (plant, dept, team, or region)."""
    perm = db.query(UserPermissionProfile).filter(
        UserPermissionProfile.user_id == user.id
    ).first()

    if user.system_role == "SUPER_ADMIN":
        return ("ORGANIZATION", None)

    if perm:
        scope_type = perm.scope_type
        if scope_type == "ORGANIZATION":
            return ("ORGANIZATION", None)
        if scope_type == "PLANT":
            sid = perm.scoped_plant_id or user.plant_id
            if sid:
                return ("PLANT", sid)
        elif scope_type == "DEPARTMENT":
            sid = perm.scoped_department_id or user.department_id
            if sid:
                return ("DEPARTMENT", sid)
        elif scope_type == "TEAM":
            sid = perm.scoped_team_id or user.team_id
            if sid:
                return ("TEAM", sid)
        elif scope_type == "REGION":
            sid = perm.scoped_region_id
            if not sid and user.org_node_id:
                anchor = db.query(OrgNode).filter(OrgNode.id == user.org_node_id).first()
                if anchor and str(anchor.node_type) == "REGION":
                    sid = anchor.id
            if not sid:
                region = (
                    db.query(OrgNode)
                    .filter(
                        OrgNode.org_id == user.org_id,
                        OrgNode.node_type == "REGION",
                        OrgNode.head_user_id == user.id,
                    )
                    .first()
                )
                if region:
                    sid = region.id
            if sid:
                return ("REGION", sid)
            return ("REGION", None)

    if user.org_node_id:
        return ("INDIVIDUAL", user.org_node_id)

    return ("ORGANIZATION", None)


def filter_tree_by_scope(
    nodes: list,
    scope_type: str,
    scope_node_id: Optional[str],
    db: Session,
) -> list:
    """SUPER_ADMIN / org-wide: all nodes. Else filter by (a)(b)(c) vs scope path P_X."""
    if scope_type == "REGION" and scope_node_id is None:
        return []
    if scope_type == "ORGANIZATION" or scope_node_id is None:
        return nodes

    scope_node = db.query(OrgNode).filter(OrgNode.id == scope_node_id).first()
    if not scope_node:
        return []

    P_X = scope_node.path

    # REGION: only the region node and its descendants (not org root / sibling branches).
    if scope_type == "REGION":
        prefix = P_X + "."
        return [N for N in nodes if N.id == scope_node_id or (N.path and N.path.startswith(prefix))]

    return [N for N in nodes if _node_visible_for_scope(N, scope_node_id, P_X)]


def _org_node_response_dict(node: OrgNode) -> dict:
    """Same JSON shape as POST /api/org-tree create response."""
    return {
        "id": node.id,
        "org_id": node.org_id,
        "parent_id": node.parent_id,
        "functional_parent_id": node.functional_parent_id,
        "node_type": node.node_type,
        "name": node.name,
        "code": node.code,
        "head_user_id": node.head_user_id,
        "path": node.path,
        "depth": node.depth,
        "node_metadata": node.node_metadata or {},
        "is_active": node.is_active,
        "created_at": node.created_at.isoformat(),
        "updated_at": node.updated_at.isoformat(),
    }


def _get_org_root_node(db: Session, org_id: str) -> OrgNode:
    """Return org root OrgNode, creating it from Organization row if missing (e.g. new register)."""
    root = db.query(OrgNode).filter(OrgNode.id == org_id, OrgNode.org_id == org_id).first()
    if root:
        return root
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(404, "Organization not found")
    return ensure_organization_root(db, org.id, org.name)


@router.get("")
def get_org_tree(
    db: Session = Depends(get_db),
    org_id: str = Query(""),
    user_id: str = Query(""),
):
    """
    Get the organization tree, scoped to what the current user can see.
    
    For SUPER_ADMIN: returns full tree.
    For others: returns only their assigned scope (plant, department, team, or individual).
    """
    # Fetch current user
    user_payload = {"user_id": user_id}
    user = get_current_user_from_db(db, user_payload)
    
    if user.org_id != org_id:
        raise HTTPException(403, "User does not belong to this organization")
    
    # Determine user's visibility scope
    scope_type, scope_node_id = get_user_scope(user, db)
    
    # Fetch all nodes for the org
    all_nodes = db.query(OrgNode).filter(
        OrgNode.org_id == org_id,
        OrgNode.is_active == True,
    ).order_by(OrgNode.path).all()
    
    # Filter by user's scope
    visible_nodes = filter_tree_by_scope(all_nodes, scope_type, scope_node_id, db)
    
    if not visible_nodes:
        return {"error": "No visible nodes for this user"}
    
    # Build nested tree
    tree = build_tree_response(visible_nodes)
    
    return tree


@router.post("/regions")
def create_region(
    req: OrgTreeNamedNodeCreate,
    db: Session = Depends(get_db),
    org_id: str = Query(""),
    _auth: dict = Depends(require_super_admin),
):
    """Create a REGION node under the organization root (SUPER_ADMIN, Bearer JWT)."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(404, "Organization not found")

    org_root = _get_org_root_node(db, org_id)
    validate_parent_child(NodeType.REGION, org_root)

    try:
        node = create_child_node(
            parent_id=org_root.id,
            node_type="REGION",
            name=req.name,
            org_id=org_id,
            code=req.code,
            head_user_id=req.head_user_id,
            node_metadata={},
            db=db,
        )
        db.add(node)
        db.commit()
        db.refresh(node)
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Failed to create region: {str(e)}")

    return _org_node_response_dict(node)


@router.post("/corporate-functions")
def create_corporate_function(
    req: OrgTreeNamedNodeCreate,
    db: Session = Depends(get_db),
    org_id: str = Query(""),
    _auth: dict = Depends(require_super_admin),
):
    """Create a CORPORATE_FUNCTION node under the organization root (SUPER_ADMIN, Bearer JWT)."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(404, "Organization not found")

    org_root = _get_org_root_node(db, org_id)
    validate_parent_child(NodeType.CORPORATE_FUNCTION, org_root)

    try:
        node = create_child_node(
            parent_id=org_root.id,
            node_type="CORPORATE_FUNCTION",
            name=req.name,
            org_id=org_id,
            code=req.code,
            head_user_id=req.head_user_id,
            node_metadata={},
            db=db,
        )
        db.add(node)
        db.commit()
        db.refresh(node)
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Failed to create corporate function: {str(e)}")

    return _org_node_response_dict(node)


@router.get("/{node_id}")
def get_org_node(
    node_id: str,
    db: Session = Depends(get_db),
    org_id: str = Query(""),
    user_id: str = Query(""),
):
    """
    Get a single node and its immediate children.
    Scoped by user permission.
    """
    user_payload = {"user_id": user_id}
    user = get_current_user_from_db(db, user_payload)
    
    node = db.query(OrgNode).filter(
        OrgNode.id == node_id,
        OrgNode.org_id == org_id,
    ).first()
    
    if not node:
        raise HTTPException(404, "Node not found")
    
    # Check permission
    scope_type, scope_node_id = get_user_scope(user, db)
    if scope_type == "REGION" and not scope_node_id:
        raise HTTPException(403, "User does not have permission to view this node")
    if scope_type != "ORGANIZATION" and scope_node_id:
        scope_anchor = db.query(OrgNode).filter(OrgNode.id == scope_node_id).first()
        if scope_anchor:
            P_X = scope_anchor.path
            if not _node_visible_for_scope(node, scope_node_id, P_X):
                raise HTTPException(403, "User does not have permission to view this node")
        else:
            raise HTTPException(403, "User does not have permission to view this node")
    
    # Fetch immediate children
    children = db.query(OrgNode).filter(
        OrgNode.parent_id == node_id,
        OrgNode.is_active == True,
    ).order_by(OrgNode.name).all()
    
    return {
        "id": node.id,
        "org_id": node.org_id,
        "parent_id": node.parent_id,
        "functional_parent_id": node.functional_parent_id,
        "node_type": node.node_type,
        "name": node.name,
        "code": node.code,
        "head_user_id": node.head_user_id,
        "path": node.path,
        "depth": node.depth,
        "node_metadata": node.node_metadata or {},
        "is_active": node.is_active,
        "children": [
            {
                "id": c.id,
                "node_type": c.node_type,
                "name": c.name,
                "code": c.code,
                "head_user_id": c.head_user_id,
                "depth": c.depth,
                "functional_parent_id": c.functional_parent_id,
            }
            for c in children
        ],
        "created_at": node.created_at.isoformat(),
        "updated_at": node.updated_at.isoformat(),
    }


@router.post("")
def create_org_node(
    req: OrgNodeCreate,
    db: Session = Depends(get_db),
    org_id: str = Query(""),
    _auth: dict = Depends(require_super_admin),
):
    """
    Create a new org node (SUPER_ADMIN only).
    
    If parent_id is None, creates an org root (not recommended during Phase 1).
    If parent_id is specified, creates as child of that node.
    """
    # Verify org exists
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(404, "Organization not found")
    
    # Verify parent exists (if specified)
    if req.parent_id:
        parent = db.query(OrgNode).filter(
            OrgNode.id == req.parent_id,
            OrgNode.org_id == org_id,
        ).first()
        if not parent:
            raise HTTPException(404, "Parent node not found")
    
    # Create the new node
    try:
        node = create_child_node(
            parent_id=req.parent_id,
            node_type=req.node_type,
            name=req.name,
            org_id=org_id,
            code=req.code,
            head_user_id=req.head_user_id,
            node_metadata=req.node_metadata or {},
            db=db,
        )
        db.add(node)
        db.commit()
        db.refresh(node)
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Failed to create node: {str(e)}")
    
    return _org_node_response_dict(node)


@router.patch("/{node_id}")
def update_org_node(
    node_id: str,
    req: OrgNodeUpdate,
    db: Session = Depends(get_db),
    org_id: str = Query(""),
    _auth: dict = Depends(require_super_admin),
):
    """
    Update an existing org node (SUPER_ADMIN only).
    
    Can update: name, code, head_user_id, node_metadata, parent_id (move), functional_parent_id.
    """
    node = db.query(OrgNode).filter(
        OrgNode.id == node_id,
        OrgNode.org_id == org_id,
    ).first()
    
    if not node:
        raise HTTPException(404, "Node not found")

    payload = req.model_dump(exclude_unset=True)

    # Update fields
    if req.name:
        node.name = req.name
    if req.code:
        node.code = req.code
    if req.head_user_id is not None:
        node.head_user_id = req.head_user_id
    if req.node_metadata is not None:
        node.node_metadata = req.node_metadata

    # Handle move (change parent) before functional_parent (validation uses solid-tree ancestry).
    if req.parent_id is not None and req.parent_id != node.parent_id:
        parent = db.query(OrgNode).filter(
            OrgNode.id == req.parent_id,
            OrgNode.org_id == org_id,
        ).first()
        if not parent:
            raise HTTPException(404, "New parent node not found")

        # Prevent moving node under itself or a descendant
        from server.services.org_tree_service import is_descendant_of
        if req.parent_id == node_id or is_descendant_of(req.parent_id, node_id, db):
            raise HTTPException(400, "Cannot move node under itself or a descendant")

        # Perform the move
        try:
            from server.services.org_tree_service import move_node
            move_node(node_id, req.parent_id, db)
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(400, f"Failed to move node: {str(e)}")

    if "functional_parent_id" in payload:
        db.refresh(node)
        validate_functional_parent(db, node, payload["functional_parent_id"])
        node.functional_parent_id = payload["functional_parent_id"]

    db.commit()
    db.refresh(node)

    return _org_node_response_dict(node)


@router.delete("/{node_id}")
def delete_org_node(
    node_id: str,
    db: Session = Depends(get_db),
    org_id: str = Query(""),
    _auth: dict = Depends(require_super_admin),
):
    """
    Soft-delete an org node (SUPER_ADMIN only).
    
    A node can only be deleted if it has no active children.
    """
    node = db.query(OrgNode).filter(
        OrgNode.id == node_id,
        OrgNode.org_id == org_id,
    ).first()
    
    if not node:
        raise HTTPException(404, "Node not found")
    
    # Check for active children
    children = db.query(OrgNode).filter(
        OrgNode.parent_id == node_id,
        OrgNode.is_active == True,
    ).first()
    
    if children:
        raise HTTPException(400, "Cannot delete node with active children. Delete children first.")
    
    # Soft delete
    node.is_active = False
    db.commit()
    
    return {"status": "deleted", "node_id": node_id}
