import { createFileRoute } from "@tanstack/react-router";
import { PagePlaceholder } from "@/components/layout/page-placeholder";

export const Route = createFileRoute("/hierarchy")({
  head: () => ({
    meta: [
      { title: "Organizational Hierarchy — Axis Operate" },
      { name: "description", content: "Visualize the reporting structure." },
    ],
  }),
  component: () => <PagePlaceholder title="Organizational Hierarchy" description="Visualize the reporting structure." />,
});
