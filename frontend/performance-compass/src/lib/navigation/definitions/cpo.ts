import {
  BarChart3,
  Globe2,
  ListChecks,
  Network,
  Sparkles,
  Target,
} from "lucide-react";

import type { NavDefinition } from "../nav-definition";

const CPO = "CPO" as const;

/** CPO — procurement / SCM functional head (mirrors CFO nav pattern). */
export const CPO_NAV: NavDefinition[] = [
  { group: "Procurement & SCM", label: "Organization OKRs", to: "/okrs?level=organization", icon: Target, roles: [CPO] },
  { group: "Procurement & SCM", label: "Organization Visibility", to: "/", icon: Globe2, roles: [CPO] },
  { group: "Procurement & SCM", label: "Plant OKRs", to: "/okrs?level=plant", icon: Target, roles: [CPO] },
  { group: "Procurement & SCM", label: "Department OKRs", to: "/okrs?level=department", icon: Target, roles: [CPO] },
  { group: "Procurement & SCM", label: "Alignment Dashboard", to: "/alignment", icon: Network, roles: [CPO] },
  { group: "Procurement & SCM", label: "Review Analytics", to: "/reviews?view=analytics", icon: BarChart3, roles: [CPO] },
  { group: "Procurement & SCM", label: "Functional Approvals", to: "/approvals?stage=functional", icon: ListChecks, roles: [CPO] },
  { group: "Procurement & SCM", label: "AI Insights", to: "/alignment", icon: Sparkles, roles: [CPO] },
];
