import { Loader2, Pencil, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { OrgNode } from "@/lib/api";

export interface OrgTypeTableSectionProps {
  rows: OrgNode[];
  isLoading: boolean;
  emptyTitle: string;
  emptyDescription: string;
  emptyCtaLabel: string;
  onEmptyCta: () => void;
  onAdd: () => void;
  onEdit: (node: OrgNode) => void;
  onDelete: (node: OrgNode) => void;
  deletePrefetchingId: string | null;
  addLabel: string;
}

export function OrgTypeTableSection({
  rows,
  isLoading,
  emptyTitle,
  emptyDescription,
  emptyCtaLabel,
  onEmptyCta,
  onAdd,
  onEdit,
  onDelete,
  deletePrefetchingId,
  addLabel,
}: OrgTypeTableSectionProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16 text-muted-foreground">
        <Loader2 className="mr-2 h-6 w-6 animate-spin" />
        Loading organization tree…
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-14 text-center">
        <p className="text-lg font-semibold">{emptyTitle}</p>
        <p className="mt-2 max-w-md text-sm text-muted-foreground">{emptyDescription}</p>
        <Button className="mt-6" onClick={onEmptyCta}>
          <Plus className="mr-2 h-4 w-4" />
          {emptyCtaLabel}
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={onAdd}>
          <Plus className="mr-2 h-4 w-4" />
          {addLabel}
        </Button>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Code</TableHead>
            <TableHead className="w-[200px]">Created</TableHead>
            <TableHead className="w-[100px] text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.id}>
              <TableCell className="font-medium">{row.name}</TableCell>
              <TableCell>
                {row.code ? <span className="font-mono text-xs">{row.code}</span> : "—"}
              </TableCell>
              <TableCell className="text-muted-foreground text-xs">
                {new Date(row.created_at).toLocaleString()}
              </TableCell>
              <TableCell className="text-right">
                <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => onEdit(row)}>
                  <Pencil className="h-4 w-4" />
                  <span className="sr-only">Edit</span>
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-destructive hover:text-destructive"
                  onClick={() => onDelete(row)}
                  disabled={deletePrefetchingId === row.id}
                >
                  {deletePrefetchingId === row.id ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                  <span className="sr-only">Delete</span>
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
