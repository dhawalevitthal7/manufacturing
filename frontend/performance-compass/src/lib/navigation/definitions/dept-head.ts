import {
  ClipboardCheck,
  ClipboardList,
  LayoutDashboard,
  LineChart,
  ListChecks,
  MessageCircle,
  Network,
  Target,
  TrendingUp,
  Users,
} from "lucide-react";

import type { NavDefinition } from "../nav-definition";

const DH = "DEPT_HEAD" as const;

/** Department Head — “Can See” list. */
export const DEPT_HEAD_NAV: NavDefinition[] = [
  { group: "Department", label: "Department Dashboard", to: "/", icon: LayoutDashboard, roles: [DH] },
  { group: "Department OKRs", label: "Department OKRs", to: "/okrs?level=department", icon: Target, roles: [DH] },
  { group: "Department OKRs", label: "Team OKRs", to: "/okrs?level=team", icon: Target, roles: [DH] },
  { group: "Department OKRs", label: "Employee OKRs", to: "/okrs?level=employee", icon: Target, roles: [DH] },
  { group: "Department execution", label: "Team Progress", to: "/progress", icon: TrendingUp, roles: [DH] },
  { group: "Department execution", label: "Team Check-In Inbox", to: "/reviews?view=inbox", icon: MessageCircle, roles: [DH] },
  { group: "Department execution", label: "Department Reviews", to: "/reviews?view=department", icon: ClipboardCheck, roles: [DH] },
  { group: "Department execution", label: "Team Alignment Dashboard", to: "/alignment", icon: Network, roles: [DH] },
  { group: "Department execution", label: "OKR Creation Approvals", to: "/approvals?type=okr_creation", icon: ListChecks, roles: [DH] },
  { group: "Department execution", label: "Progress Validation Queue", to: "/approvals?type=progress", icon: ListChecks, roles: [DH] },
  { group: "Department execution", label: "Review Queue", to: "/reviews?view=queue", icon: ClipboardList, roles: [DH] },
  { group: "Department analytics", label: "Team Performance Visibility", to: "/teams", icon: Users, roles: [DH] },
  { group: "Department analytics", label: "Team Execution Trends", to: "/progress", icon: LineChart, roles: [DH] },
];
