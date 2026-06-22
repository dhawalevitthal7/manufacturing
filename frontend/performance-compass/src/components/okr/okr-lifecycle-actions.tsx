import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Rocket, Loader2, Clock } from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/stores/auth-store";
import { useQueryClient } from "@tanstack/react-query";
import type { Objective } from "@/lib/api";

interface Props {
  okr: Objective;
}

export function OkrLifecycleActions({ okr }: Props) {
  const { user } = useAuthStore();
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);

  const isOwner = user?.id && okr.owner_id === user.id;
  const isCreator = user?.id && (okr.assigned_by_id === user.id || (!okr.assigned_by_id && okr.owner_id === user.id));
  const status = okr.okr_status || "DRAFT";

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["objectives"] });
    queryClient.invalidateQueries({ queryKey: ["pending-okr-approvals"] });
  };

  const publish = async () => {
    setBusy(true);
    try {
      await api.publishObjective(okr.id);
      refresh();
    } catch (e) {
      console.error(e);
    } finally {
      setBusy(false);
    }
  };

  if (!isOwner && !isCreator) return null;

  if (status === "PENDING_APPROVAL") {
    return (
      <p className="text-xs text-amber-500 mt-2 flex items-center gap-1">
        <Clock className="h-3 w-3" />
        Awaiting approval from {okr.pending_approver_name || "approver"}
        {okr.pending_approver_role ? ` (${okr.pending_approver_role})` : ""}
      </p>
    );
  }

  if (status === "DRAFT" || status === "REJECTED") {
    return (
      <div className="flex flex-wrap gap-2 mt-2">
        {okr.can_publish_as_ceo && isOwner ? (
          <Button size="sm" variant="default" onClick={publish} disabled={busy}>
            {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : <Rocket className="h-3 w-3 mr-1" />}
            Publish
          </Button>
        ) : null}
        {status === "REJECTED" && okr.rejection_reason && (
          <p className="text-xs text-rose-400 w-full">Rejected: {okr.rejection_reason}</p>
        )}
      </div>
    );
  }

  return null;
}

interface ApproverActionsProps {
  okr: Objective;
}

export function OkrApproverActions({ okr }: ApproverActionsProps) {
  const { user } = useAuthStore();
  const queryClient = useQueryClient();
  const [rejectOpen, setRejectOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  if (okr.okr_status !== "PENDING_APPROVAL") return null;
  if (user?.id && okr.pending_approver_user_id && user.id !== okr.pending_approver_user_id) {
    return null;
  }

  const approve = async () => {
    setBusy(true);
    try {
      await api.approveOkrHierarchy(okr.id);
      queryClient.invalidateQueries({ queryKey: ["pending-okr-approvals"] });
      queryClient.invalidateQueries({ queryKey: ["objectives"] });
    } catch (e) {
      console.error(e);
    } finally {
      setBusy(false);
    }
  };

  const reject = async () => {
    if (!reason.trim()) return;
    setBusy(true);
    try {
      await api.rejectOkrHierarchy(okr.id, reason.trim());
      setRejectOpen(false);
      queryClient.invalidateQueries({ queryKey: ["pending-okr-approvals"] });
      queryClient.invalidateQueries({ queryKey: ["objectives"] });
    } catch (e) {
      console.error(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="flex gap-2 mt-2">
        <Button size="sm" onClick={approve} disabled={busy}>Approve OKR</Button>
        <Button size="sm" variant="outline" onClick={() => setRejectOpen(true)} disabled={busy}>
          Reject
        </Button>
      </div>
      <Dialog open={rejectOpen} onOpenChange={setRejectOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Reject OKR</DialogTitle></DialogHeader>
          <Textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason for rejection" rows={3} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setRejectOpen(false)}>Cancel</Button>
            <Button variant="destructive" onClick={reject} disabled={!reason.trim() || busy}>Reject</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
