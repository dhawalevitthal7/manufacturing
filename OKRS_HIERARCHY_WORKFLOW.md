# Hierarchy-Based OKR Workflow Implementation

## Overview

This implementation provides a strict hierarchy-based OKR creation, assignment, validation, and approval workflow for the manufacturing performance management platform. OKRs cascade from higher hierarchy levels to lower levels, with proper authorization and approval workflows.

## Hierarchy Structure

```
Organization Level
    ↓
Plant Level
    ↓
Department Level
    ↓
Team Level
    ↓
Individual/Employee Level
```

## OKR Levels and Creation Authority

### ORGANIZATION Level
- **Creator**: CEO, VP Operations, VP Manufacturing, Super Admin
- **Approver**: CEO, Super Admin
- **Visibility**: All users (organization-wide)
- **Cascades to**: PLANT level OKRs
- **Scope**: No plant/department/team scope
- **Parent**: None

### PLANT Level
- **Creator**: VP Operations, VP Manufacturing, Plant Head, Super Admin
- **Approver**: VP Operations, VP Manufacturing, Plant Head, Super Admin
- **Visibility**: Plant Head, VP-level, CEO, Super Admin
- **Cascades to**: DEPARTMENT level OKRs
- **Scope**: Must specify plant_id
- **Parent**: Optional ORGANIZATION OKR

### DEPARTMENT Level
- **Creator**: Plant Head, Department Head, Super Admin
- **Approver**: Department Head, Plant Head, VP-level, Super Admin
- **Visibility**: Department Head, Plant Head, VP-level, CEO, Super Admin
- **Cascades to**: TEAM level OKRs
- **Scope**: Must specify plant_id and department_id
- **Parent**: ORGANIZATION, PLANT, or DEPARTMENT OKR

### TEAM Level
- **Creator**: Department Head, Manager, Team Lead, Super Admin
- **Approver**: Manager, Department Head, Plant Head, VP-level, Super Admin
- **Visibility**: Team Lead, Manager, Department Head, Plant Head, VP-level, CEO, Super Admin
- **Cascades to**: INDIVIDUAL level OKRs
- **Scope**: Must specify plant_id, department_id, and team_id
- **Parent**: ORGANIZATION, PLANT, DEPARTMENT, or TEAM OKR

### INDIVIDUAL Level
- **Creator**: Manager, Team Lead, Supervisor, Super Admin
- **Assignable to**: Employees, Supervisors, Team Leads, Operators, Technicians
- **Approver**: Manager, Team Lead, Department Head, Plant Head, VP-level, Super Admin
- **Visibility**: Own OKRs + team OKRs + higher level organization OKRs
- **Cannot Cascade**: Individual OKRs cannot have children
- **Scope**: Must specify plant_id, department_id, and team_id
- **Parent**: Any level OKR

## OKR Workflow States

### Creation Workflow
```
1. CREATE (PENDING)
   ↓
2. AWAITING APPROVAL
   ├─ APPROVED → Ready for Assignment
   ├─ REVISION_REQUESTED → Creator revises
   └─ REJECTED → Process ends
   ↓
3. ASSIGNED (to owner)
   ↓
4. ACTIVE (tracking begins)
```

### Approval Chain
- OKRs require approval before becoming active
- Approval follows hierarchy: CEO for ORG → VP for PLANT → Plant Head for DEPT → Manager for TEAM
- Approvers receive notification of pending approvals
- Can approve, request revisions, or reject OKRs

### Progress Validation Workflow
```
Employee submits progress
   ↓
Team Lead/Manager validates
   ↓
Department Head validates (optional)
   ↓
Plant Head validates (for cross-team impact)
   ↓
APPROVED or REJECTED with notes
```

## API Endpoints

### Validation Endpoints

#### Check if user can create OKR at level
```
POST /api/okrs/hierarchy/validate/can-create
Query: user_id, okr_level, org_id
Response: {can_create, reason, allowed_levels}
```

#### Validate hierarchy chain
```
POST /api/okrs/hierarchy/validate/hierarchy-chain
Body: {okr_level, parent_id, plant_id, department_id, team_id}
Response: {valid, reason, suggested_parent}
```

#### Check if can assign OKR to user
```
POST /api/okrs/hierarchy/validate/can-assign
Query: creator_id, assignee_id, okr_level, org_id
Response: {can_assign, reason}
```

#### Check if can approve OKR
```
POST /api/okrs/hierarchy/validate/can-approve
Query: approver_id, okr_id, org_id
Response: {can_approve, reason, approval_chain}
```

### OKR Management Endpoints

#### Create OKR with hierarchy validation
```
POST /api/okrs/hierarchy/create
Body: {
    title: string,
    description: string,
    level: "ORGANIZATION"|"PLANT"|"DEPARTMENT"|"TEAM"|"INDIVIDUAL",
    owner_id: string,
    parent_id: string (optional),
    plant_id: string (if not ORGANIZATION),
    department_id: string (if DEPARTMENT/TEAM/INDIVIDUAL),
    team_id: string (if TEAM/INDIVIDUAL),
    cycle_id: string
}
Response: {id, title, level, owner_id, approval_chain, message}
```

#### Approve OKR creation
```
POST /api/okrs/hierarchy/{okr_id}/approve
Query: approver_id, org_id
Body: {approval_notes: string}
Response: {id, approval_status, approved_by, message}
```

#### Reject OKR with revision request
```
POST /api/okrs/hierarchy/{okr_id}/reject
Query: rejector_id, org_id
Body: {rejection_reason: string}
Response: {id, approval_status, rejection_reason}
```

#### Get eligible recipients for OKR assignment
```
GET /api/okrs/hierarchy/recipients
Query: okr_level, org_id, plant_id (optional), department_id (optional), team_id (optional)
Response: {level, recipients: [{id, name, email, role, plant_id, department_id, team_id}]}
```

#### Assign approved OKR to user
```
POST /api/okrs/hierarchy/{okr_id}/assign
Query: assignee_id, assigner_id, org_id
Response: {id, title, owner_id, owner_name, assigned_by}
```

### Visibility & Access Endpoints

#### Get all OKRs visible to user
```
GET /api/okrs/hierarchy/visible
Query: org_id, user_id
Response: {user_id, user_role, visible_okr_count, okrs: [...]}
```

#### Check if user can view specific OKR
```
POST /api/okrs/hierarchy/can-view/{okr_id}
Query: user_id
Response: {user_id, okr_id, can_view}
```

### Approval Chain Endpoints

#### Get approval chain for OKR
```
GET /api/okrs/hierarchy/{okr_id}/approval-chain
Query: org_id
Response: {okr_id, okr_level, approval_chain: [{role, user_id, user_name, email}], total_approvers}
```

#### Get suggested parent OKR
```
GET /api/okrs/hierarchy/{okr_id}/suggested-parent
Response: {suggested_parent_id, suggested_parent_title, suggested_parent_level}
```

### Progress Validation Endpoints

#### Validate progress update
```
POST /api/okrs/hierarchy/progress/{progress_id}/validate
Query: validator_id, org_id
Body: {validation_notes: string}
Response: {progress_id, status, validated_by, message}
```

## Configuration & Customization

### Permission Matrix Configuration

The system supports configurable OKR creation rights through the `RolePermissionRule` model:

```python
# Example: Allow Team Leads to create INDIVIDUAL OKRs
RolePermissionRule(
    org_id=org_id,
    role="TEAM_LEAD",
    permission_key="OKR_CREATE_INDIVIDUAL",
    can_create=True,
)
```

### Visibility Scope Control

Each OKR has a `visibility_scope` field:
- **STANDARD**: Visible to hierarchy members above the OKR level
- **RESTRICTED**: Visible only to direct management chain
- **PUBLIC**: Visible to all organization members

### Cascade Control

Each OKR has an `allows_cascade` flag:
- **true**: Can be used as parent for child-level OKRs
- **false**: Terminal OKR, cannot have children

## Validation Rules

### Hierarchy Chain Validation

1. **ORGANIZATION OKRs**
   - No parent allowed
   - No plant/department/team scope
   - Only one at organization level

2. **PLANT OKRs**
   - Must specify plant_id
   - Optional ORGANIZATION parent
   - Cannot span multiple plants

3. **DEPARTMENT OKRs**
   - Must specify plant_id and department_id
   - Parent must be in same plant (if PLANT/DEPT level)
   - Cannot have INDIVIDUAL parent

4. **TEAM OKRs**
   - Must specify plant_id, department_id, team_id
   - Parent must be in same hierarchy scope
   - Cannot span departments

5. **INDIVIDUAL OKRs**
   - Must specify plant_id, department_id, team_id
   - Assigned to specific employee
   - No children allowed
   - Can link to any parent at any level

### Assignment Validation

- Creator must have authority to create at that level
- Assignee must have visible scope that includes the OKR level
- No cross-plant assignment (unless VP-level/Super Admin)
- Assignee role must be capable of owning OKR at that level

## Error Handling

### Common Error Codes

- **403 Forbidden**: User lacks permission to create/assign/approve OKR
- **400 Bad Request**: Hierarchy chain invalid or missing required scope fields
- **404 Not Found**: OKR, parent, or user not found
- **422 Unprocessable Entity**: Invalid OKR level or scope

### Error Messages

All errors include descriptive messages explaining:
1. What operation was attempted
2. Why it failed (permission, hierarchy, validation)
3. What the user can do instead (allowed levels, prerequisites)

## Usage Examples

### Example 1: CEO Creates Organization OKR

```python
POST /api/okrs/hierarchy/create
{
    "title": "Increase manufacturing efficiency by 25%",
    "description": "Organization-wide efficiency improvement initiative",
    "level": "ORGANIZATION",
    "owner_id": "ceo123",
    "cycle_id": "cycle123"
}

Response:
{
    "id": "okr_org_001",
    "title": "Increase manufacturing efficiency by 25%",
    "level": "ORGANIZATION",
    "owner_id": "ceo123",
    "creation_approval_status": "PENDING",
    "approval_chain": [
        {"role": "CEO", "user_id": "ceo123", "user_name": "John CEO"},
        {"role": "SUPER_ADMIN", ...}
    ]
}
```

### Example 2: Plant Head Creates Department OKR

```python
POST /api/okrs/hierarchy/create
{
    "title": "Reduce production downtime to <2% by Q3",
    "description": "Maintenance team focused OKR",
    "level": "DEPARTMENT",
    "owner_id": "depthead456",
    "parent_id": "okr_plant_001",  # Links to Plant OKR
    "plant_id": "plant123",
    "department_id": "dept456",
    "cycle_id": "cycle123"
}

// Validation checks:
// 1. Plant Head can create DEPARTMENT OKRs ✓
// 2. Parent is PLANT level in same plant ✓
// 3. Plant/department scope provided ✓
// 4. Assignee (Dept Head) is in department ✓
```

### Example 3: Manager Assigns Team OKR to Employee

```python
// Step 1: Get eligible recipients
GET /api/okrs/hierarchy/recipients?okr_level=INDIVIDUAL&team_id=team789

Response:
{
    "level": "INDIVIDUAL",
    "recipients": [
        {"id": "emp1", "name": "Alice", "email": "alice@mfg.com", "role": "EMPLOYEE"},
        {"id": "emp2", "name": "Bob", "email": "bob@mfg.com", "role": "SUPERVISOR"}
    ]
}

// Step 2: Assign OKR
POST /api/okrs/hierarchy/okr789/assign
{
    "assignee_id": "emp1",
    "assigner_id": "mgr123"
}
```

### Example 4: Validate Employee Progress

```python
// Employee submits progress
POST /api/okrs/hierarchy/progress/progress_update_123/validate
{
    "validation_notes": "Good progress. On track for Q3 target."
}

// Manager validates. System checks:
// 1. Manager is hierarchy superior of employee ✓
// 2. Progress value is valid (0-100) ✓
// 3. OKR is not archived ✓
// Updates KR current_value and cascades to parent OKR
```

## Testing

### Test Scenarios

1. **Permission Testing**
   - CEO can create ORG OKRs but not PLANT OKRs (without permission override)
   - Employee cannot create TEAM OKRs
   - Plant Head can only see their own plant's OKRs (not other plants)

2. **Hierarchy Chain Testing**
   - DEPARTMENT OKR with INDIVIDUAL parent → Rejected
   - TEAM OKR in plant A linking to parent in plant B → Rejected
   - Orphan OKRs (no parent when required) → Rejected

3. **Assignment Testing**
   - Assign OKR to user outside assigned scope → Rejected
   - Assign pending OKR → Rejected (must be approved first)
   - Cross-plant assignment by Department Head → Rejected

4. **Approval Testing**
   - Non-approver tries to approve PLANT OKR → Rejected
   - Approver validates progress of subordinate → Approved
   - Cascade of approvals for nested OKRs

## Database Migrations

The following columns were added to support the hierarchy workflow:

### Objective Table
- `creation_approval_status`: PENDING|APPROVED|REJECTED|REVISION_REQUESTED
- `creation_approved_by_id`: FK to User
- `creation_approved_at`: Timestamp
- `creation_approval_notes`: Text
- `visibility_scope`: STANDARD|RESTRICTED|PUBLIC
- `allows_cascade`: Boolean

### ProgressUpdate Table
- `validation_level`: TEAM_LEAD|MANAGER|DEPT_HEAD|PLANT_HEAD|VP|CEO
- `validation_chain`: JSON array of validators
- `next_approver_role`: String
- `approved_at`: Timestamp

## Performance Considerations

1. **Caching**: Permission lookups are done per-request. Consider caching user permission profiles.
2. **Approval Chain**: Building approval chains queries multiple user records. Index by role and scope.
3. **Visibility Queries**: Use indexed queries on `org_id`, `level`, and scope fields.
4. **Progress Aggregation**: Pre-calculate progress scores for dashboard displays.

## Future Enhancements

1. **Batch OKR Creation**: Create multiple OKRs in one operation with validation
2. **OKR Templates**: Pre-defined OKR templates by level and department
3. **Approval Workflows**: Custom workflow rules (e.g., require 2 approvals at plant level)
4. **Delegation**: Allow delegation of approval authority temporarily
5. **OKR Linking**: Create cross-functional OKR links between different plants
6. **Periodic Sync**: Sync OKR progress up the hierarchy on schedule
