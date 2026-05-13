# Enterprise RBAC Implementation Guide

## Overview

This document describes the comprehensive role-based access control (RBAC) system implemented for the Manufacturing Performance OS.

**Key Principle**: Instead of hardcoded `role = page`, the system implements:
```
role/designation + permissions + hierarchy scope + module visibility = workspace experience
```

## What Changed

### Backend Changes

#### 1. New Database Tables

**`UserPermissionProfile`** - Complete permission snapshot for each user
- Stores role, designation, hierarchy scope, and all capabilities
- Updated whenever user role is changed
- Queried on every permission check

**`UserInvitation`** - Tracks user invitations with pre-assigned roles
- Email-based invitation system
- Automatic permission initialization when user accepts
- 7-day expiration

#### 2. New Permissions Service (`permissions_service.py`)

Centralized permission logic with:
- `DEFAULT_ROLE_CAPABILITIES` - Base capabilities for each role
- `initialize_user_permissions()` - Create/update permission profile
- `get_user_permission_profile()` - Retrieve complete permissions
- `can_user_access_module()` - Check specific actions

#### 3. New Routes

**Permission Profile Routes**
- `GET /api/permissions/my-modules` - Get user's module access
- `GET /api/permissions/my-permissions` - Get complete permission profile
- `GET /api/permissions/user/{id}/profile` - Admin: get other user's permissions
- `PUT /api/permissions/user/{id}/permissions` - Admin: update user permissions

**Invitation Routes**
- `POST /api/permissions/invitations` - Create invitation
- `POST /api/permissions/invitations/accept` - Accept invitation and create account
- `GET /api/permissions/invitations` - List all invitations
- `DELETE /api/permissions/invitations/{id}` - Revoke invitation

#### 4. Auth Changes

When user registers or logs in:
1. Permission profile is automatically initialized
2. Full permission profile included in `user` response
3. User sees all available modules based on role

### Frontend Changes

#### 1. Enhanced API Types

Added comprehensive permission types:
```typescript
ModulePermission - Granular permissions per module
UserPermissionProfile - Complete user permission snapshot
UserInvitationCreate - For inviting users
UserPermissionUpdate - For updating user permissions
```

#### 2. Updated Auth Store

New permission checking methods:
```typescript
// Check module access
canView(moduleKey)        // can view module
canCreate(moduleKey)      // can create in module
canEdit(moduleKey)        // can edit in module
canApprove(moduleKey)     // can approve in module
canDelete(moduleKey)      // can delete in module

// Check capabilities
hasCapability(capability)   // e.g., can_create_plants, can_invite_employees
```

#### 3. New Permission Methods in APIClient
```typescript
getMyPermissions()                    // Get complete profile
getUserPermissions(userId)            // Admin: get other user
updateUserPermissions(userId, update) // Admin: update user
inviteUser(invitation)                // Send invitation
acceptInvitation(token)               // Accept and create account
listInvitations()                     // Admin: list all
revokeInvitation(id)                  // Admin: revoke
```

## System Architecture

### Permission Resolution Flow

```
Login → Initialize/Update Permission Profile
        ↓
        Get UserPermissionProfile from DB
        ↓
        Merge: role capabilities + designation rules + ModuleAccess rules
        ↓
        Return complete profile to frontend
        ↓
Frontend: Use permissions to show/hide UI elements
```

### Role Hierarchy

Built-in roles (customizable via ModuleAccess):
1. **SUPER_ADMIN** - Organization creator, full access
2. **CEO** - Strategic oversight
3. **VP_OPERATIONS** - Multi-plant oversight
4. **PLANT_HEAD** - Plant-level ownership
5. **DEPT_HEAD** - Department execution
6. **MANAGER** - Team execution
7. **TEAM_LEAD** - Operational coordination
8. **SUPERVISOR** - Shift execution
9. **EMPLOYEE** - Individual participation
10. **HR_HEAD** - Performance governance

### Visibility Matrix

Each role CAN SEE and CAN DO specific things:

**SUPER_ADMIN (Example)**
- Can see: All plants, departments, teams, employees, OKRs, reviews
- Can do: Create anything, configure permissions, invite employees, assign roles
- Modules: ALL modules with full permissions

**PLANT_HEAD (Example)**
- Can see: Plant details, department OKRs, team execution, reviews
- Can do: Create plant OKRs, approve department OKRs, monitor execution
- Hierarchy scope: Restricted to assigned plant
- Modules: Limited set

## Usage Examples

### Frontend: Show Fields Based on Permissions

```typescript
// In a component
import { useAuthStore } from '@/lib/stores/auth-store';

function OrganizationSetup() {
  const { permissions, hasCapability, canCreate } = useAuthStore();

  return (
    <div>
      {hasCapability('can_create_plants') && (
        <button>+ Create Plant</button>
      )}
      
      {hasCapability('can_invite_employees') && (
        <button>Invite Employee</button>
      )}
      
      {canCreate('ORG_OKRS') && (
        <section>Create Organization OKRs</section>
      )}
    </div>
  );
}
```

### Backend: Invite User with Pre-assigned Role

```python
# Via API
POST /api/permissions/invitations
{
  "invited_email": "manager@company.com",
  "system_role": "MANAGER",
  "plant_id": "plant-123",
  "department_id": "dept-456",
  "team_id": "team-789"
}

# Response includes invitation token for email link
# User accepts via: POST /api/permissions/invitations/accept
# {
#   "invitation_token": "...",
#   "name": "John Manager",
#   "password": "SecurePassword123"
# }
```

### Backend: Update User Permissions

```python
PUT /api/permissions/user/{user_id}/permissions
{
  "system_role": "DEPT_HEAD",
  "designation_id": "desig-123",
  "plant_id": "plant-456",
  "department_id": "dept-789"
}

# Permission profile automatically updated
# User immediately sees new UI on next page load
```

### Frontend: Check Granular Permissions

```typescript
const { canView, canCreate, canApprove } = useAuthStore();

if (canView('REVIEW_DASHBOARD')) {
  // Show reviews tab
}

if (canCreate('TEAM_OKRS')) {
  // Show create button
}

if (canApprove('APPROVAL_QUEUE')) {
  // Show approve button
}
```

## Migration Guide

### For Existing Installations

1. **Database Migration**
   - Tables are created on first app run (Alembic migration recommended for production)

2. **Seed Default Permissions**
   ```bash
   curl -X POST http://localhost:8000/api/permissions/seed-defaults \
     -H "Authorization: Bearer {admin_token}"
   ```

3. **Register as SUPER_ADMIN**
   - First registration creates organization and SUPER_ADMIN user
   - Automatic permission initialization
   - Can now see all modules

4. **Invite Employees**
   - Use API to invite with pre-assigned roles
   - System sends invitation link with token
   - User accepts and creates account with assigned permissions

### For New Installations

1. User registers → SUPER_ADMIN created with full permissions
2. SUPER_ADMIN can immediately see all configuration options
3. SUPER_ADMIN invites other users with specific roles
4. Invited users automatically get assigned permissions on acceptance

## Configuration

### Customize Role Capabilities

Edit `DEFAULT_ROLE_CAPABILITIES` in `permissions_service.py`:

```python
DEFAULT_ROLE_CAPABILITIES = {
    "YOUR_ROLE": {
        "scope_type": "ORGANIZATION",  # or PLANT, DEPARTMENT, TEAM, INDIVIDUAL
        "can_view_all_plants": True,
        "can_create_plants": False,
        # ... other capabilities ...
        "modules": [
            "ORG_OKRS", "PLANT_OKRS", # ... accessible modules
        ]
    }
}
```

### Configure Module Access per Organization

Organizations can override defaults:

```typescript
// Via API
POST /api/permissions/access
{
  "module_id": "mod-123",
  "system_role": "MANAGER",
  "can_view": true,
  "can_create": true,
  "can_edit": false,
  "can_approve": false,
  "can_delete": false
}
```

## UI Implementation Checklist

- [ ] Sidebar: Filter nav items based on `hasModule()`
- [ ] Dashboard: Show cards based on `permissions.scope_type`
- [ ] Forms: Disable fields user can't edit with `canEdit()`
- [ ] Buttons: Show create/approve buttons only if permitted
- [ ] Tables: Filter rows based on user's hierarchy scope
- [ ] Settings: Show admin options only if `can_configure_permissions`

## Security Notes

- ✅ Permissions are checked on every login
- ✅ Frontend checks are UI-only (backend validates all requests)
- ✅ Backend middleware injects `user_id`, `org_id` from JWT
- ✅ All permission endpoints check requester authorization
- ✅ Sensitive data filtered based on user's hierarchy scope
- ⚠️ Frontend should never trust local permissions - always validate on backend

## Troubleshooting

### User can't see fields after role change
1. User needs to refresh page or re-login
2. Permission profile only updated on login
3. Consider adding "refresh permissions" button

### Invitation expires before accepting
- Default: 7 days
- Edit `UserInvitation.expires_at` calculation in `routes_permissions.py`

### SUPER_ADMIN still can't see certain modules
1. Check DEFAULT_MODULES list is seeded
2. Verify `seed-defaults` was called
3. Check permission profile was initialized on registration

## Next Steps

1. **Email Integration** - Send actual invitation emails with tokens
2. **Role Templates** - Pre-configured role bundles
3. **Delegation** - Allow managers to temporarily grant permissions
4. **Audit Trail** - Log all permission changes
5. **UI Components** - Ready-made permission-aware form fields
