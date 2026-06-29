"""Debug West region → plant cascade state."""
import sqlite3

DB = "manufacturing_os.db"
conn = sqlite3.connect(DB)
c = conn.cursor()

print("=== Regional OKR (Digital Integration West) ===")
c.execute(
    """
    SELECT id, title, level, okr_status, region_id, owner_id,
           cascade_generation_status, parent_id, ai_generated
    FROM objectives
    WHERE title LIKE '%Digital Integration%West%'
       OR title LIKE '%Enhance Digital Integration%'
    """
)
regional_okrs = c.fetchall()
for r in regional_okrs:
    print(r)

print("\n=== Plant head (west2) ===")
c.execute(
    "SELECT id, email, name FROM users WHERE email = ?",
    ("planthead.west2@birlacement.test",),
)
ph = c.fetchone()
print(ph)

print("\n=== Regional head (west) ===")
c.execute(
    "SELECT id, email FROM users WHERE email = ?",
    ("regionalhead.west@birlacement.test",),
)
rh = c.fetchone()
print(rh)

if ph:
    print("\n=== AI objectives owned by plant head ===")
    c.execute(
        """
        SELECT id, title, level, okr_status, ai_generated, region_id, plant_id,
               ai_generated_from_objective_id
        FROM objectives
        WHERE owner_id = ? AND ai_generated = 1
        ORDER BY created_at DESC
        """,
        (ph[0],),
    )
    for r in c.fetchall():
        print(r)
    if not c.fetchall():
        pass

if regional_okrs:
    pid = regional_okrs[0][0]
    print(f"\n=== Children of regional OKR {pid[:8]}... ===")
    c.execute(
        """
        SELECT id, title, level, okr_status, ai_generated, owner_id, plant_id, region_id
        FROM objectives
        WHERE parent_id = ? OR ai_generated_from_objective_id = ?
        ORDER BY level, created_at
        """,
        (pid, pid),
    )
    children = c.fetchall()
    if children:
        for ch in children:
            c.execute("SELECT email FROM users WHERE id = ?", (ch[5],))
            em = c.fetchone()
            print(ch, "owner:", em[0] if em else "?")
    else:
        print("(none — cascade did not run)")

print("\n=== West region node ===")
c.execute(
    "SELECT id, name, head_user_id FROM org_nodes WHERE node_type = 'REGION' AND name LIKE '%West%'"
)
west = c.fetchone()
print(west)

if west:
    print("\n=== Plants under West region ===")
    c.execute(
        """
        SELECT n.id, n.name, n.head_user_id, u.email
        FROM org_nodes n
        LEFT JOIN users u ON u.id = n.head_user_id
        WHERE n.parent_id = ? AND n.node_type = 'PLANT'
        """,
        (west[0],),
    )
    for r in c.fetchall():
        print(r)

print("\n=== All PLANT AI_DRAFT / UNDER_REVIEW ===")
c.execute(
    """
    SELECT o.id, substr(o.title, 1, 60), o.okr_status, u.email, o.region_id
    FROM objectives o
    LEFT JOIN users u ON u.id = o.owner_id
    WHERE o.level = 'PLANT'
      AND o.ai_generated = 1
      AND o.okr_status IN ('AI_DRAFT', 'UNDER_REVIEW', 'PENDING_PARENT_APPROVAL')
    """
)
rows = c.fetchall()
for r in rows:
    print(r)
if not rows:
    print("(none)")

conn.close()
