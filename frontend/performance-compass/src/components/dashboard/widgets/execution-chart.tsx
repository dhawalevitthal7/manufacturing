import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { TrendingUp } from "lucide-react";

interface ExecutionDataPoint {
  week: string;
  planned: number;
  actual: number;
}

interface ExecutionChartProps {
  data?: ExecutionDataPoint[];
}

export function ExecutionChart({ data = [] }: ExecutionChartProps) {
  if (data.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold">Execution Trend</h3>
            <p className="text-xs text-muted-foreground">Planned vs actual progress</p>
          </div>
        </div>
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <TrendingUp className="mb-3 h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm font-medium text-muted-foreground">No execution data yet</p>
          <p className="mt-1 text-xs text-muted-foreground/70">Progress updates will populate this chart</p>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold">Execution Trend</h3>
          <p className="text-xs text-muted-foreground">Planned vs actual progress</p>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-primary" />
            Planned
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-accent" />
            Actual
          </span>
        </div>
      </div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <defs>
              <linearGradient id="planned" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="oklch(0.68 0.17 250)" stopOpacity={0.4} />
                <stop offset="100%" stopColor="oklch(0.68 0.17 250)" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="actual" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="oklch(0.72 0.19 165)" stopOpacity={0.4} />
                <stop offset="100%" stopColor="oklch(0.72 0.19 165)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.27 0.015 260)" vertical={false} />
            <XAxis dataKey="week" stroke="oklch(0.5 0.02 260)" fontSize={11} tickLine={false} axisLine={false} />
            <YAxis stroke="oklch(0.5 0.02 260)" fontSize={11} tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={{
                background: "oklch(0.17 0.013 260)",
                border: "1px solid oklch(0.27 0.015 260)",
                borderRadius: 8,
                fontSize: 12,
              }}
            />
            <Area type="monotone" dataKey="planned" stroke="oklch(0.68 0.17 250)" strokeWidth={2} fill="url(#planned)" />
            <Area type="monotone" dataKey="actual" stroke="oklch(0.72 0.19 165)" strokeWidth={2} fill="url(#actual)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
