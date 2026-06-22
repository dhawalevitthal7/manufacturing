import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type ReviewableTeamMember } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Bot,
  ClipboardCheck,
  Loader2,
  Sparkles,
  Target,
  TrendingUp,
  MessageCircle,
} from "lucide-react";

interface ManagerTeamReviewHubProps {
  onOpenReview: (reviewId: string) => void;
}

export function ManagerTeamReviewHub({ onOpenReview }: ManagerTeamReviewHubProps) {
  const queryClient = useQueryClient();
  const [cycleId, setCycleId] = useState<string>("");
  const [busyEmployeeId, setBusyEmployeeId] = useState<string>();

  const { data: cycles, isLoading: cyclesLoading } = useQuery({
    queryKey: ["performance-review-cycles"],
    queryFn: () => api.getPerformanceReviewCycles(),
  });

  const activeCycleId = cycleId || cycles?.find((c) => c.status === "ACTIVE")?.id || cycles?.[0]?.id || "";

  const { data: team, isLoading: teamLoading } = useQuery({
    queryKey: ["reviewable-team", activeCycleId],
    queryFn: () => api.getReviewableTeam(activeCycleId),
    enabled: !!activeCycleId,
  });

  const initiateMutation = useMutation({
    mutationFn: ({ employeeId }: { employeeId: string }) =>
      api.initiateEmployeeReview(employeeId, activeCycleId),
    onSuccess: (review) => {
      queryClient.invalidateQueries({ queryKey: ["reviewable-team", activeCycleId] });
      queryClient.invalidateQueries({ queryKey: ["performance-reviews"] });
      onOpenReview(review.id);
    },
    onSettled: () => setBusyEmployeeId(undefined),
  });

  const generateMutation = useMutation({
    mutationFn: ({ employeeId, reviewId }: { employeeId: string; reviewId?: string | null }) =>
      reviewId
        ? api.generateAIReview(reviewId).then((ai) => ({ reviewId: reviewId!, ai }))
        : api.initiateAndGenerateAIReview(employeeId, activeCycleId).then(({ review, ai }) => ({
            reviewId: review.id,
            ai,
          })),
    onSuccess: ({ reviewId }) => {
      queryClient.invalidateQueries({ queryKey: ["reviewable-team", activeCycleId] });
      queryClient.invalidateQueries({ queryKey: ["performance-reviews"] });
      queryClient.invalidateQueries({ queryKey: ["ai-review", reviewId] });
      onOpenReview(reviewId);
    },
    onSettled: () => setBusyEmployeeId(undefined),
  });

  const handleInitiate = (member: ReviewableTeamMember) => {
    setBusyEmployeeId(member.employee_id);
    initiateMutation.mutate({ employeeId: member.employee_id });
  };

  const handleGenerate = (member: ReviewableTeamMember) => {
    setBusyEmployeeId(member.employee_id);
    generateMutation.mutate({
      employeeId: member.employee_id,
      reviewId: member.review_id,
    });
  };

  const isLoading = cyclesLoading || teamLoading;
  const members = team || [];

  return (
    <div className="space-y-4">
      <Alert className="border-amber-200 bg-amber-50 dark:bg-amber-950/30">
        <Bot className="h-4 w-4 text-amber-700" />
        <AlertDescription className="text-amber-950 dark:text-amber-100">
          Generate AI performance reviews for anyone in your reporting tree. The agent pulls{" "}
          <strong>OKRs</strong>, <strong>weekly check-ins</strong>, <strong>progress submissions</strong>,{" "}
          self-review (if submitted), and prior cycle scores — then drafts an editable review you can finalize.
        </AlertDescription>
      </Alert>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-amber-500" />
            AI Review Generator — Your Team
          </CardTitle>
          <CardDescription>
            Select a review cycle, then initiate or run the Review Agent for direct and indirect reports.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="max-w-sm">
            <Select
              value={activeCycleId}
              onValueChange={(v) => setCycleId(v)}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select review cycle" />
              </SelectTrigger>
              <SelectContent>
                {(cycles || []).map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.name} ({c.status})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {isLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : members.length === 0 ? (
            <p className="text-sm text-muted-foreground py-6 text-center">
              No team members in your reporting scope for this cycle. Check-ins and OKRs from your
              direct reports will appear here once reporting relationships are configured.
            </p>
          ) : (
            <div className="space-y-2">
              {members.map((member) => {
                const busy = busyEmployeeId === member.employee_id;
                return (
                  <div
                    key={member.employee_id}
                    className="flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-medium">{member.employee_name}</p>
                        <Badge variant="outline">{member.employee_role.replace(/_/g, " ")}</Badge>
                        {member.review_state && (
                          <Badge variant="secondary">
                            {member.review_state.replace(/_/g, " ")}
                          </Badge>
                        )}
                        {member.ai_review_status && member.ai_review_status !== "NONE" && (
                          <Badge className="bg-amber-100 text-amber-900">
                            AI: {member.ai_review_status.replace(/_/g, " ")}
                          </Badge>
                        )}
                      </div>
                      <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Target className="h-3 w-3" />
                          {member.okr_count} OKRs · {member.okr_avg_progress}% avg
                        </span>
                        <span className="flex items-center gap-1">
                          <MessageCircle className="h-3 w-3" />
                          {member.checkin_count} check-ins
                        </span>
                        <span className="flex items-center gap-1">
                          <TrendingUp className="h-3 w-3" />
                          {member.progress_submission_count} progress updates
                        </span>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2 shrink-0">
                      {member.can_initiate && (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={busy}
                          onClick={() => handleInitiate(member)}
                        >
                          {busy && initiateMutation.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <ClipboardCheck className="h-4 w-4 mr-1" />
                          )}
                          Start review
                        </Button>
                      )}
                      {member.can_generate_ai && (
                        <Button
                          size="sm"
                          disabled={busy}
                          onClick={() => handleGenerate(member)}
                        >
                          {busy && generateMutation.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Sparkles className="h-4 w-4 mr-1" />
                          )}
                          {member.ai_review_status === "GENERATED" ||
                          member.ai_review_status === "MANAGER_EDITED"
                            ? "Open AI draft"
                            : "Generate AI review"}
                        </Button>
                      )}
                      {member.can_open && !member.can_generate_ai && (
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => member.review_id && onOpenReview(member.review_id)}
                        >
                          View review
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {(initiateMutation.isError || generateMutation.isError) && (
            <p className="text-sm text-destructive">
              {(initiateMutation.error || generateMutation.error) instanceof Error
                ? (initiateMutation.error || generateMutation.error)?.message
                : "Action failed"}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
