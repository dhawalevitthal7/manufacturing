"""Emit raw SQL outputs for Phase 1.5 final report."""
import sqlite3

DB = "manufacturing_os.db"


def main():
    c = sqlite3.connect(DB).cursor()
    for label, q in [
        ("organizations", "SELECT COUNT(*) FROM organizations"),
        ("plants", "SELECT COUNT(*) FROM plants"),
        ("departments", "SELECT COUNT(*) FROM departments"),
        ("teams", "SELECT COUNT(*) FROM teams"),
        ("org_nodes total", "SELECT COUNT(*) FROM org_nodes"),
        ("org_nodes by type", "SELECT node_type, COUNT(*) FROM org_nodes GROUP BY node_type ORDER BY node_type"),
    ]:
        c.execute(q)
        print(f"--- {label} ---")
        print(c.fetchall())

    c.execute(
        """SELECT COUNT(*) FROM org_nodes c JOIN org_nodes p ON p.id = c.parent_id
           WHERE c.path NOT LIKE p.path || '.%'"""
    )
    print("--- check 2d (expect 0) ---", c.fetchone()[0])

    c.execute(
        """SELECT COUNT(*) FROM org_nodes
           WHERE depth != (LENGTH(path) - LENGTH(REPLACE(path, '.', '')))"""
    )
    print("--- check 2b (expect 0) ---", c.fetchone()[0])

    c.execute("SELECT COUNT(*) FROM users WHERE org_node_id IS NULL")
    print("--- check 3 unmapped (expect 0) ---", c.fetchone()[0])

    c.execute(
        """SELECT id, node_type, path FROM org_nodes
           WHERE path LIKE '%..%' OR path LIKE '.%' OR path LIKE '%.' """
    )
    print("--- check 2a malformed (expect empty) ---", c.fetchall())

    c.execute(
        """SELECT COUNT(*) FROM org_nodes n
           LEFT JOIN org_nodes p ON p.id = n.parent_id
           WHERE n.parent_id IS NOT NULL AND p.id IS NULL"""
    )
    print("--- check 2c orphan parent (expect 0) ---", c.fetchone()[0])

    c.execute(
        """SELECT COUNT(*) FROM org_nodes
           WHERE node_type = 'ORGANIZATION' AND (parent_id IS NOT NULL OR depth != 0)"""
    )
    print("--- check 2e org root (expect 0) ---", c.fetchone()[0])

    c.execute(
        """SELECT COUNT(*) FROM org_nodes
           WHERE node_type != 'ORGANIZATION' AND parent_id IS NULL"""
    )
    print("--- check 2f non-org null parent (expect 0) ---", c.fetchone()[0])


if __name__ == "__main__":
    main()
