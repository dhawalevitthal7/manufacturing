# 🧪 API Testing Guide - After Migration

## ✅ Status: Ready to Test

Your backend is running and database has been migrated. Here are quick test commands for all major endpoints.

---

## Quick Test Commands

### 1. List OKRs (Previously Failing - Now Fixed ✅)
```bash
curl -X GET "http://localhost:8000/api/okrs?level=PLANT&org_id=58ea7177-3d39-49ad-abe6-8d1dbac7f1da"
```
**Expected**: 200 OK with JSON array of objectives

---

## Hierarchy Workflow Endpoints (27 Total)

### Validation Endpoints (Test Creation Permissions)

#### Can Create OKR?
```bash
curl -X POST "http://localhost:8000/api/okrs/hierarchy/validate/can-create" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-123",
    "okr_level": "ORGANIZATION",
    "org_id": "org-123"
  }'
```

#### Validate Hierarchy Chain
```bash
curl -X POST "http://localhost:8000/api/okrs/hierarchy/validate/hierarchy-chain" \
  -H "Content-Type: application/json" \
  -d '{
    "creator_id": "user-123",
    "okr_level": "PLANT",
    "parent_okr_id": "parent-okr-123",
    "org_id": "org-123",
    "plant_id": "plant-123"
  }'
```

#### Can Assign OKR?
```bash
curl -X POST "http://localhost:8000/api/okrs/hierarchy/validate/can-assign" \
  -H "Content-Type: application/json" \
  -d '{
    "creator_id": "manager-123",
    "assignee_id": "employee-123",
    "okr_level": "INDIVIDUAL",
    "org_id": "org-123"
  }'
```

#### Can Approve OKR?
```bash
curl -X POST "http://localhost:8000/api/okrs/hierarchy/validate/can-approve" \
  -H "Content-Type: application/json" \
  -d '{
    "approver_id": "manager-123",
    "okr_id": "okr-123",
    "org_id": "org-123"
  }'
```

---

### OKR Management Endpoints

#### Create OKR with Hierarchy Approval
```bash
curl -X POST "http://localhost:8000/api/okrs/hierarchy/create" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Increase efficiency by 25%",
    "description": "Focus on process optimization",
    "level": "ORGANIZATION",
    "okr_level": "ORGANIZATION",
    "owner_id": "ceo-123",
    "org_id": "org-123",
    "created_by": "ceo-123"
  }'
```

#### Approve OKR
```bash
curl -X POST "http://localhost:8000/api/okrs/hierarchy/okr-123/approve" \
  -H "Content-Type: application/json" \
  -d '{
    "approver_id": "manager-123",
    "approval_notes": "Looks good. Approved."
  }'
```

#### Reject OKR
```bash
curl -X POST "http://localhost:8000/api/okrs/hierarchy/okr-123/reject" \
  -H "Content-Type: application/json" \
  -d '{
    "approver_id": "manager-123",
    "rejection_notes": "Please revise scope"
  }'
```

---

### Assignment Endpoints

#### Get OKR Recipients (Who can this be assigned to?)
```bash
curl -X GET "http://localhost:8000/api/okrs/hierarchy/recipients" \
  -H "Content-Type: application/json" \
  -d '{
    "creator_id": "manager-123",
    "okr_level": "TEAM",
    "org_id": "org-123"
  }'
```

#### Assign OKR to User
```bash
curl -X POST "http://localhost:8000/api/okrs/hierarchy/okr-123/assign" \
  -H "Content-Type: application/json" \
  -d '{
    "assigned_by": "manager-123",
    "assigned_to": "employee-123",
    "notes": "Your Q2 objective"
  }'
```

---

### Visibility Endpoints

#### Get Visible OKRs for User
```bash
curl -X GET "http://localhost:8000/api/okrs/hierarchy/visible" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "employee-123",
    "org_id": "org-123"
  }'
```

#### Can User View OKR?
```bash
curl -X POST "http://localhost:8000/api/okrs/hierarchy/can-view/okr-123" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "employee-123",
    "org_id": "org-123"
  }'
```

---

### Approval Chain Endpoints

#### Get Approval Chain for OKR
```bash
curl -X GET "http://localhost:8000/api/okrs/hierarchy/okr-123/approval-chain" \
  -H "Content-Type: application/json" \
  -d '{
    "org_id": "org-123"
  }'
```

#### Get Suggested Parent OKR
```bash
curl -X GET "http://localhost:8000/api/okrs/hierarchy/okr-123/suggested-parent" \
  -H "Content-Type: application/json" \
  -d '{
    "org_id": "org-123",
    "level": "PLANT"
  }'
```

---

### Progress Validation Endpoint

#### Validate Progress Update
```bash
curl -X POST "http://localhost:8000/api/okrs/hierarchy/progress/progress-123/validate" \
  -H "Content-Type: application/json" \
  -d '{
    "validator_id": "manager-123",
    "validation_level": "MANAGER",
    "validation_notes": "On track"
  }'
```

---

## Testing Workflow

### Scenario 1: CEO Creates Organization-Level OKR
1. CEO validates can create at ORGANIZATION level → validation passes ✅
2. CEO creates ORGANIZATION OKR → OKR created in PENDING status
3. System auto-approves at ORGANIZATION level
4. OKR is now APPROVED ✅

### Scenario 2: Manager Creates Team-Level OKR
1. Manager validates can create at TEAM level → validation passes ✅
2. Manager gets eligible recipients → List of team members
3. Manager creates TEAM OKR → OKR created in PENDING status
4. Manager approves the OKR → OKR status = APPROVED
5. Manager assigns to employee → Assignment complete ✅

### Scenario 3: Employee Cannot Create OKR
1. Employee validates can create at TEAM level → Validation fails ❌
   - Response: `{"can_create": false, "reason": "Only managers and above can create at this level"}`
2. Employee cannot proceed with OKR creation ✅

### Scenario 4: Employee Submits Progress
1. Employee updates progress on their OKR
2. System sets next_approver_role = "MANAGER"
3. Manager validates progress → status = APPROVED
4. Progress cascades to next level (DEPT_HEAD)
5. Dept Head validates → cascades to PLANT_HEAD
6. Full validation chain complete ✅

---

## Expected Status Codes

| Code | Meaning | When |
|------|---------|------|
| 200 | OK | Operation successful |
| 400 | Bad Request | Invalid parameters |
| 403 | Forbidden | Permission denied |
| 404 | Not Found | OKR/User not found |
| 422 | Validation Error | Validation rules failed |

---

## Common Error Responses

### User Cannot Create at This Level
```json
{
  "detail": "User does not have permission to create OKR at TEAM level. Required role: MANAGER"
}
```
**Fix**: User must have higher role

### Hierarchy Chain Invalid
```json
{
  "detail": "Parent OKR must be at same plant. Parent is in plant-A, requested plant is plant-B"
}
```
**Fix**: Select parent OKR from same plant

### User Cannot Assign to This Person
```json
{
  "detail": "Cannot assign OKR to user. Assignee must be directly below creator in hierarchy"
}
```
**Fix**: Assign to direct report only

---

## Troubleshooting

### If You Get 500 Error
Check if backend is still running:
```bash
curl http://localhost:8000/docs
```
Should show Swagger UI. If not, restart backend with:
```bash
python main.py
```

### If You Get Database Error
Run migration again:
```bash
python server/run_migration.py
```

### If CORS Error Still Occurs
The backend URL is: `http://localhost:8000`
Frontend should request from this URL, not a different port.

---

## Performance Tips

- Use `/visible` endpoint instead of listing all and filtering client-side
- Pre-validate with `/validate/*` endpoints before creating/assigning
- Cache approval chains as they don't change frequently
- Index queries by org_id for faster results

---

## Complete Documentation

For full documentation, see:
- `OKRS_HIERARCHY_WORKFLOW.md` - Complete API reference
- `OKRS_HIERARCHY_VISUAL_GUIDE.md` - Visual workflow diagrams
- `OKRS_HIERARCHY_TESTING.py` - 50+ test scenarios

---

**Backend Status**: ✅ Running
**Database Status**: ✅ Migrated
**Ready to Test**: ✅ YES

Start with Scenario 1 above! 🚀
