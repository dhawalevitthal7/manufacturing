import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Bot,
  CheckCircle2,
  Loader2,
  Send,
  Sparkles,
  UserCheck,
} from "lucide-react";
import { api, type AIReviewPayload } from "@/lib/api";

interface ReviewAgentPanelProps {
  reviewId: string;
  employeeName?: string;
  deptHeadName?: string;
  requiresDeptModeration?: boolean;
  managerInitiated?: boolean;
  onSuccess?: () => void;
}

export function ReviewAgentPanel({
  reviewId,
  employeeName,
  deptHeadName,
  requiresDeptModeration,
  managerInitiated,
  onSuccess,
}: ReviewAgentPanelProps) {
  const queryClient = useQueryClient();
  const [behavioral, setBehavioral] = useState({
    collaboration: 3,
    ownership: 3,
    execution: 3,
    accountability: 3,
  });
  const [managerNotes, setManagerNotes] = useState("");
  const [draft, setDraft] = useState<AIReviewPayload>({});

  const { data: aiReview, isLoading } = useQuery({
    queryKey: ["ai-review", reviewId],
    queryFn: () => api.getAIReview(reviewId),
    enabled: !!reviewId,
    retry: false,
  });

  useEffect(() => {
    if (aiReview?.payload) {
      setDraft(aiReview.payload);
    }
  }, [aiReview?.payload]);

  const generateMutation = useMutation({
    mutationFn: async () => {
      const result = await api.generateAIReview(reviewId);
      if (result.payload) {
        await api.updateAIReview(reviewId, {
          ...result.payload,
          behavioral_competency_scores: behavioral,
        });
      }
      return result;
    },
    onSuccess: (data) => {
      setDraft(data.payload || {});
      queryClient.invalidateQueries({ queryKey: ["ai-review", reviewId] });
      queryClient.invalidateQueries({ queryKey: ["review-calculation", reviewId] });
    },
  });

  const saveMutation = useMutation({
    mutationFn: () => api.updateAIReview(reviewId, draft),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ai-review", reviewId] });
    },
  });

  const submitMutation = useMutation({
    mutationFn: () =>
      api.submitAIReviewWithManager(reviewId, {
        behavioral_competency_scores: behavioral,
        manager_notes: managerNotes,
        promotion_eligible: draft.promotion_recommendation === "READY",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["performance-reviews"] });
      queryClient.invalidateQueries({ queryKey: ["performance-reviews", reviewId] });
      queryClient.invalidateQueries({ queryKey: ["ai-review", reviewId] });
      onSuccess?.();
    },
  });

  const hasGenerated = aiReview?.ai_review_status && aiReview.ai_review_status !== "NONE";
  const isSubmitted = aiReview?.ai_review_status === "SUBMITTED";

  const setField = (key: keyof AIReviewPayload, value: string | string[]) => {
    setDraft((prev) => ({ ...prev, [key]: value }));
  };

  if (isLoading) {
    return (
      <div className="flex justify-center py-8">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Alert>
        <Bot className="h-4 w-4" />
        <AlertDescription>
          {managerInitiated ? (
            <>
              Run the <strong>Review Agent</strong> to synthesize OKR progress, weekly check-ins, progress
              submissions, and any self-review data for {employeeName || "this employee"}. You can generate
              without waiting for employee self-review — edit the draft, then submit.
            </>
          ) : (
            <>
              After {employeeName || "the employee"} submits their self-review, run the{" "}
              <strong>Review Agent</strong> to synthesize OKR progress, check-ins, and self-assessment.
              Edit the draft, then submit to the employee
              {requiresDeptModeration && deptHeadName
                ? ` and ${deptHeadName} (dept head) for promotion moderation`
                : " and HR calibration"}
              .
            </>
          )}
        </AlertDescription>
      </Alert>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-amber-500" />
            Step 1 — Behavioral ratings
          </CardTitle>
          <CardDescription>Rate collaboration, ownership, execution, and accountability (1–5)</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          {(["collaboration", "ownership", "execution", "accountability"] as const).map((key) => (
            <div key={key} className="space-y-1">
              <Label className="capitalize">{key}</Label>
              <Input
                type="number"
                min={1}
                max={5}
                value={behavioral[key]}
                disabled={isSubmitted}
                onChange={(e) => setBehavioral({ ...behavioral, [key]: Number(e.target.value) })}
              />
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5" />
            Step 2 — Review Agent
          </CardTitle>
          <CardDescription>
            Pulls live OKR progress, weekly check-ins, progress submissions, self-review (if any), and score preview
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Button
            onClick={() => generateMutation.mutate()}
            disabled={generateMutation.isPending || isSubmitted}
            className="gap-2"
          >
            {generateMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            {hasGenerated ? "Regenerate AI review" : "Run Review Agent"}
          </Button>

          {generateMutation.isError && (
            <p className="text-sm text-destructive">
              {generateMutation.error instanceof Error
                ? generateMutation.error.message
                : "Failed to generate review"}
            </p>
          )}

          {draft.source === "rule_based" && (
            <Badge variant="outline">Rule-based synthesis (Azure OpenAI not configured)</Badge>
          )}

          {hasGenerated && (
            <div className="space-y-4 border-t pt-4">
              <div className="space-y-2">
                <Label>Executive summary</Label>
                <Textarea
                  value={draft.executive_summary || ""}
                  disabled={isSubmitted}
                  onChange={(e) => setField("executive_summary", e.target.value)}
                  rows={3}
                />
              </div>
              <div className="space-y-2">
                <Label>OKR performance analysis</Label>
                <Textarea
                  value={draft.okr_performance_analysis || ""}
                  disabled={isSubmitted}
                  onChange={(e) => setField("okr_performance_analysis", e.target.value)}
                  rows={3}
                />
              </div>
              <div className="space-y-2">
                <Label>Self-review synthesis</Label>
                <Textarea
                  value={draft.self_review_synthesis || ""}
                  disabled={isSubmitted}
                  onChange={(e) => setField("self_review_synthesis", e.target.value)}
                  rows={3}
                />
              </div>
              <div className="space-y-2">
                <Label>Check-in insights</Label>
                <Textarea
                  value={draft.checkin_insights || ""}
                  disabled={isSubmitted}
                  onChange={(e) => setField("checkin_insights", e.target.value)}
                  rows={2}
                />
              </div>
              <div className="space-y-2">
                <Label>Promotion recommendation</Label>
                <Input
                  value={draft.promotion_recommendation || ""}
                  disabled={isSubmitted}
                  placeholder="READY | NEEDS_DEVELOPMENT | NOT_READY"
                  onChange={(e) => setField("promotion_recommendation", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Promotion rationale</Label>
                <Textarea
                  value={draft.promotion_rationale || ""}
                  disabled={isSubmitted}
                  onChange={(e) => setField("promotion_rationale", e.target.value)}
                  rows={2}
                />
              </div>
              {!isSubmitted && (
                <Button variant="outline" onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
                  {saveMutation.isPending ? "Saving..." : "Save edits"}
                </Button>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {hasGenerated && !isSubmitted && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Send className="h-5 w-5" />
              Step 3 — Submit review
            </CardTitle>
            <CardDescription>
              Shares narrative with {employeeName || "employee"}
              {requiresDeptModeration ? ` and routes to ${deptHeadName || "department head"}` : ""}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Additional manager notes (optional)</Label>
              <Textarea
                value={managerNotes}
                onChange={(e) => setManagerNotes(e.target.value)}
                rows={3}
                placeholder="Personal coaching notes for the employee..."
              />
            </div>
            <Button
              onClick={async () => {
                await saveMutation.mutateAsync();
                submitMutation.mutate();
              }}
              disabled={submitMutation.isPending || saveMutation.isPending}
              className="gap-2"
            >
              {submitMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <UserCheck className="h-4 w-4" />
              )}
              Submit to employee
              {requiresDeptModeration ? " & dept head" : ""}
            </Button>
            {submitMutation.isError && (
              <p className="text-sm text-destructive">
                {submitMutation.error instanceof Error
                  ? submitMutation.error.message
                  : "Submission failed"}
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {isSubmitted && (
        <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 p-4 text-green-900">
          <CheckCircle2 className="h-5 w-5" />
          <p className="text-sm">
            Review submitted. Employee can view their narrative
            {requiresDeptModeration ? `; awaiting ${deptHeadName || "dept head"} moderation` : ""}.
          </p>
        </div>
      )}
    </div>
  );
}
