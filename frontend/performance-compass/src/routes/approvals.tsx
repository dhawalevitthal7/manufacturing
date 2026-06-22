import { createFileRoute } from "@tanstack/react-router";
import { ApprovalsPage } from "@/components/approvals/approvals-page";

type ApprovalsSearch = {
  type?: "okr_creation" | "progress";
  stage?: "line" | "functional";
};

export const Route = createFileRoute("/approvals")({
  validateSearch: (search: Record<string, unknown>): ApprovalsSearch => ({
    type:
      search.type === "okr_creation" || search.type === "progress"
        ? search.type
        : undefined,
    stage:
      search.stage === "line" || search.stage === "functional"
        ? search.stage
        : undefined,
  }),
  head: () => ({
    meta: [
      { title: "Approval Queue — Axis Operate" },
      { name: "description", content: "OKR creation approvals and progress validation queues." },
    ],
  }),
  component: ApprovalsPage,
});
