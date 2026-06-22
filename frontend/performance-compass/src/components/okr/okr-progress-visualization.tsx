import { useMemo } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  LineChart, Line, BarChart, Bar, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  ComposedChart
} from "recharts";
import {
  TrendingUp, TrendingDown, AlertCircle, CheckCircle2,
  Zap, Target, Clock, Flame
} from "lucide-react";
import { cn } from "@/lib/utils";

interface KeyResult {
  id: string;
  title: string;
  target_value: number;
  current_value: number;
  unit: string;
  start_value: number;
  expected_progress: number;
  progress_pct: number;
  trend: "ahead" | "on_track" | "behind" | "critical_delay";
  is_lower_better?: boolean;
}

interface OKRProgressProps {
  objective: string;
  keyResults: KeyResult[];
  overallProgress: number;
  deadline: string;
  owner: { name: string; email: string } | null;
  level: string;
}

export function OKRProgressVisualization({
  objective,
  keyResults,
  overallProgress,
  deadline,
  owner,
  level,
}: OKRProgressProps) {
  // Calculate trend metrics
  const trendMetrics = useMemo(() => {
    const onTrack = keyResults.filter(kr => kr.trend === "on_track").length;
    const ahead = keyResults.filter(kr => kr.trend === "ahead").length;
    const behind = keyResults.filter(kr => kr.trend === "behind").length;
    const critical = keyResults.filter(kr => kr.trend === "critical_delay").length;
    
    return { onTrack, ahead, behind, critical };
  }, [keyResults]);

  // Generate mock historical data for charts
  const historicalData = useMemo(() => {
    return [
      { week: "W1", progress: 10, expected: 12 },
      { week: "W2", progress: 15, expected: 25 },
      { week: "W3", progress: 22, expected: 37 },
      { week: "W4", progress: 28, expected: 50 },
      { week: "W5", progress: 35, expected: 62 },
      { week: "W6", progress: 40, expected: 75 },
      { week: "W7", progress: 45, expected: 87 },
      { week: "W8", progress: overallProgress, expected: 100 },
    ];
  }, [overallProgress]);

  // Get status colors and icons
  const getTrendColor = (trend: string) => {
    switch (trend) {
      case "ahead":
        return "text-green-600";
      case "on_track":
        return "text-blue-600";
      case "behind":
        return "text-amber-600";
      case "critical_delay":
        return "text-red-600";
      default:
        return "text-gray-600";
    }
  };

  const getTrendBadge = (trend: string) => {
    switch (trend) {
      case "ahead":
        return { label: "Ahead", color: "bg-green-100 text-green-800 border-green-300" };
      case "on_track":
        return { label: "On Track", color: "bg-blue-100 text-blue-800 border-blue-300" };
      case "behind":
        return { label: "Behind", color: "bg-amber-100 text-amber-800 border-amber-300" };
      case "critical_delay":
        return { label: "Critical", color: "bg-red-100 text-red-800 border-red-300" };
      default:
        return { label: "Unknown", color: "bg-gray-100 text-gray-800 border-gray-300" };
    }
  };

  const daysUntilDeadline = useMemo(() => {
    const deadline_date = new Date(deadline);
    const today = new Date();
    const diff = deadline_date.getTime() - today.getTime();
    return Math.ceil(diff / (1000 * 60 * 60 * 24));
  }, [deadline]);

  return (
    <div className="space-y-6 w-full">
      {/* Main OKR Header */}
      <Card className="border-blue-200 bg-gradient-to-r from-blue-50 to-transparent">
        <CardContent className="pt-6">
          <div className="space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <h2 className="text-2xl font-bold">{objective}</h2>
                {owner && (
                  <p className="text-sm text-muted-foreground mt-1">
                    Owner: {owner.name} ({owner.email})
                  </p>
                )}
              </div>
              <div className="text-right">
                <div className="text-5xl font-bold text-blue-600">{overallProgress}%</div>
                <Badge className="mt-2 bg-blue-600">{level} Level</Badge>
              </div>
            </div>
            
            {/* Overall Progress Bar */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">Overall Progress</span>
                <span className="text-muted-foreground">{Math.round(overallProgress)}%</span>
              </div>
              <Progress value={overallProgress} className="h-3" />
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>Start</span>
                <span>{daysUntilDeadline} days until deadline</span>
                <span>Target</span>
              </div>
            </div>

            {/* Status Summary */}
            <div className="grid grid-cols-4 gap-2 pt-2">
              <div className="p-2 rounded bg-green-50 border border-green-200">
                <div className="text-sm font-semibold text-green-700">{trendMetrics.ahead}</div>
                <div className="text-xs text-green-600">Ahead</div>
              </div>
              <div className="p-2 rounded bg-blue-50 border border-blue-200">
                <div className="text-sm font-semibold text-blue-700">{trendMetrics.onTrack}</div>
                <div className="text-xs text-blue-600">On Track</div>
              </div>
              <div className="p-2 rounded bg-amber-50 border border-amber-200">
                <div className="text-sm font-semibold text-amber-700">{trendMetrics.behind}</div>
                <div className="text-xs text-amber-600">Behind</div>
              </div>
              <div className="p-2 rounded bg-red-50 border border-red-200">
                <div className="text-sm font-semibold text-red-700">{trendMetrics.critical}</div>
                <div className="text-xs text-red-600">Critical</div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Progress Over Time */}
      <Card>
        <CardHeader>
          <CardTitle>Progress Trajectory</CardTitle>
          <CardDescription>Actual vs Expected progress over time</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={historicalData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="week" />
              <YAxis />
              <Tooltip 
                formatter={(value) => `${value}%`}
                labelFormatter={(label) => `${label}`}
              />
              <Legend />
              <Area
                type="monotone"
                dataKey="expected"
                fill="#e0f2fe"
                stroke="#0ea5e9"
                fillOpacity={0.3}
                name="Expected Progress"
              />
              <Line
                type="monotone"
                dataKey="progress"
                stroke="#2563eb"
                strokeWidth={3}
                name="Actual Progress"
                dot={{ fill: "#2563eb" }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Key Results Detail */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold">Key Results</h3>
          <span className="text-sm text-muted-foreground">{keyResults.length} KRs</span>
        </div>

        {keyResults.map((kr, index) => {
          const badge = getTrendBadge(kr.trend);
          const variance = kr.progress_pct - kr.expected_progress;
          const isAhead = variance > 0;

          return (
            <Card key={kr.id} className="hover:shadow-md transition-shadow">
              <CardContent className="pt-6">
                <div className="space-y-3">
                  {/* KR Header */}
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm">KR {index + 1}:</span>
                        <h4 className="font-semibold">{kr.title}</h4>
                      </div>
                      <div className="mt-1 flex items-center gap-2">
                        <Badge variant="outline" className={badge.color}>
                          {badge.label}
                        </Badge>
                        {isAhead ? (
                          <div className="flex items-center gap-1 text-green-600 text-sm">
                            <TrendingUp className="h-3 w-3" />
                            +{variance.toFixed(1)}%
                          </div>
                        ) : variance < 0 ? (
                          <div className="flex items-center gap-1 text-red-600 text-sm">
                            <TrendingDown className="h-3 w-3" />
                            {variance.toFixed(1)}%
                          </div>
                        ) : null}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-3xl font-bold text-blue-600">{kr.progress_pct}%</div>
                      <div className="text-xs text-muted-foreground mt-1">
                        {kr.current_value.toFixed(1)} / {kr.target_value} {kr.unit}
                      </div>
                    </div>
                  </div>

                  {/* Progress Bar */}
                  <div className="space-y-1">
                    <Progress value={kr.progress_pct} className="h-2" />
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>{kr.start_value} {kr.unit}</span>
                      <span>Expected: {kr.expected_progress}%</span>
                      <span>{kr.target_value} {kr.unit}</span>
                    </div>
                  </div>

                  {/* Value Changes */}
                  <div className="grid grid-cols-3 gap-2 text-xs">
                    <div className="p-2 bg-gray-50 rounded">
                      <div className="text-muted-foreground">Start</div>
                      <div className="font-semibold">{kr.start_value}</div>
                    </div>
                    <div className="p-2 bg-blue-50 rounded">
                      <div className="text-muted-foreground">Current</div>
                      <div className="font-semibold text-blue-700">{kr.current_value.toFixed(1)}</div>
                    </div>
                    <div className="p-2 bg-green-50 rounded">
                      <div className="text-muted-foreground">Target</div>
                      <div className="font-semibold text-green-700">{kr.target_value}</div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Insights and Recommendations */}
      {trendMetrics.critical > 0 && (
        <Card className="border-red-200 bg-red-50">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2 text-red-700">
              <AlertCircle className="h-5 w-5" />
              Critical Issues
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-red-700">
            <p>
              {trendMetrics.critical} Key Result{trendMetrics.critical !== 1 ? "s" : ""} is in critical status.
              Immediate action may be required to get back on track.
            </p>
          </CardContent>
        </Card>
      )}

      {trendMetrics.behind > 0 && trendMetrics.critical === 0 && (
        <Card className="border-amber-200 bg-amber-50">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2 text-amber-700">
              <Zap className="h-5 w-5" />
              Behind Schedule
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-amber-700">
            <p>
              {trendMetrics.behind} Key Result{trendMetrics.behind !== 1 ? "s" : ""} are behind schedule.
              Consider reviewing and adjusting your action plans.
            </p>
          </CardContent>
        </Card>
      )}

      {trendMetrics.critical === 0 && trendMetrics.behind === 0 && trendMetrics.ahead > 0 && (
        <Card className="border-green-200 bg-green-50">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2 text-green-700">
              <CheckCircle2 className="h-5 w-5" />
              Great Progress!
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-green-700">
            <p>
              {trendMetrics.ahead} Key Result{trendMetrics.ahead !== 1 ? "s" : ""} ahead of schedule.
              Maintain this momentum!
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
