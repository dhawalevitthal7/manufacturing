import { useState, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import {
  ChevronDown, ChevronRight, CheckCircle2, XCircle, Pencil, Save,
  Loader2, Clock, User,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/stores/auth-store";
import { DualApprovalChainBadge } from "@/components/approvals/dual-approval-chain-badge";
import type { Objective, KeyResult } from "@/lib/api";

const STATUS_STYLE: Record<string, string> = {
  PENDING_APPROVAL: "text-amber-500 border-amber-500/40 bg-amber-500/10",
  ACTIVE: "text-emerald-500 border-emerald-500/40 bg-emerald-500/10",
  REJECTED: "text-rose-500 border-rose-500/40 bg-rose-500/10",
};

interface KrDraft {
  id: string;
  title: string;
  target_value: number;
  unit: string;
  weight: number;
}

interface Props {
  okr: Objective;
  queueStatus: "pending" | "approved" | "rejected";
  onApproved?: () => void;
}

export function OkrApprovalReviewCard({ okr: initialOkr, queueStatus, onApproved }: Props) {
  const { user } = useAuthStore();
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(queueStatus === "pending");
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [okr, setOkr] = useState(initialOkr);
  const [title, setTitle] = useState(initialOkr.title);
  const [description, setDescription] = useState(initialOkr.description || "");
  const [krDrafts, setKrDrafts] = useState<KrDraft[]>([]);

  const isPendingApprover =
    queueStatus === "pending" &&
    okr.okr_status === "PENDING_APPROVAL" &&
    (!okr.pending_approver_user_id || okr.pending_approver_user_id === user?.id);

  const canEdit = queueStatus === "pending" && isPendingApprover;

  useEffect(() => {
    setOkr(initialOkr);
    setTitle(initialOkr.title);
    setDescription(initialOkr.description || "");
  }, [initialOkr]);

  useEffect(() => {
    if (!expanded) return;
    api.getObjective(okr.id).then((fresh) => {
      setOkr(fresh);
      setTitle(fresh.title);
      setDescription(fresh.description || "");
      setKrDrafts(
        (fresh.key_results || []).map((kr) => ({
          id: kr.id,
          title: kr.title,
          target_value: kr.target_value,
          unit: kr.unit || "%",
          weight: kr.weight ?? 1,
        })),
      );
    }).catch(() => {
      setKrDrafts(
        (okr.key_results || []).map((kr) => ({
          id: kr.id,
          title: kr.title,
          target_value: kr.target_value,
          unit: kr.unit || "%",
          weight: kr.weight ?? 1,
        })),
      );
    });
  }, [expanded, okr.id]);

  const refreshQueues = () => {
    queryClient.invalidateQueries({ queryKey: ["okr-creation-queue"] });
    queryClient.invalidateQueries({ queryKey: ["pending-okr-approvals"] });
    queryClient.invalidateQueries({ queryKey: ["objectives"] });
  };

  const saveEdits = async () => {
    setBusy(true);
    try {
      const updated = await api.updateObjective(okr.id, {
        title: title.trim(),
        description: description.trim() || undefined,
        level: okr.level,
        parent_id: okr.parent_id,
        plant_id: okr.plant_id,
        department_id: okr.department_id,
        team_id: okr.team_id,
        cycle_id: okr.cycle_id,
      });
      for (const kr of krDrafts) {
        await api.updateKeyResult(kr.id, {
          title: kr.title,
          target_value: kr.target_value,
          unit: kr.unit,
          weight: kr.weight,
        });
      }
      const fresh = await api.getObjective(okr.id);
      setOkr(fresh);
      setEditing(false);
      toast.success("OKR and key results updated");
      refreshQueues();
      return updated;
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to save changes");
    } finally {
      setBusy(false);
    }
  };

  const approve = async () => {
    if (editing) await saveEdits();
    setBusy(true);
    try {
      await api.approveOkrHierarchy(okr.id);
      const chain = okr.approval_chain_status;
      const awaitingFunctional =
        chain?.functional === "PENDING" && chain?.line === "APPROVED";
      toast.success(`Approved: ${title}`, {
        description: awaitingFunctional
          ? "Line approval recorded — awaiting functional head."
          : "OKR is now ACTIVE for the owner.",
      });
      refreshQueues();
      onApproved?.();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Approval failed");
    } finally {
      setBusy(false);
    }
  };

  const reject = async () => {
    if (!rejectReason.trim()) return;
    setBusy(true);
    try {
      await api.rejectOkrHierarchy(okr.id, rejectReason.trim());
      toast.info("OKR rejected", { description: rejectReason.trim() });
      setRejectOpen(false);
      refreshQueues();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Rejection failed");
    } finally {
      setBusy(false);
    }
  };

  const updateKr = (id: string, patch: Partial<KrDraft>) => {
    setKrDrafts((prev) => prev.map((k) => (k.id === id ? { ...k, ...patch } : k)));
  };

  const statusKey = okr.okr_status || "DRAFT";

  return (
    <div className="rounded-lg border border-border/60 bg-card overflow-hidden">
      <button
        type="button"
        className="w-full flex items-start justify-between gap-3 p-4 text-left hover:bg-muted/20 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-start gap-2 min-w-0 flex-1">
          {expanded ? <ChevronDown className="h-4 w-4 mt-0.5 shrink-0" /> : <ChevronRight className="h-4 w-4 mt-0.5 shrink-0" />}
          <div className="min-w-0 flex-1">
            <p className="font-medium text-sm truncate">{okr.title}</p>
            <p className="text-xs text-muted-foreground mt-0.5 flex flex-wrap gap-x-2">
              <span>{okr.level}</span>
              {okr.owner_name && <span>· {okr.owner_name}</span>}
              {okr.plant_name && <span>· {okr.plant_name}</span>}
              {(okr.key_results?.length ?? 0) > 0 && (
                <span>· {okr.key_results!.length} KR{(okr.key_results!.length !== 1) ? "s" : ""}</span>
              )}
            </p>
            <div className="mt-1.5">
              <DualApprovalChainBadge chain={okr.approval_chain_status} compact />
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0" onClick={(e) => e.stopPropagation()}>
          {!expanded && isPendingApprover && (
            <>
              <Button size="sm" className="h-7 text-xs" onClick={approve} disabled={busy}>
                {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : "Approve"}
              </Button>
              <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => setExpanded(true)} disabled={busy}>
                Review
              </Button>
            </>
          )}
          <Badge variant="outline" className={`text-[10px] ${STATUS_STYLE[statusKey] || ""}`}>
            {statusKey.replace(/_/g, " ")}
          </Badge>
        </div>
      </button>

      {expanded && (
        <div className="border-t border-border/40 px-4 pb-4 pt-3 space-y-4">
          {/* Meta */}
          <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
            {okr.assigned_by_name && (
              <span className="flex items-center gap-1"><User className="h-3 w-3" /> Created by {okr.assigned_by_name}</span>
            )}
            {okr.pending_approver_name && queueStatus === "pending" && (
              <span className="flex items-center gap-1"><Clock className="h-3 w-3" /> Awaiting {okr.pending_approver_name}</span>
            )}
            {queueStatus === "approved" && okr.creation_approved_by_name && (
              <span className="flex items-center gap-1 text-emerald-500">
                <CheckCircle2 className="h-3 w-3" /> Approved by {okr.creation_approved_by_name}
                {okr.creation_approved_at && ` · ${new Date(okr.creation_approved_at).toLocaleDateString()}`}
              </span>
            )}
            {queueStatus === "rejected" && okr.rejection_reason && (
              <span className="flex items-center gap-1 text-rose-400 col-span-2">
                <XCircle className="h-3 w-3" /> {okr.rejection_reason}
              </span>
            )}
          </div>

          {/* OKR fields */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Objective</Label>
              {canEdit && !editing && (
                <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setEditing(true)}>
                  <Pencil className="h-3 w-3 mr-1" /> Edit
                </Button>
              )}
            </div>
            {editing ? (
              <div className="space-y-2">
                <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="OKR title" />
                <Textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Description" rows={2} />
              </div>
            ) : (
              <div>
                <p className="text-sm font-medium">{okr.title}</p>
                {okr.description && <p className="text-xs text-muted-foreground mt-1">{okr.description}</p>}
              </div>
            )}
          </div>

          {/* Key Results */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Key Results ({krDrafts.length || okr.key_results?.length || 0})
            </Label>
            {(krDrafts.length > 0 ? krDrafts : (okr.key_results || []).map((kr) => ({
              id: kr.id, title: kr.title, target_value: kr.target_value, unit: kr.unit || "%", weight: kr.weight ?? 1,
            }))).map((kr) => (
              <div key={kr.id} className="rounded-md border border-border/40 bg-muted/10 p-2.5 space-y-1.5">
                {editing ? (
                  <>
                    <Input value={kr.title} onChange={(e) => updateKr(kr.id, { title: e.target.value })} className="h-8 text-xs" />
                    <div className="grid grid-cols-3 gap-2">
                      <Input type="number" value={kr.target_value} onChange={(e) => updateKr(kr.id, { target_value: parseFloat(e.target.value) || 0 })} className="h-8 text-xs" placeholder="Target" />
                      <Input value={kr.unit} onChange={(e) => updateKr(kr.id, { unit: e.target.value })} className="h-8 text-xs" placeholder="Unit" />
                      <Input type="number" value={kr.weight} onChange={(e) => updateKr(kr.id, { weight: parseFloat(e.target.value) || 1 })} className="h-8 text-xs" placeholder="Weight" min={1} max={5} />
                    </div>
                  </>
                ) : (
                  <>
                    <p className="text-xs font-medium">{kr.title}</p>
                    <p className="text-[10px] text-muted-foreground">
                      Target: {kr.target_value} {kr.unit} · Weight: {kr.weight}
                      {!editing && okr.key_results && (() => {
                        const live = okr.key_results?.find((k: KeyResult) => k.id === kr.id);
                        if (live && live.current_value != null) {
                          return ` · Current: ${live.current_value}`;
                        }
                        return "";
                      })()}
                    </p>
                  </>
                )}
              </div>
            ))}
            {krDrafts.length === 0 && (!okr.key_results || okr.key_results.length === 0) && (
              <p className="text-xs text-muted-foreground italic">No key results defined yet.</p>
            )}
          </div>

          {/* Actions */}
          <div className="flex flex-wrap gap-2 pt-1">
            {editing && (
              <>
                <Button size="sm" onClick={saveEdits} disabled={busy}>
                  {busy ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Save className="h-3 w-3 mr-1" />}
                  Save changes
                </Button>
                <Button size="sm" variant="outline" onClick={() => setEditing(false)} disabled={busy}>Cancel</Button>
              </>
            )}
            {isPendingApprover && !editing && (
              <>
                <Button size="sm" onClick={approve} disabled={busy}>
                  {busy ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <CheckCircle2 className="h-3 w-3 mr-1" />}
                  Approve OKR
                </Button>
                <Button size="sm" variant="outline" onClick={() => setRejectOpen(true)} disabled={busy}>
                  <XCircle className="h-3 w-3 mr-1" /> Reject
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setEditing(true)} disabled={busy}>
                  <Pencil className="h-3 w-3 mr-1" /> Modify before approve
                </Button>
              </>
            )}
            {queueStatus === "approved" && (
              <Badge variant="outline" className="text-emerald-500 border-emerald-500/30">
                <CheckCircle2 className="h-3 w-3 mr-1 inline" /> Active — visible to owner
              </Badge>
            )}
          </div>
        </div>
      )}

      <Dialog open={rejectOpen} onOpenChange={setRejectOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Reject OKR Creation</DialogTitle></DialogHeader>
          <Textarea value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} placeholder="Reason for rejection (required)" rows={3} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setRejectOpen(false)}>Cancel</Button>
            <Button variant="destructive" onClick={reject} disabled={!rejectReason.trim() || busy}>Reject</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
