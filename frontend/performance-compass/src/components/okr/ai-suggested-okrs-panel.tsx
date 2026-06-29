import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Loader2,
  Sparkles,
  RefreshCw,
  Send,
  CheckCircle2,
  XCircle,
  Eye,
  Pencil,
} from "lucide-react";
import { api, type AICascadeDraft } from "@/lib/api";
import { useAuthStore } from "@/lib/stores/auth-store";
import { AiCascadeDetailDrawer } from "@/components/okr/ai-cascade-detail-drawer";
import { AiCascadeEditDialog } from "@/components/okr/ai-cascade-edit-dialog";

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
  const { user } = useAuthStore();
  const queryClient = useQueryClient();
  const [detailDraft, setDetailDraft] = useState<AICascadeDraft | null>(null);
  const [editDraft, setEditDraft] = useState<AICascadeDraft | null>(null);

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

  const isChildOwner = (draft: AICascadeDraft) =>
    !!user?.id && draft.owner_id === user.id;

  const canChildEdit = (draft: AICascadeDraft) =>
    mode === "child_review" &&
    isChildOwner(draft) &&
    ["AI_DRAFT", "UNDER_REVIEW"].includes(draft.okr_status);

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
      {mode === "child_review" && (
        <Alert className="mb-4 border-primary/30 bg-primary/5">
          <AlertDescription className="text-sm">
            <strong>Your workflow:</strong> Edit the AI suggestion to match your regional priorities →
            save changes → submit to your parent (CEO) for approval. You do not approve your own OKR here.
          </AlertDescription>
        </Alert>
      )}

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
                  {draft.ai_metadata?.source === "rule_based" ? (
                    <Badge variant="secondary" className="text-[10px]">Level-specific template</Badge>
                  ) : draft.ai_metadata?.source === "azure_openai" ? (
                    <Badge variant="secondary" className="text-[10px]">AI generated</Badge>
                  ) : null}
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

              {mode === "child_review" && draft.rejection_reason && canChildEdit(draft) && (
                <p className="text-xs text-amber-600 dark:text-amber-400">
                  Parent feedback: {draft.rejection_reason}
                </p>
              )}

              {mode === "child_review" && draft.okr_status === "PENDING_PARENT_APPROVAL" && (
                <p className="text-xs text-amber-600 dark:text-amber-400">
                  Submitted — waiting for {draft.parent_title ? "parent" : "CEO"} approval. Editing is locked.
                </p>
              )}

              {mode === "child_review" && !isChildOwner(draft) && user?.system_role === "CEO" && (
                <p className="text-xs text-muted-foreground">
                  Assigned to {draft.owner_name || "regional owner"} for review and edit.
                </p>
              )}

              <div className="flex flex-wrap gap-2 pt-1">
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setDetailDraft(draft)}
                >
                  <Eye className="h-3 w-3 mr-1" /> Preview / History
                </Button>

                {canChildEdit(draft) && (
                  <>
                    <Button
                      size="sm"
                      variant="default"
                      onClick={() => setEditDraft({ ...draft, key_results: draft.key_results ? [...draft.key_results] : [] })}
                    >
                      <Pencil className="h-3 w-3 mr-1" /> Edit & customize
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => regenerate.mutate(draft.id)}
                      disabled={regenerate.isPending}
                    >
                      <RefreshCw className="h-3 w-3 mr-1" /> Regenerate with AI
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => submitParent.mutate(draft.id)}
                      disabled={submitParent.isPending}
                    >
                      <Send className="h-3 w-3 mr-1" /> Submit for approval
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => {
                        const reason = prompt("Reason for rejecting this AI suggestion?");
                        if (reason) rejectAi.mutate({ id: draft.id, reason });
                      }}
                    >
                      <XCircle className="h-3 w-3 mr-1" /> Reject suggestion
                    </Button>
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
                      variant="outline"
                      onClick={() => {
                        const reason = prompt(
                          "What should the owner change? They can edit and resubmit.",
                        );
                        if (reason) rejectParent.mutate({ id: draft.id, reason });
                      }}
                    >
                      <XCircle className="h-3 w-3 mr-1" /> Send back for edits
                    </Button>
                  </>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <AiCascadeEditDialog
        draft={editDraft}
        open={!!editDraft}
        onOpenChange={(open) => !open && setEditDraft(null)}
        onSaved={invalidate}
      />

      <AiCascadeDetailDrawer
        draft={detailDraft}
        open={!!detailDraft}
        onOpenChange={(open) => !open && setDetailDraft(null)}
        canEdit={detailDraft ? canChildEdit(detailDraft) : false}
        onEdit={() => {
          if (detailDraft) {
            setEditDraft(detailDraft);
            setDetailDraft(null);
          }
        }}
      />
    </>
  );
}
