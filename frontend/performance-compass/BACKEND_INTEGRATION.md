# Backend Integration Guide

## Overview
This document describes how the frontend has been integrated with the Manufacturing Performance OS backend API.

## Architecture

### API Layer (`src/lib/api.ts`)
- **Purpose**: Single source of truth for all backend API communication
- **Features**:
  - Type-safe API client with TypeScript interfaces
  - Automatic JWT token management
  - Fetch wrapper with error handling
  - All backend endpoints mapped to methods
  - Automatic token persistence to localStorage

### Authentication (`src/lib/stores/auth-store.ts`)
- **JWT Token Management**: Tokens stored in localStorage
- **Session Restoration**: `restoreSession()` called on app load to resume user sessions
- **Module Access**: `loadModules()` fetches user's accessible dashboard modules
- **User State**: Tracks authenticated user info and loaded modules

### Data Fetching (`src/lib/hooks.ts`)
- **React Query Integration**: Custom hooks for all API endpoints
- **Automatic Caching**: Query keys properly structured for caching
- **Mutations**: Create/update operations with automatic cache invalidation
- **Example Usage**:
  ```typescript
  const { data: objectives, isLoading, error } = useObjectives();
  const createOkr = useCreateObjective();
  await createOkr.mutateAsync(objectiveData);
  ```

## Auth Flow

### Login
1. User navigates to `/auth/login`
2. Submits credentials (email, password)
3. Backend returns JWT token + user info
4. Token stored in localStorage
5. User redirected to dashboard
6. Session restored on next page load

### Register
1. User navigates to `/auth/register`
2. Submits organization and admin account info
3. Backend creates org and admin user
4. Returns JWT token
5. Auto-login and redirect to dashboard

### Session Restoration
1. App loads, RootComponent renders
2. `useAuthStore.restoreSession()` called
3. Attempts `GET /api/auth/me` with stored token
4. If successful: user data loaded, modules fetched
5. If failed: token cleared, user redirected to login

## Role-Based UI

### User Roles (from backend)
- `SUPER_ADMIN` / `HR_ADMIN` - See all data
- `PLANT_MANAGER` / `DEPT_HEAD` - See plant/dept data
- `MANAGER` / `SUPERVISOR` - See team data
- `EMPLOYEE` - Personal data only

### Module Access
- Sidebar items filtered by `hasModule(key)`
- Dashboard layout changes based on `user.system_role`
- Components should respect `my-modules` permissions

### Dashboard Role-Based Layouts
```typescript
if (isSuperAdmin) { /* Org-wide view */ }
if (isPlantManager) { /* Plant/dept view */ }
if (isManager) { /* Team view */ }
// Employee view (default)
```

## API Contract Mapping

### Auth
- `POST /api/auth/register` → `api.register()`
- `POST /api/auth/login` → `api.login()`
- `GET /api/auth/me` → `api.getMe()`

### Organization
- `GET /api/org` → `api.getOrg()` / `useOrganization()`
- `POST /api/org/plants` → `api.createPlant()` / `useCreatePlant()`
- `GET /api/org/plants` → `api.getPlants()` / `usePlants()`
- And more for departments, teams, shifts, designations

### Employees
- `GET /api/employees` → `api.getEmployees()` / `useEmployees()`
- `POST /api/employees` → `api.createEmployee()` / `useCreateEmployee()`
- `GET /api/employees/{uid}` → `api.getEmployee()` / `useEmployee()`
- `PUT /api/employees/{uid}` → `api.updateEmployee()` / `useUpdateEmployee()`

### OKRs
- `GET /api/okrs` → `api.getObjectives()` / `useObjectives()`
- `POST /api/okrs` → `api.createObjective()` / `useCreateObjective()`
- `GET /api/okrs/alignment-tree` → `api.getAlignmentTree()` / `useAlignmentTree()`
- `POST /api/okrs/{objId}/key-results` → `api.createKeyResult()`
- `POST /api/okrs/key-results/{krId}/progress` → `api.submitProgressUpdate()`

### Reviews
- `GET /api/reviews/cycles` → `api.getReviewCycles()` / `useReviewCycles()`
- `GET /api/reviews` → `api.getReviews()` / `useReviews()`
- `PUT /api/reviews/{reviewId}/self-review` → `api.submitSelfReview()`
- `PUT /api/reviews/{reviewId}/manager-review` → `api.submitManagerReview()`

### Dashboard
- `GET /api/dashboard` → `api.getDashboard()` / `useDashboard()`
- `GET /api/dashboard/audit-log` → `api.getAuditLog()` / `useAuditLog()`

### Permissions
- `GET /api/permissions/my-modules` → `api.getMyModules()` / `useMyModules()`
- `GET /api/permissions/modules` → `api.getDashboardModules()` / `useDashboardModules()`

## Request/Response Format

### Authorization Header
All protected requests automatically include:
```
Authorization: Bearer <access_token>
```

### Error Handling
Errors from backend are caught and rethrown as Error objects:
```typescript
try {
  await api.login(email, password);
} catch (error) {
  // error.message contains backend's "detail" field
}
```

### Query Parameters
Middleware on server injects from JWT:
- `org_id`
- `user_id`
- `role`

These are automatically added by middleware and don't need to be manually passed.

## Updated Routes

### `/` - Dashboard
- Fetches `GET /api/dashboard`
- Shows role-specific stats and widgets
- Displays pending actions from backend

### `/auth/login` - Login Page
- Form submission sends to `POST /api/auth/login`
- Stores JWT token on success
- Redirects to dashboard

### `/auth/register` - Registration Page
- Creates new organization and admin user
- `POST /api/auth/register`
- Auto-login on success

### `/okrs` - OKRs List
- Fetches `GET /api/okrs`
- Displays objectives with key results
- Shows progress bars

### `/employees` - Employee Directory
- Fetches `GET /api/employees`
- Displays employee cards with role and assignments
- Avatar with initials

### `/reviews` - Performance Reviews
- Fetches `GET /api/reviews` and `GET /api/reviews/cycles`
- Grouped by review status
- Shows cycles in header

## Configuration

### Base URL
Currently set to `http://localhost:8000` in `src/lib/api.ts`:
```typescript
new APIClient(baseUrl: string = "http://localhost:8000")
```

Change for production:
```typescript
new APIClient("https://api.yourdomain.com")
```

### Token Expiration
Backend sets token lifetime to 24 hours. Frontend automatically:
- Stores token in localStorage
- Restores from storage on page load
- Handles expired tokens by redirecting to login

## Key Changes from Original

### Before
- Mock data in `src/lib/mock-data.ts`
- Hardcoded role switching in Topbar
- No real authentication
- Placeholder pages

### After
- Real API integration via `src/lib/api.ts`
- JWT-based authentication
- Roles from backend (`system_role`)
- Functional pages with real data
- React Query for data management
- Proper error handling and loading states

## Development Workflow

### Adding a New API Endpoint

1. **Add to API client** (`src/lib/api.ts`):
   ```typescript
   async newEndpoint(): Promise<ResponseType> {
     return this.request<ResponseType>("GET", "/api/path");
   }
   ```

2. **Add React Query hook** (`src/lib/hooks.ts`):
   ```typescript
   export function useNewEndpoint() {
     return useQuery({
       queryKey: ["new-endpoint"],
       queryFn: () => api.newEndpoint(),
     });
   }
   ```

3. **Use in component**:
   ```typescript
   const { data, isLoading, error } = useNewEndpoint();
   ```

### Testing Auth Flow
1. Start backend: `python main.py`
2. Frontend runs on http://localhost:5173
3. Backend on http://localhost:8000
4. Login with demo credentials or register new org
5. Check browser localStorage for `access_token`

## Type Safety
All API responses are typed:
- `User`, `Organization`, `Objective`, `Review`, etc.
- `SystemRole`, `ObjectiveLevel`, `ReviewStatus` enums
- Request bodies typed: `LoginRequest`, `RegisterRequest`, etc.

## Error Handling Strategy

### Auth Store
```typescript
try {
  await login(email, password);
} catch (error) {
  // Error set in store.error
  // Component displays using {error}
}
```

### Hooks/Components
```typescript
const { error } = useObjectives();
if (error) {
  return <Alert>{error.message}</Alert>;
}
```

### API Calls
```typescript
try {
  const data = await api.getDashboard();
} catch (error) {
  // Error automatically handled by React Query
}
```

## Next Steps

1. **Complete remaining routes**: Implement hierarchy, alignment, and other pages
2. **Form submissions**: Add create/update/delete forms for OKRs, employees, reviews
3. **Error boundaries**: Add per-route error handling
4. **Loading skeletons**: Replace generic loading spinners with skeleton components
5. **Offline support**: Consider React Query's offline capabilities
6. **Optimistic updates**: Add optimistic UI updates for mutations
7. **Real-time updates**: Consider WebSocket integration for live data
8. **Search/filtering**: Implement full-text search using API parameters
9. **Export functionality**: Connect export buttons to backend
10. **Notifications**: Integrate notification system with pending actions

## Common Patterns

### Fetch data on component load
```typescript
export function MyComponent() {
  const { data, isLoading, error } = useMyData();
  
  if (isLoading) return <Spinner />;
  if (error) return <Error />;
  
  return <Content data={data} />;
}
```

### Submit form
```typescript
const mutation = useCreateItem();

async function handleSubmit(formData) {
  try {
    await mutation.mutateAsync(formData);
    // Cache auto-invalidated, data refetched
  } catch (error) {
    // Show error to user
  }
}
```

### Check permissions
```typescript
const hasAccess = useAuthStore(s => s.hasModule("admin_panel"));
if (!hasAccess) return <Forbidden />;
```

## Troubleshooting

### "Not authenticated" error on page load
- Check if token exists in localStorage
- Verify backend is running
- Check CORS settings on backend

### API returns 401 Unauthorized
- Token may have expired
- Clear localStorage and re-login
- Verify token format in Authorization header

### Module access not showing up
- Check `GET /api/permissions/my-modules` response
- Verify user role in backend permissions
- Clear browser cache and refresh

### Dashboard shows no stats
- Backend `GET /api/dashboard` may be returning empty stats
- Check dashboard query in React Query DevTools
- Verify test data exists in backend database
