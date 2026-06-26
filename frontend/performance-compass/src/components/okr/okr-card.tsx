import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  ChevronDown, ChevronRight, Plus, Target, TrendingUp, Trash2, Send,
  GitBranch, Weight, CheckCircle, Clock, XCircle, AlertTriangle, Lock, Radio,
} from "lucide-react";
import { KrIngestDialog } from "./kr-ingest-dialog";
import { api } from "@/lib/api";
import { useQueryClient, useQuery } from "@tanstack/react-query";
import type { Objective } from "@/lib/api";
import { OkrLifecycleActions } from "./okr-lifecycle-actions";
import { OkrCreationApprovalPanel } from "./okr-creation-approval-panel";
import { OkrProgressValidationActions } from "./okr-progress-validation-actions";
import { canSubmitOkrProgress, canManageOkrStructure } from "@/utils/okr-permissions";
import { useAuthStore } from "@/lib/stores/auth-store";
import type { PendingValidation } from "@/lib/api";

const OKR_STATUS_BADGE: Record<string, string> = {
  DRAFT: "text-slate-400 bg-slate-500/10 border-slate-500/30",
  PENDING_APPROVAL: "text-amber-400 bg-amber-500/10 border-amber-500/30",
  ACTIVE: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
  REJECTED: "text-rose-400 bg-rose-500/10 border-rose-500/30",
  AI_DRAFT: "text-purple-400 bg-purple-500/10 border-purple-500/30",
  UNDER_REVIEW: "text-sky-400 bg-sky-500/10 border-sky-500/30",
  PENDING_PARENT_APPROVAL: "text-amber-400 bg-amber-500/10 border-amber-500/30",
  AI_REJECTED: "text-rose-400 bg-rose-500/10 border-rose-500/30",
};

// ── Level colors ──
const LEVEL_COLORS: Record<string, string> = {
  ORGANIZATION: "bg-violet-500/15 text-violet-400 border-violet-500/30",
  REGION: "bg-cyan-500/15 text-cyan-400 border-cyan-500/30",
  PLANT: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  DEPARTMENT: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  TEAM: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  INDIVIDUAL: "bg-rose-500/15 text-rose-400 border-rose-500/30",
};

const STATUS_CONFIG: Record<string, { color: string; icon: React.ElementType }> = {
  PENDING: { color: "text-amber-400 bg-amber-500/10 border-amber-500/30", icon: Clock },
  APPROVED: { color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30", icon: CheckCircle },
  REJECTED: { color: "text-rose-400 bg-rose-500/10 border-rose-500/30", icon: XCircle },
  REVISION_REQUESTED: { color: "text-amber-400 bg-amber-500/10 border-amber-500/30", icon: AlertTriangle },
};

interface Props {
  objective: Objective;
  canManage: boolean;
  onDelete?: (id: string) => void;
  /** Pending progress submissions for this OKR (validator view). */
  pendingValidations?: PendingValidation[];
  canValidateProgress?: boolean;
}

export function OKRCard({
  objective: okr,
  canManage,
  onDelete,
  pendingValidations = [],
  canValidateProgress = false,
}: Props) {
  const { user } = useAuthStore();
  const [expanded, setExpanded] = useState(false);
  const [addKROpen, setAddKROpen] = useState(false);
  const [progressOpen, setProgressOpen] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data: cycles } = useQuery({
    queryKey: ["cycles"],
    queryFn: () => api.getCycles(),
  });
  
  const okrCycle = cycles?.find(c => c.id === okr.cycle_id);
  const isCycleLocked = okrCycle?.status === "FROZEN" || okrCycle?.status === "CLOSED";
  const lifecycle = okr.okr_status || "ACTIVE";
  // Allow KR progress entry while OKR is still being prepared (DRAFT/REJECTED).
  // Once the OKR is submitted for approval (PENDING_APPROVAL), KR progress should be locked.
  const isExecutionActive = lifecycle === "ACTIVE" || lifecycle === "DRAFT" || lifecycle === "REJECTED";
  const canEditExecution = isExecutionActive && !isCycleLocked;
  const canSubmitProgress = canEditExecution && canSubmitOkrProgress(okr, user);
  const canEditStructure = canEditExecution && canManageOkrStructure(okr, user, canManage);

  // Add KR state
  const [krTitle, setKrTitle] = useState("");
  const [krTarget, setKrTarget] = useState("100");
  const [krUnit, setKrUnit] = useState("%");
  const [krWeight, setKrWeight] = useState("1");

  // Progress submission state
  const [newValue, setNewValue] = useState("");
  const [progressNotes, setProgressNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [ingestKrId, setIngestKrId] = useState<string | null>(null);

  const pct = okr.progress ?? 0;

  const handleAddKR = async () => {
    if (!krTitle.trim()) return;
    try {
      await api.createKeyResult(okr.id, {
        title: krTitle.trim(),
        target_value: parseFloat(krTarget) || 100,
        unit: krUnit || "%",
        weight: parseFloat(krWeight) || 1,
      });
      setKrTitle(""); setKrTarget("100"); setKrUnit("%"); setKrWeight("1");
      setAddKROpen(false);
      queryClient.invalidateQueries({ queryKey: ["objectives"] });
    } catch (e) { console.error(e); }
  };

  const handleSubmitProgress = async (krId: string) => {
    if (!newValue || submitting) return;
    setSubmitting(true);
    try {
      // Use the new progress submission endpoint (approval-gated)
      await api.submitProgressSubmission({
        key_result_id: krId,
        employee_value: parseFloat(newValue),
        employee_note: progressNotes || undefined,
      });
      setNewValue(""); setProgressNotes(""); setProgressOpen(null);
      queryClient.invalidateQueries({ queryKey: ["objectives"] });
      queryClient.invalidateQueries({ queryKey: ["pending-validations"] });
    } catch (e: any) {
      // Fallback to legacy endpoint if submissions not available
      try {
        await api.submitProgressUpdate(krId, {
          new_value: parseFloat(newValue),
          notes: progressNotes || undefined,
        });
        setNewValue(""); setProgressNotes(""); setProgressOpen(null);
        queryClient.invalidateQueries({ queryKey: ["objectives"] });
        queryClient.invalidateQueries({ queryKey: ["pending-validations"] });
      } catch (e2) { console.error(e2); }
    } finally {
      setSubmitting(false);
    }
  };

  // Determine progress bar color
  const progressBarColor = pct >= 75
    ? "bg-emerald-500"
    : pct >= 50
    ? "bg-amber-500"
    : "bg-rose-500";

  // Rating badge
  const ratingText = pct >= 90
    ? "Exceptional"
    : pct >= 75
    ? "On Track"
    : pct >= 60
    ? "At Risk"
    : "Off Track";

  const ratingColor = pct >= 75
    ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/30"
    : pct >= 60
    ? "text-amber-400 bg-amber-500/10 border-amber-500/30"
    : "text-rose-400 bg-rose-500/10 border-rose-500/30";

  const okrPendingValidations = pendingValidations.filter((v) => v.objective_id === okr.id);
  const showValidationPanel = canValidateProgress && okrPendingValidations.length > 0;

  return (
    <>
      <Card className="hover:shadow-lg transition-all border-border/60 overflow-hidden group">
        {/* Header */}
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-3 flex-1 min-w-0">
              <button onClick={() => setExpanded(!expanded)} className="mt-1 shrink-0 text-muted-foreground hover:text-foreground transition-colors">
                {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              </button>
              <div className="flex-1 min-w-0">
                <CardTitle className="text-sm font-semibold leading-tight">{okr.title}</CardTitle>
                {okr.description && <p className="mt-0.5 text-xs text-muted-foreground line-clamp-1">{okr.description}</p>}
                <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                  <Badge variant="outline" className={`text-[10px] px-1.5 py-0 ${LEVEL_COLORS[okr.level] || ""}`}>
                    {okr.level}
                  </Badge>
                  {okr.okr_status && okr.okr_status !== "ACTIVE" && (
                    <Badge variant="outline" className={`text-[10px] px-1.5 py-0 ${OKR_STATUS_BADGE[okr.okr_status] || ""}`}>
                      {okr.okr_status.replace("_", " ")}
                    </Badge>
                  )}
                  <Badge variant="outline" className={`text-[10px] px-1.5 py-0 ${ratingColor}`}>
                    {ratingText}
                  </Badge>
                  {okr.parent_title && (
                    <span className="flex items-center gap-0.5 text-[10px] text-muted-foreground">
                      <GitBranch className="h-3 w-3" /> {okr.parent_title}
                    </span>
                  )}
                  {okr.functional_parent_title && (
                    <span className="flex items-center gap-0.5 text-[10px] text-muted-foreground border-l border-border pl-1.5 ml-0.5 border-dashed">
                      <GitBranch className="h-3 w-3 text-muted-foreground/70" /> {okr.functional_parent_title} (Functional)
                    </span>
                  )}
                  {okr.owner_name && (
                    <span className="text-[10px] text-muted-foreground">• {okr.owner_name}</span>
                  )}
                  {okr.plant_name && <span className="text-[10px] text-muted-foreground">• {okr.plant_name}</span>}
                  {okr.department_name && <span className="text-[10px] text-muted-foreground">• {okr.department_name}</span>}
                  {okr.team_name && <span className="text-[10px] text-muted-foreground">• {okr.team_name}</span>}
                  {(okr.children_count ?? 0) > 0 && (
                    <span className="text-[10px] text-muted-foreground">• {okr.children_count} child OKR{(okr.children_count ?? 0) > 1 ? "s" : ""}</span>
                  )}
                </div>
                <OkrLifecycleActions okr={okr} />
              </div>
            </div>
            <div className="flex items-start gap-2 shrink-0">
              {showValidationPanel && (
                <OkrProgressValidationActions validations={okrPendingValidations} />
              )}
              {!showValidationPanel && canValidateProgress && (okr.pending_validations ?? 0) > 0 && (
                <Badge variant="outline" className="text-[9px] border-amber-500/30 text-amber-400 bg-amber-500/10 shrink-0">
                  <Clock className="h-2.5 w-2.5 mr-0.5" />
                  {okr.pending_validations} pending
                </Badge>
              )}
              <div className="text-right flex flex-col items-end gap-1">
                <div className="flex items-center gap-2">
                  <div className="text-lg font-bold tabular-nums leading-none">{pct}%</div>
                  <Badge variant={okr.status === "COMPLETED" ? "secondary" : "outline"} className="text-[10px]">
                    {okr.status}
                  </Badge>
                </div>
                {okr.okr_status === "PENDING_APPROVAL" && (okr.parent_id || okr.functional_parent_obj_id) && (
                  <div className="flex items-center gap-1 mt-0.5">
                    {okr.parent_id && (
                      <Badge variant="outline" className={`text-[8px] px-1 py-0 h-4 ${okr.creation_primary_approved_at ? 'text-emerald-500 border-emerald-500/30 bg-emerald-500/10' : 'text-amber-500 border-amber-500/30 bg-amber-500/10'}`}>
                        Primary {okr.creation_primary_approved_at ? '✓' : '⏳'}
                      </Badge>
                    )}
                    {okr.functional_parent_obj_id && (
                      <Badge variant="outline" className={`text-[8px] px-1 py-0 h-4 ${okr.creation_functional_approved_at ? 'text-emerald-500 border-emerald-500/30 bg-emerald-500/10' : 'text-amber-500 border-amber-500/30 bg-amber-500/10'}`}>
                        Functional {okr.creation_functional_approved_at ? '✓' : '⏳'}
                      </Badge>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
          {/* Progress bar */}
          <div className="mt-2">
            <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${progressBarColor}`}
                style={{ width: `${Math.min(pct, 100)}%` }}
              />
            </div>
          </div>
        </CardHeader>

        {/* Expanded: Key Results */}
        {expanded && (
          <CardContent className="pt-0">
            <div className="border-t border-border/40 pt-3 mt-1">
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide flex items-center gap-1.5">
                  Key Results
                  {okr.key_results && (
                    <span className="text-[10px] font-normal text-muted-foreground/60">
                      ({okr.key_results.length})
                    </span>
                  )}
                </h4>
                <div className="flex gap-1">
                  {canEditStructure && (
                    <Button size="sm" variant="ghost" className="h-6 text-xs gap-1" onClick={() => setAddKROpen(true)}>
                      <Plus className="h-3 w-3" /> Add KR
                    </Button>
                  )}
                  {canEditStructure && onDelete && (
                    <Button size="sm" variant="ghost" className="h-6 text-xs text-destructive" onClick={() => onDelete(okr.id)}>
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  )}
                </div>
              </div>

              {okr.key_results && okr.key_results.length > 0 ? (
                <div className="space-y-2">
                  {okr.key_results.map((kr) => {
                    const hasPending = (kr.pending_updates ?? 0) > 0;
                    const krValidations = okrPendingValidations.filter((v) => v.key_result_id === kr.id);
                    const approvedValue = kr.current_value ?? 0;
                    const displayValue =
                      hasPending && kr.pending_submitted_value != null
                        ? kr.pending_submitted_value
                        : approvedValue;
                    const krPct =
                      kr.progress_pct ??
                      (kr.target_value > 0
                        ? Math.min((displayValue / kr.target_value) * 100, 100)
                        : 0);
                    const krBarColor = krPct >= 75 ? "bg-emerald-500" : krPct >= 50 ? "bg-amber-500" : "bg-rose-500";
                    const krWeight = kr.weight || 1;

                    return (
                      <div key={kr.id} className="rounded-lg border border-border/40 bg-muted/20 p-2.5 hover:bg-muted/30 transition-colors">
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-medium">{kr.title}</p>
                            {hasPending && (
                              <p className="text-[9px] text-amber-400 flex items-center gap-1 mt-0.5">
                                <Clock className="h-2.5 w-2.5" />
                                {kr.pending_submitted_value != null ? (
                                  <>
                                    Submitted {kr.pending_submitted_value}/{kr.target_value} {kr.unit}
                                    {" "}— awaiting approval
                                  </>
                                ) : (
                                  <>
                                    {kr.pending_updates} pending approval{kr.pending_updates !== 1 ? "s" : ""}
                                  </>
                                )}
                              </p>
                            )}
                            {!hasPending && approvedValue > 0 && (
                              <p className="text-[9px] text-muted-foreground mt-0.5 tabular-nums">
                                Approved: {approvedValue}/{kr.target_value} {kr.unit}
                              </p>
                            )}
                          </div>
                          <div className="flex items-center gap-2 flex-wrap justify-end">
                            {/* Approval status badge */}
                            {hasPending && (
                              <Badge variant="outline" className="text-[9px] px-1 py-0 bg-amber-500/10 text-amber-400 border-amber-500/20 animate-pulse">
                                <Clock className="h-2 w-2 mr-0.5" />
                                Awaiting
                              </Badge>
                            )}
                            {canValidateProgress && krValidations.length > 0 && (
                              <OkrProgressValidationActions
                                validations={krValidations}
                                variant="inline"
                              />
                            )}
                            {kr.auto_ingest_active && (
                              <Badge variant="outline" className="text-[9px] px-1 py-0 gap-0.5 bg-cyan-500/10 text-cyan-400 border-cyan-500/30">
                                <Radio className="h-2 w-2" /> Live
                              </Badge>
                            )}
                            {/* Weight badge */}
                            <Badge variant="outline" className="text-[9px] px-1 py-0 gap-0.5 bg-blue-500/5 text-blue-400 border-blue-500/20">
                              <Weight className="h-2 w-2" /> W{krWeight}
                            </Badge>
                            {canEditStructure && (
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-5 text-[10px] px-1"
                                onClick={() => setIngestKrId(kr.id)}
                                title="Configure auto-update from MES/SCADA"
                              >
                                <Radio className="h-2.5 w-2.5" />
                              </Button>
                            )}
                            {/* Progress values */}
                            <span className="text-[10px] text-muted-foreground tabular-nums whitespace-nowrap">
                              {hasPending && kr.pending_submitted_value != null ? (
                                <>
                                  <span className="text-muted-foreground/70">{approvedValue}</span>
                                  <span className="mx-0.5">→</span>
                                  <span className="text-amber-400 font-medium">{displayValue}</span>
                                  /{kr.target_value} {kr.unit}
                                </>
                              ) : (
                                <>
                                  {approvedValue}/{kr.target_value} {kr.unit}
                                </>
                              )}
                            </span>
                            {/* Percentage */}
                            <span className={`text-[10px] font-semibold tabular-nums ${krPct >= 75 ? "text-emerald-400" : krPct >= 50 ? "text-amber-400" : "text-rose-400"}`}>
                              {Math.round(krPct)}%
                            </span>
                            {/* Submit progress */}
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-5 text-[10px] px-1.5 gap-0.5"
                              onClick={() => {
                                setProgressOpen(kr.id);
                                setNewValue(
                                  String(
                                    kr.pending_submitted_value ??
                                      kr.current_value ??
                                      0,
                                  ),
                                );
                                setProgressNotes(kr.pending_submitted_note ?? "");
                              }}
                              disabled={!canSubmitProgress}
                              title={
                                !canSubmitProgress
                                  ? okr.level === "TEAM"
                                    ? "Team progress is submitted by the team lead (OKR owner)"
                                    : okr.level === "INDIVIDUAL" && okr.owner_id !== user?.id
                                      ? "Only the assigned employee can submit progress"
                                      : !isExecutionActive
                                        ? "Progress entry disabled while OKR is pending approval"
                                        : isCycleLocked
                                          ? "Progress submission locked for this cycle"
                                          : "You cannot submit progress on this OKR"
                                  : "Submit Progress"
                              }
                            >
                              {!canSubmitProgress ? <Lock className="h-2.5 w-2.5" /> : <Send className="h-2.5 w-2.5" />}
                              {!canSubmitProgress ? "Locked" : "Submit"}
                            </Button>
                          </div>
                        </div>
                        {/* KR progress bar */}
                        <div className="mt-1.5 h-1 w-full rounded-full bg-muted overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${krBarColor}`}
                            style={{ width: `${Math.min(krPct, 100)}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-xs text-muted-foreground italic">No key results yet. Add key results to track progress.</p>
              )}

              {/* Weighted progress info */}
              {okr.key_results && okr.key_results.length > 0 && (
                <div className="mt-3 p-2 rounded-md bg-primary/5 border border-primary/10">
                  <p className="text-[10px] text-muted-foreground">
                    <span className="font-medium text-foreground/70">Weighted Progress:</span>{" "}
                    Progress = Σ(KR Progress × Weight) / Σ(Weights). Submissions require manager approval before cascading upward.
                  </p>
                </div>
              )}

              <div className="mt-3">
                <OkrCreationApprovalPanel okr={okr} />
              </div>
            </div>
          </CardContent>
        )}
      </Card>

      {/* Add KR Dialog */}
      <Dialog open={addKROpen} onOpenChange={setAddKROpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle>Add Key Result</DialogTitle></DialogHeader>
          <div className="grid gap-3 py-2">
            <div className="grid gap-1"><Label>Title</Label><Input value={krTitle} onChange={e => setKrTitle(e.target.value)} placeholder="e.g. Reduce defect rate to 1%" /></div>
            <div className="grid grid-cols-3 gap-2">
              <div className="grid gap-1"><Label>Target</Label><Input type="number" value={krTarget} onChange={e => setKrTarget(e.target.value)} /></div>
              <div className="grid gap-1"><Label>Unit</Label><Input value={krUnit} onChange={e => setKrUnit(e.target.value)} /></div>
              <div className="grid gap-1">
                <Label className="flex items-center gap-1">Weight <Weight className="h-3 w-3 text-muted-foreground" /></Label>
                <Input type="number" value={krWeight} onChange={e => setKrWeight(e.target.value)} min="1" max="5" />
              </div>
            </div>
            <p className="text-[10px] text-muted-foreground">
              Weight (1-5) determines how much this KR contributes to overall objective progress.
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddKROpen(false)}>Cancel</Button>
            <Button onClick={handleAddKR} disabled={!krTitle.trim()}>Add Key Result</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {ingestKrId && okr.key_results && (
        <KrIngestDialog
          kr={okr.key_results.find((k) => k.id === ingestKrId)!}
          open={!!ingestKrId}
          onOpenChange={(o) => !o && setIngestKrId(null)}
        />
      )}

      {/* Submit Progress Dialog */}
      <Dialog open={!!progressOpen} onOpenChange={() => setProgressOpen(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Send className="h-4 w-4 text-primary" />
              Submit Progress Update
            </DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <div className="p-2 rounded-md bg-amber-500/10 border border-amber-500/20">
              <p className="text-[10px] text-amber-300 flex items-center gap-1">
                <Clock className="h-3 w-3" />
                Your submission will be sent for manager approval before updating progress.
              </p>
            </div>
            <div className="grid gap-1">
              <Label>New Value</Label>
              <Input
                type="number"
                value={newValue}
                onChange={e => setNewValue(e.target.value)}
                placeholder="Enter current value"
              />
              {progressOpen && okr.key_results && (() => {
                const kr = okr.key_results.find((k) => k.id === progressOpen);
                if (!kr) return null;
                return (
                  <p className="text-[10px] text-muted-foreground tabular-nums">
                    Current approved: {kr.current_value ?? 0}/{kr.target_value} {kr.unit}
                    {kr.pending_submitted_value != null && (
                      <span className="text-amber-400">
                        {" "}· Pending: {kr.pending_submitted_value}/{kr.target_value} {kr.unit}
                      </span>
                    )}
                  </p>
                );
              })()}
            </div>
            <div className="grid gap-1">
              <Label>Notes (optional)</Label>
              <Textarea value={progressNotes} onChange={e => setProgressNotes(e.target.value)} rows={2} placeholder="Explain what was accomplished..." />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setProgressOpen(null)}>Cancel</Button>
            <Button
              onClick={() => progressOpen && handleSubmitProgress(progressOpen)}
              disabled={!newValue || submitting}
            >
              {submitting ? "Submitting..." : "Submit for Approval"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
