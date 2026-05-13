import { useState, useMemo } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useEmployees, usePlants, useDepartments } from "@/lib/hooks";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { AlertCircle, Loader2, Users, Shield, Filter } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export const Route = createFileRoute("/employees")({
  head: () => ({
    meta: [
      { title: "Employees — Axis Operate" },
      { name: "description", content: "Hierarchy-aware employee directory with organizational visibility." },
    ],
  }),
  component: EmployeesPage,
});

// Leadership roles are globally visible
const LEADERSHIP_ROLES = ["CEO", "VP_OPERATIONS", "PLANT_HEAD", "DEPT_HEAD", "SUPER_ADMIN", "HR_HEAD", "HR_ADMIN"];
// Operational roles need hierarchy filters
const OPERATIONAL_ROLES = ["MANAGER", "SUPERVISOR", "TEAM_LEAD", "EMPLOYEE", "PLANT_MANAGER"];

function EmployeesPage() {
  const [selectedPlant, setSelectedPlant] = useState("");
  const [selectedDept, setSelectedDept] = useState("");

  const { data: allEmployees = [], isLoading, error } = useEmployees({ is_active: true });
  const { data: plants = [] } = usePlants();
  const { data: departments = [] } = useDepartments(selectedPlant || undefined);

  // Split employees into leadership (always visible) and operational (hierarchy-filtered)
  const { leadership, operational } = useMemo(() => {
    const lead: any[] = [];
    const ops: any[] = [];
    for (const emp of allEmployees) {
      if (LEADERSHIP_ROLES.includes(emp.system_role)) {
        lead.push(emp);
      } else {
        ops.push(emp);
      }
    }
    return { leadership: lead, operational: ops };
  }, [allEmployees]);

  // Filter operational employees by selected hierarchy
  const filteredOperational = useMemo(() => {
    let filtered = operational;
    if (selectedPlant) {
      filtered = filtered.filter((e: any) => {
        const plantId = e.assignments?.plant_id || e.plant_id;
        return plantId === selectedPlant;
      });
    }
    if (selectedDept) {
      filtered = filtered.filter((e: any) => {
        const deptId = e.assignments?.department_id || e.department_id;
        return deptId === selectedDept;
      });
    }
    return filtered;
  }, [operational, selectedPlant, selectedDept]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-muted-foreground" />
          <p className="mt-2 text-sm text-muted-foreground">Loading employees...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <div>
          <h2 className="text-2xl font-semibold">Employees</h2>
          <p className="text-sm text-muted-foreground">Hierarchy-aware employee directory.</p>
        </div>
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {error instanceof Error ? error.message : "Failed to load employees"}
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold">Employees</h2>
        <p className="text-sm text-muted-foreground">
          {allEmployees.length} employee{allEmployees.length !== 1 ? "s" : ""} in your organization
        </p>
      </div>

      {/* Leadership Section — Always Visible */}
      {leadership.length > 0 && (
        <div>
          <div className="mb-3 flex items-center gap-2">
            <Shield className="h-4 w-4 text-primary" />
            <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Leadership ({leadership.length})
            </h3>
          </div>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {leadership.map((emp: any) => (
              <EmployeeCard key={emp.id} emp={emp} isLeadership />
            ))}
          </div>
        </div>
      )}

      {/* Hierarchy Filters for Operational Employees */}
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold">Hierarchy Filters</h3>
        </div>
        <div className="flex flex-wrap gap-3">
          <div className="min-w-[200px]">
            <label className="text-xs font-medium text-muted-foreground">Plant</label>
            <Select value={selectedPlant || "all"} onValueChange={(v) => { setSelectedPlant(v === "all" ? "" : v); setSelectedDept(""); }}>
              <SelectTrigger className="mt-1">
                <SelectValue placeholder="All Plants" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Plants</SelectItem>
                {plants.map((p: any) => (
                  <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {selectedPlant && (
            <div className="min-w-[200px]">
              <label className="text-xs font-medium text-muted-foreground">Department</label>
              <Select value={selectedDept || "all"} onValueChange={(v) => setSelectedDept(v === "all" ? "" : v)}>
                <SelectTrigger className="mt-1">
                  <SelectValue placeholder="All Departments" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Departments</SelectItem>
                  {departments.map((d: any) => (
                    <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
        </div>
      </div>

      {/* Operational Employees — Filtered by Hierarchy */}
      <div>
        <div className="mb-3 flex items-center gap-2">
          <Users className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Operational Staff ({filteredOperational.length})
          </h3>
        </div>
        {filteredOperational.length > 0 ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {filteredOperational.map((emp: any) => (
              <EmployeeCard key={emp.id} emp={emp} />
            ))}
          </div>
        ) : (
          <Card>
            <CardContent className="pt-6">
              <div className="text-center py-4">
                <Users className="mx-auto mb-2 h-8 w-8 text-muted-foreground/40" />
                <p className="text-muted-foreground">
                  {selectedPlant || selectedDept
                    ? "No operational employees match the selected filters"
                    : "No operational employees found"}
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

function EmployeeCard({ emp, isLeadership = false }: { emp: any; isLeadership?: boolean }) {
  const initials = emp.name
    .split(" ")
    .map((n: string) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader>
        <div className="flex items-start gap-4">
          <Avatar className="h-10 w-10 shrink-0">
            <AvatarFallback
              className="font-semibold text-primary-foreground"
              style={{ backgroundColor: emp.avatar_color || (isLeadership ? "#6366f1" : "#8b5cf6") }}
            >
              {initials}
            </AvatarFallback>
          </Avatar>
          <div className="flex-1 min-w-0">
            <CardTitle className="text-base">{emp.name}</CardTitle>
            <p className="text-xs text-muted-foreground mt-0.5">{emp.email}</p>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          <div className="flex gap-2 flex-wrap">
            <Badge variant={isLeadership ? "default" : "outline"}>{emp.system_role}</Badge>
            {emp.employee_id && <Badge variant="secondary">{emp.employee_id}</Badge>}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
