import { motion } from "framer-motion";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

export interface StatCardData {
  id: string;
  label: string;
  value: string;
  delta: number;
  trend: "up" | "down" | "flat";
  hint?: string;
}

export function StatsCard({ stat, index = 0 }: { stat: StatCardData; index?: number }) {
  const trendColor =
    stat.trend === "up"
      ? "text-success"
      : stat.trend === "down"
        ? "text-destructive"
        : "text-muted-foreground";
  const Icon = stat.trend === "up" ? ArrowUpRight : stat.trend === "down" ? ArrowDownRight : Minus;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, duration: 0.3 }}
      className="group relative overflow-hidden rounded-xl border border-border bg-card p-5"
    >
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/40 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
      <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        {stat.label}
      </div>
      <div className="mt-3 flex items-baseline gap-2">
        <span className="font-mono text-3xl font-semibold tracking-tight">{stat.value}</span>
        {stat.delta !== 0 && (
          <span className={cn("inline-flex items-center gap-0.5 text-xs font-medium", trendColor)}>
            <Icon className="h-3 w-3" />
            {Math.abs(stat.delta)}
            {typeof stat.delta === "number" && Number.isFinite(stat.delta) ? "%" : ""}
          </span>
        )}
      </div>
      {stat.hint && <div className="mt-1 text-xs text-muted-foreground">{stat.hint}</div>}
    </motion.div>
  );
}
