import { createFileRoute } from "@tanstack/react-router";
import { ApprovalsPage } from "@/components/approvals/approvals-page";

export const Route = createFileRoute("/approvals")({
  head: () => ({
    meta: [
      { title: "Approval Queue — Axis Operate" },
      { name: "description", content: "Pending submissions awaiting your decision." },
    ],
  }),
  component: ApprovalsPage,
});
