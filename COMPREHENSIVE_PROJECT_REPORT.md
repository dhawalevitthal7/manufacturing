# Comprehensive Project Report: Manufacturing Performance OS

## 1. Executive Summary

This project is a full-stack manufacturing performance management platform. In the UI it is branded as **Axis Operate - Manufacturing OKR OS**. In the backend it is named **Manufacturing Performance OS**.

The product combines:

- Multi-tenant organization setup.
- Manufacturing hierarchy management across organization, regions, corporate functions, plants, departments, sub-departments, teams, and employees.
- Role-based permission and visibility control.
- OKR creation, assignment, approval, cascading, progress tracking, alignment, and analytics.
- Continuous employee check-ins and coaching workflows.
- Formal performance review cycles with scoring, calibration, employee narratives, and manager/HR workflows.
- AI-assisted OKR generation, OKR cascading, progress coaching, alignment validation, and performance review drafting through Azure OpenAI when configured.
- Local seed, migration, verification, and pytest coverage for the major workflow phases.

Important note: the repository does not currently contain the root reference files `PRD.md`, `techstack.md`, or `tracking.md` mentioned in the user rules. This report is therefore based on direct code inspection of the files present in the workspace.

## 2. Repository Shape

The project root contains a Python FastAPI backend, a React/TanStack frontend, test files, data/backfill scripts, verification scripts, and a local SQLite database.

Primary areas:

- `main.py`: backend entrypoint, FastAPI app setup, middleware, router registration, frontend static serving, health route.
- `server/`: backend domain models, routes, services, schemas, auth, permissions, migrations, and repositories.
- `frontend/performance-compass/`: React 19 + Vite/TanStack Start frontend.
- `tests/`: pytest tests for OKR visibility, OKR lifecycle, OKR cascade, KR ingest, review scoring, and performance review agent behavior.
- `scripts/`: seed, backfill, investigation, verification, and demo data scripts.
- `requirements.txt`: backend Python dependencies.
- `frontend/performance-compass/package.json`: frontend dependencies and scripts.

## 3. High-Level Architecture

The system uses a classic API-backed SPA/server-rendered frontend architecture:

1. The user opens the frontend.
2. The frontend restores a JWT token from `localStorage`.
3. If unauthenticated, the root route redirects to `/auth/login`.
4. Login/register calls backend auth endpoints.
5. Authenticated frontend requests include a Bearer token.
6. FastAPI decodes the JWT.
7. Middleware injects `org_id`, `user_id`, and `role` into query parameters for older route handlers.
8. Newer route handlers often depend directly on `get_jwt_payload`.
9. SQLAlchemy persists and reads data from local SQLite.
10. Domain services enforce workflow rules.
11. The frontend renders role-aware navigation, dashboards, OKRs, reviews, approvals, hierarchy, and settings.

The backend is not just CRUD. Most business rules live in service modules under `server/services/`, especially around OKR lifecycle, visibility, dual approvals, review scoring, and AI-assisted workflows.

## 4. Backend Tech Stack

The backend stack is defined by `requirements.txt`:

- `fastapi==0.115.0`: HTTP API framework.
- `uvicorn[standard]==0.30.0`: ASGI server for local development and runtime.
- `sqlalchemy==2.0.35`: ORM and database access.
- `pydantic==2.9.0`: request/response validation.
- `python-jose[cryptography]==3.3.0`: JWT encoding and decoding.
- `passlib[bcrypt]==1.7.4` plus `bcrypt>=4.0.1,<4.1.0`: password hashing.
- `python-multipart==0.0.9`: multipart/form-data support.
- `aiofiles==24.1.0`: async file support.
- `openai>=1.51.0`: Azure OpenAI client support.
- `python-dotenv>=1.0.0`: `.env` loading.

The database is SQLite by default:

- Database URL: `sqlite:///./manufacturing_os.db`.
- Engine uses `check_same_thread=False`.
- Tables are created through `Base.metadata.create_all(bind=engine)`.
- Idempotent local schema migrations are applied through `apply_sqlite_schema_migrations(engine)`.

## 5. Frontend Tech Stack

The frontend lives under `frontend/performance-compass`.

Core frontend libraries:

- React 19.
- TypeScript.
- Vite 7.
- TanStack Router.
- TanStack Query.
- TanStack Start.
- Zustand for state stores.
- Tailwind CSS 4.
- Radix UI primitives.
- Lucide React icons.
- Recharts for charts.
- D3 force and React Force Graph for constellation/alignment views.
- React Hook Form and Zod for forms and validation.
- Sonner for notifications.
- Framer Motion for UI motion.

Scripts:

- `npm run dev`: start Vite dev server.
- `npm run build`: production build.
- `npm run build:dev`: development-mode build.
- `npm run preview`: preview built frontend.
- `npm run lint`: run ESLint.
- `npm run format`: run Prettier.

The Vite config uses `@lovable.dev/vite-tanstack-config`, which already supplies TanStack Start, React, Tailwind, tsconfig paths, Cloudflare build plugin, aliases, env injection, and related defaults.

## 6. Application Entry Flow

### Backend Startup

`main.py` performs the backend boot sequence:

1. Loads `.env`.
2. Imports database engine, models, auth helpers, and routers.
3. Registers performance review models so their tables are included.
4. Creates all known SQLAlchemy tables.
5. Applies SQLite migrations for older local databases.
6. Creates a FastAPI app named `Manufacturing Performance OS`.
7. Adds permissive CORS.
8. Adds middleware to inject JWT context into API query parameters.
9. Includes all routers.
10. Serves `static/index.html` if a built frontend exists under `static`.
11. Exposes `/health`.
12. Runs `uvicorn` when called as `python main.py`.

### Frontend Startup

The frontend root route:

1. Creates a TanStack router from generated route tree.
2. Wraps the app in `QueryClientProvider`.
3. Restores auth state.
4. Applies dark/light theme.
5. Redirects unauthenticated users to `/auth/login`.
6. Renders authenticated users inside `AppSidebar`, `Topbar`, and a main content outlet.

The dashboard route fetches `api.getDashboard()` and shows role-specific dashboard copy.

## 7. Authentication and Session Model

Authentication is JWT-based.

Main backend auth behavior:

- Passwords are hashed with bcrypt through Passlib.
- `create_access_token` issues HS256 JWTs.
- Tokens expire after 1440 minutes, which is 24 hours.
- `decode_access_token` normalizes `role` and `system_role` claims.
- Auth routes include register, login, me, and onboarding flows.
- Protected endpoints use either injected query context or `get_jwt_payload`.

Frontend behavior:

- The API client stores the JWT under `localStorage` key `access_token`.
- All API requests attach the token as a Bearer header.
- The auth store restores the session on app load.

Security note:

- `SECRET_KEY` is hardcoded in `server/auth.py` as a development value. For production, this should come from environment configuration.
- CORS is currently `allow_origins=["*"]`, which is useful locally but should be restricted in production.

## 8. Tenant and Organization Model

The system is multi-tenant by `org_id`.

Core tenant entities:

- `Organization`: root tenant with name, domain, industry, size, setup status, and creation timestamp.
- `User`: tenant member with email, password hash, name, employee ID, role, org assignment, active flag, legacy plant/department/team fields, and newer `org_node_id`.
- `Plant`, `Department`, `Team`, `Shift`, `Designation`: legacy manufacturing structure.
- `OrgNode`: newer flexible organization tree that can represent organization root, regions, corporate functions, plants, verticals, departments, sub-departments, and teams.

The code maintains compatibility between legacy tables and the newer `OrgNode` hierarchy. SQLite migrations backfill org nodes from legacy plant/department/team records.

## 9. Organization Tree and Hierarchy

The flexible hierarchy is built around `OrgNode`.

Important invariants:

- `path` is a dotted string of UUIDs from root to current node.
- Organization root path is the org ID.
- Child path is `parent.path + "." + child.id`.
- `depth` is derived from path dot count.
- Legacy plant, department, and team nodes reuse legacy entity IDs.
- New region/corporate/function nodes use generated UUIDs.

Supported node types:

- `ORGANIZATION`
- `REGION`
- `CORPORATE_COMMITTEE`
- `CORPORATE_FUNCTION`
- `PLANT`
- `VERTICAL`
- `DEPARTMENT`
- `SUB_DEPARTMENT`
- `TEAM`

The hierarchy supports:

- Parent-child reporting structure.
- Dotted-line functional relationships through `functional_parent_id`.
- Region and corporate function setup.
- Plant, department, and team sync with org nodes.
- Tree rendering in the frontend.
- Scope-based permission and visibility queries.

Services:

- `org_tree_service.py`: creates, moves, syncs, and reads org nodes.
- `org_node_validation.py`: validation rules around nodes.
- `function_area_service.py`: function area resolution.
- `manager_resolution.py`: manager and coaching relationship resolution.

## 10. Role Model and Permission System

The canonical roles are defined in `server/roles.py`.

Roles include:

- Platform/admin: `SUPER_ADMIN`.
- Executive roles: `CEO`, `COO`, `CRO`, `CFO`, `CMO`, `CHRO`, `CPO`, `CSO`, `CTO`, `HR_HEAD`.
- Manufacturing hierarchy roles: `VP_OPERATIONS`, `REGIONAL_HEAD`, `PLANT_HEAD`, `DEPT_HEAD`, `MANAGER`, `TEAM_LEAD`, `SUPERVISOR`, `EMPLOYEE`.
- Functional/business roles: `FUNCTIONAL_SUB_HEAD`, `AREA_SALES_MANAGER`.

Role normalization:

- Legacy roles such as `VP_MANUFACTURING`, `OPERATIONS_HEAD`, `OPERATOR`, `TECHNICIAN`, `INSPECTOR`, `HR_ADMIN`, `PLANT_MANAGER`, and `FACTORY_DIRECTOR` are mapped to canonical roles.
- Unknown roles fall back to `EMPLOYEE` with warning logs.
- User roles are normalized on assignment, ORM load, ORM refresh, and JWT decode.

Permission layers:

- `ModuleAccess`: module-level access by role or designation.
- `UserPermissionProfile`: user scope, module permissions, and special flags.
- `RolePermissionRule`: granular enterprise matrix rules with view/create/edit/delete/approve/assign/manage flags.
- `permission_registry.py`: central registry of permission keys.
- `permissions_service.py`: permission profile behavior.

The frontend also has role-specific navigation definitions under `frontend/performance-compass/src/lib/navigation/definitions`.

## 11. OKR Data Model

There are two OKR model families in the backend:

1. The main live model in `server/models.py`:
   - `Objective`
   - `KeyResult`
   - `ProgressSubmission`
   - `ProgressUpdate`
   - `ApprovalStep`
   - `ObjectiveConnection`
   - `KRIngestSource`

2. A more formal/advanced OKR model in `server/okr_models.py`:
   - `OKR`
   - `KeyResult`
   - `KRProgressUpdate`
   - `OKRAlignment`
   - `OKRAnalyticsSnapshot`
   - `OKRHealthAudit`
   - `OKRSubmission`
   - `OKRApproval`

The active route set heavily uses `Objective` and `KeyResult` from `server/models.py`. The advanced model appears to support a production-grade OKR architecture and advanced routes, but the main app routers are centered on the `Objective` model.

Main `Objective` fields:

- Ownership: `owner_id`, `assigned_by_id`, `org_id`.
- Hierarchy: `parent_id`, `functional_parent_obj_id`.
- Cycle: `cycle_id`, `quarter`, `year`.
- Scope: `region_id`, `plant_id`, `department_id`, `team_id`.
- Workflow: `creation_approval_status`, primary/functional approval fields, `okr_status`, pending approver info, rejection reason.
- AI: `ai_generated`, `ai_metadata`.
- Function: `function_area`, `function_node_id`.
- Progress: `progress`, status, cascade permission.

Main `KeyResult` fields:

- Objective link.
- Title.
- Target value.
- Current value.
- Unit.
- Status.
- Weight.
- Optional ingest source.

## 12. OKR Workflow

The OKR workflow is one of the core parts of the system.

### OKR Creation

The creation flow:

1. User opens OKR page and creates an objective.
2. Backend validates role, target level, owner, and assignment.
3. Backend fills scope from owner or creator where needed.
4. Backend resolves cycle, quarter, year, function area, and function node.
5. Objective is created as `DRAFT`.
6. Creation approval chain is enqueued.
7. Key results are added.
8. Objective waits for approval before becoming active.

Role gates:

- `SUPER_ADMIN` and `CEO` can create broadly.
- Other roles are constrained by allowed objective levels.
- Team OKRs require a selected team.
- Individual OKRs require assignment to an employee.
- Assigning OKRs to someone else requires relationship/scope validation.

### OKR Lifecycle

The lifecycle is documented in code as:

`DRAFT -> PENDING_APPROVAL -> ACTIVE | REJECTED | ACHIEVED | MISSED | ARCHIVED`

Important lifecycle service functions:

- `can_user_draft_objective`
- `resolve_business_approver`
- `enqueue_okr_creation_approval`
- `submit_for_approval`
- `activate_okr`
- `publish_ceo_okr`
- `reject_okr`
- `assert_okr_allows_progress`
- `assert_okr_allows_kr_edit`
- `admin_approve_okr`
- `admin_reject_okr`

### Dual Approval

The dual approval service supports ordered approval chains:

- Subject types include OKR creation and progress submission.
- Step 1 is usually line approval.
- Step 2 may be functional approval.
- Functional approval is used when dotted-line/functional parent relationships apply.
- The chain stores approver ID, approver role, sequence, approval type, status, decision timestamp, and comments.

This is implemented through the `ApprovalStep` model and `dual_approval_service.py`.

### OKR Visibility

Visibility is not simply "owner only."

Visibility considers:

- Role.
- User permission profile.
- Region/plant/department/team scope.
- Direct and descendant hierarchy.
- Parent objective peeking.
- Functional alignment.
- Optional UI scope filters.

Main service:

- `okr_visibility_service.py`

Main behavior:

- Builds user OKR scope.
- Applies SQLAlchemy filters to objective queries.
- Supports region and plant narrowing.
- Exposes a visibility-scope response for the UI.

### Progress Updates

Progress can flow through:

- `ProgressSubmission`: newer submission and review workflow.
- `ProgressUpdate`: legacy progress tracking kept for compatibility.
- KR ingest: external systems update KRs by token-authenticated ingest.

Progress submission supports:

- Employee submitted value and note.
- Manager review and optional override.
- Approval/rejection/revision status.
- Validation chain.
- Next approver role.
- Cascade and parent objective progress approval.

### KR Ingest

`KRIngestSource` connects a key result to external metric sources:

- SCADA.
- MES.
- SAP.
- Other tagged source metrics.

The ingest service:

- Generates and verifies ingest tokens.
- Hashes tokens.
- Applies rate limiting.
- Applies safe arithmetic transforms.
- Updates KR values.
- Records source metadata and last ingest value/time.

## 13. OKR AI Features

AI is optional and depends on Azure OpenAI configuration.

Config values:

- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_API_VERSION`
- `AZURE_OPENAI_DEPLOYMENT_NAME`

Defaults:

- Endpoint defaults to `https://openai-04.openai.azure.com/`.
- API version defaults to `2024-12-01-preview`.
- Deployment defaults to `gpt-4o`.

AI OKR capabilities:

- Conversational OKR generation.
- Cascaded OKR personalization.
- Alignment validation between parent and child OKRs.
- Auto-progress suggestions.
- Coaching suggestions for progress updates.
- Batch auto-track operations.

AI response pattern:

- Backend requests JSON from Azure OpenAI.
- Prompts require structured JSON output.
- The API returns suggestions, whether a suggestion is ready, and generated key results.
- If AI is not configured, friendly errors are returned for user-facing flows.

Important files:

- `server/services/azure_openai_service.py`
- `server/services/okr_ai_agent.py`
- `server/services/progress_ai_agent.py`
- `server/routes_okrs_ai.py`

## 14. Performance Review Data Model

Enhanced review models live in `server/performance_review_models.py`.

Main review-cycle models:

- `PerformanceReviewCycle`: configurable review cycle with dates, submission window, lock/publish settings, eligible plants/departments/roles, status, and creator.
- `ContinuousCheckin`: weekly/monthly check-in with achievements, blockers, support needed, confidence, engagement, mood, OKR snapshot, manager feedback, actions, escalation, concern flags, and workflow status.
- `CheckinComment`: threaded coaching comments.
- `CheckinEscalation`: exception-based escalation from manager to department head.
- `CheckinNotification`: in-app notification queue.
- `EmployeePerformanceReview`: formal review object linking employee, manager, cycle, review sections, workflow state, final score/rating, OKR score, promotion fields, attrition risk, and AI review payload.
- `ReviewSection`: self, manager, skip-level, HR, or final review content.
- `FeedbackTemplate` and `FeedbackResponse`: 360 feedback capabilities.
- `CompetencyFramework`, `Competency`, `CompetencyAssessment`: role-specific competency scoring.
- `ScoringConfiguration`: score weighting.
- `ReviewCalculation`: persisted scoring results.
- `ReviewAdjustment`: calibration/bias/manual/appeal adjustments.
- `FeedbackSynthesis`: synthesized feedback output.
- `ReviewAuditLog`: review workflow audit trail.

## 15. Performance Review Workflow

The review system has two related workflows: continuous check-ins and formal reviews.

### Continuous Check-Ins

Check-ins are coaching and monitoring records, not approval chains.

Typical flow:

1. Employee submits weekly/monthly check-in.
2. The check-in captures achievements, wins, blockers, risks, support needed, confidence, engagement, mood, and OKR progress snapshot.
3. Manager reviews and responds.
4. Manager can add action items and coaching notes.
5. If needed, the check-in is escalated.
6. Escalations can be resolved.
7. Notifications are generated for relevant users.

Workflow statuses include:

- `DRAFT`
- `SUBMITTED`
- `UNDER_REVIEW`
- `ACTION_REQUIRED`
- `ESCALATED`
- `RESOLVED`
- `CLOSED`

### Formal Performance Reviews

The formal review flow is hierarchy-driven:

1. Review cycle is created and activated.
2. Eligible employees are identified.
3. Review records are initiated.
4. Employee submits self-review.
5. Manager submits manager review.
6. Department head moderation may occur.
7. HR calibration may occur.
8. Review is finalized.
9. Review is published.
10. Audit logs record the state transitions.

Review states include:

- `DRAFT`
- `SELF_SUBMITTED`
- `MANAGER_REVIEW`
- `DEPT_HEAD_MODERATION`
- `PEER_REVIEW`
- `SKIP_LEVEL_REVIEW`
- `HR_CALIBRATION`
- `FINALIZED`
- `PUBLISHED`
- `LOCKED`
- `ARCHIVED`

The code notes that regional and CEO roles do not review individual employees directly. They are intended for dashboard visibility rather than individual review ownership.

## 16. Review Scoring Model

The scoring service calculates a final performance score from weighted components.

Default formula in code:

- OKR achievement: 40 percent.
- KR quality: 20 percent.
- Manager feedback: 15 percent.
- Behavioral competency: 10 percent.
- Peer feedback: 10 percent.
- Continuous check-in: 5 percent.

The scoring engine:

- Redistributes weights when data is missing.
- Calculates confidence as the percentage of configured weight backed by available data.
- Maps scores to ratings.
- Stores review calculations.
- Can use AI payload recommended rating as a preview before formal manager submission.
- Integrates live OKR progress and check-in data.

Ratings:

- `EXCEEDS_EXPECTATIONS`
- `MEETS_EXPECTATIONS`
- `BELOW_EXPECTATIONS`
- `NEEDS_IMPROVEMENT`

## 17. Performance Review AI Agent

The performance review AI agent supports manager-triggered review drafting after self-review.

The agent gathers:

- Employee and manager context.
- Review cycle dates.
- Department head context if moderation is required.
- OKR snapshot.
- OKR achievement score.
- Self-review section.
- Manager draft section.
- Check-ins in the review period.
- Progress submissions in the review period.
- Prior reviews.
- Score preview and component breakdown.

It asks Azure OpenAI to return JSON containing:

- Executive summary.
- OKR performance analysis.
- Self-review synthesis.
- Check-in insights.
- Strengths.
- Development areas.
- Promotion recommendation.
- Promotion rationale.
- Recommended rating.
- Coaching actions.
- Risk flags.

If Azure OpenAI is unavailable or not configured, the system falls back to deterministic rule-based review generation.

Manager workflow:

1. Manager runs AI review.
2. Agent gathers context.
3. Azure OpenAI generates structured review payload, or fallback does.
4. Payload is stored on `EmployeePerformanceReview`.
5. Manager can edit the payload.
6. Manager submits the review using the agent.
7. System builds employee-facing performance narrative.
8. Promotion recommendation and rationale are stored.
9. Review is routed to department head if needed.

## 18. Dashboard and Analytics

Dashboard APIs aggregate:

- Current user profile and role.
- OKR counts and progress.
- Pending approvals.
- Reviews.
- Audits.
- Alignment and execution data.

The frontend dashboard uses:

- `DashboardGrid`
- `alignment-summary`
- `execution-chart`
- `queue-widget`
- `dashboard-constellation`

The OKR analytics services support:

- KR progress calculation.
- Objective score snapshots.
- Organization-level scores.
- Velocity.
- Consistency.
- Health status.
- Trajectory.
- Confidence.
- At-risk OKRs.
- Low-confidence OKRs.

## 19. Constellation and Alignment View

The frontend includes a constellation graph experience.

Relevant files:

- `components/constellation/OrbitalConstellationView.tsx`
- `components/constellation/LineOfSightView.tsx`
- `components/constellation/NodeDetailPanel.tsx`
- `components/constellation/ExecutiveInsightsPanel.tsx`
- `components/constellation/draw/*`
- `store/constellationStore.ts`
- `hooks/useConstellationGraph.ts`
- `routes/alignment.tsx`

Backend route:

- `server/routes_constellation.py`

The constellation route set supports:

- Graph retrieval.
- Stats.
- Insights.
- Objective connections.

The model `ObjectiveConnection` supports cross-functional links with types such as `SUPPORTS`, `DEPENDS_ON`, and `RELATED_TO`.

## 20. Frontend Route Surface

Current frontend routes include:

- `/`: dashboard.
- `/auth/login`: login.
- `/auth/register`: registration.
- `/okrs`: OKR management.
- `/progress`: progress submissions and validation.
- `/reviews`: performance reviews and check-ins.
- `/approvals`: approval queue.
- `/org-tree`: flexible organization tree.
- `/hierarchy`: hierarchy management.
- `/employees`: employee management.
- `/teams`: team management.
- `/permissions`: permission matrix.
- `/settings`: settings.
- `/alignment`: constellation/alignment view.
- `/audit-logs`: audit logs.
- `/blockers`: blocker tracking.
- `/admin/okr-overrides`: admin OKR lifecycle overrides.

The root route owns:

- App shell.
- Error boundary.
- Not-found page.
- Auth redirect.
- Theme application.
- Sidebar and topbar layout.

## 21. Backend API Surface

Major route modules:

- `routes_auth.py`: onboarding, registration, login, current user.
- `routes_org.py`: organization setup, plants, departments, teams, shifts, designations.
- `routes_org_tree.py`: org tree, regions, corporate functions, node create/update/delete.
- `routes_employees.py`: employee list/create/bulk/get/update/delete/org-chart.
- `routes_teams.py`: team CRUD and membership management.
- `routes_hierarchy.py`: reporting relationships, chains, subtree, reviewers, approvers.
- `routes_okrs.py`: objectives, KRs, progress, visibility, lifecycle approvals, alignment tree, allowed levels.
- `routes_okrs_hierarchy.py`: validation, hierarchy-chain, assignment, approval, recipients, visible OKRs.
- `routes_okrs_ai.py`: AI OKR generation, cascading, alignment validation, auto tracking, coaching.
- `routes_progress.py`: newer progress submissions, review, history, cascade pending, approval dashboard.
- `routes_reviews.py`: legacy review cycles and review flow.
- `routes_reviews_performance.py`: enhanced performance cycles, check-ins, employee reviews, scoring, AI review agent, team review hub.
- `routes_checkins_coaching.py`: coaching-oriented check-in workflow.
- `routes_dashboard.py`: dashboard and audit log.
- `routes_permissions.py`: dashboard modules, module access, profiles, invitations.
- `routes_permission_matrix.py`: registry and role permission matrix.
- `routes_cycles.py`: OKR cycles.
- `routes_integrations.py`: KR ingest.
- `routes_approvals.py`: approval queue and chain.
- `routes_constellation.py`: graph, stats, insights, objective connections.

## 22. External Integration Model

The main integration surface is KR metric ingest.

The intended external systems include:

- SCADA.
- MES.
- SAP.
- Other manufacturing or enterprise data systems.

Flow:

1. Admin configures a `KRIngestSource` for a key result.
2. Backend generates an ingest token.
3. External system posts a metric to `/api/integrations/kr-ingest`.
4. Token is verified.
5. Value is optionally transformed.
6. KR progress updates.
7. Source metadata records last ingest value and timestamp.

This enables auto-updating measurable manufacturing KRs from operational systems.

## 23. Audit Model

Audit appears in two layers:

- General `AuditLog` in `server/models.py`.
- Review-specific `ReviewAuditLog` in `server/performance_review_models.py`.

Audited actions include:

- Login and auth behavior.
- Create/update/delete.
- Approve/reject.
- Role normalization.
- Review state transitions.
- AI review generation and manager submission.

Audit logs support accountability in approval-heavy manufacturing workflows.

## 24. Scripts and Operational Utilities

The repository includes many scripts for setup, seeding, migration, verification, and investigation.

Important categories:

- Seed data:
  - `seed_birla_demo.py`
  - `seed_birla_cement.py`
  - `ultratech_seed_data.py`
  - `reset_and_seed_minimal_demo.py`
  - `seed_performance_review_cycle.py`
  - `seed_constellation_connections.py`
  - `server/scripts/seed_default_region.py`

- Backfills:
  - `backfill_permission_profiles.py`
  - `backfill_reporting_relationships.py`
  - `backfill_scope_assignments.py`

- Verification:
  - `verify_okr_progress.py`
  - `verify_roles_module.py`
  - `verify_corporate_committee_okr.py`
  - `verify_v32_substep.py`
  - `verify_v33_substep.py`
  - `verify_v34_behavioral.py`
  - `verify_v35_hardening.py`
  - `verify_v42_phase.py`
  - `verify_v43_phase.py`

- Phase/demo investigations:
  - `phase15_*`
  - `_q42_investigate.py`
  - `_v41_verify.py`
  - `_test_okr_visibility.py`

These scripts suggest the project has been built through staged phases with validation after each phase.

## 25. Test Coverage

Current pytest files:

- `test_okr_visibility_scope.py`
- `test_okr_phase44_workflow.py`
- `test_kr_ingest.py`
- `test_performance_review_agent.py`
- `test_review_scoring_service.py`
- `test_okr_cascade_service_v43.py`
- `test_okr_phase6_lifecycle.py`

Coverage themes:

- OKR visibility and scope.
- OKR lifecycle.
- Dual/cascade workflow.
- KR ingest behavior.
- Performance review AI agent behavior.
- Review scoring logic.

The tests focus on workflow correctness rather than only low-level CRUD.

## 26. Main User Workflows

### Organization Setup Workflow

1. User registers an organization.
2. Backend creates `Organization` and admin user.
3. Organization setup can create plants, departments, teams, shifts, and designations.
4. Org tree service ensures root and child nodes exist.
5. Permission defaults can be seeded.
6. Employees are onboarded and assigned to hierarchy nodes.

### Employee Onboarding Workflow

1. Admin or HR creates/invites employee.
2. User is assigned role, designation, plant, department, team, shift, or org node.
3. Permission profile is created or backfilled.
4. Reporting relationships can be established.
5. User can log in and sees role-aware modules.

### OKR Workflow

1. User creates objective with key results.
2. Backend validates allowed level and scope.
3. Objective enters draft/pending approval.
4. Approval chain routes to line and optional functional approvers.
5. Approved OKR becomes active.
6. KRs are updated manually, through progress submissions, or via KR ingest.
7. Managers validate progress.
8. Objective progress is recalculated.
9. Alignment tree and dashboards update.
10. Reviews consume OKR performance as evidence.

### AI-Assisted OKR Workflow

1. User opens AI OKR chat.
2. User describes desired objective.
3. AI asks clarifying questions or returns a structured OKR suggestion.
4. User accepts suggestion.
5. Backend creates objective/KRs from suggestion.
6. Normal approval workflow applies.

### Continuous Check-In Workflow

1. Employee submits check-in.
2. Check-in captures wins, blockers, support needs, confidence, mood, and OKR snapshot.
3. Manager acknowledges/responds.
4. Manager adds comments/actions/coaching.
5. Escalation occurs only for exception cases.
6. Check-in history feeds formal review context.

### Formal Review Workflow

1. HR/admin creates review cycle.
2. Reviews are initiated for eligible employees.
3. Employee self-review is submitted.
4. Manager review is submitted manually or with AI draft assistance.
5. Department head moderation may occur.
6. HR calibration may occur.
7. Score is calculated from OKRs, feedback, competencies, peers, and check-ins.
8. Review is finalized and published.
9. Audit logs preserve state transitions.

### Approval Queue Workflow

1. User opens approvals.
2. Backend returns pending subjects for the current approver.
3. User reviews OKR creation or progress subject.
4. User approves or rejects.
5. Chain advances or finalizes.
6. Subject status is synchronized.

## 27. Important Business Rules

Key rules encoded in services:

- Unknown roles degrade to `EMPLOYEE` instead of granting unexpected privileges.
- Users can create OKRs only at allowed objective levels.
- Users can generally create OKRs at their business level or one level below.
- `SUPER_ADMIN` bypasses many business-level restrictions.
- CEO and super admin can create at all objective levels.
- Team OKRs require teams.
- Individual OKRs require explicit employee assignment.
- Progress is blocked unless OKR lifecycle allows it.
- KR baseline editing is blocked after lifecycle locks it.
- Functional approval is required when functional parent/dotted-line context applies.
- Check-ins are coaching workflows, not approval chains.
- Regional/CEO roles are dashboard-level for individual review visibility, not direct individual reviewers.
- Review scoring redistributes weights when some evidence is missing.

## 28. Known Design Characteristics

The project shows several design decisions:

- Backward compatibility with older local SQLite databases.
- Gradual migration from rigid plant/department/team hierarchy to flexible `OrgNode`.
- Parallel support for legacy and enhanced review systems.
- Separation between route handlers and domain services.
- Strong workflow/state modeling for OKRs and reviews.
- Manufacturing-specific roles and hierarchy.
- Optional AI with deterministic fallback where needed.
- Heavy local-demo/script support for staged development.

## 29. Potential Risks and Gaps

These are not necessarily bugs, but important observations:

- The root governance files `PRD.md`, `techstack.md`, and `tracking.md` are absent, so project scope and prescribed conventions cannot be verified from source-of-truth docs.
- `SECRET_KEY` is hardcoded in `server/auth.py`.
- CORS allows all origins.
- SQLite is suitable for local development/demo, but production would likely need PostgreSQL or another managed database.
- `Base.metadata.create_all` plus custom SQLite migrations is practical locally but should be replaced or supplemented by a formal migration system for production.
- Some route context comes from query-param injection middleware, while newer routes use JWT dependencies directly. That mixed pattern can be confusing.
- There are two OKR model families, which may represent a migration or unfinished consolidation.
- Azure OpenAI defaults include a specific endpoint/deployment name; production deployments should make all AI configuration environment-driven.

## 30. How to Run Locally

Backend:

```bash
pip install -r requirements.txt
python main.py
```

Frontend:

```bash
cd frontend/performance-compass
npm install
npm run dev
```

Tests:

```bash
pytest
```

If using AI features, create a `.env` file at the project root with Azure OpenAI credentials:

```bash
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_API_VERSION=...
AZURE_OPENAI_DEPLOYMENT_NAME=...
```

## 31. Overall Interpretation

This is an enterprise-style manufacturing performance operating system. It is more than an OKR tracker. It models the organization structure, roles, hierarchy, approvals, dotted-line functional relationships, operational metric ingestion, coaching, performance reviews, and executive visibility.

The backend carries most of the business logic. The frontend provides role-aware surfaces for users to execute the workflows. AI is used as an assistant layer over structured workflows, not as the source of truth: generated OKRs still become normal objectives, generated reviews remain editable, and deterministic fallback behavior exists for performance review drafts.

The strongest parts of the project are the workflow modeling, manufacturing hierarchy support, OKR/review integration, and test coverage around critical behaviors. The main cleanup opportunities are production hardening, documentation restoration, model consolidation, and replacing local SQLite migration patterns with a formal production migration path.
