import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  AlertCircle, CheckCircle2, XCircle, MessageSquare, Loader2,
  Clock, User, Calendar, FileText, Flag, Target
} from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/use-toast";

interface PendingSubmission {
  id: string;
  objective: string;
  level_type: string;
  progress: number;
  owner?: {
    id: string;
    name: string;
    email: string;
  };
  submitted_at?: string;
  submitted_by?: {
    id: string;
    name: string;
  };
}

export function OKRApprovalDashboard() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [selectedSubmission, setSelectedSubmission] = useState<string | null>(null);
  const [approvalComments, setApprovalComments] = useState("");
  const [approvalAction, setApprovalAction] = useState<"approve" | "reject" | "request_revision">("approve");
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  // Fetch pending submissions
  const { data: pendingSubmissions = [], isLoading, refetch } = useQuery({
    queryKey: ["okr-pending-submissions"],
    queryFn: () => api.getPendingOKRSubmissions(),
    refetchInterval: 30000, // Refetch every 30 seconds
  });

  // Approve/Reject mutation
  const approveMutation = useMutation({
    mutationFn: (okrId: string) =>
      api.approveOKRSubmission(okrId, {
        action: approvalAction,
        comments: approvalComments,
      }),
    onSuccess: () => {
      toast({
        title: "Success",
        description: `OKR submission ${approvalAction}d successfully`,
      });
      queryClient.invalidateQueries({ queryKey: ["okr-pending-submissions"] });
      queryClient.invalidateQueries({ queryKey: ["accessible-okrs"] });
      setIsDialogOpen(false);
      setApprovalComments("");
      setSelectedSubmission(null);
    },
    onError: (error: any) => {
      toast({
        title: "Error",
        description: error.message || "Failed to process submission",
        variant: "destructive",
      });
    },
  });

  const handleApprove = (submissionId: string) => {
    setSelectedSubmission(submissionId);
    setApprovalAction("approve");
    setIsDialogOpen(true);
  };

  const handleReject = (submissionId: string) => {
    setSelectedSubmission(submissionId);
    setApprovalAction("reject");
    setIsDialogOpen(true);
  };

  const handleRequestRevision = (submissionId: string) => {
    setSelectedSubmission(submissionId);
    setApprovalAction("request_revision");
    setIsDialogOpen(true);
  };

  const handleSubmitDecision = async () => {
    if (!selectedSubmission) return;
    
    if (approvalAction === "reject" || approvalAction === "request_revision") {
      if (!approvalComments.trim()) {
        toast({
          title: "Comments Required",
          description: `Please provide comments when ${approvalAction === "reject" ? "rejecting" : "requesting revision for"} an OKR`,
          variant: "destructive",
        });
        return;
      }
    }

    approveMutation.mutate(selectedSubmission);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold">OKR Approval Dashboard</h2>
        <p className="text-muted-foreground">
          Review and approve OKR progress submissions
        </p>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Pending Approvals
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold text-amber-600">{pendingSubmissions.length}</span>
              <Clock className="h-5 w-5 text-amber-600" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Average Progress
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold">
                {pendingSubmissions.length > 0
                  ? Math.round(
                      pendingSubmissions.reduce((sum, s) => sum + (s.progress || 0), 0) /
                        pendingSubmissions.length
                    )
                  : 0}
                %
              </span>
              <Target className="h-5 w-5 text-blue-600" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Time to Approve
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold text-green-600">
                {pendingSubmissions.length > 0 ? "≤ 24h" : "—"}
              </span>
              <FileText className="h-5 w-5 text-green-600" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Submissions List */}
      {pendingSubmissions.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <CheckCircle2 className="h-12 w-12 mx-auto mb-4 text-green-600 opacity-50" />
            <p className="text-lg font-semibold text-muted-foreground">
              All caught up!
            </p>
            <p className="text-sm text-muted-foreground">
              No OKR submissions pending your approval
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {pendingSubmissions.map((submission) => (
            <Card key={submission.id} className="hover:shadow-md transition-shadow">
              <CardContent className="pt-6">
                <div className="space-y-4">
                  {/* Main Info */}
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <h3 className="font-semibold text-lg">{submission.objective}</h3>
                      <div className="mt-2 flex flex-wrap gap-2 items-center">
                        <Badge variant="outline">{submission.level_type}</Badge>
                        {submission.owner && (
                          <div className="flex items-center gap-1 text-sm text-muted-foreground">
                            <User className="h-3 w-3" />
                            {submission.owner.name}
                          </div>
                        )}
                        {submission.submitted_at && (
                          <div className="flex items-center gap-1 text-sm text-muted-foreground">
                            <Calendar className="h-3 w-3" />
                            {new Date(submission.submitted_at).toLocaleDateString()}
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-3xl font-bold text-blue-600">{submission.progress}%</div>
                      <Badge variant="secondary" className="mt-2">
                        <Clock className="h-3 w-3 mr-1" />
                        Pending
                      </Badge>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="flex gap-2 justify-end pt-2 border-t">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleRequestRevision(submission.id)}
                      disabled={approveMutation.isPending}
                    >
                      <MessageSquare className="h-4 w-4 mr-1" />
                      Request Revision
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleReject(submission.id)}
                      disabled={approveMutation.isPending}
                      className="text-red-600 border-red-200 hover:bg-red-50"
                    >
                      <XCircle className="h-4 w-4 mr-1" />
                      Reject
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => handleApprove(submission.id)}
                      disabled={approveMutation.isPending}
                      className="bg-green-600 hover:bg-green-700"
                    >
                      <CheckCircle2 className="h-4 w-4 mr-1" />
                      Approve
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Approval Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>
              {approvalAction === "approve"
                ? "Approve OKR Submission"
                : approvalAction === "reject"
                ? "Reject OKR Submission"
                : "Request Revision"}
            </DialogTitle>
            <DialogDescription>
              {approvalAction === "approve"
                ? "Confirm approval of this OKR progress submission"
                : approvalAction === "reject"
                ? "Provide feedback on why this submission is being rejected"
                : "Request changes before approval"}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {(approvalAction === "reject" || approvalAction === "request_revision") && (
              <Alert className={
                approvalAction === "reject" 
                  ? "border-red-200 bg-red-50" 
                  : "border-amber-200 bg-amber-50"
              }>
                <AlertCircle className={
                  approvalAction === "reject"
                    ? "h-4 w-4 text-red-600"
                    : "h-4 w-4 text-amber-600"
                } />
                <AlertDescription className={
                  approvalAction === "reject"
                    ? "text-red-700"
                    : "text-amber-700"
                }>
                  Comments are required when {approvalAction === "reject" ? "rejecting" : "requesting revision for"} a submission.
                </AlertDescription>
              </Alert>
            )}

            <div className="space-y-2">
              <label className="text-sm font-medium">
                {approvalAction === "approve"
                  ? "Optional Comments"
                  : "Comments"}
              </label>
              <Textarea
                placeholder={
                  approvalAction === "approve"
                    ? "Add any comments about your approval..."
                    : approvalAction === "reject"
                    ? "Explain why this submission is being rejected..."
                    : "Specify what changes are needed..."
                }
                value={approvalComments}
                onChange={(e) => setApprovalComments(e.target.value)}
                rows={4}
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setIsDialogOpen(false);
                setApprovalComments("");
              }}
              disabled={approveMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSubmitDecision}
              disabled={approveMutation.isPending}
              className={
                approvalAction === "approve"
                  ? "bg-green-600 hover:bg-green-700"
                  : "bg-red-600 hover:bg-red-700"
              }
            >
              {approveMutation.isPending && (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              )}
              {approvalAction === "approve"
                ? "Approve"
                : approvalAction === "reject"
                ? "Reject"
                : "Request Revision"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
