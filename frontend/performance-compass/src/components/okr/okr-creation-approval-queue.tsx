import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, Target, CheckCircle2, Clock, XCircle } from "lucide-react";
import { api } from "@/lib/api";
import { OkrApprovalReviewCard } from "./okr-approval-review-card";

type QueueTab = "pending" | "approved" | "rejected";

const TAB_CONFIG: { id: QueueTab; label: string; icon: React.ElementType; empty: string }[] = [
  { id: "pending", label: "Pending", icon: Clock, empty: "No OKRs awaiting your creation approval." },
  { id: "approved", label: "Approved", icon: CheckCircle2, empty: "No OKRs you have approved yet." },
  { id: "rejected", label: "Rejected", icon: XCircle, empty: "No rejected OKRs in your scope." },
];

export function OkrCreationApprovalQueue() {
  const [tab, setTab] = useState<QueueTab>("pending");

  const { data: okrs = [], isLoading, refetch } = useQuery({
    queryKey: ["okr-creation-queue", tab],
    queryFn: () => api.getLifecycleApprovalQueue(tab),
    refetchInterval: 30000,
  });

  const pendingQuery = useQuery({
    queryKey: ["okr-creation-queue", "pending"],
    queryFn: () => api.getLifecycleApprovalQueue("pending"),
    refetchInterval: 30000,
  });

  const tabMeta = TAB_CONFIG.find((t) => t.id === tab)!;

  return (
    <Card className="border-primary/30 bg-slate-900/50 border-slate-700">
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2 text-white">
          <Target className="h-4 w-4 text-primary" />
          OKR Creation Approvals
        </CardTitle>
        <div className="flex gap-1 mt-3">
          {TAB_CONFIG.map(({ id, label, icon: Icon }) => {
            const count = id === "pending" ? (pendingQuery.data?.length ?? 0) : undefined;
            return (
              <button
                key={id}
                type="button"
                onClick={() => setTab(id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                  tab === id
                    ? "bg-primary text-primary-foreground"
                    : "bg-slate-800 text-gray-400 hover:bg-slate-700 hover:text-gray-200"
                }`}
              >
                <Icon className="h-3 w-3" />
                {label}
                {count != null && count > 0 && (
                  <span className="ml-1 rounded-full bg-amber-500/20 text-amber-400 px-1.5 py-0 text-[10px]">
                    {count}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="py-12 flex justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : okrs.length === 0 ? (
          <p className="text-sm text-muted-foreground py-6 text-center">{tabMeta.empty}</p>
        ) : (
          <div className="space-y-3">
            {okrs.map((okr) => (
              <OkrApprovalReviewCard
                key={okr.id}
                okr={okr}
                queueStatus={tab}
                onApproved={() => {
                  refetch();
                  pendingQuery.refetch();
                  if (tab === "pending") setTab("approved");
                }}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/** @deprecated Use OkrCreationApprovalQueue */
export function OkrPendingApprovals({ alwaysShow = false }: { alwaysShow?: boolean }) {
  return <OkrCreationApprovalQueue />;
}
