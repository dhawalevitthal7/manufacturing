"""
Pure parent/child rules for OrgNode hierarchy (Phase 2).

Callers load ``parent_node`` from the DB and pass it here. This module performs
no queries — only type checks — so rules stay testable and avoid duplicate reads.
"""

from __future__ import annotations

from typing import Optional, Union

from fastapi import HTTPException

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
