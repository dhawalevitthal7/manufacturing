import { createFileRoute } from "@tanstack/react-router";
import { HierarchyPage } from "@/components/hierarchy/hierarchy-page";

export const Route = createFileRoute("/hierarchy")({
  head: () => ({
    meta: [
      { title: "Regions & Corporate Functions — Axis Operate" },
      {
        name: "description",
        content:
          "Manage regions and corporate functions for your organization tree: create, edit, and remove top-level org nodes.",
      },
    ],
  }),
  component: HierarchyRoute,
});

function HierarchyRoute() {
  return <HierarchyPage />;
}
