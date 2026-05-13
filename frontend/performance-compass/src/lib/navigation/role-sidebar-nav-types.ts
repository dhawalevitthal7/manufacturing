import type { LucideIcon } from "lucide-react";

export interface SidebarNavItem {
  label: string;
  to: string;
  icon: LucideIcon;
}

export interface SidebarNavGroup {
  label: string;
  items: SidebarNavItem[];
}
