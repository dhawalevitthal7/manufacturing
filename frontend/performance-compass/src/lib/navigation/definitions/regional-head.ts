import {
  AlertTriangle,
  BarChart3,
  ClipboardCheck,
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
  CheckCircle2,
} from "lucide-react";

import type { NavDefinition } from "../nav-definition";

const RH = "REGIONAL_HEAD" as const;

/** Regional Head — “Can See” list (aligned with REGIONAL_HEAD module matrix). */
export const REGIONAL_HEAD_NAV: NavDefinition[] = [
  { group: "Operations", label: "Cross-Plant Dashboard", to: "/", icon: LayoutDashboard, roles: [RH] },
  { group: "Operations OKRs", label: "Regional OKRs", to: "/okrs?level=region", icon: Target, roles: [RH] },
  { group: "Operations OKRs", label: "Plant OKRs", to: "/okrs?level=plant", icon: Target, roles: [RH] },
  { group: "Operations OKRs", label: "Department OKRs", to: "/okrs?level=department", icon: Target, roles: [RH] },
  { group: "Operations OKRs", label: "Team OKRs", to: "/okrs?level=team", icon: Target, roles: [RH] },
  { group: "Operations OKRs", label: "Validations (0)", to: "/okrs?view=validations", icon: CheckCircle2, roles: [RH] },
  { group: "Operations", label: "Department Alignment", to: "/alignment", icon: Network, roles: [RH] },
  { group: "Operations", label: "Operational Execution Visibility", to: "/progress", icon: Gauge, roles: [RH] },
  { group: "Operations", label: "Escalation Dashboard", to: "/blockers", icon: AlertTriangle, roles: [RH] },
  { group: "Operations", label: "OKR Creation Approvals", to: "/approvals?type=okr_creation", icon: ListChecks, roles: [RH] },
  { group: "Operations", label: "Progress Validation Queue", to: "/approvals?type=progress", icon: ListChecks, roles: [RH] },
  { group: "Operations", label: "Review Dashboard", to: "/reviews?view=dashboard", icon: ClipboardCheck, roles: [RH] },
  { group: "Operations analytics", label: "Review Completion Analytics", to: "/reviews?view=completion", icon: BarChart3, roles: [RH] },
  { group: "Operations analytics", label: "Cross-Plant Team Visibility", to: "/teams", icon: Users, roles: [RH] },
  { group: "Operations analytics", label: "Operational AI Insights", to: "/alignment", icon: Sparkles, roles: [RH] },
  { group: "Operations analytics", label: "Plant Review Summaries", to: "/reviews?view=summaries", icon: ClipboardList, roles: [RH] },
  { group: "Operations analytics", label: "Execution Bottlenecks", to: "/blockers", icon: Workflow, roles: [RH] },
  { group: "Operations analytics", label: "Delayed Departments", to: "/okrs?level=department", icon: TrendingUp, roles: [RH] },
  { group: "Operations analytics", label: "Alignment Quality", to: "/alignment", icon: LineChart, roles: [RH] },
];
