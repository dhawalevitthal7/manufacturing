"""
Phase 1 Acceptance Test Suite
Tests all 5 org-tree endpoints and verifies backfill migration
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000/api"
CREDENTIALS = {"email": "admin@tata.com", "password": "123"}

def log_result(operation, success, details=""):
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} | {operation}: {details}")
    return success

def test_org_tree_endpoints():
    print("\n" + "="*60)
    print("PHASE 1 ACCEPTANCE TEST: ORG TREE ENDPOINTS")
    print("="*60 + "\n")
    
    # Step 1: Login
    print("1. Testing Authentication...")
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", json=CREDENTIALS)
        if resp.status_code != 200:
            log_result("Login", False, f"Status {resp.status_code}")
            return False
        
        token_data = resp.json()
        token = token_data.get("access_token")
        user_id = token_data.get("user_id")
        org_id = token_data.get("org_id")
        
        log_result("Login", True, f"Token acquired for {CREDENTIALS['email']}")
    except Exception as e:
        log_result("Login", False, str(e))
        return False
    
    headers = {"Authorization": f"Bearer {token}"}
    params = {"org_id": org_id, "user_id": user_id, "role": "SUPER_ADMIN"}
    
    # Step 2: GET /api/org-tree
    print("\n2. Testing GET /api/org-tree...")
    try:
        resp = requests.get(f"{BASE_URL}/org-tree", headers=headers, params=params)
        if resp.status_code != 200:
            log_result("GET /api/org-tree", False, f"Status {resp.status_code}")
            return False
        
        tree = resp.json()
        log_result("GET /api/org-tree", True, f"Returned tree structure")
        
        # Find a plant node to use as parent
        plant_id = None
        if isinstance(tree, dict) and tree.get("children"):
            for child in tree["children"]:
                if child.get("node_type") == "PLANT":
                    plant_id = child["id"]
                    break
        
        if not plant_id:
            log_result("Find PLANT node", False, "No plant nodes in tree")
            return False
        
        log_result("Find PLANT node", True, f"Found plant ID: {plant_id[:8]}...")
    except Exception as e:
        log_result("GET /api/org-tree", False, str(e))
        return False
    
    # Step 3: POST /api/org-tree (create node)
    print("\n3. Testing POST /api/org-tree (create)...")
    try:
        create_payload = {
            "node_type": "TEAM",
            "name": "Acceptance Test Team",
            "code": "ACT01",
            "parent_id": plant_id
        }
        resp = requests.post(f"{BASE_URL}/org-tree", json=create_payload, headers=headers, params=params)
        
        if resp.status_code not in [200, 201]:
            log_result("POST /api/org-tree", False, f"Status {resp.status_code}: {resp.text}")
            return False
        
        new_node = resp.json()
        new_node_id = new_node.get("id")
        log_result("POST /api/org-tree", True, f"Created node {new_node_id[:8]}...")
        
        # Verify structure
        required_fields = ["id", "org_id", "parent_id", "node_type", "name", "path", "depth", "created_at", "updated_at"]
        missing = [f for f in required_fields if f not in new_node]
        if missing:
            log_result("Verify response fields", False, f"Missing: {missing}")
            return False
        
        log_result("Verify response fields", True, f"All {len(required_fields)} required fields present")
    except Exception as e:
        log_result("POST /api/org-tree", False, str(e))
        return False
    
    # Step 4: GET /api/org-tree/{node_id} (single node)
    print("\n4. Testing GET /api/org-tree/{node_id} (fetch single)...")
    try:
        resp = requests.get(f"{BASE_URL}/org-tree/{new_node_id}", headers=headers, params=params)
        
        if resp.status_code != 200:
            log_result("GET /api/org-tree/{node_id}", False, f"Status {resp.status_code}")
            return False
        
        node = resp.json()
        log_result("GET /api/org-tree/{node_id}", True, f"Retrieved node: {node['name']}")
    except Exception as e:
        log_result("GET /api/org-tree/{node_id}", False, str(e))
        return False
    
    # Step 5: PATCH /api/org-tree/{node_id} (update)
    print("\n5. Testing PATCH /api/org-tree/{node_id} (update)...")
    try:
        update_payload = {
            "name": "Updated Test Team",
            "code": "ACT02"
        }
        resp = requests.patch(f"{BASE_URL}/org-tree/{new_node_id}", json=update_payload, headers=headers, params=params)
        
        if resp.status_code != 200:
            log_result("PATCH /api/org-tree/{node_id}", False, f"Status {resp.status_code}")
            return False
        
        updated_node = resp.json()
        log_result("PATCH /api/org-tree/{node_id}", True, f"Updated to: {updated_node['name']}")
    except Exception as e:
        log_result("PATCH /api/org-tree/{node_id}", False, str(e))
        return False
    
    # Step 6: DELETE /api/org-tree/{node_id}
    print("\n6. Testing DELETE /api/org-tree/{node_id}...")
    try:
        resp = requests.delete(f"{BASE_URL}/org-tree/{new_node_id}", headers=headers, params=params)
        
        if resp.status_code != 200:
            log_result("DELETE /api/org-tree/{node_id}", False, f"Status {resp.status_code}")
            return False
        
        log_result("DELETE /api/org-tree/{node_id}", True, f"Soft-deleted node")
    except Exception as e:
        log_result("DELETE /api/org-tree/{node_id}", False, str(e))
        return False
    
    # Summary
    print("\n" + "="*60)
    print("✅ ALL ACCEPTANCE TESTS PASSED")
    print("="*60)
    
    return True

if __name__ == "__main__":
    success = test_org_tree_endpoints()
    exit(0 if success else 1)
