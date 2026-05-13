import { useState, useEffect } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { usePlants, useDepartments, useTeams } from "@/lib/hooks";
import { useAuthStore } from "@/lib/stores/auth-store";
import { api } from "@/lib/api";
import { TeamMemberManager } from "@/components/teams/team-member-manager";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AlertCircle, Loader2, Factory, GitBranch, Users, ChevronRight, ArrowLeft, Crown } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/teams")({
  head: () => ({
    meta: [
      { title: "Teams — Axis Operate" },
      { name: "description", content: "Team composition and OKR rollups via Plant → Department → Team hierarchy." },
    ],
  }),
  component: TeamsPage,
});

function TeamsPage() {
  const { hasCapability } = useAuthStore();
  const queryClient = useQueryClient();
  const [selectedPlantId, setSelectedPlantId] = useState<string | null>(null);
  const [selectedDeptId, setSelectedDeptId] = useState<string | null>(null);
  const [selectedTeamId, setSelectedTeamId] = useState<string | null>(null);

  const { data: plants = [], isLoading: plantsLoading } = usePlants();
  const { data: departments = [], isLoading: deptsLoading } = useDepartments(selectedPlantId || undefined);
  const { data: teams = [], isLoading: teamsLoading } = useTeams(selectedDeptId || undefined);

  const { data: teamDetail, isLoading: teamDetailLoading, error: teamDetailError } = useQuery({
    queryKey: ["team", selectedTeamId],
    queryFn: () => api.getTeamDetail(selectedTeamId!),
    enabled: !!selectedTeamId,
  });

  const selectedPlant = plants.find((p: any) => p.id === selectedPlantId);
  const selectedDept = departments.find((d: any) => d.id === selectedDeptId);

  useEffect(() => {
    setSelectedTeamId(null);
  }, [selectedDeptId]);

  // Breadcrumb navigation
  const handleBack = () => {
    if (selectedTeamId) {
      setSelectedTeamId(null);
      return;
    }
    if (selectedDeptId) {
      setSelectedDeptId(null);
    } else if (selectedPlantId) {
      setSelectedPlantId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header with Breadcrumb */}
      <div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
          <button onClick={() => { setSelectedPlantId(null); setSelectedDeptId(null); }}
            className="hover:text-foreground transition-colors">Plants</button>
          {selectedPlant && (
            <>
              <ChevronRight className="h-3 w-3" />
              <button onClick={() => setSelectedDeptId(null)}
                className="hover:text-foreground transition-colors">{selectedPlant.name}</button>
            </>
          )}
          {selectedDept && !selectedTeamId && (
            <>
              <ChevronRight className="h-3 w-3" />
              <span className="text-foreground font-medium">{selectedDept.name}</span>
            </>
          )}
          {selectedDept && selectedTeamId && (
            <>
              <ChevronRight className="h-3 w-3" />
              <button type="button" onClick={() => setSelectedTeamId(null)} className="hover:text-foreground transition-colors">
                {selectedDept.name}
              </button>
              <ChevronRight className="h-3 w-3" />
              <span className="text-foreground font-medium">
                {teamDetail?.name || teams.find((t: any) => t.id === selectedTeamId)?.name || "Team"}
              </span>
            </>
          )}
        </div>
        <div className="flex items-center gap-3">
          {(selectedPlantId || selectedDeptId || selectedTeamId) && (
            <Button variant="ghost" size="sm" onClick={handleBack}>
              <ArrowLeft className="mr-1 h-4 w-4" /> Back
            </Button>
          )}
          <div>
            <h2 className="text-2xl font-semibold">
              {selectedTeamId && teamDetail
                ? teamDetail.name
                : selectedDeptId
                ? "Teams"
                : selectedPlantId
                ? "Departments"
                : "Plants"}
            </h2>
            <p className="text-sm text-muted-foreground">
              {selectedTeamId && teamDetail
                ? "Roster and alignment for this team"
                : selectedDeptId
                ? `Teams in ${selectedDept?.name || "department"}`
                : selectedPlantId
                ? `Departments in ${selectedPlant?.name || "plant"}`
                : "Select a plant to navigate the hierarchy"}
            </p>
          </div>
        </div>
      </div>

      {/* Level 1: Plants */}
      {!selectedPlantId && (
        <>
          {plantsLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : plants.length === 0 ? (
            <Card>
              <CardContent className="pt-6">
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <Factory className="mb-3 h-12 w-12 text-muted-foreground/40" />
                  <p className="text-muted-foreground font-medium">No plants created yet</p>
                  <p className="text-sm text-muted-foreground/70 mt-1">Create plants from the Administration panel to get started</p>
                </div>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {plants.map((plant: any) => (
                <Card key={plant.id} className="cursor-pointer hover:shadow-md hover:border-primary/30 transition-all"
                  onClick={() => setSelectedPlantId(plant.id)}>
                  <CardHeader>
                    <div className="flex items-center gap-3">
                      <div className="grid h-10 w-10 place-items-center rounded-lg bg-primary/10">
                        <Factory className="h-5 w-5 text-primary" />
                      </div>
                      <div>
                        <CardTitle className="text-base">{plant.name}</CardTitle>
                        {plant.location && <p className="text-xs text-muted-foreground">{plant.location}</p>}
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center justify-between">
                      <div className="flex gap-2">
                        {plant.departments && (
                          <Badge variant="outline">{plant.departments.length} dept{plant.departments.length !== 1 ? "s" : ""}</Badge>
                        )}
                        {plant.employee_count !== undefined && (
                          <Badge variant="outline">{plant.employee_count} employees</Badge>
                        )}
                      </div>
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </>
      )}

      {/* Level 2: Departments for selected Plant */}
      {selectedPlantId && !selectedDeptId && (
        <>
          {deptsLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : departments.length === 0 ? (
            <Card>
              <CardContent className="pt-6">
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <GitBranch className="mb-3 h-12 w-12 text-muted-foreground/40" />
                  <p className="text-muted-foreground font-medium">No departments in this plant</p>
                  <p className="text-sm text-muted-foreground/70 mt-1">Create departments from the Administration panel</p>
                </div>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {departments.map((dept: any) => (
                <Card key={dept.id} className="cursor-pointer hover:shadow-md hover:border-primary/30 transition-all"
                  onClick={() => setSelectedDeptId(dept.id)}>
                  <CardHeader>
                    <div className="flex items-center gap-3">
                      <div className="grid h-10 w-10 place-items-center rounded-lg bg-accent/10">
                        <GitBranch className="h-5 w-5 text-accent" />
                      </div>
                      <div>
                        <CardTitle className="text-base">{dept.name}</CardTitle>
                        {dept.dept_type && <p className="text-xs text-muted-foreground">{dept.dept_type}</p>}
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center justify-between">
                      <Badge variant="outline">Department</Badge>
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </>
      )}

      {/* Level 3: Teams for selected Department */}
      {selectedDeptId && (
        <>
          {teamsLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : teams.length === 0 ? (
            <Card>
              <CardContent className="pt-6">
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <Users className="mb-3 h-12 w-12 text-muted-foreground/40" />
                  <p className="text-muted-foreground font-medium">No teams in this department</p>
                  <p className="text-sm text-muted-foreground/70 mt-1">Create teams from the Administration panel</p>
                </div>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-6">
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {teams.map((team: any) => (
                  <Card
                    key={team.id}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setSelectedTeamId(team.id);
                      }
                    }}
                    className={`cursor-pointer hover:shadow-md transition-shadow ${
                      selectedTeamId === team.id ? "ring-2 ring-primary/40 border-primary/50" : ""
                    }`}
                    onClick={() => setSelectedTeamId(team.id)}
                  >
                    <CardHeader>
                      <div className="flex items-center gap-3">
                        <div className="grid h-10 w-10 place-items-center rounded-lg bg-success/10">
                          <Users className="h-5 w-5 text-success" />
                        </div>
                        <div>
                          <CardTitle className="text-base">{team.name}</CardTitle>
                          {team.lead_name && <p className="text-xs text-muted-foreground">Lead: {team.lead_name}</p>}
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="flex gap-2">
                        <Badge variant="outline">{team.member_count || 0} members</Badge>
                        {team.lead_name && <Badge variant="secondary">Has Lead</Badge>}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>

              {selectedTeamId && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Team roster</CardTitle>
                    <p className="text-sm text-muted-foreground">
                      Members assigned to this team. Team leads can validate progress from their peers alongside managers.
                    </p>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    {teamDetailLoading && (
                      <div className="flex justify-center py-8">
                        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                      </div>
                    )}
                    {teamDetailError && (
                      <Alert variant="destructive">
                        <AlertCircle className="h-4 w-4" />
                        <AlertDescription>Could not load team details.</AlertDescription>
                      </Alert>
                    )}
                    {teamDetail && (
                      <>
                        {teamDetail.members?.length ? (
                          <ul className="divide-y divide-border rounded-md border border-border">
                            {(teamDetail.members as Array<{
                              id: string;
                              name: string;
                              email: string;
                              employee_id?: string;
                              is_team_lead?: boolean;
                              role_in_team?: string;
                            }>).map((m) => (
                              <li key={m.id} className="flex items-center justify-between gap-2 px-3 py-2 text-sm">
                                <div className="min-w-0">
                                  <div className="flex items-center gap-2 font-medium">
                                    <span className="truncate">{m.name}</span>
                                    {m.is_team_lead && (
                                      <Crown className="h-3.5 w-3.5 shrink-0 text-amber-500" aria-label="Team lead" />
                                    )}
                                  </div>
                                  <div className="truncate text-xs text-muted-foreground">{m.email}</div>
                                </div>
                                <Badge variant="outline" className="shrink-0 text-[10px]">
                                  {m.role_in_team || "MEMBER"}
                                </Badge>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="text-sm text-muted-foreground">No members on this team yet.</p>
                        )}

                        {hasCapability("can_create_teams") && (
                          <TeamMemberManager
                            teamId={teamDetail.id}
                            plantId={teamDetail.plant_id ?? null}
                            members={(teamDetail.members || []).map(
                              (m: {
                                id: string;
                                name: string;
                                email: string;
                                employee_id?: string;
                                team_member_id: string;
                                is_team_lead: boolean;
                                role_in_team: string;
                                joined_at?: string;
                              }) => ({
                                id: m.id,
                                name: m.name,
                                email: m.email,
                                employee_id: m.employee_id,
                                team_member_id: m.team_member_id,
                                is_team_lead: m.is_team_lead,
                                role_in_team: m.role_in_team,
                                joined_at: m.joined_at,
                              })
                            )}
                            onMembersChange={() => {
                              void queryClient.invalidateQueries({ queryKey: ["team", selectedTeamId] });
                              void queryClient.invalidateQueries({ queryKey: ["teams", selectedDeptId] });
                            }}
                          />
                        )}
                      </>
                    )}
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
