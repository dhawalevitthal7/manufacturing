import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  CheckCircle2, XCircle, Edit3, ArrowRight, Clock, Loader2,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, type PendingValidation } from "@/lib/api";
import { useValidateProgress } from "@/lib/hooks";

interface Props {
  validations: PendingValidation[];
  variant?: "panel" | "inline";
  onActionComplete?: () => void;
}

export function OkrProgressValidationActions({
  validations,
  variant = "panel",
  onActionComplete,
}: Props) {
  const queryClient = useQueryClient();
  const validate = useValidateProgress();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [overrideOpen, setOverrideOpen] = useState<PendingValidation | null>(null);
  const [overrideValue, setOverrideValue] = useState("");
  const [overrideNote, setOverrideNote] = useState("");

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["objectives"] });
    queryClient.invalidateQueries({ queryKey: ["pending-validations"] });
    queryClient.invalidateQueries({ queryKey: ["progress-summary"] });
    queryClient.invalidateQueries({ queryKey: ["alignment-tree"] });
    queryClient.invalidateQueries({ queryKey: ["approvals-dashboard"] });
    onActionComplete?.();
  };

  const handleApprove = async (v: PendingValidation) => {
    setBusyId(v.id);
    try {
      const result = await api.reviewProgressSubmission(v.id, { action: "approve" }) as {
        objective_progress?: number;
      };
      toast.success("Progress approved", {
        description: `${v.key_result_title}: ${result.objective_progress ?? v.new_value}% recorded.`,
      });
      refresh();
    } catch (err: unknown) {
      if (v.source === "legacy_update") {
        validate.mutate({ updateId: v.id, validation: { status: "APPROVED" } }, { onSettled: refresh });
      } else {
        toast.error(err instanceof Error ? err.message : "Approval failed");
      }
    } finally {
      setBusyId(null);
    }
  };

  const handleReject = async (v: PendingValidation) => {
    setBusyId(v.id);
    try {
      await api.reviewProgressSubmission(v.id, {
        action: "reject",
        manager_note: "Rejected by validator",
      });
      toast.info("Progress submission rejected");
      refresh();
    } catch {
      validate.mutate(
        { updateId: v.id, validation: { status: "REJECTED", validation_notes: "Rejected" } },
        { onSettled: refresh },
      );
    } finally {
      setBusyId(null);
    }
  };

  const handleOverride = async () => {
    if (!overrideOpen || !overrideValue) return;
    setBusyId(overrideOpen.id);
    try {
      await api.reviewProgressSubmission(overrideOpen.id, {
        action: "override",
        manager_value: parseFloat(overrideValue),
        manager_note: overrideNote || undefined,
      });
      toast.success("Progress overridden and approved");
      setOverrideOpen(null);
      setOverrideValue("");
      setOverrideNote("");
      refresh();
    } catch {
      validate.mutate(
        { updateId: overrideOpen.id, validation: { status: "APPROVED" } },
        { onSettled: refresh },
      );
    } finally {
      setBusyId(null);
    }
  };

  if (!validations.length) return null;

  const compact = variant === "inline";

  return (
    <>
      <div
        className={
          compact
            ? "flex flex-col gap-1 min-w-[7.5rem]"
            : "rounded-lg border border-amber-500/30 bg-amber-500/5 p-2 min-w-[9rem] max-w-[11rem]"
        }
      >
        {!compact && (
          <div className="flex items-center gap-1 mb-1">
            <Clock className="h-3 w-3 text-amber-400 shrink-0" />
            <span className="text-[10px] font-medium text-amber-300 uppercase tracking-wide">
              Validate
            </span>
            <Badge variant="outline" className="text-[8px] px-1 py-0 h-4 ml-auto border-amber-500/30 text-amber-400">
              {validations.length}
            </Badge>
          </div>
        )}

        {validations.map((v) => {
          const isBusy = busyId === v.id;
          return (
            <div key={v.id} className={compact ? "space-y-1" : "space-y-1.5 not-first:mt-2 pt-2 not-first:border-t border-amber-500/20"}>
              {!compact && (
                <p className="text-[9px] text-muted-foreground truncate" title={v.key_result_title}>
                  {v.key_result_title}
                </p>
              )}
              <p className="text-[9px] tabular-nums text-muted-foreground flex items-center gap-0.5">
                <span>{v.previous_value}</span>
                <ArrowRight className="h-2.5 w-2.5 text-primary" />
                <span className="text-foreground font-semibold">{v.new_value}</span>
              </p>
              <div className="flex flex-col gap-0.5">
                <Button
                  size="sm"
                  variant="outline"
                  className="h-6 text-[10px] text-emerald-500 border-emerald-500/30 hover:bg-emerald-500/10 gap-1 px-2"
                  onClick={() => handleApprove(v)}
                  disabled={isBusy}
                >
                  {isBusy ? <Loader2 className="h-2.5 w-2.5 animate-spin" /> : <CheckCircle2 className="h-2.5 w-2.5" />}
                  Approve
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-6 text-[10px] text-blue-400 border-blue-500/30 hover:bg-blue-500/10 gap-1 px-2"
                  onClick={() => {
                    setOverrideOpen(v);
                    setOverrideValue(String(v.new_value));
                    setOverrideNote("");
                  }}
                  disabled={isBusy}
                >
                  <Edit3 className="h-2.5 w-2.5" /> Override
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-6 text-[10px] text-rose-500 border-rose-500/30 hover:bg-rose-500/10 gap-1 px-2"
                  onClick={() => handleReject(v)}
                  disabled={isBusy}
                >
                  <XCircle className="h-2.5 w-2.5" /> Reject
                </Button>
              </div>
            </div>
          );
        })}
      </div>

      <Dialog open={!!overrideOpen} onOpenChange={() => { setOverrideOpen(null); setOverrideValue(""); setOverrideNote(""); }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Edit3 className="h-4 w-4 text-blue-400" />
              Override Progress Value
            </DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            {overrideOpen && (
              <p className="text-xs text-muted-foreground">
                {overrideOpen.key_result_title}: employee submitted {overrideOpen.new_value}
              </p>
            )}
            <div className="grid gap-1">
              <Label>Validator value</Label>
              <Input
                type="number"
                value={overrideValue}
                onChange={(e) => setOverrideValue(e.target.value)}
              />
            </div>
            <div className="grid gap-1">
              <Label>Note (optional)</Label>
              <Textarea
                value={overrideNote}
                onChange={(e) => setOverrideNote(e.target.value)}
                rows={2}
                placeholder="Reason for override..."
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setOverrideOpen(null); setOverrideValue(""); setOverrideNote(""); }}>
              Cancel
            </Button>
            <Button onClick={handleOverride} disabled={!overrideValue || busyId !== null}>
              Override & Approve
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
