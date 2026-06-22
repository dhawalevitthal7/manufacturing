import {
  ClipboardCheck,
  ClipboardList,
  GitBranch,
  History,
  LayoutDashboard,
  ListChecks,
  MessageCircle,
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
  { group: "My work", label: "My Progress", to: "/progress", icon: TrendingUp, roles: [E] },
  { group: "My work", label: "Weekly Check-In", to: "/reviews?view=checkins", icon: MessageCircle, roles: [E] },
  { group: "My work", label: "My Timeline", to: "/reviews?view=timeline", icon: History, roles: [E] },
  { group: "My work", label: "Quarterly Reviews", to: "/reviews?view=reviews", icon: ClipboardCheck, roles: [E] },
  { group: "My work", label: "My Reporting Manager", to: "/hierarchy", icon: GitBranch, roles: [E] },
  { group: "My work", label: "Team Visibility", to: "/teams", icon: Users, roles: [E] },
  { group: "My work", label: "Progress Submission History", to: "/progress", icon: ClipboardList, roles: [E] },
  { group: "My work", label: "Assigned Tasks", to: "/progress", icon: ListChecks, roles: [E] },
];
