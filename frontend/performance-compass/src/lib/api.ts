/**
 * API Service Layer
 * 
 * This module provides a type-safe interface to the Manufacturing Performance OS backend.
 * All requests automatically include JWT Bearer token from auth store.
 * Middleware on server injects org_id, user_id, role from JWT.
 */

// ============================================================================
// AUTH API TYPES
// ============================================================================

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  company_name: string;
  domain?: string;
  org_size?: string;
  admin_name: string;
  admin_email: string;
  password: string;
}

export interface UserAssignment {
  plant_id?: string;
  department_id?: string;
  team_id?: string;
  designation_id?: string;
  shift_id?: string;
}

export interface User {
  id: string;
  email: string;
  name: string;
  system_role: SystemRole;
  is_org_creator?: boolean;
  org_id: string;
  assignments?: UserAssignment[];
  is_active?: boolean;
  avatar_color?: string;
  permissions?: UserPermissionProfile;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

// ============================================================================
// ORG TYPES
// ============================================================================

export interface Organization {
  id: string;
  name: string;
  domain?: string;
  org_size?: string;
  setup_completed?: boolean;
}

export interface Plant {
  id: string;
  name: string;
  location?: string;
  is_active: boolean;
}

export interface Department {
  id: string;
  name: string;
  plant_id: string;
  dept_type?: string;
  is_active: boolean;
}

export interface Team {
  id: string;
  name: string;
  department_id: string;
  is_active: boolean;
}

export interface Shift {
  id: string;
  name: string;
  plant_id: string;
  start_time?: string;
  end_time?: string;
}

export interface Designation {
  id: string;
  title: string;
  level?: number;
}

// ============================================================================
// ORG TREE (OrgNode) TYPES
// ============================================================================

export type NodeType =
  | "ORGANIZATION"
  | "REGION"
  | "CORPORATE_FUNCTION"
  | "PLANT"
  | "VERTICAL"
  | "DEPARTMENT"
  | "SUB_DEPARTMENT"
  | "TEAM";

export interface OrgNode {
  id: string;
  org_id: string;
  parent_id: string | null;
  node_type: NodeType;
  name: string;
  code: string | null;
  head_user_id: string | null;
  path: string;
  depth: number;
  node_metadata: Record<string, unknown> | null;
  is_active: boolean;
  children?: OrgNode[];
  created_at: string;
  updated_at: string;
}

export interface OrgNodeCreateRequest {
  node_type: NodeType;
  name: string;
  parent_id?: string | null;
  code?: string | null;
  head_user_id?: string | null;
  node_metadata?: Record<string, unknown>;
}

export interface OrgNodeUpdateRequest {
  name?: string;
  code?: string;
  head_user_id?: string | null;
  parent_id?: string | null;
  node_metadata?: Record<string, unknown>;
}

/** Body for POST /api/org-tree/regions and POST /api/org-tree/corporate-functions */
export interface OrgTreeNamedNodeCreate {
  name: string;
  code?: string | null;
  head_user_id?: string | null;
}

export interface PlantCreate {
  name: string;
  location?: string;
  code?: string;
  /** When omitted, backend assigns plant under org root. */
  region_id?: string;
}

export interface DepartmentCreate {
  name: string;
  plant_id: string;
  dept_type?: string;
}

export interface TeamCreate {
  name: string;
  department_id: string;
  lead_id?: string;
  /** Initial roster; users must belong to the team's plant. */
  member_user_ids?: string[];
}

export interface ShiftCreate {
  name: string;
  plant_id: string;
  start_time?: string;
  end_time?: string;
}

export interface DesignationCreate {
  title: string;
  level?: number;
}

// ============================================================================
// EMPLOYEE TYPES
// ============================================================================

export interface EmployeeCreate {
  name: string;
  email: string;
  password?: string;
  employee_id?: string;
  system_role?: SystemRole;
  plant_id?: string;
  department_id?: string;
  team_id?: string;
  designation_id?: string;
  shift_id?: string;
}

export interface EmployeeUpdate {
  name?: string;
  email?: string;
  system_role?: SystemRole;
  plant_id?: string;
  department_id?: string;
  team_id?: string;
  designation_id?: string;
  shift_id?: string;
}

export interface Employee {
  id: string;
  name: string;
  email: string;
  employee_id?: string;
  system_role: SystemRole;
  is_active: boolean;
  assignments?: UserAssignment;
  reporting_to?: Employee[];
  direct_reports?: Employee[];
}

// ============================================================================
// HIERARCHY TYPES
// ============================================================================

export type RelationshipType = "DIRECT" | "DOTTED_LINE" | "REVIEWER" | "APPROVER";

export interface ReportingRelCreate {
  employee_id: string;
  manager_id: string;
  relationship_type: RelationshipType;
}

export interface ReportingRelBulkCreate {
  relationships: ReportingRelCreate[];
}

export interface ReportingRelationship {
  id: string;
  employee_id: string;
  manager_id: string;
  relationship_type: RelationshipType;
  is_active: boolean;
}

// ============================================================================
// OKR TYPES
// ============================================================================

export type ObjectiveLevel = "ORGANIZATION" | "PLANT" | "DEPARTMENT" | "TEAM" | "INDIVIDUAL";
export type ObjectiveStatus = "ACTIVE" | "COMPLETED" | "ARCHIVED";
export type KeyResultStatus = "NOT_STARTED" | "IN_PROGRESS" | "COMPLETED";
export type ProgressStatus = "PENDING" | "APPROVED" | "REJECTED" | "REVISION_REQUESTED";

export interface KeyResultCreate {
  title: string;
  target_value: number;
  unit: string;
  weight?: number;
}

export interface KeyResult {
  id: string;
  objective_id: string;
  title: string;
  target_value: number;
  current_value: number;
  unit: string;
  weight?: number;
  status: KeyResultStatus;
  progress_pct?: number;
  pending_updates?: number;
}

export interface ProgressUpdateCreate {
  new_value: number;
  notes?: string;
  blockers?: string;
  evidence_url?: string;
}

export interface ProgressUpdate {
  id: string;
  key_result_id: string;
  value: number;
  notes?: string;
  blocker?: string;
  status: ProgressStatus;
  submitted_by: string;
  submitted_at: string;
  validated_by?: string;
  validated_at?: string;
}

export interface ProgressValidation {
  status: "APPROVED" | "REJECTED" | "REVISION_REQUESTED";
  validation_notes?: string;
}

export interface ObjectiveCreate {
  title: string;
  description?: string;
  level: ObjectiveLevel;
  owner_id?: string;
  cycle_id?: string;
  parent_id?: string;
  plant_id?: string;
  department_id?: string;
  team_id?: string;
}

export interface Objective {
  id: string;
  title: string;
  description?: string;
  level: ObjectiveLevel;
  status: ObjectiveStatus;
  owner_id?: string;
  owner_name?: string;
  assigned_by_id?: string;
  assigned_by_name?: string;
  cycle_id?: string;
  cycle_name?: string;
  parent_id?: string;
  parent_title?: string;
  parent_level?: string;
  plant_id?: string;
  plant_name?: string;
  department_id?: string;
  department_name?: string;
  team_id?: string;
  team_name?: string;
  key_results?: KeyResult[];
  pending_validations?: number;
  children_count?: number;
  progress?: number;
}

export interface ParentOption {
  id: string;
  title: string;
  level: ObjectiveLevel;
  progress: number;
}

export interface AllowedLevelsResponse {
  role: string;
  allowed_levels: ObjectiveLevel[];
}

export interface ProgressSummary {
  [level: string]: {
    total: number;
    on_track: number;
    at_risk: number;
    off_track: number;
    avg_progress: number;
  };
}

// AI Chat OKR types
export interface AIConversationMessage {
  role: "user" | "assistant";
  content: string;
}

export interface AIKeyResult {
  title: string;
  target: number;
  unit: string;
  due_date?: string;
}

export interface AIOKRSuggestion {
  objective: string;
  quarter?: string;
  year?: number;
  due_date?: string;
  key_results: AIKeyResult[];
}

export interface GenerateOKRChatRequest {
  message: string;
  department_name: string;
  hierarchy_level?: string;
  conversation_history?: AIConversationMessage[];
  quarter?: string;
  year?: number;
}

export interface CascadeOKRChatRequest {
  message: string;
  department_name: string;
  parent_objective_id: string;
  conversation_history?: AIConversationMessage[];
  quarter?: string;
  year?: number;
}

export interface GenerateOKRChatResponse {
  reply: string;
  has_suggestion: boolean;
  okr_suggestion?: AIOKRSuggestion;
}

// Progress Submission types
export interface ProgressSubmissionCreate {
  key_result_id: string;
  employee_value: number;
  employee_note?: string;
}

export interface ProgressSubmissionReview {
  action: "approve" | "override" | "reject" | "revision_requested";
  manager_value?: number;
  manager_note?: string;
}

export interface ProgressSubmission {
  id: string;
  key_result_id: string;
  submitted_by: string;
  submitted_by_id: string;
  reviewed_by?: string;
  reviewed_by_id?: string;
  employee_value: number;
  employee_note?: string;
  manager_value?: number;
  manager_note?: string;
  status: string;
  validation_level?: string;
  next_approver_role?: string;
  created_at: string;
  reviewed_at?: string;
}

export interface PendingValidation {
  id: string;
  key_result_id: string;
  key_result_title: string;
  objective_id: string;
  objective_title: string;
  objective_level: string;
  previous_value: number;
  new_value: number;
  notes?: string;
  submitted_by: string;
  submitted_by_id: string;
  created_at: string;
}

export interface CascadeTreeNode {
  id: string;
  title: string;
  description?: string;
  level: ObjectiveLevel;
  status: ObjectiveStatus;
  progress: number;
  rating: string;
  owner_id: string;
  owner_name?: string;
  parent_id?: string;
  plant_id?: string;
  department_id?: string;
  team_id?: string;
  key_results_count: number;
  children: CascadeTreeNode[];
}

// ============================================================================
// REVIEW TYPES
// ============================================================================

export type ReviewCycleStatus = "DRAFT" | "ACTIVE" | "CLOSED";
export type ReviewStatus =
  | "SELF_REVIEW_PENDING"
  | "MANAGER_REVIEW_PENDING"
  | "SKIP_LEVEL_PENDING"
  | "CALIBRATION_PENDING"
  | "COMPLETED";

export interface ReviewCycleCreate {
  name: string;
  start_date: string;
  end_date: string;
}

export interface ReviewCycle {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
  status: ReviewCycleStatus;
  org_id: string;
}

export interface ReviewCreate {
  reviewee_id: string;
  cycle_id: string;
  manager_id?: string;
  skip_level_reviewer_id?: string;
}

export interface SelfReviewSubmit {
  self_summary?: string;
  okr_reflections?: string;
}

export interface ManagerReviewSubmit {
  manager_summary?: string;
  rating?: number;
  strengths?: string;
  development_areas?: string;
}

export interface SkipLevelReviewSubmit {
  skip_level_summary?: string;
  skip_level_rating?: number;
}

export interface CalibrationSubmit {
  calibration_notes?: string;
  final_rating?: number;
}

export interface Review {
  id: string;
  reviewee_id: string;
  reviewee_name?: string;
  cycle_id: string;
  cycle_name?: string;
  status: ReviewStatus;
  manager_id?: string;
  manager_name?: string;
  skip_level_reviewer_id?: string;
  self_summary?: string;
  manager_summary?: string;
  skip_level_summary?: string;
  calibration_notes?: string;
  okr_summary?: string;
  created_at?: string;
  updated_at?: string;
}

// ============================================================================
// DASHBOARD TYPES
// ============================================================================

export type PendingActionType =
  | "PROGRESS_VALIDATION"
  | "MANAGER_REVIEW"
  | "SKIP_LEVEL_REVIEW"
  | "CALIBRATION_REVIEW"
  | "SELF_REVIEW";

export interface PendingAction {
  id: string;
  type: PendingActionType;
  title: string;
  description?: string;
  actor_name?: string;
  created_at: string;
  priority?: "low" | "medium" | "high";
}

export interface StatItem {
  label: string;
  value: number | string;
  delta?: number;
  trend?: "up" | "down" | "flat";
  hint?: string;
}

export interface DashboardStats {
  [key: string]: StatItem;
}

export interface TopObjective {
  id: string;
  objective: string;
  owner: string;
  scope: string;
  level?: string;
  progress: number;
  status: "on_track" | "at_risk" | "off_track" | "completed";
  parent_objective?: string | null;
  key_results?: { title: string; progress: number }[];
}

export interface DepartmentHealth {
  dept: string;
  plant_name?: string;
  onTrack: number;
  atRisk: number;
  offTrack: number;
  avg_progress?: number;
  objective_count?: number;
  employee_count?: number;
}

export interface ExecutionDataPoint {
  week: string;
  planned: number;
  actual: number;
}

export interface DashboardResponse {
  stats: DashboardStats;
  recent_updates?: ProgressUpdate[];
  okr_summary?: {
    [level: string]: { on_track: number; at_risk: number; off_track: number };
  };
  pending_actions?: PendingAction[];
  department_progress?: Array<{ name: string; on_track: number; at_risk: number; off_track: number }>;
  top_objectives?: TopObjective[];
  department_health?: DepartmentHealth[];
  execution_trend?: ExecutionDataPoint[];
}

export interface AuditLog {
  id: string;
  action: string;
  actor_id: string;
  actor_name?: string;
  resource_type: string;
  resource_id: string;
  changes?: Record<string, unknown>;
  timestamp: string;
}

// ============================================================================
// PERMISSION TYPES
// ============================================================================

export interface DashboardModule {
  key: string;
  name: string;
  description?: string;
}

export interface ModuleAccess {
  id: string;
  module_key: string;
  system_role?: SystemRole;
  designation_id?: string;
}

export interface ModuleAccessCreate {
  module_key: string;
  system_role?: SystemRole;
  designation_id?: string;
}

export interface ModuleAccessBulkUpdate {
  accesses: ModuleAccessCreate[];
}

// ============================================================================
// PERMISSIONS & ROLES
// ============================================================================

export interface ModulePermission {
  module_key: string;
  module_name: string;
  category: string;
  can_view: boolean;
  can_create: boolean;
  can_edit: boolean;
  can_approve: boolean;
  can_delete: boolean;
}

export interface UserPermissionProfile {
  user_id: string;
  system_role: string;
  designation_id?: string;
  scope_type: string;
  scoped_plant_id?: string;
  scoped_department_id?: string;
  scoped_team_id?: string;
  scoped_region_id?: string;
  can_view_all_plants: boolean;
  can_view_all_departments: boolean;
  can_view_all_teams: boolean;
  can_view_all_employees: boolean;
  can_create_plants: boolean;
  can_create_departments: boolean;
  can_create_teams: boolean;
  can_create_designations: boolean;
  can_configure_permissions: boolean;
  can_invite_employees: boolean;
  can_assign_roles: boolean;
  can_access_analytics: boolean;
  can_access_audit_logs: boolean;
  modules: ModulePermission[];
}

export interface UserInvitationCreate {
  invited_email: string;
  system_role: string;
  designation_id?: string;
  plant_id?: string;
  department_id?: string;
  team_id?: string;
}

export interface UserInvitationAccept {
  invitation_token: string;
  name: string;
  password: string;
}

export interface UserPermissionUpdate {
  system_role?: string;
  designation_id?: string;
  plant_id?: string;
  department_id?: string;
  team_id?: string;
}

// ============================================================================
// PERMISSION MATRIX TYPES
// ============================================================================

export interface PermissionCategory {
  key: string;
  label: string;
  order: number;
}

export interface PermissionDefinition {
  key: string;
  label: string;
  category: string;
  actions: string[];
}

export interface HierarchyScope {
  key: string;
  label: string;
}

export interface PermissionRegistryResponse {
  categories: PermissionCategory[];
  permissions: PermissionDefinition[];
  hierarchy_scopes: HierarchyScope[];
  system_roles: string[];
  actions: string[];
}

export interface PermissionRuleValues {
  id?: string;
  can_view: boolean;
  can_create: boolean;
  can_edit: boolean;
  can_delete: boolean;
  can_approve: boolean;
  can_assign: boolean;
  can_manage: boolean;
  hierarchy_scope: string;
}

export interface PermissionRuleRecord extends PermissionRuleValues {
  system_role: string;
  permission_key: string;
}

export interface PermissionRuleUpdate {
  permission_key: string;
  can_view: boolean;
  can_create: boolean;
  can_edit: boolean;
  can_delete: boolean;
  can_approve: boolean;
  can_assign: boolean;
  can_manage: boolean;
  hierarchy_scope: string;
}

// ============================================================================
// SYSTEM ROLE ENUM
// ============================================================================

export type SystemRole =
  | "SUPER_ADMIN"
  | "CEO"
  | "VP_OPERATIONS"
  | "PLANT_HEAD"
  | "PLANT_MANAGER"
  | "DEPT_HEAD"
  | "MANAGER"
  | "TEAM_LEAD"
  | "SUPERVISOR"
  | "EMPLOYEE"
  | "HR_HEAD"
  | "HR_ADMIN";

// ============================================================================
// API ERROR RESPONSE
// ============================================================================

export interface ApiErrorResponse {
  detail: string;
}

// ============================================================================
// API CLIENT
// ============================================================================

class APIClient {
  private baseUrl: string;
  private token: string | null = null;

  constructor(baseUrl: string = "http://localhost:8000") {
    this.baseUrl = baseUrl;
    // Try to restore token from localStorage
    if (typeof window !== "undefined") {
      this.token = localStorage.getItem("access_token");
    }
  }

  setToken(token: string) {
    this.token = token;
    localStorage.setItem("access_token", token);
  }

  getToken(): string | null {
    return this.token;
  }

  clearToken() {
    this.token = null;
    localStorage.removeItem("access_token");
  }

  private getHeaders(contentType: string = "application/json") {
    const headers: HeadersInit = {
      "Content-Type": contentType,
    };

    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }

    return headers;
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
    options?: { params?: Record<string, string | number | boolean> }
  ): Promise<T> {
    const url = new URL(`${this.baseUrl}${path}`);

    if (options?.params) {
      Object.entries(options.params).forEach(([key, value]) => {
        // Skip undefined/null — otherwise String(undefined) becomes "undefined" in the query string.
        if (value === undefined || value === null) return;
        url.searchParams.append(key, String(value));
      });
    }

    const response = await fetch(url.toString(), {
      method,
      headers: this.getHeaders(),
      body: body ? JSON.stringify(body) : undefined,
    });

    const data = await response.json() as T | ApiErrorResponse;

    if (!response.ok) {
      const error = data as ApiErrorResponse;
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return data as T;
  }

  // ========================================================================
  // AUTH ENDPOINTS
  // ========================================================================

  async register(request: RegisterRequest): Promise<TokenResponse> {
    return this.request<TokenResponse>("POST", "/api/auth/register", request);
  }

  async login(request: LoginRequest): Promise<TokenResponse> {
    return this.request<TokenResponse>("POST", "/api/auth/login", request);
  }

  async getMe(): Promise<User> {
    return this.request<User>("GET", "/api/auth/me");
  }

  // ========================================================================
  // ORG ENDPOINTS
  // ========================================================================

  async getOrg(): Promise<Organization> {
    return this.request<Organization>("GET", "/api/org");
  }

  async updateOrg(name?: string, domain?: string): Promise<Organization> {
    const params: Record<string, string> = {};
    if (name) params.name = name;
    if (domain) params.domain = domain;
    return this.request<Organization>("PUT", "/api/org", undefined, { params });
  }

  async completeOrgSetup(): Promise<void> {
    return this.request<void>("POST", "/api/org/complete-setup");
  }

  // ========================================================================
  // PLANTS ENDPOINTS
  // ========================================================================

  async createPlant(plant: PlantCreate): Promise<Plant> {
    return this.request<Plant>("POST", "/api/org/plants", plant);
  }

  async getPlants(plantId?: string): Promise<Plant[]> {
    return this.request<Plant[]>("GET", "/api/org/plants", undefined, {
      params: plantId ? { plant_id: plantId } : undefined,
    });
  }

  async updatePlant(plantId: string, plant: PlantCreate): Promise<Plant> {
    return this.request<Plant>("PUT", `/api/org/plants/${plantId}`, plant);
  }

  // ========================================================================
  // DEPARTMENTS ENDPOINTS
  // ========================================================================

  async createDepartment(dept: DepartmentCreate): Promise<Department> {
    return this.request<Department>("POST", "/api/org/departments", dept);
  }

  async getDepartments(plantId?: string): Promise<Department[]> {
    return this.request<Department[]>("GET", "/api/org/departments", undefined, {
      params: plantId ? { plant_id: plantId } : undefined,
    });
  }

  async seedDefaultDepartments(plantId: string): Promise<void> {
    return this.request<void>("POST", "/api/org/departments/seed-defaults", undefined, {
      params: { plant_id: plantId },
    });
  }

  // ========================================================================
  // TEAMS ENDPOINTS
  // ========================================================================

  async createTeam(team: TeamCreate): Promise<Team> {
    return this.request<Team>("POST", "/api/org/teams", team);
  }

  async getTeams(departmentId?: string): Promise<Team[]> {
    return this.request<Team[]>("GET", "/api/org/teams", undefined, {
      params: departmentId ? { department_id: departmentId } : undefined,
    });
  }

  // ========================================================================
  // SHIFTS ENDPOINTS
  // ========================================================================

  async createShift(shift: ShiftCreate): Promise<Shift> {
    return this.request<Shift>("POST", "/api/org/shifts", shift);
  }

  async getShifts(plantId?: string): Promise<Shift[]> {
    return this.request<Shift[]>("GET", "/api/org/shifts", undefined, {
      params: plantId ? { plant_id: plantId } : undefined,
    });
  }

  // ========================================================================
  // DESIGNATIONS ENDPOINTS
  // ========================================================================

  async getDesignations(): Promise<Designation[]> {
    return this.request<Designation[]>("GET", "/api/org/designations");
  }

  async createDesignation(desig: DesignationCreate): Promise<Designation> {
    return this.request<Designation>("POST", "/api/org/designations", desig);
  }

  async seedDefaultDesignations(): Promise<void> {
    return this.request<void>("POST", "/api/org/designations/seed-defaults");
  }

  async updateDesignation(desigId: string, desig: DesignationCreate): Promise<Designation> {
    return this.request<Designation>("PUT", `/api/org/designations/${desigId}`, desig);
  }

  // ========================================================================
  // EMPLOYEE ENDPOINTS
  // ========================================================================

  async getEmployees(params?: {
    search?: string;
    plant_id?: string;
    department_id?: string;
    team_id?: string;
    system_role?: SystemRole;
    is_active?: boolean;
  }): Promise<Employee[]> {
    return this.request<Employee[]>("GET", "/api/employees", undefined, { params });
  }

  async createEmployee(employee: EmployeeCreate): Promise<Employee> {
    return this.request<Employee>("POST", "/api/employees", employee);
  }

  async bulkCreateEmployees(employees: EmployeeCreate[]): Promise<{ created: number; skipped: string[] }> {
    return this.request<{ created: number; skipped: string[] }>("POST", "/api/employees/bulk", {
      employees,
    });
  }

  async getEmployee(uid: string): Promise<Employee> {
    return this.request<Employee>("GET", `/api/employees/${uid}`);
  }

  async updateEmployee(uid: string, employee: EmployeeUpdate): Promise<Employee> {
    return this.request<Employee>("PUT", `/api/employees/${uid}`, employee);
  }

  async deleteEmployee(uid: string): Promise<void> {
    return this.request<void>("DELETE", `/api/employees/${uid}`);
  }

  async getOrgChart(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>("GET", "/api/employees/tree/org-chart");
  }

  // ========================================================================
  // HIERARCHY ENDPOINTS
  // ========================================================================

  async createReportingRelationship(rel: ReportingRelCreate): Promise<ReportingRelationship> {
    return this.request<ReportingRelationship>("POST", "/api/hierarchy/relationships", rel);
  }

  async bulkCreateReportingRelationships(
    rels: ReportingRelBulkCreate
  ): Promise<ReportingRelationship[]> {
    return this.request<ReportingRelationship[]>(
      "POST",
      "/api/hierarchy/relationships/bulk",
      rels
    );
  }

  async getReportingRelationships(params?: {
    employee_id?: string;
    manager_id?: string;
    relationship_type?: RelationshipType;
  }): Promise<ReportingRelationship[]> {
    return this.request<ReportingRelationship[]>(
      "GET",
      "/api/hierarchy/relationships",
      undefined,
      { params }
    );
  }

  async deleteReportingRelationship(relId: string): Promise<void> {
    return this.request<void>("DELETE", `/api/hierarchy/relationships/${relId}`);
  }

  async getReportingChain(uid: string): Promise<Employee[]> {
    return this.request<Employee[]>("GET", `/api/hierarchy/chain/${uid}`);
  }

  async getDirectReports(uid: string): Promise<Employee[]> {
    return this.request<Employee[]>("GET", `/api/hierarchy/subtree/${uid}`);
  }

  async getReviewers(uid: string): Promise<Employee[]> {
    return this.request<Employee[]>("GET", `/api/hierarchy/reviewers/${uid}`);
  }

  async getApprovers(uid: string): Promise<Employee[]> {
    return this.request<Employee[]>("GET", `/api/hierarchy/approvers/${uid}`);
  }

  // ========================================================================
  // OKR ENDPOINTS
  // ========================================================================

  async getObjectives(params?: {
    owner_id?: string;
    level?: ObjectiveLevel;
    cycle_id?: string;
    plant_id?: string;
    department_id?: string;
    team_id?: string;
    parent_id?: string;
  }): Promise<Objective[]> {
    return this.request<Objective[]>("GET", "/api/okrs", undefined, { params });
  }

  async getMyObjectives(): Promise<Objective[]> {
    return this.request<Objective[]>("GET", "/api/okrs/my");
  }

  async createObjective(obj: ObjectiveCreate): Promise<Objective> {
    return this.request<Objective>("POST", "/api/okrs", obj);
  }

  async getAlignmentTree(plantId?: string): Promise<CascadeTreeNode[]> {
    return this.request<CascadeTreeNode[]>("GET", "/api/okrs/alignment-tree", undefined, {
      params: plantId ? { plant_id: plantId } : undefined,
    });
  }

  async getProgressSummary(plantId?: string): Promise<ProgressSummary> {
    return this.request<ProgressSummary>("GET", "/api/okrs/progress-summary", undefined, {
      params: plantId ? { plant_id: plantId } : undefined,
    });
  }

  async getAllowedLevels(role?: string): Promise<AllowedLevelsResponse> {
    return this.request<AllowedLevelsResponse>("GET", "/api/okrs/allowed-levels", undefined, {
      params: role ? { role } : undefined,
    });
  }

  async getParentOptions(level: string, plantId?: string, departmentId?: string): Promise<ParentOption[]> {
    const params: Record<string, string> = { level };
    if (plantId) params.plant_id = plantId;
    if (departmentId) params.department_id = departmentId;
    return this.request<ParentOption[]>("GET", "/api/okrs/parent-options", undefined, { params });
  }

  async getPendingValidations(plantId?: string): Promise<PendingValidation[]> {
    return this.request<PendingValidation[]>("GET", "/api/progress/pending", undefined, {
      params: plantId ? { plant_id: plantId } : undefined,
    });
  }

  async getObjective(objId: string): Promise<Objective> {
    return this.request<Objective>("GET", `/api/okrs/${objId}`);
  }

  async updateObjective(objId: string, obj: ObjectiveCreate): Promise<Objective> {
    return this.request<Objective>("PUT", `/api/okrs/${objId}`, obj);
  }

  async deleteObjective(objId: string): Promise<void> {
    return this.request<void>("DELETE", `/api/okrs/${objId}`);
  }

  async createKeyResult(objId: string, kr: KeyResultCreate): Promise<KeyResult> {
    return this.request<KeyResult>("POST", `/api/okrs/${objId}/key-results`, kr);
  }

  async updateKeyResult(krId: string, kr: KeyResultCreate): Promise<KeyResult> {
    return this.request<KeyResult>("PUT", `/api/okrs/key-results/${krId}`, kr);
  }

  async deleteKeyResult(krId: string): Promise<void> {
    return this.request<void>("DELETE", `/api/okrs/key-results/${krId}`);
  }

  async submitProgressUpdate(krId: string, update: ProgressUpdateCreate): Promise<ProgressUpdate> {
    return this.request<ProgressUpdate>("POST", "/api/progress/submit", update, {
      params: { key_result_id: krId },
    });
  }

  async validateProgress(
    updateId: string,
    validation: ProgressValidation
  ): Promise<ProgressUpdate> {
    return this.request<ProgressUpdate>("POST", `/api/progress/${updateId}/validate`, validation);
  }

  async getProgressHistory(krId: string): Promise<ProgressUpdate[]> {
    return this.request<ProgressUpdate[]>("GET", `/api/progress/key-result/${krId}/history`);
  }

  // ========================================================================
  // AI OKR CHAT ENDPOINTS
  // ========================================================================

  async generateOKRChat(request: GenerateOKRChatRequest): Promise<GenerateOKRChatResponse> {
    return this.request<GenerateOKRChatResponse>("POST", "/api/okrs/ai/generate-okr-chat", request);
  }

  async cascadeOKRChat(request: CascadeOKRChatRequest): Promise<GenerateOKRChatResponse> {
    return this.request<GenerateOKRChatResponse>("POST", "/api/okrs/ai/cascade-okr-chat", request);
  }

  async autoImplementAIOKRSuggestion(data: {
    objective_title: string;
    objective_description?: string;
    hierarchy_level: string;
    quarter: string;
    year: number;
    plant_id?: string;
    department_id?: string;
    team_id?: string;
    owner_id?: string;
    key_results: Array<{ title: string; target: number; unit: string }>;
    parent_objective_id?: string;
  }): Promise<any> {
    return this.request<any>("POST", "/api/okrs/ai/auto-implement-suggestion", data);
  }

  // ========================================================================
  // PROGRESS SUBMISSION ENDPOINTS (new approval workflow)
  // ========================================================================

  async submitProgressSubmission(submission: ProgressSubmissionCreate): Promise<ProgressSubmission> {
    return this.request<ProgressSubmission>("POST", "/api/progress/submissions", submission);
  }

  async getPendingSubmissions(params?: {
    team_id?: string;
    department_id?: string;
  }): Promise<ProgressSubmission[]> {
    return this.request<ProgressSubmission[]>("GET", "/api/progress/submissions/pending", undefined, { params });
  }

  async reviewProgressSubmission(
    submissionId: string,
    review: ProgressSubmissionReview
  ): Promise<ProgressSubmission> {
    return this.request<ProgressSubmission>(
      "POST",
      `/api/progress/submissions/${submissionId}/review`,
      review
    );
  }

  async getCascadingSubmissions(params?: {
    level?: string;
  }): Promise<ProgressSubmission[]> {
    return this.request<ProgressSubmission[]>("GET", "/api/progress/submissions/cascade/pending", undefined, { params });
  }

  async getSubmissionCascadeChain(submissionId: string): Promise<{
    chain: Array<{
      objective_id: string;
      level: ObjectiveLevel;
      title: string;
      progress: number;
      status: ProgressStatus;
      submission_id?: string;
    }>;
    total_levels: number;
    current_submission_id: string;
  }> {
    return this.request("GET", `/api/progress/submissions/${submissionId}/cascade-chain`);
  }

  async getApprovalsDashboard(): Promise<{
    user_role: SystemRole;
    total_pending: number;
    by_level: Record<string, Record<string, number>>;
    user_queue: ProgressSubmission[];
    user_queue_count: number;
  }> {
    return this.request("GET", "/api/progress/approvals/dashboard");
  }

  async getSubmissionHistory(krId: string): Promise<ProgressSubmission[]> {
    return this.request<ProgressSubmission[]>("GET", `/api/progress/submissions/${krId}/history`);
  }

  // ========================================================================
  // TEAM ENDPOINTS
  // ========================================================================

  async getTeamList(params?: {
    department_id?: string;
    plant_id?: string;
  }): Promise<any[]> {
    return this.request<any[]>("GET", "/api/teams", undefined, { params });
  }

  async getTeamDetail(teamId: string): Promise<any> {
    return this.request<any>("GET", `/api/teams/${teamId}`);
  }

  async addTeamMember(teamId: string, data: { user_id: string; is_team_lead?: boolean }): Promise<any> {
    // Query param must not be `user_id`: middleware injects JWT `user_id` and would clobber the member id.
    const params: Record<string, string | boolean> = { member_user_id: data.user_id };
    if (data.is_team_lead !== undefined) params.is_team_lead = data.is_team_lead;
    return this.request<any>("POST", `/api/teams/${teamId}/members`, undefined, { params });
  }

  async removeTeamMember(teamId: string, userId: string): Promise<void> {
    return this.request<void>("DELETE", `/api/teams/${teamId}/members/${userId}`);
  }

  async updateTeamLeadStatus(teamId: string, userId: string, isTeamLead: boolean): Promise<any> {
    return this.request<any>("PUT", `/api/teams/${teamId}/members/${userId}/lead-status`, undefined, {
      params: { is_team_lead: isTeamLead },
    });
  }

  async getTeamMembers(teamId: string): Promise<any[]> {
    return this.request<any[]>("GET", `/api/teams/${teamId}/members`);
  }

  // ========================================================================
  // PROGRESS ENDPOINTS
  // ========================================================================

  async getPendingProgressUpdates(params?: {
    team_id?: string;
    department_id?: string;
  }): Promise<any[]> {
    return this.request<any[]>("GET", "/api/progress/pending", undefined, { params });
  }

  async validateProgressUpdate(updateId: string, validation: {
    status: "APPROVED" | "REJECTED" | "REVISION_REQUESTED";
    validation_notes?: string;
  }): Promise<any> {
    return this.request<any>("POST", `/api/progress/${updateId}/validate`, validation);
  }

  async getObjectiveProgressSummary(objectiveId: string): Promise<any> {
    return this.request<any>("GET", `/api/progress/objective/${objectiveId}/summary`);
  }

  // ========================================================================
  // REVIEW ENDPOINTS
  // ========================================================================

  async getReviewCycles(): Promise<ReviewCycle[]> {
    return this.request<ReviewCycle[]>("GET", "/api/reviews/cycles");
  }

  async createReviewCycle(cycle: ReviewCycleCreate): Promise<ReviewCycle> {
    return this.request<ReviewCycle>("POST", "/api/reviews/cycles", cycle);
  }

  async closeReviewCycle(cycleId: string): Promise<void> {
    return this.request<void>("PUT", `/api/reviews/cycles/${cycleId}/close`);
  }

  async getReviews(params?: {
    cycle_id?: string;
    status?: ReviewStatus;
  }): Promise<Review[]> {
    return this.request<Review[]>("GET", "/api/reviews", undefined, { params });
  }

  async createReview(review: ReviewCreate): Promise<Review> {
    return this.request<Review>("POST", "/api/reviews", review);
  }

  async initiateBulkReviews(cycleId: string): Promise<void> {
    return this.request<void>("POST", "/api/reviews/initiate-bulk", undefined, {
      params: { cycle_id: cycleId },
    });
  }

  async getReview(reviewId: string): Promise<Review> {
    return this.request<Review>("GET", `/api/reviews/${reviewId}`);
  }

  async submitSelfReview(reviewId: string, review: SelfReviewSubmit): Promise<Review> {
    return this.request<Review>("PUT", `/api/reviews/${reviewId}/self-review`, review);
  }

  async submitManagerReview(reviewId: string, review: ManagerReviewSubmit): Promise<Review> {
    return this.request<Review>("PUT", `/api/reviews/${reviewId}/manager-review`, review);
  }

  async submitSkipLevelReview(reviewId: string, review: SkipLevelReviewSubmit): Promise<Review> {
    return this.request<Review>("PUT", `/api/reviews/${reviewId}/skip-level-review`, review);
  }

  async submitCalibration(reviewId: string, calib: CalibrationSubmit): Promise<Review> {
    return this.request<Review>("PUT", `/api/reviews/${reviewId}/calibrate`, calib);
  }

  async generateAISummary(reviewId: string): Promise<void> {
    return this.request<void>("POST", `/api/reviews/${reviewId}/generate-ai`);
  }

  // ========================================================================
  // DASHBOARD ENDPOINTS
  // ========================================================================

  async getDashboard(): Promise<DashboardResponse> {
    return this.request<DashboardResponse>("GET", "/api/dashboard");
  }

  async getAuditLog(limit: number = 50): Promise<AuditLog[]> {
    return this.request<AuditLog[]>("GET", "/api/dashboard/audit-log", undefined, { params: { limit } });
  }

  // ========================================================================
  // PERMISSIONS ENDPOINTS
  // ========================================================================

  async getDashboardModules(): Promise<DashboardModule[]> {
    return this.request<DashboardModule[]>("GET", "/api/permissions/modules");
  }

  async getModuleAccess(params?: {
    system_role?: SystemRole;
    designation_id?: string;
  }): Promise<ModuleAccess[]> {
    return this.request<ModuleAccess[]>("GET", "/api/permissions/access", undefined, { params });
  }

  async createModuleAccess(access: ModuleAccessCreate): Promise<ModuleAccess> {
    return this.request<ModuleAccess>("POST", "/api/permissions/access", access);
  }

  async bulkUpdateModuleAccess(update: ModuleAccessBulkUpdate): Promise<void> {
    return this.request<void>("POST", "/api/permissions/access/bulk", update);
  }

  async deleteModuleAccess(ruleId: string): Promise<void> {
    return this.request<void>("DELETE", `/api/permissions/access/${ruleId}`);
  }

  async getMyModules(): Promise<ModulePermission[]> {
    return this.request<ModulePermission[]>("GET", "/api/permissions/my-modules");
  }

  async getMyPermissions(): Promise<UserPermissionProfile> {
    return this.request<UserPermissionProfile>("GET", "/api/permissions/my-permissions");
  }

  async getUserPermissions(userId: string): Promise<UserPermissionProfile> {
    return this.request<UserPermissionProfile>("GET", `/api/permissions/user/${userId}/profile`);
  }

  async updateUserPermissions(userId: string, update: UserPermissionUpdate): Promise<UserPermissionProfile> {
    return this.request<UserPermissionProfile>("PUT", `/api/permissions/user/${userId}/permissions`, update);
  }

  async inviteUser(invitation: UserInvitationCreate): Promise<{ id: string; email: string; status: string; token: string; expires_at: string }> {
    return this.request<{ id: string; email: string; status: string; token: string; expires_at: string }>("POST", "/api/permissions/invitations", invitation);
  }

  async acceptInvitation(accept: UserInvitationAccept): Promise<TokenResponse> {
    return this.request<TokenResponse>("POST", "/api/permissions/invitations/accept", accept);
  }

  async listInvitations(): Promise<Array<{ id: string; email: string; system_role: string; status: string; invited_at: string; accepted_at?: string; expires_at: string }>> {
    return this.request<Array<{ id: string; email: string; system_role: string; status: string; invited_at: string; accepted_at?: string; expires_at: string }>>("GET", "/api/permissions/invitations");
  }

  async revokeInvitation(invitationId: string): Promise<{ status: string }> {
    return this.request<{ status: string }>("DELETE", `/api/permissions/invitations/${invitationId}`);
  }

  async seedDefaultPermissions(): Promise<void> {
    return this.request<void>("POST", "/api/permissions/seed-defaults");
  }

  // ── Permission Matrix ──

  async getPermissionRegistry(): Promise<PermissionRegistryResponse> {
    return this.request<PermissionRegistryResponse>("GET", "/api/permission-matrix/registry");
  }

  async getPermissionRules(systemRole?: string): Promise<PermissionRuleRecord[]> {
    const params = systemRole ? `?system_role=${systemRole}` : "";
    return this.request<PermissionRuleRecord[]>("GET", `/api/permission-matrix/rules${params}`);
  }

  async getRoleRules(role: string): Promise<Record<string, PermissionRuleValues>> {
    return this.request<Record<string, PermissionRuleValues>>("GET", `/api/permission-matrix/rules/${role}`);
  }

  async bulkUpdatePermissionRules(systemRole: string, rules: PermissionRuleUpdate[]): Promise<{ upserted: number }> {
    return this.request<{ upserted: number }>("PUT", "/api/permission-matrix/rules/bulk", {
      system_role: systemRole,
      rules,
    });
  }

  async seedDefaultPermissionMatrix(): Promise<{ seeded: number }> {
    return this.request<{ seeded: number }>("POST", "/api/permission-matrix/seed-defaults");
  }

  // ========================================================================
  // ORG TREE ENDPOINTS
  // ========================================================================

  async fetchOrgTree(): Promise<OrgNode | { roots: OrgNode[] }> {
    const t = await this.request<OrgNode | { roots: OrgNode[] } | { error: string }>("GET", "/api/org-tree");
    if (t && typeof t === "object" && "error" in t && !("id" in t) && !("roots" in t)) {
      throw new Error(String((t as { error: string }).error));
    }
    return t as OrgNode | { roots: OrgNode[] };
  }

  async fetchOrgNode(nodeId: string): Promise<OrgNode> {
    return this.request<OrgNode>("GET", `/api/org-tree/${nodeId}`);
  }

  async createOrgNode(payload: OrgNodeCreateRequest): Promise<OrgNode> {
    return this.request<OrgNode>("POST", "/api/org-tree", payload);
  }

  async updateOrgNode(nodeId: string, payload: OrgNodeUpdateRequest): Promise<OrgNode> {
    return this.request<OrgNode>("PATCH", `/api/org-tree/${nodeId}`, payload);
  }

  async deleteOrgNode(nodeId: string): Promise<{ status: string; node_id: string }> {
    return this.request<{ status: string; node_id: string }>("DELETE", `/api/org-tree/${nodeId}`);
  }

  async createRegion(body: OrgTreeNamedNodeCreate): Promise<OrgNode> {
    return this.request<OrgNode>("POST", "/api/org-tree/regions", body);
  }

  async createCorporateFunction(body: OrgTreeNamedNodeCreate): Promise<OrgNode> {
    return this.request<OrgNode>("POST", "/api/org-tree/corporate-functions", body);
  }

}

// ============================================================================
// SINGLETON INSTANCE
// ============================================================================

export const api = new APIClient();
