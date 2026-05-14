# SUB-STEP 3.2 PLAN: Wire normalize_role INTO AUTH FLOW
**Status:** Ready for approval  
**Date:** 2026-05-14  
**Objective:** Ensure every place the system reads a user's role from the DB or JWT runs it through `normalize_role`, so that downstream code sees only canonical SystemRole values.

---

## FINDINGS SUMMARY

### (a) JWT Generation and get_current_user (server/auth.py)

**JWT Creation (encode time):**
```python
# Line 25-27: create_access_token()
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
```
**Current behavior:** The JWT is created with claim `"role"` = raw `user.system_role` from DB (no normalization).

**JWT Verification (decode time):**
```python
# Line 32-37: decode_access_token()
def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
```
**Current behavior:** Raw payload returned; no normalization applied.

**require_super_admin dependency (Line 54-60):**
```python
def require_super_admin(payload: dict = Depends(get_jwt_payload)) -> dict:
    system_role = payload.get("system_role") or payload.get("role")
    if system_role != "SUPER_ADMIN":
        raise HTTPException(403, "SUPER_ADMIN role required for this operation")
    return payload
```
**Issue:** Compares raw JWT role against hardcoded string. If JWT contains legacy "PLANT_MANAGER", this check will reject valid PLANT_HEAD users. Needs to normalize before comparison.

---

### (b) Login Response Construction (server/routes_auth.py)

Three endpoints create JWTs and return user objects. All three follow the same pattern:

**1. onboard_employee (Line 84):**
```python
token = create_access_token({"sub": user.id, "org_id": user.org_id, "role": user.system_role})
return TokenResponse(
    access_token=token,
    user=_user_dict(user, org, db),
)
```

**2. register (Line 124):**
```python
token = create_access_token({"sub": user.id, "org_id": org.id, "role": user.system_role})
return TokenResponse(
    access_token=token,
    user=_user_dict(user, org, db),
)
```

**3. login (Line 144):**
```python
token = create_access_token({"sub": user.id, "org_id": user.org_id, "role": user.system_role})
return TokenResponse(
    access_token=token,
    user=_user_dict(user, org, db),
)
```

**_user_dict response (Line 181-196):**
```python
def _user_dict(user, org, db):
    """Build user response dict with permissions."""
    perm_profile = get_user_permission_profile(user.id, db)
    
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "employee_id": user.employee_id,
        "system_role": user.system_role,  # ← Line 183: raw DB value
        ...
        "permissions": perm_profile,
    }
```
**Issue:** Frontend receives raw `system_role` from DB. If a legacy "PLANT_MANAGER" row exists in DB, frontend sees "PLANT_MANAGER" instead of canonical "PLANT_HEAD".

---

### (c) Permissions Service Role Usage (server/permissions_service.py)

**initialize_user_permissions (Line 239 + 254):**
```python
def initialize_user_permissions(user: User, db: Session) -> UserPermissionProfile:
    ...
    # Line 239: Direct DB read
    profile.system_role = user.system_role
    
    # Line 254: Lookup against hardcoded capability dict
    capabilities = DEFAULT_ROLE_CAPABILITIES.get(user.system_role, DEFAULT_ROLE_CAPABILITIES["EMPLOYEE"])
```

**Issue:** 
- If `user.system_role` = "PLANT_MANAGER", the lookup `.get("PLANT_MANAGER", ...)` returns the default ("EMPLOYEE"), incorrectly assigning minimal capabilities.
- Legacy role values are silently downgraded to EMPLOYEE instead of being normalized to their correct capability set.

**DEFAULT_ROLE_CAPABILITIES keys:**
- "SUPER_ADMIN", "CEO", "VP_OPERATIONS", "PLANT_HEAD", "DEPT_HEAD", "MANAGER", "TEAM_LEAD", "SUPERVISOR", "EMPLOYEE", "HR_HEAD"

These are all canonical; any legacy values missing from this dict get downgraded to EMPLOYEE.

---

### (d) Middleware / User Scope Resolution (server/routes_org_tree.py)

**get_current_user_from_db (Line 28-38):**
```python
def get_current_user_from_db(db: Session, user_payload: dict) -> User:
    """Fetch the current user from DB given JWT payload."""
    user_id = user_payload.get("user_id") or user_payload.get("id")
    if not user_id:
        raise HTTPException(401, "No user_id in token")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(401, "User not found")
    
    return user
```

**get_user_scope (Line 41-71):**
```python
def get_user_scope(user: User, db: Session) -> tuple:
    ...
    # Line 65: Direct comparison
    if user.system_role == "SUPER_ADMIN":
        return ("ORGANIZATION", None)
    
    if perm:
        scope_type = perm.scope_type
        if scope_type == "ORGANIZATION":
            return ("ORGANIZATION", None)
        ...
```

**Issue:** Direct string comparison `user.system_role == "SUPER_ADMIN"`. If user.system_role is legacy value like "HR_ADMIN" that was historically a high-privilege role, this fails and silently falls through to lower-privilege scope.

---

### (e) Grep Results: All system_role References in server/

**Critical normalization points:**

1. **JWT Creation (encode time):**
   - `routes_auth.py:84` — onboard_employee
   - `routes_auth.py:124` — register
   - `routes_auth.py:144` — login

2. **JWT Verification (decode time):**
   - `auth.py:57` — require_super_admin (compares `payload.get("role")`)

3. **Role Lookups / Comparisons:**
   - `routes_org_tree.py:65` — `if user.system_role == "SUPER_ADMIN":`
   - `okr_hierarchy_workflow.py:120-121` — `workflow.ROLE_CREATION_LEVELS.get(system_role)`
   - `okr_hierarchy_workflow.py:351, 362, 373, 386, 403` — `User.system_role.in_([...])` queries
   - `okr_hierarchy_workflow.py:552, 556, 560, 570, 580` — `if user.system_role in [...]`
   - `routes_okrs_hierarchy.py:47` — `workflow.ROLE_CREATION_LEVELS.get(user.system_role)`
   - `permissions_service.py:254` — `DEFAULT_ROLE_CAPABILITIES.get(user.system_role)`
   - `routes_permission_matrix.py:62, 105` — `RolePermissionRule.system_role == role`
   - `routes_hierarchy.py:118, 148` — returning role in responses
   - `routes_employees.py:42, 43, 91` — filtering and returning role

4. **Response Construction:**
   - `routes_auth.py:183` — `_user_dict()` returns `"system_role": user.system_role`
   - `routes_hierarchy.py:118, 148` — responses include raw role
   - `routes_employees.py:91, 198` — responses include raw role
   - `routes_okrs_hierarchy.py:52, 126, 127, 157, 392, 476` — responses include raw role

---

## 3.2 PLAN: Implementation Strategy

### Normalization Architecture

**Principle:** Normalize at the **boundary** (when reading from DB or JWT), not in the middle of business logic.

**Two entry points require normalization:**
1. **JWT decode time** (stale JWTs from before refactor)
2. **DB read time** (legacy rows still in database)

### 1. JWT Decode-Time Normalization (server/auth.py)

**Change: decode_access_token → normalize returned role**

```python
from server.roles import normalize_role

def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # NEW: Normalize role from JWT
        if "role" in payload:
            raw_role = payload["role"]
            canonical_role = normalize_role(raw_role)
            payload["role"] = str(canonical_role.value)  # Update payload in-place
        if "system_role" in payload:
            raw_role = payload["system_role"]
            canonical_role = normalize_role(raw_role)
            payload["system_role"] = str(canonical_role.value)
        return payload
    except JWTError:
        return None
```

**Rationale:**
- Handles stale JWTs in browser localStorage containing old role strings.
- Ensures all downstream code sees only canonical values.
- Logs a WARNING if normalization occurred (audit trail).

---

### 2. JWT Encode-Time Normalization (server/auth.py + routes_auth.py)

**Change: create_access_token caller → normalize role before JWT creation**

In `routes_auth.py`, all three endpoints that create JWTs:

```python
from server.roles import normalize_role

@router.post("/onboard-employee", response_model=TokenResponse)
def onboard_employee(...):
    ...
    user = User(...)
    ...
    # Before JWT creation:
    canonical_role = normalize_role(user.system_role)
    token = create_access_token({
        "sub": user.id,
        "org_id": user.org_id,
        "role": str(canonical_role.value)
    })
    return TokenResponse(
        access_token=token,
        user=_user_dict(user, org, db),
    )

@router.post("/register", ...)
def register(...):
    ...
    user = User(system_role="SUPER_ADMIN", ...)
    ...
    canonical_role = normalize_role(user.system_role)
    token = create_access_token({
        "sub": user.id,
        "org_id": org.id,
        "role": str(canonical_role.value)
    })
    ...

@router.post("/login", ...)
def login(...):
    ...
    canonical_role = normalize_role(user.system_role)
    token = create_access_token({
        "sub": user.id,
        "org_id": user.org_id,
        "role": str(canonical_role.value)
    })
    ...
```

**Rationale:**
- New logins always get canonical role in JWT.
- Pairs with decode-time normalization to handle both current and legacy JWTs.

---

### 3. Response Normalization (_user_dict in routes_auth.py)

**Change: Normalize user.system_role before including in response**

```python
def _user_dict(user, org, db):
    """Build user response dict with permissions."""
    from server.roles import normalize_role
    
    perm_profile = get_user_permission_profile(user.id, db)
    canonical_role = normalize_role(user.system_role)
    
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "employee_id": user.employee_id,
        "system_role": str(canonical_role.value),  # ← Canonical, not raw DB value
        "is_org_creator": user.is_org_creator,
        "avatar_color": user.avatar_color,
        "org_id": user.org_id,
        "org_name": org.name if org else None,
        "org_setup_completed": org.setup_completed if org else False,
        "plant_id": user.plant_id,
        "department_id": user.department_id,
        "designation_id": user.designation_id,
        "shift_id": user.shift_id,
        "permissions": perm_profile,
    }
```

**Rationale:**
- Frontend always receives canonical role string.
- Prevents frontend from seeing legacy values like "PLANT_MANAGER".

---

### 4. Permission Lookup Normalization (server/permissions_service.py)

**Change: Initialize_user_permissions → normalize before capability lookup**

```python
from server.roles import normalize_role

def initialize_user_permissions(user: User, db: Session) -> UserPermissionProfile:
    """
    Initialize or update a user's permission profile based on their role.
    """
    # NEW: Normalize role before lookup
    canonical_role = normalize_role(user.system_role)
    
    # Get base capabilities for this role
    capabilities = DEFAULT_ROLE_CAPABILITIES.get(
        str(canonical_role.value),
        DEFAULT_ROLE_CAPABILITIES["EMPLOYEE"]
    )
    
    ...
    # Update with current values
    profile.system_role = str(canonical_role.value)  # ← Store canonical, not raw
    
    ...
```

**Rationale:**
- Legacy "PLANT_MANAGER" is correctly looked up as "PLANT_HEAD" capabilities, not downgraded to EMPLOYEE.
- `UserPermissionProfile.system_role` column now stores canonical values.
- Downstream code that reads `profile.system_role` gets canonical value.

---

### 5. Middleware / Route-Level Normalization (server/routes_org_tree.py, okr_hierarchy_workflow.py, etc.)

**Problem:** Dozens of direct comparisons like `if user.system_role == "SUPER_ADMIN"` or lookups like `.get(user.system_role)`.

**Solution:** Create a helper function that wraps DB-fetched users:

```python
# In server/auth.py or server/roles.py (new file section)
from server.roles import normalize_role

def normalize_user_role(user: User) -> None:
    """
    Mutate user.system_role to canonical value.
    Called after fetching user from DB to ensure all subsequent logic sees canonical role.
    """
    canonical_role = normalize_role(user.system_role)
    user.system_role = str(canonical_role.value)
```

**Apply in:**
- `routes_org_tree.py:get_current_user_from_db()` → call `normalize_user_role(user)` before return
- `okr_hierarchy_workflow.py:can_create_okr_at_level()` → normalize at start
- `permissions_service.py:get_user_permission_profile()` → normalize before lookups
- Any other route that fetches User and uses `user.system_role`

**Rationale:**
- Once user is fetched, immediately normalize. Downstream code never sees legacy values.
- Single normalization point per request → no repeated normalization overhead.
- Does not modify DB, only mutates in-memory object.

---

### 6. Audit Logging Strategy

**When to audit:** First time a role normalization occurs for a **user-session**.

**Implementation:**

```python
# In server/auth.py or new audit helper module
import json
from server.models import AuditLog
from datetime import datetime

# Session-scoped dedupe set (in-memory per request cycle; Python dict by default)
_normalized_users_this_session = set()

def audit_role_normalization(user_id: str, org_id: str, raw_role: str, canonical_role: str, db: Session):
    """
    Log role normalization exactly once per user per session.
    
    Uses in-memory dedupe to prevent repeated audit rows for the same user.
    """
    # Dedupe key: (org_id, user_id) — one audit row per user per session
    dedupe_key = (org_id, user_id)
    
    if dedupe_key in _normalized_users_this_session:
        return  # Already logged for this session
    
    # Create audit row
    audit_entry = AuditLog(
        org_id=org_id,
        user_id=user_id,
        action="ROLE_NORMALIZATION",
        entity_type="USER",
        entity_id=user_id,
        details=json.dumps({
            "raw_role": raw_role,
            "canonical_role": canonical_role,
            "reason": "Legacy role alias mapped to canonical value"
        }),
        created_at=datetime.utcnow(),
    )
    db.add(audit_entry)
    db.commit()
    
    # Mark as logged for this session
    _normalized_users_this_session.add(dedupe_key)
```

**Where to call:**
```python
def normalize_role_with_audit(raw: str, user_id: str, org_id: str, db: Session) -> SystemRole:
    """Normalize and optionally audit if raw != canonical."""
    canonical = normalize_role(raw)
    
    if raw != str(canonical.value):
        audit_role_normalization(user_id, org_id, raw, str(canonical.value), db)
    
    return canonical
```

**Rationale:**
- Audit fires once per user per session, not every request.
- Session-scoped dedupe prevents spam if user makes many API calls.
- Includes both raw and canonical value for forensics.
- Action = "ROLE_NORMALIZATION" is searchable in audit_logs table.

---

### 7. DB Column: No Rewrite, Normalize on Read

**Decision:** Leave `users.system_role` column as-is; do not backfill legacy values.

**Rationale:**
- Avoids lock contention during concurrent requests.
- Preserves audit trail (can see original value was "PLANT_MANAGER" if needed).
- Normalization on read is transparent to existing code.
- Future migration (if desired) can batch-rewrite during maintenance window.

---

## Call Sites Summary

| File | Line(s) | Change | Priority |
|------|---------|--------|----------|
| **server/auth.py** | 32-37 | `decode_access_token()` → normalize JWT role claim | HIGH |
| **server/auth.py** | 57-58 | `require_super_admin()` → use `normalize_role()` in comparison | HIGH |
| **server/routes_auth.py** | 84, 124, 144 | All JWT creation calls → normalize before `create_access_token()` | HIGH |
| **server/routes_auth.py** | 183 | `_user_dict()` → normalize `system_role` before return | HIGH |
| **server/routes_org_tree.py** | 38, 65 | `get_current_user_from_db()`, `get_user_scope()` → normalize after DB fetch | MEDIUM |
| **server/permissions_service.py** | 239, 254 | `initialize_user_permissions()` → normalize before capability lookup | HIGH |
| **server/okr_hierarchy_workflow.py** | 120-121, 351+ | Role comparisons → normalize before `.get()` or `.in_()` | MEDIUM |
| **server/routes_okrs_hierarchy.py** | 47 | `workflow.ROLE_CREATION_LEVELS.get(user.system_role)` → normalize | MEDIUM |
| **Response endpoints** | (various) | Any endpoint returning `system_role` in response → normalize | MEDIUM |

---

## Verification Checkpoints (3.2 Verification Phase)

See main user request for V3.2a through V3.2f (login tests, legacy JWT test, audit log check, middleware test, DB no-write check, cleanup).

---

## Implementation Sequence

1. **Phase 1:** Add `decode_access_token()` and `require_super_admin()` normalization (server/auth.py).
2. **Phase 2:** Add encode-time normalization in `routes_auth.py` (JWT creation endpoints).
3. **Phase 3:** Normalize in `_user_dict()` response.
4. **Phase 4:** Add `normalize_user_role()` helper + apply in middleware (`routes_org_tree.py`).
5. **Phase 5:** Normalize in `permissions_service.py` lookups.
6. **Phase 6:** Add audit logging + test.
7. **Phase 7:** Spot-check other endpoints (OKR hierarchy, permission matrix, etc.).
8. **Phase 8:** Run verification tests (V3.2a–V3.2f).

---

## Notes

- ✅ `normalize_role()` function already exists in `server/roles.py` with LEGACY_ROLE_ALIASES map.
- ✅ `SystemRole` enum defined; all canonical values listed.
- ✅ `AuditLog` model exists in `server/models.py`.
- ✅ No database migration needed (normalize on read, not in DB).
- ⚠️ In-memory session dedupe for audit requires careful testing (may not survive across async requests; alternative: use DB timestamp + user_id + hour window).

---

## Approval Required

**Awaiting user approval to proceed with implementation of all seven phases above.**
