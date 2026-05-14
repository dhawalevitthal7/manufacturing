"""
Seed a Default Region and reparent org-root plants under it.

Manual one-off only. Not invoked from migrations, startup, or CI.

Usage (from repository root):
  python -m server.scripts.seed_default_region --org-id <uuid>
  python -m server.scripts.seed_default_region --org-id <uuid> --dry-run
"""

from __future__ import annotations

import argparse
import sys
from typing import List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from server.database import SessionLocal
from server.models import Organization, OrgNode
from server.services.org_tree_service import create_child_node, move_node

DEFAULT_REGION_NAME = "Default Region"


def _get_org_root_node(db: Session, org_id: str) -> OrgNode:
    """Same rule as routes_org_tree._get_org_root_node (ORGANIZATION row id == org_id)."""
    root = db.query(OrgNode).filter(OrgNode.id == org_id, OrgNode.org_id == org_id).first()
    if not root:
        raise ValueError(f"Organization root OrgNode not found for org_id={org_id}")
    return root


def _plants_under_org_root(db: Session, org_id: str) -> List[OrgNode]:
    return (
        db.query(OrgNode)
        .filter(
            OrgNode.org_id == org_id,
            OrgNode.node_type == "PLANT",
            OrgNode.parent_id == org_id,
            OrgNode.is_active == True,
        )
        .order_by(OrgNode.name)
        .all()
    )


def _count_descendants_below_plants(db: Session, plants: List[OrgNode]) -> int:
    """Strict descendants (path under each plant), excluding the plant row itself."""
    total = 0
    for p in plants:
        total += (
            db.query(OrgNode)
            .filter(
                OrgNode.path.like(f"{p.path}.%"),
                OrgNode.is_active == True,
            )
            .count()
        )
    return total


def run(org_id: str, dry_run: bool) -> int:
    db = SessionLocal()
    try:
        org = db.query(Organization).filter(Organization.id == org_id).first()
        if not org:
            print(f"ERROR: No organization found with id={org_id}", file=sys.stderr)
            return 1

        existing = (
            db.query(OrgNode)
            .filter(
                OrgNode.org_id == org_id,
                OrgNode.node_type == "REGION",
                OrgNode.name == DEFAULT_REGION_NAME,
                OrgNode.is_active == True,
            )
            .first()
        )
        if existing:
            print(f"Default Region already exists for org {org_id}; nothing to do")
            return 0

        org_root = _get_org_root_node(db, org_id)
        plants = _plants_under_org_root(db, org_id)
        n = len(plants)
        m = _count_descendants_below_plants(db, plants)

        if dry_run:
            print(
                f"DRY-RUN: Would create REGION named '{DEFAULT_REGION_NAME}' "
                f"under organization root for org_id={org_id}."
            )
            print(f"DRY-RUN: Would reparent {n} plant(s) with root parent_id==org onto that region.")
            print(f"DRY-RUN: Would update paths for {m} descendant org node(s) under those plants (via move_node).")
            print("DRY-RUN: No database changes were made.")
            return 0

        region = create_child_node(
            parent_id=org_root.id,
            node_type="REGION",
            name=DEFAULT_REGION_NAME,
            org_id=org_id,
            code=None,
            head_user_id=None,
            node_metadata={},
            db=db,
        )
        db.add(region)
        db.flush()

        for p in plants:
            move_node(p.id, region.id, db)

        db.commit()
        print(f"Created Default Region {region.id}. Reparented {n} plants and {m} descendants.")
        return 0

    except HTTPException as exc:
        db.rollback()
        print(f"ERROR: {exc.detail}", file=sys.stderr)
        return 1
    except ValueError as exc:
        db.rollback()
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        db.rollback()
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed Default Region and reparent root-level plants.")
    parser.add_argument("--org-id", required=True, help="Organization UUID (organizations.id)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned actions only; do not write to the database.",
    )
    args = parser.parse_args(argv)
    return run(args.org_id.strip(), args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
