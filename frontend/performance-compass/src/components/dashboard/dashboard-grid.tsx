import { useAuthStore } from "@/lib/stores/auth-store";
import { OKRProgressCard } from "./widgets/okr-progress-card";
import { DashboardConstellation } from "./dashboard-constellation";
import { type DashboardResponse } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Link } from "@tanstack/react-router";
import { Network } from "lucide-react";

interface DashboardGridProps {
  dashboard?: DashboardResponse;
}

export function DashboardGrid({ dashboard }: DashboardGridProps) {
  const { user } = useAuthStore();

  if (!user) {
    return <div>Not authenticated</div>;
  }

  const topObjectives = dashboard?.top_objectives || [];
  const orgId = user.org_id;
  const showConstellation = user.system_role !== "EMPLOYEE";

  return (
    <div className="space-y-6">
      {showConstellation && (
        <>
          <DashboardConstellation orgId={orgId} height={620} />

          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-muted-foreground">
              Drag and zoom the map above · Full screen alignment view available
            </p>
            <Button variant="outline" size="sm" asChild>
              <Link to="/alignment">
                <Network className="mr-2 h-4 w-4" />
                Open alignment view
              </Link>
            </Button>
          </div>
        </>
      )}

      <OKRProgressCard objectives={topObjectives} />
    </div>
  );
}
