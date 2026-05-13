import { createFileRoute, Outlet } from "@tanstack/react-router";

export const Route = createFileRoute("/auth/__layout")({
  component: AuthLayout,
});

function AuthLayout() {
  return <Outlet />;
}
