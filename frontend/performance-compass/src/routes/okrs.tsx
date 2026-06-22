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
  Building2, Network, TrendingUp, CheckCircle2, AlertTriangle, XCircle,
} from "lucide-react";
import {
  useObjectives, usePlants, useAllowedLevels, useVisibilityScope,
  usePendingValidations, useDeleteObjective, useProgressSummary,
} from "@/lib/hooks";
import { useAuthStore } from "@/lib/stores/auth-store";
import { usePeriodFilter } from "@/lib/hooks/use-period-filter";
import { CreateOKRDialog } from "@/components/okr/create-okr-dialog";
import { OKRCard } from "@/components/okr/okr-card";
import { ValidationQueue } from "@/components/okr/validation-queue";
import { OkrPendingApprovals } from "@/components/okr/okr-pending-approvals";
import { canValidateOkrProgress } from "@/utils/okr-permissions";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
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
  REGION: Network,
  PLANT: Factory,
  DEPARTMENT: GitBranch,
  TEAM: Users,
  INDIVIDUAL: User,
};

const LEVEL_ORDER: ObjectiveLevel[] = [
  "ORGANIZATION",
  "REGION",
  "PLANT",
  "DEPARTMENT",
  "TEAM",
  "INDIVIDUAL",
];

const LEVEL_TAB_LABELS: Record<string, string> = {
  ORGANIZATION: "Organization",
  REGION: "Regional",
  PLANT: "Plant",
  DEPARTMENT: "Department",
  TEAM: "Team",
  INDIVIDUAL: "Individual",
};

function OKRsPage() {
  const { user } = useAuthStore();
  const role = user?.system_role || "EMPLOYEE";

  // Get level from URL search params
  const searchParams = Route.useSearch() as Record<string, string>;
  const urlLevel = searchParams.level?.toUpperCase() || "";
  const urlView = searchParams.view || "";

  const [selectedPlantId, setSelectedPlantId] = useState<string>("");
  const [activeTab, setActiveTab] = useState(
    urlView === "validations" ? "validations" : 
    (urlLevel === "EMPLOYEE" ? "INDIVIDUAL" : (urlLevel || "all"))
  );
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [createLevel, setCreateLevel] = useState<ObjectiveLevel | undefined>();

  const { data: plants = [], isLoading: plantsLoading } = usePlants();
  const { data: visibilityScope } = useVisibilityScope();
  const { data: allowedLevelsData } = useAllowedLevels(role, user?.id);
  const allowedLevels = (allowedLevelsData?.allowed_levels || []) as ObjectiveLevel[];

  const scopedPlants = useMemo(() => {
    const all = plants as { id: string; name: string }[];
    if (!visibilityScope || visibilityScope.unrestricted) return all;
    if (visibilityScope.plant_ids?.length) {
      const allowed = new Set(visibilityScope.plant_ids);
      return all.filter((p) => allowed.has(p.id));
    }
    if (visibilityScope.plant_id) {
      return all.filter((p) => p.id === visibilityScope.plant_id);
    }
    return [];
  }, [plants, visibilityScope]);

  const showPlantFilter = scopedPlants.length > 1 || visibilityScope?.unrestricted;

  const { year, quarter, cycleId } = usePeriodFilter();
  const { data: progressSummary } = useProgressSummary({
    plantId: selectedPlantId || undefined,
    year,
    quarter,
    cycleId: cycleId || undefined,
  });
  const { data: pendingValidations = [] } = usePendingValidations(
    selectedPlantId || undefined,
    cycleId || undefined,
  );

  const canValidateProgress = canValidateOkrProgress(user);
  const { data: pendingLifecycleOkrs = [] } = useQuery({
    queryKey: ["pending-okr-approvals"],
    queryFn: () => api.getPendingLifecycleApprovals(),
    enabled: canValidateProgress,
    refetchInterval: 30_000,
  });
  const pendingReviewCount = pendingValidations.length + pendingLifecycleOkrs.length;

  // Fetch objectives for current tab — filtered by global year/quarter from top bar
  const levelFilter = activeTab !== "all" && activeTab !== "validations" ? activeTab : undefined;
  const { data: objectives, isLoading, error } = useObjectives({
    level: levelFilter as ObjectiveLevel | undefined,
    plant_id: selectedPlantId || undefined,
    year,
    quarter,
  });

  const deleteObj = useDeleteObjective();

  // Phase 6: anyone with allowed_levels (incl. self-draft INDIVIDUAL) can draft OKRs
  const canDraft = allowedLevels.length > 0;

  const visibleLevelSet = useMemo(() => {
    if (visibilityScope?.visible_levels?.length) {
      return new Set(visibilityScope.visible_levels);
    }
    return new Set(LEVEL_ORDER);
  }, [visibilityScope]);

  // Determine which tabs to show based on role + hierarchy visibility
  const visibleTabs = useMemo(() => {
    const tabs: { value: string; label: string; icon: React.ElementType }[] = [
      { value: "all", label: "All OKRs", icon: Target },
    ];
    for (const lvl of LEVEL_ORDER) {
      if (!visibleLevelSet.has(lvl)) continue;
      tabs.push({
        value: lvl,
        label: LEVEL_TAB_LABELS[lvl] || lvl,
        icon: LEVEL_ICONS[lvl] || Target,
      });
    }
    // Progress / OKR approval queue for managers and regional heads
    if (canValidateProgress) {
      tabs.push({
        value: "validations",
        label: `Validations (${pendingReviewCount})`,
        icon: CheckCircle2,
      });
    }
    return tabs;
  }, [role, canValidateProgress, pendingReviewCount, visibleLevelSet]);

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
            Showing <strong>{quarter} {year}</strong> OKRs
            {visibilityScope?.region_name
              ? ` · scoped to ${visibilityScope.region_name}`
              : " · Organization → Region → Plant → Department → Team → Individual"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Plant filter (in-scope plants only) */}
          {showPlantFilter && (
            <Select value={selectedPlantId || "__all__"} onValueChange={(v) => setSelectedPlantId(v === "__all__" ? "" : v)}>
              <SelectTrigger className="w-[180px] h-9">
                <Factory className="h-3.5 w-3.5 mr-1.5 text-muted-foreground" />
                <SelectValue placeholder="All Plants" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All Plants</SelectItem>
                {scopedPlants.map((p) => (
                  <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          {/* Create button */}
          {canDraft && (
            <Button onClick={() => handleCreateOKR()} className="h-9">
              <Plus className="h-4 w-4 mr-1" /> Draft New OKR
            </Button>
          )}
        </div>
      </div>

      {/* Progress summary + validations card */}
      {(progressSummary || canValidateProgress) && (
        <div className="grid gap-3 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7">
          {progressSummary &&
            LEVEL_ORDER.filter((lvl) => visibleLevelSet.has(lvl)).map((lvl) => {
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
          {canValidateProgress && (
            <Card
              key="validations"
              className={`cursor-pointer transition-colors ${
                activeTab === "validations"
                  ? "border-primary ring-1 ring-primary/30"
                  : pendingReviewCount > 0
                    ? "border-amber-500/40 hover:border-amber-500/60"
                    : "hover:border-primary/30"
              }`}
              onClick={() => setActiveTab("validations")}
            >
              <CardContent className="py-3 px-4">
                <div className="flex items-center gap-2 mb-1">
                  <CheckCircle2 className={`h-4 w-4 ${pendingReviewCount > 0 ? "text-amber-500" : "text-primary"}`} />
                  <p className="text-[10px] font-medium text-muted-foreground uppercase">Validations</p>
                </div>
                <p className="text-xl font-bold">{pendingReviewCount}</p>
                <p className="mt-1 text-[10px] text-muted-foreground">
                  {pendingValidations.length} progress · {pendingLifecycleOkrs.length} OKR approval
                </p>
              </CardContent>
            </Card>
          )}
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
              Progress & OKR approval queue
            </h3>
            <p className="text-xs text-muted-foreground">
              Review progress submissions from your region and approve OKRs routed to you.
            </p>
          </div>
          <div className="space-y-4">
            <OkrPendingApprovals />
            <ValidationQueue validations={pendingValidations} />
          </div>
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
                  <OKRCard
                    key={okr.id}
                    objective={okr}
                    canManage={canDraft}
                    onDelete={handleDeleteOKR}
                    pendingValidations={pendingValidations}
                    canValidateProgress={canValidateProgress}
                  />
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
                      {canDraft ? "Draft an OKR to get started — it will go to your manager for approval." : "OKRs will appear here once created by your manager."}
                    </p>
                    {canDraft && allowedLevels.includes((tabVal === "all" ? allowedLevels[0] : tabVal) as ObjectiveLevel) && (
                      <Button variant="outline" className="mt-3" onClick={() => handleCreateOKR(tabVal === "all" ? undefined : tabVal as ObjectiveLevel)}>
                        <Plus className="h-4 w-4 mr-1" /> Draft New OKR
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
