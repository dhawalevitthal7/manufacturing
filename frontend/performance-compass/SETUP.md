# Frontend Environment Setup

## Prerequisites
- Node.js 18+
- npm or yarn
- Backend running on http://localhost:8000

## Installation

```bash
cd frontend/performance-compass
npm install
```

## Development

```bash
# Start dev server (Vite)
npm run dev

# Frontend runs on http://localhost:5173
# Backend should run on http://localhost:8000
```

## Configuration

### API Base URL
Edit `src/lib/api.ts`:
```typescript
// Line ~335
new APIClient(baseUrl: string = "http://localhost:8000")
```

Change to your backend URL:
```typescript
new APIClient("https://api.yourdomain.com")
```

### CORS
Backend has CORS enabled with wildcard. If accessing from different origin, ensure backend CORS is configured.

## Environment Variables
Create `.env` file (optional):
```
VITE_API_URL=http://localhost:8000
```

But currently hardcoded in `src/lib/api.ts`.

## Build

```bash
# Production build
npm run build

# Preview production build
npm run preview
```

## Troubleshooting

### Backend connection fails
- Verify backend is running: `python main.py`
- Check backend logs for errors
- CORS should allow connections from http://localhost:5173

### Login shows "Network error"
- Backend may be down or unreachable
- Check browser console for fetch errors
- Verify http://localhost:8000 is accessible

### "Invalid token" after login
- Token may have expired (24h lifetime)
- Clear localStorage: `localStorage.clear()`
- Re-login to get new token

### Modules not loading
- Backend permission sync may be needed
- Try `/api/permissions/seed-defaults` endpoint
- Check `/api/permissions/my-modules` response

## Database Setup (Backend)
Ensure backend has initialized database:
```bash
cd backend/
python main.py
# Creates manufacturing_os.db on first run
```

## Demo Data
For testing, you can register a new organization or use:
- Email: admin@example.com
- Password: Welcome@123

## TypeScript
All components are TypeScript. Type definitions auto-imported:
```typescript
import { SystemRole, ObjectiveLevel } from "@/lib/api";
```

## React Query DevTools
React Query DevTools included for debugging:
- Access via the DevTools widget (check for floating icon)
- View all queries, cached data, and network requests

## Performance Tips
1. React Query caching reduces API calls
2. Route-based code splitting with TanStack Router
3. Lazy loading images and components
4. Memoization where needed

## Code Style
- ESLint configured (run `npm run lint`)
- Prettier configured (run `npm run format`)
- Use TypeScript strict mode for type safety

## API Documentation
- Backend Swagger UI: http://localhost:8000/docs
- Full API contract in BACKEND_INTEGRATION.md
- All endpoints typed in src/lib/api.ts

## Common Tasks

### Add new API endpoint
1. Add method to APIClient in src/lib/api.ts
2. Add React Query hook in src/lib/hooks.ts
3. Use in component with the hook

### Add new route
1. Create file in src/routes/
2. Use TanStack Router: `createFileRoute("/path")`
3. Add to sidebar navigation if needed (check module access)

### Create form
1. Use React Hook Form + Zod (already imported)
2. Use API hooks: `useCreateX()`, `useUpdateX()`
3. Show loading/error states

## Support
See BACKEND_INTEGRATION.md for architecture overview and detailed API information.
