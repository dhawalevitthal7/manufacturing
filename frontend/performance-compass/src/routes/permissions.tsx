import { createFileRoute } from "@tanstack/react-router";
import { PermissionMatrix } from "@/components/admin/permission-matrix";

export const Route = createFileRoute("/permissions")({
  head: () => ({
    meta: [
      { title: "Permission Matrix — Axis Operate" },
      { name: "description", content: "Enterprise RBAC permission configuration and access matrix." },
    ],
  }),
  component: () => <PermissionMatrix />,
});
