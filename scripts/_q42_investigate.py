"""Pre-4.2 investigation: corporate objective anchoring. Run from repo root."""
import sqlite3
import os

DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "manufacturing_os.db")
con = sqlite3.connect(DB)
cur = con.cursor()

print("=== Q1: level distribution ===")
for r in cur.execute("SELECT level, COUNT(*) FROM objectives GROUP BY level"):
    print(r)

print("\n=== Objectives with NULL plant_id AND NULL department_id AND NULL team_id ===")
rows = cur.execute(
    """
    SELECT o.id, o.title, o.level, o.plant_id, o.department_id, o.team_id, o.owner_id
    FROM objectives o
    WHERE o.plant_id IS NULL AND o.department_id IS NULL AND o.team_id IS NULL
    """
).fetchall()
print("count:", len(rows))
for row in rows[:25]:
    print(row)

print("\n=== ORGANIZATION-level objectives (sample) ===")
for r in cur.execute(
    "SELECT id, title, plant_id, department_id, team_id, owner_id FROM objectives WHERE level = 'ORGANIZATION' LIMIT 20"
):
    print(r)

print("\n=== Join owner -> users.org_node_id -> org_nodes.node_type (all objectives) ===")
q = """
SELECT o.id, o.title, o.level, o.plant_id, o.department_id, o.team_id,
       u.org_node_id, n.node_type AS owner_org_node_type, n.name AS owner_node_name
FROM objectives o
JOIN users u ON u.id = o.owner_id
LEFT JOIN org_nodes n ON n.id = u.org_node_id
WHERE o.plant_id IS NULL AND o.department_id IS NULL AND o.team_id IS NULL
LIMIT 30
"""
for r in cur.execute(q):
    print(r)

print("\n=== Owners whose org_node is CORPORATE_FUNCTION or VERTICAL (any objective) ===")
q2 = """
SELECT o.id, o.title, o.level, o.plant_id, o.department_id, o.team_id, n.node_type
FROM objectives o
JOIN users u ON u.id = o.owner_id
JOIN org_nodes n ON n.id = u.org_node_id
WHERE n.node_type IN ('CORPORATE_FUNCTION', 'VERTICAL')
LIMIT 30
"""
for r in cur.execute(q2):
    print(r)

print("\n=== DEPARTMENT-level with dept set: owner org_node CF/VERTICAL? (sample) ===")
q3 = """
SELECT o.id, o.title, o.level, o.department_id, n2.node_type AS dept_node_type,
       u.org_node_id, n3.node_type AS owner_anchor_type
FROM objectives o
JOIN users u ON u.id = o.owner_id
LEFT JOIN org_nodes n2 ON n2.id = o.department_id
LEFT JOIN org_nodes n3 ON n3.id = u.org_node_id
WHERE o.level = 'DEPARTMENT' AND o.department_id IS NOT NULL
LIMIT 15
"""
for r in cur.execute(q3):
    print(r)

con.close()
