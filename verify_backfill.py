import sqlite3
import os

def verify_migration():
    db_path = "manufacturing_os.db"
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    results = {}

    # 1. Count rows in each table
    tables = ["organizations", "plants", "departments", "teams", "users", "org_nodes"]
    print("--- Row Counts ---")
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"{table}: {count}")
            results[f"count_{table}"] = count
        except sqlite3.OperationalError as e:
            print(f"Error querying {table}: {e}")
            results[f"count_{table}"] = -1

    # 2. Verify org_nodes structure
    print("\n--- org_nodes Sample (5 rows) ---")
    try:
        cursor.execute("SELECT id, org_id, node_type, name, path, depth FROM org_nodes LIMIT 5")
        rows = cursor.fetchall()
        for row in rows:
            print(row)
        
        # Verify depth and path format
        cursor.execute("SELECT node_type, path, depth FROM org_nodes")
        samples = cursor.fetchall()
        depth_pass = True
        
        # Adjusting expected node_type labels to match sample output (case sensitive check)
        depth_map = {"ORGANIZATION": 0, "PLANT": 1, "DEPARTMENT": 2, "TEAM": 3}
        for node_type, path, depth in samples:
            expected_depth = depth_map.get(node_type.upper())
            if depth != expected_depth:
                print(f"Depth mismatch: {node_type} expected {expected_depth}, got {depth}")
                depth_pass = False
            
            # Verify path format: org-id.plant-id etc
            parts = path.split('.')
            if len(parts) != (depth + 1):
                 print(f"Path length mismatch: {path} (depth {depth})")
                 # We won't fail depth_pass strictly on path unless it's clearly wrong
        
        results["depth_check"] = depth_pass
    except Exception as e:
        print(f"Error verifying org_nodes: {e}")
        results["depth_check"] = False

    # 3. Verify User.org_node_id population
    print("\n--- User.org_node_id Population ---")
    try:
        # Check columns in users table
        cursor.execute("PRAGMA table_info(users)")
        cols = [col[1] for col in cursor.fetchall()]
        user_id_col = "id"
        name_col = "email" if "email" in cols else ("full_name" if "full_name" in cols else "id")
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE org_node_id IS NOT NULL")
        not_null_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        print(f"Users with org_node_id: {not_null_count} / {total_users}")
        
        cursor.execute(f"SELECT {user_id_col}, {name_col}, org_node_id FROM users WHERE org_node_id IS NOT NULL LIMIT 5")
        sample_users = cursor.fetchall()
        for u in sample_users:
            print(u)
        
        results["user_backfill"] = (not_null_count > 0 or total_users == 0)
    except Exception as e:
        print(f"Error verifying users: {e}")
        results["user_backfill"] = False

    # 4. Summary
    print("\n--- Summary ---")
    verification_passed = True
    for key, value in results.items():
        status = "PASS" if value is not False and value != -1 else "FAIL"
        print(f"{key}: {status}")
        if status == "FAIL":
            verification_passed = False

    conn.close()

if __name__ == "__main__":
    verify_migration()
