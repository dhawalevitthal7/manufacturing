import {
  AlertTriangle,
  BarChart3,
  ClipboardList,
  Gauge,
  LayoutDashboard,
  LineChart,
  ListChecks,
  Network,
  Sparkles,
  Target,
  TrendingUp,
  Users,
  Workflow,
} from "lucide-react";

import type { NavDefinition } from "../nav-definition";

const VP = "VP_OPERATIONS" as const;

/** VP Manufacturing / Operations — “Can See” list. */
export const VP_OPERATIONS_NAV: NavDefinition[] = [
  { group: "Operations", label: "Cross-Plant Dashboard", to: "/", icon: LayoutDashboard, roles: [VP] },
  { group: "Operations OKRs", label: "Regional OKRs", to: "/okrs?level=region", icon: Target, roles: [VP] },
  { group: "Operations OKRs", label: "Plant OKRs", to: "/okrs?level=plant", icon: Target, roles: [VP] },
  { group: "Operations", label: "Department Alignment", to: "/alignment", icon: Network, roles: [VP] },
  { group: "Operations", label: "Operational Execution Visibility", to: "/progress", icon: Gauge, roles: [VP] },
  { group: "Operations", label: "Escalation Dashboard", to: "/blockers", icon: AlertTriangle, roles: [VP] },
  { group: "Operations", label: "Approval Queue", to: "/approvals", icon: ListChecks, roles: [VP] },
  { group: "Operations analytics", label: "Review Completion Analytics", to: "/reviews?view=completion", icon: BarChart3, roles: [VP] },
  { group: "Operations analytics", label: "Cross-Plant Team Visibility", to: "/teams", icon: Users, roles: [VP] },
  { group: "Operations analytics", label: "Operational AI Insights", to: "/alignment", icon: Sparkles, roles: [VP] },
  { group: "Operations analytics", label: "Plant Review Summaries", to: "/reviews?view=summaries", icon: ClipboardList, roles: [VP] },
  { group: "Operations analytics", label: "Execution Bottlenecks", to: "/blockers", icon: Workflow, roles: [VP] },
  { group: "Operations analytics", label: "Delayed Departments", to: "/okrs?level=department", icon: TrendingUp, roles: [VP] },
  { group: "Operations analytics", label: "Alignment Quality", to: "/alignment", icon: LineChart, roles: [VP] },
];
