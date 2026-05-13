# RBAC System - Quick Start & Testing Guide

## What Was Implemented

### Problem Solved ✅
- **Issue**: SUPER_ADMIN couldn't see any fields or access options after registration
- **Root Cause**: No permission initialization system; hardcoded role-to-page mapping
- **Solution**: Enterprise-grade RBAC with comprehensive permission profiles

### Key Features Implemented

1. **Automatic Permission Initialization**
   - When SUPER_ADMIN registers → all permissions automatically granted
   - When any user logs in → full permission profile loaded from DB
   - Permissions stored persistently in `UserPermissionProfile` table

2. **User Invitation System**
   - Invite users with pre-assigned roles and hierarchy scope
   - Email-based with secure token
   - Automatic permission initialization on acceptance
   - User immediately has their assigned capabilities after creating account

3. **Granular Permission Control**
   - Per-module granular permissions: can_view, can_create, can_edit, can_approve, can_delete
   - User capability flags: can_create_plants, can_invite_employees, etc.
   - Hierarchy scope: can assign users to specific plants/departments/teams

4. **Flexible Role-Based System**
   - 10 built-in roles with sensible defaults
   - Organization-specific customization via ModuleAccess table
   - NOT hardcoded - fully configurable

## How It Works Now

### Registration Flow
```
1. User registers (admin_name, admin_email, password, company_name)
2. Backend creates: Organization + User (SUPER_ADMIN)
3. System initializes: UserPermissionProfile with all capabilities
4. Response includes: User object + complete permission profile
5. Frontend: Auth store loads permissions → UI shows all options
```

### Login Flow
```
1. User logs in (email, password)
2. Backend fetches: User + initializes/updates UserPermissionProfile
3. Response includes: User object + complete permission profile
4. Frontend: Auth store loads permissions → UI renders based on permissions
```

### User Invitation Flow
```
1. SUPER_ADMIN/HR_HEAD invites: POST /api/permissions/invitations
   {
     "invited_email": "user@company.com",
     "system_role": "MANAGER",
     "plant_id": "plant-123"  # optional
   }
2. System creates: UserInvitation with 7-day expiration token
3. Email sent: (TODO: implement email service)
4. User receives: Invitation link with token
5. User accepts: POST /api/permissions/invitations/accept
   {
     "invitation_token": "...",
     "name": "John Manager",
     "password": "SecurePass123"
   }
6. System creates: User account + initializes UserPermissionProfile
7. User can log in: Permissions automatically load
```

## Testing the System

### Test 1: Register as SUPER_ADMIN

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Acme Manufacturing",
    "admin_name": "John Admin",
    "admin_email": "admin@acme.com",
    "password": "AdminPass123",
    "domain": "acme.com",
    "org_size": "500-1000"
  }'

# Response should include:
{
  "access_token": "...",
  "user": {
    "id": "user-123",
    "email": "admin@acme.com",
    "system_role": "SUPER_ADMIN",
    "permissions": {
      "can_view_all_plants": true,
      "can_view_all_departments": true,
      "can_create_plants": true,
      "can_create_departments": true,
      "can_invite_employees": true,
      "can_assign_roles": true,
      "modules": [
        {
          "module_key": "ORG_OKRS",
          "can_view": true,
          "can_create": true,
          "can_edit": true,
          "can_approve": true,
          "can_delete": true
        },
        // ... all other modules
      ]
    }
  }
}
```

**Expected**: `can_view_all_plants`, `can_create_plants`, all other admin flags = true

### Test 2: Check SUPER_ADMIN Permissions

```bash
# Get complete permission profile
curl -X GET http://localhost:8000/api/permissions/my-permissions \
  -H "Authorization: Bearer {access_token}"

# Should return: Complete UserPermissionProfile with all TRUE flags
```

### Test 3: Invite User with MANAGER Role

```bash
curl -X POST http://localhost:8000/api/permissions/invitations \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "invited_email": "manager@acme.com",
    "system_role": "MANAGER",
    "plant_id": "plant-123",
    "department_id": "dept-456",
    "team_id": "team-789"
  }'

# Response:
{
  "id": "inv-123",
  "email": "manager@acme.com",
  "status": "PENDING",
  "token": "secure-token-123",
  "expires_at": "2026-05-17T10:00:00"
}
```

### Test 4: Accept Invitation and Create Account

```bash
curl -X POST http://localhost:8000/api/permissions/invitations/accept \
  -H "Content-Type: application/json" \
  -d '{
    "invitation_token": "secure-token-123",
    "name": "Jane Manager",
    "password": "ManagerPass123"
  }'

# Response:
{
  "access_token": "...",
  "user": {
    "id": "user-456",
    "email": "manager@acme.com",
    "system_role": "MANAGER",
    "permissions": {
      "scope_type": "TEAM",
      "scoped_team_id": "team-789",
      "can_view_all_plants": false,
      "can_create_plants": false,
      "can_create_teams": false,
      "modules": [
        {
          "module_key": "TEAM_OKRS",
          "can_view": true,
          "can_create": true,
          "can_edit": false,
          "can_approve": false,
          "can_delete": false
        },
        // ... manager-allowed modules
      ]
    }
  }
}
```

**Expected**: 
- `scope_type` = "TEAM"
- `scoped_team_id` = "team-789"
- `can_create_plants` = false
- `TEAM_OKRS` module with limited permissions

### Test 5: Update User Permission via API

```bash
# Admin updates user's role from MANAGER to DEPT_HEAD
curl -X PUT http://localhost:8000/api/permissions/user/user-456/permissions \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "system_role": "DEPT_HEAD",
    "department_id": "dept-456"
  }'

# User's permission profile immediately updated in DB
# Next time user logs in → new permissions loaded
```

## Frontend Integration

### Update Sidebar to Use Permissions

```typescript
// In app-sidebar.tsx
export function AppSidebar() {
  const { hasModule, canCreate, hasCapability } = useAuthStore();
  
  // Filter navigation items based on permissions
  const visibleItems = NAV.map(group => ({
    ...group,
    items: group.items.filter(item => {
      // Must have module view access
      if (!hasModule(item.module)) return false;
      // Special handling for admin-only items
      if (item.requiresAdmin && !hasCapability('can_configure_permissions')) {
        return false;
      }
      return true;
    })
  })).filter(g => g.items.length > 0);

  return (
    // ... render filtered items
  );
}
```

### Show/Hide Fields Based on Permissions

```typescript
// In any component
function EmployeeManagement() {
  const { canCreate, canDelete } = useAuthStore();

  return (
    <div>
      {canCreate('EMPLOYEE_DIRECTORY') && (
        <button onClick={createEmployee}>Add Employee</button>
      )}
      
      {canDelete('EMPLOYEE_DIRECTORY') && (
        <button onClick={deleteEmployee}>Delete</button>
      )}
    </div>
  );
}
```

### Check Capabilities

```typescript
function AdminSettings() {
  const { hasCapability } = useAuthStore();

  return (
    <div>
      {hasCapability('can_create_plants') && (
        <PlantManagement />
      )}
      
      {hasCapability('can_invite_employees') && (
        <UserInvitation />
      )}
      
      {hasCapability('can_configure_permissions') && (
        <PermissionMatrix />
      )}
    </div>
  );
}
```

## Database Verification

### Check Permission Profile Creation

```sql
-- Verify SUPER_ADMIN has permission profile
SELECT * FROM user_permission_profiles 
WHERE system_role = 'SUPER_ADMIN';

-- Should show: all can_* flags = True, all modules in module_permissions JSON

-- Verify invited user's permissions
SELECT * FROM user_permission_profiles 
WHERE user_id = 'invited-user-id';

-- Should show: Limited permissions based on role
```

## Next Steps

1. **Frontend Integration** (Required)
   - Update sidebar to filter nav items with `hasModule()`
   - Update forms to show/hide fields with `canCreate()`, `canEdit()`
   - Add invitation UI in admin panel

2. **Email Integration** (Required for invitations)
   - Send actual invitation emails
   - Include secure token in link
   - Set up email templates

3. **Audit Trail** (Recommended)
   - Log all permission changes
   - Log user invitations and acceptances
   - Compliance reporting

4. **UI Components** (Recommended)
   - PermissionGate component - conditionally render based on permissions
   - PermissionButton - button that disables if no permission
   - Ready-made invitation form

5. **Testing**
   - Test each role's default permissions
   - Test custom ModuleAccess configurations
   - Test permission change effectiveness
   - Security testing (frontend + backend validation)

## Troubleshooting

### SUPER_ADMIN sees permission denied
- Check `UserPermissionProfile` exists and has `can_view_all_*` = true
- Verify `initialize_user_permissions()` was called on registration
- Check `permissions_service.py` `DEFAULT_ROLE_CAPABILITIES["SUPER_ADMIN"]`

### Invited user doesn't see permissions
- User must accept invitation and create account
- Check `UserInvitation.status` = "ACCEPTED"
- Verify `UserPermissionProfile` was created for new user
- User must re-login to get new permissions (JWT doesn't update on role change)

### Changes not reflected immediately
- Frontend: Changes only apply after page refresh or re-login
- Consider adding "Refresh Permissions" button that calls API
- Token-based auth means frontend doesn't auto-update

## API Endpoints Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/auth/register` | POST | Register new org + SUPER_ADMIN |
| `/api/auth/login` | POST | Login + load permissions |
| `/api/permissions/my-permissions` | GET | Get complete permission profile |
| `/api/permissions/my-modules` | GET | Get only module list |
| `/api/permissions/invitations` | POST | Create invitation |
| `/api/permissions/invitations/accept` | POST | Accept invitation |
| `/api/permissions/invitations` | GET | List all invitations |
| `/api/permissions/user/{id}/permissions` | PUT | Update user permissions |
| `/api/permissions/user/{id}/profile` | GET | View other user's permissions |

## Success Criteria

✅ SUPER_ADMIN registers → sees all modules, all fields  
✅ SUPER_ADMIN can see "Create Plant", "Invite Employee", "Assign Roles" options  
✅ Users invited with specific roles → see only their permitted fields  
✅ Role changes immediately → reflect in DB, effective after next login  
✅ Permission matrix stored in DB → persists across server restarts  
