# RBAC Frontend Implementation Examples

## Example 1: Updated App Sidebar

### Before (Old - All roles see all nav items)
```typescript
export function AppSidebar() {
  const collapsed = useUIStore((s) => s.sidebarCollapsed);
  const toggle = useUIStore((s) => s.toggleSidebar);
  const hasModule = useAuthStore((s) => s.hasModule);  // ⚠️ This was just checking if key exists
  const user = useAuthStore((s) => s.user);
  const path = useRouterState({ select: (r) => r.location.pathname });

  const groups = NAV.map((g) => ({
    ...g,
    items: g.items.filter((i) => hasModule(i.module)),  // ⚠️ All items likely passed
  })).filter((g) => g.items.length > 0);

  // ... rest of component
}
```

### After (New - Only show items user has permission to view)
```typescript
export function AppSidebar() {
  const collapsed = useUIStore((s) => s.sidebarCollapsed);
  const toggle = useUIStore((s) => s.toggleSidebar);
  const { canView, permissions, user } = useAuthStore();  // ✅ Get full permissions
  const path = useRouterState({ select: (r) => r.location.pathname });

  // Only show nav items for modules user can actually view
  const groups = NAV.map((g) => ({
    ...g,
    items: g.items.filter((i) => {
      // Check if user has view access to this module
      return canView(i.module);
    }),
  })).filter((g) => g.items.length > 0);

  return (
    <motion.aside
      animate={{ width: collapsed ? 72 : 264 }}
      transition={{ type: "spring", stiffness: 260, damping: 30 }}
      className="sticky top-0 z-30 hidden h-screen flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground md:flex"
    >
      <div className="flex h-16 items-center gap-3 border-b border-sidebar-border px-4">
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg gradient-primary glow-primary">
          <Factory className="h-5 w-5 text-primary-foreground" />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold">Axis Operate</div>
            <div className="truncate text-[11px] text-muted-foreground">Manufacturing OS</div>
          </div>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto px-2 py-4">
        {groups.map((group) => (
          <div key={group.label} className="mb-5">
            {!collapsed && (
              <div className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                {group.label}
              </div>
            )}
            <ul className="space-y-0.5">
              {group.items.map((item) => {
                const active = path === item.to || (item.to !== "/" && path.startsWith(item.to));
                const Icon = item.icon;
                return (
                  <li key={item.to}>
                    <Link
                      to={item.to}
                      className={cn(
                        "group relative flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                        active
                          ? "bg-sidebar-accent text-sidebar-accent-foreground"
                          : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
                      )}
                    >
                      {active && (
                        <motion.span
                          layoutId="nav-active"
                          className="absolute inset-y-1 left-0 w-0.5 rounded-full bg-primary"
                        />
                      )}
                      <Icon className="h-4 w-4 shrink-0" />
                      {!collapsed && <span className="flex-1 truncate">{item.label}</span>}
                      {!collapsed && item.badge ? (
                        <span className="rounded-full bg-primary/15 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                          {item.badge}
                        </span>
                      ) : null}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="border-t border-sidebar-border p-3">
        <div className="flex items-center gap-3 rounded-md p-2">
          <div
            className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-xs font-semibold text-primary-foreground"
            style={{ backgroundColor: user?.avatarColor }}
          >
            {user?.name.split(" ").map((n) => n[0]).join("").slice(0, 2)}
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <div className="truncate text-sm font-medium">{user?.name}</div>
              <div className="truncate text-[11px] text-muted-foreground">
                {user?.system_role}  {/* ✅ Show role */}
              </div>
            </div>
          )}
        </div>
        <button
          onClick={toggle}
          className="mt-2 flex w-full items-center justify-center gap-2 rounded-md border border-sidebar-border px-2 py-1.5 text-xs text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
        >
          <ChevronLeft className={cn("h-3.5 w-3.5 transition-transform", collapsed && "rotate-180")} />
          {!collapsed && "Collapse"}
        </button>
      </div>
    </motion.aside>
  );
}
```

## Example 2: Organization Setup Page

Shows/hides options based on SUPER_ADMIN capabilities:

```typescript
import { useAuthStore } from "@/lib/stores/auth-store";
import { Button } from "@/components/ui/button";

export function OrganizationSetup() {
  const { hasCapability, permissions } = useAuthStore();

  if (!permissions) {
    return <div>Loading permissions...</div>;
  }

  return (
    <div className="space-y-8">
      {/* ✅ Only show for users who can create plants */}
      {hasCapability('can_create_plants') && (
        <section className="space-y-4">
          <h2 className="text-2xl font-bold">Plants</h2>
          <p className="text-muted-foreground">
            Manage your manufacturing plants and locations.
          </p>
          <Button>+ Create Plant</Button>
        </section>
      )}

      {/* ✅ Only show for users who can create departments */}
      {hasCapability('can_create_departments') && (
        <section className="space-y-4">
          <h2 className="text-2xl font-bold">Departments</h2>
          <p className="text-muted-foreground">
            Create and manage departments within plants.
          </p>
          <Button>+ Create Department</Button>
        </section>
      )}

      {/* ✅ Only show for users who can create designations */}
      {hasCapability('can_create_designations') && (
        <section className="space-y-4">
          <h2 className="text-2xl font-bold">Designations</h2>
          <p className="text-muted-foreground">
            Define organizational roles and designations.
          </p>
          <Button>+ Create Designation</Button>
        </section>
      )}

      {/* ✅ Only show for users who can invite employees */}
      {hasCapability('can_invite_employees') && (
        <section className="space-y-4">
          <h2 className="text-2xl font-bold">Team Members</h2>
          <p className="text-muted-foreground">
            Invite and manage employees in your organization.
          </p>
          <Button>+ Invite Employee</Button>
        </section>
      )}

      {/* ✅ Only show for users who can assign roles */}
      {hasCapability('can_assign_roles') && (
        <section className="space-y-4">
          <h2 className="text-2xl font-bold">Role Assignment</h2>
          <p className="text-muted-foreground">
            Assign roles and permissions to users.
          </p>
          <Button>Manage Roles</Button>
        </section>
      )}

      {/* ✅ Only show for users who can configure permissions */}
      {hasCapability('can_configure_permissions') && (
        <section className="space-y-4">
          <h2 className="text-2xl font-bold">Permission Matrix</h2>
          <p className="text-muted-foreground">
            Configure role-based module access and capabilities.
          </p>
          <Button>Configure Permissions</Button>
        </section>
      )}

      {/* ✅ Only show for users who can access audit logs */}
      {hasCapability('can_access_audit_logs') && (
        <section className="space-y-4">
          <h2 className="text-2xl font-bold">Audit Logs</h2>
          <p className="text-muted-foreground">
            View system activity and changes.
          </p>
          <Button>View Audit Logs</Button>
        </section>
      )}

      {/* Current Permissions Debug Info (remove in production) */}
      <section className="space-y-4 border-t pt-8">
        <h3 className="text-lg font-bold">Your Permissions</h3>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div>Role: <span className="font-mono">{permissions.system_role}</span></div>
          <div>Scope: <span className="font-mono">{permissions.scope_type}</span></div>
          <div>Can Create Plants: {permissions.can_create_plants ? '✅' : '❌'}</div>
          <div>Can Invite: {permissions.can_invite_employees ? '✅' : '❌'}</div>
          <div>Can Assign Roles: {permissions.can_assign_roles ? '✅' : '❌'}</div>
          <div>Can Configure: {permissions.can_configure_permissions ? '✅' : '❌'}</div>
        </div>
      </section>
    </div>
  );
}
```

## Example 3: Permission Gate Component

Reusable component to conditionally show content:

```typescript
import React from 'react';
import { useAuthStore } from '@/lib/stores/auth-store';

interface PermissionGateProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  capability?: keyof UserPermissionProfile;
  canViewModule?: string;
  canCreateModule?: string;
  requireAll?: boolean;
}

/**
 * PermissionGate - Conditionally render content based on permissions
 * 
 * @example
 * <PermissionGate capability="can_create_plants">
 *   <CreatePlantForm />
 * </PermissionGate>
 * 
 * @example
 * <PermissionGate canViewModule="ORG_OKRS">
 *   <OKRsDashboard />
 * </PermissionGate>
 */
export function PermissionGate({
  children,
  fallback = null,
  capability,
  canViewModule,
  canCreateModule,
  requireAll = false,
}: PermissionGateProps) {
  const { hasCapability, canView, canCreate } = useAuthStore();

  // Check capability first if provided
  if (capability) {
    const hasCapabilityAccess = hasCapability(capability);
    if (!hasCapabilityAccess) return <>{fallback}</>;
  }

  // Check module view access if provided
  if (canViewModule) {
    const hasViewAccess = canView(canViewModule);
    if (!hasViewAccess) return <>{fallback}</>;
  }

  // Check module create access if provided
  if (canCreateModule) {
    const hasCreateAccess = canCreate(canCreateModule);
    if (!hasCreateAccess) return <>{fallback}</>;
  }

  return <>{children}</>;
}

// Usage examples:
/*
// Example 1: Show only if SUPER_ADMIN
<PermissionGate capability="can_configure_permissions">
  <AdminPanel />
  <PermissionGate fallback={<div>No access</div>}>
    <AdminPanel />
  </PermissionGate>
</PermissionGate>

// Example 2: Show only if can view ORG_OKRS module
<PermissionGate canViewModule="ORG_OKRS">
  <OKRsDashboard />
</PermissionGate>

// Example 3: Show only if can create in TEAM_OKRS
<PermissionGate canCreateModule="TEAM_OKRS">
  <CreateOKRButton />
</PermissionGate>
*/
```

## Example 4: Conditional Form Fields

Show/hide form fields based on permissions:

```typescript
import { useAuthStore } from "@/lib/stores/auth-store";
import { FormField, FormItem, FormLabel, FormControl, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

interface EmployeeFormProps {
  form: UseFormReturn<EmployeeCreateForm>;
}

export function EmployeeForm({ form }: EmployeeFormProps) {
  const { canCreate, canEdit, permissions } = useAuthStore();

  return (
    <form className="space-y-4">
      {/* Basic fields - everyone can see these */}
      <FormField
        control={form.control}
        name="name"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Name</FormLabel>
            <FormControl>
              <Input {...field} placeholder="Employee name" />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={form.control}
        name="email"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Email</FormLabel>
            <FormControl>
              <Input {...field} type="email" placeholder="employee@company.com" />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      {/* ✅ Only show role selection if user can assign roles */}
      {permissions?.can_assign_roles && (
        <FormField
          control={form.control}
          name="system_role"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Role</FormLabel>
              <Select onValueChange={field.onChange} defaultValue={field.value}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  <SelectItem value="EMPLOYEE">Employee</SelectItem>
                  <SelectItem value="SUPERVISOR">Supervisor</SelectItem>
                  {/* Show higher roles only if user can assign them */}
                  {permissions.can_assign_roles && (
                    <>
                      <SelectItem value="MANAGER">Manager</SelectItem>
                      <SelectItem value="DEPT_HEAD">Department Head</SelectItem>
                      <SelectItem value="PLANT_HEAD">Plant Head</SelectItem>
                    </>
                  )}
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />
      )}

      {/* ✅ Only show plant assignment if user can see all plants OR is scoped to plant */}
      {(permissions?.can_view_all_plants || permissions?.scoped_plant_id) && (
        <FormField
          control={form.control}
          name="plant_id"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Plant</FormLabel>
              <Select onValueChange={field.onChange} defaultValue={field.value}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {/* Load available plants based on user's scope */}
                  {/* If user is scoped to plant, only show that plant */}
                  {/* If user can see all plants, show all */}
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />
      )}

      {/* ✅ Only show department if user can see all departments */}
      {permissions?.can_view_all_departments && (
        <FormField
          control={form.control}
          name="department_id"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Department</FormLabel>
              <Select onValueChange={field.onChange} defaultValue={field.value}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {/* Load departments */}
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />
      )}

      {/* Submit button - only show if can create */}
      {canCreate('EMPLOYEE_DIRECTORY') && (
        <button type="submit">Create Employee</button>
      )}
    </form>
  );
}
```

## Example 5: Invitation UI

Admin panel to invite users:

```typescript
import { useState } from 'react';
import { useAuthStore } from '@/lib/stores/auth-store';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

export function InviteUserPanel() {
  const { hasCapability } = useAuthStore();
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('EMPLOYEE');
  const [isLoading, setIsLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  // Only show if user can invite
  if (!hasCapability('can_invite_employees')) {
    return <div>You don't have permission to invite employees.</div>;
  }

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      const response = await api.inviteUser({
        invited_email: email,
        system_role: role,
      });

      setSuccess(true);
      setEmail('');
      setRole('EMPLOYEE');

      // Show invitation token or send via email
      console.log('Invitation sent:', response);
      // TODO: Send email with token or show link for user to copy
    } catch (error) {
      console.error('Failed to invite:', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-4 border rounded-lg p-4">
      <h3 className="font-bold text-lg">Invite Team Member</h3>

      {success && (
        <div className="p-3 bg-green-100 text-green-800 rounded">
          Invitation sent! User will receive an email to accept.
        </div>
      )}

      <form onSubmit={handleInvite} className="space-y-4">
        <div>
          <label className="text-sm font-medium">Email Address</label>
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="user@company.com"
            required
          />
        </div>

        <div>
          <label className="text-sm font-medium">Role</label>
          <Select value={role} onValueChange={setRole}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="EMPLOYEE">Employee</SelectItem>
              <SelectItem value="SUPERVISOR">Supervisor</SelectItem>
              <SelectItem value="MANAGER">Manager</SelectItem>
              <SelectItem value="DEPT_HEAD">Department Head</SelectItem>
              <SelectItem value="PLANT_HEAD">Plant Head</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Button type="submit" disabled={isLoading} className="w-full">
          {isLoading ? 'Sending...' : 'Send Invitation'}
        </Button>
      </form>
    </div>
  );
}
```

## Integration Checklist

- [ ] Update `app-sidebar.tsx` to use `canView()` method
- [ ] Update dashboard to show/hide sections based on capabilities
- [ ] Update forms to show/hide fields based on permissions
- [ ] Add `PermissionGate` component for reusable permission checks
- [ ] Add invitation UI to admin panel
- [ ] Test each role's visibility (SUPER_ADMIN, MANAGER, EMPLOYEE, etc.)
- [ ] Verify SUPER_ADMIN sees all options
- [ ] Verify invited users see only their permitted options
- [ ] Add error states for permission denied scenarios
