import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useCreateObjective, useParentOptions, usePlants, useDepartments,
  useTeams, useEmployees,
} from "@/lib/hooks";
import { useAuthStore } from "@/lib/stores/auth-store";
import { api } from "@/lib/api";
import { AIOKRChat } from "./ai-okr-chat";
import { Bot, Plus, Sparkles, Trash2, PenLine } from "lucide-react";
import type { ObjectiveLevel } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  allowedLevels: ObjectiveLevel[];
  defaultLevel?: ObjectiveLevel;
  defaultPlantId?: string;
}

const LEVEL_LABELS: Record<string, string> = {
  ORGANIZATION: "Organization OKR",
  PLANT: "Plant OKR",
  DEPARTMENT: "Department OKR",
  TEAM: "Team OKR",
  INDIVIDUAL: "Individual OKR",
};

interface InlineKR {
  title: string;
  target: string;
  unit: string;
  weight: string;
}

export function CreateOKRDialog({ open, onOpenChange, allowedLevels, defaultLevel, defaultPlantId }: Props) {
  const { user } = useAuthStore();
  const createObj = useCreateObjective();
  const queryClient = useQueryClient();

  const [mode, setMode] = useState<"manual" | "ai">("manual");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [level, setLevel] = useState<string>(defaultLevel || allowedLevels[0] || "INDIVIDUAL");
  const [parentId, setParentId] = useState<string>("");
  const [plantId, setPlantId] = useState<string>(defaultPlantId || "");
  const [deptId, setDeptId] = useState<string>("");
  const [teamId, setTeamId] = useState<string>("");
  const [ownerId, setOwnerId] = useState<string>("");
  const [inlineKRs, setInlineKRs] = useState<InlineKR[]>([]);

  useEffect(() => {
    if (defaultLevel) setLevel(defaultLevel);
    if (defaultPlantId) setPlantId(defaultPlantId);
  }, [defaultLevel, defaultPlantId]);

  useEffect(() => {
    setOwnerId("");
  }, [plantId, deptId, teamId]);

  const { data: plants = [] } = usePlants();
  const { data: departments = [] } = useDepartments(plantId || undefined);
  const { data: teams = [] } = useTeams(deptId || undefined);
  const { data: parentOptions = [] } = useParentOptions(level, plantId || undefined, deptId || undefined);
  const { data: employees = [], isLoading: employeesLoading } = useEmployees(
    level === "INDIVIDUAL" && plantId && deptId
      ? {
          plant_id: plantId || undefined,
          department_id: deptId || undefined,
          team_id: teamId || undefined,
        }
      : undefined
  );

  const needsPlant = ["PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"].includes(level);
  const needsDept = ["DEPARTMENT", "TEAM", "INDIVIDUAL"].includes(level);
  const needsTeam = ["TEAM", "INDIVIDUAL"].includes(level);
  const needsOwner = level === "INDIVIDUAL";

  // Determine department name for AI chat
  const selectedDept = (departments as any[]).find((d: any) => d.id === deptId);
  const departmentNameForAI = selectedDept?.name || (plants as any[]).find((p: any) => p.id === plantId)?.name || "Manufacturing";

  const addInlineKR = () => {
    setInlineKRs((prev) => [...prev, { title: "", target: "100", unit: "%", weight: "1" }]);
  };

  const removeInlineKR = (idx: number) => {
    setInlineKRs((prev) => prev.filter((_, i) => i !== idx));
  };

  const updateInlineKR = (idx: number, field: keyof InlineKR, value: string) => {
    setInlineKRs((prev) =>
      prev.map((kr, i) => (i === idx ? { ...kr, [field]: value } : kr))
    );
  };

  const handleAISuggestion = (suggestion: {
    title: string;
    description?: string;
    keyResults: { title: string; target: number; unit: string }[];
  }) => {
    setTitle(suggestion.title);
    if (suggestion.description) setDescription(suggestion.description);
    setInlineKRs(
      suggestion.keyResults.map((kr) => ({
        title: kr.title,
        target: String(kr.target),
        unit: kr.unit,
        weight: "1",
      }))
    );
    setMode("manual"); // Switch to manual to let user review/edit
  };

  const handleSubmit = async () => {
    if (!title.trim()) return;
    try {
      // Create objective
      const obj = await createObj.mutateAsync({
        title: title.trim(),
        description: description.trim() || undefined,
        level: level as ObjectiveLevel,
        parent_id: parentId || undefined,
        plant_id: plantId || undefined,
        department_id: deptId || undefined,
        team_id: teamId || undefined,
        owner_id: needsOwner && ownerId ? ownerId : undefined,
      });

      // Create inline key results
      for (const kr of inlineKRs) {
        if (kr.title.trim()) {
          try {
            await api.createKeyResult(obj.id, {
              title: kr.title.trim(),
              target_value: parseFloat(kr.target) || 100,
              unit: kr.unit || "%",
              weight: parseFloat(kr.weight) || 1,
            });
          } catch (e) {
            console.error("Failed to create KR:", e);
          }
        }
      }

      // Invalidate queries
      queryClient.invalidateQueries({ queryKey: ["objectives"] });
      queryClient.invalidateQueries({ queryKey: ["progress-summary"] });
      queryClient.invalidateQueries({ queryKey: ["alignment-tree"] });

      // Reset
      setTitle("");
      setDescription("");
      setParentId("");
      setOwnerId("");
      setInlineKRs([]);
      onOpenChange(false);
    } catch (e) {
      console.error(e);
    }
  };

  const resetAll = () => {
    setTitle("");
    setDescription("");
    setParentId("");
    setOwnerId("");
    setInlineKRs([]);
    setMode("manual");
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) resetAll(); onOpenChange(v); }}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto p-0">
        <DialogHeader className="px-6 pt-5 pb-3 border-b border-border/40">
          <div className="flex items-center justify-between">
            <DialogTitle className="text-lg">Create {LEVEL_LABELS[level] || "OKR"}</DialogTitle>
            <div className="flex items-center gap-1 bg-muted/50 rounded-lg p-0.5">
              <button
                onClick={() => setMode("manual")}
                className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-[10px] font-medium transition-all ${
                  mode === "manual"
                    ? "bg-background shadow-sm text-foreground"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <PenLine className="h-3 w-3" /> Manual
              </button>
              <button
                onClick={() => setMode("ai")}
                className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-[10px] font-medium transition-all ${
                  mode === "ai"
                    ? "bg-gradient-to-r from-violet-500/20 to-blue-500/20 shadow-sm text-violet-400"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <Bot className="h-3 w-3" /> AI Assistant
              </button>
            </div>
          </div>
        </DialogHeader>

        <div className="px-6 py-4">
          {mode === "ai" ? (
            <AIOKRChat
              departmentName={departmentNameForAI}
              hierarchyLevel={level}
              quarter="Q2"
              year={2026}
              parentObjectiveId={parentId || undefined}
              onApplySuggestion={handleAISuggestion}
              onImplemented={() => {
                // Invalidate queries after OKR auto-creation
                queryClient.invalidateQueries({ queryKey: ["objectives"] });
                queryClient.invalidateQueries({ queryKey: ["progress-summary"] });
                queryClient.invalidateQueries({ queryKey: ["alignment-tree"] });
                // Close dialog
                resetAll();
                onOpenChange(false);
              }}
            />
          ) : (
            <div className="grid gap-4">
              {/* Level */}
              <div className="grid gap-1.5">
                <Label>OKR Level</Label>
                <Select value={level} onValueChange={(v) => { setLevel(v); setParentId(""); }}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {allowedLevels.map((l) => (
                      <SelectItem key={l} value={l}>{LEVEL_LABELS[l] || l}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Title */}
              <div className="grid gap-1.5">
                <Label>Objective Title</Label>
                <Input
                  placeholder="e.g. Increase production efficiency by 20%"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </div>

              {/* Description */}
              <div className="grid gap-1.5">
                <Label>Description (optional)</Label>
                <Textarea
                  placeholder="Describe the objective..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={2}
                />
              </div>

              {/* Plant selector */}
              {needsPlant && (
                <div className="grid gap-1.5">
                  <Label>Plant</Label>
                  <Select value={plantId} onValueChange={(v) => { setPlantId(v); setDeptId(""); setTeamId(""); }}>
                    <SelectTrigger><SelectValue placeholder="Select plant" /></SelectTrigger>
                    <SelectContent>
                      {(plants as any[]).map((p: any) => (
                        <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {/* Department selector */}
              {needsDept && plantId && (
                <div className="grid gap-1.5">
                  <Label>Department</Label>
                  <Select value={deptId} onValueChange={(v) => { setDeptId(v); setTeamId(""); }}>
                    <SelectTrigger><SelectValue placeholder="Select department" /></SelectTrigger>
                    <SelectContent>
                      {(departments as any[]).map((d: any) => (
                        <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {/* Team selector */}
              {needsTeam && deptId && (
                <div className="grid gap-1.5">
                  <Label>Team (optional)</Label>
                  <Select
                    value={teamId || "__any__"}
                    onValueChange={(v) => setTeamId(v === "__any__" ? "" : v)}
                  >
                    <SelectTrigger><SelectValue placeholder="All teams in department" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__any__">All teams in department</SelectItem>
                      {(teams as any[]).map((t: any) => (
                        <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {/* Owner selector */}
              {needsOwner && plantId && deptId && (
                <div className="grid gap-1.5">
                  <Label>Assign To (Employee)</Label>
                  <Select value={ownerId} onValueChange={setOwnerId}>
                    <SelectTrigger>
                      <SelectValue
                        placeholder={
                          employeesLoading
                            ? "Loading employees…"
                            : (employees as any[]).length
                              ? "Select employee"
                              : "No employees in this scope"
                        }
                      />
                    </SelectTrigger>
                    <SelectContent>
                      {(employees as any[]).map((e: any) => (
                        <SelectItem key={e.id} value={e.id}>
                          {e.name} ({e.system_role})
                        </SelectItem>
                      ))}
                      {!employeesLoading && (employees as any[]).length === 0 && (
                        <SelectItem value="__empty" disabled>
                          No employees match — check team roster and User assignments
                        </SelectItem>
                      )}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {/* Parent OKR for cascading */}
              {parentOptions.length > 0 && (
                <div className="grid gap-1.5">
                  <Label>Align to Parent OKR (cascade)</Label>
                  <Select value={parentId} onValueChange={setParentId}>
                    <SelectTrigger><SelectValue placeholder="Select parent (optional)" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">— No parent —</SelectItem>
                      {parentOptions.map((p) => (
                        <SelectItem key={p.id} value={p.id}>
                          [{p.level}] {p.title} ({p.progress}%)
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {/* Inline Key Results */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-sm font-semibold">Key Results</Label>
                  <Button size="sm" variant="outline" onClick={addInlineKR} className="h-7 text-xs gap-1">
                    <Plus className="h-3 w-3" /> Add KR
                  </Button>
                </div>

                {inlineKRs.length === 0 && (
                  <p className="text-xs text-muted-foreground italic">
                    Add key results to track measurable progress. You can also add them after creating the OKR.
                  </p>
                )}

                {inlineKRs.map((kr, i) => (
                  <div key={i} className="grid grid-cols-[1fr_80px_60px_50px_28px] gap-1.5 items-end">
                    <div>
                      {i === 0 && <Label className="text-[10px]">Title</Label>}
                      <Input
                        value={kr.title}
                        onChange={(e) => updateInlineKR(i, "title", e.target.value)}
                        placeholder="e.g. Reduce defect rate"
                        className="h-8 text-xs"
                      />
                    </div>
                    <div>
                      {i === 0 && <Label className="text-[10px]">Target</Label>}
                      <Input
                        type="number"
                        value={kr.target}
                        onChange={(e) => updateInlineKR(i, "target", e.target.value)}
                        className="h-8 text-xs"
                      />
                    </div>
                    <div>
                      {i === 0 && <Label className="text-[10px]">Unit</Label>}
                      <Input
                        value={kr.unit}
                        onChange={(e) => updateInlineKR(i, "unit", e.target.value)}
                        className="h-8 text-xs"
                      />
                    </div>
                    <div>
                      {i === 0 && <Label className="text-[10px]">Wt</Label>}
                      <Input
                        type="number"
                        value={kr.weight}
                        onChange={(e) => updateInlineKR(i, "weight", e.target.value)}
                        min="1"
                        max="5"
                        className="h-8 text-xs"
                      />
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => removeInlineKR(i)}
                      className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <DialogFooter className="px-6 py-3 border-t border-border/40">
          <Button variant="outline" onClick={() => { resetAll(); onOpenChange(false); }}>Cancel</Button>
          {mode === "ai" ? (
            <Button
              variant="outline"
              onClick={() => setMode("manual")}
              className="border-violet-500/30 text-violet-400 hover:bg-violet-500/10"
            >
              <PenLine className="h-3.5 w-3.5 mr-1" /> Switch to Manual
            </Button>
          ) : (
            <Button onClick={handleSubmit} disabled={!title.trim() || createObj.isPending}>
              {createObj.isPending ? "Creating..." : "Create OKR"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
