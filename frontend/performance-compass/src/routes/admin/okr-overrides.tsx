import { createFileRoute } from "@tanstack/react-router";
import { OkrOverridesPage } from "@/components/admin/okr-overrides-page";

export const Route = createFileRoute("/admin/okr-overrides")({
  head: () => ({
    meta: [
      { title: "OKR Admin Overrides — Axis Operate" },
      {
        name: "description",
        content: "SUPER_ADMIN audited override for OKR lifecycle when business approvers are unavailable.",
      },
    ],
  }),
  component: OkrOverridesPage,
});
