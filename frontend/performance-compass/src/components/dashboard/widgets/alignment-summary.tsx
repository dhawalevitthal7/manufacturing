import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Network } from "lucide-react";

interface ObjectiveNode {
  id: string;
  objective: string;
  scope: string;
  level?: string;
  progress: number;
  status: string;
  owner: string;
}

interface AlignmentSummaryProps {
  objectives?: ObjectiveNode[];
}

const levelLabel: Record<string, string> = {
  ORGANIZATION: "Organization",
  PLANT: "Plant",
  DEPARTMENT: "Department",
  TEAM: "Team",
  INDIVIDUAL: "Individual",
};

const levelOrder = ["ORGANIZATION", "PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"];

export function AlignmentSummary({ objectives = [] }: AlignmentSummaryProps) {
  if (objectives.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="mb-4">
          <h3 className="text-sm font-semibold">Strategic Alignment</h3>
          <p className="text-xs text-muted-foreground">Cascade from objective to execution</p>
        </div>
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Network className="mb-3 h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm font-medium text-muted-foreground">No alignment data</p>
          <p className="mt-1 text-xs text-muted-foreground/70">Create objectives at different levels to see alignment cascade</p>
        </div>
      </div>
    );
  }

  // Group objectives by level
  const grouped = levelOrder
    .map((lvl) => ({
      level: lvl,
      label: levelLabel[lvl] || lvl,
      nodes: objectives.filter((o) => (o.level || "INDIVIDUAL") === lvl),
    }))
    .filter((g) => g.nodes.length > 0);

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="mb-4">
        <h3 className="text-sm font-semibold">Strategic Alignment</h3>
        <p className="text-xs text-muted-foreground">Cascade from objective to execution · {objectives.length} objectives</p>
      </div>
      <div className="space-y-4">
        {grouped.map((group, lvlIdx) => (
          <div key={group.level}>
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              {group.label}
            </div>
            <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${Math.max(group.nodes.length, 1)}, minmax(0, 1fr))` }}>
              {group.nodes.map((n, i) => {
                const tone =
                  n.progress >= 70
                    ? "border-success/40 bg-success/5"
                    : n.progress >= 50
                      ? "border-warning/40 bg-warning/5"
                      : "border-destructive/40 bg-destructive/5";
                return (
                  <motion.div
                    key={n.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: lvlIdx * 0.1 + i * 0.04 }}
                    className={cn("rounded-lg border p-2.5", tone)}
                  >
                    <div className="line-clamp-2 text-xs font-medium">{n.objective}</div>
                    <div className="mt-1 text-[10px] text-muted-foreground">{n.scope}</div>
                    <div className="mt-2 flex items-center justify-between text-[10px] text-muted-foreground">
                      <span>Progress</span>
                      <span className="font-mono text-foreground">{n.progress}%</span>
                    </div>
                    <div className="mt-1 h-1 overflow-hidden rounded-full bg-muted">
                      <div
                        className={cn(
                          "h-full rounded-full",
                          n.progress >= 70 ? "bg-success" : n.progress >= 50 ? "bg-warning" : "bg-destructive",
                        )}
                        style={{ width: `${n.progress}%` }}
                      />
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
