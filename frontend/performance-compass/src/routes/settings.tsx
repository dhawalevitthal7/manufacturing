import { createFileRoute } from "@tanstack/react-router";
import { AdminPanel } from "@/components/admin/admin-panel";

export const Route = createFileRoute("/settings")({
  head: () => ({
    meta: [
      { title: "Administration — Axis Operate" },
      { name: "description", content: "Administration panel for managing organization, teams, and permissions." },
    ],
  }),
  component: () => <AdminPanel />,
});
