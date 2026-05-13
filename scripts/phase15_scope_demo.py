"""Demonstrate _node_visible_for_scope for final report (run from repo root)."""
import sys

sys.path.insert(0, ".")
from sqlalchemy.orm import Session
from server.database import SessionLocal
from server.models import OrgNode
from server.routes_org_tree import _node_visible_for_scope


def main():
    db: Session = SessionLocal()
    org = (
        db.query(OrgNode)
        .filter(OrgNode.node_type == "ORGANIZATION", OrgNode.name == "Tata")
        .first()
    )
    if not org:
        print("no org node")
        db.close()
        return
    # Tata org from sanity: pick plant pune under this org if present
    plant = (
        db.query(OrgNode)
        .filter(OrgNode.org_id == org.id, OrgNode.node_type == "PLANT")
        .order_by(OrgNode.path)
        .first()
    )
    dept = (
        db.query(OrgNode)
        .filter(OrgNode.org_id == org.id, OrgNode.node_type == "DEPARTMENT")
        .first()
    )
    team = (
        db.query(OrgNode)
        .filter(OrgNode.org_id == org.id, OrgNode.node_type == "TEAM")
        .first()
    )
    if not plant or not dept or not team:
        print("missing chain", bool(plant), bool(dept), bool(team))
        db.close()
        return

    X = dept.id
    scope_node = db.query(OrgNode).filter(OrgNode.id == X).first()
    P_X = scope_node.path

    unrelated = (
        db.query(OrgNode)
        .filter(OrgNode.org_id == org.id, OrgNode.node_type == "PLANT", OrgNode.id != plant.id)
        .first()
    )

    cases = [
        ("ancestor (ORG)", org),
        ("scope (DEPT)", dept),
        ("descendant (TEAM)", team),
        ("unrelated plant", unrelated),
    ]
    for label, N in cases:
        if N is None:
            print(label, "SKIP None")
            continue
        v = _node_visible_for_scope(N, X, P_X)
        print(f"{label:22} id={N.id[:8]}... path={N.path[:48]}... -> visible={v}")

    # SUPER_ADMIN: all nodes count
    alln = db.query(OrgNode).filter(OrgNode.org_id == org.id, OrgNode.is_active == True).count()
    print("total active nodes in org", alln)
    db.close()


if __name__ == "__main__":
    main()
