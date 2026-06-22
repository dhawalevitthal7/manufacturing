import {
  BarChart3,
  Globe2,
  ListChecks,
  Network,
  Sparkles,
  Target,
} from "lucide-react";

import type { NavDefinition } from "../nav-definition";

const CSO = "CSO" as const;

/** CSO — technical / quality / HSE functional head (mirrors CFO nav pattern). */
export const CSO_NAV: NavDefinition[] = [
  { group: "Technical & quality", label: "Organization OKRs", to: "/okrs?level=organization", icon: Target, roles: [CSO] },
  { group: "Technical & quality", label: "Organization Visibility", to: "/", icon: Globe2, roles: [CSO] },
  { group: "Technical & quality", label: "Plant OKRs", to: "/okrs?level=plant", icon: Target, roles: [CSO] },
  { group: "Technical & quality", label: "Department OKRs", to: "/okrs?level=department", icon: Target, roles: [CSO] },
  { group: "Technical & quality", label: "Alignment Dashboard", to: "/alignment", icon: Network, roles: [CSO] },
  { group: "Technical & quality", label: "Review Analytics", to: "/reviews?view=analytics", icon: BarChart3, roles: [CSO] },
  { group: "Technical & quality", label: "Functional Approvals", to: "/approvals?stage=functional", icon: ListChecks, roles: [CSO] },
  { group: "Technical & quality", label: "AI Insights", to: "/alignment", icon: Sparkles, roles: [CSO] },
];
