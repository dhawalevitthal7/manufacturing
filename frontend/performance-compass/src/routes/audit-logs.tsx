import { createFileRoute } from "@tanstack/react-router";
import { PagePlaceholder } from "@/components/layout/page-placeholder";

export const Route = createFileRoute("/audit-logs")({
  head: () => ({
    meta: [
      { title: "Audit Logs — Axis Operate" },
      { name: "description", content: "System events and access trail." },
    ],
  }),
  component: () => <PagePlaceholder title="Audit Logs" description="System events and access trail." />,
});
