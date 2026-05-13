import sqlite3
db_path = r'c:\Users\dhawa\Desktop\manufacturing\manufacturing_os.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()
queries = [
    'SELECT "organizations" as table_name, COUNT(*) as row_count FROM organizations UNION ALL SELECT "plants", COUNT(*) FROM plants UNION ALL SELECT "departments", COUNT(*) FROM departments UNION ALL SELECT "teams", COUNT(*) FROM teams UNION ALL SELECT "users", COUNT(*) FROM users UNION ALL SELECT "org_nodes", COUNT(*) FROM org_nodes;',
    'SELECT COUNT(*) as users_with_org_node FROM users WHERE org_node_id IS NOT NULL;',
    'SELECT id, org_id, parent_id, node_type, name, path, depth FROM org_nodes LIMIT 20;'
]
for q in queries:
    print(f"Executing: {q}")
    rows = cur.execute(q).fetchall()
    for row in rows:
        print(row)
    print("-" * 20)
conn.close()
