import requests

BASE_URL = "http://localhost:8000/api"

def test_crud():
    # 1. Login
    login_url = f"{BASE_URL}/auth/login"
    login_data = {"email": "admin@tata.com", "password": "123"}
    try:
        response = requests.post(login_url, json=login_data)
        response.raise_for_status()
        token = response.json().get("access_token")
        if not token:
            print("LOGIN: FAILED (No token)")
            return
        print("LOGIN: SUCCESS")
    except Exception as e:
        print(f"LOGIN: FAILED ({e})")
        return

    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get tree
    tree_url = f"{BASE_URL}/org-tree"
    try:
        response = requests.get(tree_url, headers=headers)
        response.raise_for_status()
        tree = response.json()
    except Exception as e:
        print(f"GET TREE: FAILED ({e})")
        return

    # 3. Find a PLANT node
    def find_plant(nodes):
        for node in nodes:
            if node.get("node_type") == "PLANT":
                return node.get("id")
            children = node.get("children", [])
            res = find_plant(children)
            if res: return res
        return None

    plant_id = find_plant(tree)
    if not plant_id:
        print("FIND PLANT: FAILED (No PLANT node found)")
        return
    print(f"FIND PLANT: SUCCESS (ID: {plant_id})")

    # 4. POST new node (TEAM)
    new_node_data = {
        "node_type": "TEAM",
        "name": "QA Team",
        "code": "QA01",
        "parent_id": plant_id
    }
    new_node_id = None
    try:
        response = requests.post(tree_url, json=new_node_data, headers=headers)
        if response.status_code == 201 or response.status_code == 200:
            new_node = response.json()
            new_node_id = new_node.get("id")
            print(f"CREATE: SUCCESS (ID: {new_node_id})")
        else:
            print(f"CREATE: FAILED ({response.status_code} - {response.text})")
            return
    except Exception as e:
        print(f"CREATE: FAILED ({e})")
        return

    # 5. PATCH (Update name)
    try:
        patch_url = f"{tree_url}/{new_node_id}"
        patch_data = {"name": "QA Team Updated"}
        response = requests.patch(patch_url, json=patch_data, headers=headers)
        if response.status_code == 200:
            print("PATCH: SUCCESS")
        else:
            print(f"PATCH: FAILED ({response.status_code} - {response.text})")
    except Exception as e:
        print(f"PATCH: FAILED ({e})")

    # 6. DELETE
    try:
        delete_url = f"{tree_url}/{new_node_id}"
        response = requests.delete(delete_url, headers=headers)
        if response.status_code == 200 or response.status_code == 204:
            print("DELETE: SUCCESS")
        else:
            print(f"DELETE: FAILED ({response.status_code} - {response.text})")
    except Exception as e:
        print(f"DELETE: FAILED ({e})")

if __name__ == "__main__":
    test_crud()
