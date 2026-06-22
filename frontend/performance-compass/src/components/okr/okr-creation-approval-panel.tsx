import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ClipboardCheck, Clock, CheckCircle2, XCircle } from "lucide-react";
import type { Objective } from "@/lib/api";
import { useAuthStore } from "@/lib/stores/auth-store";
import { OkrApproverActions } from "./okr-lifecycle-actions";

const STATUS_STYLES: Record<string, string> = {
  DRAFT: "text-slate-400 bg-slate-500/10 border-slate-500/30",
  PENDING_APPROVAL: "text-amber-400 bg-amber-500/10 border-amber-500/30",
  ACTIVE: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
  REJECTED: "text-rose-400 bg-rose-500/10 border-rose-500/30",
};

const APPROVAL_STYLES: Record<string, string> = {
  PENDING: "text-amber-400 bg-amber-500/10 border-amber-500/30",
  APPROVED: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
  REJECTED: "text-rose-400 bg-rose-500/10 border-rose-500/30",
  REVISION_REQUESTED: "text-rose-400 bg-rose-500/10 border-rose-500/30",
};

interface Props {
  okr: Objective;
}

export function OkrCreationApprovalPanel({ okr }: Props) {
  const { user } = useAuthStore();
  const okrStatus = okr.okr_status || "DRAFT";
  const approvalStatus = okr.creation_approval_status || "PENDING";
  const isPendingApprover = user?.id && okr.pending_approver_user_id === user.id;
  const isOwnerOrAssignee =
    user?.id && (okr.owner_id === user.id || okr.assigned_by_id === user.id);

  return (
    <Card className="border-border/60 bg-muted/10">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <ClipboardCheck className="h-4 w-4 text-primary" />
          OKR Creation Approval
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline" className={STATUS_STYLES[okrStatus] || ""}>
            OKR: {okrStatus.replace(/_/g, " ")}
          </Badge>
          <Badge variant="outline" className={APPROVAL_STYLES[approvalStatus] || ""}>
            Approval: {approvalStatus.replace(/_/g, " ")}
          </Badge>
        </div>

        {okrStatus === "PENDING_APPROVAL" && (
          <div className="flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/5 p-2.5">
            <Clock className="h-4 w-4 text-amber-400 mt-0.5 shrink-0" />
            <div>
              <p className="text-xs font-medium text-amber-300">
                {isOwnerOrAssignee && !isPendingApprover
                  ? `Awaiting approval from ${okr.pending_approver_name || "approver"}${okr.pending_approver_role ? ` (${okr.pending_approver_role})` : ""}`
                  : `Pending approver: ${okr.pending_approver_name || "—"}${okr.pending_approver_role ? ` (${okr.pending_approver_role})` : ""}`}
              </p>
              <p className="text-[10px] text-muted-foreground mt-0.5">
                This OKR is not active until creation is approved. KR progress submission is disabled.
              </p>
            </div>
          </div>
        )}

        {okrStatus === "ACTIVE" && approvalStatus === "APPROVED" && (
          <div className="flex items-center gap-2 text-xs text-emerald-400">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Approved
            {okr.creation_approved_by_name && ` by ${okr.creation_approved_by_name}`}
            {okr.creation_approved_at && ` on ${new Date(okr.creation_approved_at).toLocaleDateString()}`}
          </div>
        )}

        {okrStatus === "REJECTED" && (
          <div className="flex items-start gap-2 text-xs text-rose-400">
            <XCircle className="h-3.5 w-3.5 mt-0.5" />
            <span>{okr.rejection_reason || "Creation rejected"}</span>
          </div>
        )}

        {isPendingApprover && okrStatus === "PENDING_APPROVAL" && (
          <OkrApproverActions okr={okr} />
        )}
      </CardContent>
    </Card>
  );
}
