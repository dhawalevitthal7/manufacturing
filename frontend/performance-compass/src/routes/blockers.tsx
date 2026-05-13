import { createFileRoute } from "@tanstack/react-router";
import { PagePlaceholder } from "@/components/layout/page-placeholder";

export const Route = createFileRoute("/blockers")({
  head: () => ({
    meta: [
      { title: "Blockers — Axis Operate" },
      { name: "description", content: "Active blockers reported by your scope." },
    ],
  }),
  component: () => <PagePlaceholder title="Blockers" description="Active blockers reported by your scope." />,
});
