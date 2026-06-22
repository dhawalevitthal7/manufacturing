import { createFileRoute } from "@tanstack/react-router";
import { OrgTreePage } from "@/components/org-tree/org-tree-page";

type OrgTreeSearch = {
  focus?: string;
};

export const Route = createFileRoute("/org-tree")({
  validateSearch: (search: Record<string, unknown>): OrgTreeSearch => ({
    focus: typeof search.focus === "string" ? search.focus : undefined,
  }),
  head: () => ({
    meta: [
      { title: "Organization Tree — Axis Operate" },
      {
        name: "description",
        content: "Unified explorer for regions, plants, departments, teams, and corporate functions.",
      },
    ],
  }),
  component: OrgTreeRoute,
});

function OrgTreeRoute() {
  const { focus } = Route.useSearch();
  return <OrgTreePage focusNodeId={focus} />;
}
