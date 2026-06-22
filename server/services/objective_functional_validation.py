"""
Functional parent linkage for objectives (Phase 4.2).

Validates ``Objective.functional_parent_obj_id`` (dotted-line alignment to another
objective) with subject-side rules mirroring org-node 4.1 and corporate target anchors.
"""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from server.models import Objective, OrgNode, User
from server.services.org_node_validation import _node_has_plant_ancestor_on_solid_tree

SUBJECT_INELIGIBLE_DETAIL = (
    "functional_parent_obj_id is only allowed when the objective is anchored to a "
    "DEPARTMENT or SUB_DEPARTMENT org node inside a plant subtree."
)
DETAIL_TARGET_NOT_IN_ORG = "Functional parent objective must exist in the same organization"
DETAIL_SELF = "Functional parent objective cannot be the objective itself"
DETAIL_DESCENDANT = (
    "Functional parent objective cannot be a descendant of this objective on the solid tree"
)
DETAIL_TARGET_ANCHOR_TYPE = (
    "Functional parent objective must be anchored to a CORPORATE_FUNCTION or VERTICAL org node"
)
DETAIL_TARGET_ANCHOR_UNRESOLVED = "Cannot resolve corporate anchor for functional parent objective"
DETAIL_CYCLE_MISMATCH = (
    "Functional parent objective must share the same cycle_id; linking across cycles is not allowed"
)
DETAIL_EMPTY_FP = "functional_parent_obj_id must be a non-empty string or null"
DETAIL_CREATE_FORBIDDEN = "functional_parent_obj_id cannot be set on objective create"


def reject_functional_parent_obj_id_in_create_body(body: object) -> None:
    """POST create/assign/hierarchy must not accept ``functional_parent_obj_id`` in JSON."""
    if isinstance(body, dict) and "functional_parent_obj_id" in body:
        raise HTTPException(400, DETAIL_CREATE_FORBIDDEN)


def resolve_objective_org_anchor(obj: Objective, db: Session) -> Optional[OrgNode]:
    """
    Subject (plant department) anchor: ``OrgNode`` for ``objective.department_id`` when
    the objective is strictly DEPARTMENT-level scoped (no team_id), under a plant subtree.
    """
    if (obj.level or "").strip().upper() != "DEPARTMENT":
        return None
    if not obj.department_id or not obj.plant_id:
        return None
    if obj.team_id is not None:
        return None
    node = (
        db.query(OrgNode)
        .filter(OrgNode.id == obj.department_id, OrgNode.org_id == obj.org_id)
        .first()
    )
    if not node:
        return None
    nt = str(node.node_type)
    if nt not in ("DEPARTMENT", "SUB_DEPARTMENT"):
        return None
    if not _node_has_plant_ancestor_on_solid_tree(node, db):
        return None
    return node


def is_descendant_of_objective(descendant_id: str, ancestor_id: str, db: Session) -> bool:
    """True if ``descendant_id`` is a strict descendant of ``ancestor_id`` via ``parent_id`` edges."""
    cur = descendant_id
    visited: set[str] = set()
    for _ in range(64):
        row = db.query(Objective).filter(Objective.id == cur).first()
        if not row or not row.parent_id:
            return False
        if row.parent_id in visited:
            return False
        visited.add(cur)
        if row.parent_id == ancestor_id:
            return True
        cur = row.parent_id
    return False


def _corporate_anchor_and_wrong_type_hint(target: Objective, db: Session) -> tuple[Optional[OrgNode], bool]:
    """
    Returns (anchor, wrong_type_hint): anchor is set only for CORPORATE_FUNCTION / VERTICAL;
    wrong_type_hint is True if an org node was found via department_id or owner.org_node_id
    but neither branch yielded a corporate anchor.
    """
    anchor: Optional[OrgNode] = None
    wrong = False
    if target.department_id:
        n = (
            db.query(OrgNode)
            .filter(OrgNode.id == target.department_id, OrgNode.org_id == target.org_id)
            .first()
        )
        if n:
            if str(n.node_type) in ("CORPORATE_FUNCTION", "VERTICAL"):
                anchor = n
            else:
                wrong = True
    if anchor is None:
        owner = db.query(User).filter(User.id == target.owner_id).first()
        if owner and owner.org_node_id:
            m = (
                db.query(OrgNode)
                .filter(OrgNode.id == owner.org_node_id, OrgNode.org_id == target.org_id)
                .first()
            )
            if m:
                if str(m.node_type) in ("CORPORATE_FUNCTION", "VERTICAL"):
                    anchor = m
                else:
                    wrong = True
    return anchor, wrong and anchor is None


def validate_functional_parent_objective(
    self_obj: Objective,
    functional_parent_obj_id: Optional[str],
    db: Session,
) -> None:
    """
    Raises ``HTTPException(400)`` unless ``functional_parent_obj_id`` is valid for ``self_obj``.
    ``None`` clears (caller applies); non-None applies full matrix.
    """
    if functional_parent_obj_id is None:
        return

    fp = str(functional_parent_obj_id).strip()
    if not fp:
        raise HTTPException(400, DETAIL_EMPTY_FP)

    if resolve_objective_org_anchor(self_obj, db) is None:
        raise HTTPException(400, SUBJECT_INELIGIBLE_DETAIL)

    target = db.query(Objective).filter(Objective.id == fp).first()
    if not target or target.org_id != self_obj.org_id:
        raise HTTPException(400, DETAIL_TARGET_NOT_IN_ORG)

    if target.id == self_obj.id:
        raise HTTPException(400, DETAIL_SELF)

    if is_descendant_of_objective(target.id, self_obj.id, db):
        raise HTTPException(400, DETAIL_DESCENDANT)

    anchor, wrong_hint = _corporate_anchor_and_wrong_type_hint(target, db)
    if anchor is None:
        if wrong_hint:
            raise HTTPException(400, DETAIL_TARGET_ANCHOR_TYPE)
        raise HTTPException(400, DETAIL_TARGET_ANCHOR_UNRESOLVED)

    sc = self_obj.cycle_id
    tc = target.cycle_id
    if (sc is not None or tc is not None) and sc != tc:
        raise HTTPException(400, DETAIL_CYCLE_MISMATCH)
