import {
  AlertTriangle,
  BarChart3,
  ClipboardCheck,
  LineChart,
  ListChecks,
  Network,
  PieChart,
  UserCircle2,
  Users,
  Workflow,
} from "lucide-react";

import type { NavDefinition } from "../nav-definition";

const HR = "HR_HEAD" as const;

/** HR Head / HR Admin — “Can See” list. */
export const HR_HEAD_NAV: NavDefinition[] = [
  { group: "HR & reviews", label: "Review Dashboard", to: "/reviews?view=dashboard", icon: ClipboardCheck, roles: [HR] },
  { group: "HR & reviews", label: "Review Analytics", to: "/reviews?view=analytics", icon: BarChart3, roles: [HR] },
  { group: "HR & reviews", label: "Calibration Dashboard", to: "/reviews?view=calibration", icon: PieChart, roles: [HR] },
  { group: "HR & reviews", label: "Employee Review Visibility", to: "/reviews?view=employees", icon: UserCircle2, roles: [HR] },
  { group: "HR & reviews", label: "Organization Review Trends", to: "/reviews?view=trends", icon: LineChart, roles: [HR] },
  { group: "HR & reviews", label: "Performance Distribution", to: "/reviews?view=distribution", icon: PieChart, roles: [HR] },
  { group: "HR & reviews", label: "Alignment Analytics", to: "/alignment", icon: Network, roles: [HR] },
  { group: "HR & reviews", label: "Review Completion Status", to: "/reviews?view=completion", icon: ListChecks, roles: [HR] },
  { group: "HR & reviews", label: "Escalation Analytics", to: "/blockers", icon: AlertTriangle, roles: [HR] },
  { group: "HR & reviews", label: "Employee Directory", to: "/employees", icon: Users, roles: [HR] },
  { group: "HR & reviews", label: "Functional Approvals", to: "/approvals?stage=functional", icon: ListChecks, roles: [HR] },
  { group: "HR & reviews", label: "Review Workflows", to: "/reviews?view=workflows", icon: Workflow, roles: [HR] },
];
