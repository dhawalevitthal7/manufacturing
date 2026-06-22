import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  AlertCircle,
  TrendingUp,
  Target,
  Users,
  Award,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import { type ReviewCalculation, type ReviewRating } from "@/lib/api";

interface ReviewScoringVisualizationProps {
  calculation: ReviewCalculation;
}

const ratingConfig: Record<ReviewRating, { color: string; bg: string; icon: React.ComponentType<{ className?: string }> }> = {
  EXCEEDS_EXPECTATIONS: {
    color: "text-emerald-600",
    bg: "bg-emerald-50 border-emerald-200",
    icon: Award,
  },
  MEETS_EXPECTATIONS: {
    color: "text-blue-600",
    bg: "bg-blue-50 border-blue-200",
    icon: CheckCircle2,
  },
  BELOW_EXPECTATIONS: {
    color: "text-amber-600",
    bg: "bg-amber-50 border-amber-200",
    icon: AlertTriangle,
  },
  NEEDS_IMPROVEMENT: {
    color: "text-red-600",
    bg: "bg-red-50 border-red-200",
    icon: AlertCircle,
  },
};

const componentConfig = [
  {
    label: "OKR Achievement",
    key: "okr_achievement_score" as const,
    weight: 40,
    icon: Target,
    description: "Progress on key objectives",
  },
  {
    label: "KR Quality",
    key: "kr_quality_score" as const,
    weight: 20,
    icon: TrendingUp,
    description: "Quality of execution",
  },
  {
    label: "Manager Feedback",
    key: "manager_feedback_score" as const,
    weight: 15,
    icon: Users,
    description: "Manager assessment",
  },
  {
    label: "Competencies",
    key: "behavioral_competency_score" as const,
    weight: 10,
    icon: Award,
    description: "Behavioral competencies",
  },
  {
    label: "Peer Feedback",
    key: "peer_feedback_score" as const,
    weight: 10,
    icon: Users,
    description: "360 feedback insights",
  },
  {
    label: "Check-Ins",
    key: "continuous_checkin_score" as const,
    weight: 5,
    icon: CheckCircle2,
    description: "Weekly engagement",
  },
];

function isComponentAvailable(
  calculation: ReviewCalculation,
  key: (typeof componentConfig)[number]["key"]
): boolean {
  const score = calculation[key];
  if (score != null && !Number.isNaN(score)) {
    return true;
  }
  if (calculation.component_available) {
    if (calculation.component_available[key] === true) return true;
    const shortKey = key.replace(/_score$/, "");
    if (calculation.component_available[shortKey] === true) return true;
  }
  return false;
}

export function ReviewScoringVisualization({ calculation }: ReviewScoringVisualizationProps) {
  const config = ratingConfig[calculation.final_rating];
  const RatingIcon = config.icon;
  const availableCount = componentConfig.filter((c) =>
    isComponentAvailable(calculation, c.key)
  ).length;

  return (
    <div className="space-y-6">
      {/* Overall Score */}
      <Card className={`border-2 ${config.bg}`}>
        <CardContent className="pt-6">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">Final Performance Rating</p>
              <div className="flex items-baseline gap-2">
                <span className={`text-5xl font-bold ${config.color}`}>
                  {calculation.calculated_final_score.toFixed(1)}
                </span>
                <span className="text-xl text-muted-foreground">/100</span>
              </div>
              <Badge className={`mt-2 gap-1 ${config.color}`}>
                <RatingIcon className="h-3 w-3" />
                {calculation.final_rating.replace(/_/g, " ")}
              </Badge>
              {calculation.confidence_score < 100 && (
                <p className="text-xs text-muted-foreground max-w-sm">
                  Preview score from {availableCount} of {componentConfig.length} data sources.
                  Manager review and peer feedback will refine this after submission.
                </p>
              )}
            </div>
            <div className="text-right space-y-2">
              <div className="text-sm">
                <p className="text-muted-foreground">Data Confidence</p>
                <p className="text-2xl font-semibold">{calculation.confidence_score.toFixed(0)}%</p>
              </div>
              <p className="text-xs text-muted-foreground">
                {availableCount} of {componentConfig.length} components with real data
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Score Breakdown */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Target className="h-5 w-5" />
            Score Breakdown
          </CardTitle>
          <CardDescription>Component scores weighted by importance</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {componentConfig.map((component) => {
            const score = calculation[component.key];
            const hasData = isComponentAvailable(calculation, component.key);
            const Icon = component.icon;

            return (
              <div key={component.key} className="space-y-3">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-semibold flex items-center gap-2">
                      <Icon className="h-4 w-4 text-muted-foreground" />
                      {component.label}
                    </p>
                    <p className="text-xs text-muted-foreground">{component.description}</p>
                  </div>
                  <div className="text-right">
                    {hasData && score != null ? (
                      <p className="text-lg font-bold">{score.toFixed(1)}</p>
                    ) : (
                      <Badge variant="outline" className="text-xs">
                        Awaiting data
                      </Badge>
                    )}
                    <p className="text-xs text-muted-foreground">Weight: {component.weight}%</p>
                  </div>
                </div>
                {hasData && score != null ? (
                  <div className="space-y-1">
                    <Progress value={score} className="h-2" />
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>0</span>
                      <span>50</span>
                      <span>100</span>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground italic">
                    Not included until the related review step is completed.
                  </p>
                )}
              </div>
            );
          })}
        </CardContent>
      </Card>

      {/* Bias Flags */}
      {calculation.bias_flags && calculation.bias_flags.length > 0 && (
        <Card className="border-amber-200 bg-amber-50">
          <CardHeader>
            <CardTitle className="text-amber-900 flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" />
              Review Quality Flags
            </CardTitle>
            <CardDescription className="text-amber-800">
              Items to consider during calibration
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {calculation.bias_flags.map((flag, index) => (
                <li key={index} className="flex gap-3 text-sm text-amber-900">
                  <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
                  <span>{flag}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Override Info */}
      {calculation.override_applied && (
        <Card className="border-blue-200 bg-blue-50">
          <CardContent className="pt-6">
            <div className="flex gap-3">
              <AlertCircle className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-blue-900">Score Override Applied</p>
                <p className="text-sm text-blue-800 mt-1">{calculation.override_reason}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Calculation Timestamp */}
      {calculation.calculation_timestamp && (
        <div className="text-xs text-muted-foreground text-right">
          <p>
            Calculated on {new Date(calculation.calculation_timestamp).toLocaleDateString()} at{" "}
            {new Date(calculation.calculation_timestamp).toLocaleTimeString()}
          </p>
        </div>
      )}
    </div>
  );
}
