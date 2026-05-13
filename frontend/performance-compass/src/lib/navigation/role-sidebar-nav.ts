import { ALL_NAV_DEFINITIONS } from "./definitions";
import type { SidebarNavGroup, SidebarNavItem } from "./role-sidebar-nav-types";
import { normalizeCanonicalRole } from "./role-nav-types";

export type { SidebarNavGroup, SidebarNavItem };
export { normalizeCanonicalRole, type CanonicalRole } from "./role-nav-types";

/** Sidebar sections from the enterprise “Can See” matrix (visibility-only). */
export function getSidebarGroupsForRole(systemRole: string): SidebarNavGroup[] {
  const canonical = normalizeCanonicalRole(systemRole);
  const groups = new Map<string, SidebarNavItem[]>();

  for (const def of ALL_NAV_DEFINITIONS) {
    if (!def.roles.includes(canonical)) continue;
    const items = groups.get(def.group) ?? [];
    items.push({ label: def.label, to: def.to, icon: def.icon });
    groups.set(def.group, items);
  }

  return [...groups.entries()].map(([label, items]) => ({ label, items }));
}
