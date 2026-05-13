import {
  ClipboardCheck,
  ClipboardList,
  GitBranch,
  Goal,
  LayoutDashboard,
  ListChecks,
  Network,
  Target,
  TrendingUp,
  Users,
} from "lucide-react";

import type { NavDefinition } from "../nav-definition";

const E = "EMPLOYEE" as const;

/** Employee / Operator — “Can See” list. */
export const EMPLOYEE_NAV: NavDefinition[] = [
  { group: "My work", label: "My Dashboard", to: "/", icon: LayoutDashboard, roles: [E] },
  { group: "My work", label: "My OKRs", to: "/okrs", icon: Target, roles: [E] },
  { group: "My work", label: "My Team Alignment", to: "/alignment", icon: Network, roles: [E] },
  { group: "My work", label: "My Progress", to: "/progress", icon: TrendingUp, roles: [E] },
  { group: "My work", label: "My Reviews", to: "/reviews?view=my", icon: ClipboardCheck, roles: [E] },
  { group: "My work", label: "My Reporting Manager", to: "/hierarchy", icon: GitBranch, roles: [E] },
  { group: "My work", label: "Team Visibility", to: "/teams", icon: Users, roles: [E] },
  { group: "My work", label: "Organization Goal Alignment", to: "/alignment", icon: Goal, roles: [E] },
  { group: "My work", label: "Progress Submission History", to: "/progress", icon: ClipboardList, roles: [E] },
  { group: "My work", label: "Assigned Tasks", to: "/progress", icon: ListChecks, roles: [E] },
  { group: "My work", label: "Review Status", to: "/reviews?view=status", icon: ClipboardCheck, roles: [E] },
];
