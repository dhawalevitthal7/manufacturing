import { useState, useEffect } from "react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import {
  CheckCircle2, XCircle, AlertCircle, Clock, ChevronRight,
  TrendingUp, Users, Layers, Activity, Search, Filter,
} from "lucide-react";
import { api } from "@/lib/api";
import { CascadeVisualizer } from "./cascade-visualizer";
import type { ProgressSubmission, ProgressStatus } from "@/lib/api";

const STATUS_CONFIG: Record<ProgressStatus, { color: string; icon: React.ElementType; label: string }> = {
  PENDING: {
    color: "bg-amber-500/10 text-amber-600 border-amber-500/30",
    icon: Clock,
    label: "Awaiting Decision",
  },
  APPROVED: {
    color: "bg-emerald-500/10 text-emerald-600 border-emerald-500/30",
    icon: CheckCircle2,
    label: "Approved",
  },
  REJECTED: {
    color: "bg-rose-500/10 text-rose-600 border-rose-500/30",
    icon: XCircle,
    label: "Rejected",
  },
  REVISION_REQUESTED: {
    color: "bg-blue-500/10 text-blue-600 border-blue-500/30",
    icon: AlertCircle,
    label: "Revision Requested",
  },
};

const LEVEL_ICONS: Record<string, React.ElementType> = {
  ORGANIZATION: Activity,
  PLANT: Layers,
  DEPARTMENT: Users,
  TEAM: Users,
  INDIVIDUAL: TrendingUp,
};

interface SubmissionRow {
  submission: ProgressSubmission;
  objective_level?: string;
  objective_title?: string;
  submitted_by_name?: string;
}

export function ApprovalsPage() {
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedSubmission, setSelectedSubmission] = useState<ProgressSubmission | null>(null);
  const [reviewDialogOpen, setReviewDialogOpen] = useState(false);
  const [reviewAction, setReviewAction] = useState<"approve" | "override" | "reject" | "revision_requested">("approve");
  const [overrideValue, setOverrideValue] = useState("");
  const [reviewNotes, setReviewNotes] = useState("");

  // Fetch pending submissions and dashboard
  const { data: submissions, isLoading: submissionsLoading } = useQuery({
    queryKey: ["pending-submissions"],
    queryFn: () => api.getPendingSubmissions(),
    refetchInterval: 30000,
  });

  const { data: dashboard, isLoading: dashboardLoading } = useQuery({
    queryKey: ["approvals-dashboard"],
    queryFn: () => api.getApprovalsDashboard(),
    refetchInterval: 30000,
  });

  // Fetch cascade chain for selected submission
  const { data: cascadeChain } = useQuery({
    queryKey: ["cascade-chain", selectedSubmission?.id],
    queryFn: () => selectedSubmission?.id ? api.getSubmissionCascadeChain(selectedSubmission.id) : null,
    enabled: !!selectedSubmission?.id && reviewDialogOpen,
  });

  // Review mutation
  const reviewMutation = useMutation({
    mutationFn: async () => {
      if (!selectedSubmission?.id) throw new Error("No submission selected");
      
      const review: any = {
        action: reviewAction,
        manager_note: reviewNotes,
      };

      if (reviewAction === "override" && overrideValue) {
        review.manager_value = parseFloat(overrideValue);
      }

      return api.reviewProgressSubmission(selectedSubmission.id, review);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pending-submissions"] });
      queryClient.invalidateQueries({ queryKey: ["approvals-dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["objectives"] });
      setReviewDialogOpen(false);
      setSelectedSubmission(null);
      setReviewAction("approve");
      setOverrideValue("");
      setReviewNotes("");
    },
  });

  const handleReview = (submission: ProgressSubmission) => {
    setSelectedSubmission(submission);
    setReviewDialogOpen(true);
  };

  const handleSubmitReview = () => {
    reviewMutation.mutate();
  };

  const filteredSubmissions = submissions?.filter((s) => {
    const text = searchTerm.toLowerCase();
    return (
      s.submitted_by?.toLowerCase().includes(text) ||
      s.employee_note?.toLowerCase().includes(text)
    );
  }) || [];

  if (submissionsLoading || dashboardLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4" />
          <p className="text-gray-500">Loading approvals...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Approval Queue</h1>
          <p className="text-gray-400">Review and approve pending OKR progress submissions</p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <Card className="bg-slate-900 border-slate-700">
            <CardContent className="pt-6">
              <div className="text-3xl font-bold text-white mb-2">{dashboard?.user_queue_count || 0}</div>
              <p className="text-gray-400 text-sm">Awaiting Your Decision</p>
            </CardContent>
          </Card>

          <Card className="bg-slate-900 border-slate-700">
            <CardContent className="pt-6">
              <div className="text-3xl font-bold text-amber-400 mb-2">{dashboard?.total_pending || 0}</div>
              <p className="text-gray-400 text-sm">Total Pending Approvals</p>
            </CardContent>
          </Card>

          <Card className="bg-slate-900 border-slate-700">
            <CardContent className="pt-6">
              <div className="text-3xl font-bold text-blue-400 mb-2">
                {dashboard?.by_level?.MANAGER?.count || 0}
              </div>
              <p className="text-gray-400 text-sm">Manager Level</p>
            </CardContent>
          </Card>

          <Card className="bg-slate-900 border-slate-700">
            <CardContent className="pt-6">
              <div className="text-3xl font-bold text-emerald-400 mb-2">
                {dashboard?.by_level?.DEPT_HEAD?.count || 0}
              </div>
              <p className="text-gray-400 text-sm">Department Level</p>
            </CardContent>
          </Card>
        </div>

        {/* Submissions Table */}
        <Card className="bg-slate-900 border-slate-700">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-white">Pending Submissions</CardTitle>
              <div className="flex items-center gap-2 w-64">
                <Search className="w-4 h-4 text-gray-500" />
                <Input
                  placeholder="Search by employee or notes..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="bg-slate-800 border-slate-700 text-white placeholder:text-gray-500"
                />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {filteredSubmissions.length === 0 ? (
              <div className="text-center py-12">
                <CheckCircle2 className="w-12 h-12 text-emerald-500 mx-auto mb-4 opacity-50" />
                <p className="text-gray-400">No pending submissions</p>
              </div>
            ) : (
              <div className="space-y-3">
                {filteredSubmissions.map((submission) => {
                  const statusConfig = STATUS_CONFIG[submission.status as ProgressStatus];
                  const LevelIcon = LEVEL_ICONS[submission.objective_level || "TEAM"] || Users;

                  return (
                    <div
                      key={submission.id}
                      className="flex items-center justify-between p-4 bg-slate-800 rounded-lg border border-slate-700 hover:border-slate-600 transition-all"
                    >
                      <div className="flex items-center gap-4 flex-1">
                        <LevelIcon className="w-5 h-5 text-gray-400" />
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <h3 className="font-semibold text-white">
                              {submission.submitted_by || "Unknown"}
                            </h3>
                            <Badge variant="outline" className="text-xs">
                              {submission.objective_level || "TEAM"}
                            </Badge>
                          </div>
                          <p className="text-sm text-gray-400">
                            {submission.employee_note || "No notes"}
                          </p>
                          <div className="flex items-center gap-2 mt-2">
                            <span className="text-xs text-gray-500">
                              Value: {submission.employee_value}
                            </span>
                            {submission.manager_value !== undefined && (
                              <span className="text-xs text-gray-500">
                                → {submission.manager_value}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-4">
                        <div className={`px-3 py-1 rounded-full text-xs font-medium border ${statusConfig.color}`}>
                          <statusConfig.icon className="w-3 h-3 inline mr-1" />
                          {statusConfig.label}
                        </div>

                        <Button
                          onClick={() => handleReview(submission)}
                          size="sm"
                          className="bg-blue-600 hover:bg-blue-700 text-white"
                        >
                          <ChevronRight className="w-4 h-4 mr-1" />
                          Review
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Review Dialog */}
      <Dialog open={reviewDialogOpen} onOpenChange={setReviewDialogOpen}>
        <DialogContent className="bg-slate-900 border-slate-700 max-w-2xl">
          <DialogHeader>
            <DialogTitle className="text-white">Review Progress Submission</DialogTitle>
          </DialogHeader>

          {selectedSubmission && (
            <div className="space-y-6">
              {/* Cascade Visualizer */}
              <CascadeVisualizer submissionId={selectedSubmission.id} />

              {/* Submission Details */}
              <div className="space-y-4">
                <div>
                  <label className="text-sm text-gray-400">Submitted By</label>
                  <p className="text-white font-medium">{selectedSubmission.submitted_by}</p>
                </div>

                <div>
                  <label className="text-sm text-gray-400">Submitted Value</label>
                  <p className="text-white font-medium">{selectedSubmission.employee_value}</p>
                </div>

                <div>
                  <label className="text-sm text-gray-400">Employee Notes</label>
                  <p className="text-gray-300 text-sm">
                    {selectedSubmission.employee_note || "No notes provided"}
                  </p>
                </div>
              </div>

              {/* Action Selection */}
              <div className="space-y-3 border-t border-slate-700 pt-4">
                <label className="text-sm font-semibold text-white">Your Decision</label>

                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => setReviewAction("approve")}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                      reviewAction === "approve"
                        ? "bg-emerald-600 text-white"
                        : "bg-slate-800 text-gray-300 hover:bg-slate-700"
                    }`}
                  >
                    <CheckCircle2 className="w-4 h-4 inline mr-2" />
                    Approve
                  </button>

                  <button
                    onClick={() => setReviewAction("override")}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                      reviewAction === "override"
                        ? "bg-blue-600 text-white"
                        : "bg-slate-800 text-gray-300 hover:bg-slate-700"
                    }`}
                  >
                    <TrendingUp className="w-4 h-4 inline mr-2" />
                    Override
                  </button>

                  <button
                    onClick={() => setReviewAction("revision_requested")}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                      reviewAction === "revision_requested"
                        ? "bg-amber-600 text-white"
                        : "bg-slate-800 text-gray-300 hover:bg-slate-700"
                    }`}
                  >
                    <AlertCircle className="w-4 h-4 inline mr-2" />
                    Request Revision
                  </button>

                  <button
                    onClick={() => setReviewAction("reject")}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                      reviewAction === "reject"
                        ? "bg-rose-600 text-white"
                        : "bg-slate-800 text-gray-300 hover:bg-slate-700"
                    }`}
                  >
                    <XCircle className="w-4 h-4 inline mr-2" />
                    Reject
                  </button>
                </div>

                {reviewAction === "override" && (
                  <Input
                    placeholder="Enter override value"
                    type="number"
                    value={overrideValue}
                    onChange={(e) => setOverrideValue(e.target.value)}
                    className="bg-slate-800 border-slate-700 text-white placeholder:text-gray-500"
                  />
                )}
              </div>

              {/* Notes */}
              <div>
                <label className="text-sm font-semibold text-white">Your Notes</label>
                <Textarea
                  placeholder="Add any feedback or notes for the employee..."
                  value={reviewNotes}
                  onChange={(e) => setReviewNotes(e.target.value)}
                  className="bg-slate-800 border-slate-700 text-white placeholder:text-gray-500 mt-2"
                  rows={4}
                />
              </div>
            </div>
          )}

          <DialogFooter className="border-t border-slate-700 pt-4">
            <Button
              variant="outline"
              onClick={() => setReviewDialogOpen(false)}
              className="border-slate-700"
            >
              Cancel
            </Button>
            <Button
              onClick={handleSubmitReview}
              disabled={reviewMutation.isPending}
              className="bg-blue-600 hover:bg-blue-700"
            >
              {reviewMutation.isPending ? "Submitting..." : "Submit Review"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
