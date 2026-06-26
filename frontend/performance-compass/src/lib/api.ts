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
  /** Dotted-line link to corporate function / vertical (plant-embedded depts only). */
  functional_parent_id?: string | null;
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
  functional_parent_id?: string | null;
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

export type ObjectiveLevel =
  | "ORGANIZATION"
  | "REGION"
  | "VERTICAL"
  | "SUB_DEPARTMENT"
  | "PLANT"
  | "DEPARTMENT"
  | "TEAM"
  | "INDIVIDUAL";

export type FunctionArea =
  | "OPERATIONS"
  | "FINANCE"
  | "HR"
  | "SALES_MARKETING"
  | "PROCUREMENT"
  | "TECHNICAL"
  | "REGIONS";
export type ObjectiveStatus = "ACTIVE" | "COMPLETED" | "ARCHIVED";
export type KeyResultStatus = "NOT_STARTED" | "IN_PROGRESS" | "COMPLETED";
export type ProgressStatus = "PENDING" | "APPROVED" | "REJECTED" | "REVISION_REQUESTED";

export interface KeyResultCreate {
  title: string;
  target_value: number;
  unit: string;
  weight?: number;
}

export interface KRIngestSourceInfo {
  id: string;
  key_result_id: string;
  source_system: string;
  source_metric_tag: string | null;
  transform_expr?: string | null;
  is_active: boolean;
  last_ingest_at?: string | null;
  last_ingest_value?: number | null;
  created_at?: string | null;
}

export interface KRIngestSourceConfigure {
  source_system: string;
  source_metric_tag: string;
  transform_expr?: string;
  is_active?: boolean;
  rotate_token?: boolean;
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
  /** Latest value awaiting manager approval (not yet in current_value). */
  pending_submitted_value?: number | null;
  pending_submitted_note?: string | null;
  ingest_source?: KRIngestSourceInfo | null;
  auto_ingest_active?: boolean;
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

/** Role-based OKR list visibility (GET /api/okrs/visibility-scope). */
export interface OkrVisibilityScope {
  anchor_level: string;
  scope_id: string | null;
  visible_levels: ObjectiveLevel[];
  parent_level: string | null;
  unrestricted: boolean;
  region_id: string | null;
  region_name: string | null;
  plant_ids: string[];
  plant_id: string | null;
  department_id: string | null;
  team_id: string | null;
}

export interface ObjectiveCreate {
  title: string;
  description?: string;
  level: ObjectiveLevel;
  owner_id?: string;
  cycle_id?: string;
  parent_id?: string;
  region_id?: string;
  plant_id?: string;
  department_id?: string;
  team_id?: string;
  function_area?: FunctionArea;
  function_node_id?: string;
}

/** PATCH /api/okrs/{id} — SUPER_ADMIN only; exactly one field. */
export interface ObjectiveFunctionalParentPatch {
  functional_parent_obj_id?: string | null;
}

export type OkrLifecycleStatus =
  | "DRAFT"
  | "PENDING_APPROVAL"
  | "ACTIVE"
  | "REJECTED"
  | "ACHIEVED"
  | "MISSED"
  | "ARCHIVED"
  | "AI_DRAFT"
  | "UNDER_REVIEW"
  | "PENDING_PARENT_APPROVAL"
  | "AI_REJECTED";

export interface AICascadeDraft {
  id: string;
  title: string;
  description?: string;
  level: ObjectiveLevel;
  okr_status: string;
  review_status?: string;
  ai_generated: boolean;
  ai_confidence?: number;
  ai_generation_reason?: string;
  ai_generation_version?: number;
  alignment_score?: number;
  parent_id?: string;
  parent_title?: string;
  parent_objective_id?: string;
  owner_id?: string;
  owner_name?: string;
  region_id?: string;
  quarter?: string;
  year?: number;
  submitted_for_parent_approval_at?: string | null;
  rejection_reason?: string | null;
  created_at?: string;
  key_results?: KeyResult[];
  ai_metadata?: Record<string, unknown>;
  ai_prompt_tokens?: number | null;
  ai_completion_tokens?: number | null;
  ai_total_tokens?: number | null;
}

export interface AICascadeVersion {
  id: string;
  objective_id: string;
  version: number;
  change_type: string;
  title: string;
  description?: string;
  key_results: KeyResult[];
  ai_metadata?: Record<string, unknown>;
  changed_by_id?: string;
  created_at?: string;
}

export interface AlignmentPreview {
  child_id: string;
  child_title: string;
  child_description?: string;
  child_level: string;
  parent_id: string;
  parent_title: string;
  parent_description?: string;
  parent_level: string;
  alignment_score?: number;
  confidence?: number;
  reasoning?: string;
  child_key_results: { title: string; target_value: number; unit: string }[];
  parent_key_results: { title: string; target_value: number; unit: string }[];
}

export interface CascadeNotification {
  id: string;
  objective_id: string;
  event_type: string;
  title: string;
  body?: string;
  is_read: boolean;
  actor_user_id?: string;
  created_at?: string;
}

export interface Objective {
  id: string;
  title: string;
  description?: string;
  level: ObjectiveLevel;
  status: ObjectiveStatus;
  okr_status?: OkrLifecycleStatus;
  creation_approval_status?: string;
  rejection_reason?: string | null;
  pending_approver_user_id?: string | null;
  pending_approver_role?: string | null;
  pending_approver_name?: string | null;
  creation_approved_by_id?: string | null;
  creation_approved_by_name?: string | null;
  creation_approved_at?: string | null;
  kr_baseline_locked?: boolean;
  can_publish_as_ceo?: boolean;
  owner_id?: string;
  owner_name?: string;
  assigned_by_id?: string;
  assigned_by_name?: string;
  cycle_id?: string;
  cycle_name?: string;
  parent_id?: string;
  functional_parent_obj_id?: string | null;
  parent_title?: string;
  parent_level?: string;
  functional_parent_title?: string;
  functional_parent_level?: string;
  region_id?: string;
  region_name?: string;
  plant_id?: string;
  plant_name?: string;
  department_id?: string;
  department_name?: string;
  team_id?: string;
  team_name?: string;
  function_area?: FunctionArea | null;
  function_area_label?: string | null;
  function_node_id?: string | null;
  key_results?: KeyResult[];
  pending_validations?: number;
  children_count?: number;
  progress?: number;
  creation_primary_approved_at?: string | null;
  creation_functional_approved_at?: string | null;
  approval_chain_status?: ApprovalChainStatus;
}

export type ApprovalStepStatus = "PENDING" | "APPROVED" | "REJECTED" | "SKIPPED";

export interface ApprovalChainStep {
  id: string;
  sequence_order: number;
  approval_type: "LINE" | "FUNCTIONAL";
  status: ApprovalStepStatus;
  approver_id?: string | null;
  approver_name?: string | null;
  approver_role?: string | null;
  decided_at?: string | null;
  comment?: string | null;
}

export interface ApprovalChainStatus {
  line?: ApprovalStepStatus | null;
  functional?: ApprovalStepStatus | null;
  steps: ApprovalChainStep[];
  current_step_id?: string | null;
  current_approval_type?: "LINE" | "FUNCTIONAL" | null;
  is_complete?: boolean;
}

export interface ApprovalQueueItem {
  subject_type: "OKR_CREATION" | "PROGRESS_SUBMISSION";
  subject_id: string;
  title?: string;
  level?: string;
  owner_name?: string;
  okr_status?: string;
  creation_approval_status?: string;
  key_result_id?: string;
  key_result_title?: string;
  objective_title?: string;
  objective_level?: string;
  submitted_by_name?: string;
  employee_value?: number;
  status?: string;
  approval_chain_status: ApprovalChainStatus;
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

export type CycleType = "ANNUAL" | "HALF_YEARLY" | "QUARTERLY" | "MONTHLY";
export type CycleStatus = "PLANNED" | "ACTIVE" | "FROZEN" | "CLOSED";

export interface Cycle {
  id: string;
  name: string;
  cycle_type: CycleType;
  start_date: string;
  end_date: string;
  freeze_date: string;
  status: CycleStatus;
  applies_to_levels: number[];
  created_at: string;
}

export interface CycleCreate {
  name: string;
  cycle_type?: CycleType;
  start_date: string;
  end_date: string;
  freeze_date: string;
  applies_to_levels?: number[];
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
  objective_level?: string;
  objective_title?: string;
  created_at: string;
  reviewed_at?: string;
  approval_chain_status?: ApprovalChainStatus;
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
  /** Present when merged from /api/progress/pending */
  source?: "submission" | "legacy_update";
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
// CONTINUOUS CHECK-IN TYPES
// ============================================================================

export type EmployeeMood = "VERY_POSITIVE" | "POSITIVE" | "NEUTRAL" | "CONCERNING" | "CRITICAL";

export interface ContinuousCheckinSubmit {
  checkin_week: number;
  checkin_month?: number;
  achievements: string;
  key_wins?: string[];
  blockers: string;
  risks?: Array<{ risk: string; impact: string }>;
  support_needed?: string;
  confidence_score: number; // 0-100
  engagement_score: number; // 1-10
  employee_mood: EmployeeMood;
  okr_progress_snapshot?: Record<string, number>;
  progress_notes?: string;
}

export interface ManagerCheckinResponse {
  manager_feedback: string;
  manager_response_quality?: number; // 1-5
  action_items?: Array<{ action: string; owner: string; due_date: string }>;
  corrective_actions?: string[];
  coaching_notes?: string;
}

export interface ContinuousCheckin {
  id: string;
  employee_id: string;
  employee_name?: string;
  employee_role?: string;
  manager_id: string;
  manager_name?: string;
  checkin_week: number;
  checkin_month?: number;
  achievements: string;
  key_wins?: string[];
  blockers: string;
  risks?: Array<{ risk: string; impact: string }>;
  support_needed?: string;
  confidence_score: number;
  engagement_score: number;
  employee_mood: EmployeeMood;
  okr_progress_snapshot?: Record<string, number>;
  progress_notes?: string;
  manager_feedback?: string;
  manager_response_quality?: number;
  action_items?: Array<{ action: string; owner: string; due_date: string }>;
  corrective_actions?: string[];
  coaching_notes?: string;
  workflow_status?:
    | "DRAFT"
    | "SUBMITTED"
    | "UNDER_REVIEW"
    | "ACTION_REQUIRED"
    | "ESCALATED"
    | "RESOLVED"
    | "CLOSED";
  status: string;
  performance_concern_flag?: boolean;
  concern_notes?: string;
  escalation_reason?: string;
  escalation_target_name?: string;
  comments?: CheckinComment[];
  is_latest?: boolean;
  created_at: string;
  updated_at?: string;
  manager_responded_at?: string;
  submitted_at?: string;
}

export interface CheckinComment {
  id: string;
  checkin_id: string;
  commented_by_user_id: string;
  commented_by_name?: string;
  parent_comment_id?: string | null;
  comment: string;
  comment_type?: string;
  commented_at: string;
}

// ============================================================================
// PERFORMANCE REVIEW TYPES
// ============================================================================

export type ReviewState = 
  | "DRAFT" 
  | "SELF_SUBMITTED" 
  | "MANAGER_REVIEW"
  | "DEPT_HEAD_MODERATION"
  | "PEER_REVIEW" 
  | "SKIP_LEVEL_REVIEW" 
  | "HR_CALIBRATION" 
  | "FINALIZED" 
  | "PUBLISHED" 
  | "LOCKED" 
  | "ARCHIVED";

export type ReviewRating = "EXCEEDS_EXPECTATIONS" | "MEETS_EXPECTATIONS" | "BELOW_EXPECTATIONS" | "NEEDS_IMPROVEMENT";

export interface OKRAssessment {
  okr_id: string;
  title: string;
  kr_id?: string;
  kr_title?: string;
  self_assessed_completion?: number;
  quality_assessment?: string;
  alignment_contribution?: string;
}

export interface SelfReviewSubmitEnhanced {
  achievements: string;
  major_wins?: string[];
  okr_self_assessment?: OKRAssessment[];
  strengths: string;
  challenges: string;
  growth_areas?: string[];
  evidence?: string;
}

export interface ManagerReviewSubmitEnhanced {
  okr_outcomes_assessment: string;
  kr_completion_accuracy?: number;
  kr_quality_assessment: string;
  behavioral_competency_scores?: Record<string, number>;
  collaboration_assessment?: string;
  ownership_assessment?: string;
  accountability_assessment?: string;
  execution_assessment?: string;
  manager_feedback: string;
  strengths_observed?: string;
  development_areas_observed?: string;
  promotion_eligible?: boolean;
  recommended_for_promotion?: boolean;
  pip_needed?: boolean;
  attrition_risk?: string;
}

export interface SkipLevelReviewSubmitEnhanced {
  executive_perspective: string;
  strategic_impact_assessment: string;
  leadership_potential?: boolean;
  next_level_readiness?: boolean;
  succession_ready?: boolean;
  recommended_development?: string;
  recommended_next_role?: string;
}

export interface PerformanceReviewEnhanced {
  id: string;
  employee_id: string;
  employee_name?: string;
  manager_id: string;
  manager_name?: string;
  skip_level_manager_id?: string;
  hr_reviewer_id?: string;
  review_cycle_id: string;
  cycle_name?: string;
  current_state: ReviewState;
  final_rating?: ReviewRating;
  final_score?: number; // 0-100
  rating_locked?: boolean;
  okr_achievement_score?: number;
  okr_ids?: string[];
  promotion_eligible?: boolean;
  attrition_risk?: string;
  created_at: string;
  updated_at: string;
  finalized_at?: string;
  published_at?: string;
  okr_context?: Array<{ id: string; title: string; progress: number; level?: string }>;
  ai_review_status?: string;
  promotion_recommendation?: string;
  promotion_rationale?: string;
  employee_performance_narrative?: string;
  shared_with_employee_at?: string;
  submitted_to_dept_head_at?: string;
  dept_head_reviewer_id?: string;
  dept_head_name?: string;
  requires_dept_moderation?: boolean;
}

export interface ReviewableTeamMember {
  employee_id: string;
  employee_name: string;
  employee_role: string;
  employee_email?: string;
  review_id?: string | null;
  review_state?: string | null;
  ai_review_status?: string;
  manager_id?: string | null;
  manager_name?: string | null;
  can_initiate: boolean;
  can_generate_ai: boolean;
  can_open: boolean;
  okr_count: number;
  okr_avg_progress: number;
  checkin_count: number;
  progress_submission_count: number;
}

export interface AIReviewPayload {
  executive_summary?: string;
  okr_performance_analysis?: string;
  self_review_synthesis?: string;
  checkin_insights?: string;
  strengths?: string[];
  development_areas?: string[];
  promotion_recommendation?: "READY" | "NEEDS_DEVELOPMENT" | "NOT_READY";
  promotion_rationale?: string;
  recommended_rating?: ReviewRating;
  behavioral_competency_scores?: Record<string, number>;
  coaching_actions?: string[];
  risk_flags?: string[];
  source?: string;
}

export interface AIReviewResponse {
  review_id: string;
  ai_review_status: string;
  ai_review_generated_at?: string;
  payload?: AIReviewPayload;
  employee_performance_narrative?: string;
  promotion_recommendation?: string;
  promotion_rationale?: string;
  shared_with_employee_at?: string;
  submitted_to_dept_head_at?: string;
}

export interface ReviewCalculation {
  id?: string;
  performance_review_id: string;
  okr_achievement_score: number | null;
  kr_quality_score: number | null;
  manager_feedback_score: number | null;
  behavioral_competency_score: number | null;
  peer_feedback_score: number | null;
  continuous_checkin_score: number | null;
  calculated_final_score: number;
  final_rating: ReviewRating;
  confidence_score: number;
  component_available?: Record<string, boolean>;
  bias_flags?: string[];
  override_applied?: boolean;
  override_reason?: string;
  calculation_timestamp?: string;
}

// ============================================================================
// 360 FEEDBACK TYPES
// ============================================================================

export type FeedbackType = "PEER" | "SUBORDINATE" | "CROSS_FUNCTIONAL" | "MANAGER";

export interface FeedbackTemplateQuestion {
  id: string;
  question: string;
  scale: number;
  required: boolean;
}

export interface FeedbackTemplate {
  id: string;
  org_id: string;
  feedback_type: FeedbackType;
  role_type?: string;
  name: string;
  questions: FeedbackTemplateQuestion[];
  created_at: string;
  updated_at: string;
}

export interface FeedbackResponseSubmit {
  performance_review_id: string;
  feedback_giver_user_id: string;
  feedback_type: FeedbackType;
  is_anonymous?: boolean;
  responses: Record<string, any>;
  overall_feedback: string;
  strengths_observed?: string[];
  development_areas?: string[];
}

export interface FeedbackResponse {
  id: string;
  performance_review_id: string;
  feedback_giver_user_id: string;
  feedback_type: FeedbackType;
  is_anonymous: boolean;
  responses: Record<string, any>;
  overall_feedback: string;
  strengths_observed?: string[];
  development_areas?: string[];
  sentiment_score?: number; // -1 to +1
  created_at: string;
}

export interface FeedbackSynthesis {
  id: string;
  performance_review_id: string;
  peer_feedback_score?: number;
  peer_feedback_count?: number;
  subordinate_feedback_score?: number;
  subordinate_feedback_count?: number;
  cross_functional_feedback_score?: number;
  cross_functional_feedback_count?: number;
  strengths_consensus?: Array<{ theme: string; count: number }>;
  development_consensus?: Array<{ theme: string; count: number }>;
  perception_vs_self_gap?: number;
  created_at: string;
  updated_at: string;
}

// ============================================================================
// COMPETENCY TYPES
// ============================================================================

export interface CompetencyFramework {
  id: string;
  org_id: string;
  role_type: string;
  name: string;
  department_id?: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProficiencyLevel {
  level: number;
  name: string;
  description: string;
}

export interface Competency {
  id: string;
  framework_id: string;
  name: string;
  description?: string;
  weight?: number;
  proficiency_levels: ProficiencyLevel[];
  enabled: boolean;
  display_order: number;
}

export interface CompetencyAssessment {
  id: string;
  review_section_id: string;
  competency_id: string;
  competency_name?: string;
  proficiency_level: number; // 1-5
  assessor_comments?: string;
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
  | "COO"
  | "CFO"
  | "CMO"
  | "CPO"
  | "CSO"
  | "CHRO"
  | "CRO"
  | "FUNCTIONAL_SUB_HEAD"
  | "AREA_SALES_MANAGER"
  | "REGIONAL_HEAD"
  | "PLANT_HEAD"
  | "PLANT_MANAGER"
  | "DEPT_HEAD"
  | "MANAGER"
  | "TEAM_LEAD"
  | "SUPERVISOR"
  | "EMPLOYEE"
  | "HR_HEAD"
  | "HR_ADMIN";

export interface FunctionAreaOption {
  value: FunctionArea;
  label: string;
}

export interface FunctionalOverviewFunction {
  function_area: FunctionArea;
  label: string;
  vertical_okrs: Array<Record<string, unknown>>;
  aggregate_progress: number;
  org_alignments: Array<Record<string, unknown>>;
  count: number;
}

export interface FunctionalOverviewResponse {
  functions: FunctionalOverviewFunction[];
  viewer_function_area: FunctionArea | null;
}

export interface FunctionStructureTree {
  vertical: Record<string, unknown>;
  sub_heads: Array<Record<string, unknown>>;
  plant_departments: Array<Record<string, unknown>>;
}

export interface FunctionStructureResponse {
  function_area: FunctionArea | null;
  trees: FunctionStructureTree[];
}

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

  async getVisibilityScope(): Promise<OkrVisibilityScope> {
    return this.request<OkrVisibilityScope>("GET", "/api/okrs/visibility-scope");
  }

  async getObjectives(params?: {
    owner_id?: string;
    level?: ObjectiveLevel;
    cycle_id?: string;
    year?: number;
    quarter?: string;
    plant_id?: string;
    department_id?: string;
    team_id?: string;
    parent_id?: string;
    function_area?: FunctionArea;
  }): Promise<Objective[]> {
    return this.request<Objective[]>("GET", "/api/okrs", undefined, { params });
  }

  async getFunctionalOverview(functionArea?: FunctionArea): Promise<FunctionalOverviewResponse> {
    return this.request<FunctionalOverviewResponse>(
      "GET",
      "/api/okrs/functional-overview",
      undefined,
      { params: functionArea ? { function_area: functionArea } : undefined },
    );
  }

  async getFunctionStructure(): Promise<FunctionStructureResponse> {
    return this.request<FunctionStructureResponse>("GET", "/api/okrs/function-structure");
  }

  async getFunctionAreas(): Promise<{ areas: FunctionAreaOption[] }> {
    return this.request<{ areas: FunctionAreaOption[] }>("GET", "/api/okrs/function-areas");
  }

  async getMyObjectives(): Promise<Objective[]> {
    return this.request<Objective[]>("GET", "/api/okrs/my");
  }

  async createObjective(obj: ObjectiveCreate): Promise<Objective> {
    return this.request<Objective>("POST", "/api/okrs", obj);
  }

  async submitObjectiveForApproval(objId: string): Promise<{ objective: Objective }> {
    return this.request("POST", `/api/okrs/${objId}/submit-for-approval`);
  }

  async publishObjective(objId: string): Promise<Objective> {
    return this.request<Objective>("POST", `/api/okrs/${objId}/publish`);
  }

  async getLifecycleApprovalQueue(
    status: "pending" | "approved" | "rejected" = "pending",
  ): Promise<Objective[]> {
    return this.request<Objective[]>("GET", "/api/okrs/lifecycle-approval-queue", undefined, {
      params: { status },
    });
  }

  async getPendingLifecycleApprovals(): Promise<Objective[]> {
    return this.getLifecycleApprovalQueue("pending");
  }

  async getAdminLifecycleOverrides(): Promise<Objective[]> {
    return this.request<Objective[]>("GET", "/api/okrs/admin/lifecycle-overrides");
  }

  async adminApproveObjective(objId: string, overrideReason: string): Promise<Objective> {
    return this.request<Objective>("POST", `/api/okrs/${objId}/admin-approve`, {
      override_reason: overrideReason,
    });
  }

  async adminRejectObjective(
    objId: string,
    overrideReason: string,
    rejectionReason?: string,
  ): Promise<Objective> {
    return this.request<Objective>("POST", `/api/okrs/${objId}/admin-reject`, {
      override_reason: overrideReason,
      rejection_reason: rejectionReason,
    });
  }

  async approveOkrHierarchy(okrId: string, approvalNotes = ""): Promise<unknown> {
    return this.request("POST", `/api/okrs/hierarchy/${okrId}/approve`, undefined, {
      params: { approval_notes: approvalNotes },
    });
  }

  async rejectOkrHierarchy(okrId: string, rejectionReason: string): Promise<unknown> {
    return this.request("POST", `/api/okrs/hierarchy/${okrId}/reject`, undefined, {
      params: { rejection_reason: rejectionReason },
    });
  }

  // ========================================================================
  // AI CASCADE ENDPOINTS
  // ========================================================================

  async getAiDraftOkrs(status?: string): Promise<AICascadeDraft[]> {
    return this.request<AICascadeDraft[]>("GET", "/api/okrs/ai-drafts", undefined, {
      params: status ? { status } : {},
    });
  }

  async getParentApprovalQueue(): Promise<AICascadeDraft[]> {
    return this.request<AICascadeDraft[]>("GET", "/api/okrs/parent-approval-queue");
  }

  async reviewAiDraft(
    objId: string,
    body: { title?: string; description?: string; key_results?: KeyResultCreate[] },
  ): Promise<AICascadeDraft> {
    return this.request<AICascadeDraft>("PUT", `/api/okrs/${objId}/review`, body);
  }

  async submitAiDraftForParentApproval(objId: string): Promise<AICascadeDraft> {
    return this.request<AICascadeDraft>("POST", `/api/okrs/${objId}/submit-parent`);
  }

  async approveParentAiDraft(objId: string): Promise<AICascadeDraft> {
    return this.request<AICascadeDraft>("POST", `/api/okrs/${objId}/approve-parent`);
  }

  async rejectParentAiDraft(objId: string, reason: string): Promise<AICascadeDraft> {
    return this.request<AICascadeDraft>("POST", `/api/okrs/${objId}/reject-parent`, { reason });
  }

  async rejectAiDraft(objId: string, reason: string): Promise<AICascadeDraft> {
    return this.request<AICascadeDraft>("POST", `/api/okrs/${objId}/reject-ai`, { reason });
  }

  async regenerateAiDraft(objId: string): Promise<AICascadeDraft> {
    return this.request<AICascadeDraft>("POST", `/api/okrs/${objId}/regenerate`);
  }

  async triggerOkrCascade(objId: string): Promise<{ message: string; parent_id: string }> {
    return this.request("POST", `/api/okrs/${objId}/cascade`);
  }

  async getAiCascadeVersions(objId: string): Promise<AICascadeVersion[]> {
    return this.request<AICascadeVersion[]>("GET", `/api/okrs/${objId}/versions`);
  }

  async getAiAlignmentPreview(objId: string): Promise<AlignmentPreview> {
    return this.request<AlignmentPreview>("GET", `/api/okrs/${objId}/alignment-preview`);
  }

  async getAiCascadeDiff(objId: string, version?: number): Promise<{
    current: { title: string; description?: string; version?: number; key_results: unknown[] };
    previous: { title: string; description?: string; version: number; key_results: unknown[] };
    title_changed: boolean;
    description_changed: boolean;
  }> {
    return this.request("GET", `/api/okrs/${objId}/diff`, undefined, {
      params: version ? { version } : {},
    });
  }

  async getCascadeNotifications(unreadOnly = false): Promise<CascadeNotification[]> {
    return this.request<CascadeNotification[]>("GET", "/api/okrs/cascade-notifications", undefined, {
      params: unreadOnly ? { unread_only: true } : {},
    });
  }

  async markCascadeNotificationRead(notifId: string): Promise<{ id: string; is_read: boolean }> {
    return this.request("PATCH", `/api/okrs/cascade-notifications/${notifId}/read`);
  }

  async getMyApprovalQueue(params?: {
    stage?: "line" | "functional";
    subject?: "okr" | "progress" | "all";
  }): Promise<{ items: ApprovalQueueItem[]; count: number }> {
    return this.request("GET", "/api/approvals/my-queue", undefined, { params });
  }

  async getApprovalChain(
    subjectType: "OKR_CREATION" | "PROGRESS_SUBMISSION",
    subjectId: string,
  ): Promise<ApprovalChainStatus> {
    return this.request<ApprovalChainStatus>(
      "GET",
      `/api/approvals/chain/${subjectType}/${subjectId}`,
    );
  }

  async getAlignmentTree(plantId?: string, cycleId?: string): Promise<CascadeTreeNode[]> {
    const params: Record<string, string> = {};
    if (plantId) params.plant_id = plantId;
    if (cycleId) params.cycle_id = cycleId;
    return this.request<CascadeTreeNode[]>("GET", "/api/okrs/alignment-tree", undefined, {
      params: Object.keys(params).length ? params : undefined,
    });
  }

  async getProgressSummary(options?: {
    plantId?: string;
    cycleId?: string;
    year?: number;
    quarter?: string;
  }): Promise<ProgressSummary> {
    const params: Record<string, string | number> = {};
    if (options?.plantId) params.plant_id = options.plantId;
    if (options?.year != null) params.year = options.year;
    if (options?.quarter) params.quarter = options.quarter;
    else if (options?.cycleId) params.cycle_id = options.cycleId;
    return this.request<ProgressSummary>("GET", "/api/okrs/progress-summary", undefined, {
      params: Object.keys(params).length ? params : undefined,
    });
  }

  async getAllowedLevels(role?: string, userId?: string): Promise<AllowedLevelsResponse> {
    const params: Record<string, string> = {};
    if (role) params.role = role;
    if (userId) params.user_id = userId;
    return this.request<AllowedLevelsResponse>("GET", "/api/okrs/allowed-levels", undefined, {
      params: Object.keys(params).length ? params : undefined,
    });
  }

  async getParentOptions(level: string, plantId?: string, departmentId?: string, cycleId?: string): Promise<ParentOption[]> {
    const params: Record<string, string> = { level };
    if (plantId) params.plant_id = plantId;
    if (departmentId) params.department_id = departmentId;
    if (cycleId) params.cycle_id = cycleId;
    return this.request<ParentOption[]>("GET", "/api/okrs/parent-options", undefined, { params });
  }

  async getPendingValidations(plantId?: string, cycleId?: string): Promise<PendingValidation[]> {
    const params: Record<string, string> = {};
    if (plantId) params.plant_id = plantId;
    if (cycleId) params.cycle_id = cycleId;
    return this.request<PendingValidation[]>("GET", "/api/progress/pending", undefined, {
      params: Object.keys(params).length ? params : undefined,
    });
  }

  async getObjective(objId: string): Promise<Objective> {
    return this.request<Objective>("GET", `/api/okrs/${objId}`);
  }

  async updateObjective(objId: string, obj: ObjectiveCreate): Promise<Objective> {
    return this.request<Objective>("PUT", `/api/okrs/${objId}`, obj);
  }

  async patchObjectiveFunctionalParent(
    objId: string,
    body: ObjectiveFunctionalParentPatch,
  ): Promise<Objective> {
    return this.request<Objective>("PATCH", `/api/okrs/${objId}`, body);
  }

  async getCycles(status?: string): Promise<Cycle[]> {
    return this.request<Cycle[]>("GET", "/api/cycles", undefined, {
      params: status ? { status } : undefined,
    });
  }

  async createCycle(cycle: CycleCreate): Promise<Cycle> {
    return this.request<Cycle>("POST", "/api/cycles", cycle);
  }

  async freezeCycle(cycleId: string): Promise<{ status: string; cycle_status: string }> {
    return this.request<{ status: string; cycle_status: string }>("PATCH", `/api/cycles/${cycleId}/freeze`);
  }

  async closeCycle(cycleId: string): Promise<{ status: string; cycle_status: string }> {
    return this.request<{ status: string; cycle_status: string }>("PATCH", `/api/cycles/${cycleId}/close`);
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
    stage?: "line" | "functional";
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

  async getPerformanceReviewCycles(): Promise<Array<{
    id: string;
    name: string;
    cycle_type: string;
    status: string;
    start_date?: string;
    end_date?: string;
  }>> {
    return this.request("GET", "/api/reviews/performance-cycles");
  }

  async createPerformanceReviewCycle(
    cycle: ReviewCycleCreate & {
      start_date: string;
      end_date: string;
      submission_start: string;
      submission_end: string;
    }
  ): Promise<{ id: string; name: string }> {
    return this.request("POST", "/api/reviews/performance-cycles", cycle);
  }

  async initiatePerformanceReviewsBulk(cycleId: string): Promise<{ created: number }> {
    return this.request("POST", "/api/reviews/performance/initiate-bulk", { cycle_id: cycleId });
  }

  // ========================================================================
  // CONTINUOUS CHECK-IN ENDPOINTS
  // ========================================================================

  async submitCheckin(employeeId: string, checkin: ContinuousCheckinSubmit): Promise<ContinuousCheckin> {
    return this.request<ContinuousCheckin>("POST", "/api/reviews/checkins", {
      ...checkin,
      employee_id: employeeId,
    });
  }

  async getManagerCheckinInbox(includeResolved = false): Promise<ContinuousCheckin[]> {
    return this.request<ContinuousCheckin[]>("GET", "/api/reviews/checkins/inbox", undefined, {
      params: { include_resolved: includeResolved },
    });
  }

  async getEmployeeCheckinTimeline(employeeId: string, limit = 24): Promise<ContinuousCheckin[]> {
    return this.request<ContinuousCheckin[]>("GET", `/api/reviews/checkins/timeline/${employeeId}`, undefined, {
      params: { limit },
    });
  }

  async getCheckinDetail(checkinId: string): Promise<ContinuousCheckin> {
    return this.request<ContinuousCheckin>("GET", `/api/reviews/checkins/${checkinId}`);
  }

  async acknowledgeCheckin(checkinId: string): Promise<ContinuousCheckin> {
    return this.request<ContinuousCheckin>("POST", `/api/reviews/checkins/${checkinId}/acknowledge`);
  }

  async addCheckinComment(
    checkinId: string,
    comment: string,
    parentCommentId?: string
  ): Promise<ContinuousCheckin> {
    return this.request<ContinuousCheckin>("POST", `/api/reviews/checkins/${checkinId}/comments`, {
      comment,
      parent_comment_id: parentCommentId,
    });
  }

  async assignCheckinActionItems(
    checkinId: string,
    actionItems: Array<{ action: string; owner: string; due_date: string; status?: string }>,
    coachingNotes?: string
  ): Promise<ContinuousCheckin> {
    return this.request<ContinuousCheckin>("POST", `/api/reviews/checkins/${checkinId}/action-items`, {
      action_items: actionItems,
      coaching_notes: coachingNotes,
    });
  }

  async escalateCheckin(checkinId: string, reason: string, notes?: string): Promise<ContinuousCheckin> {
    return this.request<ContinuousCheckin>("POST", `/api/reviews/checkins/${checkinId}/escalate`, {
      reason,
      notes,
    });
  }

  async resolveCheckin(checkinId: string, resolutionNotes?: string): Promise<ContinuousCheckin> {
    return this.request<ContinuousCheckin>("POST", `/api/reviews/checkins/${checkinId}/resolve`, {
      resolution_notes: resolutionNotes,
    });
  }

  async approveCheckin(checkinId: string, approvalNotes?: string): Promise<ContinuousCheckin> {
    return this.request<ContinuousCheckin>("POST", `/api/reviews/checkins/${checkinId}/approve`, {
      approval_notes: approvalNotes,
    });
  }

  async submitDeptHeadModeration(
    reviewId: string,
    body: { moderation_notes?: string; endorse_manager_rating?: boolean }
  ): Promise<PerformanceReviewEnhanced> {
    return this.request<PerformanceReviewEnhanced>(
      "POST",
      `/api/reviews/performance/${reviewId}/dept-head-moderation`,
      body
    );
  }

  async getCheckin(checkinId: string): Promise<ContinuousCheckin> {
    return this.request<ContinuousCheckin>("GET", `/api/reviews/checkins/${checkinId}`);
  }

  async getEmployeeCheckins(employeeId: string, limit: number = 20, offset: number = 0): Promise<ContinuousCheckin[]> {
    return this.request<ContinuousCheckin[]>("GET", `/api/reviews/checkins/employee/${employeeId}`, undefined, {
      params: { limit, offset },
    });
  }

  async provideManagerCheckinResponse(checkinId: string, response: ManagerCheckinResponse): Promise<ContinuousCheckin> {
    return this.request<ContinuousCheckin>("POST", `/api/reviews/checkins/${checkinId}/manager-response`, response);
  }

  async getTeamCheckins(managerId: string, week?: number): Promise<ContinuousCheckin[]> {
    return this.request<ContinuousCheckin[]>("GET", `/api/reviews/checkins/manager/${managerId}`, undefined, {
      params: { ...(week ? { week } : {}) },
    });
  }

  // ========================================================================
  // ENHANCED PERFORMANCE REVIEW ENDPOINTS
  // ========================================================================

  async createPerformanceReview(employeeId: string, cycleId: string): Promise<PerformanceReviewEnhanced> {
    return this.request<PerformanceReviewEnhanced>("POST", "/api/reviews/performance", {
      employee_id: employeeId,
      cycle_id: cycleId,
    });
  }

  async getReviewableTeam(cycleId: string): Promise<ReviewableTeamMember[]> {
    return this.request<ReviewableTeamMember[]>("GET", "/api/reviews/performance/reviewable-team", undefined, {
      params: { cycle_id: cycleId },
    });
  }

  async initiateEmployeeReview(employeeId: string, cycleId: string): Promise<PerformanceReviewEnhanced> {
    return this.request<PerformanceReviewEnhanced>("POST", "/api/reviews/performance/initiate-for-employee", {
      employee_id: employeeId,
      cycle_id: cycleId,
    });
  }

  async initiateAndGenerateAIReview(
    employeeId: string,
    cycleId: string
  ): Promise<{ review: PerformanceReviewEnhanced; ai: AIReviewResponse }> {
    const review = await this.initiateEmployeeReview(employeeId, cycleId);
    const ai = await this.generateAIReview(review.id);
    return { review, ai };
  }

  async getPerformanceReviews(params?: {
    cycle_id?: string;
    status?: ReviewState;
    employee_id?: string;
  }): Promise<PerformanceReviewEnhanced[]> {
    return this.request<PerformanceReviewEnhanced[]>("GET", "/api/reviews/performance", undefined, { params });
  }

  async getPerformanceReview(reviewId: string): Promise<PerformanceReviewEnhanced> {
    return this.request<PerformanceReviewEnhanced>("GET", `/api/reviews/performance/${reviewId}`);
  }

  async submitSelfReviewEnhanced(reviewId: string, review: SelfReviewSubmitEnhanced): Promise<PerformanceReviewEnhanced> {
    return this.request<PerformanceReviewEnhanced>("POST", `/api/reviews/performance/${reviewId}/self-review`, review);
  }

  async submitManagerReviewEnhanced(reviewId: string, review: ManagerReviewSubmitEnhanced): Promise<PerformanceReviewEnhanced> {
    return this.request<PerformanceReviewEnhanced>("POST", `/api/reviews/performance/${reviewId}/manager-review`, review);
  }

  async getAIReviewContext(reviewId: string): Promise<Record<string, unknown>> {
    return this.request("GET", `/api/reviews/performance/${reviewId}/ai-review/context`);
  }

  async getAIReview(reviewId: string): Promise<AIReviewResponse> {
    return this.request<AIReviewResponse>("GET", `/api/reviews/performance/${reviewId}/ai-review`);
  }

  async generateAIReview(reviewId: string): Promise<AIReviewResponse> {
    return this.request<AIReviewResponse>("POST", `/api/reviews/performance/${reviewId}/ai-review/generate`);
  }

  async updateAIReview(reviewId: string, payload: Partial<AIReviewPayload>): Promise<AIReviewResponse> {
    return this.request<AIReviewResponse>("PUT", `/api/reviews/performance/${reviewId}/ai-review`, payload);
  }

  async submitAIReviewWithManager(
    reviewId: string,
    body: {
      behavioral_competency_scores?: Record<string, number>;
      manager_notes?: string;
      promotion_eligible?: boolean;
      attrition_risk?: string;
    }
  ): Promise<PerformanceReviewEnhanced> {
    return this.request<PerformanceReviewEnhanced>(
      "POST",
      `/api/reviews/performance/${reviewId}/ai-review/submit`,
      body
    );
  }

  async submitSkipLevelReviewEnhanced(reviewId: string, review: SkipLevelReviewSubmitEnhanced): Promise<PerformanceReviewEnhanced> {
    return this.request<PerformanceReviewEnhanced>("POST", `/api/reviews/performance/${reviewId}/skip-level-review`, review);
  }

  async finalizeReview(reviewId: string): Promise<PerformanceReviewEnhanced> {
    return this.request<PerformanceReviewEnhanced>("POST", `/api/reviews/performance/${reviewId}/finalize`);
  }

  async publishReview(reviewId: string): Promise<PerformanceReviewEnhanced> {
    return this.request<PerformanceReviewEnhanced>("POST", `/api/reviews/performance/${reviewId}/publish`);
  }

  async getReviewAuditTrail(reviewId: string): Promise<any[]> {
    return this.request<any[]>("GET", `/api/reviews/performance/${reviewId}/audit-trail`);
  }

  async getReviewCalculation(reviewId: string): Promise<ReviewCalculation> {
    return this.request<ReviewCalculation>("GET", `/api/reviews/performance/${reviewId}/calculation`);
  }

  // ========================================================================
  // 360 FEEDBACK ENDPOINTS
  // ========================================================================

  async getFeedbackTemplates(feedbackType?: FeedbackType): Promise<FeedbackTemplate[]> {
    return this.request<FeedbackTemplate[]>("GET", "/api/reviews/feedback-templates", undefined, {
      params: feedbackType ? { feedback_type: feedbackType } : undefined,
    });
  }

  async submitFeedbackResponse(feedback: FeedbackResponseSubmit): Promise<FeedbackResponse> {
    return this.request<FeedbackResponse>("POST", "/api/reviews/feedback-responses", feedback);
  }

  async getFeedbackResponses(reviewId: string): Promise<FeedbackResponse[]> {
    return this.request<FeedbackResponse[]>("GET", `/api/reviews/performance/${reviewId}/feedback-responses`);
  }

  async getFeedbackSynthesis(reviewId: string): Promise<FeedbackSynthesis> {
    return this.request<FeedbackSynthesis>("GET", `/api/reviews/performance/${reviewId}/feedback-synthesis`);
  }

  // ========================================================================
  // COMPETENCY FRAMEWORK ENDPOINTS
  // ========================================================================

  async getCompetencyFrameworks(roleType?: string): Promise<CompetencyFramework[]> {
    return this.request<CompetencyFramework[]>("GET", "/api/reviews/competency-frameworks", undefined, {
      params: roleType ? { role_type: roleType } : undefined,
    });
  }

  async getCompetencies(frameworkId: string): Promise<Competency[]> {
    return this.request<Competency[]>("GET", `/api/reviews/competency-frameworks/${frameworkId}/competencies`);
  }

  async submitCompetencyAssessment(reviewId: string, assessments: CompetencyAssessment[]): Promise<CompetencyAssessment[]> {
    return this.request<CompetencyAssessment[]>("POST", `/api/reviews/performance/${reviewId}/competency-assessments`, {
      assessments,
    });
  }

  // ========================================================================
  // REVIEW DASHBOARD ENDPOINTS
  // ========================================================================

  async getEmployeeReviewDashboard(employeeId?: string): Promise<any> {
    return this.request<any>("GET", "/api/reviews/dashboards/employee", undefined, {
      params: employeeId ? { employee_id: employeeId } : undefined,
    });
  }

  async getManagerReviewDashboard(managerId?: string): Promise<any> {
    return this.request<any>("GET", "/api/reviews/dashboards/manager", undefined, {
      params: managerId ? { manager_id: managerId } : undefined,
    });
  }

  async getDepartmentReviewDashboard(departmentId: string): Promise<any> {
    return this.request<any>("GET", `/api/reviews/dashboards/department/${departmentId}`);
  }

  async getOrganizationReviewDashboard(): Promise<any> {
    return this.request<any>("GET", "/api/reviews/dashboards/organization");
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
    // Fetch current user and org to get required query parameters
    const [user, org] = await Promise.all([this.getMe(), this.getOrg()]);
    
    const t = await this.request<OrgNode | { roots: OrgNode[] } | { error: string }>(
      "GET",
      "/api/org-tree",
      undefined,
      {
        params: {
          org_id: org.id,
          user_id: user.id,
        },
      }
    );
    if (t && typeof t === "object" && "error" in t && !("id" in t) && !("roots" in t)) {
      throw new Error(String((t as { error: string }).error));
    }
    return t as OrgNode | { roots: OrgNode[] };
  }

  async fetchOrgNode(nodeId: string): Promise<OrgNode> {
    const [user, org] = await Promise.all([this.getMe(), this.getOrg()]);
    
    return this.request<OrgNode>(
      "GET",
      `/api/org-tree/${nodeId}`,
      undefined,
      {
        params: {
          org_id: org.id,
          user_id: user.id,
        },
      }
    );
  }

  async createOrgNode(payload: OrgNodeCreateRequest): Promise<OrgNode> {
    const org = await this.getOrg();
    return this.request<OrgNode>("POST", "/api/org-tree", payload, {
      params: { org_id: org.id },
    });
  }

  async updateOrgNode(nodeId: string, payload: OrgNodeUpdateRequest): Promise<OrgNode> {
    const org = await this.getOrg();
    return this.request<OrgNode>("PATCH", `/api/org-tree/${nodeId}`, payload, {
      params: { org_id: org.id },
    });
  }

  async deleteOrgNode(nodeId: string): Promise<{ status: string; node_id: string }> {
    const org = await this.getOrg();
    return this.request<{ status: string; node_id: string }>("DELETE", `/api/org-tree/${nodeId}`, undefined, {
      params: { org_id: org.id },
    });
  }

  async createRegion(body: OrgTreeNamedNodeCreate): Promise<OrgNode> {
    const org = await this.getOrg();
    return this.request<OrgNode>("POST", "/api/org-tree/regions", body, {
      params: { org_id: org.id },
    });
  }

  async createCorporateFunction(body: OrgTreeNamedNodeCreate): Promise<OrgNode> {
    const org = await this.getOrg();
    return this.request<OrgNode>("POST", "/api/org-tree/corporate-functions", body, {
      params: { org_id: org.id },
    });
  }

  // ========================================================================
  // KR INGEST (Phase 8)
  // ========================================================================

  async getKrIngestSource(krId: string): Promise<{ configured: boolean; ingest_source?: KRIngestSourceInfo }> {
    return this.request("GET", `/api/okrs/key-results/${krId}/ingest-source`);
  }

  async configureKrIngestSource(
    krId: string,
    body: KRIngestSourceConfigure,
  ): Promise<{ configured: boolean; ingest_source: KRIngestSourceInfo; api_token?: string }> {
    return this.request("PUT", `/api/okrs/key-results/${krId}/ingest-source`, body);
  }

  // ========================================================================
  // HIERARCHICAL OKR MANAGEMENT
  // ========================================================================

  /**
   * Get all OKRs accessible to the current user based on their role and hierarchy
   */
  async getAccessibleOKRs(params?: {
    quarter?: number;
    year?: number;
    level_type?: string;
  }): Promise<any[]> {
    return this.request<any[]>("GET", "/api/v1/okrs/accessible", undefined, { params });
  }

  /**
   * Get all OKRs for a specific region (VP/Regional Head only)
   */
  async getRegionOKRs(regionId: string): Promise<any[]> {
    return this.request<any[]>("GET", `/api/v1/okrs/region/${regionId}`);
  }

  /**
   * Get all OKRs for a specific plant (Plant Head and above only)
   */
  async getPlantOKRs(plantId: string): Promise<any[]> {
    return this.request<any[]>("GET", `/api/v1/okrs/plant/${plantId}`);
  }

  /**
   * Get all OKRs for a specific department (Department Head and above only)
   */
  async getDepartmentOKRs(departmentId: string): Promise<any[]> {
    return this.request<any[]>("GET", `/api/v1/okrs/department/${departmentId}`);
  }

  /**
   * Submit OKR progress for approval
   */
  async submitOKRProgress(okrId: string, data: {
    comments?: string;
  }): Promise<any> {
    return this.request<any>("POST", `/api/v1/okrs/${okrId}/submit`, data);
  }

  /**
   * Get all OKR submissions pending approval for the current user
   */
  async getPendingOKRSubmissions(): Promise<any[]> {
    return this.request<any[]>("GET", "/api/v1/okrs/submissions/pending");
  }

  /**
   * Approve or reject an OKR submission
   */
  async approveOKRSubmission(okrId: string, data: {
    action: "approve" | "reject" | "request_revision" | "override";
    comments?: string;
  }): Promise<any> {
    return this.request<any>("POST", `/api/v1/okrs/${okrId}/approve`, data);
  }

  /**
   * Get approval history for an OKR
   */
  async getOKRApprovalHistory(okrId: string): Promise<any[]> {
    return this.request<any[]>("GET", `/api/v1/okrs/${okrId}/approvals`);
  }

}

// ============================================================================
// SINGLETON INSTANCE
// ============================================================================

export const api = new APIClient();
