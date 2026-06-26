import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Loader2, Sparkles, RefreshCw, Send, CheckCircle2, XCircle, Eye } from "lucide-react";
import { api, type AICascadeDraft } from "@/lib/api";
import { AiCascadeDetailDrawer } from "@/components/okr/ai-cascade-detail-drawer";

function statusBadge(status: string) {
  const map: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
    AI_DRAFT: "secondary",
    UNDER_REVIEW: "outline",
    PENDING_PARENT_APPROVAL: "default",
    AI_REJECTED: "destructive",
    ACTIVE: "default",
  };
  return (
    <Badge variant={map[status] || "outline"} className="text-[10px]">
      {status.replace(/_/g, " ")}
    </Badge>
  );
}

interface Props {
  mode: "child_review" | "parent_approval";
}

export function AiSuggestedOkrsPanel({ mode }: Props) {
  const queryClient = useQueryClient();
  const [detailDraft, setDetailDraft] = useState<AICascadeDraft | null>(null);

  const { data: drafts = [], isLoading, error } = useQuery({
    queryKey: mode === "parent_approval" ? ["parent-approval-queue"] : ["ai-drafts"],
    queryFn: () =>
      mode === "parent_approval" ? api.getParentApprovalQueue() : api.getAiDraftOkrs(),
    refetchInterval: 30_000,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["ai-drafts"] });
    queryClient.invalidateQueries({ queryKey: ["parent-approval-queue"] });
    queryClient.invalidateQueries({ queryKey: ["cascade-notifications"] });
    queryClient.invalidateQueries({ queryKey: ["objectives"] });
  };

  const regenerate = useMutation({
    mutationFn: (id: string) => api.regenerateAiDraft(id),
    onSuccess: invalidate,
  });

  const submitParent = useMutation({
    mutationFn: (id: string) => api.submitAiDraftForParentApproval(id),
    onSuccess: invalidate,
  });

  const approveParent = useMutation({
    mutationFn: (id: string) => api.approveParentAiDraft(id),
    onSuccess: invalidate,
  });

  const rejectParent = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      api.rejectParentAiDraft(id, reason),
    onSuccess: invalidate,
  });

  const rejectAi = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      api.rejectAiDraft(id, reason),
    onSuccess: invalidate,
  });

  const startReview = useMutation({
    mutationFn: (id: string) => api.reviewAiDraft(id, {}),
    onSuccess: invalidate,
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>
          {error instanceof Error ? error.message : "Failed to load AI suggested OKRs"}
        </AlertDescription>
      </Alert>
    );
  }

  if (drafts.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-sm text-muted-foreground">
          <Sparkles className="mx-auto mb-2 h-6 w-6 opacity-50" />
          {mode === "parent_approval"
            ? "No child OKRs pending your approval."
            : "No AI suggested OKRs ready for review."}
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <div className="space-y-4">
        {drafts.map((draft: AICascadeDraft) => (
          <Card key={draft.id} className="border-primary/20">
            <CardHeader className="pb-2">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-primary" />
                    {draft.title}
                  </CardTitle>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Parent: {draft.parent_title || "—"} · {draft.level}
                    {draft.owner_name ? ` · Owner: ${draft.owner_name}` : ""}
                  </p>
                </div>
                <div className="flex flex-wrap gap-1">
                  <Badge variant="outline" className="text-[10px]">AI Suggested</Badge>
                  {statusBadge(draft.okr_status)}
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {draft.description && (
                <p className="text-sm text-muted-foreground">{draft.description}</p>
              )}

              <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                {draft.alignment_score != null && (
                  <span>Alignment: {Math.round(draft.alignment_score)}%</span>
                )}
                {draft.ai_confidence != null && (
                  <span>Confidence: {Math.round(draft.ai_confidence * 100)}%</span>
                )}
                {draft.ai_total_tokens != null && (
                  <span>{draft.ai_total_tokens} tokens</span>
                )}
                {draft.ai_generation_reason && (
                  <span className="italic">{draft.ai_generation_reason}</span>
                )}
              </div>

              {draft.key_results && draft.key_results.length > 0 && (
                <ul className="space-y-1 rounded-md border border-border bg-muted/30 p-3 text-xs">
                  {draft.key_results.map((kr) => (
                    <li key={kr.id} className="flex justify-between gap-2">
                      <span>{kr.title}</span>
                      <span className="text-muted-foreground">
                        {kr.target_value} {kr.unit}
                      </span>
                    </li>
                  ))}
                </ul>
              )}

              <div className="flex flex-wrap gap-2 pt-1">
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setDetailDraft(draft)}
                >
                  <Eye className="h-3 w-3 mr-1" /> Preview / History
                </Button>

                {mode === "child_review" && (
                  <>
                    {draft.okr_status === "AI_DRAFT" && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => startReview.mutate(draft.id)}
                        disabled={startReview.isPending}
                      >
                        Review
                      </Button>
                    )}
                    {["AI_DRAFT", "UNDER_REVIEW"].includes(draft.okr_status) && (
                      <>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => regenerate.mutate(draft.id)}
                          disabled={regenerate.isPending}
                        >
                          <RefreshCw className="h-3 w-3 mr-1" /> Regenerate
                        </Button>
                        <Button
                          size="sm"
                          onClick={() => submitParent.mutate(draft.id)}
                          disabled={submitParent.isPending}
                        >
                          <Send className="h-3 w-3 mr-1" /> Submit for Approval
                        </Button>
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => {
                            const reason = prompt("Reason for rejecting this AI suggestion?");
                            if (reason) rejectAi.mutate({ id: draft.id, reason });
                          }}
                        >
                          <XCircle className="h-3 w-3 mr-1" /> Reject
                        </Button>
                      </>
                    )}
                  </>
                )}

                {mode === "parent_approval" && draft.okr_status === "PENDING_PARENT_APPROVAL" && (
                  <>
                    <Button
                      size="sm"
                      onClick={() => approveParent.mutate(draft.id)}
                      disabled={approveParent.isPending}
                    >
                      <CheckCircle2 className="h-3 w-3 mr-1" /> Approve
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => {
                        const reason = prompt("Reason for rejection?");
                        if (reason) rejectParent.mutate({ id: draft.id, reason });
                      }}
                    >
                      <XCircle className="h-3 w-3 mr-1" /> Reject
                    </Button>
                  </>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <AiCascadeDetailDrawer
        draft={detailDraft}
        open={!!detailDraft}
        onOpenChange={(open) => !open && setDetailDraft(null)}
      />
    </>
  );
}
