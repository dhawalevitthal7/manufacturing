import sqlite3
c = sqlite3.connect(r"C:\Users\Girish\OneDrive\Desktop\Vitthal\manufacturing\manufacturing_os.db")
cur = c.cursor()
for lvl in ["REGION", "PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"]:
    rows = cur.execute(
        "SELECT okr_status, COUNT(*) FROM objectives WHERE level=? AND ai_generated=1 GROUP BY okr_status",
        (lvl,),
    ).fetchall()
    print(lvl, dict(rows))
c.close()
