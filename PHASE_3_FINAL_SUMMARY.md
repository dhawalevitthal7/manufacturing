# Phase 3 — final summary (checkpoint)

## Carry-forward to Phase 4

- **REGION scope vs OKR assignment:** `server/okr_hierarchy_workflow.py` — `can_assign_okr_to_user` does not include `REGION` in the PLANT/DEPARTMENT/TEAM assignee allow-lists. A `REGIONAL_HEAD` who creates a PLANT-level OKR may be unable to assign it to plant employees under their region until Phase 4 replaces coarse lists with **path-based** hierarchy checks. See the inline NOTE in that method.

Related operator script after capability-matrix deploys: `scripts/backfill_permission_profiles.py` (documented in `RBAC_IMPLEMENTATION.md`).
