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

const CRO = "CRO" as const;

/** Chief Regional Officer — region-wide oversight. */
export const CRO_NAV: NavDefinition[] = [
  { group: "Regional", label: "Regional Dashboard", to: "/", icon: LayoutDashboard, roles: [CRO] },
  { group: "Regional OKRs", label: "Regional OKRs", to: "/okrs?level=region", icon: Target, roles: [CRO] },
  { group: "Regional OKRs", label: "Plant OKRs", to: "/okrs?level=plant", icon: Target, roles: [CRO] },
  { group: "Regional", label: "Regional Alignment", to: "/alignment", icon: Network, roles: [CRO] },
  { group: "Regional", label: "Execution Visibility", to: "/progress", icon: Gauge, roles: [CRO] },
  { group: "Regional", label: "OKR Creation Approvals", to: "/approvals?type=okr_creation", icon: ListChecks, roles: [CRO] },
  { group: "Regional", label: "Progress Validation Queue", to: "/approvals?type=progress", icon: ListChecks, roles: [CRO] },
  { group: "Regional", label: "Escalation Dashboard", to: "/blockers", icon: AlertTriangle, roles: [CRO] },
  { group: "Regional analytics", label: "Cross-Region Visibility", to: "/teams", icon: Users, roles: [CRO] },
  { group: "Regional analytics", label: "Review Summaries", to: "/reviews?view=summaries", icon: ClipboardList, roles: [CRO] },
  { group: "Regional analytics", label: "Review Completion Analytics", to: "/reviews?view=completion", icon: BarChart3, roles: [CRO] },
  { group: "Regional analytics", label: "Delayed Plants", to: "/okrs?level=plant", icon: TrendingUp, roles: [CRO] },
];
