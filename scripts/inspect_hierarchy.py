"""Inspect org hierarchy depth and head assignments for cascade simulation."""
import sqlite3

DB = r"C:\Users\Girish\OneDrive\Desktop\Vitthal\manufacturing\manufacturing_os.db"
conn = sqlite3.connect(DB)
c = conn.cursor()

ORG = "781357f0-7ef1-4077-a414-a2d53b318188"

for nt in ("REGION", "PLANT", "DEPARTMENT", "TEAM"):
    c.execute(
        "SELECT count(*), sum(case when head_user_id is not null then 1 else 0 end) "
        "FROM org_nodes WHERE org_id=? AND node_type=? AND is_active=1",
        (ORG, nt),
    )
    total, withhead = c.fetchone()
    print(f"{nt}: {total} nodes, {withhead or 0} with head_user_id")

print("\n=== Sample: nodes under East Region ===")
c.execute("SELECT id FROM org_nodes WHERE name='East Region' AND node_type='REGION'")
east = c.fetchone()
if east:
    east_id = east[0]
    c.execute(
        "SELECT node_type, name, head_user_id FROM org_nodes WHERE parent_id=? AND is_active=1",
        (east_id,),
    )
    for r in c.fetchall():
        print(" ", r)

print("\n=== TeamMembers count ===")
c.execute("SELECT count(*) FROM team_members WHERE is_active=1")
print("active team_members:", c.fetchone()[0])

conn.close()
