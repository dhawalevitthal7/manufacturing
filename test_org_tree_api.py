import requests
import json

def test_org_tree():
    login_url = "http://localhost:8000/api/auth/login"
    tree_url = "http://localhost:8000/api/org-tree"
    
    login_payload = {
        "email": "admin@tata.com",
        "password": "123"
    }

    try:
        # 1. Login
        print(f"Logging in to {login_url}...")
        login_response = requests.post(login_url, json=login_payload)
        login_response.raise_for_status()
        token = login_response.json().get("access_token")
        
        if not token:
            print("Login failed: Access token not found in response.")
            return

        # 2. Get Org Tree
        print("Fetching org tree...")
        headers = {"Authorization": f"Bearer {token}"}
        tree_response = requests.get(tree_url, headers=headers)
        tree_response.raise_for_status()
        tree_data = tree_response.json()

        # 3. Print Response JSON
        print("\nOrg Tree Response:")
        print(json.dumps(tree_data, indent=2))

        # 4. Check for fields
        def validate_node(node):
            required_fields = ["node_type", "path", "depth", "children"]
            for field in required_fields:
                if field not in node:
                    print(f"Error: Missing field '{field}' in node: {node.get('name', 'Unknown')}")
            
            for child in node.get("children", []):
                validate_node(child)

        if isinstance(tree_data, list):
            for root_node in tree_data:
                validate_node(root_node)
        elif tree_data:
            validate_node(tree_data)
        else:
            print("Info: Tree is empty.")
            
        print("\nValidation complete.")

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        if hasattr(e, 'response') and e.response is not None:
             print(f"Response status: {e.response.status_code}")
             print(f"Response body: {e.response.text}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    test_org_tree()
