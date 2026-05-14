import sqlite3
con = sqlite3.connect("manufacturing_os.db")
cur = con.cursor()
cur.execute(
    "SELECT org_id, COUNT(*) FROM org_nodes WHERE name='Default Region' "
    "AND node_type='REGION' GROUP BY org_id"
)
print(cur.fetchall())
con.close()
