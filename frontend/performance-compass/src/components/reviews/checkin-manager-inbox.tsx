import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type ContinuousCheckin } from "@/lib/api";
import { useAuthStore } from "@/lib/stores/auth-store";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CheckinDetailPanel } from "./checkin-detail-panel";
import { Inbox, Loader2 } from "lucide-react";

const statusColors: Record<string, string> = {
  SUBMITTED: "bg-blue-100 text-blue-800",
  UNDER_REVIEW: "bg-yellow-100 text-yellow-800",
  ACTION_REQUIRED: "bg-orange-100 text-orange-800",
  ESCALATED: "bg-red-100 text-red-800",
  RESOLVED: "bg-green-100 text-green-800",
  CLOSED: "bg-slate-100 text-slate-800",
};

const LEADERSHIP_ROLES = new Set(["MANAGER", "TEAM_LEAD", "SUPERVISOR", "DEPT_HEAD"]);

export function CheckinManagerInbox() {
  const { user } = useAuthStore();
  const isDeptHead = user?.system_role === "DEPT_HEAD";
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string>();

  const { data: inbox, isLoading } = useQuery({
    queryKey: ["checkin-inbox"],
    queryFn: () => api.getManagerCheckinInbox(),
  });

  const acknowledge = useMutation({
    mutationFn: (id: string) => api.acknowledgeCheckin(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["checkin-inbox"] });
      queryClient.invalidateQueries({ queryKey: ["checkin-detail"] });
    },
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-8">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const items = inbox || [];

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Inbox className="h-5 w-5" />
            {isDeptHead ? "Department check-in queue" : "Team check-in queue"}
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            {isDeptHead
              ? "Review and approve check-ins from managers, team leads, and employees in your department."
              : "Coaching workflow for your direct reports. Acknowledge, comment, and approve when complete."}
          </p>
        </CardHeader>
        <CardContent className="space-y-2 max-h-[480px] overflow-y-auto">
          {items.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">No pending check-ins</p>
          ) : (
            items.map((c: ContinuousCheckin) => (
              <button
                key={c.id}
                type="button"
                onClick={() => setSelectedId(c.id)}
                className={`w-full text-left p-3 rounded-lg border transition-colors ${
                  selectedId === c.id ? "border-primary bg-primary/5" : "hover:bg-muted/50"
                }`}
              >
                <div className="flex justify-between items-start gap-2">
                  <div>
                    <p className="font-medium">{c.employee_name || "Employee"}</p>
                    <p className="text-xs text-muted-foreground">
                      Week {c.checkin_week}
                      {c.employee_role && LEADERSHIP_ROLES.has(c.employee_role)
                        ? ` · ${c.employee_role.replace(/_/g, " ")}`
                        : ""}
                      {c.manager_name && c.manager_id !== user?.id
                        ? ` · Coach: ${c.manager_name}`
                        : ""}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    {c.employee_role && LEADERSHIP_ROLES.has(c.employee_role) && isDeptHead && (
                      <Badge variant="secondary" className="text-xs">
                        Leadership
                      </Badge>
                    )}
                    <Badge className={statusColors[c.workflow_status || c.status] || ""}>
                    {(c.workflow_status || c.status) === "SUBMITTED" ? "Submitted" : (c.workflow_status || c.status).replace(/_/g, " ")}
                    </Badge>
                  </div>
                </div>
                {c.performance_concern_flag && (
                  <Badge variant="destructive" className="mt-2">
                    Concern flagged
                  </Badge>
                )}
                {c.workflow_status === "SUBMITTED" && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="mt-2"
                    onClick={(e) => {
                      e.stopPropagation();
                      acknowledge.mutate(c.id);
                    }}
                  >
                    Acknowledge
                  </Button>
                )}
              </button>
            ))
          )}
        </CardContent>
      </Card>

      {selectedId && (
        <CheckinDetailPanel checkinId={selectedId} onClose={() => setSelectedId(undefined)} />
      )}
    </div>
  );
}
