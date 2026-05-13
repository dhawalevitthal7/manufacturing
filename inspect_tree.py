import requests
import json

base_url = 'http://localhost:5000'

def inspect_tree():
    # 1. Login
    login_url = f'{base_url}/api/auth/login'
    login_data = {'email': 'admin@tata.com', 'password': '123'}
    
    session = requests.Session()
    response = session.post(login_url, json=login_data)
    
    if response.status_code != 200:
        print(f'Login failed: {response.status_code}')
        print(response.text)
        return

    print('Login successful')

    # 2. Get org-tree
    tree_url = f'{base_url}/api/org-tree'
    response = session.get(tree_url)

    if response.status_code != 200:
        print(f'Failed to get org-tree: {response.status_code}')
        print(response.text)
        return

    data = response.json()

    # 4. Print the type of the root response object
    print(f'Root response object type: {type(data)}')

    # 3. Print the full JSON response structure
    print('Response structure:')
    print(json.dumps(data, indent=2))

if __name__ == '__main__':
    inspect_tree()
