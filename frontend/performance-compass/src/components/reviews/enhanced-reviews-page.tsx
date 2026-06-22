import { useEffect, useState } from "react";
import {
  usePerformanceReviews,
  usePerformanceReview,
  useReviewCalculation,
  useFinalizeReview,
} from "@/lib/hooks";
import { useAuthStore } from "@/lib/stores/auth-store";
import { api } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  AlertCircle,
  Loader2,
  CheckCircle2,
  Clock,
  User,
  Target,
  FileText,
  BarChart3,
  Bot,
} from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ContinuousCheckinForm } from "./continuous-checkin-form";
import { CheckinManagerInbox } from "./checkin-manager-inbox";
import { CheckinEmployeeTimeline } from "./checkin-employee-timeline";
import { SelfReviewForm } from "./self-review-form";
import { ReviewAgentPanel } from "./review-agent-panel";
import { ManagerTeamReviewHub } from "./manager-team-review-hub";
import { EmployeePerformanceNarrative } from "./employee-performance-narrative";
import { ReviewScoringVisualization } from "./scoring-visualization";

type ReviewWithContext = {
  okr_context?: Array<{ id: string; title: string; progress: number; level?: string }>;
};

function viewToTab(view?: string): string {
  switch (view) {
    case "checkins":
    case "checkin":
      return "checkins";
    case "timeline":
      return "timeline";
    case "reviews":
    case "my":
    case "status":
      return "reviews";
    case "detail":
      return "detail";
    case "scores":
      return "scores";
    case "inbox":
      return "inbox";
    case "queue":
      return "inbox";
    case "department":
      return "reviews";
    default:
      return "checkins";
  }
}

function formatScore(value: number | null | undefined, suffix = ""): string | null {
  if (value == null || Number.isNaN(value)) return null;
  return `${value.toFixed(1)}${suffix}`;
}

interface EnhancedReviewsPageProps {
  initialView?: string;
}

export function EnhancedReviewsPage({ initialView }: EnhancedReviewsPageProps) {
  const { user } = useAuthStore();
  const { data: reviews, isLoading, error } = usePerformanceReviews();
  const [selectedReviewId, setSelectedReviewId] = useState<string>();
  const [activeTab, setActiveTab] = useState(() => viewToTab(initialView));
  const { data: selectedReview } = usePerformanceReview(selectedReviewId || "");
  const { data: calculation } = useReviewCalculation(selectedReviewId || "");
  const finalizeReview = useFinalizeReview();
  const queryClient = useQueryClient();
  const reviewDetail = selectedReview as (typeof selectedReview & ReviewWithContext) | undefined;
  const isManagerRole =
    user?.system_role &&
    ["MANAGER", "TEAM_LEAD", "SUPERVISOR", "DEPT_HEAD", "PLANT_HEAD", "HR_HEAD", "SUPER_ADMIN"].includes(
      user.system_role
    );
  const isDeptHeadRole = user?.system_role === "DEPT_HEAD";
  const isManagerOfSelected =
    !!user?.id &&
    !!selectedReview &&
    selectedReview.employee_id !== user.id &&
    (selectedReview.manager_id === user.id || isManagerRole);
  const canRunReviewAgent =
    isManagerOfSelected &&
    selectedReview &&
    ["DRAFT", "SELF_SUBMITTED"].includes(selectedReview.current_state) &&
    (selectedReview.ai_review_status || "NONE") !== "SUBMITTED";
  const isDeptHeadOfSelected =
    !!user?.id && (selectedReview as { dept_head_reviewer_id?: string })?.dept_head_reviewer_id === user.id;
  const okrOptions =
    reviewDetail?.okr_context?.map((o) => ({ id: o.id, title: o.title })) ||
    selectedReview?.okr_ids?.map((id) => ({ id, title: `OKR ${id}` })) ||
    [];

  const managerQueueReviews =
    reviews?.filter(
      (r) =>
        r.current_state === "SELF_SUBMITTED" &&
        r.employee_id !== user?.id &&
        isManagerRole
    ) ?? [];

  const deptModerationQueue =
    reviews?.filter(
      (r) =>
        r.dept_head_reviewer_id === user?.id &&
        r.current_state === "DEPT_HEAD_MODERATION"
    ) ?? [];

  const displayedReviews = (() => {
    if (!reviews) return [];
    let list = [...reviews];
    if (initialView === "department" && isDeptHeadRole) {
      list = list.filter((r) => r.dept_head_reviewer_id === user?.id);
    }
    return list.sort((a, b) => {
      if (isDeptHeadRole) {
        const aMod = a.current_state === "DEPT_HEAD_MODERATION";
        const bMod = b.current_state === "DEPT_HEAD_MODERATION";
        if (aMod !== bMod) return aMod ? -1 : 1;
      }
      if (isManagerRole) {
        const aReady = a.manager_id === user?.id && a.current_state === "SELF_SUBMITTED";
        const bReady = b.manager_id === user?.id && b.current_state === "SELF_SUBMITTED";
        if (aReady !== bReady) return aReady ? -1 : 1;
      }
      return 0;
    });
  })();

  useEffect(() => {
    const tab = viewToTab(initialView);
    if (tab === "inbox" && !isManagerRole) {
      setActiveTab("reviews");
    } else {
      setActiveTab(tab);
    }
  }, [initialView, isManagerRole]);

  useEffect(() => {
    if ((activeTab === "detail" || activeTab === "scores") && !selectedReviewId) {
      setActiveTab("reviews");
    }
  }, [activeTab, selectedReviewId]);

  const handleSelectReview = (reviewId: string) => {
    setSelectedReviewId(reviewId);
    setActiveTab("detail");
  };

  const stateConfig: Record<string, { color: string; icon: React.ComponentType<{ className?: string }>; label: string }> = {
    DRAFT: {
      color: "bg-slate-100 text-slate-800 border-slate-200",
      icon: FileText,
      label: "Draft",
    },
    SELF_SUBMITTED: {
      color: "bg-blue-100 text-blue-800 border-blue-200",
      icon: User,
      label: "Self-Review Submitted",
    },
    MANAGER_REVIEW: {
      color: "bg-yellow-100 text-yellow-800 border-yellow-200",
      icon: Clock,
      label: "Manager Review In Progress",
    },
    DEPT_HEAD_MODERATION: {
      color: "bg-indigo-100 text-indigo-800 border-indigo-200",
      icon: Target,
      label: "Dept Head Moderation",
    },
    HR_CALIBRATION: {
      color: "bg-purple-100 text-purple-800 border-purple-200",
      icon: Target,
      label: "HR Calibration",
    },
    FINALIZED: {
      color: "bg-amber-100 text-amber-800 border-amber-200",
      icon: CheckCircle2,
      label: "Finalized",
    },
    PUBLISHED: {
      color: "bg-green-100 text-green-800 border-green-200",
      icon: CheckCircle2,
      label: "Published",
    },
    LOCKED: {
      color: "bg-gray-100 text-gray-800 border-gray-200",
      icon: CheckCircle2,
      label: "Locked",
    },
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-muted-foreground" />
          <p className="mt-2 text-sm text-muted-foreground">Loading reviews...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <div>
          <h2 className="text-2xl font-semibold">Performance Reviews</h2>
          <p className="text-sm text-muted-foreground">Manage your performance reviews and check-ins</p>
        </div>
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {error instanceof Error ? error.message : "Failed to load reviews"}
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold">Performance Reviews</h2>
        <p className="text-sm text-muted-foreground">
          {displayedReviews.length} review{displayedReviews.length !== 1 ? "s" : ""}{" "}
          {initialView === "department" && isDeptHeadRole
            ? "in your department moderation scope"
            : "in your cycle"}
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className={`grid w-full ${isManagerRole ? "grid-cols-3 md:grid-cols-6" : "grid-cols-2 md:grid-cols-5"}`}>
          <TabsTrigger value="checkins">Submit Check-In</TabsTrigger>
          {isManagerRole && <TabsTrigger value="inbox">Team Inbox</TabsTrigger>}
          <TabsTrigger value="timeline">My Timeline</TabsTrigger>
          <TabsTrigger value="reviews">Quarterly Reviews</TabsTrigger>
          <TabsTrigger value="detail" disabled={!selectedReviewId}>
            Details
          </TabsTrigger>
          <TabsTrigger value="scores" disabled={!selectedReviewId}>
            Scores
          </TabsTrigger>
        </TabsList>

        <TabsContent value="checkins" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Weekly Check-In & 1:1 Coaching</CardTitle>
              <CardDescription>
                Share wins, blockers, and mood with your direct manager for weekly coaching (not CEO/Regional chain).
              </CardDescription>
            </CardHeader>
            <CardContent>
              {user?.id ? (
                <ContinuousCheckinForm employeeId={user.id} />
              ) : (
                <p className="text-sm text-muted-foreground">Sign in to submit check-ins.</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {isManagerRole && (
          <TabsContent value="inbox">
            <CheckinManagerInbox />
          </TabsContent>
        )}

        <TabsContent value="timeline">
          {user?.id ? (
            <CheckinEmployeeTimeline employeeId={user.id} />
          ) : (
            <p className="text-sm text-muted-foreground">Sign in to view timeline.</p>
          )}
        </TabsContent>

        {/* Reviews Tab */}
        <TabsContent value="reviews" className="space-y-4">
          {isDeptHeadRole && deptModerationQueue.length > 0 && (
            <Alert className="border-indigo-200 bg-indigo-50">
              <User className="h-4 w-4 text-indigo-700" />
              <AlertDescription className="text-indigo-900">
                <strong>{deptModerationQueue.length}</strong> manager-submitted performance review
                {deptModerationQueue.length !== 1 ? "s" : ""} awaiting your{" "}
                <strong>verification and approval</strong>. Open each review in Details to moderate.
              </AlertDescription>
            </Alert>
          )}

          {isManagerRole && (
            <ManagerTeamReviewHub
              onOpenReview={(reviewId) => {
                setSelectedReviewId(reviewId);
                setActiveTab("detail");
              }}
            />
          )}

          {isManagerRole && managerQueueReviews.length > 0 && (
            <Alert className="border-amber-200 bg-amber-50">
              <Bot className="h-4 w-4 text-amber-700" />
              <AlertDescription className="text-amber-900">
                <strong>{managerQueueReviews.length}</strong> self-review
                {managerQueueReviews.length !== 1 ? "s" : ""} ready for the{" "}
                <strong>Review AI Agent</strong>. Open a review with status{" "}
                <strong>Self-Review Submitted</strong> (not Draft).
              </AlertDescription>
            </Alert>
          )}
          {isDeptHeadRole && deptModerationQueue.length > 0 && (
            <Alert className="border-indigo-200 bg-indigo-50">
              <User className="h-4 w-4 text-indigo-700" />
              <AlertDescription className="text-indigo-900">
                <strong>{deptModerationQueue.length}</strong> review
                {deptModerationQueue.length !== 1 ? "s" : ""} awaiting your{" "}
                <strong>promotion moderation</strong> (manager submitted with AI narrative).
              </AlertDescription>
            </Alert>
          )}
          {isDeptHeadRole && displayedReviews.length > 0 && deptModerationQueue.length === 0 && (
            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                No reviews pending moderation yet. Employees must complete self-review, then
                managers must run the Review AI Agent and submit — then they appear here as{" "}
                <strong>Dept Head Moderation</strong>.
              </AlertDescription>
            </Alert>
          )}
          {displayedReviews.length > 0 ? (
            <div className="space-y-2">
              <h3 className="text-sm font-semibold text-muted-foreground">Existing reviews</h3>
              <div className="grid gap-4">
              {displayedReviews.map((review) => {
                const config = stateConfig[review.current_state] || stateConfig.DRAFT;
                const Icon = config.icon;

                return (
                  <Card
                    key={review.id}
                    className={`cursor-pointer transition-all hover:shadow-md ${
                      selectedReviewId === review.id ? "ring-2 ring-primary" : ""
                    }`}
                    onClick={() => handleSelectReview(review.id)}
                  >
                    <CardContent className="pt-6">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-2">
                            <h3 className="text-lg font-semibold truncate">
                              {review.employee_name || "Unknown"}
                            </h3>
                            <Badge variant="outline">{review.cycle_name}</Badge>
                            {isManagerRole &&
                              review.manager_id === user?.id &&
                              review.current_state === "SELF_SUBMITTED" && (
                              <Badge className="bg-amber-100 text-amber-900 border-amber-300">
                                <Bot className="h-3 w-3 mr-1" />
                                AI Review Ready
                              </Badge>
                            )}
                            {isDeptHeadRole &&
                              review.dept_head_reviewer_id === user?.id &&
                              review.current_state === "DEPT_HEAD_MODERATION" && (
                              <Badge className="bg-indigo-100 text-indigo-900 border-indigo-300">
                                Awaiting moderation
                              </Badge>
                            )}
                          </div>
                          <p className="text-sm text-muted-foreground mb-3">
                            Manager: {review.manager_name || "Unassigned"}
                          </p>
                          <div className="flex flex-wrap gap-2">
                            {formatScore(review.final_score) && (
                              <div className="px-3 py-1 bg-slate-100 rounded text-sm font-medium">
                                Score: {formatScore(review.final_score)}/100
                              </div>
                            )}
                            {review.final_rating && (
                              <Badge variant="secondary">
                                {review.final_rating.replace(/_/g, " ")}
                              </Badge>
                            )}
                          </div>
                        </div>
                        <div className="text-right flex-shrink-0">
                          <div className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg border ${config.color}`}>
                            <Icon className="h-4 w-4" />
                            <span className="text-sm font-medium">{config.label}</span>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
              </div>
            </div>
          ) : !isManagerRole ? (
            <Card>
              <CardContent className="pt-6">
                <p className="text-center text-muted-foreground">No reviews available</p>
              </CardContent>
            </Card>
          ) : null}
        </TabsContent>

        {/* Detail Tab */}
        {selectedReview && (
          <TabsContent value="detail" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Review Details: {selectedReview.employee_name}</CardTitle>
                <CardDescription>
                  Cycle: {selectedReview.cycle_name} | Status: {selectedReview.current_state}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Review State */}
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <p className="text-sm text-muted-foreground">Current State</p>
                    <Badge>{selectedReview.current_state.replace(/_/g, " ")}</Badge>
                  </div>
                  {formatScore(selectedReview.final_score) && (
                    <div>
                      <p className="text-sm text-muted-foreground">Final Score</p>
                      <p className="text-2xl font-bold">{formatScore(selectedReview.final_score)}</p>
                    </div>
                  )}
                  {selectedReview.final_rating && (
                    <div>
                      <p className="text-sm text-muted-foreground">Rating</p>
                      <Badge variant="secondary">
                        {selectedReview.final_rating.replace(/_/g, " ")}
                      </Badge>
                    </div>
                  )}
                </div>

                {/* Self-Review Form */}
                {selectedReview.current_state === "DRAFT" &&
                  user?.id === selectedReview.employee_id && (
                  <SelfReviewForm
                    reviewId={selectedReview.id}
                    okrs={okrOptions}
                  />
                )}

                {canRunReviewAgent && (
                  <ReviewAgentPanel
                    reviewId={selectedReview.id}
                    employeeName={selectedReview.employee_name}
                    deptHeadName={(selectedReview as { dept_head_name?: string }).dept_head_name}
                    requiresDeptModeration={selectedReview.requires_dept_moderation}
                    managerInitiated={selectedReview.current_state === "DRAFT"}
                  />
                )}

                {isManagerOfSelected &&
                  selectedReview.employee_performance_narrative &&
                  (selectedReview.ai_review_status || "NONE") === "SUBMITTED" &&
                  !["DEPT_HEAD_MODERATION"].includes(selectedReview.current_state) && (
                  <>
                    <Alert className="border-green-200 bg-green-50">
                      <CheckCircle2 className="h-4 w-4 text-green-700" />
                      <AlertDescription className="text-green-900">
                        You already submitted this review with the AI agent. The narrative was shared
                        with the employee
                        {selectedReview.requires_dept_moderation ? " and department head" : ""}.
                      </AlertDescription>
                    </Alert>
                    <EmployeePerformanceNarrative
                      narrative={selectedReview.employee_performance_narrative}
                      promotionRecommendation={selectedReview.promotion_recommendation}
                      promotionRationale={selectedReview.promotion_rationale}
                      cycleName={selectedReview.cycle_name}
                      sharedAt={selectedReview.shared_with_employee_at}
                    />
                  </>
                )}

                {selectedReview.shared_with_employee_at &&
                  user?.id === selectedReview.employee_id &&
                  selectedReview.current_state !== "DRAFT" && (
                  <EmployeePerformanceNarrative
                    narrative={selectedReview.employee_performance_narrative}
                    promotionRecommendation={selectedReview.promotion_recommendation}
                    promotionRationale={selectedReview.promotion_rationale}
                    cycleName={selectedReview.cycle_name}
                    sharedAt={selectedReview.shared_with_employee_at}
                  />
                )}

                {selectedReview.current_state === "DEPT_HEAD_MODERATION" && isDeptHeadOfSelected && (
                  <div className="space-y-4">
                    <EmployeePerformanceNarrative
                      narrative={selectedReview.employee_performance_narrative}
                      promotionRecommendation={selectedReview.promotion_recommendation}
                      promotionRationale={selectedReview.promotion_rationale}
                      cycleName={selectedReview.cycle_name}
                      sharedAt={selectedReview.submitted_to_dept_head_at}
                    />
                    <Button
                      onClick={() =>
                        api
                          .submitDeptHeadModeration(selectedReview.id, {
                            moderation_notes: "Department head moderation complete — promotion pipeline reviewed",
                          })
                          .then(() => {
                            queryClient.invalidateQueries({ queryKey: ["performance-reviews"] });
                          })
                      }
                    >
                      Approve & forward to HR calibration
                    </Button>
                  </div>
                )}

                {selectedReview.current_state === "HR_CALIBRATION" &&
                  (isManagerOfSelected || user?.system_role === "HR_HEAD" || user?.system_role === "SUPER_ADMIN") && (
                  <div className="pt-2">
                    <Button
                      onClick={() => finalizeReview.mutate(selectedReview.id)}
                      disabled={finalizeReview.isPending}
                    >
                      {finalizeReview.isPending ? "Finalizing..." : "Finalize & calculate score"}
                    </Button>
                  </div>
                )}

                {/* Key Information */}
                <div className="grid grid-cols-2 gap-4 p-4 bg-slate-50 rounded-lg border">
                  <div>
                    <p className="text-xs text-muted-foreground">Employee</p>
                    <p className="font-medium">{selectedReview.employee_name}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Manager</p>
                    <p className="font-medium">{selectedReview.manager_name}</p>
                  </div>
                  {formatScore(selectedReview.okr_achievement_score, "%") && (
                    <div>
                      <p className="text-xs text-muted-foreground">OKR Achievement</p>
                      <p className="font-medium">{formatScore(selectedReview.okr_achievement_score, "%")}</p>
                    </div>
                  )}
                  <div>
                    <p className="text-xs text-muted-foreground">Rating Locked</p>
                    <p className="font-medium">
                      {selectedReview.rating_locked ? "Yes" : "No"}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        )}

        {/* Scores Tab */}
        {selectedReview && calculation && (
          <TabsContent value="scores" className="space-y-4">
            <ReviewScoringVisualization calculation={calculation} />
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}
