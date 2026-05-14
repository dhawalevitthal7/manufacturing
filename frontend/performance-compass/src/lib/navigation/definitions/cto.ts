import { Network, Sparkles, Target, TrendingUp } from "lucide-react";

import type { NavDefinition } from "../nav-definition";

const CTO = "CTO" as const;

/** CTO — engineering execution visibility (aligned with CTO module matrix). */
export const CTO_NAV: NavDefinition[] = [
  { group: "Engineering OKRs", label: "Plant OKRs", to: "/okrs?level=plant", icon: Target, roles: [CTO] },
  { group: "Engineering OKRs", label: "Department OKRs", to: "/okrs?level=department", icon: Target, roles: [CTO] },
  { group: "Engineering OKRs", label: "Team OKRs", to: "/okrs?level=team", icon: Target, roles: [CTO] },
  { group: "Engineering OKRs", label: "Employee OKRs", to: "/okrs?level=employee", icon: Target, roles: [CTO] },
  { group: "Engineering", label: "Progress Tracking", to: "/progress", icon: TrendingUp, roles: [CTO] },
  { group: "Engineering", label: "Alignment Dashboard", to: "/alignment", icon: Network, roles: [CTO] },
  { group: "Engineering", label: "AI Insights", to: "/alignment", icon: Sparkles, roles: [CTO] },
];
