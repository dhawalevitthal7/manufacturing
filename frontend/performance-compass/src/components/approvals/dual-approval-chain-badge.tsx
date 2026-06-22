import { Badge } from "@/components/ui/badge";
import type { ApprovalChainStatus, ApprovalStepStatus } from "@/lib/api";

const STEP_LABEL: Record<string, string> = {
  LINE: "Plant Head",
  FUNCTIONAL: "Functional head",
};

function iconFor(status?: ApprovalStepStatus | null) {
  if (status === "APPROVED") return "✓";
  if (status === "REJECTED") return "✗";
  if (status === "SKIPPED") return "—";
  return "⏳";
}

interface Props {
  chain?: ApprovalChainStatus | null;
  compact?: boolean;
}

export function DualApprovalChainBadge({ chain, compact = false }: Props) {
  if (!chain?.steps?.length) return null;

  if (compact) {
    const line = chain.line ?? "PENDING";
    const functional = chain.functional;
    if (functional === "SKIPPED" || functional == null) {
      return (
        <Badge variant="outline" className="text-[10px] font-normal">
          Line {iconFor(line)}
        </Badge>
      );
    }
    return (
      <Badge variant="outline" className="text-[10px] font-normal gap-1">
        {STEP_LABEL.LINE} {iconFor(line)} · {STEP_LABEL.FUNCTIONAL} {iconFor(functional)}
      </Badge>
    );
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {chain.steps
        .filter((s) => s.status !== "SKIPPED")
        .map((step) => (
          <Badge
            key={step.id}
            variant="outline"
            className={`text-[10px] font-normal ${
              step.status === "APPROVED"
                ? "border-emerald-500/40 text-emerald-600"
                : step.status === "REJECTED"
                  ? "border-rose-500/40 text-rose-600"
                  : "border-amber-500/40 text-amber-600"
            }`}
          >
            {STEP_LABEL[step.approval_type] ?? step.approval_type} {iconFor(step.status)}
            {step.approver_name ? ` · ${step.approver_name}` : ""}
          </Badge>
        ))}
    </div>
  );
}
