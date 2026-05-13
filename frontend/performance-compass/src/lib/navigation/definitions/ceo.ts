import {
  Activity,
  AlertTriangle,
  BarChart3,
  ClipboardList,
  Globe2,
  Goal,
  LayoutDashboard,
  LineChart,
  ListChecks,
  Map,
  Network,
  PieChart,
  Sparkles,
  Target,
  TrendingUp,
} from "lucide-react";

import type { NavDefinition } from "../nav-definition";

const CEO = "CEO" as const;

/** CEO / Executive Leadership — “Can See” list. */
export const CEO_NAV: NavDefinition[] = [
  { group: "Executive", label: "Executive Dashboard", to: "/", icon: LayoutDashboard, roles: [CEO] },
  { group: "Executive", label: "Organization Alignment Dashboard", to: "/alignment", icon: Network, roles: [CEO] },
  { group: "Executive OKRs", label: "Organization OKRs", to: "/okrs?level=organization", icon: Target, roles: [CEO] },
  { group: "Executive OKRs", label: "Plant OKRs", to: "/okrs?level=plant", icon: Target, roles: [CEO] },
  { group: "Executive OKRs", label: "Department OKRs", to: "/okrs?level=department", icon: Target, roles: [CEO] },
  { group: "Strategy & alignment", label: "Strategic Alignment Map", to: "/alignment", icon: Map, roles: [CEO] },
  { group: "Strategy & alignment", label: "Cross-Plant Visibility", to: "/alignment", icon: Globe2, roles: [CEO] },
  { group: "Strategy & alignment", label: "Department Comparison", to: "/alignment", icon: BarChart3, roles: [CEO] },
  { group: "Insights", label: "Executive Review Analytics", to: "/reviews?view=executive", icon: PieChart, roles: [CEO] },
  { group: "Insights", label: "AI Strategic Insights", to: "/alignment", icon: Sparkles, roles: [CEO] },
  { group: "Insights", label: "Organizational Progress Heatmaps", to: "/alignment", icon: Goal, roles: [CEO] },
  { group: "Insights", label: "Escalation Insights", to: "/blockers", icon: AlertTriangle, roles: [CEO] },
  { group: "Insights", label: "Leadership Review Summaries", to: "/reviews?view=summaries", icon: ClipboardList, roles: [CEO] },
  { group: "Execution overview", label: "Organization Activity Feed", to: "/progress", icon: Activity, roles: [CEO] },
  { group: "Execution overview", label: "Approval Overview", to: "/approvals", icon: ListChecks, roles: [CEO] },
  { group: "Risk & gaps", label: "High-Risk Teams", to: "/alignment", icon: AlertTriangle, roles: [CEO] },
  { group: "Risk & gaps", label: "Delayed Objectives", to: "/okrs", icon: TrendingUp, roles: [CEO] },
  { group: "Risk & gaps", label: "Alignment Gaps", to: "/alignment", icon: Network, roles: [CEO] },
];
