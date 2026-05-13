"""
Hierarchy-Based OKR Workflow Testing Guide
============================================

Comprehensive test cases and examples for the strict hierarchy-based OKR workflow.
"""

# ════════════════════════════════════════════════════════════════════════════════
# TEST CASE 1: PERMISSION & CREATION VALIDATION
# ════════════════════════════════════════════════════════════════════════════════

"""
Scenario: Validate that only authorized roles can create OKRs at each level

Test Data:
- CEO: user_ceo@mfg.com (Super Admin)
- VP Operations: user_vp@mfg.com
- Plant Head (Plant A): user_ph_a@mfg.com
- Department Head (Dept A): user_dh_a@mfg.com
- Manager (Team A): user_mgr_a@mfg.com
- Employee: user_emp@mfg.com

Test Cases:
"""

test_cases_permission = [
    {
        "name": "CEO can create ORGANIZATION OKR",
        "user": "user_ceo@mfg.com",
        "okr_level": "ORGANIZATION",
        "expected": "SUCCESS",
    },
    {
        "name": "VP Operations can create PLANT OKR",
        "user": "user_vp@mfg.com",
        "okr_level": "PLANT",
        "expected": "SUCCESS",
    },
    {
        "name": "Plant Head can create DEPARTMENT OKR",
        "user": "user_ph_a@mfg.com",
        "okr_level": "DEPARTMENT",
        "expected": "SUCCESS",
    },
    {
        "name": "Department Head can create TEAM OKR",
        "user": "user_dh_a@mfg.com",
        "okr_level": "TEAM",
        "expected": "SUCCESS",
    },
    {
        "name": "Manager can create INDIVIDUAL OKR",
        "user": "user_mgr_a@mfg.com",
        "okr_level": "INDIVIDUAL",
        "expected": "SUCCESS",
    },
    {
        "name": "Employee CANNOT create TEAM OKR",
        "user": "user_emp@mfg.com",
        "okr_level": "TEAM",
        "expected": "FORBIDDEN - Role EMPLOYEE cannot create TEAM OKRs",
    },
    {
        "name": "Department Head CANNOT create ORGANIZATION OKR",
        "user": "user_dh_a@mfg.com",
        "okr_level": "ORGANIZATION",
        "expected": "FORBIDDEN - Role DEPT_HEAD cannot create ORGANIZATION OKRs",
    },
    {
        "name": "Manager CANNOT create PLANT OKR",
        "user": "user_mgr_a@mfg.com",
        "okr_level": "PLANT",
        "expected": "FORBIDDEN - Role MANAGER cannot create PLANT OKRs",
    },
]


# ════════════════════════════════════════════════════════════════════════════════
# TEST CASE 2: HIERARCHY CHAIN VALIDATION
# ════════════════════════════════════════════════════════════════════════════════

"""
Scenario: Validate that OKR hierarchy chains are correct

Test Structure:
- Org OKR (okr_org_001): "Increase efficiency"
  - Plant OKR (okr_plant_001): "Plant A efficiency"
    - Dept OKR (okr_dept_001): "Production dept efficiency"
      - Team OKR (okr_team_001): "Production team efficiency"
        - Individual OKR (okr_emp_001): "Employee production target"
"""

test_cases_hierarchy = [
    {
        "name": "PLANT OKR can link to ORGANIZATION OKR",
        "child_level": "PLANT",
        "parent_id": "okr_org_001",
        "parent_level": "ORGANIZATION",
        "expected": "SUCCESS",
    },
    {
        "name": "DEPARTMENT OKR can link to PLANT OKR",
        "child_level": "DEPARTMENT",
        "parent_id": "okr_plant_001",
        "parent_level": "PLANT",
        "expected": "SUCCESS",
    },
    {
        "name": "TEAM OKR can link to DEPARTMENT OKR",
        "child_level": "TEAM",
        "parent_id": "okr_dept_001",
        "parent_level": "DEPARTMENT",
        "expected": "SUCCESS",
    },
    {
        "name": "INDIVIDUAL OKR can link to TEAM OKR",
        "child_level": "INDIVIDUAL",
        "parent_id": "okr_team_001",
        "parent_level": "TEAM",
        "expected": "SUCCESS",
    },
    {
        "name": "DEPARTMENT OKR CANNOT link to INDIVIDUAL parent",
        "child_level": "DEPARTMENT",
        "parent_id": "okr_emp_001",
        "parent_level": "INDIVIDUAL",
        "expected": "BAD_REQUEST - Parent must be ORGANIZATION, PLANT, or DEPARTMENT",
    },
    {
        "name": "TEAM OKR CANNOT link to different plant's PLANT OKR",
        "child_level": "TEAM",
        "parent_id": "okr_plant_002",  # Different plant
        "parent_level": "PLANT",
        "plant_id": "plant_a",
        "expected": "BAD_REQUEST - Parent must be in same plant",
    },
    {
        "name": "INDIVIDUAL OKR can skip levels and link to DEPARTMENT",
        "child_level": "INDIVIDUAL",
        "parent_id": "okr_dept_001",
        "parent_level": "DEPARTMENT",
        "expected": "SUCCESS",
    },
]


# ════════════════════════════════════════════════════════════════════════════════
# TEST CASE 3: SCOPE VALIDATION (Plant/Department/Team Binding)
# ════════════════════════════════════════════════════════════════════════════════

"""
Scenario: Validate that scope fields are required and correct for each level
"""

test_cases_scope = [
    {
        "name": "ORGANIZATION OKR has no scope",
        "okr_level": "ORGANIZATION",
        "scope": {"plant_id": None, "department_id": None, "team_id": None},
        "expected": "SUCCESS",
    },
    {
        "name": "PLANT OKR requires plant_id only",
        "okr_level": "PLANT",
        "scope": {"plant_id": "plant_a", "department_id": None, "team_id": None},
        "expected": "SUCCESS",
    },
    {
        "name": "PLANT OKR CANNOT have department_id",
        "okr_level": "PLANT",
        "scope": {"plant_id": "plant_a", "department_id": "dept_a", "team_id": None},
        "expected": "BAD_REQUEST - PLANT OKRs cannot be scoped to department",
    },
    {
        "name": "DEPARTMENT OKR requires plant_id and department_id",
        "okr_level": "DEPARTMENT",
        "scope": {"plant_id": "plant_a", "department_id": "dept_a", "team_id": None},
        "expected": "SUCCESS",
    },
    {
        "name": "DEPARTMENT OKR CANNOT have team_id",
        "okr_level": "DEPARTMENT",
        "scope": {"plant_id": "plant_a", "department_id": "dept_a", "team_id": "team_a"},
        "expected": "BAD_REQUEST - DEPARTMENT OKRs cannot be scoped to team",
    },
    {
        "name": "TEAM OKR requires plant_id, department_id, and team_id",
        "okr_level": "TEAM",
        "scope": {"plant_id": "plant_a", "department_id": "dept_a", "team_id": "team_a"},
        "expected": "SUCCESS",
    },
    {
        "name": "INDIVIDUAL OKR requires all scope fields",
        "okr_level": "INDIVIDUAL",
        "scope": {"plant_id": "plant_a", "department_id": "dept_a", "team_id": "team_a"},
        "expected": "SUCCESS",
    },
]


# ════════════════════════════════════════════════════════════════════════════════
# TEST CASE 4: ASSIGNMENT VALIDATION
# ════════════════════════════════════════════════════════════════════════════════

"""
Scenario: Validate that OKRs can only be assigned to appropriate users

Users:
- CEO (scope: ORGANIZATION)
- VP Ops (scope: ORGANIZATION)
- Plant Head (scope: PLANT)
- Dept Head (scope: DEPARTMENT)
- Manager (scope: TEAM)
- Employee (scope: INDIVIDUAL)
"""

test_cases_assignment = [
    {
        "name": "CEO can be assigned ORGANIZATION OKR",
        "assignee_role": "CEO",
        "okr_level": "ORGANIZATION",
        "expected": "SUCCESS",
    },
    {
        "name": "Plant Head can be assigned PLANT OKR",
        "assignee_role": "PLANT_HEAD",
        "okr_level": "PLANT",
        "expected": "SUCCESS",
    },
    {
        "name": "Department Head can be assigned DEPARTMENT OKR",
        "assignee_role": "DEPT_HEAD",
        "okr_level": "DEPARTMENT",
        "expected": "SUCCESS",
    },
    {
        "name": "Manager can be assigned TEAM OKR",
        "assignee_role": "MANAGER",
        "okr_level": "TEAM",
        "expected": "SUCCESS",
    },
    {
        "name": "Employee can be assigned INDIVIDUAL OKR",
        "assignee_role": "EMPLOYEE",
        "okr_level": "INDIVIDUAL",
        "expected": "SUCCESS",
    },
    {
        "name": "Manager CANNOT be assigned PLANT OKR",
        "assignee_role": "MANAGER",
        "okr_level": "PLANT",
        "expected": "FORBIDDEN - Manager scope cannot own PLANT OKRs",
    },
    {
        "name": "Employee CANNOT be assigned TEAM OKR",
        "assignee_role": "EMPLOYEE",
        "okr_level": "TEAM",
        "expected": "FORBIDDEN - Employee scope cannot own TEAM OKRs",
    },
    {
        "name": "Department Head can be assigned TEAM OKR (higher authority)",
        "assignee_role": "DEPT_HEAD",
        "okr_level": "TEAM",
        "expected": "SUCCESS",
    },
]


# ════════════════════════════════════════════════════════════════════════════════
# TEST CASE 5: APPROVAL WORKFLOW
# ════════════════════════════════════════════════════════════════════════════════

"""
Scenario: Test the approval workflow and approval chain

Approval Chain by Level:
- ORGANIZATION: CEO, Super Admin
- PLANT: Plant Head, VP Operations, VP Manufacturing, Super Admin
- DEPARTMENT: Department Head, Plant Head, VP Operations, Super Admin
- TEAM: Manager, Department Head, Plant Head, VP Operations, Super Admin
- INDIVIDUAL: Manager, Team Lead, Department Head, Plant Head, VP Operations, Super Admin
"""

test_cases_approval = [
    {
        "name": "CEO can approve ORGANIZATION OKR",
        "approver_role": "CEO",
        "okr_level": "ORGANIZATION",
        "expected": "SUCCESS",
    },
    {
        "name": "VP Operations can approve PLANT OKR",
        "approver_role": "VP_OPERATIONS",
        "okr_level": "PLANT",
        "expected": "SUCCESS",
    },
    {
        "name": "Plant Head can approve DEPARTMENT OKR in their plant",
        "approver_role": "PLANT_HEAD",
        "okr_level": "DEPARTMENT",
        "same_plant": True,
        "expected": "SUCCESS",
    },
    {
        "name": "Plant Head CANNOT approve DEPARTMENT in different plant",
        "approver_role": "PLANT_HEAD",
        "okr_level": "DEPARTMENT",
        "same_plant": False,
        "expected": "FORBIDDEN - Must be in same plant",
    },
    {
        "name": "Manager can approve INDIVIDUAL OKR in their team",
        "approver_role": "MANAGER",
        "okr_level": "INDIVIDUAL",
        "same_team": True,
        "expected": "SUCCESS",
    },
    {
        "name": "Employee CANNOT approve any OKR",
        "approver_role": "EMPLOYEE",
        "okr_level": "INDIVIDUAL",
        "expected": "FORBIDDEN - Employee role cannot approve OKRs",
    },
    {
        "name": "Super Admin can approve any OKR at any level",
        "approver_role": "SUPER_ADMIN",
        "okr_level": "ORGANIZATION",
        "expected": "SUCCESS",
    },
]


# ════════════════════════════════════════════════════════════════════════════════
# TEST CASE 6: VISIBILITY & ACCESS CONTROL
# ════════════════════════════════════════════════════════════════════════════════

"""
Scenario: Test that users can only see OKRs they have authority to view

Visibility Rules:
- SUPER_ADMIN: All OKRs
- CEO: All OKRs (org-level view)
- VP-level: All OKRs in their oversight
- Plant Head: All OKRs in their plant + org OKRs
- Department Head: Dept + team + individual + higher level org OKRs
- Manager: Team + individual + higher level org OKRs
- Team Lead: Team + individual + higher level org OKRs
- Employee: Own OKRs + team OKRs + org OKRs they can see
"""

test_cases_visibility = [
    {
        "name": "CEO can view all OKRs (organization-wide)",
        "user_role": "CEO",
        "expected_visible": ["org_okr_001", "plant_okr_001", "dept_okr_001", "team_okr_001", "emp_okr_001"],
    },
    {
        "name": "Plant Head can view plant OKRs and below + org OKRs",
        "user_role": "PLANT_HEAD",
        "plant_id": "plant_a",
        "expected_visible": ["org_okr_001", "plant_okr_a_001", "dept_okr_a_001", "team_okr_a_001"],
        "expected_hidden": ["plant_okr_b_001", "dept_okr_b_001"],  # From other plant
    },
    {
        "name": "Department Head can view department OKRs and below",
        "user_role": "DEPT_HEAD",
        "dept_id": "dept_a",
        "expected_visible": ["dept_okr_a_001", "team_okr_a_001", "emp_okr_a_001"],
        "expected_hidden": ["dept_okr_b_001", "team_okr_b_001"],  # From other dept
    },
    {
        "name": "Manager can view team OKRs and employee OKRs in their team",
        "user_role": "MANAGER",
        "team_id": "team_a",
        "expected_visible": ["team_okr_a_001", "emp_okr_a_001", "emp_okr_a_002"],
        "expected_hidden": ["team_okr_b_001", "emp_okr_b_001"],  # From other team
    },
    {
        "name": "Employee can view own OKRs and team OKRs",
        "user_role": "EMPLOYEE",
        "team_id": "team_a",
        "employee_id": "emp_001",
        "expected_visible": ["okr_emp_001"],  # Own OKR
        "expected_also_visible": ["team_okr_a_001", "org_okr_001"],  # Team and org
    },
]


# ════════════════════════════════════════════════════════════════════════════════
# TEST CASE 7: PROGRESS VALIDATION WORKFLOW
# ════════════════════════════════════════════════════════════════════════════════

"""
Scenario: Test the progress validation workflow flowing upward

Progress Submission Flow:
1. Employee submits progress for INDIVIDUAL OKR
2. Manager validates (can approve, reject, or request revision)
3. Department Head may validate for cross-team impact
4. Plant Head monitors plant-wide progress
"""

test_cases_progress = [
    {
        "name": "Manager can validate employee progress in their team",
        "submitter_role": "EMPLOYEE",
        "validator_role": "MANAGER",
        "same_team": True,
        "expected": "SUCCESS - Progress approved",
    },
    {
        "name": "Team Lead can validate employee progress in their team",
        "submitter_role": "EMPLOYEE",
        "validator_role": "TEAM_LEAD",
        "same_team": True,
        "expected": "SUCCESS - Progress approved",
    },
    {
        "name": "Employee CANNOT validate their own progress",
        "submitter_role": "EMPLOYEE",
        "validator_role": "EMPLOYEE",
        "same_person": True,
        "expected": "FORBIDDEN - Cannot validate own progress",
    },
    {
        "name": "Manager in different team CANNOT validate employee progress",
        "submitter_role": "EMPLOYEE",
        "validator_role": "MANAGER",
        "different_team": True,
        "expected": "FORBIDDEN - Must be hierarchy superior",
    },
    {
        "name": "Department Head can validate manager progress",
        "submitter_role": "MANAGER",
        "validator_role": "DEPT_HEAD",
        "same_dept": True,
        "expected": "SUCCESS - Manager progress validated",
    },
    {
        "name": "Plant Head can validate department progress",
        "submitter_role": "DEPT_HEAD",
        "validator_role": "PLANT_HEAD",
        "same_plant": True,
        "expected": "SUCCESS - Department progress validated",
    },
]


# ════════════════════════════════════════════════════════════════════════════════
# TEST CASE 8: CASCADING & PARENT-CHILD RELATIONSHIPS
# ════════════════════════════════════════════════════════════════════════════════

"""
Scenario: Test that OKRs cascade correctly from parent to child

Cascade Structure:
Organization OKR: "Increase efficiency by 25%"
├── Plant OKR: "Plant A increase efficiency by 25%"
│   ├── Dept OKR: "Production dept increase efficiency by 20%"
│   │   ├── Team OKR: "Production line 1 increase efficiency by 25%"
│   │   │   ├── Employee OKR: "Complete 10 process optimizations"
│   │   │   └── Employee OKR: "Reduce cycle time by 5 hours"
│   │   └── Team OKR: "Production line 2 increase efficiency by 25%"
│   └── Dept OKR: "Quality dept increase efficiency by 10%"
```

Parent-Child Progress Calculation:
- Child progress is weighted and aggregated
- Parent progress = AVERAGE(weighted child progress)
- When child is validated, parent progress updates
"""

test_cases_cascade = [
    {
        "name": "Child OKR links to parent ORGANIZATION OKR",
        "child_level": "PLANT",
        "parent_level": "ORGANIZATION",
        "can_link": True,
    },
    {
        "name": "Multiple children can link to same parent",
        "parent_id": "plant_okr_001",
        "child_1_id": "dept_okr_001",
        "child_2_id": "dept_okr_002",
        "can_link": True,
    },
    {
        "name": "INDIVIDUAL OKR cannot have children",
        "parent_id": "emp_okr_001",
        "child_level": "INDIVIDUAL",
        "can_link": False,
        "reason": "Individual OKRs are terminal",
    },
    {
        "name": "Parent progress updates when child progress validates",
        "parent_id": "plant_okr_001",
        "child_id": "dept_okr_001",
        "child_progress": 75,
        "expected_parent_progress": 75,  # If only child
    },
    {
        "name": "Parent progress is weighted average of children",
        "parent_id": "plant_okr_001",
        "children": [
            {"id": "dept_okr_001", "progress": 80, "weight": 2},
            {"id": "dept_okr_002", "progress": 60, "weight": 1},
        ],
        "expected_parent_progress": 73.33,  # (80*2 + 60*1) / 3
    },
]


# ════════════════════════════════════════════════════════════════════════════════
# TEST CASE 9: CROSS-HIERARCHY OPERATIONS
# ════════════════════════════════════════════════════════════════════════════════

"""
Scenario: Test operations that span multiple hierarchy levels
"""

test_cases_cross_hierarchy = [
    {
        "name": "Plant Head can link plant OKR to org OKR",
        "creator_role": "PLANT_HEAD",
        "plant_id": "plant_a",
        "child_level": "PLANT",
        "parent_level": "ORGANIZATION",
        "expected": "SUCCESS",
    },
    {
        "name": "Dept Head can create INDIVIDUAL OKR (skipping team level)",
        "creator_role": "DEPT_HEAD",
        "dept_id": "dept_a",
        "okr_level": "INDIVIDUAL",
        "expected": "SUCCESS (with Manager/Team Lead approval)",
    },
    {
        "name": "Manager can view up to plant-level OKRs",
        "user_role": "MANAGER",
        "plant_id": "plant_a",
        "expected_visible": ["org_okr_001", "plant_okr_a_001", "dept_okr_a_001", "team_okr_a_001"],
    },
    {
        "name": "VP Operations can see all plants' OKRs",
        "user_role": "VP_OPERATIONS",
        "expected_visible": ["plant_okr_a_*", "plant_okr_b_*", "plant_okr_c_*"],
    },
]


# ════════════════════════════════════════════════════════════════════════════════
# TEST CASE 10: EDGE CASES & ERROR HANDLING
# ════════════════════════════════════════════════════════════════════════════════

"""
Scenario: Test edge cases and error conditions
"""

test_cases_edge_cases = [
    {
        "name": "Cannot create circular parent reference",
        "parent_id": "okr_a",
        "child_id": "okr_b",
        "linking_as_parent": "okr_a_as_parent_of_okr_b",
        "then_linking": "okr_b_as_parent_of_okr_a",
        "expected": "ERROR - Circular reference detected",
    },
    {
        "name": "Cannot create OKR with missing required scope",
        "okr_level": "DEPARTMENT",
        "scope": {"plant_id": "plant_a", "department_id": None, "team_id": None},
        "expected": "ERROR - Missing required department_id",
    },
    {
        "name": "Cannot assign approved OKR that's already assigned",
        "okr_status": "APPROVED",
        "current_owner": "user_a",
        "attempting_reassign_to": "user_b",
        "expected": "SUCCESS (change owner) or ERROR (based on policy)",
    },
    {
        "name": "Cannot view OKR from different plant",
        "user_plant_id": "plant_a",
        "okr_plant_id": "plant_b",
        "user_role": "PLANT_HEAD",
        "expected": "FORBIDDEN - Cannot view OKR from different plant",
    },
    {
        "name": "Cannot approve OKR with pending validations",
        "okr_id": "okr_001",
        "pending_progress_count": 3,
        "can_approve": False,
        "expected": "WARNING - OKR has pending validations",
    },
]


# ════════════════════════════════════════════════════════════════════════════════
# INTEGRATION TEST SCENARIO: COMPLETE OKR LIFECYCLE
# ════════════════════════════════════════════════════════════════════════════════

"""
End-to-end test of a complete OKR lifecycle:

Q3 Manufacturing Efficiency Initiative
"""

complete_lifecycle_test = {
    "scenario": "Q3 Manufacturing Efficiency Initiative",
    "steps": [
        {
            "step": 1,
            "actor": "CEO",
            "action": "Create ORGANIZATION OKR",
            "details": {
                "title": "Increase manufacturing efficiency by 25%",
                "level": "ORGANIZATION",
                "expected_status": "PENDING",
            },
            "expected_result": "SUCCESS - OKR created with PENDING approval status",
        },
        {
            "step": 2,
            "actor": "CEO",
            "action": "Approve ORGANIZATION OKR",
            "okr_id": "okr_org_001",
            "expected_result": "SUCCESS - OKR status: APPROVED",
        },
        {
            "step": 3,
            "actor": "VP_OPERATIONS",
            "action": "Create PLANT OKR linked to ORG OKR",
            "details": {
                "title": "Plant A efficiency increase by 25%",
                "level": "PLANT",
                "parent_id": "okr_org_001",
                "plant_id": "plant_a",
                "expected_status": "PENDING",
            },
            "expected_result": "SUCCESS - PLANT OKR created, awaiting approval",
        },
        {
            "step": 4,
            "actor": "PLANT_HEAD",
            "action": "Approve PLANT OKR",
            "okr_id": "okr_plant_001",
            "expected_result": "SUCCESS - PLANT OKR approved",
        },
        {
            "step": 5,
            "actor": "PLANT_HEAD",
            "action": "Assign PLANT OKR to Plant Head",
            "okr_id": "okr_plant_001",
            "assignee_id": "plant_head_user_id",
            "expected_result": "SUCCESS - PLANT OKR assigned",
        },
        {
            "step": 6,
            "actor": "PLANT_HEAD",
            "action": "Create DEPARTMENT OKR linked to PLANT OKR",
            "details": {
                "title": "Production dept efficiency +20%",
                "level": "DEPARTMENT",
                "parent_id": "okr_plant_001",
                "plant_id": "plant_a",
                "department_id": "production",
            },
            "expected_result": "SUCCESS - DEPARTMENT OKR created",
        },
        {
            "step": 7,
            "actor": "DEPT_HEAD",
            "action": "Approve DEPARTMENT OKR",
            "okr_id": "okr_dept_001",
            "expected_result": "SUCCESS - DEPARTMENT OKR approved",
        },
        {
            "step": 8,
            "actor": "DEPT_HEAD",
            "action": "Create TEAM OKR linked to DEPARTMENT OKR",
            "details": {
                "title": "Line 1 efficiency +25%",
                "level": "TEAM",
                "parent_id": "okr_dept_001",
                "team_id": "line_1_team",
            },
            "expected_result": "SUCCESS - TEAM OKR created",
        },
        {
            "step": 9,
            "actor": "MANAGER",
            "action": "Approve TEAM OKR",
            "okr_id": "okr_team_001",
            "expected_result": "SUCCESS - TEAM OKR approved",
        },
        {
            "step": 10,
            "actor": "MANAGER",
            "action": "Create and assign INDIVIDUAL OKRs to team members",
            "details": {
                "okrs": [
                    {
                        "title": "Reduce line 1 cycle time by 5 hours",
                        "assignee": "employee_1",
                        "level": "INDIVIDUAL",
                    },
                    {
                        "title": "Achieve 98% line 1 first-pass quality",
                        "assignee": "employee_2",
                        "level": "INDIVIDUAL",
                    },
                ]
            },
            "expected_result": "SUCCESS - Individual OKRs created and assigned",
        },
        {
            "step": 11,
            "actor": "EMPLOYEE_1",
            "action": "Submit progress update: 3 hours reduced (60% progress)",
            "okr_id": "okr_emp_001",
            "progress_value": 60,
            "expected_result": "SUCCESS - Progress submitted with PENDING status",
        },
        {
            "step": 12,
            "actor": "MANAGER",
            "action": "Validate employee progress",
            "progress_id": "progress_001",
            "expected_result": "SUCCESS - Progress validated, KR updated, parent progress recalculated",
        },
        {
            "step": 13,
            "actor": "MANAGER",
            "action": "View progress dashboard",
            "expected_view": {
                "team_okr_progress": "~60% (from children)",
                "dept_okr_progress": "~40% (from team)",
                "plant_okr_progress": "~35% (from depts)",
                "org_okr_progress": "~35% (from plants)",
            },
        },
        {
            "step": 14,
            "actor": "MANAGER",
            "action": "View approval queue",
            "expected": "No pending approvals for TEAM level",
        },
        {
            "step": 15,
            "actor": "CEO",
            "action": "View organization dashboard",
            "expected_view": {
                "total_org_okrs": 1,
                "total_plant_okrs": 1,
                "total_dept_okrs": 1,
                "total_team_okrs": 1,
                "overall_progress": "~35% (weighted cascade)",
                "status": "ON_TRACK",
            },
        },
    ],
}
