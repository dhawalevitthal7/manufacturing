import {
  AlertTriangle,
  BarChart3,
  ClipboardList,
  Gauge,
  LayoutDashboard,
  ListChecks,
  Network,
  Target,
  TrendingUp,
  Users,
} from "lucide-react";

import type { NavDefinition } from "../nav-definition";

const COO = "COO" as const;

/** Chief Operating Officer — plant-wide oversight. */
export const COO_NAV: NavDefinition[] = [
  { group: "Operations", label: "Cross-Plant Dashboard", to: "/", icon: LayoutDashboard, roles: [COO] },
  { group: "Operations OKRs", label: "Plant OKRs", to: "/okrs?level=plant", icon: Target, roles: [COO] },
  { group: "Operations OKRs", label: "Department OKRs", to: "/okrs?level=department", icon: Target, roles: [COO] },
  { group: "Operations", label: "Department Alignment", to: "/alignment", icon: Network, roles: [COO] },
  { group: "Operations", label: "Operational Execution Visibility", to: "/progress", icon: Gauge, roles: [COO] },
  { group: "Operations", label: "OKR Creation Approvals", to: "/approvals?type=okr_creation", icon: ListChecks, roles: [COO] },
  { group: "Operations", label: "Progress Validation Queue", to: "/approvals?type=progress", icon: ListChecks, roles: [COO] },
  { group: "Operations", label: "Escalation Dashboard", to: "/blockers", icon: AlertTriangle, roles: [COO] },
  { group: "Operations analytics", label: "Cross-Plant Team Visibility", to: "/teams", icon: Users, roles: [COO] },
  { group: "Operations analytics", label: "Plant Review Summaries", to: "/reviews?view=summaries", icon: ClipboardList, roles: [COO] },
  { group: "Operations analytics", label: "Delayed Departments", to: "/okrs?level=department", icon: TrendingUp, roles: [COO] },
  { group: "Operations analytics", label: "Review Completion Analytics", to: "/reviews?view=completion", icon: BarChart3, roles: [COO] },
];
