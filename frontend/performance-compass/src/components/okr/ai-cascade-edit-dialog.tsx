import { useCallback, useEffect, useRef, useState } from "react";
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

function toKrRows(draft: AICascadeDraft, counter: { current: number }): KrRow[] {
  const krs = draft.key_results || [];
  if (krs.length === 0) {
    counter.current += 1;
    return [{ key: `kr-${counter.current}`, title: "", target_value: 100, unit: "%", weight: 1 }];
  }
  return krs.map((kr, i) => {
    counter.current += 1;
    return {
      key: kr.id || `kr-${counter.current}-${i}`,
      title: kr.title,
      target_value: kr.target_value,
      unit: kr.unit || "%",
      weight: kr.weight ?? 1,
    };
  });
}

export function AiCascadeEditDialog({ draft, open, onOpenChange, onSaved }: Props) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [krRows, setKrRows] = useState<KrRow[]>([]);

  const initializedDraftId = useRef<string | null>(null);
  const krKeyCounter = useRef(0);
  const krListEndRef = useRef<HTMLDivElement>(null);

  // Load draft fields only when the dialog opens for a given OKR — never reset while editing.
  useEffect(() => {
    if (!open) {
      initializedDraftId.current = null;
      return;
    }
    if (!draft?.id) return;
    if (initializedDraftId.current === draft.id) return;

    initializedDraftId.current = draft.id;
    krKeyCounter.current = 0;
    setTitle(draft.title);
    setDescription(draft.description || "");
    setKrRows(toKrRows(draft, krKeyCounter));
    // Intentionally only re-init when dialog opens or OKR id changes — not on every draft field update.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, draft?.id]);

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

  const updateKr = useCallback((key: string, patch: Partial<KrRow>) => {
    setKrRows((prev) => prev.map((kr) => (kr.key === key ? { ...kr, ...patch } : kr)));
  }, []);

  const addKr = useCallback((event: React.MouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
    event.stopPropagation();

    krKeyCounter.current += 1;
    const newKey = `kr-new-${krKeyCounter.current}`;

    setKrRows((prev) => [
      ...prev,
      { key: newKey, title: "", target_value: 100, unit: "%", weight: 1 },
    ]);

    requestAnimationFrame(() => {
      krListEndRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
  }, []);

  const removeKr = useCallback((key: string) => {
    setKrRows((prev) => {
      if (prev.length <= 1) {
        toast.error("At least one key result is required");
        return prev;
      }
      return prev.filter((kr) => kr.key !== key);
    });
  }, []);

  if (!draft) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[90vh] w-[min(calc(100vw-2rem),52rem)] max-w-none flex-col gap-0 overflow-hidden p-0 sm:rounded-lg">
        <DialogHeader className="shrink-0 space-y-1.5 border-b border-border px-6 py-5 pr-12">
          <DialogTitle>Edit AI suggested OKR</DialogTitle>
          <DialogDescription className="text-left">
            Customize the AI suggestion for your level, then save or submit to{" "}
            {draft.parent_title ? `"${draft.parent_title}"` : "your parent OKR"} for approval.
          </DialogDescription>
        </DialogHeader>

        <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-6 py-4">
          <div className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="ai-edit-title">Objective</Label>
              <Input
                id="ai-edit-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Regional objective aligned with parent goal"
                className="w-full"
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
                className="w-full resize-y"
              />
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <Label className="shrink-0">Key results ({krRows.length})</Label>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-8 shrink-0 text-xs"
                  onClick={addKr}
                >
                  <Plus className="h-3 w-3 mr-1" /> Add KR
                </Button>
              </div>

              <div className="space-y-3">
                {krRows.map((kr, index) => (
                  <div
                    key={kr.key}
                    className="w-full min-w-0 rounded-md border border-border bg-muted/20 p-4 space-y-3"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-medium text-muted-foreground">
                        Key result {index + 1}
                      </span>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="h-7 w-7 shrink-0 p-0 text-destructive hover:text-destructive"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          removeKr(kr.key);
                        }}
                        aria-label={`Remove key result ${index + 1}`}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>

                    <div className="space-y-1.5">
                      <Label className="text-[11px] text-muted-foreground">Title</Label>
                      <Input
                        value={kr.title}
                        onChange={(e) => updateKr(kr.key, { title: e.target.value })}
                        placeholder="Measurable key result"
                        className="w-full min-w-0 text-sm"
                      />
                    </div>

                    <div className="grid grid-cols-3 gap-3">
                      <div className="min-w-0 space-y-1.5">
                        <Label className="text-[11px] text-muted-foreground">Target</Label>
                        <Input
                          type="number"
                          value={kr.target_value}
                          onChange={(e) =>
                            updateKr(kr.key, { target_value: parseFloat(e.target.value) || 0 })
                          }
                          placeholder="100"
                          className="w-full min-w-0 text-sm"
                        />
                      </div>
                      <div className="min-w-0 space-y-1.5">
                        <Label className="text-[11px] text-muted-foreground">Unit</Label>
                        <Input
                          value={kr.unit}
                          onChange={(e) => updateKr(kr.key, { unit: e.target.value })}
                          placeholder="%"
                          className="w-full min-w-0 text-sm"
                        />
                      </div>
                      <div className="min-w-0 space-y-1.5">
                        <Label className="text-[11px] text-muted-foreground">Weight</Label>
                        <Input
                          type="number"
                          min={1}
                          max={5}
                          value={kr.weight ?? 1}
                          onChange={(e) =>
                            updateKr(kr.key, { weight: parseFloat(e.target.value) || 1 })
                          }
                          placeholder="1"
                          className="w-full min-w-0 text-sm"
                        />
                      </div>
                    </div>
                  </div>
                ))}
                <div ref={krListEndRef} />
              </div>
            </div>
          </div>
        </div>

        <DialogFooter className="shrink-0 flex-wrap gap-2 border-t border-border px-6 py-4 sm:justify-end">
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
};
