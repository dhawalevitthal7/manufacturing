import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Loader2, Radio } from "lucide-react";
import { api, type KeyResult, type KRIngestSourceConfigure } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";

interface Props {
  kr: KeyResult;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function KrIngestDialog({ kr, open, onOpenChange }: Props) {
  const queryClient = useQueryClient();
  const [enabled, setEnabled] = useState(false);
  const [sourceSystem, setSourceSystem] = useState("SAP");
  const [metricTag, setMetricTag] = useState("");
  const [transform, setTransform] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newToken, setNewToken] = useState<string | null>(null);
  const [lastIngest, setLastIngest] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setNewToken(null);
    const src = kr.ingest_source;
    if (src) {
      setEnabled(src.is_active);
      setSourceSystem(src.source_system);
      setMetricTag(src.source_metric_tag || "");
      setTransform(src.transform_expr || "");
      setLastIngest(src.last_ingest_at || null);
    } else {
      setEnabled(false);
      setSourceSystem("SAP");
      setMetricTag("");
      setTransform("");
      setLastIngest(null);
    }
  }, [open, kr]);

  const save = async (rotateToken = false) => {
    if (!enabled) {
      setError("Turn on auto-update to save configuration.");
      return;
    }
    if (!metricTag.trim()) {
      setError("Metric tag is required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const body: KRIngestSourceConfigure = {
        source_system: sourceSystem.trim(),
        source_metric_tag: metricTag.trim(),
        transform_expr: transform.trim() || undefined,
        is_active: true,
        rotate_token: rotateToken || !kr.ingest_source,
      };
      const res = await api.configureKrIngestSource(kr.id, body);
      if (res.api_token) setNewToken(res.api_token);
      queryClient.invalidateQueries({ queryKey: ["objectives"] });
      if (res.ingest_source?.last_ingest_at) {
        setLastIngest(res.ingest_source.last_ingest_at);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Radio className="h-4 w-4 text-primary" />
            Auto-update — {kr.title}
          </DialogTitle>
        </DialogHeader>
        <div className="grid gap-3 py-1">
          <div className="flex items-center justify-between">
            <Label htmlFor="ingest-on">Enable auto-update</Label>
            <Switch id="ingest-on" checked={enabled} onCheckedChange={setEnabled} />
          </div>
          {enabled && (
            <>
              <div className="grid gap-1">
                <Label>Source system</Label>
                <Input value={sourceSystem} onChange={(e) => setSourceSystem(e.target.value)} placeholder="SAP, MES, PI_SYSTEM" />
              </div>
              <div className="grid gap-1">
                <Label>Metric tag</Label>
                <Input value={metricTag} onChange={(e) => setMetricTag(e.target.value)} placeholder="RAJ1.KILN1.TPD" />
              </div>
              <div className="grid gap-1">
                <Label>Transform (optional)</Label>
                <Input value={transform} onChange={(e) => setTransform(e.target.value)} placeholder="x or x / 1000" />
              </div>
              {lastIngest && (
                <p className="text-xs text-muted-foreground">Last ingest: {new Date(lastIngest).toLocaleString()}</p>
              )}
            </>
          )}
          {newToken && (
            <Alert>
              <AlertDescription className="text-xs break-all">
                Copy this ingest token now — it will not be shown again: <strong>{newToken}</strong>
              </AlertDescription>
            </Alert>
          )}
          {error && <p className="text-xs text-destructive">{error}</p>}
        </div>
        <DialogFooter className="flex-col sm:flex-row gap-2">
          {kr.ingest_source && (
            <Button type="button" variant="outline" onClick={() => save(true)} disabled={busy}>
              Rotate token
            </Button>
          )}
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
          <Button type="button" onClick={() => save(false)} disabled={busy || !enabled}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
