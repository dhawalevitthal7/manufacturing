import requests
import json

BASE_URL = 'http://localhost:5000'

def test_org_tree_full():
    # 1. Login
    login_data = {'email': 'admin@tata.com', 'password': '123'}
    res = requests.post(f'{BASE_URL}/api/login', json=login_data)
    if res.status_code != 200:
        print(f'Login failed: {res.status_code}')
        return
    token = res.json().get('token')
    headers = {'Authorization': f'Bearer {token}'}
    print('1. Login: Success')

    # 2. Get org tree
    res = requests.get(f'{BASE_URL}/api/org-tree', headers=headers)
    if res.status_code != 200:
        print(f'Get org tree failed: {res.status_code}')
        return
    tree = res.json()
    print('2. Get Org Tree: Success')

    # 3. Extract a parent node (looking for a Plant node - usually level 1 or 2)
    def find_parent(nodes):
        for node in nodes:
            if node.get('type') == 'PLANT':
                return node
            if 'children' in node:
                found = find_parent(node['children'])
                if found: return found
        return None

    parent_node = find_parent(tree)
    if not parent_node:
        # Fallback to the root if no plant is found
        parent_node = tree[0] if tree else None
    
    if not parent_node:
        print('No parent node found')
        return
    
    parent_id = parent_node['id']
    print(f'3. Parent Node Found: {parent_node.get("name")} (ID: {parent_id})')

    # 4. POST /api/org-tree: Create Team node
    new_node_data = {
        'name': 'Test Team',
        'code': 'TST01',
        'type': 'TEAM',
        'parent_id': parent_id
    }
    res = requests.post(f'{BASE_URL}/api/org-tree', json=new_node_data, headers=headers)
    if res.status_code not in [200, 201]:
        print(f'Create node failed: {res.status_code} {res.text}')
        return
    new_node = res.json()
    new_node_id = new_node.get('id')
    print(f'4. Create Node: Success (ID: {new_node_id})')

    # 5. PATCH /api/org-tree/{id}: Update name
    update_data = {'name': 'Updated Test Team'}
    res = requests.patch(f'{BASE_URL}/api/org-tree/{new_node_id}', json=update_data, headers=headers)
    if res.status_code != 200:
        print(f'Update node failed: {res.status_code} {res.text}')
        return
    print('5. Update Node: Success')

    # 6. DELETE /api/org-tree/{id}
    res = requests.delete(f'{BASE_URL}/api/org-tree/{new_node_id}', headers=headers)
    if res.status_code not in [200, 204]:
        print(f'Delete node failed: {res.status_code} {res.text}')
        return
    print('6. Delete Node: Success')

    print('\nAll 5 operations completed successfully.')

if __name__ == '__main__':
    test_org_tree_full()
