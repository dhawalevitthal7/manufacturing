import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  CheckCircle2, XCircle, Edit3, ArrowRight, GitBranch, Clock,
  AlertTriangle,
} from "lucide-react";
import { useValidateProgress } from "@/lib/hooks";
import { api } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import type { PendingValidation } from "@/lib/api";

interface Props {
  validations: PendingValidation[];
}

export function ValidationQueue({ validations }: Props) {
  const validate = useValidateProgress();
  const queryClient = useQueryClient();
  const [overrideOpen, setOverrideOpen] = useState<string | null>(null);
  const [overrideValue, setOverrideValue] = useState("");
  const [overrideNote, setOverrideNote] = useState("");
  const [reviewingId, setReviewingId] = useState<string | null>(null);

  const handleApprove = async (v: PendingValidation) => {
    setReviewingId(v.id);
    try {
      const result = await api.reviewProgressSubmission(v.id, { action: "approve" }) as {
        objective_progress?: number;
        kr_current_value?: number;
      };
      queryClient.invalidateQueries({ queryKey: ["objectives"] });
      queryClient.invalidateQueries({ queryKey: ["pending-validations"] });
      queryClient.invalidateQueries({ queryKey: ["progress-summary"] });
      queryClient.invalidateQueries({ queryKey: ["alignment-tree"] });
      const pct = result.objective_progress ?? v.new_value;
      toast.success("Progress approved and saved", {
        description: `${v.objective_title}: ${pct}% objective progress recorded in the system.`,
      });
    } catch (err: unknown) {
      if (v.source === "legacy_update") {
        validate.mutate({ updateId: v.id, validation: { status: "APPROVED" } });
      } else {
        const msg = err instanceof Error ? err.message : "Approval failed";
        toast.error(msg);
      }
    }
    setReviewingId(null);
  };

  const handleReject = async (id: string) => {
    setReviewingId(id);
    try {
      await api.reviewProgressSubmission(id, {
        action: "reject",
        manager_note: "Rejected by manager",
      });
      queryClient.invalidateQueries({ queryKey: ["pending-validations"] });
    } catch {
      validate.mutate({ updateId: id, validation: { status: "REJECTED", validation_notes: "Rejected by manager" } });
    }
    setReviewingId(null);
  };

  const handleOverride = async () => {
    if (!overrideOpen || !overrideValue) return;
    setReviewingId(overrideOpen);
    try {
      await api.reviewProgressSubmission(overrideOpen, {
        action: "override",
        manager_value: parseFloat(overrideValue),
        manager_note: overrideNote || undefined,
      });
      queryClient.invalidateQueries({ queryKey: ["objectives"] });
      queryClient.invalidateQueries({ queryKey: ["pending-validations"] });
      queryClient.invalidateQueries({ queryKey: ["progress-summary"] });
      queryClient.invalidateQueries({ queryKey: ["alignment-tree"] });
    } catch {
      // Fallback
      validate.mutate({ updateId: overrideOpen, validation: { status: "APPROVED" } });
    }
    setOverrideOpen(null);
    setOverrideValue("");
    setOverrideNote("");
    setReviewingId(null);
  };

  if (!validations.length) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="text-center py-6">
            <CheckCircle2 className="mx-auto h-10 w-10 text-emerald-500/40 mb-2" />
            <p className="text-sm text-muted-foreground">No pending validations</p>
            <p className="text-xs text-muted-foreground/60 mt-0.5">
              Progress submissions from your team (and levels below you) appear here for approve or override.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <div className="space-y-2">
        {validations.map((v) => {
          const isReviewing = reviewingId === v.id;
          return (
            <Card key={v.id} className="border-amber-500/20 hover:border-amber-500/30 transition-colors">
              <CardContent className="py-3 px-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{v.key_result_title}</p>
                    <p className="text-xs text-muted-foreground truncate flex items-center gap-1 mt-0.5">
                      <GitBranch className="h-3 w-3 shrink-0" />
                      {v.objective_title}
                      <Badge variant="outline" className="text-[9px] px-1 py-0 ml-1">{v.objective_level}</Badge>
                    </p>
                    <div className="mt-1.5 flex items-center gap-2 text-xs text-muted-foreground">
                      <span className="font-medium text-foreground/80">{v.submitted_by}</span>
                      <span className="flex items-center gap-1">
                        <span className="text-muted-foreground tabular-nums">{v.previous_value}</span>
                        <ArrowRight className="h-3 w-3 text-primary" />
                        <span className="text-foreground font-semibold tabular-nums">{v.new_value}</span>
                      </span>
                      {v.notes && (
                        <span className="truncate max-w-[200px] italic text-muted-foreground/70">
                          "{v.notes}"
                        </span>
                      )}
                    </div>
                    <div className="mt-1 flex items-center gap-1 text-[10px] text-muted-foreground/60">
                      <Clock className="h-2.5 w-2.5" />
                      {new Date(v.created_at).toLocaleDateString()} {new Date(v.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </div>
                  </div>
                  <div className="flex flex-col gap-1 shrink-0">
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs text-emerald-500 border-emerald-500/30 hover:bg-emerald-500/10 gap-1"
                      onClick={() => handleApprove(v)}
                      disabled={isReviewing}
                    >
                      <CheckCircle2 className="h-3 w-3" /> Approve
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs text-blue-400 border-blue-500/30 hover:bg-blue-500/10 gap-1"
                      onClick={() => {
                        setOverrideOpen(v.id);
                        setOverrideValue(String(v.new_value));
                      }}
                      disabled={isReviewing}
                    >
                      <Edit3 className="h-3 w-3" /> Override
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs text-rose-500 border-rose-500/30 hover:bg-rose-500/10 gap-1"
                      onClick={() => handleReject(v.id)}
                      disabled={isReviewing}
                    >
                      <XCircle className="h-3 w-3" /> Reject
                    </Button>
                  </div>
                </div>

                {/* Cascade info */}
                <div className="mt-2 p-1.5 rounded bg-primary/5 border border-primary/10">
                  <p className="text-[10px] text-muted-foreground flex items-center gap-1">
                    <AlertTriangle className="h-2.5 w-2.5 text-amber-400" />
                    Approving will update KR value, recalculate weighted progress, and cascade upward through the OKR hierarchy.
                  </p>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Override Dialog */}
      <Dialog open={!!overrideOpen} onOpenChange={() => { setOverrideOpen(null); setOverrideValue(""); setOverrideNote(""); }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Edit3 className="h-4 w-4 text-blue-400" />
              Override Progress Value
            </DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <p className="text-xs text-muted-foreground">
              Override the employee's submitted value with your own assessment.
              The overridden value will be used for weighted progress calculation.
            </p>
            <div className="grid gap-1">
              <Label>Manager's Value</Label>
              <Input
                type="number"
                value={overrideValue}
                onChange={(e) => setOverrideValue(e.target.value)}
                placeholder="Enter corrected value"
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
            <Button onClick={handleOverride} disabled={!overrideValue || reviewingId !== null}>
              Override & Approve
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
