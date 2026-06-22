import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { FileText, TrendingUp } from "lucide-react";

interface EmployeePerformanceNarrativeProps {
  narrative?: string;
  promotionRecommendation?: string;
  promotionRationale?: string;
  cycleName?: string;
  sharedAt?: string;
}

export function EmployeePerformanceNarrative({
  narrative,
  promotionRecommendation,
  promotionRationale,
  cycleName,
  sharedAt,
}: EmployeePerformanceNarrativeProps) {
  if (!narrative) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-sm text-muted-foreground">
            Your manager has not shared the performance narrative yet. You will see it here after
            they complete the AI-assisted review.
          </p>
        </CardContent>
      </Card>
    );
  }

  const promoLabel = promotionRecommendation?.replace(/_/g, " ");

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileText className="h-5 w-5" />
          Your Performance Review
        </CardTitle>
        <CardDescription>
          {cycleName ? `${cycleName} · ` : ""}
          {sharedAt ? `Shared ${new Date(sharedAt).toLocaleDateString()}` : "Shared by your manager"}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {promotionRecommendation && (
          <div className="flex items-start gap-3 rounded-lg border bg-slate-50 p-4">
            <TrendingUp className="h-5 w-5 text-primary mt-0.5" />
            <div>
              <p className="text-sm font-medium">Promotion consideration</p>
              <Badge variant="secondary" className="mt-1">
                {promoLabel}
              </Badge>
              {promotionRationale && (
                <p className="text-sm text-muted-foreground mt-2">{promotionRationale}</p>
              )}
            </div>
          </div>
        )}
        <div className="prose prose-sm max-w-none dark:prose-invert whitespace-pre-wrap">
          {narrative.split("\n").map((line, i) => {
            if (line.startsWith("## ")) {
              return (
                <h3 key={i} className="text-base font-semibold mt-4 mb-2">
                  {line.replace("## ", "")}
                </h3>
              );
            }
            if (line.startsWith("• ")) {
              return (
                <p key={i} className="ml-4 text-sm">
                  {line}
                </p>
              );
            }
            return line ? (
              <p key={i} className="text-sm text-muted-foreground">
                {line}
              </p>
            ) : (
              <br key={i} />
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
