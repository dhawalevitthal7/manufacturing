import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  AlertCircle,
  Send,
  Loader2,
  CheckCircle2,
  TrendingUp,
} from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";

interface KeyResult {
  id: string;
  title: string;
  target_value: number;
  current_value: number;
  unit: string;
  weight?: number;
  progress_pct?: number;
}

interface Props {
  keyResult: KeyResult;
  onSubmitSuccess?: () => void;
}

export function ProgressSubmissionForm({
  keyResult,
  onSubmitSuccess,
}: Props) {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [newValue, setNewValue] = useState<string>(keyResult.current_value.toString());
  const [notes, setNotes] = useState("");
  const [blockers, setBlockers] = useState("");
  const [evidenceUrl, setEvidenceUrl] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const progressPct = keyResult.current_value / keyResult.target_value * 100;
  const projectedPct = parseFloat(newValue || "0") / keyResult.target_value * 100;

  const handleSubmit = async () => {
    if (!newValue) {
      setError("Please enter a new value");
      return;
    }

    setIsLoading(true);
    setError("");
    setSuccess("");

    try {
      await api.submitProgressUpdate(keyResult.id, {
        new_value: parseFloat(newValue),
        notes: notes || undefined,
        blockers: blockers || undefined,
        evidence_url: evidenceUrl || undefined,
      });

      setSuccess("Progress update submitted successfully!");
      setNewValue(keyResult.current_value.toString());
      setNotes("");
      setBlockers("");
      setEvidenceUrl("");
      
      // Reset dialog after success
      setTimeout(() => {
        setDialogOpen(false);
        setSuccess("");
      }, 1500);

      queryClient.invalidateQueries({ queryKey: ["objectives"] });
      queryClient.invalidateQueries({ queryKey: ["pending-validations"] });
      onSubmitSuccess?.();
    } catch (e: any) {
      setError(e.message || "Failed to submit progress update");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      <Button
        size="sm"
        variant="outline"
        className="h-7 text-xs"
        onClick={() => setDialogOpen(true)}
      >
        <TrendingUp className="h-3 w-3 mr-1" />
        Update Progress
      </Button>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-base">Update Progress</DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {/* KR Info */}
            <div className="p-3 bg-muted/50 rounded-lg border border-border/50">
              <p className="text-xs font-medium text-muted-foreground mb-1">
                Key Result
              </p>
              <p className="text-sm font-medium">{keyResult.title}</p>
              <div className="text-xs text-muted-foreground mt-2">
                Target: {keyResult.target_value} {keyResult.unit}
              </div>
            </div>

            {/* Current Progress */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className="text-xs font-medium">Current Progress</Label>
                <span className="text-xs font-medium">
                  {keyResult.current_value} / {keyResult.target_value}{" "}
                  {keyResult.unit}
                </span>
              </div>
              <Progress value={Math.min(progressPct, 100)} className="h-2" />
              <p className="text-xs text-muted-foreground">
                {Math.round(progressPct)}% complete
              </p>
            </div>

            {/* New Value Input */}
            <div className="space-y-2">
              <Label htmlFor="newValue" className="text-xs font-medium">
                New Value
              </Label>
              <div className="flex items-center gap-2">
                <Input
                  id="newValue"
                  type="number"
                  placeholder="Enter new value"
                  value={newValue}
                  onChange={(e) => setNewValue(e.target.value)}
                  className="text-xs"
                />
                <span className="text-xs font-medium text-muted-foreground px-2">
                  {keyResult.unit}
                </span>
              </div>
            </div>

            {/* Projected Progress */}
            {newValue && parseFloat(newValue) !== keyResult.current_value && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-xs font-medium">Projected Progress</Label>
                  <span className="text-xs font-medium text-emerald-600">
                    {parseFloat(newValue)} / {keyResult.target_value}{" "}
                    {keyResult.unit}
                  </span>
                </div>
                <Progress
                  value={Math.min(projectedPct, 100)}
                  className="h-2"
                />
                <p className="text-xs text-emerald-600">
                  {Math.round(projectedPct)}% projected
                </p>
              </div>
            )}

            {/* Notes */}
            <div className="space-y-2">
              <Label htmlFor="notes" className="text-xs font-medium">
                Progress Notes (Optional)
              </Label>
              <Textarea
                id="notes"
                placeholder="What progress did you make? Any updates?"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="text-xs min-h-20"
              />
            </div>

            {/* Blockers */}
            <div className="space-y-2">
              <Label htmlFor="blockers" className="text-xs font-medium">
                Blockers/Challenges (Optional)
              </Label>
              <Textarea
                id="blockers"
                placeholder="Any challenges or blockers preventing progress?"
                value={blockers}
                onChange={(e) => setBlockers(e.target.value)}
                className="text-xs min-h-16"
              />
            </div>

            {/* Evidence URL */}
            <div className="space-y-2">
              <Label htmlFor="evidence" className="text-xs font-medium">
                Evidence/Reference URL (Optional)
              </Label>
              <Input
                id="evidence"
                type="url"
                placeholder="Link to supporting document or metric"
                value={evidenceUrl}
                onChange={(e) => setEvidenceUrl(e.target.value)}
                className="text-xs"
              />
            </div>

            {error && (
              <Alert variant="destructive" className="text-xs">
                <AlertCircle className="h-3 w-3" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {success && (
              <Alert className="border-emerald-500/30 bg-emerald-500/10 text-emerald-700 text-xs">
                <CheckCircle2 className="h-3 w-3" />
                <AlertDescription>{success}</AlertDescription>
              </Alert>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDialogOpen(false)}
              disabled={isLoading}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleSubmit}
              disabled={isLoading || !newValue}
            >
              {isLoading ? (
                <Loader2 className="h-3 w-3 mr-1 animate-spin" />
              ) : (
                <Send className="h-3 w-3 mr-1" />
              )}
              Submit Update
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
