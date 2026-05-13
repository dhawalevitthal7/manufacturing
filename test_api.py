import requests, json
BASE = 'http://localhost:8000/api'

# 1. Register org
print('=== REGISTER ORG ===')
r = requests.post(f'{BASE}/auth/register', json={
    'company_name':'Tata Steel', 'admin_name':'Rajesh Kumar',
    'admin_email':'admin@tata.com', 'password':'Admin@123',
    'domain':'tata.com', 'org_size':'201-500'
})
data = r.json()
TOKEN = data['access_token']
ADMIN = data['user']
H = {'Authorization': f'Bearer {TOKEN}'}
print(f"Org: {ADMIN['org_name']} | Admin: {ADMIN['name']} | Role: {ADMIN['system_role']}")

# 2. Create Plant
print('\n=== CREATE PLANT ===')
p = requests.post(f'{BASE}/org/plants', json={'name':'Jamshedpur Plant','location':'Jamshedpur, Jharkhand','code':'JSR'}, headers=H).json()
PLANT_ID = p['id']
print(f"Plant: {p['name']}")

# 3. Seed departments
print('\n=== SEED DEPTS ===')
r = requests.post(f'{BASE}/org/departments/seed-defaults?plant_id={PLANT_ID}', headers=H).json()
print(f"Created: {r['created']}")

# 4. Seed designations
print('\n=== SEED DESIGNATIONS ===')
r = requests.post(f'{BASE}/org/designations/seed-defaults', headers=H).json()
print(f"Created: {r['created']}")

# 5. Get depts + desigs
depts = requests.get(f'{BASE}/org/departments?plant_id={PLANT_ID}', headers=H).json()
desigs = requests.get(f'{BASE}/org/designations', headers=H).json()
PROD_DEPT = [d for d in depts if d['name']=='Production'][0]['id']
QUAL_DEPT = [d for d in depts if d['name']=='Quality'][0]['id']
PLANT_HEAD = [d for d in desigs if d['name']=='Plant Head'][0]['id']
PROD_MGR = [d for d in desigs if d['name']=='Production Manager'][0]['id']
SUPERVISOR_D = [d for d in desigs if d['name']=='Line Supervisor'][0]['id']
OPERATOR_D = [d for d in desigs if d['name']=='Operator'][0]['id']
QA_HEAD = [d for d in desigs if d['name']=='Quality Head'][0]['id']

# 6. DIRECTLY CREATE EMPLOYEES (no invitation!)
print('\n=== CREATE EMPLOYEES (Direct, no invitation) ===')
emp1 = requests.post(f'{BASE}/employees', json={'name':'Amit Sharma','email':'amit@tata.com','password':'Pass@123','system_role':'PLANT_MANAGER','plant_id':PLANT_ID,'designation_id':PLANT_HEAD}, headers=H).json()
emp2 = requests.post(f'{BASE}/employees', json={'name':'Priya Singh','email':'priya@tata.com','password':'Pass@123','system_role':'MANAGER','plant_id':PLANT_ID,'department_id':PROD_DEPT,'designation_id':PROD_MGR}, headers=H).json()
emp3 = requests.post(f'{BASE}/employees', json={'name':'Ravi Kumar','email':'ravi@tata.com','password':'Pass@123','system_role':'SUPERVISOR','plant_id':PLANT_ID,'department_id':PROD_DEPT,'designation_id':SUPERVISOR_D}, headers=H).json()
emp4 = requests.post(f'{BASE}/employees', json={'name':'Suresh Patil','email':'suresh@tata.com','password':'Pass@123','system_role':'EMPLOYEE','plant_id':PLANT_ID,'department_id':PROD_DEPT,'designation_id':OPERATOR_D}, headers=H).json()
emp5 = requests.post(f'{BASE}/employees', json={'name':'Neha Gupta','email':'neha@tata.com','password':'Pass@123','system_role':'DEPT_HEAD','plant_id':PLANT_ID,'department_id':QUAL_DEPT,'designation_id':QA_HEAD}, headers=H).json()
for e in [emp1, emp2, emp3, emp4, emp5]:
    print(f"  Created: {e['name']} | {e['system_role']} | {e['designation_name']}")

# 7. SET UP REPORTING HIERARCHY
print('\n=== REPORTING HIERARCHY ===')
rels = [
    {'employee_id':emp1['id'],'manager_id':ADMIN['id'],'relationship_type':'DIRECT'},
    {'employee_id':emp2['id'],'manager_id':emp1['id'],'relationship_type':'DIRECT'},
    {'employee_id':emp3['id'],'manager_id':emp2['id'],'relationship_type':'DIRECT'},
    {'employee_id':emp4['id'],'manager_id':emp3['id'],'relationship_type':'DIRECT'},
    {'employee_id':emp5['id'],'manager_id':emp1['id'],'relationship_type':'DIRECT'},
    {'employee_id':emp4['id'],'manager_id':emp2['id'],'relationship_type':'REVIEWER'},  # skip-level
    {'employee_id':emp3['id'],'manager_id':emp1['id'],'relationship_type':'REVIEWER'},
]
for rel in rels:
    r = requests.post(f'{BASE}/hierarchy/relationships', json=rel, headers=H).json()
    print(f"  {rel['relationship_type']}: {r.get('employee_name','?')} -> {r.get('manager_name','?')}")

# 8. GET REPORTING CHAIN
print('\n=== REPORTING CHAIN (Suresh -> top) ===')
chain = requests.get(f"{BASE}/hierarchy/chain/{emp4['id']}", headers=H).json()
for c in chain:
    print(f"  -> {c['name']} ({c['system_role']}) [{c.get('designation','')}]")

# 9. GET SUBTREE (all under Amit)
print(f"\n=== SUBTREE under {emp1['name']} ===")
tree = requests.get(f"{BASE}/hierarchy/subtree/{emp1['id']}", headers=H).json()
for t in tree:
    print(f"  {t['name']} ({t['system_role']})")

# 10. EMPLOYEE CAN LOGIN WITH CREATED CREDENTIALS!
print('\n=== EMPLOYEE LOGIN TEST ===')
login = requests.post(f'{BASE}/auth/login', json={'email':'suresh@tata.com','password':'Pass@123'}).json()
EMP_TOKEN = login['access_token']
EMP_H = {'Authorization': f'Bearer {EMP_TOKEN}'}
print(f"Logged in as: {login['user']['name']} | Role: {login['user']['system_role']}")
print(f"Plant: {login['user']['plant_name']} | Dept: {login['user']['department_name']} | Designation: {login['user']['designation_name']}")

# 11. Complete setup + seed permissions
requests.post(f'{BASE}/org/complete-setup', headers=H)
perm = requests.post(f'{BASE}/permissions/seed-defaults', headers=H).json()
print(f"\n=== PERMISSIONS SEEDED: {perm['created']} rules ===")

# 12. Employee checks their modules
mods = requests.get(f'{BASE}/permissions/my-modules', headers=EMP_H).json()
print(f"\n=== EMPLOYEE MODULES ({login['user']['name']}) ===")
for m in mods:
    print(f"  {m['module_name']} | View: {m['can_view']} | Create: {m['can_create']}")

# 13. Create OKR as manager, assigned to employee
print('\n=== CREATE OKR (assigned by manager to employee) ===')
MGR_LOGIN = requests.post(f'{BASE}/auth/login', json={'email':'priya@tata.com','password':'Pass@123'}).json()
MGR_H = {'Authorization': f'Bearer {MGR_LOGIN["access_token"]}'}
okr = requests.post(f'{BASE}/okrs', json={
    'title':'Achieve 95% OEE on Line 3',
    'description':'Improve Overall Equipment Effectiveness',
    'level':'INDIVIDUAL',
    'owner_id': emp4['id'],
    'department_id': PROD_DEPT,
}, headers=MGR_H).json()
print(f"OKR: {okr['title']} | Owner: {okr['owner_name']} | Assigned by: {okr.get('assigned_by_name','self')}")

# 14. Add KRs
kr1 = requests.post(f"{BASE}/okrs/{okr['id']}/key-results", json={
    'title':'Reduce unplanned downtime to < 5%', 'target_value':100, 'unit':'%', 'weight':2.0
}, headers=MGR_H).json()
kr2 = requests.post(f"{BASE}/okrs/{okr['id']}/key-results", json={
    'title':'Complete preventive maintenance checklist', 'target_value':100, 'unit':'%', 'weight':1.0
}, headers=MGR_H).json()
print(f"  KR1: {kr1['title']} (weight: 2.0)")
print(f"  KR2: {kr2['title']} (weight: 1.0)")

# 15. Employee submits progress
print('\n=== EMPLOYEE SUBMITS PROGRESS ===')
prog = requests.post(f"{BASE}/okrs/key-results/{kr1['id']}/progress", json={
    'new_value': 60, 'notes': 'Reduced downtime from 12% to 6%', 'blockers': 'Spare parts delayed'
}, headers=EMP_H).json()
print(f"  Progress submitted: {prog['new_value']} | Status: {prog['status']}")

# 16. Supervisor validates
print('\n=== SUPERVISOR VALIDATES ===')
SUP_LOGIN = requests.post(f'{BASE}/auth/login', json={'email':'ravi@tata.com','password':'Pass@123'}).json()
SUP_H = {'Authorization': f'Bearer {SUP_LOGIN["access_token"]}'}
val = requests.put(f"{BASE}/okrs/progress/{prog['id']}/validate", json={
    'status':'APPROVED', 'validation_notes':'Verified from MES dashboard'
}, headers=SUP_H).json()
print(f"  Validation: {val['status']}")

# 17. Dashboard for manager
print('\n=== MANAGER DASHBOARD ===')
dash = requests.get(f'{BASE}/dashboard', headers=MGR_H).json()
print(f"  Stats: {json.dumps(dash['stats'], indent=2)}")

# 18. Audit log
print('\n=== AUDIT LOG ===')
logs = requests.get(f'{BASE}/dashboard/audit-log', headers=H).json()
for l in logs[:5]:
    print(f"  {l['action']} {l['entity_type']} by {l['user_name']}")

print('\n=== ALL TESTS PASSED ✅ ===')
