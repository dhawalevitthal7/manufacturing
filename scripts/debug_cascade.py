"""Debug AI cascade state for production efficiency OKR."""
import sqlite3

DB = r"C:\Users\Girish\OneDrive\Desktop\Vitthal\manufacturing\manufacturing_os.db"
conn = sqlite3.connect(DB)
c = conn.cursor()

print("=== Parent OKR (production efficiency) ===")
c.execute(
    """
    SELECT id, title, level, okr_status, cascade_generation_status,
           ai_generated, allows_cascade, owner_id, org_id, created_at
    FROM objectives
    WHERE lower(title) LIKE '%production efficiency%'
    """
)
parents = c.fetchall()
for r in parents:
    print(r)

for parent in parents:
    pid = parent[0]
    print(f"\n=== Children of {pid[:8]}... ===")
    c.execute(
        """
        SELECT id, title, level, okr_status, ai_generated,
               ai_generated_from_objective_id, owner_id, region_id
        FROM objectives
        WHERE ai_generated_from_objective_id = ? OR parent_id = ?
        """,
        (pid, pid),
    )
    children = c.fetchall()
    if children:
        for ch in children:
            print(ch)
    else:
        print("(none)")

print("\n=== All AI_DRAFT / UNDER_REVIEW objectives ===")
c.execute(
    """
    SELECT id, title, level, okr_status, ai_generated_from_objective_id, owner_id
    FROM objectives
    WHERE ai_generated = 1
      AND okr_status IN ('AI_DRAFT', 'UNDER_REVIEW', 'PENDING_PARENT_APPROVAL', 'AI_REJECTED')
    """
)
for r in c.fetchall():
    print(r)

print("\n=== REGION org_nodes ===")
c.execute(
    "SELECT id, name, head_user_id, org_id FROM org_nodes WHERE node_type='REGION' LIMIT 15"
)
regions = c.fetchall()
for r in regions:
    print(r)
print(f"Total regions: {len(regions)}")

print("\n=== Check columns exist ===")
c.execute("PRAGMA table_info(objectives)")
cols = [row[1] for row in c.fetchall()]
for col in ["cascade_generation_status", "ai_generated_from_objective_id", "okr_status"]:
    print(f"  {col}: {'YES' if col in cols else 'MISSING'}")

conn.close()
