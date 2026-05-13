import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2, ChevronDown, CheckCircle2, Clock, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";
import type { ObjectiveLevel, ProgressStatus } from "@/lib/api";

interface CascadeVisualizerProps {
  submissionId?: string;
  objectiveId?: string;
}

const LEVEL_ORDER: ObjectiveLevel[] = ["ORGANIZATION", "PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"];

const STATUS_ICONS: Record<ProgressStatus, React.ElementType> = {
  PENDING: Clock,
  APPROVED: CheckCircle2,
  REJECTED: AlertCircle,
  REVISION_REQUESTED: AlertCircle,
};

const STATUS_COLORS: Record<ProgressStatus, string> = {
  PENDING: "text-amber-400 bg-amber-500/10 border-amber-500/30",
  APPROVED: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
  REJECTED: "text-rose-400 bg-rose-500/10 border-rose-500/30",
  REVISION_REQUESTED: "text-blue-400 bg-blue-500/10 border-blue-500/30",
};

export function CascadeVisualizer({ submissionId, objectiveId }: CascadeVisualizerProps) {
  const { data: cascadeChain, isLoading } = useQuery({
    queryKey: ["cascade-chain", submissionId],
    queryFn: () => (submissionId ? api.getSubmissionCascadeChain(submissionId) : null),
    enabled: !!submissionId,
  });

  if (!submissionId) return null;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-gray-500" />
      </div>
    );
  }

  if (!cascadeChain || cascadeChain.chain.length === 0) {
    return null;
  }

  // Reverse to show bottom-up: INDIVIDUAL → ORG
  const chain = cascadeChain.chain.reverse();

  return (
    <Card className="bg-slate-900 border-slate-700">
      <CardHeader>
        <CardTitle className="text-white">Approval Cascade Path</CardTitle>
        <p className="text-sm text-gray-400 mt-1">
          This submission will cascade through the following approval levels
        </p>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {chain.map((item, idx) => {
            const StatusIcon = STATUS_ICONS[item.status as ProgressStatus] || Clock;
            const statusColor = STATUS_COLORS[item.status as ProgressStatus] || STATUS_COLORS.PENDING;
            const isCurrentLevel = idx === chain.length - 1;

            return (
              <div key={item.objective_id}>
                {/* Chain item */}
                <div className="flex items-start gap-4">
                  {/* Level indicator */}
                  <div className="flex flex-col items-center">
                    <div
                      className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
                        isCurrentLevel
                          ? "bg-blue-600 text-white ring-2 ring-blue-400"
                          : item.status === "APPROVED"
                          ? "bg-emerald-600 text-white"
                          : "bg-slate-800 text-gray-400 border border-slate-700"
                      }`}
                    >
                      {idx + 1}
                    </div>
                    {idx < chain.length - 1 && (
                      <ChevronDown className="h-4 w-4 text-slate-700 mt-1" />
                    )}
                  </div>

                  {/* Details */}
                  <div className="flex-1 mt-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-semibold text-white">{item.level}</span>
                      <Badge variant="outline" className={`text-xs ${statusColor}`}>
                        <StatusIcon className="h-3 w-3 mr-1 inline" />
                        {item.status}
                      </Badge>
                      {isCurrentLevel && (
                        <Badge className="bg-blue-600 text-white text-xs">Current</Badge>
                      )}
                    </div>
                    <p className="text-sm text-gray-400">{item.title}</p>
                    <div className="mt-2 flex items-center gap-3 text-xs">
                      <span className="text-gray-500">
                        Progress: <span className="text-gray-300 font-medium">{item.progress.toFixed(1)}%</span>
                      </span>
                      {item.submission_id && (
                        <span className="text-gray-500 font-mono text-[10px] truncate">
                          {item.submission_id.substring(0, 8)}...
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Info box */}
        <div className="mt-6 p-3 rounded-lg bg-slate-800 border border-slate-700">
          <p className="text-xs text-gray-400">
            <span className="font-semibold text-gray-300">How it works:</span> Once approved at this level,
            the submission will automatically cascade to the next level up the hierarchy for the next approver's
            review.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
