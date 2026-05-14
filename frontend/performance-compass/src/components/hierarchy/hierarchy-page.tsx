import { useMemo, useState, useEffect } from "react";
import { Lock, MapPin, Building2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useAuthStore } from "@/lib/stores/auth-store";
import {
  useOrgTree,
  useCreateRegion,
  useCreateCorporateFunction,
  useUpdateOrgNode,
  useDeleteOrgNode,
  useOrgNodeDetail,
} from "@/lib/hooks";
import { flattenOrgNodes } from "@/lib/org-tree-utils";
import type { OrgNode } from "@/lib/api";
import { OrgNodeFormDialog, type OrgNodeFormValues } from "./org-node-form-dialog";
import { DeleteOrgNodeDialog } from "./delete-org-node-dialog";
import { OrgTypeTableSection } from "./org-type-table-section";

type TabKey = "regions" | "corporate";

interface FormContext {
  mode: "create" | "edit";
  tab: TabKey;
  node?: OrgNode;
}

export function HierarchyPage() {
  const { permissions } = useAuthStore();
  const isSuperAdmin = permissions?.system_role === "SUPER_ADMIN";

  const treeQuery = useOrgTree(isSuperAdmin);
  const createRegion = useCreateRegion();
  const createCorp = useCreateCorporateFunction();
  const updateNode = useUpdateOrgNode();
  const deleteNode = useDeleteOrgNode();

  const [formCtx, setFormCtx] = useState<FormContext | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    if (formCtx) setFormError(null);
  }, [formCtx]);

  const deleteDetailQuery = useOrgNodeDetail(deleteTargetId, !!deleteTargetId);
  const deleteDetailMatches =
    !!deleteTargetId &&
    deleteDetailQuery.data?.id === deleteTargetId &&
    deleteDetailQuery.isSuccess;
  const deleteDialogOpen = deleteDetailMatches;
  const deletePrefetching =
    !!deleteTargetId && deleteDetailQuery.isFetching && !deleteDetailMatches;

  useEffect(() => {
    if (!deleteTargetId || !deleteDetailQuery.isError) return;
    const msg =
      deleteDetailQuery.error instanceof Error
        ? deleteDetailQuery.error.message
        : "Could not load node details.";
    setDeleteError(msg);
    setDeleteTargetId(null);
  }, [deleteTargetId, deleteDetailQuery.isError, deleteDetailQuery.error]);

  const flatNodes = useMemo(() => {
    if (!treeQuery.data) return [];
    return flattenOrgNodes(treeQuery.data);
  }, [treeQuery.data]);

  const regions = useMemo(
    () =>
      flatNodes
        .filter((n) => n.node_type === "REGION")
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()),
    [flatNodes],
  );

  const corporateFunctions = useMemo(
    () =>
      flatNodes
        .filter((n) => n.node_type === "CORPORATE_FUNCTION")
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()),
    [flatNodes],
  );

  const formSubmitting =
    createRegion.isPending || createCorp.isPending || updateNode.isPending;

  async function handleFormSubmit(values: OrgNodeFormValues) {
    if (!formCtx) return;
    setFormError(null);
    const trimmedName = values.name.trim();
    const trimmedCode = values.code.trim();
    try {
      if (formCtx.mode === "create") {
        const body = { name: trimmedName, code: trimmedCode || null };
        if (formCtx.tab === "regions") {
          await createRegion.mutateAsync(body);
        } else {
          await createCorp.mutateAsync(body);
        }
      } else if (formCtx.node) {
        await updateNode.mutateAsync({
          id: formCtx.node.id,
          payload: {
            name: trimmedName,
            ...(trimmedCode ? { code: trimmedCode } : {}),
          },
        });
      }
      setFormCtx(null);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Request failed.");
    }
  }

  function openDeleteFlow(node: OrgNode) {
    setDeleteError(null);
    setDeleteTargetId(node.id);
  }

  function closeDeleteDialog(open: boolean) {
    if (!open) {
      setDeleteTargetId(null);
      setDeleteError(null);
    }
  }

  function handleConfirmDelete() {
    const id = deleteDetailQuery.data?.id;
    if (!id) return;
    setDeleteError(null);
    deleteNode.mutate(id, {
      onSuccess: () => closeDeleteDialog(false),
      onError: (err) => {
        setDeleteError(err instanceof Error ? err.message : "Delete failed.");
      },
    });
  }

  // Access guard — after hooks (same pattern as Permission Matrix).
  if (!isSuperAdmin) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-destructive/20 bg-destructive/5 p-12 text-center">
        <Lock className="mb-3 h-10 w-10 text-destructive/60" />
        <h3 className="text-lg font-semibold">Access Denied</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Only super administrators can manage regions and corporate functions.
        </p>
      </div>
    );
  }

  const treeError =
    treeQuery.error instanceof Error ? treeQuery.error.message : treeQuery.error ? String(treeQuery.error) : null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Regions &amp; corporate functions</h1>
        <p className="text-muted-foreground">
          Organize plants under regions and define HQ functions that span the organization. Names may repeat; use
          codes and created dates to tell rows apart.
        </p>
      </div>

      {treeError ? (
        <Alert variant="destructive">
          <AlertDescription>{treeError}</AlertDescription>
        </Alert>
      ) : null}

      {formError ? (
        <Alert variant="destructive">
          <AlertDescription>{formError}</AlertDescription>
        </Alert>
      ) : null}

      {deleteError && !deleteDialogOpen ? (
        <Alert variant="destructive">
          <AlertDescription>{deleteError}</AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg">Organization structure</CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="regions" className="w-full">
            <TabsList className="mb-4 grid w-full max-w-md grid-cols-2">
              <TabsTrigger value="regions" className="gap-2">
                <MapPin className="h-4 w-4" />
                Regions
              </TabsTrigger>
              <TabsTrigger value="corporate" className="gap-2">
                <Building2 className="h-4 w-4" />
                Corporate functions
              </TabsTrigger>
            </TabsList>

            <TabsContent value="regions">
              <OrgTypeTableSection
                rows={regions}
                isLoading={treeQuery.isLoading}
                emptyTitle="No regions yet"
                emptyDescription="Group plants by geography or business unit. Create your first region to start organizing the org tree."
                emptyCtaLabel="Create region"
                onEmptyCta={() => setFormCtx({ mode: "create", tab: "regions" })}
                onAdd={() => setFormCtx({ mode: "create", tab: "regions" })}
                onEdit={(n) => setFormCtx({ mode: "edit", tab: "regions", node: n })}
                onDelete={openDeleteFlow}
                deletePrefetchingId={deletePrefetching ? deleteTargetId : null}
                addLabel="Add region"
              />
            </TabsContent>

            <TabsContent value="corporate">
              <OrgTypeTableSection
                rows={corporateFunctions}
                isLoading={treeQuery.isLoading}
                emptyTitle="No corporate functions yet"
                emptyDescription="Add HQ functions like Finance, HR, or IT that span across plants. Create your first corporate function to start."
                emptyCtaLabel="Create corporate function"
                onEmptyCta={() => setFormCtx({ mode: "create", tab: "corporate" })}
                onAdd={() => setFormCtx({ mode: "create", tab: "corporate" })}
                onEdit={(n) => setFormCtx({ mode: "edit", tab: "corporate", node: n })}
                onDelete={openDeleteFlow}
                deletePrefetchingId={deletePrefetching ? deleteTargetId : null}
                addLabel="Add corporate function"
              />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      <OrgNodeFormDialog
        open={!!formCtx}
        onOpenChange={(o) => !o && setFormCtx(null)}
        title={
          formCtx?.mode === "edit"
            ? formCtx.tab === "regions"
              ? "Edit region"
              : "Edit corporate function"
            : formCtx?.tab === "regions"
              ? "Create region"
              : "Create corporate function"
        }
        submitLabel={formCtx?.mode === "edit" ? "Save changes" : "Create"}
        initial={formCtx?.mode === "edit" ? formCtx.node ?? null : null}
        isSubmitting={formSubmitting}
        onSubmit={handleFormSubmit}
      />

      <DeleteOrgNodeDialog
        open={deleteDialogOpen}
        onOpenChange={closeDeleteDialog}
        node={deleteDetailQuery.data ?? null}
        kindLabel={deleteDetailQuery.data?.node_type === "CORPORATE_FUNCTION" ? "corporate function" : "region"}
        isDeleting={deleteNode.isPending}
        deleteError={deleteError}
        onConfirmDelete={handleConfirmDelete}
      />
    </div>
  );
}
