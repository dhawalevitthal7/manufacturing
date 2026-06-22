import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CheckinDetailPanel } from "./checkin-detail-panel";
import { History, Loader2 } from "lucide-react";

interface CheckinEmployeeTimelineProps {
  employeeId: string;
}

export function CheckinEmployeeTimeline({ employeeId }: CheckinEmployeeTimelineProps) {
  const [selectedId, setSelectedId] = useState<string>();

  const { data: timeline, isLoading } = useQuery({
    queryKey: ["employee-checkin-timeline", employeeId],
    queryFn: () => api.getEmployeeCheckinTimeline(employeeId),
    enabled: !!employeeId,
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-8">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const items = timeline || [];

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <History className="h-5 w-5" />
            My check-in timeline
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 max-h-[400px] overflow-y-auto">
          {items.length === 0 ? (
            <p className="text-sm text-muted-foreground">No check-ins yet. Submit your first weekly check-in.</p>
          ) : (
            items.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => setSelectedId(c.id)}
                className={`w-full text-left p-3 rounded-lg border ${
                  selectedId === c.id ? "border-primary" : ""
                }`}
              >
                <div className="flex justify-between">
                  <span className="font-medium">Week {c.checkin_week}</span>
                  <Badge variant="outline">{(c.workflow_status || c.status).replace(/_/g, " ")}</Badge>
                </div>
                <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{c.achievements}</p>
              </button>
            ))
          )}
        </CardContent>
      </Card>
      {selectedId && <CheckinDetailPanel checkinId={selectedId} readOnly />}
    </div>
  );
}
