import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/lib/stores/auth-store";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from "recharts";
import {
  Plus, Eye, FileText, Clock, AlertCircle, CheckCircle2,
  TrendingUp, Zap, Users, Target, Filter
} from "lucide-react";
import { api } from "@/lib/api";
import { useAllowedLevels } from "@/lib/hooks";
import type { ObjectiveLevel } from "@/lib/api";
import { OkrPendingApprovals } from "./okr-pending-approvals";
import { CreateOKRDialog } from "./create-okr-dialog";

interface AccessibleOKR {
  id: string;
  objective: string;
  level_type: string;
  owner?: {
    id: string;
    name: string;
    email: string;
  };
  status: string;
  submission_status: string;
  progress: number;
  quarter: number;
  year: number;
  region_id?: string;
  plant_id?: string;
  department_id?: string;
  team_id?: string;
}

export function OkrHierarchyDashboard() {
  const { user, canCreate, hasCapability } = useAuthStore();
  const { data: allowedLevelsData } = useAllowedLevels(user?.system_role, user?.id);
  const allowedLevels = (allowedLevelsData?.allowed_levels ?? []) as ObjectiveLevel[];
  const [activeTab, setActiveTab] = useState("overview");
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [filterLevel, setFilterLevel] = useState<string>("all");

  // Fetch accessible OKRs
  const { data: okrs = [], isLoading, refetch } = useQuery({
    queryKey: ["accessible-okrs"],
    queryFn: () => api.getAccessibleOKRs(),
    refetchInterval: 60000, // Refetch every minute
  });

  // Get pending approvals if user is an approver
  const { data: pendingApprovals = [] } = useQuery({
    queryKey: ["pending-okr-submissions"],
    queryFn: () => api.getPendingOKRSubmissions(),
    enabled: hasCapability("can_approve_okr_progress"),
    refetchInterval: 30000,
  });

  // Filter OKRs
  const filteredOkrs = useMemo(() => {
    return okrs.filter(okr => {
      const statusMatch = filterStatus === "all" || okr.submission_status === filterStatus;
      const levelMatch = filterLevel === "all" || okr.level_type === filterLevel;
      return statusMatch && levelMatch;
    });
  }, [okrs, filterStatus, filterLevel]);

  // Calculate statistics
  const stats = useMemo(() => {
    return {
      totalOkrs: okrs.length,
      approved: okrs.filter(o => o.submission_status === "approved").length,
      submitted: okrs.filter(o => o.submission_status === "submitted").length,
      draft: okrs.filter(o => o.submission_status === "draft").length,
      avgProgress: okrs.length > 0 
        ? Math.round(okrs.reduce((sum, o) => sum + (o.progress || 0), 0) / okrs.length)
        : 0,
    };
  }, [okrs]);

  // Group OKRs by level for pie chart
  const okrsByLevel = useMemo(() => {
    const levels = new Map<string, number>();
    okrs.forEach(okr => {
      levels.set(okr.level_type, (levels.get(okr.level_type) || 0) + 1);
    });
    return Array.from(levels).map(([name, value]) => ({
      name: name.charAt(0).toUpperCase() + name.slice(1),
      value,
    }));
  }, [okrs]);

  // Progress distribution data
  const progressDistribution = useMemo(() => {
    const ranges = [
      { range: "0-25%", count: 0 },
      { range: "25-50%", count: 0 },
      { range: "50-75%", count: 0 },
      { range: "75-100%", count: 0 },
    ];
    okrs.forEach(okr => {
      const progress = okr.progress || 0;
      if (progress < 25) ranges[0].count++;
      else if (progress < 50) ranges[1].count++;
      else if (progress < 75) ranges[2].count++;
      else ranges[3].count++;
    });
    return ranges;
  }, [okrs]);

  const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444"];

  return (
    <div className="w-full space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">OKR Management</h1>
          <p className="text-muted-foreground">
            Manage objectives and key results across your organization
          </p>
        </div>
        <Button
          onClick={() => setShowCreateDialog(true)}
          className="gap-2"
          disabled={!canCreate("OKR_MANAGE")}
        >
          <Plus className="h-4 w-4" />
          Create OKR
        </Button>
      </div>

      {/* Create OKR Dialog */}
      <CreateOKRDialog
        open={showCreateDialog}
        onOpenChange={(open) => {
          setShowCreateDialog(open);
          if (!open) refetch();
        }}
        allowedLevels={allowedLevels.length > 0 ? allowedLevels : ["INDIVIDUAL"]}
      />

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total OKRs
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold">{stats.totalOkrs}</span>
              <Target className="h-4 w-4 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Approved
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-green-600">{stats.approved}</span>
              <CheckCircle2 className="h-4 w-4 text-green-600" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Submitted
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-yellow-600">{stats.submitted}</span>
              <Clock className="h-4 w-4 text-yellow-600" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Draft
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-gray-600">{stats.draft}</span>
              <FileText className="h-4 w-4 text-gray-600" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Avg Progress
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold">{stats.avgProgress}%</span>
              <TrendingUp className="h-4 w-4 text-blue-600" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Pending Approvals Alert */}
      {pendingApprovals.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex gap-3">
          <AlertCircle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-semibold text-amber-900">
              {pendingApprovals.length} OKR submission{pendingApprovals.length !== 1 ? "s" : ""} awaiting your approval
            </h3>
            <p className="text-sm text-amber-700">
              Review and approve pending submissions in the Approvals tab
            </p>
          </div>
        </div>
      )}

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="all-okrs">All OKRs</TabsTrigger>
          <TabsTrigger value="approvals" disabled={!hasCapability("can_approve_okr_progress")}>
            Approvals {pendingApprovals.length > 0 && `(${pendingApprovals.length})`}
          </TabsTrigger>
          <TabsTrigger value="progress">Progress</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* OKRs by Level */}
            <Card>
              <CardHeader>
                <CardTitle>OKRs by Level</CardTitle>
                <CardDescription>Distribution of OKRs across hierarchy</CardDescription>
              </CardHeader>
              <CardContent>
                {okrsByLevel.length > 0 ? (
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie
                        data={okrsByLevel}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={({ name, value }) => `${name}: ${value}`}
                        outerRadius={80}
                        fill="#8884d8"
                        dataKey="value"
                      >
                        {okrsByLevel.map((_, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-64 flex items-center justify-center text-muted-foreground">
                    No OKRs to display
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Progress Distribution */}
            <Card>
              <CardHeader>
                <CardTitle>Progress Distribution</CardTitle>
                <CardDescription>OKRs by completion percentage</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={progressDistribution}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="range" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="count" fill="#3b82f6" />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>

          {/* OKR Pending Approvals Component */}
          <OkrPendingApprovals />
        </TabsContent>

        {/* All OKRs Tab */}
        <TabsContent value="all-okrs" className="space-y-4">
          {/* Filters */}
          <div className="flex gap-2 items-center">
            <Filter className="h-4 w-4 text-muted-foreground" />
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="px-3 py-1 rounded border border-input text-sm"
            >
              <option value="all">All Status</option>
              <option value="draft">Draft</option>
              <option value="submitted">Submitted</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
            </select>
            <select
              value={filterLevel}
              onChange={(e) => setFilterLevel(e.target.value)}
              className="px-3 py-1 rounded border border-input text-sm"
            >
              <option value="all">All Levels</option>
              <option value="organization">Organization</option>
              <option value="region">Region</option>
              <option value="plant">Plant</option>
              <option value="department">Department</option>
              <option value="team">Team</option>
              <option value="employee">Employee</option>
            </select>
          </div>

          {/* OKR List */}
          <div className="space-y-2">
            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
              </div>
            ) : filteredOkrs.length === 0 ? (
              <Card>
                <CardContent className="py-12 text-center">
                  <Target className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
                  <p className="text-muted-foreground">No OKRs found</p>
                </CardContent>
              </Card>
            ) : (
              filteredOkrs.map((okr) => (
                <Card key={okr.id} className="hover:shadow-md transition-shadow">
                  <CardContent className="pt-6">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <h3 className="font-semibold">{okr.objective}</h3>
                        <div className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
                          <Badge variant="outline">{okr.level_type}</Badge>
                          {okr.owner && (
                            <>
                              <Users className="h-3 w-3" />
                              <span>{okr.owner.name}</span>
                            </>
                          )}
                          <span>Q{okr.quarter}/{okr.year}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="text-right">
                          <div className="text-2xl font-bold text-blue-600">{okr.progress}%</div>
                          <Badge 
                            variant={
                              okr.submission_status === "approved" ? "default" :
                              okr.submission_status === "submitted" ? "secondary" :
                              "outline"
                            }
                            className="mt-1"
                          >
                            {okr.submission_status}
                          </Badge>
                        </div>
                        <Button variant="ghost" size="sm">
                          <Eye className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </TabsContent>

        {/* Approvals Tab */}
        <TabsContent value="approvals">
          {hasCapability("can_approve_okr_progress") && <OkrPendingApprovals />}
        </TabsContent>

        {/* Progress Tab */}
        <TabsContent value="progress" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>OKR Progress Timeline</CardTitle>
              <CardDescription>Progress tracking over time</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={400}>
                <LineChart data={progressDistribution}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="range" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="count"
                    stroke="#3b82f6"
                    name="OKR Count"
                    connectNulls
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
