import os
import sqlite3

db = os.path.join(os.path.dirname(os.path.dirname(__file__)), "manufacturing_os.db")
con = sqlite3.connect(db)
cur = con.cursor()
cur.execute("SELECT COUNT(*) FROM org_nodes WHERE name LIKE 'Step4Test%' OR name LIKE 'Step4Dup%'")
b1 = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM plants WHERE name LIKE 'Step4Test%' OR name LIKE 'Step4Dup%'")
b2 = cur.fetchone()[0]
cur.execute("DELETE FROM org_nodes WHERE name LIKE 'Step4Test%' OR name LIKE 'Step4Dup%'")
d1 = cur.rowcount
cur.execute("DELETE FROM plants WHERE name LIKE 'Step4Test%' OR name LIKE 'Step4Dup%'")
d2 = cur.rowcount
con.commit()
cur.execute("SELECT COUNT(*) FROM org_nodes WHERE name LIKE 'Step4Test%' OR name LIKE 'Step4Dup%'")
a1 = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM plants WHERE name LIKE 'Step4Test%' OR name LIKE 'Step4Dup%'")
a2 = cur.fetchone()[0]
con.close()
print("V4h org_nodes matching before:", b1, "after:", a1, "deleted:", d1)
print("V4h plants matching before:", b2, "after:", a2, "deleted:", d2)
