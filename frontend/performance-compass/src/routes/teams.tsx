/** @deprecated Use /org-tree — kept for backward-compatible deep links. */
import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/teams")({
  beforeLoad: () => {
    throw redirect({ to: "/org-tree" });
  },
});
