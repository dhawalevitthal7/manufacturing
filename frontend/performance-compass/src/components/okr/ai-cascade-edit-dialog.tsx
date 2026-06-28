import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, Plus, Save, Send, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, type AICascadeDraft, type KeyResultCreate } from "@/lib/api";

interface KrRow extends KeyResultCreate {
  key: string;
}

interface Props {
  draft: AICascadeDraft | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved?: () => void;
}

function toKrRows(draft: AICascadeDraft): KrRow[] {
  const krs = draft.key_results || [];
  if (krs.length === 0) {
    return [{ key: "new-0", title: "", target_value: 100, unit: "%", weight: 1 }];
  }
  return krs.map((kr, i) => ({
    key: kr.id || `kr-${i}`,
    title: kr.title,
    target_value: kr.target_value,
    unit: kr.unit || "%",
    weight: kr.weight ?? 1,
  }));
}

export function AiCascadeEditDialog({ draft, open, onOpenChange, onSaved }: Props) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [krRows, setKrRows] = useState<KrRow[]>([]);

  useEffect(() => {
    if (!draft || !open) return;
    setTitle(draft.title);
    setDescription(draft.description || "");
    setKrRows(toKrRows(draft));
  }, [draft, open]);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["ai-drafts"] });
    queryClient.invalidateQueries({ queryKey: ["parent-approval-queue"] });
    queryClient.invalidateQueries({ queryKey: ["objectives"] });
    queryClient.invalidateQueries({ queryKey: ["ai-versions", draft?.id] });
    queryClient.invalidateQueries({ queryKey: ["alignment-preview", draft?.id] });
    onSaved?.();
  };

  const saveDraft = useMutation({
    mutationFn: async (submitAfterSave: boolean) => {
      if (!draft) throw new Error("No draft selected");
      const trimmedTitle = title.trim();
      if (!trimmedTitle) throw new Error("Objective title is required");

      const key_results: KeyResultCreate[] = krRows
        .map((kr) => ({
          title: kr.title.trim(),
          target_value: Number(kr.target_value) || 0,
          unit: (kr.unit || "%").trim(),
          weight: kr.weight ?? 1,
        }))
        .filter((kr) => kr.title.length > 0);

      if (key_results.length === 0) {
        throw new Error("Add at least one key result with a title");
      }

      await api.reviewAiDraft(draft.id, {
        title: trimmedTitle,
        description: description.trim() || undefined,
        key_results,
      });

      if (submitAfterSave) {
        await api.submitAiDraftForParentApproval(draft.id);
      }
    },
    onSuccess: (_data, submitAfterSave) => {
      invalidate();
      toast.success(
        submitAfterSave
          ? "OKR updated and submitted for parent approval"
          : "Changes saved — review and submit when ready",
      );
      onOpenChange(false);
    },
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Failed to save changes");
    },
  });

  const updateKr = (key: string, patch: Partial<KrRow>) => {
    setKrRows((prev) => prev.map((kr) => (kr.key === key ? { ...kr, ...patch } : kr)));
  };

  const addKr = () => {
    setKrRows((prev) => [
      ...prev,
      { key: `new-${Date.now()}`, title: "", target_value: 100, unit: "%", weight: 1 },
    ]);
  };

  const removeKr = (key: string) => {
    setKrRows((prev) => (prev.length <= 1 ? prev : prev.filter((kr) => kr.key !== key)));
  };

  if (!draft) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Edit AI suggested OKR</DialogTitle>
          <DialogDescription>
            Customize the AI suggestion for your level, then save or submit to{" "}
            {draft.parent_title ? `"${draft.parent_title}"` : "your parent OKR"} for approval.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-1">
          <div className="space-y-2">
            <Label htmlFor="ai-edit-title">Objective</Label>
            <Input
              id="ai-edit-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Regional objective aligned with parent goal"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="ai-edit-desc">Description / your suggestions</Label>
            <Textarea
              id="ai-edit-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Explain how this OKR supports the parent, or note local priorities…"
              rows={3}
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Key results</Label>
              <Button type="button" size="sm" variant="outline" className="h-7 text-xs" onClick={addKr}>
                <Plus className="h-3 w-3 mr-1" /> Add KR
              </Button>
            </div>
            <div className="space-y-2">
              {krRows.map((kr, index) => (
                <div key={kr.key} className="rounded-md border border-border bg-muted/20 p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-muted-foreground">KR {index + 1}</span>
                    {krRows.length > 1 && (
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="h-6 w-6 p-0 text-destructive"
                        onClick={() => removeKr(kr.key)}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    )}
                  </div>
                  <Input
                    value={kr.title}
                    onChange={(e) => updateKr(kr.key, { title: e.target.value })}
                    placeholder="Measurable key result"
                    className="text-sm"
                  />
                  <div className="grid grid-cols-3 gap-2">
                    <Input
                      type="number"
                      value={kr.target_value}
                      onChange={(e) =>
                        updateKr(kr.key, { target_value: parseFloat(e.target.value) || 0 })
                      }
                      placeholder="Target"
                      className="text-sm"
                    />
                    <Input
                      value={kr.unit}
                      onChange={(e) => updateKr(kr.key, { unit: e.target.value })}
                      placeholder="Unit"
                      className="text-sm"
                    />
                    <Input
                      type="number"
                      min={1}
                      max={5}
                      value={kr.weight ?? 1}
                      onChange={(e) =>
                        updateKr(kr.key, { weight: parseFloat(e.target.value) || 1 })
                      }
                      placeholder="Weight"
                      className="text-sm"
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <DialogFooter className="flex-col gap-2 sm:flex-row sm:justify-end">
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={saveDraft.isPending}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={() => saveDraft.mutate(false)}
            disabled={saveDraft.isPending}
          >
            {saveDraft.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin mr-1" />
            ) : (
              <Save className="h-4 w-4 mr-1" />
            )}
            Save changes
          </Button>
          <Button
            type="button"
            onClick={() => saveDraft.mutate(true)}
            disabled={saveDraft.isPending}
          >
            {saveDraft.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin mr-1" />
            ) : (
              <Send className="h-4 w-4 mr-1" />
            )}
            Save & submit for approval
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
