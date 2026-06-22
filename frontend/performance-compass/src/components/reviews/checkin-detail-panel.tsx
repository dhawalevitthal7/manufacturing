import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Loader2, X, CheckCircle2 } from "lucide-react";
import { useAuthStore } from "@/lib/stores/auth-store";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface CheckinDetailPanelProps {
  checkinId: string;
  onClose?: () => void;
  readOnly?: boolean;
}

export function CheckinDetailPanel({ checkinId, onClose, readOnly }: CheckinDetailPanelProps) {
  const { user } = useAuthStore();
  const queryClient = useQueryClient();
  const [comment, setComment] = useState("");
  const [actionText, setActionText] = useState("");
  const [escalationReason, setEscalationReason] = useState("SEVERE_BLOCKER");

  const { data: checkin, isLoading } = useQuery({
    queryKey: ["checkin-detail", checkinId],
    queryFn: () => api.getCheckinDetail(checkinId),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["checkin-detail", checkinId] });
    queryClient.invalidateQueries({ queryKey: ["checkin-inbox"] });
    queryClient.invalidateQueries({ queryKey: ["employee-checkin-timeline"] });
  };

  const commentMutation = useMutation({
    mutationFn: () => api.addCheckinComment(checkinId, comment),
    onSuccess: () => {
      setComment("");
      invalidate();
    },
  });

  const actionMutation = useMutation({
    mutationFn: () =>
      api.assignCheckinActionItems(checkinId, [
        { action: actionText, owner: "employee", due_date: new Date().toISOString().slice(0, 10), status: "OPEN" },
      ]),
    onSuccess: () => {
      setActionText("");
      invalidate();
    },
  });

  const escalateMutation = useMutation({
    mutationFn: () => api.escalateCheckin(checkinId, escalationReason),
    onSuccess: invalidate,
  });

  const resolveMutation = useMutation({
    mutationFn: () => api.resolveCheckin(checkinId, "Resolved by manager"),
    onSuccess: invalidate,
  });

  const approveMutation = useMutation({
    mutationFn: () => api.approveCheckin(checkinId, comment || "Approved"),
    onSuccess: () => {
      setComment("");
      invalidate();
    },
  });

  if (isLoading || !checkin) {
    return (
      <Card>
        <CardContent className="py-12 flex justify-center">
          <Loader2 className="h-6 w-6 animate-spin" />
        </CardContent>
      </Card>
    );
  }

  const ws = checkin.workflow_status || checkin.status;
  const isLeadershipCheckin =
    !!checkin.employee_role &&
    ["MANAGER", "TEAM_LEAD", "SUPERVISOR", "DEPT_HEAD"].includes(checkin.employee_role);
  const canApprove =
    !readOnly &&
    user?.system_role === "DEPT_HEAD" &&
    ["SUBMITTED", "UNDER_REVIEW", "ACTION_REQUIRED"].includes(ws);

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between">
        <div>
          <CardTitle>{checkin.employee_name}</CardTitle>
          <p className="text-sm text-muted-foreground">
            Week {checkin.checkin_week} · {ws.replace(/_/g, " ")}
          </p>
        </div>
        {onClose && (
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="text-sm space-y-2 p-3 bg-muted/30 rounded-lg">
          <p><strong>Achievements:</strong> {checkin.achievements}</p>
          <p><strong>Blockers:</strong> {checkin.blockers}</p>
          {checkin.support_needed && <p><strong>Support:</strong> {checkin.support_needed}</p>}
          <p>
            <strong>Confidence:</strong> {checkin.confidence_score}% · Mood: {checkin.employee_mood}
          </p>
        </div>

        <div className="space-y-2">
          <p className="text-sm font-semibold">Conversation</p>
          {(checkin.comments || []).map((c) => (
            <div key={c.id} className="text-sm p-2 border rounded bg-background">
              <span className="font-medium">{c.commented_by_name || "User"}</span>
              <span className="text-muted-foreground text-xs ml-2">{c.comment_type}</span>
              <p className="mt-1">{c.comment}</p>
            </div>
          ))}
        </div>

        {!readOnly && (
          <>
            <Textarea
              placeholder="Coaching comment..."
              value={comment}
              onChange={(e) => setComment(e.target.value)}
            />
            <Button
              size="sm"
              disabled={!comment.trim() || commentMutation.isPending}
              onClick={() => commentMutation.mutate()}
            >
              Add comment
            </Button>

            {canApprove && (
              <Button
                size="sm"
                className="gap-2"
                disabled={approveMutation.isPending}
                onClick={() => approveMutation.mutate()}
              >
                <CheckCircle2 className="h-4 w-4" />
                {isLeadershipCheckin ? "Approve leadership check-in" : "Approve check-in"}
              </Button>
            )}

            <div className="flex gap-2 flex-wrap pt-2 border-t">
              <Input
                placeholder="Action item for employee"
                value={actionText}
                onChange={(e) => setActionText(e.target.value)}
                className="flex-1 min-w-[200px]"
              />
              <Button size="sm" variant="secondary" disabled={!actionText} onClick={() => actionMutation.mutate()}>
                Assign action
              </Button>
            </div>

            <div className="flex gap-2 items-center flex-wrap pt-2 border-t">
              <Select value={escalationReason} onValueChange={setEscalationReason}>
                <SelectTrigger className="w-[220px]">
                  <SelectValue placeholder="Escalation reason" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="SEVERE_BLOCKER">Severe blocker</SelectItem>
                  <SelectItem value="REPEATED_LOW_PERFORMANCE">Repeated low performance</SelectItem>
                  <SelectItem value="CROSS_FUNCTIONAL">Cross-functional</SelectItem>
                  <SelectItem value="SAFETY_COMPLIANCE">Safety / compliance</SelectItem>
                </SelectContent>
              </Select>
              <Button size="sm" variant="destructive" onClick={() => escalateMutation.mutate()}>
                Escalate to dept head
              </Button>
              <Button size="sm" variant="outline" onClick={() => resolveMutation.mutate()}>
                Mark resolved
              </Button>
            </div>
          </>
        )}

        {checkin.escalation_target_name && (
          <Badge variant="outline">Escalated to {checkin.escalation_target_name}</Badge>
        )}
      </CardContent>
    </Card>
  );
}
