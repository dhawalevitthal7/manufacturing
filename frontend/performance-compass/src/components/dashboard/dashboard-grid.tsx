import { useAuthStore } from "@/lib/stores/auth-store";
import { type SystemRole } from "@/lib/api";
import { StatsCard } from "./widgets/stats-card";
import { OKRProgressCard } from "./widgets/okr-progress-card";
import { ExecutionChart } from "./widgets/execution-chart";
import { DepartmentComparison } from "./widgets/department-comparison";
import { QueueWidget } from "./widgets/queue-widget";
import { AIInsightsCard } from "./widgets/ai-insights-card";
import { AlignmentSummary } from "./widgets/alignment-summary";
import { type DashboardResponse, type StatItem } from "@/lib/api";

interface DashboardGridProps {
  dashboard?: DashboardResponse;
}

export function DashboardGrid({ dashboard }: DashboardGridProps) {
  const { user, permissions } = useAuthStore();
  
  if (!user) {
    return <div>Not authenticated</div>;
  }

  // Use backend stats — each stat now returns { label, value, delta, trend, hint }
  const stats: Array<{ id: string; label: string; value: string; delta: number; trend: "up" | "down" | "flat"; hint?: string }> = [];
  
  if (dashboard?.stats) {
    Object.entries(dashboard.stats).forEach(([key, stat]) => {
      const s = stat as StatItem & { hint?: string };
      stats.push({
        id: key,
        label: s.label || key.replace(/_/g, " "),
        value: String(s.value),
        delta: s.delta || 0,
        trend: s.trend || "flat",
        hint: s.hint,
      });
    });
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stats.length > 0 ? (
          stats.map((s, i) => (
            <StatsCard key={s.id} stat={s} index={i} />
          ))
        ) : (
          <div className="col-span-full text-center text-muted-foreground">
            No stats available
          </div>
        )}
      </div>
      <RoleLayout role={user.system_role} dashboard={dashboard} />
    </div>
  );
}

interface RoleLayoutProps {
  role: SystemRole;
  dashboard?: DashboardResponse;
}

function RoleLayout({ role, dashboard }: RoleLayoutProps) {
  const isSuperAdmin = role === "SUPER_ADMIN";
  const isExecutive = role === "CEO" || role === "VP_OPERATIONS";
  const isPlantScope =
    role === "PLANT_HEAD" || role === "PLANT_MANAGER" || role === "DEPT_HEAD";
  const isManagerScope =
    role === "MANAGER" || role === "TEAM_LEAD" || role === "SUPERVISOR";
  const isHR = role === "HR_HEAD" || role === "HR_ADMIN";

  const pendingActions = dashboard?.pending_actions?.slice(0, 5) || [];
  const topObjectives = dashboard?.top_objectives || [];
  const departmentHealth = dashboard?.department_health || [];
  const executionTrend = dashboard?.execution_trend || [];

  if (isSuperAdmin) {
    return (
      <>
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
          <div className="xl:col-span-2"><ExecutionChart data={executionTrend} /></div>
          <AIInsightsCard />
        </div>
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
          <div className="xl:col-span-2"><AlignmentSummary objectives={topObjectives} /></div>
          <DepartmentComparison data={departmentHealth} />
        </div>
        <OKRProgressCard objectives={topObjectives} />
      </>
    );
  }
  
  if (isExecutive || isPlantScope || isHR) {
    return (
      <>
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
          <div className="xl:col-span-2"><ExecutionChart data={executionTrend} /></div>
          <QueueWidget 
            title="Pending Actions" 
            subtitle="Awaiting your sign-off" 
            items={pendingActions.map(a => ({ 
              id: a.id, 
              title: a.title || a.description || "", 
              submittedBy: a.actor_name || "System", 
              scope: a.type,
              submittedAt: a.created_at,
              priority: a.priority || "med"
            }))}
          />
        </div>
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
          <div className="xl:col-span-2"><DepartmentComparison data={departmentHealth} /></div>
          <AIInsightsCard />
        </div>
        <OKRProgressCard objectives={topObjectives} />
      </>
    );
  }
  
  if (isManagerScope) {
    return (
      <>
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          <QueueWidget 
            title="Pending Actions" 
            subtitle="Submitted by your team" 
            items={pendingActions.map(a => ({ 
              id: a.id, 
              title: a.title || a.description || "", 
              submittedBy: a.actor_name || "System", 
              scope: a.type,
              submittedAt: a.created_at,
              priority: a.priority || "med"
            }))}
          />
          <DepartmentComparison data={departmentHealth} />
        </div>
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
          <div className="xl:col-span-2"><ExecutionChart data={executionTrend} /></div>
          <AIInsightsCard />
        </div>
        <OKRProgressCard objectives={topObjectives} />
      </>
    );
  }
  
  // Default: EMPLOYEE and other roles not matched above
  return (
    <>
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="xl:col-span-2"><OKRProgressCard objectives={topObjectives} /></div>
        <QueueWidget
          title="Your Reviews"
          subtitle="Awaiting your input"
          items={pendingActions.filter(a => a.type === "SELF_REVIEW").map(a => ({
            id: a.id,
            title: a.title || "Self Review",
            submittedBy: "You",
            scope: a.type,
            submittedAt: a.created_at,
            priority: a.priority || "med"
          }))}
          emptyText="All caught up."
        />
      </div>
      <ExecutionChart data={executionTrend} />
    </>
  );
}
