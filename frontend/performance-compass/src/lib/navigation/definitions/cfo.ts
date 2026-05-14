import {
  BarChart3,
  Globe2,
  ListChecks,
  Network,
  Sparkles,
  Target,
} from "lucide-react";

import type { NavDefinition } from "../nav-definition";

const CFO = "CFO" as const;

/** CFO — org-wide read / analytics (aligned with CFO module matrix). */
export const CFO_NAV: NavDefinition[] = [
  { group: "Finance & strategy", label: "Organization OKRs", to: "/okrs?level=organization", icon: Target, roles: [CFO] },
  { group: "Finance & strategy", label: "Organization Visibility", to: "/", icon: Globe2, roles: [CFO] },
  { group: "Finance & strategy", label: "Plant OKRs", to: "/okrs?level=plant", icon: Target, roles: [CFO] },
  { group: "Finance & strategy", label: "Department OKRs", to: "/okrs?level=department", icon: Target, roles: [CFO] },
  { group: "Finance & strategy", label: "Alignment Dashboard", to: "/alignment", icon: Network, roles: [CFO] },
  { group: "Finance & strategy", label: "Review Analytics", to: "/reviews?view=analytics", icon: BarChart3, roles: [CFO] },
  { group: "Finance & strategy", label: "Approval Queue", to: "/approvals", icon: ListChecks, roles: [CFO] },
  { group: "Finance & strategy", label: "AI Insights", to: "/alignment", icon: Sparkles, roles: [CFO] },
];
