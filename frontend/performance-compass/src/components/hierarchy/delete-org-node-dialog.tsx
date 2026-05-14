import { Loader2 } from "lucide-react";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import type { OrgNode } from "@/lib/api";

interface DeleteOrgNodeDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  node: OrgNode | null;
  kindLabel: string;
  isDeleting: boolean;
  deleteError: string | null;
  onConfirmDelete: () => void;
}

export function DeleteOrgNodeDialog({
  open,
  onOpenChange,
  node,
  kindLabel,
  isDeleting,
  deleteError,
  onConfirmDelete,
}: DeleteOrgNodeDialogProps) {
  const childCount = node?.children?.length ?? 0;
  const hasChildren = childCount > 0;
  const noun = childCount === 1 ? "node" : "nodes";

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete {kindLabel}?</AlertDialogTitle>
          <AlertDialogDescription>
            {node ? (
              <>
                This will permanently remove <span className="font-medium text-foreground">{node.name}</span>
                {node.code ? (
                  <>
                    {" "}
                    (<span className="font-mono text-xs">{node.code}</span>)
                  </>
                ) : null}
                . This cannot be undone.
              </>
            ) : null}
          </AlertDialogDescription>
        </AlertDialogHeader>
        {deleteError ? (
          <p className="text-sm text-destructive" role="alert">
            {deleteError}
          </p>
        ) : null}
        <AlertDialogFooter className="flex-col gap-2 sm:flex-col sm:space-x-0">
          {hasChildren ? (
            <>
              <Button type="button" variant="destructive" className="w-full sm:w-full" disabled>
                Cannot delete: contains {childCount} child {noun}.
              </Button>
              <AlertDialogCancel className="w-full sm:mt-0">Close</AlertDialogCancel>
            </>
          ) : (
            <div className="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <AlertDialogCancel disabled={isDeleting}>Close</AlertDialogCancel>
              <Button
                type="button"
                variant="destructive"
                disabled={isDeleting || !node}
                onClick={onConfirmDelete}
              >
                {isDeleting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Deleting…
                  </>
                ) : (
                  "Delete"
                )}
              </Button>
            </div>
          )}
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
