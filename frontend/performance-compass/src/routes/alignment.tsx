import { createFileRoute, redirect } from "@tanstack/react-router";
import { ConstellationPage } from "@/pages/ConstellationPage";
import { useAuthStore } from "@/lib/stores/auth-store";

function AlignmentPage() {
  const { user } = useAuthStore();
  const orgId = user?.org_id || "org_default";

  return <ConstellationPage orgId={orgId} />;
}

export const Route = createFileRoute("/alignment")({
  beforeLoad: () => {
    const user = useAuthStore.getState().user;
    if (user?.system_role === "EMPLOYEE") {
      throw redirect({ to: "/" });
    }
  },
  head: () => ({
    meta: [
      { title: "OKR Alignment — PerformBharat" },
      { name: "description", content: "Role-based OKR constellation alignment visualization" },
    ],
  }),
  component: AlignmentPage,
});
