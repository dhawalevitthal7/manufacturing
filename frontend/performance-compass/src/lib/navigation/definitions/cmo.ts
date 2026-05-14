import {
  BarChart3,
  ClipboardCheck,
  Globe2,
  Network,
  Sparkles,
  Target,
} from "lucide-react";

import type { NavDefinition } from "../nav-definition";

const CMO = "CMO" as const;

/** CMO — org-wide marketing & reviews visibility (aligned with CMO module matrix). */
export const CMO_NAV: NavDefinition[] = [
  { group: "Marketing & growth", label: "Organization OKRs", to: "/okrs?level=organization", icon: Target, roles: [CMO] },
  { group: "Marketing & growth", label: "Organization Visibility", to: "/", icon: Globe2, roles: [CMO] },
  { group: "Marketing & growth", label: "Department OKRs", to: "/okrs?level=department", icon: Target, roles: [CMO] },
  { group: "Marketing & growth", label: "Team OKRs", to: "/okrs?level=team", icon: Target, roles: [CMO] },
  { group: "Marketing & growth", label: "Alignment Dashboard", to: "/alignment", icon: Network, roles: [CMO] },
  { group: "Marketing & growth", label: "Review Dashboard", to: "/reviews?view=dashboard", icon: ClipboardCheck, roles: [CMO] },
  { group: "Marketing & growth", label: "Review Analytics", to: "/reviews?view=analytics", icon: BarChart3, roles: [CMO] },
  { group: "Marketing & growth", label: "AI Insights", to: "/alignment", icon: Sparkles, roles: [CMO] },
];
