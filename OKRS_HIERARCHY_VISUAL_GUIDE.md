# OKR Hierarchy Workflow - Visual Reference Guide

## 1. Organizational Hierarchy Structure

```
┌─────────────────────────────────────────────────────────────┐
│  CEO / SUPER_ADMIN                    (ORGANIZATION Scope)   │
│  - Creates ORGANIZATION-level OKRs                           │
│  - Approves all levels                                       │
│  - Views all OKRs                                            │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼────────┐ ┌────────▼────────┐ ┌───────▼────────┐
│ VP OPERATIONS  │ │ VP MANUFACTURING│ │ VP SALES       │
│ (ORG Scope)    │ │ (ORG Scope)     │ │ (ORG Scope)    │
│ - Create       │ │ - Create        │ │ - Create       │
│   PLANT        │ │   PLANT         │ │   PLANT        │
│   DEPARTMENT   │ │   DEPARTMENT    │ │   DEPARTMENT   │
│ - Approve      │ │ - Approve       │ │ - Approve      │
│   PLANT level  │ │   PLANT level   │ │   PLANT level  │
└───────┬────────┘ └────────┬────────┘ └────────────────┘
        │                   │
    ┌───▼──────────┬────────┴───────┬──────────┐
    │              │                │          │
┌───▼────────┐ ┌──▼────────┐ ┌─────▼──────┐ ┌─▼──────────┐
│ PLANT HEAD │ │PLANT HEAD  │ │PLANT HEAD  │ │PLANT HEAD  │
│ Plant A    │ │ Plant B    │ │ Plant C    │ │ Plant D    │
│(PLANT Scope)│ │(PLANT Scope)│ │(PLANT Scope)│ │(PLANT Scope│
│ - Create   │ │ - Create   │ │ - Create   │ │ - Create   │
│   DEPT     │ │   DEPT     │ │   DEPT     │ │   DEPT     │
│   TEAM     │ │   TEAM     │ │   TEAM     │ │   TEAM     │
└───┬────────┘ └────────────┘ └────────────┘ └────────────┘
    │
    ├──────────────────────────────────┐
    │                                  │
┌───▼──────────┐              ┌────────▼────────┐
│ DEPT HEAD    │              │ DEPT HEAD       │
│ Production   │              │ Quality         │
│ (DEPT Scope) │              │ (DEPT Scope)    │
│ - Create     │              │ - Create        │
│   TEAM       │              │   TEAM          │
│ - Assign     │              │ - Assign        │
│   to Mgr     │              │   to Mgr        │
└───┬──────────┘              └─────────────────┘
    │
    ├──────────────┬─────────────┐
    │              │             │
┌───▼────┐   ┌────▼────┐   ┌───▼────┐
│MANAGER │   │MANAGER  │   │MANAGER │
│Line 1  │   │Line 2   │   │Line 3  │
│(TEAM)  │   │(TEAM)   │   │(TEAM)  │
│Create  │   │Create   │   │Create  │
│INDIV.  │   │INDIV.   │   │INDIV.  │
└───┬────┘   └─────────┘   └────────┘
    │
    ├─────┬─────┬─────┐
    │     │     │     │
  EMP1  EMP2  EMP3  SUP1
  (INDIV Scope)
```

## 2. OKR Level Hierarchy & Cascading

```
ORGANIZATION OKR
↓ "Increase manufacturing efficiency by 25%"
├─ Parent: None
├─ Owner: CEO
├─ Scope: None (organization-wide)
├─ Level: 0
└─ Approval: CEO, Super Admin
    │
    ├─ PLANT OKR (Plant A)
    │  ↓ "Plant A efficiency increase 25%"
    │  ├─ Parent: ORG OKR
    │  ├─ Owner: Plant Head A
    │  ├─ Scope: Plant A
    │  ├─ Level: 1
    │  └─ Approval: Plant Head, VP, Super Admin
    │      │
    │      ├─ DEPARTMENT OKR (Production)
    │      │  ↓ "Production efficiency 20%"
    │      │  ├─ Parent: PLANT OKR
    │      │  ├─ Owner: Dept Head Production
    │      │  ├─ Scope: Plant A, Production Dept
    │      │  ├─ Level: 2
    │      │  └─ Approval: Dept Head, Plant Head, VP, Super Admin
    │      │      │
    │      │      ├─ TEAM OKR (Line 1)
    │      │      │  ↓ "Line 1 efficiency 25%"
    │      │      │  ├─ Parent: DEPT OKR
    │      │      │  ├─ Owner: Manager Line 1
    │      │      │  ├─ Scope: Plant A, Production, Line 1
    │      │      │  ├─ Level: 3
    │      │      │  └─ Approval: Manager, Dept Head, Plant Head, VP, Super Admin
    │      │      │      │
    │      │      │      ├─ INDIVIDUAL OKR (Employee 1)
    │      │      │      │  "Reduce cycle time by 5 hours"
    │      │      │      │  ├─ Parent: TEAM OKR (optional)
    │      │      │      │  ├─ Owner: Employee 1
    │      │      │      │  ├─ Level: 4 (terminal)
    │      │      │      │  └─ NO CHILDREN ALLOWED
    │      │      │      │
    │      │      │      └─ INDIVIDUAL OKR (Employee 2)
    │      │      │         "Achieve 98% quality score"
    │      │      │
    │      │      └─ TEAM OKR (Line 2)
    │      │
    │      └─ DEPARTMENT OKR (Quality)
    │
    └─ PLANT OKR (Plant B)
```

## 3. OKR Creation Permission Matrix

```
┌─────────────────────┬─────────┬─────────┬─────────┬─────────┬──────────┐
│ User Role           │ ORG     │ PLANT   │ DEPT    │ TEAM    │ INDIV    │
├─────────────────────┼─────────┼─────────┼─────────┼─────────┼──────────┤
│ SUPER_ADMIN         │ ✓ YES   │ ✓ YES   │ ✓ YES   │ ✓ YES   │ ✓ YES    │
│ CEO                 │ ✓ YES   │ ✗ NO    │ ✗ NO    │ ✗ NO    │ ✗ NO     │
│ VP_OPERATIONS       │ ✗ NO    │ ✓ YES   │ ✓ YES   │ ✗ NO    │ ✗ NO     │
│ VP_MANUFACTURING    │ ✗ NO    │ ✓ YES   │ ✓ YES   │ ✗ NO    │ ✗ NO     │
│ PLANT_HEAD          │ ✗ NO    │ ✓ YES   │ ✓ YES   │ ✓ YES   │ ✗ NO     │
│ OPERATIONS_HEAD     │ ✗ NO    │ ✓ YES   │ ✓ YES   │ ✗ NO    │ ✗ NO     │
│ DEPT_HEAD           │ ✗ NO    │ ✗ NO    │ ✓ YES   │ ✓ YES   │ ✗ NO     │
│ MANAGER             │ ✗ NO    │ ✗ NO    │ ✗ NO    │ ✓ YES   │ ✓ YES    │
│ TEAM_LEAD           │ ✗ NO    │ ✗ NO    │ ✗ NO    │ ✗ NO    │ ✓ YES    │
│ SUPERVISOR          │ ✗ NO    │ ✗ NO    │ ✗ NO    │ ✗ NO    │ ✓ YES    │
│ EMPLOYEE            │ ✗ NO    │ ✗ NO    │ ✗ NO    │ ✗ NO    │ ✗ NO     │
│ OPERATOR            │ ✗ NO    │ ✗ NO    │ ✗ NO    │ ✗ NO    │ ✗ NO     │
│ TECHNICIAN          │ ✗ NO    │ ✗ NO    │ ✗ NO    │ ✗ NO    │ ✗ NO     │
└─────────────────────┴─────────┴─────────┴─────────┴─────────┴──────────┘
```

## 4. OKR Approval Authority

```
┌──────────────────┬────────────────────────────────────────────────────┐
│ OKR Level        │ Can Approve (in order of precedence)               │
├──────────────────┼────────────────────────────────────────────────────┤
│ ORGANIZATION     │ • CEO                                              │
│                  │ • SUPER_ADMIN                                      │
├──────────────────┼────────────────────────────────────────────────────┤
│ PLANT            │ • PLANT_HEAD (same plant)                          │
│                  │ • VP_OPERATIONS                                    │
│                  │ • VP_MANUFACTURING                                 │
│                  │ • SUPER_ADMIN                                      │
├──────────────────┼────────────────────────────────────────────────────┤
│ DEPARTMENT       │ • DEPT_HEAD (same dept)                            │
│                  │ • PLANT_HEAD (same plant)                          │
│                  │ • VP_OPERATIONS                                    │
│                  │ • SUPER_ADMIN                                      │
├──────────────────┼────────────────────────────────────────────────────┤
│ TEAM             │ • MANAGER (same team)                              │
│                  │ • DEPT_HEAD (same dept)                            │
│                  │ • PLANT_HEAD (same plant)                          │
│                  │ • VP_OPERATIONS                                    │
│                  │ • SUPER_ADMIN                                      │
├──────────────────┼────────────────────────────────────────────────────┤
│ INDIVIDUAL       │ • MANAGER (same team)                              │
│                  │ • TEAM_LEAD (same team)                            │
│                  │ • DEPT_HEAD (same dept)                            │
│                  │ • PLANT_HEAD (same plant)                          │
│                  │ • VP_OPERATIONS                                    │
│                  │ • SUPER_ADMIN                                      │
└──────────────────┴────────────────────────────────────────────────────┘
```

## 5. Progress Validation Flow (Upward)

```
EMPLOYEE SUBMITS PROGRESS
        ↓
    PENDING
        ↓
    VALIDATION QUEUE
        ↓
TEAM_LEAD / MANAGER VALIDATES
        ├─ APPROVE → Progress accepted
        │   ↓
        │   KR VALUE UPDATED
        │   ↓
        │   PARENT OKR PROGRESS RECALCULATED
        │   ↓
        │   APPROVED (Optional: next level validates)
        │
        ├─ REJECT → Rejected with notes
        │   ↓
        │   Employee notified
        │   ↓
        │   Employee resubmits
        │
        └─ REQUEST REVISION → Employee revises and resubmits
            ↓
            Back to validation queue

[TEAM LEVEL VALIDATION]
Manager submits team progress
    ↓
Dept Head validates
    ↓
Approved/Rejected

[DEPARTMENT LEVEL VALIDATION]
Dept Head submits dept progress
    ↓
Plant Head validates
    ↓
Approved/Rejected

[PLANT LEVEL VALIDATION]
Plant Head submits plant progress
    ↓
VP Operations validates
    ↓
Approved/Rejected

[ORGANIZATION LEVEL MONITORING]
CEO views aggregate progress
```

## 6. OKR Scope Requirements by Level

```
┌──────────────────┬────────────┬──────────────┬────────────┬──────────────┐
│ OKR Level        │ plant_id   │ department_id│ team_id    │ owner_scope  │
├──────────────────┼────────────┼──────────────┼────────────┼──────────────┤
│ ORGANIZATION     │ NOT SET    │ NOT SET      │ NOT SET    │ CEO / VP     │
│                  │            │              │            │              │
│ PLANT            │ REQUIRED   │ NOT SET      │ NOT SET    │ Plant Head   │
│                  │            │              │            │ / VP         │
│                  │            │              │            │              │
│ DEPARTMENT       │ REQUIRED   │ REQUIRED     │ NOT SET    │ Dept Head    │
│                  │            │              │            │ / Plant Head │
│                  │            │              │            │              │
│ TEAM             │ REQUIRED   │ REQUIRED     │ REQUIRED   │ Manager      │
│                  │            │              │            │ / Dept Head  │
│                  │            │              │            │              │
│ INDIVIDUAL       │ REQUIRED   │ REQUIRED     │ REQUIRED   │ Employee     │
│                  │            │              │            │ / Manager    │
└──────────────────┴────────────┴──────────────┴────────────┴──────────────┘

Rules:
• Once set, scope fields cannot be changed
• Scope determines visibility and validation authority
• Cross-scope assignments only allowed for VP/Super Admin
```

## 7. Visibility Access Rules

```
USER ROLE           ORGANIZATION    PLANT*    DEPARTMENT*  TEAM*    INDIVIDUAL*
──────────────────  ──────────────  ────────  ──────────────  ───────  ────────────
CEO                 ALL             ALL       ALL            ALL      ALL
VP_OPERATIONS       ALL             ALL       ALL            ALL      ALL
PLANT_HEAD          All + ORG       Own       All in own      All      All
                                    PLANT     Plant
DEPT_HEAD           All + ORG       All +     Own DEPT       All in    All in
                                    Plant     OKRs           own       own
                                              OKRs           DEPT      DEPT
MANAGER             All + ORG       All +     All +          Own TEAM  Own TEAM
                                    Plant     DEPT OKRs      OKRs      OKRs
                                    OKRs
TEAM_LEAD           All + ORG       All +     All +          Own TEAM  Own TEAM
                                    Plant     DEPT OKRs      OKRs      OKRs
                                    OKRs
EMPLOYEE            ORG OKRs        Plant     DEPT OKRs      TEAM      Own only
                    visible to      OKRs                     OKRs
                    all

* Within assigned hierarchy scope
```

## 8. API Workflow - Complete OKR Lifecycle

```
STEP 1: VALIDATE CREATION PERMISSION
POST /api/okrs/hierarchy/validate/can-create
├─ Input: user_id, okr_level
└─ Output: {can_create: boolean, allowed_levels: [...]}

STEP 2: VALIDATE HIERARCHY CHAIN
POST /api/okrs/hierarchy/validate/hierarchy-chain
├─ Input: okr_level, parent_id, plant_id, department_id, team_id
└─ Output: {valid: boolean, reason: string}

STEP 3: GET ELIGIBLE RECIPIENTS
GET /api/okrs/hierarchy/recipients
├─ Input: okr_level, plant_id, department_id, team_id
└─ Output: {recipients: [...]}

STEP 4: VALIDATE ASSIGNMENT
POST /api/okrs/hierarchy/validate/can-assign
├─ Input: creator_id, assignee_id, okr_level
└─ Output: {can_assign: boolean}

STEP 5: CREATE OKR
POST /api/okrs/hierarchy/create
├─ Input: {title, level, owner_id, parent_id, plant_id, ...}
└─ Output: {id, approval_chain, creation_approval_status: PENDING}

STEP 6: GET APPROVAL CHAIN
GET /api/okrs/hierarchy/{okr_id}/approval-chain
├─ Input: okr_id
└─ Output: {approval_chain: [{role, user_id, user_name}]}

STEP 7: APPROVE OKR
POST /api/okrs/hierarchy/{okr_id}/approve
├─ Input: approver_id, approval_notes
└─ Output: {creation_approval_status: APPROVED}

STEP 8: ASSIGN OKR (Optional)
POST /api/okrs/hierarchy/{okr_id}/assign
├─ Input: assignee_id, assigner_id
└─ Output: {owner_id: new_owner}

STEP 9: VIEW VISIBLE OKRs
GET /api/okrs/hierarchy/visible
├─ Input: user_id
└─ Output: {okrs: [...]}

STEP 10: SUBMIT & VALIDATE PROGRESS
POST /api/okrs/hierarchy/progress/{progress_id}/validate
├─ Input: validator_id, validation_notes
└─ Output: {status: APPROVED}
```

## 9. Error Codes & Resolutions

```
400 - BAD REQUEST
├─ Missing required scope field (plant_id, department_id, team_id)
├─ Invalid parent-child level combination
├─ OKR not in APPROVED state for assignment
└─ Hierarchy chain validation failed

403 - FORBIDDEN
├─ User role cannot create OKRs at this level
├─ User cannot approve OKR (not in approval chain)
├─ User cannot view this OKR (visibility restriction)
└─ Cross-plant assignment not allowed

404 - NOT FOUND
├─ User not found
├─ OKR not found
├─ Parent OKR not found
└─ Progress update not found

422 - UNPROCESSABLE ENTITY
├─ Invalid OKR level specified
├─ Circular parent reference detected
└─ Conflicting scope assignments
```

## 10. Common Workflows

### Workflow A: Cascade OKRs from CEO to Employee

```
CEO creates ORG OKR → Approves it
        ↓
VP creates PLANT OKR (parent = ORG OKR) → Approves it
        ↓
Plant Head creates DEPT OKR (parent = PLANT OKR) → Approves it
        ↓
Dept Head creates TEAM OKR (parent = DEPT OKR) → Approves it
        ↓
Manager creates INDIVIDUAL OKR (parent = TEAM OKR) → Approves it
        ↓
Manager assigns INDIVIDUAL OKR to Employee
        ↓
Employee owns the OKR and can submit progress
        ↓
Manager validates progress
        ↓
Progress cascades up: Team → Dept → Plant → Org
```

### Workflow B: Multi-Approver Scenario

```
Manager creates TEAM OKR → Status: PENDING
        ↓
AWAITING APPROVAL (approval_chain includes: Manager, Dept Head, Plant Head)
        ↓
Manager approves (First approver)
        ↓
Status still: PENDING (second approval needed)
        ↓
Dept Head approves (Second approver)
        ↓
Status: APPROVED (can now be assigned)
```

### Workflow C: Rejection & Revision

```
Manager creates TEAM OKR → Status: PENDING
        ↓
Dept Head reviews → Status: REVISION_REQUESTED
├─ Rejection reason: "OKR targets too aggressive"
        ↓
Manager revises OKR
        ↓
Manager resubmits
        ↓
Dept Head reviews again → Status: APPROVED
```

---

**For detailed API documentation, see: `OKRS_HIERARCHY_WORKFLOW.md`**
**For setup instructions, see: `OKRS_HIERARCHY_SETUP_GUIDE.md`**
**For test scenarios, see: `OKRS_HIERARCHY_TESTING.py`**
