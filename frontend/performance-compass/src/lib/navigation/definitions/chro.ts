import {
  BarChart3,
  Globe2,
  ListChecks,
  Network,
  Sparkles,
  Target,
} from "lucide-react";

import type { NavDefinition } from "../nav-definition";

const CHRO = "CHRO" as const;

/** CHRO — HR / IR functional head (mirrors CFO nav pattern). */
export const CHRO_NAV: NavDefinition[] = [
  { group: "HR & IR", label: "Organization OKRs", to: "/okrs?level=organization", icon: Target, roles: [CHRO] },
  { group: "HR & IR", label: "Organization Visibility", to: "/", icon: Globe2, roles: [CHRO] },
  { group: "HR & IR", label: "Plant OKRs", to: "/okrs?level=plant", icon: Target, roles: [CHRO] },
  { group: "HR & IR", label: "Department OKRs", to: "/okrs?level=department", icon: Target, roles: [CHRO] },
  { group: "HR & IR", label: "Alignment Dashboard", to: "/alignment", icon: Network, roles: [CHRO] },
  { group: "HR & IR", label: "Review Analytics", to: "/reviews?view=analytics", icon: BarChart3, roles: [CHRO] },
  { group: "HR & IR", label: "Functional Approvals", to: "/approvals?stage=functional", icon: ListChecks, roles: [CHRO] },
  { group: "HR & IR", label: "AI Insights", to: "/alignment", icon: Sparkles, roles: [CHRO] },
];
