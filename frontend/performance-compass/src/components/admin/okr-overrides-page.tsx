import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Loader2, ShieldAlert } from "lucide-react";
import { api } from "@/lib/api";
import type { Objective } from "@/lib/api";

const OKR_STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-slate-500/15 text-slate-400",
  PENDING_APPROVAL: "bg-amber-500/15 text-amber-400",
  REJECTED: "bg-rose-500/15 text-rose-400",
  ACTIVE: "bg-emerald-500/15 text-emerald-400",
};

export function OkrOverridesPage() {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [action, setAction] = useState<"approve" | "reject">("approve");
  const [selected, setSelected] = useState<Objective | null>(null);
  const [overrideReason, setOverrideReason] = useState("");
  const [rejectionReason, setRejectionReason] = useState("");
  const [busy, setBusy] = useState(false);

  const { data: okrs = [], isLoading } = useQuery({
    queryKey: ["admin-okr-overrides"],
    queryFn: () => api.getAdminLifecycleOverrides(),
  });

  const openDialog = (okr: Objective, act: "approve" | "reject") => {
    setSelected(okr);
    setAction(act);
    setOverrideReason("");
    setRejectionReason("");
    setDialogOpen(true);
  };

  const submit = async () => {
    if (!selected || !overrideReason.trim()) return;
    setBusy(true);
    try {
      if (action === "approve") {
        await api.adminApproveObjective(selected.id, overrideReason.trim());
      } else {
        await api.adminRejectObjective(
          selected.id,
          overrideReason.trim(),
          rejectionReason.trim() || overrideReason.trim(),
        );
      }
      setDialogOpen(false);
      queryClient.invalidateQueries({ queryKey: ["admin-okr-overrides"] });
      queryClient.invalidateQueries({ queryKey: ["objectives"] });
    } catch (e) {
      console.error(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold flex items-center gap-2">
          <ShieldAlert className="h-6 w-6 text-amber-500" />
          OKR Admin Overrides
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Use only when the business approver is unavailable. Every action is audited.
        </p>
      </div>

      <Alert className="border-amber-500/40 bg-amber-500/5">
        <AlertDescription>
          This is not the normal approval queue. Use /approvals for progress validation.
        </AlertDescription>
      </Alert>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : okrs.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground text-sm">
            No in-flight OKRs requiring override.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3">
          {okrs.map((okr) => (
            <Card key={okr.id}>
              <CardHeader className="py-3 px-4 flex flex-row items-center justify-between space-y-0">
                <div>
                  <CardTitle className="text-base">{okr.title}</CardTitle>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {okr.level} · {okr.owner_name || "Owner"}
                  </p>
                </div>
                <Badge className={OKR_STATUS_COLORS[okr.okr_status || "DRAFT"] || ""}>
                  {okr.okr_status || "DRAFT"}
                </Badge>
              </CardHeader>
              <CardContent className="px-4 pb-4 flex gap-2">
                <Button size="sm" variant="outline" onClick={() => openDialog(okr, "approve")}>
                  Admin approve
                </Button>
                <Button size="sm" variant="destructive" onClick={() => openDialog(okr, "reject")}>
                  Admin reject
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{action === "approve" ? "Admin approve OKR" : "Admin reject OKR"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">{selected?.title}</p>
            <Textarea
              placeholder="Override reason (required)"
              value={overrideReason}
              onChange={(e) => setOverrideReason(e.target.value)}
              rows={3}
            />
            {action === "reject" && (
              <Textarea
                placeholder="Rejection reason for owner (optional)"
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
                rows={2}
              />
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={submit} disabled={busy || !overrideReason.trim()}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Confirm"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}