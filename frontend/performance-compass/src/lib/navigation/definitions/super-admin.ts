import {
  BookOpen,
  Building2,
  Factory,
  GitBranch,
  LayoutDashboard,
  Layers3,
  Network,
  Shield,
  Target,
  UserCircle2,
  Users,
} from "lucide-react";

import type { NavDefinition } from "../nav-definition";

const SA = "SUPER_ADMIN" as const;

/** SUPER_ADMIN / Organization Admin — “Can See” list. */
export const SUPER_ADMIN_NAV: NavDefinition[] = [
  { group: "Dashboards", label: "Organization Dashboard", to: "/", icon: LayoutDashboard, roles: [SA] },
  { group: "Organization scope", label: "All Plants", to: "/employees?segment=plants", icon: Factory, roles: [SA] },
  { group: "Organization scope", label: "All Departments", to: "/employees?segment=departments", icon: Building2, roles: [SA] },
  { group: "Organization scope", label: "All Teams", to: "/employees?segment=teams", icon: Users, roles: [SA] },
  { group: "Organization scope", label: "All Employees", to: "/employees?segment=directory", icon: UserCircle2, roles: [SA] },
  { group: "Structure & governance", label: "Organization Tree", to: "/org-tree", icon: Network, roles: [SA] },
  { group: "Structure & governance", label: "Regions & Corp Functions", to: "/hierarchy", icon: GitBranch, roles: [SA] },
  { group: "Structure & governance", label: "Designation Structure", to: "/settings", icon: Layers3, roles: [SA] },
  { group: "Structure & governance", label: "Permission Matrix", to: "/permissions", icon: Shield, roles: [SA] },
  { group: "Alignment", label: "Organization Alignment Dashboard", to: "/alignment", icon: Network, roles: [SA] },
  { group: "OKRs", label: "Organization OKRs", to: "/okrs?level=organization", icon: Target, roles: [SA] },
  { group: "OKRs", label: "Regional OKRs", to: "/okrs?level=region", icon: Target, roles: [SA] },
  { group: "OKRs", label: "Plant OKRs", to: "/okrs?level=plant", icon: Target, roles: [SA] },
  { group: "OKRs", label: "Department OKRs", to: "/okrs?level=department", icon: Target, roles: [SA] },
  { group: "OKRs", label: "Team OKRs", to: "/okrs?level=team", icon: Target, roles: [SA] },
  { group: "OKRs", label: "Employee OKRs", to: "/okrs?level=employee", icon: Target, roles: [SA] },
  { group: "OKRs", label: "OKR Lifecycle Overrides", to: "/admin/okr-overrides", icon: Shield, roles: [SA] },
  { group: "Administration", label: "Onboarding", to: "/onboarding", icon: BookOpen, roles: [SA] },
];
