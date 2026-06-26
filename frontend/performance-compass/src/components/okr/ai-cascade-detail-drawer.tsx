import { useQuery } from "@tanstack/react-query";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Loader2, GitCompare, History } from "lucide-react";
import { api, type AICascadeDraft } from "@/lib/api";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface Props {
  draft: AICascadeDraft | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AiCascadeDetailDrawer({ draft, open, onOpenChange }: Props) {
  const objId = draft?.id ?? "";

  const { data: alignment, isLoading: alignLoading } = useQuery({
    queryKey: ["alignment-preview", objId],
    queryFn: () => api.getAiAlignmentPreview(objId),
    enabled: open && !!objId,
  });

  const { data: versions = [], isLoading: versionsLoading } = useQuery({
    queryKey: ["ai-versions", objId],
    queryFn: () => api.getAiCascadeVersions(objId),
    enabled: open && !!objId,
  });

  const { data: diff, isLoading: diffLoading } = useQuery({
    queryKey: ["ai-diff", objId],
    queryFn: () => api.getAiCascadeDiff(objId),
    enabled: open && !!objId && versions.length > 1,
  });

  if (!draft) return null;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="text-base">{draft.title}</SheetTitle>
          <SheetDescription>
            Parent: {draft.parent_title || "—"} · {draft.level}
          </SheetDescription>
        </SheetHeader>

        <Tabs defaultValue="alignment" className="mt-4">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="alignment" className="text-xs">
              <GitCompare className="h-3 w-3 mr-1" /> Alignment
            </TabsTrigger>
            <TabsTrigger value="history" className="text-xs">
              <History className="h-3 w-3 mr-1" /> History
            </TabsTrigger>
          </TabsList>

          <TabsContent value="alignment" className="mt-3 space-y-3">
            {alignLoading ? (
              <Loader2 className="h-5 w-5 animate-spin mx-auto" />
            ) : alignment ? (
              <>
                <div className="flex flex-wrap gap-2">
                  {alignment.alignment_score != null && (
                    <Badge variant="default">
                      Alignment {Math.round(Number(alignment.alignment_score))}%
                    </Badge>
                  )}
                  {alignment.confidence != null && (
                    <Badge variant="outline">
                      Confidence {Math.round(Number(alignment.confidence) * 100)}%
                    </Badge>
                  )}
                  {draft.ai_total_tokens != null && (
                    <Badge variant="secondary">{draft.ai_total_tokens} tokens</Badge>
                  )}
                </div>
                {alignment.reasoning && (
                  <p className="text-xs text-muted-foreground italic">{alignment.reasoning}</p>
                )}
                <div className="space-y-2">
                  <p className="text-xs font-medium">Parent ({alignment.parent_level})</p>
                  <p className="text-sm">{alignment.parent_title}</p>
                  <ul className="text-xs space-y-1 rounded border p-2 bg-muted/30">
                    {alignment.parent_key_results.map((kr, i) => (
                      <li key={i} className="flex justify-between">
                        <span>{kr.title}</span>
                        <span>{kr.target_value} {kr.unit}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="space-y-2">
                  <p className="text-xs font-medium">Child ({alignment.child_level})</p>
                  <p className="text-sm">{alignment.child_title}</p>
                  <ul className="text-xs space-y-1 rounded border p-2 bg-muted/30">
                    {alignment.child_key_results.map((kr, i) => (
                      <li key={i} className="flex justify-between">
                        <span>{kr.title}</span>
                        <span>{kr.target_value} {kr.unit}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">No alignment data.</p>
            )}
          </TabsContent>

          <TabsContent value="history" className="mt-3 space-y-3">
            {versionsLoading ? (
              <Loader2 className="h-5 w-5 animate-spin mx-auto" />
            ) : (
              <>
                {diff && !diffLoading && (
                  <div className="rounded border p-3 text-xs space-y-1 bg-muted/20">
                    <p className="font-medium">Latest diff (v{diff.previous.version} → v{diff.current.version})</p>
                    {diff.title_changed && (
                      <p><span className="text-muted-foreground">Title:</span> {diff.previous.title} → {diff.current.title}</p>
                    )}
                    {diff.description_changed && (
                      <p><span className="text-muted-foreground">Description changed</span></p>
                    )}
                  </div>
                )}
                <ul className="space-y-2">
                  {versions.map((v) => (
                    <li key={v.id} className="rounded border p-2 text-xs">
                      <div className="flex justify-between">
                        <Badge variant="outline" className="text-[10px]">{v.change_type}</Badge>
                        <span className="text-muted-foreground">v{v.version}</span>
                      </div>
                      <p className="mt-1 font-medium">{v.title}</p>
                      {v.created_at && (
                        <p className="text-muted-foreground mt-0.5">
                          {new Date(v.created_at).toLocaleString()}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </TabsContent>
        </Tabs>
      </SheetContent>
    </Sheet>
  );
}
