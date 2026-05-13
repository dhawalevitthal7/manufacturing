import { createFileRoute } from "@tanstack/react-router";
import { useReviews, useReviewCycles } from "@/lib/hooks";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AlertCircle, Loader2, Clock, CheckCircle2 } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";

export const Route = createFileRoute("/reviews")({
  head: () => ({
    meta: [
      { title: "Performance Reviews — Axis Operate" },
      { name: "description", content: "Self, manager, skip-level and AI-assisted reviews." },
    ],
  }),
  component: ReviewsPage,
});

function ReviewsPage() {
  const { data: cycles, isLoading: cyclesLoading } = useReviewCycles();
  const { data: reviews, isLoading: reviewsLoading, error } = useReviews();

  const isLoading = cyclesLoading || reviewsLoading;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-muted-foreground" />
          <p className="mt-2 text-sm text-muted-foreground">Loading reviews...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <div>
          <h2 className="text-2xl font-semibold">Performance Reviews</h2>
          <p className="text-sm text-muted-foreground">Self, manager, skip-level and AI-assisted reviews.</p>
        </div>
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {error instanceof Error ? error.message : "Failed to load reviews"}
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const statusGroups = {
    SELF_REVIEW_PENDING: reviews?.filter((r) => r.status === "SELF_REVIEW_PENDING") || [],
    MANAGER_REVIEW_PENDING: reviews?.filter((r) => r.status === "MANAGER_REVIEW_PENDING") || [],
    SKIP_LEVEL_PENDING: reviews?.filter((r) => r.status === "SKIP_LEVEL_PENDING") || [],
    CALIBRATION_PENDING: reviews?.filter((r) => r.status === "CALIBRATION_PENDING") || [],
    COMPLETED: reviews?.filter((r) => r.status === "COMPLETED") || [],
  };

  const getStatusIcon = (status: string) => {
    if (status === "COMPLETED") return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    return <Clock className="h-4 w-4 text-yellow-500" />;
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "SELF_REVIEW_PENDING":
        return "bg-blue-50 border-blue-200";
      case "MANAGER_REVIEW_PENDING":
        return "bg-yellow-50 border-yellow-200";
      case "SKIP_LEVEL_PENDING":
        return "bg-purple-50 border-purple-200";
      case "CALIBRATION_PENDING":
        return "bg-orange-50 border-orange-200";
      case "COMPLETED":
        return "bg-green-50 border-green-200";
      default:
        return "";
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold">Performance Reviews</h2>
        <p className="text-sm text-muted-foreground">
          {reviews?.length || 0} review{(reviews?.length || 0) !== 1 ? "s" : ""} across all cycles
        </p>
      </div>

      {cycles && cycles.length > 0 && (
        <div className="grid gap-2 md:grid-cols-4">
          {cycles.map((cycle) => (
            <Card key={cycle.id} className="p-3">
              <p className="text-sm font-medium">{cycle.name}</p>
              <p className="text-xs text-muted-foreground">
                {new Date(cycle.start_date).toLocaleDateString()} - {new Date(cycle.end_date).toLocaleDateString()}
              </p>
              <Badge className="mt-2" variant={cycle.status === "ACTIVE" ? "default" : "outline"}>
                {cycle.status}
              </Badge>
            </Card>
          ))}
        </div>
      )}

      <Tabs defaultValue="SELF_REVIEW_PENDING" className="space-y-4">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="SELF_REVIEW_PENDING">Self ({statusGroups.SELF_REVIEW_PENDING.length})</TabsTrigger>
          <TabsTrigger value="MANAGER_REVIEW_PENDING">Manager ({statusGroups.MANAGER_REVIEW_PENDING.length})</TabsTrigger>
          <TabsTrigger value="SKIP_LEVEL_PENDING">Skip-Level ({statusGroups.SKIP_LEVEL_PENDING.length})</TabsTrigger>
          <TabsTrigger value="CALIBRATION_PENDING">Calib ({statusGroups.CALIBRATION_PENDING.length})</TabsTrigger>
          <TabsTrigger value="COMPLETED">Done ({statusGroups.COMPLETED.length})</TabsTrigger>
        </TabsList>

        {Object.entries(statusGroups).map(([status, items]) => (
          <TabsContent key={status} value={status} className="space-y-4">
            {items.length > 0 ? (
              items.map((review) => (
                <Card key={review.id} className={`border ${getStatusColor(status)}`}>
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <CardTitle className="text-base">{review.reviewee_name || "Unknown"}</CardTitle>
                        <p className="text-xs text-muted-foreground mt-1">
                          Cycle: {review.cycle_name || "Unknown"}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        {getStatusIcon(status)}
                        <Badge variant="outline" className="whitespace-nowrap">
                          {status.replace(/_/g, " ")}
                        </Badge>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {review.self_summary && (
                      <div>
                        <p className="text-xs font-semibold text-muted-foreground">Self Summary</p>
                        <p className="text-sm mt-1 line-clamp-2">{review.self_summary}</p>
                      </div>
                    )}
                    {review.manager_summary && (
                      <div>
                        <p className="text-xs font-semibold text-muted-foreground">Manager Summary</p>
                        <p className="text-sm mt-1 line-clamp-2">{review.manager_summary}</p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))
            ) : (
              <Card>
                <CardContent className="pt-6">
                  <p className="text-center text-muted-foreground">No reviews in this stage</p>
                </CardContent>
              </Card>
            )}
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
