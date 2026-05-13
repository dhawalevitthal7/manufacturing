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
  GitBranch, Weight, CheckCircle, Clock, XCircle, AlertTriangle,
} from "lucide-react";
import { api } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";
import type { Objective } from "@/lib/api";

// ── Level colors ──
const LEVEL_COLORS: Record<string, string> = {
  ORGANIZATION: "bg-violet-500/15 text-violet-400 border-violet-500/30",
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
}

export function OKRCard({ objective: okr, canManage, onDelete }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [addKROpen, setAddKROpen] = useState(false);
  const [progressOpen, setProgressOpen] = useState<string | null>(null);
  const queryClient = useQueryClient();

  // Add KR state
  const [krTitle, setKrTitle] = useState("");
  const [krTarget, setKrTarget] = useState("100");
  const [krUnit, setKrUnit] = useState("%");
  const [krWeight, setKrWeight] = useState("1");

  // Progress submission state
  const [newValue, setNewValue] = useState("");
  const [progressNotes, setProgressNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

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
                  <Badge variant="outline" className={`text-[10px] px-1.5 py-0 ${ratingColor}`}>
                    {ratingText}
                  </Badge>
                  {okr.parent_title && (
                    <span className="flex items-center gap-0.5 text-[10px] text-muted-foreground">
                      <GitBranch className="h-3 w-3" /> {okr.parent_title}
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
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <div className="text-right">
                <div className="text-lg font-bold tabular-nums">{pct}%</div>
                <Badge variant={okr.status === "COMPLETED" ? "secondary" : "outline"} className="text-[10px]">
                  {okr.status}
                </Badge>
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
                  {canManage && (
                    <Button size="sm" variant="ghost" className="h-6 text-xs gap-1" onClick={() => setAddKROpen(true)}>
                      <Plus className="h-3 w-3" /> Add KR
                    </Button>
                  )}
                  {canManage && onDelete && (
                    <Button size="sm" variant="ghost" className="h-6 text-xs text-destructive" onClick={() => onDelete(okr.id)}>
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  )}
                </div>
              </div>

              {okr.key_results && okr.key_results.length > 0 ? (
                <div className="space-y-2">
                  {okr.key_results.map((kr) => {
                    const krPct = kr.progress_pct ?? (kr.target_value > 0 ? Math.min((kr.current_value / kr.target_value) * 100, 100) : 0);
                    const krBarColor = krPct >= 75 ? "bg-emerald-500" : krPct >= 50 ? "bg-amber-500" : "bg-rose-500";
                    const krWeight = kr.weight || 1;

                    return (
                      <div key={kr.id} className="rounded-lg border border-border/40 bg-muted/20 p-2.5 hover:bg-muted/30 transition-colors">
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-medium">{kr.title}</p>
                            {kr.pending_updates && kr.pending_updates > 0 && (
                              <p className="text-[9px] text-amber-400 flex items-center gap-1 mt-0.5">
                                <Clock className="h-2.5 w-2.5" />
                                {kr.pending_updates} pending approval{kr.pending_updates > 1 ? "s" : ""}
                              </p>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            {/* Approval status badge */}
                            {kr.pending_updates && kr.pending_updates > 0 && (
                              <Badge variant="outline" className="text-[9px] px-1 py-0 bg-amber-500/10 text-amber-400 border-amber-500/20 animate-pulse">
                                <Clock className="h-2 w-2 mr-0.5" />
                                Awaiting
                              </Badge>
                            )}
                            {/* Weight badge */}
                            <Badge variant="outline" className="text-[9px] px-1 py-0 gap-0.5 bg-blue-500/5 text-blue-400 border-blue-500/20">
                              <Weight className="h-2 w-2" /> W{krWeight}
                            </Badge>
                            {/* Progress values */}
                            <span className="text-[10px] text-muted-foreground tabular-nums whitespace-nowrap">
                              {kr.current_value}/{kr.target_value} {kr.unit}
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
                              onClick={() => setProgressOpen(kr.id)}
                            >
                              <Send className="h-2.5 w-2.5" /> Submit
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
              <Input type="number" value={newValue} onChange={e => setNewValue(e.target.value)} placeholder="Enter current value" />
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
