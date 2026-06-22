"""
Pure parent/child rules for OrgNode hierarchy (Phase 2).

Callers load ``parent_node`` from the DB and pass it here. This module performs
no queries — only type checks — so rules stay testable and avoid duplicate reads.
"""

from __future__ import annotations

from typing import Optional, Union

from fastapi import HTTPException
from sqlalchemy.orm import Session

from server.models import NodeType, OrgNode


def _as_child_type(child_type: Union[NodeType, str]) -> NodeType:
    if isinstance(child_type, NodeType):
        return child_type
    try:
        return NodeType(child_type)
    except ValueError as exc:
        raise HTTPException(400, f"Invalid node_type: {child_type!r}") from exc


def _parent_kind(parent_node: Optional[OrgNode]) -> Optional[NodeType]:
    if parent_node is None:
        return None
    pt = parent_node.node_type
    if isinstance(pt, NodeType):
        return pt
    try:
        return NodeType(pt)
    except ValueError as exc:
        raise HTTPException(400, f"Invalid parent node_type: {pt!r}") from exc


def validate_parent_child(
    child_type: Union[NodeType, str],
    parent_node: Optional[OrgNode],
) -> None:
    """
    Raises HTTPException(400, ...) if the parent/child relationship is invalid.

    Rules:
      - ORGANIZATION: parent must be None (root only).
      - REGION: parent must be ORGANIZATION.
      - CORPORATE_FUNCTION: parent must be ORGANIZATION.
      - PLANT: parent must be ORGANIZATION or REGION.
      - VERTICAL: parent must be CORPORATE_FUNCTION.
      - DEPARTMENT: parent must be PLANT, CORPORATE_FUNCTION, or VERTICAL.
      - SUB_DEPARTMENT: parent must be DEPARTMENT.
      - TEAM: parent must be DEPARTMENT or SUB_DEPARTMENT.
    """
    ct = _as_child_type(child_type)
    pk = _parent_kind(parent_node)

    if ct == NodeType.ORGANIZATION:
        if pk is not None:
            raise HTTPException(400, "ORGANIZATION root must have no parent")
        return

    if pk is None:
        raise HTTPException(
            400,
            f"A {ct.value} node must have a parent; only ORGANIZATION may be root",
        )

    if ct == NodeType.REGION:
        if pk != NodeType.ORGANIZATION:
            raise HTTPException(400, "REGION may only be created under the organization root")
        return

    if ct == NodeType.CORPORATE_FUNCTION:
        if pk != NodeType.ORGANIZATION:
            raise HTTPException(
                400,
                "CORPORATE_FUNCTION may only be created under the organization root",
            )
        return

    if ct == NodeType.PLANT:
        if pk not in (NodeType.ORGANIZATION, NodeType.REGION):
            raise HTTPException(
                400,
                "PLANT may only be placed under ORGANIZATION or REGION",
            )
        return

    if ct == NodeType.VERTICAL:
        if pk != NodeType.CORPORATE_FUNCTION:
            raise HTTPException(
                400,
                "VERTICAL may only be placed under CORPORATE_FUNCTION",
            )
        return

    if ct == NodeType.DEPARTMENT:
        if pk not in (
            NodeType.PLANT,
            NodeType.CORPORATE_FUNCTION,
            NodeType.VERTICAL,
        ):
            raise HTTPException(
                400,
                "DEPARTMENT may only be placed under PLANT, CORPORATE_FUNCTION, or VERTICAL",
            )
        return

    if ct == NodeType.SUB_DEPARTMENT:
        if pk != NodeType.DEPARTMENT:
            raise HTTPException(400, "SUB_DEPARTMENT may only be placed under DEPARTMENT")
        return

    if ct == NodeType.TEAM:
        if pk not in (NodeType.DEPARTMENT, NodeType.SUB_DEPARTMENT):
            raise HTTPException(
                400,
                "TEAM may only be placed under DEPARTMENT or SUB_DEPARTMENT",
            )
        return

    raise HTTPException(400, f"Unsupported node_type for placement rules: {ct.value}")


def _node_has_plant_ancestor_on_solid_tree(node: OrgNode, db: Session) -> bool:
    """True if walking ``parent_id`` from ``node`` reaches a PLANT (plant-embedded subtree)."""
    cur_id = node.parent_id
    while cur_id:
        cur = db.query(OrgNode).filter(OrgNode.id == cur_id).first()
        if not cur:
            break
        pk = _parent_kind(cur)
        if pk == NodeType.PLANT:
            return True
        cur_id = cur.parent_id
    return False


def validate_functional_parent(db: Session, node: OrgNode, functional_parent_id: Optional[str]) -> None:
    """
    Raises HTTPException(400, ...) unless ``functional_parent_id`` is valid for ``node``.

    ``None`` clears the link (always allowed). Non-``None`` values apply the Phase 4.1 matrix:
    only DEPARTMENT / SUB_DEPARTMENT under a plant subtree; target same org;
    CORPORATE_FUNCTION or VERTICAL; not self; target not a solid-tree descendant of ``node``.
    """
    if functional_parent_id is None:
        return

    fp = str(functional_parent_id).strip()
    if not fp:
        raise HTTPException(400, "functional_parent_id must be a non-empty string or null")

    ct = _as_child_type(node.node_type)
    if ct not in (NodeType.DEPARTMENT, NodeType.SUB_DEPARTMENT):
        raise HTTPException(
            400,
            "functional_parent_id may only be set on DEPARTMENT or SUB_DEPARTMENT nodes",
        )

    if not _node_has_plant_ancestor_on_solid_tree(node, db):
        raise HTTPException(
            400,
            "functional_parent_id is only allowed for nodes inside a plant subtree (solid parent chain must reach PLANT)",
        )

    target = db.query(OrgNode).filter(OrgNode.id == fp).first()
    if not target or target.org_id != node.org_id:
        raise HTTPException(
            400,
            "Functional parent must reference an existing org node in the same organization",
        )

    if target.id == node.id:
        raise HTTPException(400, "A node cannot be its own functional parent")

    from server.services.org_tree_service import is_descendant_of

    if is_descendant_of(target.id, node.id, db):
        raise HTTPException(
            400,
            "Functional parent cannot be a descendant of this node on the solid tree",
        )

    tt = _parent_kind(target)
    if tt not in (NodeType.CORPORATE_FUNCTION, NodeType.VERTICAL):
        raise HTTPException(
            400,
            "Functional parent must be a CORPORATE_FUNCTION or VERTICAL node",
        )


def validate_plant_region_parent_node(region_node: OrgNode) -> None:
    """
    When ``region_id`` is supplied on plant create, the node must be an active REGION
    in the tree (caller already scoped by org_id).
    """
    if _parent_kind(region_node) != NodeType.REGION:
        raise HTTPException(
            400,
            "region_id must reference a REGION node in this organization",
        )
