/**
 * React Query Hooks
 * 
 * Custom hooks for data fetching using React Query + API client.
 * Provides automatic caching, refetching, and error handling.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  api,
  type Employee,
  type Objective,
  type Review,
  type ReviewCycle,
  type Organization,
  type Plant,
  type Department,
  type Team,
  type Designation,
  type DashboardResponse,
  type AuditLog,
  type DashboardModule,
  type Shift,
  type SystemRole,
  type ObjectiveLevel,
  type ReviewStatus,
  type OrgTreeNamedNodeCreate,
  type OrgNodeUpdateRequest,
} from "./api";

// ============================================================================
// ORGANIZATION HOOKS
// ============================================================================

export function useOrganization() {
  return useQuery({
    queryKey: ["organization"],
    queryFn: () => api.getOrg(),
  });
}

export function useUpdateOrganization() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ name, domain }: { name?: string; domain?: string }) =>
      api.updateOrg(name, domain),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["organization"] });
    },
  });
}

// ============================================================================
// PLANTS HOOKS
// ============================================================================

export function usePlants(plantId?: string) {
  return useQuery({
    queryKey: ["plants", plantId],
    queryFn: () => api.getPlants(plantId),
  });
}

export function useCreatePlant() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.createPlant.bind(api),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["plants"] });
      queryClient.invalidateQueries({ queryKey: ["org-tree"] });
    },
  });
}

// ============================================================================
// DEPARTMENTS HOOKS
// ============================================================================

export function useDepartments(plantId?: string) {
  return useQuery({
    queryKey: ["departments", plantId],
    queryFn: () => api.getDepartments(plantId),
  });
}

export function useCreateDepartment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.createDepartment.bind(api),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["departments"] });
    },
  });
}

// ============================================================================
// TEAMS HOOKS
// ============================================================================

export function useTeams(departmentId?: string) {
  return useQuery({
    queryKey: ["teams", departmentId],
    queryFn: () => api.getTeams(departmentId),
  });
}

export function useCreateTeam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.createTeam.bind(api),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["teams"] });
    },
  });
}

// ============================================================================
// SHIFTS HOOKS
// ============================================================================

export function useShifts(plantId?: string) {
  return useQuery({
    queryKey: ["shifts", plantId],
    queryFn: () => api.getShifts(plantId),
  });
}

// ============================================================================
// DESIGNATIONS HOOKS
// ============================================================================

export function useDesignations() {
  return useQuery({
    queryKey: ["designations"],
    queryFn: () => api.getDesignations(),
  });
}

// ============================================================================
// EMPLOYEE HOOKS
// ============================================================================

export function useEmployees(params?: {
  search?: string;
  plant_id?: string;
  department_id?: string;
  team_id?: string;
  system_role?: SystemRole;
  is_active?: boolean;
}) {
  return useQuery({
    queryKey: ["employees", params],
    queryFn: () => api.getEmployees(params),
  });
}

export function useEmployee(uid: string) {
  return useQuery({
    queryKey: ["employees", uid],
    queryFn: () => api.getEmployee(uid),
    enabled: !!uid,
  });
}

export function useCreateEmployee() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.createEmployee.bind(api),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["employees"] });
    },
  });
}

export function useUpdateEmployee(uid: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.updateEmployee.bind(api, uid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["employees"] });
      queryClient.invalidateQueries({ queryKey: ["employees", uid] });
    },
  });
}

export function useDeleteEmployee() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.deleteEmployee.bind(api),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["employees"] });
    },
  });
}

export function useOrgChart() {
  return useQuery({
    queryKey: ["org-chart"],
    queryFn: () => api.getOrgChart(),
  });
}

// ============================================================================
// ORG TREE (OrgNode)
// ============================================================================

export function useOrgTree(enabled = true) {
  return useQuery({
    queryKey: ["org-tree"],
    queryFn: () => api.fetchOrgTree(),
    enabled,
  });
}

export function useOrgNodeDetail(nodeId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ["org-node", nodeId],
    queryFn: () => api.fetchOrgNode(nodeId!),
    enabled: !!nodeId && enabled,
  });
}

export function useCreateRegion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: OrgTreeNamedNodeCreate) => api.createRegion(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org-tree"] });
    },
  });
}

export function useCreateCorporateFunction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: OrgTreeNamedNodeCreate) => api.createCorporateFunction(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org-tree"] });
    },
  });
}

export function useUpdateOrgNode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: OrgNodeUpdateRequest }) =>
      api.updateOrgNode(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org-tree"] });
      queryClient.invalidateQueries({ queryKey: ["org-node"] });
    },
  });
}

export function useDeleteOrgNode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteOrgNode(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org-tree"] });
      queryClient.invalidateQueries({ queryKey: ["org-node"] });
    },
  });
}

// ============================================================================
// HIERARCHY HOOKS
// ============================================================================

export function useReportingChain(uid: string) {
  return useQuery({
    queryKey: ["reporting-chain", uid],
    queryFn: () => api.getReportingChain(uid),
    enabled: !!uid,
  });
}

export function useDirectReports(uid: string) {
  return useQuery({
    queryKey: ["direct-reports", uid],
    queryFn: () => api.getDirectReports(uid),
    enabled: !!uid,
  });
}

// ============================================================================
// OKR HOOKS
// ============================================================================

export function useVisibilityScope() {
  return useQuery({
    queryKey: ["okr-visibility-scope"],
    queryFn: () => api.getVisibilityScope(),
    staleTime: 60_000,
  });
}

export function useObjectives(params?: {
  owner_id?: string;
  level?: ObjectiveLevel;
  cycle_id?: string;
  year?: number;
  quarter?: string;
  plant_id?: string;
  department_id?: string;
  team_id?: string;
  parent_id?: string;
}) {
  return useQuery({
    queryKey: ["objectives", params],
    queryFn: () => api.getObjectives(params),
  });
}

export function useMyObjectives() {
  return useQuery({
    queryKey: ["my-objectives"],
    queryFn: () => api.getMyObjectives(),
  });
}

export function useObjective(objId: string) {
  return useQuery({
    queryKey: ["objectives", objId],
    queryFn: () => api.getObjective(objId),
    enabled: !!objId,
  });
}

export function useAlignmentTree(plantId?: string, cycleId?: string) {
  return useQuery({
    queryKey: ["alignment-tree", plantId, cycleId],
    queryFn: () => api.getAlignmentTree(plantId, cycleId),
  });
}

export function useProgressSummary(options?: {
  plantId?: string;
  cycleId?: string;
  year?: number;
  quarter?: string;
}) {
  return useQuery({
    queryKey: ["progress-summary", options],
    queryFn: () => api.getProgressSummary(options),
  });
}

export function useAllowedLevels(role?: string, userId?: string) {
  return useQuery({
    queryKey: ["allowed-levels", role, userId],
    queryFn: () => api.getAllowedLevels(role, userId),
    enabled: !!role && !!userId,
  });
}

export function useParentOptions(level: string, plantId?: string, departmentId?: string, cycleId?: string) {
  return useQuery({
    queryKey: ["parent-options", level, plantId, departmentId, cycleId],
    queryFn: () => api.getParentOptions(level, plantId, departmentId, cycleId),
    enabled: !!level,
  });
}

export function usePendingValidations(plantId?: string, cycleId?: string) {
  return useQuery({
    queryKey: ["pending-validations", plantId, cycleId],
    queryFn: () => api.getPendingValidations(plantId, cycleId),
  });
}

export function useCreateObjective() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.createObjective.bind(api),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["objectives"] });
      queryClient.invalidateQueries({ queryKey: ["my-objectives"] });
      queryClient.invalidateQueries({ queryKey: ["alignment-tree"] });
      queryClient.invalidateQueries({ queryKey: ["progress-summary"] });
    },
  });
}

export function useUpdateObjective(objId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.updateObjective.bind(api, objId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["objectives"] });
      queryClient.invalidateQueries({ queryKey: ["objectives", objId] });
      queryClient.invalidateQueries({ queryKey: ["alignment-tree"] });
      queryClient.invalidateQueries({ queryKey: ["progress-summary"] });
    },
  });
}

export function useDeleteObjective() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.deleteObjective.bind(api),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["objectives"] });
      queryClient.invalidateQueries({ queryKey: ["my-objectives"] });
      queryClient.invalidateQueries({ queryKey: ["alignment-tree"] });
      queryClient.invalidateQueries({ queryKey: ["progress-summary"] });
    },
  });
}

export function useCreateKeyResult(objId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (kr: { title: string; target_value: number; unit: string; weight?: number }) =>
      api.createKeyResult(objId, kr),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["objectives"] });
      queryClient.invalidateQueries({ queryKey: ["objectives", objId] });
      queryClient.invalidateQueries({ queryKey: ["progress-summary"] });
    },
  });
}

export function useSubmitProgress(krId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (update: { new_value: number; notes?: string; blockers?: string; evidence_url?: string }) =>
      api.submitProgressUpdate(krId, update),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["objectives"] });
      queryClient.invalidateQueries({ queryKey: ["pending-validations"] });
      queryClient.invalidateQueries({ queryKey: ["progress-summary"] });
    },
  });
}

export function useValidateProgress() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      updateId,
      validation,
    }: {
      updateId: string;
      validation: import("@/lib/api").ProgressValidation;
    }) => api.validateProgress(updateId, validation),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["objectives"] });
      queryClient.invalidateQueries({ queryKey: ["pending-validations"] });
      queryClient.invalidateQueries({ queryKey: ["progress-summary"] });
      queryClient.invalidateQueries({ queryKey: ["alignment-tree"] });
    },
  });
}

// ============================================================================
// REVIEW HOOKS
// ============================================================================

export function useReviewCycles() {
  return useQuery({
    queryKey: ["review-cycles"],
    queryFn: () => api.getReviewCycles(),
  });
}

export function useCreateReviewCycle() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.createReviewCycle.bind(api),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["review-cycles"] });
    },
  });
}

export function useReviews(params?: {
  cycle_id?: string;
  status?: ReviewStatus;
}) {
  return useQuery({
    queryKey: ["reviews", params],
    queryFn: () => api.getReviews(params),
  });
}

export function useReview(reviewId: string) {
  return useQuery({
    queryKey: ["reviews", reviewId],
    queryFn: () => api.getReview(reviewId),
    enabled: !!reviewId,
  });
}

// ============================================================================
// CONTINUOUS CHECK-IN HOOKS
// ============================================================================

export function useSubmitCheckin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ employeeId, checkin }: { employeeId: string; checkin: any }) =>
      api.submitCheckin(employeeId, checkin),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["checkins"] });
    },
  });
}

export function useCheckin(checkinId: string) {
  return useQuery({
    queryKey: ["checkins", checkinId],
    queryFn: () => api.getCheckin(checkinId),
    enabled: !!checkinId,
  });
}

export function useEmployeeCheckins(employeeId: string, limit?: number, offset?: number) {
  return useQuery({
    queryKey: ["employee-checkins", employeeId, limit, offset],
    queryFn: () => api.getEmployeeCheckins(employeeId, limit, offset),
    enabled: !!employeeId,
  });
}

export function useProvideManagerCheckinResponse() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ checkinId, response }: { checkinId: string; response: any }) =>
      api.provideManagerCheckinResponse(checkinId, response),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["checkins"] });
    },
  });
}

export function useTeamCheckins(managerId: string, week?: number) {
  return useQuery({
    queryKey: ["team-checkins", managerId, week],
    queryFn: () => api.getTeamCheckins(managerId, week),
    enabled: !!managerId,
  });
}

// ============================================================================
// ENHANCED PERFORMANCE REVIEW HOOKS
// ============================================================================

export function useCreatePerformanceReview() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ employeeId, cycleId }: { employeeId: string; cycleId: string }) =>
      api.createPerformanceReview(employeeId, cycleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reviews"] });
    },
  });
}

export function usePerformanceReviews(params?: any) {
  return useQuery({
    queryKey: ["performance-reviews", params],
    queryFn: () => api.getPerformanceReviews(params),
  });
}

export function usePerformanceReview(reviewId: string) {
  return useQuery({
    queryKey: ["performance-reviews", reviewId],
    queryFn: () => api.getPerformanceReview(reviewId),
    enabled: !!reviewId,
  });
}

export function useSubmitSelfReviewEnhanced() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ reviewId, review }: { reviewId: string; review: any }) =>
      api.submitSelfReviewEnhanced(reviewId, review),
    onSuccess: (_, { reviewId }) => {
      queryClient.invalidateQueries({ queryKey: ["performance-reviews", reviewId] });
    },
  });
}

export function useSubmitManagerReviewEnhanced() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ reviewId, review }: { reviewId: string; review: any }) =>
      api.submitManagerReviewEnhanced(reviewId, review),
    onSuccess: (_, { reviewId }) => {
      queryClient.invalidateQueries({ queryKey: ["performance-reviews", reviewId] });
    },
  });
}

export function useSubmitSkipLevelReviewEnhanced() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ reviewId, review }: { reviewId: string; review: any }) =>
      api.submitSkipLevelReviewEnhanced(reviewId, review),
    onSuccess: (_, { reviewId }) => {
      queryClient.invalidateQueries({ queryKey: ["performance-reviews", reviewId] });
    },
  });
}

export function useFinalizeReview() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (reviewId: string) => api.finalizeReview(reviewId),
    onSuccess: (_, reviewId) => {
      queryClient.invalidateQueries({ queryKey: ["performance-reviews", reviewId] });
    },
  });
}

export function usePublishReview() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (reviewId: string) => api.publishReview(reviewId),
    onSuccess: (_, reviewId) => {
      queryClient.invalidateQueries({ queryKey: ["performance-reviews", reviewId] });
    },
  });
}

export function useReviewAuditTrail(reviewId: string) {
  return useQuery({
    queryKey: ["review-audit-trail", reviewId],
    queryFn: () => api.getReviewAuditTrail(reviewId),
    enabled: !!reviewId,
  });
}

export function useReviewCalculation(reviewId: string) {
  return useQuery({
    queryKey: ["review-calculation", reviewId],
    queryFn: () => api.getReviewCalculation(reviewId),
    enabled: !!reviewId,
  });
}

// ============================================================================
// 360 FEEDBACK HOOKS
// ============================================================================

export function useFeedbackTemplates(feedbackType?: any) {
  return useQuery({
    queryKey: ["feedback-templates", feedbackType],
    queryFn: () => api.getFeedbackTemplates(feedbackType),
  });
}

export function useSubmitFeedbackResponse() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (feedback: any) => api.submitFeedbackResponse(feedback),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["feedback-responses"] });
    },
  });
}

export function useFeedbackResponses(reviewId: string) {
  return useQuery({
    queryKey: ["feedback-responses", reviewId],
    queryFn: () => api.getFeedbackResponses(reviewId),
    enabled: !!reviewId,
  });
}

export function useFeedbackSynthesis(reviewId: string) {
  return useQuery({
    queryKey: ["feedback-synthesis", reviewId],
    queryFn: () => api.getFeedbackSynthesis(reviewId),
    enabled: !!reviewId,
  });
}

// ============================================================================
// COMPETENCY FRAMEWORK HOOKS
// ============================================================================

export function useCompetencyFrameworks(roleType?: string) {
  return useQuery({
    queryKey: ["competency-frameworks", roleType],
    queryFn: () => api.getCompetencyFrameworks(roleType),
  });
}

export function useCompetencies(frameworkId: string) {
  return useQuery({
    queryKey: ["competencies", frameworkId],
    queryFn: () => api.getCompetencies(frameworkId),
    enabled: !!frameworkId,
  });
}

export function useSubmitCompetencyAssessment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ reviewId, assessments }: { reviewId: string; assessments: any[] }) =>
      api.submitCompetencyAssessment(reviewId, assessments),
    onSuccess: (_, { reviewId }) => {
      queryClient.invalidateQueries({ queryKey: ["performance-reviews", reviewId] });
    },
  });
}

// ============================================================================
// REVIEW DASHBOARD HOOKS
// ============================================================================

export function useEmployeeReviewDashboard(employeeId?: string) {
  return useQuery({
    queryKey: ["employee-review-dashboard", employeeId],
    queryFn: () => api.getEmployeeReviewDashboard(employeeId),
  });
}

export function useManagerReviewDashboard(managerId?: string) {
  return useQuery({
    queryKey: ["manager-review-dashboard", managerId],
    queryFn: () => api.getManagerReviewDashboard(managerId),
  });
}

export function useDepartmentReviewDashboard(departmentId: string) {
  return useQuery({
    queryKey: ["department-review-dashboard", departmentId],
    queryFn: () => api.getDepartmentReviewDashboard(departmentId),
    enabled: !!departmentId,
  });
}

export function useOrganizationReviewDashboard() {
  return useQuery({
    queryKey: ["organization-review-dashboard"],
    queryFn: () => api.getOrganizationReviewDashboard(),
  });
}

// ============================================================================
// DASHBOARD HOOKS
// ============================================================================

export function useDashboard() {
  return useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api.getDashboard(),
  });
}

export function useAuditLog(limit: number = 50) {
  return useQuery({
    queryKey: ["audit-log", limit],
    queryFn: () => api.getAuditLog(limit),
  });
}

// ============================================================================
// PERMISSIONS HOOKS
// ============================================================================

export function useDashboardModules() {
  return useQuery({
    queryKey: ["dashboard-modules"],
    queryFn: () => api.getDashboardModules(),
  });
}

export function useMyModules() {
  return useQuery({
    queryKey: ["my-modules"],
    queryFn: () => api.getMyModules(),
  });
}
