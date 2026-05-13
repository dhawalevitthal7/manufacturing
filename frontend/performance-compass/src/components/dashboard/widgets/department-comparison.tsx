import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BarChart3 } from "lucide-react";

interface DepartmentHealthData {
  dept: string;
  plant_name?: string;
  onTrack: number;
  atRisk: number;
  offTrack: number;
  avg_progress?: number;
  objective_count?: number;
  employee_count?: number;
}

interface DepartmentComparisonProps {
  data?: DepartmentHealthData[];
}

export function DepartmentComparison({ data = [] }: DepartmentComparisonProps) {
  if (data.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="mb-4">
          <h3 className="text-sm font-semibold">Department Health</h3>
          <p className="text-xs text-muted-foreground">OKR distribution by status</p>
        </div>
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <BarChart3 className="mb-3 h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm font-medium text-muted-foreground">No department data</p>
          <p className="mt-1 text-xs text-muted-foreground/70">Create departments and assign objectives to visualize health</p>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="mb-4">
        <h3 className="text-sm font-semibold">Department Health</h3>
        <p className="text-xs text-muted-foreground">
          OKR distribution by status · {data.length} department{data.length !== 1 ? "s" : ""}
        </p>
      </div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.27 0.015 260)" vertical={false} />
            <XAxis dataKey="dept" stroke="oklch(0.5 0.02 260)" fontSize={11} tickLine={false} axisLine={false} />
            <YAxis stroke="oklch(0.5 0.02 260)" fontSize={11} tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={{
                background: "oklch(0.17 0.013 260)",
                border: "1px solid oklch(0.27 0.015 260)",
                borderRadius: 8,
                fontSize: 12,
              }}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="onTrack" stackId="a" fill="oklch(0.7 0.18 145)" radius={[0, 0, 0, 0]} name="On track" />
            <Bar dataKey="atRisk" stackId="a" fill="oklch(0.78 0.16 80)" radius={[0, 0, 0, 0]} name="At risk" />
            <Bar dataKey="offTrack" stackId="a" fill="oklch(0.65 0.22 25)" radius={[4, 4, 0, 0]} name="Off track" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
