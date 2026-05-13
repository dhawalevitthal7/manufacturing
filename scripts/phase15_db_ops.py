"""
Phase 1.5 DB verification and cleanup. Run from repo root:
  python scripts/phase15_db_ops.py preflight-a5
  python scripts/phase15_db_ops.py show-users-a4
  python scripts/phase15_db_ops.py objectives-a4
  python scripts/phase15_db_ops.py cleanup-a5   (only after preflight zeros)
"""
import sqlite3
import sys

DB = "manufacturing_os.db"
TEST_PLANT = "faf35859-bf3d-423c-946d-5342361b8a16"
BAD_NODES = (
    "faf35859-bf3d-423c-946d-5342361b8a16",
    "e948ba6a-04b2-483a-ac14-d81fe27db4b6",
    "2972774e-f9e6-4f1c-8a66-9767cb8c0108",
)


def conn():
    return sqlite3.connect(DB)


def preflight_a5():
    c = conn().cursor()
    queries = [
        ("departments for test plant", f"SELECT COUNT(*) FROM departments WHERE plant_id = '{TEST_PLANT}'"),
        (
            "teams under those depts",
            f"""SELECT COUNT(*) FROM teams WHERE department_id IN
                (SELECT id FROM departments WHERE plant_id = '{TEST_PLANT}')""",
        ),
        (
            "objectives plant",
            f"""SELECT COUNT(*) FROM objectives WHERE plant_id = '{TEST_PLANT}'
                OR plant_id IN ('plant2','dept1')""",
        ),
        (
            "key_results",
            f"""SELECT COUNT(*) FROM key_results WHERE objective_id IN (
                SELECT id FROM objectives WHERE plant_id = '{TEST_PLANT}')""",
        ),
        (
            "users org_node refs",
            f"""SELECT COUNT(*) FROM users WHERE org_node_id IN (
                '{BAD_NODES[0]}','{BAD_NODES[1]}','{BAD_NODES[2]}')""",
        ),
    ]
    for label, sql in queries:
        c.execute(sql)
        print(label, "->", c.fetchone()[0])


def show_users_a4():
    c = conn().cursor()
    c.execute(
        """SELECT id, email, system_role, plant_id, department_id, team_id
           FROM users WHERE email IN ('s@tata.com','a@tata.com','b@tata.com')"""
    )
    for row in c.fetchall():
        print(row)


def objectives_a4():
    c = conn().cursor()
    c.execute(
        """SELECT COUNT(*) FROM objectives WHERE owner_id IN (
            SELECT id FROM users WHERE email IN ('s@tata.com','a@tata.com','b@tata.com'))"""
    )
    print("objectives owned by s/a/b ->", c.fetchone()[0])
    c.execute(
        """SELECT o.id, o.title, o.owner_id, o.plant_id, o.department_id, u.email
           FROM objectives o
           JOIN users u ON u.id = o.owner_id
           WHERE o.owner_id IN (
             SELECT id FROM users WHERE email IN ('s@tata.com','a@tata.com','b@tata.com'))"""
    )
    for row in c.fetchall():
        print(" detail:", row)


def apply_a4_updates():
    """Option 1: point dirty dev users at real plant/dept in their org."""
    cx = conn()
    c = cx.cursor()
    org = c.execute(
        "SELECT org_id FROM users WHERE email = 's@tata.com'"
    ).fetchone()[0]
    plant = c.execute(
        "SELECT id FROM plants WHERE org_id = ? AND is_active = 1 LIMIT 1", (org,)
    ).fetchone()
    if not plant:
        raise SystemExit("no plant for org")
    plant_id = plant[0]
    dept = c.execute(
        "SELECT id FROM departments WHERE org_id = ? AND plant_id = ? AND is_active = 1 LIMIT 1",
        (org, plant_id),
    ).fetchone()
    if not dept:
        raise SystemExit("no department")
    dept_id = dept[0]
    # PLANT_HEAD: plant only
    c.execute(
        "UPDATE users SET plant_id = ?, department_id = NULL, team_id = NULL WHERE email = 'a@tata.com'",
        (plant_id,),
    )
    # DEPT_HEAD: plant + dept
    c.execute(
        "UPDATE users SET plant_id = ?, department_id = ?, team_id = NULL WHERE email = 'b@tata.com'",
        (plant_id, dept_id),
    )
    # EMPLOYEE: plant + dept (no team in seed)
    c.execute(
        "UPDATE users SET plant_id = ?, department_id = ?, team_id = NULL WHERE email = 's@tata.com'",
        (plant_id, dept_id),
    )
    # Fix objective plant_id if it referenced bogus plant2
    c.execute(
        """UPDATE objectives SET plant_id = ?, department_id = ?
           WHERE owner_id IN (SELECT id FROM users WHERE email IN ('s@tata.com','a@tata.com','b@tata.com'))
             AND (plant_id IS NULL OR plant_id NOT IN (SELECT id FROM plants))""",
        (plant_id, dept_id),
    )
    cx.commit()
    print("A4 user + objective scope updates committed", plant_id, dept_id)


def cleanup_a5():
    cx = conn()
    c = cx.cursor()
    c.executescript(
        f"""
        BEGIN TRANSACTION;
        UPDATE users SET plant_id = NULL WHERE plant_id = '{TEST_PLANT}';
        UPDATE users SET org_node_id = NULL WHERE org_node_id IN (
          '{BAD_NODES[0]}','{BAD_NODES[1]}','{BAD_NODES[2]}');
        DELETE FROM org_nodes WHERE id = '{BAD_NODES[2]}';
        DELETE FROM org_nodes WHERE id = '{BAD_NODES[1]}';
        DELETE FROM org_nodes WHERE id = '{BAD_NODES[0]}';
        DELETE FROM plants WHERE id = '{TEST_PLANT}';
        COMMIT;
        """
    )
    cx.close()
    print("cleanup committed")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "preflight-a5":
        preflight_a5()
    elif cmd == "show-users-a4":
        show_users_a4()
    elif cmd == "objectives-a4":
        objectives_a4()
    elif cmd == "apply-a4":
        apply_a4_updates()
    elif cmd == "cleanup-a5":
        cleanup_a5()
    else:
        print("usage: phase15_db_ops.py preflight-a5|show-users-a4|objectives-a4|apply-a4|cleanup-a5")
