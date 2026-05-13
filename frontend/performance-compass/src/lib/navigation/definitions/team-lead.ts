import {
  Activity,
  Bell,
  ClipboardCheck,
  LayoutDashboard,
  ListChecks,
  Network,
  TrendingUp,
  Users,
} from "lucide-react";

import type { NavDefinition } from "../nav-definition";

const TL = "TEAM_LEAD" as const;

/** Team Lead — “Can See” list. */
export const TEAM_LEAD_NAV: NavDefinition[] = [
  { group: "Team lead", label: "Team Execution Dashboard", to: "/", icon: LayoutDashboard, roles: [TL] },
  { group: "Team lead", label: "Assigned Team Members", to: "/employees", icon: Users, roles: [TL] },
  { group: "Team lead", label: "Team Progress", to: "/progress", icon: TrendingUp, roles: [TL] },
  { group: "Team lead", label: "Team Alignment", to: "/alignment", icon: Network, roles: [TL] },
  { group: "Team lead", label: "Shift Visibility", to: "/teams", icon: Activity, roles: [TL] },
  { group: "Team lead", label: "Employee Execution Updates", to: "/progress", icon: Activity, roles: [TL] },
  { group: "Team lead", label: "Pending Validations", to: "/approvals", icon: ListChecks, roles: [TL] },
  { group: "Team lead", label: "Team Reviews", to: "/reviews?view=team", icon: ClipboardCheck, roles: [TL] },
  { group: "Team lead", label: "Operational Alerts", to: "/blockers", icon: Bell, roles: [TL] },
];
