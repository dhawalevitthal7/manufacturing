"""Compare GET /api/org-tree for SUPER_ADMIN vs EMPLOYEE (agrawal)."""
import json
import urllib.request

BASE = "http://127.0.0.1:8000/api"


def login(email, pw):
    req = urllib.request.Request(
        f"{BASE}/auth/login",
        data=json.dumps({"email": email, "password": pw}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        d = json.loads(r.read().decode())
    u = d["user"]
    q = f"org_id={u['org_id']}&user_id={u['id']}&role={u['system_role']}"
    return d["access_token"], q


def count_nodes(obj):
    if isinstance(obj, dict):
        if "roots" in obj:
            return sum(count_nodes(x) for x in obj["roots"])
        n = 1
        for ch in obj.get("children") or []:
            n += count_nodes(ch)
        return n
    return 0


def tree(email, pw):
    tok, q = login(email, pw)
    url = f"{BASE}/org-tree?{q}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())


def main():
    a = tree("admin@tata.com", "123")
    e = tree("agrawal@tata.com", "agrawal")
    print("admin keys", list(a.keys()) if isinstance(a, dict) else type(a))
    print("admin node_count", count_nodes(a))
    print("agrawal node_count", count_nodes(e))
    print("agrawal top", json.dumps(e, indent=2)[:600])


if __name__ == "__main__":
    main()
