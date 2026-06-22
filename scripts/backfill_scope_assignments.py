"""
Backfill org_node_id and permission profile scope for UltraTech hierarchy heads.
Run from repo root: python scripts/backfill_scope_assignments.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.database import SessionLocal
from server.models import User, OrgNode, UserPermissionProfile, Organization

ORG_NAME = "UltraTech Cement"


def main():
    db = SessionLocal()
    try:
        org = db.query(Organization).filter(Organization.name == ORG_NAME).first()
        if not org:
            print(f"Organization '{ORG_NAME}' not found")
            return

        updated = 0
        for node_type, scope_field, profile_field in [
            ("REGION", "org_node_id", "scoped_region_id"),
            ("PLANT", "org_node_id", "scoped_plant_id"),
            ("DEPARTMENT", "org_node_id", "scoped_department_id"),
            ("TEAM", "org_node_id", "scoped_team_id"),
        ]:
            nodes = (
                db.query(OrgNode)
                .filter(
                    OrgNode.org_id == org.id,
                    OrgNode.node_type == node_type,
                    OrgNode.head_user_id.isnot(None),
                )
                .all()
            )
            for node in nodes:
                user = db.query(User).filter(User.id == node.head_user_id).first()
                if not user:
                    continue
                setattr(user, "org_node_id", node.id)
                if node_type == "PLANT":
                    user.plant_id = node.id
                elif node_type == "DEPARTMENT":
                    user.department_id = node.id
                elif node_type == "TEAM":
                    user.team_id = node.id

                profile = (
                    db.query(UserPermissionProfile)
                    .filter(UserPermissionProfile.user_id == user.id)
                    .first()
                )
                if profile:
                    setattr(profile, profile_field, node.id)
                    if node_type == "REGION":
                        profile.scope_type = "REGION"
                    elif node_type == "PLANT":
                        profile.scope_type = "PLANT"
                    elif node_type == "DEPARTMENT":
                        profile.scope_type = "DEPARTMENT"
                    elif node_type == "TEAM":
                        profile.scope_type = "TEAM"

                updated += 1
                print(f"  {user.email} -> {node_type} {node.name} ({node.id})")

        db.commit()
        print(f"\nDone. Updated {updated} head assignments.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
