import {
  Activity,
  AlertTriangle,
  BarChart3,
  ClipboardList,
  LayoutDashboard,
  ListChecks,
  Network,
  TrendingUp,
} from "lucide-react";

import type { NavDefinition } from "../nav-definition";

const S = "SUPERVISOR" as const;

/** Supervisor / Shift Incharge — “Can See” list. */
export const SUPERVISOR_NAV: NavDefinition[] = [
  { group: "Shift", label: "Shift Dashboard", to: "/", icon: LayoutDashboard, roles: [S] },
  { group: "Shift", label: "Employee Execution Updates", to: "/progress", icon: Activity, roles: [S] },
  { group: "Shift", label: "Pending Validations", to: "/approvals", icon: ListChecks, roles: [S] },
  { group: "Shift", label: "Shift Alignment", to: "/alignment", icon: Network, roles: [S] },
  { group: "Shift", label: "Team Progress", to: "/progress", icon: TrendingUp, roles: [S] },
  { group: "Shift", label: "Operational Escalations", to: "/blockers", icon: AlertTriangle, roles: [S] },
  { group: "Shift", label: "Shift Review Queue", to: "/reviews?view=queue", icon: ClipboardList, roles: [S] },
  { group: "Shift", label: "Shift Analytics", to: "/progress", icon: BarChart3, roles: [S] },
];
