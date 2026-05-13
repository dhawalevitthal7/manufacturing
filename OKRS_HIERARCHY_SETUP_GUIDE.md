# OKR Hierarchy Workflow - Setup and Configuration Guide

## Quick Start Setup

This guide walks through setting up the hierarchy-based OKR system for your manufacturing organization.

## Step 1: Database Migration

Run the following migration to add the new fields to the Objective and ProgressUpdate tables:

```sql
-- Add approval workflow fields to objectives table
ALTER TABLE objectives ADD COLUMN creation_approval_status VARCHAR(50) DEFAULT 'PENDING';
ALTER TABLE objectives ADD COLUMN creation_approved_by_id VARCHAR(255) REFERENCES users(id);
ALTER TABLE objectives ADD COLUMN creation_approved_at TIMESTAMP NULL;
ALTER TABLE objectives ADD COLUMN creation_approval_notes TEXT;
ALTER TABLE objectives ADD COLUMN visibility_scope VARCHAR(50) DEFAULT 'STANDARD';
ALTER TABLE objectives ADD COLUMN allows_cascade BOOLEAN DEFAULT TRUE;

-- Add validation workflow fields to progress_updates table
ALTER TABLE progress_updates ADD COLUMN validation_level VARCHAR(50);
ALTER TABLE progress_updates ADD COLUMN validation_chain TEXT;
ALTER TABLE progress_updates ADD COLUMN next_approver_role VARCHAR(50);
ALTER TABLE progress_updates ADD COLUMN approved_at TIMESTAMP NULL;
```

## Step 2: Enable the Hierarchy Workflow Routes

The new routes are automatically enabled when you restart the server. They're mounted at:

- `/api/okrs/hierarchy/` - All hierarchy-based OKR endpoints
- `/api/okrs/` - Existing OKR endpoints (for backward compatibility)

## Step 3: Configure Role-Based Permissions

### Example 1: Default Manufacturing Organization Setup

```python
from server.database import SessionLocal
from server.models import RolePermissionRule
from datetime import datetime

db = SessionLocal()
org_id = "org_manufacturing_001"

# Define creation permissions for each role
permission_rules = [
    # CEO can create all OKR levels
    {"role": "CEO", "permission": "OKR_CREATE_ORGANIZATION", "can_create": True},
    {"role": "CEO", "permission": "OKR_CREATE_PLANT", "can_create": True},
    {"role": "CEO", "permission": "OKR_CREATE_DEPARTMENT", "can_create": True},
    
    # VP Operations can create PLANT and DEPARTMENT level
    {"role": "VP_OPERATIONS", "permission": "OKR_CREATE_PLANT", "can_create": True},
    {"role": "VP_OPERATIONS", "permission": "OKR_CREATE_DEPARTMENT", "can_create": True},
    
    # Plant Head can create up to TEAM level
    {"role": "PLANT_HEAD", "permission": "OKR_CREATE_PLANT", "can_create": True},
    {"role": "PLANT_HEAD", "permission": "OKR_CREATE_DEPARTMENT", "can_create": True},
    {"role": "PLANT_HEAD", "permission": "OKR_CREATE_TEAM", "can_create": True},
    
    # Department Head can create DEPARTMENT and TEAM level
    {"role": "DEPT_HEAD", "permission": "OKR_CREATE_DEPARTMENT", "can_create": True},
    {"role": "DEPT_HEAD", "permission": "OKR_CREATE_TEAM", "can_create": True},
    
    # Manager can create TEAM and INDIVIDUAL level
    {"role": "MANAGER", "permission": "OKR_CREATE_TEAM", "can_create": True},
    {"role": "MANAGER", "permission": "OKR_CREATE_INDIVIDUAL", "can_create": True},
    
    # Team Lead can create INDIVIDUAL level
    {"role": "TEAM_LEAD", "permission": "OKR_CREATE_INDIVIDUAL", "can_create": True},
    
    # Employees cannot create strategic OKRs
    {"role": "EMPLOYEE", "permission": "OKR_CREATE_INDIVIDUAL", "can_create": False},
]

for rule_data in permission_rules:
    rule = RolePermissionRule(
        org_id=org_id,
        role=rule_data["role"],
        permission_key=rule_data["permission"],
        can_create=rule_data["can_create"],
    )
    db.add(rule)

db.commit()
print("Permission rules configured successfully")
```

### Example 2: Allow Team Leads to Assign Operational OKRs

```python
from server.models import RolePermissionRule

# Enable Team Leads to assign operational execution OKRs to Operators
operational_rule = RolePermissionRule(
    org_id=org_id,
    role="TEAM_LEAD",
    permission_key="OKR_ASSIGN_OPERATIONAL_INDIVIDUAL",
    can_assign=True,
)
db.add(operational_rule)
db.commit()
```

## Step 3: Initialize User Permission Profiles

Before users can create or manage OKRs, their permission profiles must be configured:

```python
from server.models import UserPermissionProfile, Organization, User

def setup_user_permissions(org_id: str, user_id: str, system_role: str):
    """
    Setup permission profile for a user based on their role.
    """
    db = SessionLocal()
    
    # Determine scope type based on role
    scope_mapping = {
        "SUPER_ADMIN": "ORGANIZATION",
        "CEO": "ORGANIZATION",
        "VP_OPERATIONS": "ORGANIZATION",
        "VP_MANUFACTURING": "ORGANIZATION",
        "PLANT_HEAD": "PLANT",
        "OPERATIONS_HEAD": "PLANT",
        "DEPT_HEAD": "DEPARTMENT",
        "MANAGER": "TEAM",
        "TEAM_LEAD": "TEAM",
        "SUPERVISOR": "TEAM",
        "EMPLOYEE": "INDIVIDUAL",
        "OPERATOR": "INDIVIDUAL",
        "TECHNICIAN": "INDIVIDUAL",
    }
    
    scope_type = scope_mapping.get(system_role, "INDIVIDUAL")
    
    # Get user's hierarchy assignments
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        print(f"User {user_id} not found")
        return
    
    # Create or update permission profile
    profile = db.query(UserPermissionProfile).filter(
        UserPermissionProfile.user_id == user_id
    ).first()
    
    if not profile:
        profile = UserPermissionProfile(
            org_id=org_id,
            user_id=user_id,
            system_role=system_role,
            scope_type=scope_type,
            scoped_plant_id=user.plant_id if scope_type != "ORGANIZATION" else None,
            scoped_department_id=user.department_id if scope_type == "DEPARTMENT" else None,
            scoped_team_id=user.team_id if scope_type in ["TEAM", "INDIVIDUAL"] else None,
        )
        db.add(profile)
    else:
        profile.system_role = system_role
        profile.scope_type = scope_type
        profile.scoped_plant_id = user.plant_id if scope_type != "ORGANIZATION" else None
        profile.scoped_department_id = user.department_id if scope_type == "DEPARTMENT" else None
        profile.scoped_team_id = user.team_id if scope_type in ["TEAM", "INDIVIDUAL"] else None
    
    db.commit()
    print(f"Permission profile configured for {user.name} ({system_role}) - Scope: {scope_type}")


# Example usage:
setup_user_permissions("org_001", "ceo_user_001", "CEO")
setup_user_permissions("org_001", "plant_head_001", "PLANT_HEAD")
setup_user_permissions("org_001", "dept_head_001", "DEPT_HEAD")
setup_user_permissions("org_001", "manager_001", "MANAGER")
```

## Step 4: Configure OKR Visibility Rules

```python
from server.models import Objective

# Example: Set visibility scope for organization OKRs
org_okr = db.query(Objective).filter(Objective.id == "okr_org_001").first()
if org_okr:
    org_okr.visibility_scope = "PUBLIC"  # Visible to all organization members
    db.commit()

# Example: Set restricted visibility for sensitive strategic OKRs
strategic_okr = db.query(Objective).filter(Objective.id == "okr_strategic_001").first()
if strategic_okr:
    strategic_okr.visibility_scope = "RESTRICTED"  # Only visible to approval chain
    db.commit()
```

## Step 5: Test the Setup

### Test 1: Verify CEO can create ORGANIZATION OKR

```bash
curl -X POST http://localhost:8000/api/okrs/hierarchy/validate/can-create \
  -H "Authorization: Bearer <ceo_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "ceo_user_001",
    "okr_level": "ORGANIZATION",
    "org_id": "org_001"
  }'

# Expected response:
# {
#   "can_create": true,
#   "reason": "",
#   "user_role": "CEO",
#   "allowed_levels": ["ORGANIZATION"],
#   "requested_level": "ORGANIZATION"
# }
```

### Test 2: Verify Employee cannot create TEAM OKR

```bash
curl -X POST http://localhost:8000/api/okrs/hierarchy/validate/can-create \
  -H "Authorization: Bearer <employee_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "emp_user_001",
    "okr_level": "TEAM",
    "org_id": "org_001"
  }'

# Expected response:
# {
#   "can_create": false,
#   "reason": "Role 'EMPLOYEE' cannot create TEAM OKRs. Allowed levels: []",
#   "user_role": "EMPLOYEE",
#   "allowed_levels": [],
#   "requested_level": "TEAM"
# }
```

### Test 3: Create and approve an OKR

```bash
# Create OKR
curl -X POST http://localhost:8000/api/okrs/hierarchy/create \
  -H "Authorization: Bearer <ceo_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Increase production efficiency by 25%",
    "description": "Organization-wide manufacturing efficiency improvement",
    "level": "ORGANIZATION",
    "owner_id": "ceo_user_001",
    "cycle_id": "q3_2024"
  }'

# Response includes OKR ID and approval chain
# {
#   "id": "okr_org_001",
#   "title": "Increase production efficiency by 25%",
#   "level": "ORGANIZATION",
#   "creation_approval_status": "PENDING",
#   "approval_chain": [
#     {"role": "CEO", "user_id": "ceo_user_001", "user_name": "CEO Name"},
#     {"role": "SUPER_ADMIN", ...}
#   ]
# }

# Approve OKR
curl -X POST http://localhost:8000/api/okrs/hierarchy/okr_org_001/approve \
  -H "Authorization: Bearer <ceo_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "approval_notes": "Approved. Key initiative for Q3."
  }'

# Response:
# {
#   "id": "okr_org_001",
#   "creation_approval_status": "APPROVED",
#   "approved_by": "CEO Name",
#   "message": "OKR approval completed successfully"
# }
```

## Configuration Best Practices

### 1. Restrict ORGANIZATION OKR Creation

```python
# Only allow CEO and Super Admin to create organization-level OKRs
organization_rules = [
    {"role": "CEO", "permission": "OKR_CREATE_ORGANIZATION", "can_create": True},
    {"role": "SUPER_ADMIN", "permission": "OKR_CREATE_ORGANIZATION", "can_create": True},
]
```

### 2. Enable Plant Heads to Cascade OKRs

```python
# Allow Plant Heads to create and assign Plant/Department/Team level OKRs
plant_rules = [
    {"role": "PLANT_HEAD", "permission": "OKR_CREATE_PLANT", "can_create": True},
    {"role": "PLANT_HEAD", "permission": "OKR_CREATE_DEPARTMENT", "can_create": True},
    {"role": "PLANT_HEAD", "permission": "OKR_CREATE_TEAM", "can_create": True},
    {"role": "PLANT_HEAD", "permission": "OKR_ASSIGN_DEPARTMENT", "can_assign": True},
    {"role": "PLANT_HEAD", "permission": "OKR_ASSIGN_TEAM", "can_assign": True},
]
```

### 3. Configure Approval Escalation

```python
# For complex organizations, set up multiple approval levels
# Example: Department OKR requires both Dept Head and Plant Head approval

approval_chains = [
    {
        "okr_level": "DEPARTMENT",
        "approval_sequence": [
            {"role": "DEPT_HEAD", "order": 1},
            {"role": "PLANT_HEAD", "order": 2},
            {"role": "VP_OPERATIONS", "order": 3},
        ]
    }
]
```

### 4. Restrict Visibility for Sensitive OKRs

```python
# Mark strategic/confidential OKRs as RESTRICTED visibility
sensitive_okrs = [
    "okr_strategic_001",  # Strategic cost reduction initiative
    "okr_restructure_001",  # Organizational restructuring
]

for okr_id in sensitive_okrs:
    okr = db.query(Objective).filter(Objective.id == okr_id).first()
    if okr:
        okr.visibility_scope = "RESTRICTED"
        db.commit()
```

## Troubleshooting

### Issue: "User permission profile not configured"

**Solution**: Create a permission profile for the user:

```python
from server.okr_hierarchy_workflow import OKRHierarchyWorkflow
from server.models import UserPermissionProfile

user = db.query(User).filter(User.id == user_id).first()
profile = UserPermissionProfile(
    org_id=user.org_id,
    user_id=user.id,
    system_role=user.system_role,
    scope_type="ORGANIZATION" if user.system_role == "CEO" else "PLANT",
)
db.add(profile)
db.commit()
```

### Issue: "Cannot assign OKR to user in different plant"

**Solution**: Either:
1. Assign to user in same plant, or
2. Use VP-level user who has cross-plant authority

### Issue: "OKR must be APPROVED before assignment"

**Solution**: Approve the OKR first using the approval endpoint, then assign it.

## Advanced Configuration

### Custom Approval Workflows

To implement custom approval workflows (e.g., require 2 approvals):

```python
# 1. Create custom approval metadata on OKR
okr.creation_approval_notes = json.dumps({
    "requires_multiple_approval": True,
    "required_approvals": 2,
    "current_approvals": 1
})

# 2. Check before allowing to activate
approvals_needed = metadata.get("required_approvals", 1)
if current_approvals < approvals_needed:
    return {"can_activate": False, "reason": f"Needs {approvals_needed - current_approvals} more approvals"}
```

### Organization-Specific Permission Models

Different organizations may want different permission models:

```python
# Model 1: Strict hierarchy (this implementation)
# - Only hierarchical superiors can approve
# - Creation rights tied to role

# Model 2: Flexible authority
# - Configure custom approval chains per OKR level
# - Allow delegation of approval authority

# Model 3: Matrix organization
# - Support multiple reporting lines
# - Allow approvals from dotted-line managers
```

## Production Deployment Checklist

- [ ] Database migrations completed
- [ ] User permission profiles configured for all users
- [ ] Role-based permission rules defined
- [ ] OKR visibility scope configured
- [ ] Approval workflows tested
- [ ] Cross-hierarchy access controls validated
- [ ] Progress validation workflow tested
- [ ] Audit logging enabled
- [ ] Performance tuning completed
- [ ] Documentation reviewed with stakeholders

## Support and Maintenance

For issues or questions:

1. Check the [OKRS_HIERARCHY_WORKFLOW.md](./OKRS_HIERARCHY_WORKFLOW.md) documentation
2. Review test cases in [OKRS_HIERARCHY_TESTING.py](./OKRS_HIERARCHY_TESTING.py)
3. Consult error messages and use validation endpoints to debug
4. Review audit logs for permission-related issues
