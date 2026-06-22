import { ChevronRight, Target, TrendingUp, AlertTriangle, XCircle, CheckCircle } from "lucide-react";
import { cn } from "@/lib/utils";

type ObjectiveStatus = "on_track" | "at_risk" | "off_track" | "completed";

interface OKRItemData {
  id: string;
  objective: string;
  owner: string;
  scope: string;
  level?: string;
  progress: number;
  status: ObjectiveStatus;
  parent_objective?: string | null;
  key_results?: { title: string; progress: number }[];
}

const statusStyles: Record<ObjectiveStatus, string> = {
  on_track: "bg-success/15 text-success border-success/30",
  at_risk: "bg-warning/15 text-warning border-warning/30",
  off_track: "bg-destructive/15 text-destructive border-destructive/30",
  completed: "bg-info/15 text-info border-info/30",
};

const statusLabel: Record<ObjectiveStatus, string> = {
  on_track: "On track",
  at_risk: "At risk",
  off_track: "Off track",
  completed: "Completed",
};

const statusIcon: Record<ObjectiveStatus, React.ComponentType<{ className?: string }>> = {
  on_track: TrendingUp,
  at_risk: AlertTriangle,
  off_track: XCircle,
  completed: CheckCircle,
};

interface OKRProgressCardProps {
  objectives?: OKRItemData[];
}

export function OKRProgressCard({ objectives = [] }: OKRProgressCardProps) {
  if (objectives.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-card">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div>
            <h3 className="text-sm font-semibold">Top Objectives</h3>
            <p className="text-xs text-muted-foreground">Highest-impact OKRs in your scope</p>
          </div>
        </div>
        <div className="flex flex-col items-center justify-center px-5 py-12 text-center">
          <Target className="mb-3 h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm font-medium text-muted-foreground">No objectives yet</p>
          <p className="mt-1 text-xs text-muted-foreground/70">Create objectives to see them here</p>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <div>
          <h3 className="text-sm font-semibold">Top Objectives</h3>
          <p className="text-xs text-muted-foreground">Progress on key objectives</p>
        </div>
        <button className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline">
          View all <ChevronRight className="h-3 w-3" />
        </button>
      </div>
      <ul className="divide-y divide-border">
        {objectives.map((okr) => {
          const StatusIcon = statusIcon[okr.status] || TrendingUp;
          return (
            <li key={okr.id} className="px-5 py-4 transition-colors hover:bg-muted/20">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={cn("inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-medium", statusStyles[okr.status])}>
                      <StatusIcon className="h-2.5 w-2.5" />
                      {statusLabel[okr.status]}
                    </span>
                    <span className="text-[11px] text-muted-foreground">{okr.scope}</span>
                    {okr.level && (
                      <span className="rounded bg-muted px-1 py-0.5 text-[9px] font-medium uppercase tracking-wider text-muted-foreground">
                        {okr.level}
                      </span>
                    )}
                  </div>
                  <div className="mt-1.5 truncate text-sm font-medium">{okr.objective}</div>
                  <div className="mt-0.5 flex items-center gap-2 text-[11px] text-muted-foreground">
                    <span>Owner · {okr.owner}</span>
                    {okr.parent_objective && (
                      <>
                        <span>·</span>
                        <span className="truncate italic">↑ {okr.parent_objective}</span>
                      </>
                    )}
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-mono text-lg font-semibold">{okr.progress}%</div>
                  <div className="text-[10px] uppercase tracking-wider text-muted-foreground">progress</div>
                </div>
              </div>
              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted">
                <div
                  className={cn(
                    "h-full rounded-full transition-all",
                    okr.status === "completed" && "bg-info",
                    okr.status === "on_track" && "bg-success",
                    okr.status === "at_risk" && "bg-warning",
                    okr.status === "off_track" && "bg-destructive",
                  )}
                  style={{ width: `${Math.min(okr.progress, 100)}%` }}
                />
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
