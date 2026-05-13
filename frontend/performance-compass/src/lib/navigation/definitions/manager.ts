import {
  Activity,
  AlertTriangle,
  BarChart3,
  ClipboardCheck,
  ClipboardList,
  LayoutDashboard,
  ListChecks,
  Network,
  Target,
  TrendingUp,
} from "lucide-react";

import type { NavDefinition } from "../nav-definition";

const M = "MANAGER" as const;

/** Manager — “Can See” list. */
export const MANAGER_NAV: NavDefinition[] = [
  { group: "Team management", label: "Team Dashboard", to: "/", icon: LayoutDashboard, roles: [M] },
  { group: "Team OKRs", label: "Team OKRs", to: "/okrs?level=team", icon: Target, roles: [M] },
  { group: "Team OKRs", label: "Employee OKRs", to: "/okrs?level=employee", icon: Target, roles: [M] },
  { group: "Team execution", label: "Employee Progress", to: "/progress", icon: TrendingUp, roles: [M] },
  { group: "Team execution", label: "Progress Validation Queue", to: "/approvals", icon: ListChecks, roles: [M] },
  { group: "Team execution", label: "Review Queue", to: "/reviews?view=queue", icon: ClipboardList, roles: [M] },
  { group: "Team execution", label: "Team Alignment Dashboard", to: "/alignment", icon: Network, roles: [M] },
  { group: "Team execution", label: "Team Activity Feed", to: "/progress", icon: Activity, roles: [M] },
  { group: "Team analytics", label: "Team Analytics", to: "/teams", icon: BarChart3, roles: [M] },
  { group: "Team execution", label: "Pending Approvals", to: "/approvals", icon: ClipboardCheck, roles: [M] },
  { group: "Team execution", label: "Employee Review Status", to: "/reviews?view=employee-status", icon: ClipboardCheck, roles: [M] },
  { group: "Team execution", label: "Escalation Queue", to: "/blockers", icon: AlertTriangle, roles: [M] },
];
