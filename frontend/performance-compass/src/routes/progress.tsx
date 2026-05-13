import { createFileRoute } from "@tanstack/react-router";
import { PagePlaceholder } from "@/components/layout/page-placeholder";

export const Route = createFileRoute("/progress")({
  head: () => ({
    meta: [
      { title: "Progress Tracking — Axis Operate" },
      { name: "description", content: "Submit, validate and analyze KR execution." },
    ],
  }),
  component: () => <PagePlaceholder title="Progress Tracking" description="Submit, validate and analyze KR execution." />,
});
