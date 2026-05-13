import { createFileRoute } from "@tanstack/react-router";
import { PagePlaceholder } from "@/components/layout/page-placeholder";

export const Route = createFileRoute("/alignment")({
  head: () => ({
    meta: [
      { title: "Strategic Alignment — Axis Operate" },
      { name: "description", content: "Cascade goals from organization to operator." },
    ],
  }),
  component: () => <PagePlaceholder title="Strategic Alignment" description="Cascade goals from organization to operator." />,
});
