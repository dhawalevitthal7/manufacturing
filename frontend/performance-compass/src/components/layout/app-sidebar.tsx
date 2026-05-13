import { Link, useRouterState } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { useMemo } from "react";
import { Factory, ChevronLeft } from "lucide-react";

import { getSidebarGroupsForRole } from "@/lib/navigation/role-sidebar-nav";
import { isNavHrefActive, parseRouteHref } from "@/lib/navigation/href";
import { useAuthStore } from "@/lib/stores/auth-store";
import { useUIStore } from "@/lib/stores/ui-store";
import { cn } from "@/lib/utils";

export function AppSidebar() {
  const collapsed = useUIStore((s) => s.sidebarCollapsed);
  const toggle = useUIStore((s) => s.toggleSidebar);
  const { permissions, user } = useAuthStore();
  const location = useRouterState({ select: (r) => r.location });

  const groups = useMemo(
    () => (user ? getSidebarGroupsForRole(user.system_role) : []),
    [user],
  );

  const pathname = location.pathname;
  const searchObj =
    typeof location.search === "object" && location.search !== null
      ? (location.search as Record<string, unknown>)
      : {};

  if (!user) return null;

  return (
    <motion.aside
      animate={{ width: collapsed ? 72 : 288 }}
      transition={{ type: "spring", stiffness: 260, damping: 30 }}
      className="sticky top-0 z-30 hidden h-screen flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground md:flex"
    >
      <div className="flex h-16 items-center gap-3 border-b border-sidebar-border px-4">
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg gradient-primary glow-primary">
          <Factory className="h-5 w-5 text-primary-foreground" />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold">Axis Operate</div>
            <div className="truncate text-[11px] text-muted-foreground">Manufacturing OS</div>
          </div>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto px-2 py-4">
        {groups.map((group) => (
          <div key={group.label} className="mb-5">
            {!collapsed && (
              <div className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                {group.label}
              </div>
            )}
            <ul className="space-y-0.5">
              {group.items.map((item) => {
                const active = isNavHrefActive(item.to, pathname, searchObj);
                const Icon = item.icon;
                const { pathname: linkPath, search: linkSearch } = parseRouteHref(item.to);
                return (
                  <li key={`${group.label}-${item.label}-${item.to}`}>
                    <Link
                      to={linkPath}
                      {...(linkSearch && Object.keys(linkSearch).length > 0 ? { search: linkSearch } : {})}
                      className={cn(
                        "group relative flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                        active
                          ? "bg-sidebar-accent text-sidebar-accent-foreground"
                          : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
                      )}
                    >
                      {active && (
                        <motion.span
                          layoutId={`nav-${item.to}`}
                          className="absolute inset-y-1 left-0 w-0.5 rounded-full bg-primary"
                        />
                      )}
                      <Icon className="h-4 w-4 shrink-0" />
                      {!collapsed && <span className="flex-1 truncate">{item.label}</span>}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="border-t border-sidebar-border p-3">
        <div className="flex items-center gap-3 rounded-md p-2">
          <div
            className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-xs font-semibold text-primary-foreground"
            style={{ backgroundColor: user.avatarColor ?? "#6366f1" }}
          >
            {user.name.split(" ").map((n) => n[0]).join("").slice(0, 2)}
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <div className="truncate text-sm font-medium">{user.name}</div>
              <div className="truncate text-[11px] text-muted-foreground">
                {permissions?.system_role ?? user.system_role}
              </div>
              {permissions?.system_role === "SUPER_ADMIN" && (
                <div className="mt-1 inline-block rounded-full bg-primary/20 px-1.5 py-0.5 text-[9px] font-semibold text-primary">
                  Admin
                </div>
              )}
            </div>
          )}
        </div>
        <button
          type="button"
          onClick={toggle}
          className="mt-2 flex w-full items-center justify-center gap-2 rounded-md border border-sidebar-border px-2 py-1.5 text-xs text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
        >
          <ChevronLeft className={cn("h-3.5 w-3.5 transition-transform", collapsed && "rotate-180")} />
          {!collapsed && "Collapse"}
        </button>
      </div>
    </motion.aside>
  );
}
