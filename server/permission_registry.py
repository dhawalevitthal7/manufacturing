"""
Enterprise Permission Registry — Complete catalog of all configurable permissions
organized by category. Each permission has a key, label, category, and supported actions.
"""

# Permission categories matching the enterprise RBAC structure
PERMISSION_CATEGORIES = [
    {"key": "ORGANIZATION", "label": "Organization Modules", "order": 1},
    {"key": "PLANT", "label": "Plant Modules", "order": 2},
    {"key": "DEPARTMENT", "label": "Department Modules", "order": 3},
    {"key": "TEAM", "label": "Team Modules", "order": 4},
    {"key": "EMPLOYEE", "label": "Employee Modules", "order": 5},
    {"key": "OKR", "label": "OKR Modules", "order": 6},
    {"key": "PROGRESS", "label": "Progress Management", "order": 7},
    {"key": "REVIEW", "label": "Review Modules", "order": 8},
    {"key": "APPROVAL", "label": "Approval & Workflow", "order": 9},
    {"key": "ALIGNMENT", "label": "Alignment Modules", "order": 10},
    {"key": "HIERARCHY", "label": "Reporting Hierarchy", "order": 11},
    {"key": "ANALYTICS", "label": "Analytics Modules", "order": 12},
    {"key": "SETTINGS", "label": "Permission & Settings", "order": 13},
    {"key": "DASHBOARD", "label": "Dashboard Visibility", "order": 14},
]

# actions: which action columns apply to this permission
# "V"=View, "C"=Create, "E"=Edit, "D"=Delete, "A"=Approve, "S"=Assign, "M"=Manage
ALL_ACTIONS = ["view", "create", "edit", "delete", "approve", "assign", "manage"]

PERMISSION_REGISTRY = [
    # ── ORGANIZATION ──
    {"key": "ORG_DASHBOARD", "label": "View Organization Dashboard", "category": "ORGANIZATION", "actions": ["view"]},
    {"key": "ORG_ANALYTICS", "label": "View Organization Analytics", "category": "ORGANIZATION", "actions": ["view"]},
    {"key": "ORG_OKRS", "label": "Organization OKRs", "category": "ORGANIZATION", "actions": ["view", "create", "edit", "delete", "approve"]},
    {"key": "ORG_ALIGNMENT", "label": "Organization Alignment Dashboard", "category": "ORGANIZATION", "actions": ["view"]},
    {"key": "ORG_ACTIVITY_FEED", "label": "Organization Activity Feed", "category": "ORGANIZATION", "actions": ["view"]},
    {"key": "ORG_STRATEGIC_INSIGHTS", "label": "Strategic Insights", "category": "ORGANIZATION", "actions": ["view"]},
    {"key": "ORG_EXEC_ANALYTICS", "label": "Executive Analytics", "category": "ORGANIZATION", "actions": ["view"]},
    # ── PLANT ──
    {"key": "PLANT_VIEW", "label": "View Plants", "category": "PLANT", "actions": ["view"]},
    {"key": "PLANT_MANAGE", "label": "Manage Plants", "category": "PLANT", "actions": ["create", "edit", "delete"]},
    {"key": "PLANT_HEAD_ASSIGN", "label": "Assign Plant Head", "category": "PLANT", "actions": ["assign"]},
    {"key": "PLANT_DASHBOARD", "label": "Plant Dashboard", "category": "PLANT", "actions": ["view"]},
    {"key": "PLANT_OKRS", "label": "Plant OKRs", "category": "PLANT", "actions": ["view", "create", "edit", "approve"]},
    {"key": "PLANT_ANALYTICS", "label": "Plant Analytics", "category": "PLANT", "actions": ["view"]},
    {"key": "PLANT_ALIGNMENT", "label": "Plant Alignment", "category": "PLANT", "actions": ["view"]},
    {"key": "CROSS_PLANT_VISIBILITY", "label": "Cross-Plant Visibility", "category": "PLANT", "actions": ["view"]},
    # ── DEPARTMENT ──
    {"key": "DEPT_VIEW", "label": "View Departments", "category": "DEPARTMENT", "actions": ["view"]},
    {"key": "DEPT_MANAGE", "label": "Manage Departments", "category": "DEPARTMENT", "actions": ["create", "edit", "delete"]},
    {"key": "DEPT_HEAD_ASSIGN", "label": "Assign Department Head", "category": "DEPARTMENT", "actions": ["assign"]},
    {"key": "DEPT_DASHBOARD", "label": "Department Dashboard", "category": "DEPARTMENT", "actions": ["view"]},
    {"key": "DEPT_OKRS", "label": "Department OKRs", "category": "DEPARTMENT", "actions": ["view", "create", "edit", "approve"]},
    {"key": "DEPT_ANALYTICS", "label": "Department Analytics", "category": "DEPARTMENT", "actions": ["view"]},
    {"key": "DEPT_ALIGNMENT", "label": "Department Alignment", "category": "DEPARTMENT", "actions": ["view"]},
    {"key": "DEPT_REVIEWS", "label": "Department Reviews", "category": "DEPARTMENT", "actions": ["view"]},
    # ── TEAM ──
    {"key": "TEAM_VIEW", "label": "View Teams", "category": "TEAM", "actions": ["view"]},
    {"key": "TEAM_MANAGE", "label": "Manage Teams", "category": "TEAM", "actions": ["create", "edit", "delete"]},
    {"key": "TEAM_LEAD_ASSIGN", "label": "Assign Team Lead", "category": "TEAM", "actions": ["assign"]},
    {"key": "TEAM_MEMBERS", "label": "Manage Team Members", "category": "TEAM", "actions": ["manage"]},
    {"key": "TEAM_DASHBOARD", "label": "Team Dashboard", "category": "TEAM", "actions": ["view"]},
    {"key": "TEAM_OKRS", "label": "Team OKRs", "category": "TEAM", "actions": ["view", "create", "edit", "approve"]},
    {"key": "TEAM_ALIGNMENT", "label": "Team Alignment", "category": "TEAM", "actions": ["view"]},
    {"key": "TEAM_ANALYTICS", "label": "Team Analytics", "category": "TEAM", "actions": ["view"]},
    # ── EMPLOYEE ──
    {"key": "EMP_VIEW", "label": "View Employees", "category": "EMPLOYEE", "actions": ["view"]},
    {"key": "EMP_INVITE", "label": "Invite Employees", "category": "EMPLOYEE", "actions": ["create"]},
    {"key": "EMP_EDIT", "label": "Edit Employee Details", "category": "EMPLOYEE", "actions": ["edit"]},
    {"key": "EMP_REMOVE", "label": "Remove Employees", "category": "EMPLOYEE", "actions": ["delete"]},
    {"key": "EMP_REPORTING_MGR", "label": "Assign Reporting Manager", "category": "EMPLOYEE", "actions": ["assign"]},
    {"key": "EMP_DESIGNATION", "label": "Assign Designation", "category": "EMPLOYEE", "actions": ["assign"]},
    {"key": "EMP_PERM_ROLE", "label": "Assign Permission Role", "category": "EMPLOYEE", "actions": ["assign"]},
    {"key": "EMP_HIERARCHY", "label": "View Employee Hierarchy", "category": "EMPLOYEE", "actions": ["view"]},
    {"key": "EMP_PROFILES", "label": "View Employee Profiles", "category": "EMPLOYEE", "actions": ["view"]},
    {"key": "EMP_DIRECTORY", "label": "Access Employee Directory", "category": "EMPLOYEE", "actions": ["view"]},
    # ── OKR ──
    {"key": "OKR_VIEW", "label": "View OKRs", "category": "OKR", "actions": ["view"]},
    {"key": "OKR_MANAGE", "label": "Manage OKRs", "category": "OKR", "actions": ["create", "edit", "delete"]},
    {"key": "OKR_ASSIGN", "label": "Assign OKRs", "category": "OKR", "actions": ["assign"]},
    {"key": "OKR_CASCADE", "label": "Cascade OKRs", "category": "OKR", "actions": ["manage"]},
    {"key": "OKR_LINK", "label": "Link OKRs", "category": "OKR", "actions": ["manage"]},
    {"key": "OKR_ALIGNMENT_MAP", "label": "View Alignment Mapping", "category": "OKR", "actions": ["view"]},
    {"key": "OKR_APPROVE", "label": "Approve OKRs", "category": "OKR", "actions": ["approve"]},
    {"key": "OKR_ARCHIVE", "label": "Archive OKRs", "category": "OKR", "actions": ["manage"]},
    {"key": "OKR_ANALYTICS", "label": "Objective Analytics", "category": "OKR", "actions": ["view"]},
    {"key": "AI_OKR_ASSIST", "label": "AI OKR Assistant", "category": "OKR", "actions": ["view", "create"]},
    # ── PROGRESS ──
    {"key": "PROG_SUBMIT", "label": "Submit Progress", "category": "PROGRESS", "actions": ["create"]},
    {"key": "PROG_EDIT", "label": "Edit Progress", "category": "PROGRESS", "actions": ["edit"]},
    {"key": "PROG_VALIDATE", "label": "Validate Progress", "category": "PROGRESS", "actions": ["approve"]},
    {"key": "PROG_APPROVE", "label": "Approve Progress", "category": "PROGRESS", "actions": ["approve"]},
    {"key": "PROG_REJECT", "label": "Reject Progress", "category": "PROGRESS", "actions": ["approve"]},
    {"key": "PROG_ESCALATE", "label": "Escalate Progress Issues", "category": "PROGRESS", "actions": ["manage"]},
    {"key": "PROG_EVIDENCE", "label": "Upload Evidence", "category": "PROGRESS", "actions": ["create"]},
    {"key": "PROG_NOTES", "label": "Add Execution Notes", "category": "PROGRESS", "actions": ["create"]},
    {"key": "PROG_HISTORY", "label": "View Progress History", "category": "PROGRESS", "actions": ["view"]},
    {"key": "PROG_ANALYTICS", "label": "Progress Analytics", "category": "PROGRESS", "actions": ["view"]},
    # ── REVIEW ──
    {"key": "REV_VIEW", "label": "View Reviews", "category": "REVIEW", "actions": ["view"]},
    {"key": "REV_CREATE", "label": "Create Reviews", "category": "REVIEW", "actions": ["create"]},
    {"key": "REV_SELF", "label": "Submit Self Review", "category": "REVIEW", "actions": ["create"]},
    {"key": "REV_EMPLOYEE", "label": "Review Employees", "category": "REVIEW", "actions": ["manage"]},
    {"key": "REV_APPROVE", "label": "Approve Reviews", "category": "REVIEW", "actions": ["approve"]},
    {"key": "REV_REJECT", "label": "Reject Reviews", "category": "REVIEW", "actions": ["approve"]},
    {"key": "REV_CALIBRATE", "label": "Calibrate Reviews", "category": "REVIEW", "actions": ["manage"]},
    {"key": "REV_PUBLISH", "label": "Publish Final Reviews", "category": "REVIEW", "actions": ["manage"]},
    {"key": "REV_ANALYTICS", "label": "Review Analytics", "category": "REVIEW", "actions": ["view"]},
    {"key": "REV_AI_SUMMARY", "label": "AI Review Summaries", "category": "REVIEW", "actions": ["view"]},
    {"key": "REV_TIMELINE", "label": "Review Timeline", "category": "REVIEW", "actions": ["view"]},
    # ── APPROVAL & WORKFLOW ──
    {"key": "APPR_OKRS", "label": "Approve OKRs", "category": "APPROVAL", "actions": ["approve"]},
    {"key": "APPR_PROGRESS", "label": "Approve Progress", "category": "APPROVAL", "actions": ["approve"]},
    {"key": "APPR_REVIEWS", "label": "Approve Reviews", "category": "APPROVAL", "actions": ["approve"]},
    {"key": "APPR_CHAINS", "label": "Configure Approval Chains", "category": "APPROVAL", "actions": ["manage"]},
    {"key": "APPR_ESCALATION", "label": "Configure Escalation Chains", "category": "APPROVAL", "actions": ["manage"]},
    {"key": "APPR_REV_WORKFLOW", "label": "Configure Review Workflow", "category": "APPROVAL", "actions": ["manage"]},
    {"key": "APPR_REV_CYCLES", "label": "Configure Review Cycles", "category": "APPROVAL", "actions": ["manage"]},
    {"key": "APPR_REV_STAGES", "label": "Configure Review Stages", "category": "APPROVAL", "actions": ["manage"]},
    # ── ALIGNMENT ──
    {"key": "ALIGN_DASHBOARD", "label": "Alignment Dashboard", "category": "ALIGNMENT", "actions": ["view"]},
    {"key": "ALIGN_STRATEGIC", "label": "Strategic Alignment", "category": "ALIGNMENT", "actions": ["view"]},
    {"key": "ALIGN_CASCADE", "label": "Cascading Objectives", "category": "ALIGNMENT", "actions": ["view"]},
    {"key": "ALIGN_CROSS_DEPT", "label": "Cross-Department Alignment", "category": "ALIGNMENT", "actions": ["view"]},
    {"key": "ALIGN_PLANT", "label": "Plant Alignment", "category": "ALIGNMENT", "actions": ["view"]},
    {"key": "ALIGN_TEAM", "label": "Team Alignment", "category": "ALIGNMENT", "actions": ["view"]},
    {"key": "ALIGN_EMP_CONTRIB", "label": "Employee Alignment Contribution", "category": "ALIGNMENT", "actions": ["view"]},
    # ── HIERARCHY ──
    {"key": "HIER_VIEW", "label": "View Reporting Hierarchy", "category": "HIERARCHY", "actions": ["view"]},
    {"key": "HIER_CONFIGURE", "label": "Configure Reporting Structure", "category": "HIERARCHY", "actions": ["manage"]},
    {"key": "HIER_REPORTING_REL", "label": "Assign Reporting Relationships", "category": "HIERARCHY", "actions": ["assign"]},
    {"key": "HIER_REVIEWER_REL", "label": "Configure Reviewer Relationships", "category": "HIERARCHY", "actions": ["assign"]},
    {"key": "HIER_APPROVER_REL", "label": "Configure Approver Relationships", "category": "HIERARCHY", "actions": ["assign"]},
    {"key": "HIER_GRAPH", "label": "View Hierarchy Graph", "category": "HIERARCHY", "actions": ["view"]},
    {"key": "HIER_ORG_CHART", "label": "Access Org Chart", "category": "HIERARCHY", "actions": ["view"]},
    # ── ANALYTICS ──
    {"key": "ANLY_EXECUTIVE", "label": "Executive Analytics", "category": "ANALYTICS", "actions": ["view"]},
    {"key": "ANLY_OPERATIONAL", "label": "Operational Analytics", "category": "ANALYTICS", "actions": ["view"]},
    {"key": "ANLY_DEPARTMENT", "label": "Department Analytics", "category": "ANALYTICS", "actions": ["view"]},
    {"key": "ANLY_TEAM", "label": "Team Analytics", "category": "ANALYTICS", "actions": ["view"]},
    {"key": "ANLY_EMPLOYEE", "label": "Employee Analytics", "category": "ANALYTICS", "actions": ["view"]},
    {"key": "ANLY_REVIEW", "label": "Review Analytics", "category": "ANALYTICS", "actions": ["view"]},
    {"key": "ANLY_ALIGNMENT", "label": "Alignment Analytics", "category": "ANALYTICS", "actions": ["view"]},
    {"key": "ANLY_AI_INSIGHTS", "label": "AI Insights", "category": "ANALYTICS", "actions": ["view"]},
    # ── SETTINGS ──
    {"key": "SETT_PERM_MATRIX", "label": "Access Permission Matrix", "category": "SETTINGS", "actions": ["view", "manage"]},
    {"key": "SETT_MODULE_ACCESS", "label": "Configure Module Access", "category": "SETTINGS", "actions": ["manage"]},
    {"key": "SETT_DASH_VISIBILITY", "label": "Configure Dashboard Visibility", "category": "SETTINGS", "actions": ["manage"]},
    {"key": "SETT_FEATURE_FLAGS", "label": "Configure Feature Flags", "category": "SETTINGS", "actions": ["manage"]},
    {"key": "SETT_DESIG_STRUCTURE", "label": "Configure Designation Structure", "category": "SETTINGS", "actions": ["manage"]},
    {"key": "SETT_ORG_SETTINGS", "label": "Organizational Settings", "category": "SETTINGS", "actions": ["manage"]},
    {"key": "SETT_REVIEW_SETTINGS", "label": "Review Settings", "category": "SETTINGS", "actions": ["manage"]},
    {"key": "SETT_OKR_SETTINGS", "label": "OKR Settings", "category": "SETTINGS", "actions": ["manage"]},
    # ── DASHBOARD VISIBILITY ──
    {"key": "DASH_EXECUTIVE", "label": "Executive Dashboard", "category": "DASHBOARD", "actions": ["view"]},
    {"key": "DASH_PLANT", "label": "Plant Dashboard", "category": "DASHBOARD", "actions": ["view"]},
    {"key": "DASH_DEPARTMENT", "label": "Department Dashboard", "category": "DASHBOARD", "actions": ["view"]},
    {"key": "DASH_TEAM", "label": "Team Dashboard", "category": "DASHBOARD", "actions": ["view"]},
    {"key": "DASH_EMPLOYEE", "label": "Employee Dashboard", "category": "DASHBOARD", "actions": ["view"]},
    {"key": "DASH_SUPERVISOR", "label": "Supervisor Dashboard", "category": "DASHBOARD", "actions": ["view"]},
    {"key": "DASH_ALIGNMENT", "label": "Alignment Dashboard", "category": "DASHBOARD", "actions": ["view"]},
    {"key": "DASH_REVIEW", "label": "Review Dashboard", "category": "DASHBOARD", "actions": ["view"]},
    {"key": "DASH_ANALYTICS", "label": "Analytics Dashboard", "category": "DASHBOARD", "actions": ["view"]},
]

# Hierarchy scope options
HIERARCHY_SCOPES = [
    {"key": "ORGANIZATION", "label": "Entire Organization"},
    {"key": "PLANT", "label": "Specific Plants"},
    {"key": "DEPARTMENT", "label": "Specific Departments"},
    {"key": "TEAM", "label": "Specific Teams"},
    {"key": "DIRECT_REPORTS", "label": "Direct Reports Only"},
    {"key": "SUBTREE", "label": "Subtree Access"},
    {"key": "SELF", "label": "Self Only"},
]

SYSTEM_ROLES = [
    "SUPER_ADMIN", "CEO", "VP_OPERATIONS", "PLANT_HEAD", "PLANT_MANAGER",
    "DEPT_HEAD", "MANAGER", "TEAM_LEAD", "SUPERVISOR", "EMPLOYEE",
    "HR_HEAD", "HR_ADMIN",
]
