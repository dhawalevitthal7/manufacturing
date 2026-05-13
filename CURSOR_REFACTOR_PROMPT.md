# Manufacturing OKR Platform — Refactor Prompt for Cursor / Copilot

> **How to use this file:** Don't paste the entire document at once. The AI will lose track. Paste **one phase at a time**, verify the changes, commit, then move to the next phase. Each phase is self-contained and lists its files, acceptance criteria, and verification steps.

---

## Project Context (paste this header before EVERY phase)

You are working on a multi-tenant manufacturing performance OS built with:

- **Backend:** FastAPI + SQLAlchemy + JWT (SQLite in dev). Entry: `main.py`. Models in `server/models.py`. Schemas in `server/schemas.py`. Routers under `server/routes_*.py`. Services in `server/*_service.py` and `server/services/`.
- **Frontend:** Vite + React + TypeScript, TanStack Router (file-based, `src/routes/`), TanStack Query, Zustand stores (`auth-store.ts`, `ui-store.ts`), Tailwind, shadcn-style components. API client in `src/lib/api.ts`. Navigation definitions in `src/lib/navigation/definitions/*.ts`.
- **Core domain:** Organization → Plant → Department → Team → User. OKRs cascade vertically. RBAC = `system_role + designation + scope + module_permissions`.

**Before making ANY change in a phase:**
1. Read the files listed in "Files to read first".
2. Match existing patterns — naming, error handling, response shapes, migration style.
3. Do NOT rename, delete, or relocate files that are not explicitly listed in the phase.
4. Keep all existing API routes backward-compatible — add new ones, deprecate old ones with a comment, never break callers.
5. After every code change, update the matching Pydantic schema and the TypeScript type in `src/lib/api.ts`.
6. Run the app and verify the acceptance criteria at the end of the phase before claiming it done.

**Do NOT do these things:**
- Do not refactor the entire codebase to one "perfect" architecture in one shot.
- Do not rewrite the routing system, the auth flow, or the Zustand stores.
- Do not introduce new libraries (no Next.js, no Nest, no Prisma, no SWR, no Redux).
- Do not generate "TODO: implement later" stubs — finish each phase.
- Do not delete migration files. Add new ones with timestamps.

---

## Why we are refactoring (the diagnosis)

The current architecture has nine structural problems that will block enterprise adoption. The first six are hierarchy / data-model issues; the last three are role-modeling and integration issues:

1. **Region layer is missing.** Hierarchy is `Org → Plant → Department → Team → User`. Real multi-plant manufacturing companies have a `Region` (or `Cluster`, `Zone`) between Org and Plant. No CEO directly supervises 15 plant heads. The platform must model this.

2. **Corporate functions have no home.** CFO, CHRO, CMO, CTO, Company Secretary do not sit under a plant. They form a parallel sub-hierarchy at HQ. Currently the schema forces every node under a plant or treats them as floating users with no node — both wrong.

3. **Role-name drift.** `OKRHierarchyWorkflow` references `VP_MANUFACTURING`, `OPERATIONS_HEAD`, `OPERATOR`, `TECHNICIAN`. `DEFAULT_ROLE_CAPABILITIES` has a different set. Frontend `CanonicalRole` has yet another set. Comments in `User` model still mention `HR_ADMIN`, `PLANT_MANAGER`. This must be a single source of truth.

4. **Logic is keyed on role names, not levels.** `ROLE_CREATION_LEVELS` maps each role string to allowed levels. Adding a new role (e.g. `CLUSTER_HEAD`) requires touching this map plus capabilities plus nav. The right pattern is: store a **hierarchical level (0–6)** on the node + designation, and gate by level, not by role name.

5. **No matrix / dotted-line reporting.** Plant Finance reports to Plant Head (solid) AND CFO (dotted). Plant Quality reports to Plant Head (solid) AND Corporate Quality Head (dotted). Currently a user has one `manager_id`-style chain via `ReportingRelationship`, but OKR alignment and review aggregation only walk the solid line. Both must be walked.

6. **Employee cannot create OKRs.** `ROLE_CREATION_LEVELS["EMPLOYEE"] = []`. This is a KPI system, not OKRs. Engineers, planners, chemists, designers must be able to draft their own OKRs and route them for approval. Pure top-down assignment kills adoption above the shop floor.

7. **No first-class Cycle entity.** Quarter is stored as fields on the objective. A `Cycle` table with `start_date`, `end_date`, `freeze_date` is needed for review locking and cycle-over-cycle analytics.

8. **No connector hook for KR auto-update.** Plant-floor KRs (TPD, OEE, kcal/kg) come from SCADA / MES / SAP. The platform must expose a webhook/API path for ingesting KR values without manual entry.

9. **`SUPER_ADMIN` is treated as a business role.** Currently it sits in the same enum as `CEO`, `PLANT_HEAD`, etc., is mapped to "level 0" alongside CEO, and appears in OKR approval chains at every level. That conflates two different things:

   - **`SUPER_ADMIN`** is the **platform / tenant administrator** — the first user at company registration (`POST /api/auth/register` sets `system_role="SUPER_ADMIN"` and `is_org_creator=True`). Their job is to **build and govern the tenant**: create the org tree, invite users, manage designations, configure permissions, set up cycles, wire integrations. They have org-wide visibility and full module access by short-circuit in `_get_module_permissions`. They are the org's owner of *the platform*, not the org's owner of *the business*.

   - **`CEO`** is the **strategic top of the business**. They author org-level OKRs, approve regional/plant cascades, drive performance. They do not typically log into the platform to create plants — that's an HR/IT setup task that belongs to SUPER_ADMIN.

   In a small company the same person may hold both roles; in a 5,000-person manufacturing company they're different people. Conflating them produces three concrete bugs: (a) SUPER_ADMIN appears as default approver for strategic OKRs they have no business mandate to approve, (b) CEO incorrectly gets structure-creation flags (`can_create_plants`, etc.) when those should belong only to SUPER_ADMIN and HR_HEAD, (c) approval chains route to SUPER_ADMIN at the top of the tree instead of letting CEO self-publish org-level OKRs.

   **Related hardening gap:** `/api/org/*` endpoints in `routes_org.py` currently authorize on `org_id` from the JWT only — any logged-in user of an org can technically call `POST /api/org/plants`. The "only SUPER_ADMIN may create structure" intent is encoded in the permission profile and UI but is not enforced server-side. Failing-open is the wrong posture for structure-mutating endpoints.

---

# PHASE 1 — Introduce a unified `OrgNode` tree + add `Region`

**Goal:** Replace the rigid `Plant → Department → Team` chain with a self-referential `OrgNode` table so we can insert Region (and future levels) without schema migration pain. Keep the existing `Plant`, `Department`, `Team` tables as views/aliases for backward compatibility during this phase.

### Files to read first
- `server/models.py` — full file
- `server/schemas.py` — sections for Plant, Department, Team
- `server/routes_org.py`, `server/routes_hierarchy.py`
- `server/permissions_service.py` — `DEFAULT_ROLE_CAPABILITIES` and scope logic
- `frontend/performance-compass/src/lib/api.ts` — types

### Backend changes

1. **Add `OrgNode` model** in `server/models.py`:

   ```python
   class NodeType(str, enum.Enum):
       ORGANIZATION = "ORGANIZATION"
       REGION = "REGION"
       CORPORATE_FUNCTION = "CORPORATE_FUNCTION"
       PLANT = "PLANT"
       VERTICAL = "VERTICAL"          # sub-function under corp function
       DEPARTMENT = "DEPARTMENT"
       SUB_DEPARTMENT = "SUB_DEPARTMENT"
       TEAM = "TEAM"

   class OrgNode(Base):
       __tablename__ = "org_nodes"
       id = Column(Integer, primary_key=True)
       org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
       parent_id = Column(Integer, ForeignKey("org_nodes.id"), nullable=True, index=True)
       node_type = Column(SqlEnum(NodeType), nullable=False, index=True)
       name = Column(String, nullable=False)
       code = Column(String, nullable=True)   # e.g. "PLT-RAJ-01"
       head_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
       path = Column(String, nullable=False, index=True)   # materialized: "1.4.12.39"
       depth = Column(Integer, nullable=False, index=True) # 0 for org, increases downward
       node_metadata = Column(JSON, nullable=True)         # type-specific fields
       is_active = Column(Boolean, default=True)
       created_at = Column(DateTime, default=datetime.utcnow)
       updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

       parent = relationship("OrgNode", remote_side=[id], backref="children")
       head = relationship("User", foreign_keys=[head_user_id])
   ```

   Use a dotted-string `path` (not Postgres `ltree`) since the project is on SQLite. Index `path` and query with `LIKE 'X.Y.%'` for descendants.

2. **Add `User.org_node_id`** (nullable). Keep existing `plant_id`, `department_id`, `team_id` for now — they will be derived from `org_node_id` in Phase 2.

3. **Backfill migration.** Add `server/migrations/00XX_add_org_nodes.py` (match existing migration naming) that:
   - Creates `org_nodes` and `users.org_node_id`.
   - For each `Organization`, inserts a root node (`depth=0`, `parent_id=NULL`, `path='<org_id>'`).
   - For each existing `Plant`, inserts an `OrgNode` row of type `PLANT` under the org root.
   - For each `Department`, inserts a node of type `DEPARTMENT` under its plant's node.
   - For each `Team`, inserts a node of type `TEAM` under its department's node.
   - Sets `User.org_node_id` to the deepest node the user currently maps to (team → department → plant → org).
   - Leaves `Region` slots empty for Phase 2.

4. **Service helpers** in a new file `server/services/org_tree_service.py`:
   - `get_descendants(node_id) -> List[OrgNode]` — uses `path LIKE`.
   - `get_ancestors(node_id) -> List[OrgNode]` — splits `path`.
   - `is_descendant_of(child_id, ancestor_id) -> bool`.
   - `create_child_node(parent_id, node_type, name, ...) -> OrgNode` — computes `path` and `depth` from parent.
   - `move_node(node_id, new_parent_id)` — updates `path` for the node and ALL descendants.

5. **New routes** in a new file `server/routes_org_tree.py`, mounted at `/api/org-tree`:
   - `GET /api/org-tree` — returns the full tree for the user's org, scoped by permissions.
   - `GET /api/org-tree/{node_id}` — single node + immediate children.
   - `POST /api/org-tree` — create a node (requires `SUPER_ADMIN` or org-scope admin).
   - `PATCH /api/org-tree/{node_id}` — rename, move, set head.
   - `DELETE /api/org-tree/{node_id}` — soft delete (`is_active = false`), only if no descendants.

   Reuse existing JWT middleware. Do not duplicate auth code.

6. **Keep old endpoints working.** `routes_org.py`, `routes_hierarchy.py` continue to function. Internally, they should now also write to `OrgNode` when creating a plant/department/team — but the response shape stays identical so the frontend keeps working.

### Frontend changes

1. **Add types** in `src/lib/api.ts`:
   ```ts
   export type NodeType =
     | "ORGANIZATION" | "REGION" | "CORPORATE_FUNCTION"
     | "PLANT" | "VERTICAL" | "DEPARTMENT" | "SUB_DEPARTMENT" | "TEAM";

   export interface OrgNode {
     id: number;
     parent_id: number | null;
     node_type: NodeType;
     name: string;
     code: string | null;
     head_user_id: number | null;
     path: string;
     depth: number;
     node_metadata: Record<string, unknown> | null;
     children?: OrgNode[];
   }
   ```

2. **Add a query hook** `src/hooks/use-org-tree.ts` that fetches `/api/org-tree` and caches via TanStack Query.

3. **Do not yet change the existing Hierarchy / Plants / Departments / Teams pages.** That happens in Phase 7. Phase 1 must not break any current screen.

### Acceptance criteria (Phase 1)

- [ ] Migration runs cleanly on a fresh DB and on a DB with existing seed data.
- [ ] After migration, `SELECT COUNT(*) FROM org_nodes` equals `1 (org) + N (plants) + M (departments) + K (teams)` for each organization.
- [ ] `GET /api/org-tree` returns a nested tree for the test org.
- [ ] All existing tests pass. All existing frontend pages render unchanged.
- [ ] No console errors, no 500s on any current API call.

---

# PHASE 2 — Insert `Region` and `CorporateFunction` layers

**Goal:** Now that the tree exists, add the missing layers and migrate the data.

### Files to read first
- Output of Phase 1 (`server/models.py`, `routes_org_tree.py`, `org_tree_service.py`)
- `server/routes_org.py` — current Plant CRUD

### Backend changes

1. **Add helper endpoint** `POST /api/org-tree/regions` that creates a `REGION` node under the org root with a name (e.g. "North", "South").
2. **Add helper endpoint** `POST /api/org-tree/corporate-functions` that creates a `CORPORATE_FUNCTION` node under the org root with a name (e.g. "Finance", "HR", "Sales").
3. **Update `Plant` creation logic** in `routes_org.py`:
   - Accept an optional `region_id` (OrgNode id where `node_type = REGION`).
   - If provided, the new plant's `OrgNode` is created under that region instead of directly under the org root.
   - If not provided, plant continues to attach directly to the org (backward compatible).
4. **Add a one-time data migration script** `server/scripts/seed_default_region.py` that, for tenants with more than 3 plants, creates a single "Default Region" node and moves all plants under it. Document this script in `RBAC_IMPLEMENTATION.md` — do not run it automatically.

### Frontend changes

1. **Add Region management UI** under the existing Hierarchy page:
   - A new tab "Regions" listing all `REGION` nodes for the org.
   - Add/edit/delete region with name + code.
   - When creating a plant, the form now shows a Region dropdown (optional).
2. **Add Corporate Function management** as a second tab "Corporate Functions" on the same page.
3. **Update `OrgChart` / hierarchy visualization** (if it exists) to render Region and Corporate Function as two columns under the org root, with plants nesting under regions.

### Acceptance criteria (Phase 2)

- [ ] User with `SUPER_ADMIN` can create a Region, then create a Plant under that Region.
- [ ] `GET /api/org-tree` returns: Org → [Regions, Corporate Functions] → [Plants under regions, Departments under corp functions] → ...
- [ ] Existing plants without a region still show up in the tree directly under the org.
- [ ] OKR cascade still works (test by creating an OKR at org level, then plant level pointing to it).

---

# PHASE 3 — Consolidate role taxonomy (single source of truth)

**Goal:** Eliminate the role-name drift between `OKRHierarchyWorkflow`, `DEFAULT_ROLE_CAPABILITIES`, `CanonicalRole`, and User model comments.

### Files to read first
- `server/permissions_service.py` — `DEFAULT_ROLE_CAPABILITIES`
- `server/okr_hierarchy_workflow.py` — `ROLE_CREATION_LEVELS`, `APPROVAL_ROLES_BY_LEVEL`
- `server/permission_registry.py`
- `server/models.py` — `User.system_role`, the legacy enum
- `frontend/performance-compass/src/lib/navigation/role-nav-types.ts` — `CanonicalRole`
- `frontend/performance-compass/src/lib/navigation/role-sidebar-nav.ts` — `normalizeCanonicalRole`

### Backend changes

1. **Create a single roles module** `server/roles.py` with the canonical enum:

   ```python
   class SystemRole(str, enum.Enum):
       # ---- Platform administration role (NOT part of the business hierarchy) ----
       # Assigned automatically to the first user at company registration
       # (POST /api/auth/register sets system_role=SUPER_ADMIN, is_org_creator=True).
       # Owns tenant setup: org tree, designations, users, permissions, cycles,
       # integrations. Has org-wide visibility and short-circuits to all module
       # permissions in _get_module_permissions. Does NOT, by default, approve
       # business OKRs — that responsibility flows up the business chain to CEO.
       # A SUPER_ADMIN MAY also hold a business role (e.g. also be CEO) in a
       # small company; the platform treats them as two distinct grants on
       # the same user. Day-to-day, in a large enterprise, SUPER_ADMIN is held
       # by an HR ops or IT admin person — not a business leader.
       SUPER_ADMIN = "SUPER_ADMIN"

       # ---- Business hierarchy roles (mapped to levels in ROLE_TO_BUSINESS_LEVEL) ----
       CEO = "CEO"
       VP_OPERATIONS = "VP_OPERATIONS"      # regional/multi-plant ops
       REGIONAL_HEAD = "REGIONAL_HEAD"      # NEW — heads a Region node
       PLANT_HEAD = "PLANT_HEAD"
       DEPT_HEAD = "DEPT_HEAD"
       MANAGER = "MANAGER"
       TEAM_LEAD = "TEAM_LEAD"
       SUPERVISOR = "SUPERVISOR"
       EMPLOYEE = "EMPLOYEE"
       HR_HEAD = "HR_HEAD"
       CFO = "CFO"                          # NEW — corporate function head
       CMO = "CMO"                          # NEW
       CTO = "CTO"                          # NEW
   ```

   Drop these from any active code (keep only in a `LEGACY_ROLE_ALIASES` dict for normalization): `VP_MANUFACTURING`, `OPERATIONS_HEAD`, `OPERATOR`, `TECHNICIAN`, `HR_ADMIN`, `PLANT_MANAGER`, `FACTORY_DIRECTOR`.

   Reason: Operator/Technician/Inspector are **designations**, not system roles. They all map to `system_role = EMPLOYEE` with different `designation_id`s. Factory Director / Plant Manager / Works Director all map to `system_role = PLANT_HEAD` with different designation names.

2. **Add a level mapping** (business roles only — SUPER_ADMIN is intentionally excluded):
   ```python
   # SUPER_ADMIN is NOT in this map. It is a platform role, not a business
   # hierarchy role. Code that needs a level for a SUPER_ADMIN user should
   # treat it as None and bypass level-based gates (with audit logging).
   ROLE_TO_BUSINESS_LEVEL = {
       SystemRole.CEO: 0,
       SystemRole.CFO: 1,
       SystemRole.CMO: 1,
       SystemRole.CTO: 1,
       SystemRole.HR_HEAD: 1,
       SystemRole.VP_OPERATIONS: 1,
       SystemRole.REGIONAL_HEAD: 1,
       SystemRole.PLANT_HEAD: 2,
       SystemRole.DEPT_HEAD: 3,
       SystemRole.MANAGER: 4,
       SystemRole.TEAM_LEAD: 5,
       SystemRole.SUPERVISOR: 5,
       SystemRole.EMPLOYEE: 6,
   }

   def get_business_level(role: SystemRole) -> int | None:
       """Returns None for SUPER_ADMIN (no business level)."""
       return ROLE_TO_BUSINESS_LEVEL.get(role)
   ```

3. **Replace `ROLE_CREATION_LEVELS` with level-based logic** in `okr_hierarchy_workflow.py`:
   ```python
   def can_create_okr_at_level(
       role: SystemRole,
       user_business_level: int | None,
       target_level: int,
   ) -> bool:
       # Platform admins bypass business-level gating (tenant setup / support).
       # SUPER_ADMIN typically seeds initial OKRs during onboarding and then
       # hands off to CEO and business owners. Any OKR created by SUPER_ADMIN
       # MUST write an audit log row (see hardening item below).
       if role == SystemRole.SUPER_ADMIN:
           return True
       if user_business_level is None:
           # User has no business role assigned — cannot create business OKRs.
           return False
       # A business user can create at their own level and the level immediately below.
       return target_level in (user_business_level, user_business_level + 1)
   ```

   This single function replaces every per-role hardcoded list. Adding a new business role tomorrow needs zero changes here — just add it to `ROLE_TO_BUSINESS_LEVEL`.

4. **Update `DEFAULT_ROLE_CAPABILITIES`** to use `SystemRole` enum members as keys, drop any deprecated role keys, and add entries for `REGIONAL_HEAD`, `CFO`, `CMO`, `CTO`. Capability flags must be assigned with role intent in mind:

   - **`SUPER_ADMIN`** is the only role with all of `can_create_plants`, `can_create_departments`, `can_create_teams`, `can_create_designations`, `can_configure_permissions`, `can_assign_roles`, `can_invite_employees`, `can_access_audit_logs`, `can_access_analytics` set to `True`. Scope = ORGANIZATION. Module permissions return full (view/create/edit/approve/delete) for every dashboard module via the existing short-circuit in `_get_module_permissions`.
   - **`CEO`** keeps org-wide visibility (`can_view_all_*`, `can_access_analytics`) but **does NOT** get `can_create_plants/departments/teams/designations` or `can_configure_permissions`. The CEO drives strategy, not structure.
   - **`HR_HEAD`** keeps `can_invite_employees`, `can_access_audit_logs`, and review-admin flags but does NOT get plant/department creation.
   - **`REGIONAL_HEAD`** gets plant/department/team visibility for their region only (scope=PLANT path-filtered to their region subtree). No structure-creation flags.
   - **`CFO`/`CMO`/`CTO`** get org-wide visibility within their functional subtree only. No structure-creation flags.
   - All other business roles (`PLANT_HEAD` and below) keep their existing capability shape, just normalized to the new enum.

5. **Add a normalization function** `normalize_role(raw: str) -> SystemRole` in `server/roles.py` that maps legacy strings (`PLANT_MANAGER` → `PLANT_HEAD`, `HR_ADMIN` → `HR_HEAD`, `VP_MANUFACTURING` → `VP_OPERATIONS`, `OPERATIONS_HEAD` → `PLANT_HEAD`, `OPERATOR` → `EMPLOYEE`, `TECHNICIAN` → `EMPLOYEE`, `INSPECTOR` → `EMPLOYEE`, `FACTORY_DIRECTOR` → `PLANT_HEAD`). Call this in `routes_auth.py` on login and in any place that reads `User.system_role` from the DB. Existing user rows are not migrated — normalization happens on read.

6. **Update User model comment** to reference `server/roles.py` as the source of truth. Remove stale role names from the comment.

7. **Harden `/api/org/*` endpoints with explicit role checks.** `routes_org.py` currently authorizes on `org_id` from the JWT only — there is no role guard on `POST /api/org/plants`, `POST /api/org/departments`, etc. Add two FastAPI dependencies in `server/auth.py`:

   ```python
   def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
       if current_user.system_role != SystemRole.SUPER_ADMIN:
           raise HTTPException(403, "SUPER_ADMIN role required for this operation.")
       return current_user

   def require_super_admin_or_hr_head(current_user: User = Depends(get_current_user)) -> User:
       if current_user.system_role not in (SystemRole.SUPER_ADMIN, SystemRole.HR_HEAD):
           raise HTTPException(403, "SUPER_ADMIN or HR_HEAD role required.")
       return current_user
   ```

   Apply `require_super_admin` to every mutating endpoint in `routes_org.py`, `routes_org_tree.py` (from Phase 1), and structure-creation endpoints in `routes_permissions.py`/`routes_permission_matrix.py`. Apply `require_super_admin_or_hr_head` to `POST /api/auth/onboard-employee` and bulk invitation endpoints. Read endpoints (GET) continue to be scope-filtered through the existing permission profile — no role guard needed.

8. **Audit log every SUPER_ADMIN write.** Add a small helper `audit_super_admin_action(action: str, target: str, metadata: dict)` and call it from every endpoint protected by `require_super_admin`. Reason: SUPER_ADMIN actions are the riskiest writes in the system (tenant-wide blast radius) and must always be traceable to a human + timestamp + IP. The audit log entity already exists per the routes inventory; add `actor_role` and `is_admin_override` columns if not present.

9. **Decouple `SUPER_ADMIN` from OKR approval chains.** Remove `SUPER_ADMIN` from `APPROVAL_ROLES_BY_LEVEL` for every level. SUPER_ADMIN keeps a separate manual override (defined in Phase 6) but is not in the default routing. Reason: a CEO submitting an org-level OKR should not have it gated by an HR ops person who happens to hold the SUPER_ADMIN grant.

### Frontend changes

1. **Replace `CanonicalRole` union** in `role-nav-types.ts` with a union built from the backend enum. Generate or hand-mirror — keep them identical:
   ```ts
   export type SystemRole =
     | "SUPER_ADMIN" | "CEO" | "VP_OPERATIONS" | "REGIONAL_HEAD"
     | "PLANT_HEAD" | "DEPT_HEAD" | "MANAGER" | "TEAM_LEAD"
     | "SUPERVISOR" | "EMPLOYEE" | "HR_HEAD"
     | "CFO" | "CMO" | "CTO";
   ```

2. **Update `normalizeCanonicalRole`** to handle every legacy alias from the backend list. Any unknown role returns `EMPLOYEE`. Log a console warning for unknowns in dev mode.

3. **Add navigation definitions** for `REGIONAL_HEAD`, `CFO`, `CMO`, `CTO` in `src/lib/navigation/definitions/`. Use existing files as a pattern:
   - `REGIONAL_HEAD` — similar to `VP_OPERATIONS` but scope is one region, not org.
   - `CFO`, `CMO`, `CTO` — similar to `HR_HEAD` (org-wide function scope, no plant admin), but module list filtered to their function.

4. **Add the new roles to** `definitions/index.ts` merge.

### Acceptance criteria (Phase 3)

- [ ] `grep -r "VP_MANUFACTURING\|OPERATIONS_HEAD\|HR_ADMIN\|PLANT_MANAGER\|FACTORY_DIRECTOR\|OPERATOR\|TECHNICIAN" server/` returns ONLY hits in `LEGACY_ROLE_ALIASES` and migration files. Active code paths use only `SystemRole` enum values.
- [ ] A user with legacy role `PLANT_MANAGER` in the DB can still log in and is routed as `PLANT_HEAD`.
- [ ] All four new roles (`REGIONAL_HEAD`, `CFO`, `CMO`, `CTO`) can be assigned to a user and produce the correct sidebar.
- [ ] Removing a role from `ROLE_CREATION_LEVELS` is no longer necessary — the level check replaces it. Confirm by reading the new `can_create_okr_at_level` in tests.
- [ ] `get_business_level(SystemRole.SUPER_ADMIN)` returns `None`. `get_business_level(SystemRole.CEO)` returns `0`.
- [ ] A non-SUPER_ADMIN user calling `POST /api/org/plants` receives HTTP 403. A SUPER_ADMIN succeeds AND an audit log row is written with `actor_role=SUPER_ADMIN`.
- [ ] `SUPER_ADMIN` does NOT appear in `APPROVAL_ROLES_BY_LEVEL` for any level.
- [ ] `CEO` capability profile has `can_create_plants=False`, `can_create_departments=False`, `can_create_teams=False`, `can_configure_permissions=False`. Verified by a test that asserts this explicitly — these flags belong to SUPER_ADMIN, not CEO.
- [ ] A test creates a fresh org via `POST /api/auth/register`, confirms the registered user has `system_role=SUPER_ADMIN` and `is_org_creator=True`, and confirms they can complete the structure setup flow end to end without any 403.

---

# PHASE 4 — Dual reporting (matrix structure)

**Goal:** Allow a plant department to have a primary reporting line to the Plant Head and a functional dotted line to a corporate function head. OKR alignment walks both.

### Files to read first
- `server/models.py` — `ReportingRelationship` (already exists with `DIRECT`, `DOTTED_LINE`, `REVIEWER`, `APPROVER`)
- `server/okr_cascade_service.py` — current cascade walk
- `server/routes_okrs_hierarchy.py` — validation

### Backend changes

1. **Extend `OrgNode`** with `functional_parent_id` (nullable, FK to `org_nodes.id`). This is the dotted-line node. Example: Plant Finance department's `parent_id` = Plant node, `functional_parent_id` = CFO's Corporate Function node.

2. **Update `Objective` model** to allow multiple parents:
   - Option A (simpler): Add `functional_parent_obj_id` alongside the existing `parent_id`. Two parent slots.
   - Option B (cleaner): Add an `objective_alignment` join table with `(child_obj_id, parent_obj_id, alignment_type)` where type is `PRIMARY` or `FUNCTIONAL`.

   **Choose Option A for v1.** The join table is correct long-term but doubles the query complexity right now.

3. **Update cascade math in `okr_cascade_service.py`:**
   - When computing rollup progress for a parent, include children where parent matches via EITHER `parent_id` OR `functional_parent_obj_id`.
   - When the same child rolls into two parents, its weight contributes to both — this is intentional. Document it in a comment.

4. **Update validation chain** in `okr_hierarchy_workflow.py`:
   - When a Plant Finance OKR is submitted, BOTH the Plant Head AND the CFO appear in the validation chain (in parallel, not series — either can approve).
   - Track approvals separately: `primary_approved_at`, `functional_approved_at`. OKR is fully approved when both are set.

5. **Add API endpoint** `POST /api/org-tree/{node_id}/functional-parent` to set the dotted line. Restricted to `SUPER_ADMIN` and `CEO`.

### Frontend changes

1. **Org tree visualization:** render solid lines for `parent_id`, dashed lines for `functional_parent_id`. Use a different stroke color (muted secondary) for dashed.
2. **OKR creation form:** when the OKR's owning node has a `functional_parent_id`, show a second optional dropdown "Functional alignment parent" alongside the primary parent dropdown.
3. **OKR detail page:** show both parents if both exist. Approval status shows two badges (Primary ✓, Functional ⏳).

### Acceptance criteria (Phase 4)

- [ ] Can set Plant Finance department's functional parent to the CFO node.
- [ ] Creating an OKR in Plant Finance auto-suggests both parent OKRs (Plant Head's and CFO's) in the alignment dropdown.
- [ ] Rollup at Plant Head and CFO both include the Plant Finance OKR's progress.
- [ ] Approval workflow notifies both approvers; either's approval moves the OKR to "fully approved" only when the other also approves.

---

# PHASE 5 — First-class Cycle entity

**Goal:** Replace quarter/year string fields on `Objective` with a proper `Cycle` table.

### Files to read first
- `server/models.py` — `Objective` cycle/quarter/year fields
- `server/routes_okrs.py` — cycle filtering

### Backend changes

1. **Add `Cycle` model:**
   ```python
   class CycleType(str, enum.Enum):
       ANNUAL = "ANNUAL"
       HALF_YEARLY = "HALF_YEARLY"
       QUARTERLY = "QUARTERLY"
       MONTHLY = "MONTHLY"

   class CycleStatus(str, enum.Enum):
       PLANNED = "PLANNED"
       ACTIVE = "ACTIVE"
       FROZEN = "FROZEN"      # progress locked, review window open
       CLOSED = "CLOSED"

   class Cycle(Base):
       __tablename__ = "cycles"
       id = Column(Integer, primary_key=True)
       org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
       name = Column(String, nullable=False)            # "Q1-2026", "FY26"
       cycle_type = Column(SqlEnum(CycleType), nullable=False)
       start_date = Column(Date, nullable=False)
       end_date = Column(Date, nullable=False)
       freeze_date = Column(Date, nullable=False)       # after this, no progress edits
       status = Column(SqlEnum(CycleStatus), default=CycleStatus.PLANNED)
       applies_to_levels = Column(JSON, default=list)   # which depths use this cycle, e.g. [0,1,2] for strategic, [3,4,5,6] for tactical
   ```

2. **Migrate existing `Objective.quarter` / `year` data** into `Cycle` rows. For each unique (org_id, quarter, year), create a `Cycle` row and update objectives to reference it via `cycle_id`. Keep the old columns for one release as fallback, then drop in a future migration.

3. **Add cycle management endpoints** in a new `server/routes_cycles.py` at `/api/cycles`:
   - `GET /api/cycles` — list, filter by status.
   - `POST /api/cycles` — create (admin only).
   - `PATCH /api/cycles/{id}/freeze` — moves status to FROZEN.
   - `PATCH /api/cycles/{id}/close` — moves to CLOSED.

4. **Enforce freeze:** in `routes_progress.py`, reject any `ProgressSubmission` or `ProgressUpdate` whose KR's objective's cycle is `FROZEN` or `CLOSED`. Return 409 with a clear message.

### Frontend changes

1. **Add a cycle picker** to the global topbar — defaults to currently active cycle for the user's level.
2. **Cycle admin page** under Settings — list, create, freeze, close cycles.
3. **OKR list pages** filter by cycle by default (URL param `?cycle=Q1-2026`).
4. **Frozen-cycle UI:** progress submission inputs become read-only; show a banner explaining the cycle is frozen.

### Acceptance criteria (Phase 5)

- [ ] Existing OKRs are reachable under their migrated cycle.
- [ ] Creating a new OKR requires picking a cycle (or defaults to the active one).
- [ ] Freezing a cycle prevents new progress submissions but allows reviews to proceed.

---

# PHASE 6 — Let employees draft OKRs (with approval)

**Goal:** Remove the rigid `EMPLOYEE → []` block. Any user can DRAFT an OKR at their own level; their manager approves to make it active.

### Files to read first
- `server/okr_hierarchy_workflow.py` — `ROLE_CREATION_LEVELS` (already removed in Phase 3)
- `server/models.py` — `Objective.creation_approval_status`, `okr_status`

### Backend changes

1. **State machine for `okr_status`:**
   `DRAFT → PENDING_APPROVAL → ACTIVE → ACHIEVED/MISSED → ARCHIVED`. Add `REJECTED` as a terminal state with a `rejection_reason` field.

2. **Creation flow:**
   - Any authenticated user can `POST /api/okrs` with their own `owner_id` and an `org_node_id` they belong to or lead. Status is set to `DRAFT`.
   - User submits with `POST /api/okrs/{id}/submit-for-approval`. Status → `PENDING_APPROVAL`. `next_approver_role` set to the head of the immediate parent node.
   - Approver acts via `POST /api/okrs/{id}/approve` or `/reject` (existing endpoints — extend, don't duplicate).
   - On approve, status → `ACTIVE`. KR baselines lock.

3. **Update `can_create_okr_at_level`** to allow self-OKRs always (level 6 employees can create at level 6).

4. **Approval auto-routing.** The default approver is whoever heads the OKR's parent node. Three special cases:

   - **CEO-owned org-level OKRs (top of business chain).** No higher business approver exists in the system. The CEO self-publishes via a dedicated endpoint `POST /api/okrs/{id}/publish`: state goes `DRAFT → ACTIVE` directly, skipping `PENDING_APPROVAL`. Do NOT route to SUPER_ADMIN — SUPER_ADMIN is a platform role and has no business mandate to approve strategy. The publish action writes an audit row noting "self-published by CEO, no higher approver."

   - **Head is also the owner** (e.g. Plant Head writes their own plant OKR). Walk up the tree: route to the head of the parent node (Region head, then VP_OPERATIONS, then CEO). If the walk reaches the org root, fall back to CEO self-publish logic above.

   - **Owner has no business role assigned** (rare — usually a misconfigured user). Reject the submission with HTTP 400 "User has no business role; assign one before drafting OKRs."

5. **`SUPER_ADMIN` is never in the default approval chain for a business OKR.** When walking up the tree to find an approver, skip any node whose head is a SUPER_ADMIN-only user (no business role). If the only candidate is SUPER_ADMIN, treat it as "no business approver above" and apply the CEO self-publish rule (if owner is CEO) or escalate to CEO (if owner is below CEO).

6. **`SUPER_ADMIN` override endpoint:** SUPER_ADMIN retains a manual override `POST /api/okrs/{id}/admin-approve` and `POST /api/okrs/{id}/admin-reject`, each requiring an `override_reason` text field. Used for support cases — CEO unavailable, urgent compliance OKR, data correction. Every call writes a high-severity audit log entry (`is_admin_override=True`). This is the ONLY way SUPER_ADMIN touches OKR approval. The UI exposes this only on a SUPER_ADMIN-scoped Admin tools page, never in the regular Approvals queue, so that SUPER_ADMIN users who are not business leaders don't accidentally use it as their default flow.

### Frontend changes

1. **Show a "Draft New OKR" button** on every user's My OKRs page, regardless of role.
2. **Approval queue page** (`/approvals`) shows pending OKRs for the current user as approver. Hide this page from SUPER_ADMIN-only users (no business role) — their override is on a separate Admin tools page.
3. **Status badges** on every OKR card reflecting the state machine.
4. **CEO "Publish" button** on org-level draft OKRs — distinct from "Submit for approval" since CEO bypasses the approval queue.
5. **SUPER_ADMIN Admin tools page** (`/admin/okr-overrides`) — table of all in-flight OKRs with `admin-approve` and `admin-reject` actions. Each action shows a modal requiring `override_reason`. Display a warning banner: "Use only when the business approver is unavailable. Every action is audited."

### Acceptance criteria (Phase 6)

- [ ] A user with `EMPLOYEE` role can create a draft OKR, submit it, and have it appear in their manager's approval queue.
- [ ] Manager approves; OKR becomes ACTIVE; progress submissions become possible.
- [ ] Manager rejects with reason; employee sees the rejection reason and can edit and resubmit.
- [ ] A CEO drafts an org-level OKR and publishes it directly (no intermediate `PENDING_APPROVAL` state). The audit log shows "self-published by CEO."
- [ ] A SUPER_ADMIN-only user (no business role) does NOT see the `/approvals` page in the sidebar. They DO see the `/admin/okr-overrides` page.
- [ ] When a Plant Head (whose parent node is headed by a SUPER_ADMIN-only user with no business role) submits an OKR, the system skips the SUPER_ADMIN and routes to CEO.
- [ ] Calling `POST /api/okrs/{id}/admin-approve` without `override_reason` returns HTTP 400. With it, the OKR is approved and `audit_logs` has a row with `is_admin_override=True`.

---

# PHASE 7 — Frontend hierarchy refactor

**Goal:** Replace the Plant/Department/Team pages with a unified Org Tree explorer. Keep deep-link URLs working.

### Files to read first
- All `src/routes/` files
- `src/components/` directory listing

### Frontend changes

1. **New page `src/routes/org-tree.tsx`** showing the full tree with expand/collapse, search, and node detail panel on the right. Use a tree component (build one with shadcn primitives, no new library).
2. **Keep `src/routes/hierarchy.tsx`, `plants.tsx`, etc.** but redirect them to `/org-tree?focus=<node_id>` to preserve old links. Mark them deprecated in code comments.
3. **Node detail panel** shows: head, member count, child nodes, OKRs at this node, and (for plants and departments) the functional parent link.
4. **Permissions:** the org tree page filters visible nodes by the user's scope. A `PLANT_HEAD` sees their plant subtree only.

### Acceptance criteria (Phase 7)

- [ ] `/org-tree` loads the full tree for `SUPER_ADMIN`, only the scoped subtree for others.
- [ ] Old URLs `/plants`, `/departments`, `/teams` still work (redirect).
- [ ] Search by node name works.

---

# PHASE 8 — KR auto-ingest webhook

**Goal:** Expose a webhook so SCADA / MES / SAP can push KR values without manual entry. This is the killer feature for plant adoption.

### Backend changes

1. **Add `KRIngestSource` model:** holds per-KR auto-update configuration:
   - `key_result_id`, `source_system` (e.g. "SAP", "WONDERWARE", "PI_SYSTEM"), `source_metric_tag`, `transform_expr` (optional simple math), `api_token_hash`.
2. **Add endpoint** `POST /api/integrations/kr-ingest`:
   - Header `X-Ingest-Token` validates against the source's hashed token.
   - Body: `{ "source_metric_tag": "RAJ1.KILN1.TPD", "value": 8432.5, "timestamp": "..." }`.
   - Service looks up the matching `KRIngestSource`, applies transform, writes a `ProgressUpdate` with `source = "AUTO_INGEST"`.
3. **Rate limit** at 60 requests/minute per source.
4. **Audit log:** every ingest writes to existing audit_logs table.

### Frontend changes

1. **KR edit dialog:** add an "Auto-update" toggle. When on, show fields for source system, metric tag, transform. Show last ingest timestamp.
2. **KR detail page:** show a "Live" badge for KRs with active auto-ingest.

### Acceptance criteria (Phase 8)

- [ ] A KR can be configured to auto-update from a source tag.
- [ ] Posting to `/api/integrations/kr-ingest` with a valid token updates the KR's `current_value` and creates an audit trail.
- [ ] Manual progress submission on an auto-ingest KR is still allowed (override) but flagged in the audit log.

---

## Global verification checklist (run after every phase)

```bash
# Backend
cd server
python -m pytest                                  # all tests pass
python -m alembic upgrade head                    # migrations clean
python -m alembic downgrade -1 && python -m alembic upgrade head   # reversible
grep -rn "TODO\|FIXME\|XXX" .                     # no new TODOs left from this phase

# Frontend
cd frontend/performance-compass
pnpm typecheck                                    # no TS errors
pnpm lint                                         # no lint errors
pnpm build                                        # production build succeeds
```

Manual sanity test after each phase:
1. Log in as `SUPER_ADMIN`, `PLANT_HEAD`, `MANAGER`, `EMPLOYEE` (one each).
2. Visit every page in the sidebar. No 500s, no React error boundaries.
3. Create an OKR end-to-end (draft → submit → approve → progress → review).

---

## How to invoke this prompt in Cursor

Paste this into Cursor as the kickoff message:

> Read `CURSOR_REFACTOR_PROMPT.md` in the repo root. We are starting **Phase 1**. Follow the instructions in Phase 1 exactly. Before writing any code, list the files you will read, the files you will create, and the files you will modify. Wait for my confirmation before writing code. When done, run the acceptance criteria checks and report results.

After Phase 1 is verified and committed, kick off Phase 2 with the same pattern. Do not let Cursor batch phases — it will overlook details.

---

## Things this refactor does NOT include (deliberately)

- **Performance review redesign.** The current 5-stage flow (Self → Manager → Skip → Calibration → Final) is good. Don't touch it until OKR foundation is solid.
- **AI suggestion changes.** Current AI integration is fine. Revisit after the data model stabilizes.
- **Alignment constellation viz.** Build this in a separate effort once Phase 4 (dual reporting) is done — the viz depends on the matrix structure.
- **Mobile apps.** Future scope.

These are the right things to defer. Resist scope creep during the refactor.
