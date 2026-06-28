import { useState, useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/lib/stores/auth-store";
import {
  usePlants,
  useDepartments,
  useTeams,
  useDesignations,
  useCreatePlant,
  useCreateDepartment,
  useCreateTeam,
  useOrgTree,
} from "@/lib/hooks";
import { api, type PlantCreate } from "@/lib/api";
import { API_BASE_URL } from "@/lib/api-base";
import { flattenOrgNodes } from "@/lib/org-tree-utils";
import {
  onboardScopeNeedsField,
  onboardRequiredFields,
} from "@/lib/onboard-scope";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Users,
  Building2,
  GitBranch,
  Shield,
  Plus,
  CheckCircle2,
  AlertCircle,
  Factory,
  Loader2,
  Calendar,
} from "lucide-react";

import { CyclesAdmin } from "@/components/admin/cycles-admin";

export function AdminPanel() {
  const { hasCapability, permissions, user, getToken } = useAuthStore();
  const isSuperAdmin = permissions?.system_role === "SUPER_ADMIN";
  const { data: orgTree } = useOrgTree(!!isSuperAdmin);

  const regionNodes = useMemo(() => {
    if (!orgTree) return [];
    return flattenOrgNodes(orgTree)
      .filter((n) => n.node_type === "REGION")
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [orgTree]);

  const [selectedPlantForDept, setSelectedPlantForDept] = useState("");
  const [selectedPlantForTeam, setSelectedPlantForTeam] = useState("");
  const [selectedDeptForTeam, setSelectedDeptForTeam] = useState("");

  // Fetch hierarchy data from DB
  const { data: plants = [], isLoading: plantsLoading } = usePlants();
  const { data: designations = [] } = useDesignations();
  const { data: plantEmployees = [] } = useQuery({
    queryKey: ["employees", "plant-for-team", selectedPlantForTeam],
    queryFn: () => api.getEmployees({ plant_id: selectedPlantForTeam!, is_active: true }),
    enabled: !!selectedPlantForTeam,
  });

  const { data: deptsForSelectedPlant = [] } = useDepartments(selectedPlantForTeam || undefined);
  
  // Onboarding form state
  const [onboardingData, setOnboardingData] = useState({
    email: "",
    name: "",
    password: "",
    confirmPassword: "",
    role: "EMPLOYEE",
    designation_id: "",
    team: "",
  });

  const [onboardRegion, setOnboardRegion] = useState("");
  const [onboardPlant, setOnboardPlant] = useState("");
  const [onboardDept, setOnboardDept] = useState("");
  const { data: onboardDepts = [] } = useDepartments(onboardPlant || undefined);
  const { data: onboardTeams = [] } = useTeams(onboardDept || undefined);

  const flatOrgNodes = useMemo(() => (orgTree ? flattenOrgNodes(orgTree) : []), [orgTree]);

  const plantsForOnboard = useMemo(() => {
    if (!onboardScopeNeedsField(onboardingData.role, "plant")) return [];
    if (regionNodes.length > 0 && onboardRegion) {
      const plantIds = new Set(
        flatOrgNodes
          .filter((n) => n.node_type === "PLANT" && n.parent_id === onboardRegion)
          .map((n) => n.id),
      );
      return plants.filter((p: { id: string }) => plantIds.has(p.id));
    }
    return plants;
  }, [flatOrgNodes, onboardRegion, plants, regionNodes.length, onboardingData.role]);

  const showRegionField =
    regionNodes.length > 0 && onboardScopeNeedsField(onboardingData.role, "region");
  const showPlantField = onboardScopeNeedsField(onboardingData.role, "plant");
  const showDeptField =
    onboardScopeNeedsField(onboardingData.role, "department") && !!onboardPlant;
  const showTeamField =
    onboardScopeNeedsField(onboardingData.role, "team") && !!onboardDept;
  const scopeRequired = onboardRequiredFields(onboardingData.role, regionNodes.length > 0);

  // Create forms
  const [plantName, setPlantName] = useState("");
  const [plantLocation, setPlantLocation] = useState("");
  /** Optional region for new plant; only used when regionNodes.length > 0. */
  const [plantRegionId, setPlantRegionId] = useState("");
  const [deptName, setDeptName] = useState("");
  const [deptType, setDeptType] = useState("");
  const [teamName, setTeamName] = useState("");
  const [teamLeadId, setTeamLeadId] = useState("");
  const [teamMemberIds, setTeamMemberIds] = useState<Set<string>>(() => new Set());
  
  const [loading, setLoading] = useState(false);
  const [successMessage, setSuccessMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  const createPlantMutation = useCreatePlant();
  const createDeptMutation = useCreateDepartment();
  const createTeamMutation = useCreateTeam();

  // Reset cascading selects when parent changes
  useEffect(() => {
    setOnboardRegion("");
    setOnboardPlant("");
    setOnboardDept("");
    setOnboardingData((d) => ({ ...d, team: "" }));
  }, [onboardingData.role]);
  useEffect(() => {
    setOnboardPlant("");
    setOnboardDept("");
    setOnboardingData((d) => ({ ...d, team: "" }));
  }, [onboardRegion]);
  useEffect(() => {
    setOnboardDept("");
    setOnboardingData((d) => ({ ...d, team: "" }));
  }, [onboardPlant]);
  useEffect(() => {
    setOnboardingData((d) => ({ ...d, team: "" }));
  }, [onboardDept]);
  useEffect(() => { setSelectedDeptForTeam(""); }, [selectedPlantForTeam]);
  useEffect(() => {
    setTeamMemberIds(new Set());
    setTeamLeadId("");
  }, [selectedPlantForTeam, selectedDeptForTeam]);

  if (!permissions || !isSuperAdmin) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-destructive/20 bg-destructive/5 p-8 text-center">
        <AlertCircle className="mb-2 h-8 w-8 text-destructive" />
        <h3 className="font-semibold">Access Denied</h3>
        <p className="text-sm text-muted-foreground">
          Only administrators can access this page.
        </p>
      </div>
    );
  }

  const clearMessages = () => { setSuccessMessage(""); setErrorMessage(""); };

  const handleOnboardEmployee = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    clearMessages();

    if (onboardingData.password !== onboardingData.confirmPassword) {
      setErrorMessage("Passwords do not match");
      setLoading(false);
      return;
    }

    const required = onboardRequiredFields(onboardingData.role, regionNodes.length > 0);
    if (required.includes("region") && !onboardRegion) {
      setErrorMessage("Please select a region");
      setLoading(false);
      return;
    }
    if (required.includes("plant") && !onboardPlant) {
      setErrorMessage("Please select a plant");
      setLoading(false);
      return;
    }
    if (required.includes("department") && !onboardDept) {
      setErrorMessage("Please select a department");
      setLoading(false);
      return;
    }
    if (required.includes("team") && !onboardingData.team) {
      setErrorMessage("Please select a team");
      setLoading(false);
      return;
    }

    try {
      const token = getToken();
      if (!token) { setErrorMessage("Not authenticated"); setLoading(false); return; }

      const response = await fetch(`${API_BASE_URL}/api/auth/onboard-employee`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
        body: JSON.stringify({
          email: onboardingData.email,
          name: onboardingData.name,
          password: onboardingData.password,
          system_role: onboardingData.role,
          region_id: onboardRegion || null,
          plant_id: onboardPlant || null,
          department_id: onboardDept || null,
          team_id: onboardingData.team || null,
          designation_id: onboardingData.designation_id || null,
        }),
      });

      if (!response.ok) { throw new Error(await response.text()); }

      setSuccessMessage(`Employee "${onboardingData.name}" onboarded successfully!`);
      setOnboardingData({ email: "", name: "", password: "", confirmPassword: "", role: "EMPLOYEE", designation_id: "", team: "" });
      setOnboardRegion("");
      setOnboardPlant("");
      setOnboardDept("");
    } catch (error) {
      setErrorMessage(`Failed to onboard: ${error}`);
    } finally {
      setLoading(false);
    }
  };

  const handleCreatePlant = async (e: React.FormEvent) => {
    e.preventDefault();
    clearMessages();
    try {
      const plantPayload: PlantCreate = {
        name: plantName,
        location: plantLocation || undefined,
      };
      if (plantRegionId) {
        plantPayload.region_id = plantRegionId;
      }
      await createPlantMutation.mutateAsync(plantPayload);
      setSuccessMessage(`Plant "${plantName}" created and saved to database`);
      setPlantName("");
      setPlantLocation("");
      setPlantRegionId("");
    } catch (error) {
      setErrorMessage(`Failed to create plant: ${error}`);
    }
  };

  const handleCreateDept = async (e: React.FormEvent) => {
    e.preventDefault();
    clearMessages();
    if (!selectedPlantForDept) { setErrorMessage("Please select a plant for this department"); return; }
    try {
      await createDeptMutation.mutateAsync({ name: deptName, plant_id: selectedPlantForDept, dept_type: deptType || undefined });
      setSuccessMessage(`Department "${deptName}" created and linked to plant`);
      setDeptName(""); setDeptType(""); setSelectedPlantForDept("");
    } catch (error) {
      setErrorMessage(`Failed to create department: ${error}`);
    }
  };

  const handleCreateTeam = async (e: React.FormEvent) => {
    e.preventDefault();
    clearMessages();
    if (!selectedDeptForTeam) { setErrorMessage("Please select a department for this team"); return; }
    try {
      const member_user_ids = [...teamMemberIds];
      if (teamLeadId && !member_user_ids.includes(teamLeadId)) {
        member_user_ids.unshift(teamLeadId);
      }
      await createTeamMutation.mutateAsync({
        name: teamName,
        department_id: selectedDeptForTeam,
        lead_id: teamLeadId || undefined,
        member_user_ids: member_user_ids.length ? member_user_ids : undefined,
      });
      setSuccessMessage(`Team "${teamName}" created inside department hierarchy`);
      setTeamName(""); setTeamLeadId(""); setTeamMemberIds(new Set()); setSelectedPlantForTeam(""); setSelectedDeptForTeam("");
    } catch (error) {
      setErrorMessage(`Failed to create team: ${error}`);
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold">Administration Panel</h1>
        <p className="text-muted-foreground">
          Manage your organization, users, and system settings
        </p>
      </div>

      {/* Messages */}
      {successMessage && (
        <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-800">
          <CheckCircle2 className="h-4 w-4" />
          {successMessage}
        </div>
      )}
      {errorMessage && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          <AlertCircle className="h-4 w-4" />
          {errorMessage}
        </div>
      )}

      {/* Main Admin Sections */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Onboard Employee */}
        {hasCapability("can_invite_employees") && (
          <AdminSection icon={Users} title="Onboard Employee" description="Create account and assign to hierarchy">
            <form onSubmit={handleOnboardEmployee} className="space-y-3">
              <div>
                <label className="text-xs font-medium">Full Name</label>
                <Input type="text" placeholder="John Doe" value={onboardingData.name}
                  onChange={(e) => setOnboardingData({ ...onboardingData, name: e.target.value })} required className="mt-1" />
              </div>
              <div>
                <label className="text-xs font-medium">Email Address</label>
                <Input type="email" placeholder="employee@company.com" value={onboardingData.email}
                  onChange={(e) => setOnboardingData({ ...onboardingData, email: e.target.value })} required className="mt-1" />
              </div>
              <div>
                <label className="text-xs font-medium">Password</label>
                <Input type="password" placeholder="••••••••" value={onboardingData.password}
                  onChange={(e) => setOnboardingData({ ...onboardingData, password: e.target.value })} required className="mt-1" />
              </div>
              <div>
                <label className="text-xs font-medium">Confirm Password</label>
                <Input type="password" placeholder="••••••••" value={onboardingData.confirmPassword}
                  onChange={(e) => setOnboardingData({ ...onboardingData, confirmPassword: e.target.value })} required className="mt-1" />
              </div>
              <div>
                <label className="text-xs font-medium">System Role</label>
                <Select value={onboardingData.role} onValueChange={(v) => setOnboardingData({ ...onboardingData, role: v })}>
                  <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="EMPLOYEE">Employee</SelectItem>
                    <SelectItem value="SUPERVISOR">Supervisor</SelectItem>
                    <SelectItem value="MANAGER">Manager</SelectItem>
                    <SelectItem value="TEAM_LEAD">Team Lead</SelectItem>
                    <SelectItem value="DEPT_HEAD">Department Head</SelectItem>
                    <SelectItem value="PLANT_HEAD">Plant Head</SelectItem>
                    <SelectItem value="REGIONAL_HEAD">Region Head</SelectItem>
                    <SelectItem value="VP_OPERATIONS">VP Operations</SelectItem>
                    <SelectItem value="CEO">CEO</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {designations.length > 0 && (
                <div>
                  <label className="text-xs font-medium">Designation</label>
                  <Select value={onboardingData.designation_id || "none"} onValueChange={(v) => setOnboardingData({ ...onboardingData, designation_id: v === "none" ? "" : v })}>
                    <SelectTrigger className="mt-1"><SelectValue placeholder="Select designation" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">No Designation</SelectItem>
                      {designations.map((d: any) => <SelectItem key={d.id} value={d.id}>{d.name || d.title}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              )}
              {showRegionField && (
                <div>
                  <label className="text-xs font-medium">
                    Region{scopeRequired.includes("region") ? " *" : ""}
                  </label>
                  <Select value={onboardRegion || "none"} onValueChange={(v) => setOnboardRegion(v === "none" ? "" : v)}>
                    <SelectTrigger className="mt-1"><SelectValue placeholder="Select region" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Select a region</SelectItem>
                      {regionNodes.map((r) => (
                        <SelectItem key={r.id} value={r.id}>
                          {r.name}
                          {r.code ? ` (${r.code})` : ""}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
              {showPlantField && (!showRegionField || onboardRegion) && (
                <div>
                  <label className="text-xs font-medium">
                    Plant{scopeRequired.includes("plant") ? " *" : ""}
                  </label>
                  <Select value={onboardPlant || "none"} onValueChange={(v) => setOnboardPlant(v === "none" ? "" : v)}>
                    <SelectTrigger className="mt-1"><SelectValue placeholder="Select plant" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Select a plant</SelectItem>
                      {plantsForOnboard.map((p: { id: string; name: string; location?: string }) => (
                        <SelectItem key={p.id} value={p.id}>
                          {p.name}
                          {p.location ? ` · ${p.location}` : ""}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
              {showDeptField && (
                <div>
                  <label className="text-xs font-medium">
                    Department{scopeRequired.includes("department") ? " *" : ""}
                  </label>
                  <Select value={onboardDept || "none"} onValueChange={(v) => setOnboardDept(v === "none" ? "" : v)}>
                    <SelectTrigger className="mt-1"><SelectValue placeholder="Select department" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Select a department</SelectItem>
                      {onboardDepts.map((d: { id: string; name: string }) => (
                        <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
              {showTeamField && (
                <div>
                  <label className="text-xs font-medium">
                    Team{scopeRequired.includes("team") ? " *" : ""}
                  </label>
                  <Select value={onboardingData.team || "none"} onValueChange={(v) => setOnboardingData({ ...onboardingData, team: v === "none" ? "" : v })}>
                    <SelectTrigger className="mt-1"><SelectValue placeholder="Select team" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Select a team</SelectItem>
                      {onboardTeams.map((t: { id: string; name: string }) => (
                        <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
              <Button type="submit" disabled={loading} className="w-full">
                {loading ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Onboarding...</> : "Onboard Employee"}
              </Button>
            </form>
          </AdminSection>
        )}

        {/* Create Plant */}
        {hasCapability("can_create_plants") && (
          <AdminSection icon={Factory} title="Create Plant" description="Add a new manufacturing plant to the organization">
            <form onSubmit={handleCreatePlant} className="space-y-3">
              <div>
                <label className="text-xs font-medium">Plant Name</label>
                <Input placeholder="e.g., Jamshedpur Plant" value={plantName}
                  onChange={(e) => setPlantName(e.target.value)} required className="mt-1" />
              </div>
              <div>
                <label className="text-xs font-medium">Location</label>
                <Input placeholder="City, State" value={plantLocation}
                  onChange={(e) => setPlantLocation(e.target.value)} className="mt-1" />
              </div>
              {regionNodes.length > 0 && (
                <div>
                  <label className="text-xs font-medium">Region (optional)</label>
                  <Select
                    value={plantRegionId || "none"}
                    onValueChange={(v) => setPlantRegionId(v === "none" ? "" : v)}
                  >
                    <SelectTrigger className="mt-1">
                      <SelectValue placeholder="No region" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">No region</SelectItem>
                      {regionNodes.map((r) => (
                        <SelectItem key={r.id} value={r.id}>
                          {r.name}
                          {r.code ? ` (${r.code})` : ""}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
              <Button type="submit" disabled={createPlantMutation.isPending} className="w-full">
                {createPlantMutation.isPending ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Creating...</> : "Create Plant"}
              </Button>
            </form>
          </AdminSection>
        )}

        {/* Create Department — requires Plant selection */}
        {hasCapability("can_create_departments") && (
          <AdminSection icon={GitBranch} title="Create Department" description="Add department linked to a plant">
            <form onSubmit={handleCreateDept} className="space-y-3">
              <div>
                <label className="text-xs font-medium">Select Plant *</label>
                <Select value={selectedPlantForDept || "none"} onValueChange={(v) => setSelectedPlantForDept(v === "none" ? "" : v)}>
                  <SelectTrigger className="mt-1"><SelectValue placeholder="Choose plant" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Select a plant</SelectItem>
                    {plants.map((p: any) => <SelectItem key={p.id} value={p.id}>{p.name}{p.location ? ` · ${p.location}` : ""}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-xs font-medium">Department Name</label>
                <Input placeholder="e.g., Production, Quality" value={deptName}
                  onChange={(e) => setDeptName(e.target.value)} required className="mt-1" />
              </div>
              <div>
                <label className="text-xs font-medium">Department Type</label>
                <Select value={deptType || "none"} onValueChange={(v) => setDeptType(v === "none" ? "" : v)}>
                  <SelectTrigger className="mt-1"><SelectValue placeholder="Select type" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">General</SelectItem>
                    <SelectItem value="PRODUCTION">Production</SelectItem>
                    <SelectItem value="QUALITY">Quality</SelectItem>
                    <SelectItem value="MAINTENANCE">Maintenance</SelectItem>
                    <SelectItem value="WAREHOUSE">Warehouse</SelectItem>
                    <SelectItem value="SAFETY">Safety</SelectItem>
                    <SelectItem value="HR">HR</SelectItem>
                    <SelectItem value="PLANNING">Planning</SelectItem>
                    <SelectItem value="FINANCE">Finance</SelectItem>
                    <SelectItem value="SUPPLY_CHAIN">Supply Chain</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button type="submit" disabled={createDeptMutation.isPending || !selectedPlantForDept} className="w-full">
                {createDeptMutation.isPending ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Creating...</> : "Create Department"}
              </Button>
            </form>
          </AdminSection>
        )}

        {/* Create Team — Plant → Department → Team cascade */}
        {hasCapability("can_create_teams") && (
          <AdminSection icon={Users} title="Create Team" description="Plant → Department → Team hierarchy">
            <form onSubmit={handleCreateTeam} className="space-y-3">
              <div>
                <label className="text-xs font-medium">Select Plant *</label>
                <Select value={selectedPlantForTeam || "none"} onValueChange={(v) => setSelectedPlantForTeam(v === "none" ? "" : v)}>
                  <SelectTrigger className="mt-1"><SelectValue placeholder="Choose plant" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Select a plant</SelectItem>
                    {plants.map((p: any) => <SelectItem key={p.id} value={p.id}>{p.name}{p.location ? ` · ${p.location}` : ""}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              {selectedPlantForTeam && (
                <div>
                  <label className="text-xs font-medium">Select Department *</label>
                  <Select value={selectedDeptForTeam || "none"} onValueChange={(v) => setSelectedDeptForTeam(v === "none" ? "" : v)}>
                    <SelectTrigger className="mt-1"><SelectValue placeholder="Choose department" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Select a department</SelectItem>
                      {deptsForSelectedPlant.map((d: any) => <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              )}
              <div>
                <label className="text-xs font-medium">Team Name</label>
                <Input placeholder="e.g., Quality Assurance" value={teamName}
                  onChange={(e) => setTeamName(e.target.value)} required className="mt-1" />
              </div>
              {selectedPlantForTeam && plantEmployees.length > 0 && (
                <div className="space-y-2">
                  <label className="text-xs font-medium">Team members (this plant)</label>
                  <p className="text-[11px] text-muted-foreground">Optional — select employees to add to the roster on create.</p>
                  <ScrollArea className="h-[160px] rounded-md border border-border p-2">
                    <div className="space-y-2 pr-2">
                      {plantEmployees.map((e: { id: string; name: string; email: string; system_role?: string }) => (
                        <label key={e.id} className="flex cursor-pointer items-center gap-2 text-xs">
                          <Checkbox
                            checked={teamMemberIds.has(e.id)}
                            onCheckedChange={() => {
                              setTeamMemberIds((prev) => {
                                const n = new Set(prev);
                                if (n.has(e.id)) n.delete(e.id);
                                else n.add(e.id);
                                return n;
                              });
                            }}
                          />
                          <span className="truncate">{e.name} · {e.email}</span>
                        </label>
                      ))}
                    </div>
                  </ScrollArea>
                </div>
              )}
              {plantEmployees.length > 0 && (
                <div>
                  <label className="text-xs font-medium">Team Lead (Optional)</label>
                  <Select value={teamLeadId || "none"} onValueChange={(v) => setTeamLeadId(v === "none" ? "" : v)}>
                    <SelectTrigger className="mt-1"><SelectValue placeholder="Select team lead" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">No Team Lead</SelectItem>
                      {plantEmployees.map((e: any) => <SelectItem key={e.id} value={e.id}>{e.name} · {e.system_role}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              )}
              <Button type="submit" disabled={createTeamMutation.isPending || !selectedDeptForTeam} className="w-full">
                {createTeamMutation.isPending ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Creating...</> : "Create Team"}
              </Button>
            </form>
          </AdminSection>
        )}
      </div>

      {/* Permission Configuration */}
      {hasCapability("can_configure_permissions") && (
        <AdminSection icon={Shield} title="Permission Matrix" description="Configure role-based permissions">
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Manage which roles have access to which modules and features.
            </p>
            <Dialog>
              <DialogTrigger asChild>
                <Button variant="outline" className="w-full">
                  <Shield className="mr-2 h-4 w-4" />
                  Configure Permissions
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl">
                <DialogHeader>
                  <DialogTitle>Permission Matrix</DialogTitle>
                  <DialogDescription>Define which roles can access which modules</DialogDescription>
                </DialogHeader>
                <PermissionMatrixTable />
              </DialogContent>
            </Dialog>
          </div>
        </AdminSection>
      )}

      {/* Cycle Management */}
      {hasCapability("can_configure_permissions") && (
        <AdminSection icon={Calendar} title="Cycle Management" description="Manage OKR cycles (create, freeze, close)">
          <CyclesAdmin />
        </AdminSection>
      )}

      {/* Current User Info */}
      <div className="rounded-lg border border-border bg-muted/50 p-4">
        <h3 className="mb-2 font-semibold">Your Admin Profile</h3>
        <div className="grid gap-2 text-sm">
          <div><span className="font-medium">Name:</span> {user?.name}</div>
          <div><span className="font-medium">Email:</span> {user?.email}</div>
          <div><span className="font-medium">Role:</span> {permissions?.system_role}</div>
          <div><span className="font-medium">Scope:</span> {permissions?.scope_type}</div>
          <div className="pt-2">
            <p className="text-xs font-medium text-muted-foreground">Capabilities:</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {permissions?.can_create_plants && <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-800">Create Plants</span>}
              {permissions?.can_invite_employees && <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-800">Invite Employees</span>}
              {permissions?.can_assign_roles && <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-800">Assign Roles</span>}
              {permissions?.can_configure_permissions && <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-800">Configure Permissions</span>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

interface AdminSectionProps {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
  children: React.ReactNode;
}

function AdminSection({ icon: Icon, title, description, children }: AdminSectionProps) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-4 flex items-start gap-3">
        <Icon className="h-5 w-5 text-primary" />
        <div>
          <h3 className="font-semibold">{title}</h3>
          <p className="text-xs text-muted-foreground">{description}</p>
        </div>
      </div>
      {children}
    </div>
  );
}

function PermissionMatrixTable() {
  const roles = ["SUPER_ADMIN","CEO","VP_OPERATIONS","PLANT_HEAD","DEPT_HEAD","MANAGER","TEAM_LEAD","SUPERVISOR","EMPLOYEE","HR_HEAD"];
  const modules = ["ORG_OKRS","EMPLOYEE_DIRECTORY","APPROVAL_QUEUE","AUDIT_LOGS","TEAM_MANAGEMENT","ALIGNMENT_DASHBOARD"];
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-xs">
        <thead>
          <tr>
            <th className="border border-border bg-muted p-2 text-left">Role</th>
            {modules.map((m) => (
              <th key={m} className="border border-border bg-muted p-2 text-center">{m.replace(/_/g, " ")}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {roles.map((role) => (
            <tr key={role}>
              <td className="border border-border p-2 font-medium">{role}</td>
              {modules.map((m) => (
                <td key={`${role}-${m}`} className="border border-border p-2 text-center">
                  <input type="checkbox" className="h-4 w-4" />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
