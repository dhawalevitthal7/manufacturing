import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { OrgNode } from "@/lib/api";

export interface OrgNodeFormValues {
  name: string;
  code: string;
}

interface OrgNodeFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  submitLabel: string;
  initial?: OrgNode | null;
  isSubmitting: boolean;
  onSubmit: (values: OrgNodeFormValues) => void | Promise<void>;
}

export function OrgNodeFormDialog({
  open,
  onOpenChange,
  title,
  submitLabel,
  initial,
  isSubmitting,
  onSubmit,
}: OrgNodeFormDialogProps) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");

  useEffect(() => {
    if (!open) return;
    setName(initial?.name ?? "");
    setCode(initial?.code ?? "");
  }, [open, initial]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    await onSubmit({
      name: trimmed,
      code: code.trim(),
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label htmlFor="org-node-name">Name</Label>
              <Input
                id="org-node-name"
                value={name}
                onChange={(ev) => setName(ev.target.value)}
                placeholder="e.g. North America"
                autoComplete="off"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="org-node-code">Code (optional)</Label>
              <Input
                id="org-node-code"
                value={code}
                onChange={(ev) => setCode(ev.target.value)}
                placeholder="Short code for lists and reports"
                autoComplete="off"
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting || !name.trim()}>
              {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : submitLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
