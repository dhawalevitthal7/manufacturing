import { createFileRoute } from "@tanstack/react-router";
import { useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { DashboardGrid } from "@/components/dashboard/dashboard-grid";
import { useAuthStore } from "@/lib/stores/auth-store";
import { api } from "@/lib/api";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle } from "lucide-react";

export const Route = createFileRoute("/")({
  component: DashboardPage,
});

function DashboardPage() {
  const user = useAuthStore((s) => s.user);
  const navigate = useNavigate();
  
  // Fetch dashboard data from API
  const { data: dashboard, isLoading, error } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api.getDashboard(),
  });

  const handleExportDashboard = () => {
    if (!dashboard) return;

    const exportPayload = JSON.stringify(dashboard, null, 2);
    const blob = new Blob([exportPayload], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = `dashboard-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  if (!user) {
    return (
      <div className="flex items-center justify-center py-8">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>Not authenticated. Please log in.</AlertDescription>
        </Alert>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <p className="text-muted-foreground">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-8">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {error instanceof Error ? error.message : "Failed to load dashboard"}
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-wider text-muted-foreground">
            Welcome back, {user.name.split(" ")[0]}
          </p>
          <h2 className="mt-1 text-2xl font-semibold tracking-tight">Dashboard</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {user.system_role === "EMPLOYEE" ? "Your OKR progress and reviews" : "OKR alignment and progress"}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleExportDashboard}
            disabled={!dashboard}
            className="rounded-md border border-border bg-card px-3 py-2 text-sm font-medium hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
          >
            Export
          </button>
          <button
            type="button"
            onClick={() => navigate({ to: "/okrs" })}
            className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            New OKR
          </button>
        </div>
      </div>
      <DashboardGrid dashboard={dashboard} />
    </div>
  );
}
