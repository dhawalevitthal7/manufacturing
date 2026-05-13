import {
  Activity,
  BarChart3,
  Building2,
  ClipboardCheck,
  Factory,
  Gauge,
  GitBranch,
  LayoutDashboard,
  Layers3,
  ListChecks,
  Lock,
  Monitor,
  Network,
  ScrollText,
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
  { group: "Structure & governance", label: "Reporting Hierarchy", to: "/hierarchy", icon: GitBranch, roles: [SA] },
  { group: "Structure & governance", label: "Designation Structure", to: "/settings", icon: Layers3, roles: [SA] },
  { group: "Structure & governance", label: "Permission Matrix", to: "/permissions", icon: Shield, roles: [SA] },
  { group: "Alignment", label: "Organization Alignment Dashboard", to: "/alignment", icon: Network, roles: [SA] },
  { group: "OKRs", label: "Organization OKRs", to: "/okrs?level=organization", icon: Target, roles: [SA] },
  { group: "OKRs", label: "Plant OKRs", to: "/okrs?level=plant", icon: Target, roles: [SA] },
  { group: "OKRs", label: "Department OKRs", to: "/okrs?level=department", icon: Target, roles: [SA] },
  { group: "OKRs", label: "Team OKRs", to: "/okrs?level=team", icon: Target, roles: [SA] },
  { group: "OKRs", label: "Employee OKRs", to: "/okrs?level=employee", icon: Target, roles: [SA] },
  { group: "Reviews & analytics", label: "Review Analytics", to: "/reviews?view=analytics", icon: BarChart3, roles: [SA] },
  { group: "Reviews & analytics", label: "Audit Logs", to: "/audit-logs", icon: ScrollText, roles: [SA] },
  { group: "Reviews & analytics", label: "Approval Chains", to: "/approvals", icon: ListChecks, roles: [SA] },
  { group: "Configuration", label: "Module Configuration", to: "/settings", icon: Monitor, roles: [SA] },
  { group: "Configuration", label: "Dashboard Configuration", to: "/settings", icon: Gauge, roles: [SA] },
  { group: "Configuration", label: "Feature Flags", to: "/settings", icon: Lock, roles: [SA] },
  { group: "Configuration", label: "Review Cycle Settings", to: "/settings", icon: ClipboardCheck, roles: [SA] },
  { group: "Configuration", label: "Shift Structure", to: "/settings", icon: Activity, roles: [SA] },
  { group: "Configuration", label: "Team Structure", to: "/teams", icon: Users, roles: [SA] },
  { group: "Activity", label: "Organization Activity Feed", to: "/progress", icon: Activity, roles: [SA] },
];
