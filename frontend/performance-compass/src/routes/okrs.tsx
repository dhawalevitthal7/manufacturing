import { useState, useMemo } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  AlertCircle, Loader2, Plus, Target, Factory, GitBranch, Users, User,
  Building2, TrendingUp, CheckCircle2, AlertTriangle, XCircle,
} from "lucide-react";
import {
  useObjectives, usePlants, useAllowedLevels,
  usePendingValidations, useDeleteObjective, useProgressSummary,
} from "@/lib/hooks";
import { useAuthStore } from "@/lib/stores/auth-store";
import { CreateOKRDialog } from "@/components/okr/create-okr-dialog";
import { OKRCard } from "@/components/okr/okr-card";
import { ValidationQueue } from "@/components/okr/validation-queue";
import type { ObjectiveLevel } from "@/lib/api";

export const Route = createFileRoute("/okrs")({
  head: () => ({
    meta: [
      { title: "Objectives & Key Results — Axis Operate" },
      { name: "description", content: "Cascading OKR management across organization, plants, departments and teams." },
    ],
  }),
  component: OKRsPage,
});

const LEVEL_ICONS: Record<string, React.ElementType> = {
  ORGANIZATION: Building2,
  PLANT: Factory,
  DEPARTMENT: GitBranch,
  TEAM: Users,
  INDIVIDUAL: User,
};

const LEVEL_ORDER: ObjectiveLevel[] = ["ORGANIZATION", "PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"];

function OKRsPage() {
  const { user } = useAuthStore();
  const role = user?.system_role || "EMPLOYEE";

  // Get level from URL search params
  const searchParams = Route.useSearch() as Record<string, string>;
  const urlLevel = searchParams.level?.toUpperCase() || "";

  const [selectedPlantId, setSelectedPlantId] = useState<string>("");
  const [activeTab, setActiveTab] = useState(urlLevel === "EMPLOYEE" ? "INDIVIDUAL" : (urlLevel || "all"));
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [createLevel, setCreateLevel] = useState<ObjectiveLevel | undefined>();

  const { data: plants = [], isLoading: plantsLoading } = usePlants();
  const { data: allowedLevelsData } = useAllowedLevels(role);
  const allowedLevels = (allowedLevelsData?.allowed_levels || []) as ObjectiveLevel[];

  const { data: progressSummary } = useProgressSummary(selectedPlantId || undefined);
  const { data: pendingValidations = [] } = usePendingValidations(selectedPlantId || undefined);

  // Fetch objectives for current tab
  const levelFilter = activeTab !== "all" && activeTab !== "validations" ? activeTab : undefined;
  const { data: objectives, isLoading, error } = useObjectives({
    level: levelFilter as ObjectiveLevel | undefined,
    plant_id: selectedPlantId || undefined,
  });

  const deleteObj = useDeleteObjective();

  // Check if user can manage (create/delete) OKRs
  const canManage = allowedLevels.length > 0;

  // Determine which tabs to show based on role
  const visibleTabs = useMemo(() => {
    const tabs: { value: string; label: string; icon: React.ElementType }[] = [
      { value: "all", label: "All OKRs", icon: Target },
    ];
    for (const lvl of LEVEL_ORDER) {
      tabs.push({
        value: lvl,
        label: lvl === "INDIVIDUAL" ? "Individual" : lvl.charAt(0) + lvl.slice(1).toLowerCase(),
        icon: LEVEL_ICONS[lvl] || Target,
      });
    }
    // Add validation tab for managers
    if (["SUPER_ADMIN", "CEO", "VP_OPERATIONS", "PLANT_HEAD", "PLANT_MANAGER", "DEPT_HEAD", "MANAGER", "TEAM_LEAD"].includes(role)) {
      tabs.push({ value: "validations", label: `Validations (${pendingValidations.length})`, icon: CheckCircle2 });
    }
    return tabs;
  }, [role, pendingValidations.length]);

  const handleCreateOKR = (level?: ObjectiveLevel) => {
    setCreateLevel(level || allowedLevels[0]);
    setCreateDialogOpen(true);
  };

  const handleDeleteOKR = async (id: string) => {
    if (confirm("Delete this OKR and all its children?")) {
      deleteObj.mutate(id);
    }
  };

  if (isLoading && !objectives) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-muted-foreground" />
          <p className="mt-2 text-sm text-muted-foreground">Loading OKRs...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold flex items-center gap-2">
            <Target className="h-6 w-6 text-primary" />
            Objectives & Key Results
          </h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            Cascading OKRs: Organization → Plant → Department → Team → Individual
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Plant filter */}
          <Select value={selectedPlantId || "__all__"} onValueChange={(v) => setSelectedPlantId(v === "__all__" ? "" : v)}>
            <SelectTrigger className="w-[180px] h-9">
              <Factory className="h-3.5 w-3.5 mr-1.5 text-muted-foreground" />
              <SelectValue placeholder="All Plants" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All Plants</SelectItem>
              {(plants as any[]).map((p: any) => (
                <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Create button */}
          {canManage && (
            <Button onClick={() => handleCreateOKR()} className="h-9">
              <Plus className="h-4 w-4 mr-1" /> Create OKR
            </Button>
          )}
        </div>
      </div>

      {/* Progress Summary Cards */}
      {progressSummary && (
        <div className="grid gap-3 grid-cols-2 sm:grid-cols-3 lg:grid-cols-5">
          {LEVEL_ORDER.map((lvl) => {
            const data = (progressSummary as any)[lvl];
            if (!data || data.total === 0) return (
              <Card key={lvl} className="opacity-50">
                <CardContent className="py-3 px-4">
                  <div className="flex items-center gap-2">
                    {(() => { const Icon = LEVEL_ICONS[lvl] || Target; return <Icon className="h-4 w-4 text-muted-foreground" />; })()}
                    <div>
                      <p className="text-[10px] font-medium text-muted-foreground uppercase">{lvl}</p>
                      <p className="text-lg font-bold">0</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
            return (
              <Card key={lvl} className="cursor-pointer hover:border-primary/30 transition-colors" onClick={() => setActiveTab(lvl)}>
                <CardContent className="py-3 px-4">
                  <div className="flex items-center gap-2 mb-1">
                    {(() => { const Icon = LEVEL_ICONS[lvl] || Target; return <Icon className="h-4 w-4 text-primary" />; })()}
                    <p className="text-[10px] font-medium text-muted-foreground uppercase">{lvl}</p>
                  </div>
                  <p className="text-xl font-bold">{data.total}</p>
                  <div className="mt-1 flex items-center gap-1 text-[10px]">
                    <span className="text-emerald-500">{data.on_track} on track</span>
                    <span className="text-muted-foreground">•</span>
                    <span className="text-amber-500">{data.at_risk} at risk</span>
                    <span className="text-muted-foreground">•</span>
                    <span className="text-rose-500">{data.off_track} off</span>
                  </div>
                  <div className="mt-1.5 h-1 w-full rounded-full bg-muted overflow-hidden">
                    <div className={`h-full rounded-full transition-all ${data.avg_progress >= 75 ? "bg-emerald-500" : data.avg_progress >= 50 ? "bg-amber-500" : "bg-rose-500"}`}
                      style={{ width: `${Math.min(data.avg_progress, 100)}%` }} />
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Error */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error instanceof Error ? error.message : "Failed to load OKRs"}</AlertDescription>
        </Alert>
      )}

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="h-auto flex-wrap gap-1 bg-transparent p-0">
          {visibleTabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <TabsTrigger key={tab.value} value={tab.value}
                className="data-[state=active]:bg-primary/10 data-[state=active]:text-primary rounded-md border border-transparent data-[state=active]:border-primary/20 px-3 py-1.5 text-xs">
                <Icon className="h-3 w-3 mr-1" /> {tab.label}
              </TabsTrigger>
            );
          })}
        </TabsList>

        {/* Validations tab */}
        <TabsContent value="validations" className="mt-4">
          <div className="mb-3">
            <h3 className="text-base font-semibold flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-amber-500" />
              Progress Validation Queue
            </h3>
            <p className="text-xs text-muted-foreground">Review and approve/reject employee progress submissions</p>
          </div>
          <ValidationQueue validations={pendingValidations} />
        </TabsContent>

        {/* OKR list tabs */}
        {["all", ...LEVEL_ORDER].map((tabVal) => (
          <TabsContent key={tabVal} value={tabVal} className="mt-4">
            {/* Quick create buttons for this level */}
            {tabVal !== "all" && allowedLevels.includes(tabVal as ObjectiveLevel) && (
              <div className="mb-3">
                <Button size="sm" variant="outline" onClick={() => handleCreateOKR(tabVal as ObjectiveLevel)} className="h-7 text-xs">
                  <Plus className="h-3 w-3 mr-1" /> Create {tabVal.charAt(0) + tabVal.slice(1).toLowerCase()} OKR
                </Button>
              </div>
            )}

            {objectives && objectives.length > 0 ? (
              <div className="space-y-3">
                {objectives.map((okr) => (
                  <OKRCard key={okr.id} objective={okr} canManage={canManage} onDelete={handleDeleteOKR} />
                ))}
              </div>
            ) : (
              <Card>
                <CardContent className="pt-6">
                  <div className="text-center py-8">
                    <Target className="mx-auto h-12 w-12 text-muted-foreground/30 mb-3" />
                    <p className="text-muted-foreground font-medium">
                      {tabVal === "all" ? "No OKRs found" : `No ${tabVal.toLowerCase()} OKRs`}
                    </p>
                    <p className="text-sm text-muted-foreground/70 mt-1">
                      {canManage ? "Create one to get started with cascading objectives." : "OKRs will appear here once created by your manager."}
                    </p>
                    {canManage && allowedLevels.includes((tabVal === "all" ? allowedLevels[0] : tabVal) as ObjectiveLevel) && (
                      <Button variant="outline" className="mt-3" onClick={() => handleCreateOKR(tabVal === "all" ? undefined : tabVal as ObjectiveLevel)}>
                        <Plus className="h-4 w-4 mr-1" /> Create OKR
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}
          </TabsContent>
        ))}
      </Tabs>

      {/* Create OKR Dialog */}
      <CreateOKRDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
        allowedLevels={allowedLevels}
        defaultLevel={createLevel}
        defaultPlantId={selectedPlantId || undefined}
      />
    </div>
  );
}
