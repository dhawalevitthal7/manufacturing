import {
  Activity,
  AlertTriangle,
  BarChart3,
  ClipboardCheck,
  ClipboardList,
  LayoutDashboard,
  LineChart,
  ListChecks,
  Network,
  Target,
  TrendingUp,
  Users,
} from "lucide-react";

import type { NavDefinition } from "../nav-definition";

const PH = "PLANT_HEAD" as const;

/** Plant Head — “Can See” list. */
export const PLANT_HEAD_NAV: NavDefinition[] = [
  { group: "Plant", label: "Plant Dashboard", to: "/", icon: LayoutDashboard, roles: [PH] },
  { group: "Plant", label: "Plant Alignment Dashboard", to: "/alignment", icon: Network, roles: [PH] },
  { group: "Plant OKRs", label: "Department OKRs", to: "/okrs?level=department", icon: Target, roles: [PH] },
  { group: "Plant OKRs", label: "Team OKRs", to: "/okrs?level=team", icon: Target, roles: [PH] },
  { group: "Plant execution", label: "Plant Reviews", to: "/reviews?view=plant", icon: ClipboardCheck, roles: [PH] },
  { group: "Plant execution", label: "Shift Visibility", to: "/teams", icon: Activity, roles: [PH] },
  { group: "Plant execution", label: "Department Progress", to: "/progress", icon: TrendingUp, roles: [PH] },
  { group: "Plant execution", label: "Team Progress", to: "/progress", icon: LineChart, roles: [PH] },
  { group: "Plant execution", label: "Plant Escalations", to: "/blockers", icon: AlertTriangle, roles: [PH] },
  { group: "Plant execution", label: "Approval Queue", to: "/approvals", icon: ListChecks, roles: [PH] },
  { group: "Plant execution", label: "Review Queue", to: "/reviews?view=queue", icon: ClipboardList, roles: [PH] },
  { group: "Plant analytics", label: "Plant Analytics", to: "/progress", icon: BarChart3, roles: [PH] },
  { group: "Plant analytics", label: "Team Alignment Visibility", to: "/alignment", icon: Network, roles: [PH] },
  { group: "Plant analytics", label: "Execution Trends", to: "/progress", icon: TrendingUp, roles: [PH] },
];
