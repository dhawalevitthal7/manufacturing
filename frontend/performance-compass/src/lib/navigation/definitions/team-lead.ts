import {
  CheckCircle2,
  Factory,
  GitBranch,
  LayoutDashboard,
  MessageCircle,
  Network,
  Target,
  TrendingUp,
  Users,
  Lightbulb,
} from "lucide-react";

import type { NavDefinition } from "../nav-definition";

const TL = "TEAM_LEAD" as const;

/** Team Lead — “Can See” list. */
export const TEAM_LEAD_NAV: NavDefinition[] = [
  { group: "Team lead", label: "Team Execution Dashboard", to: "/", icon: LayoutDashboard, roles: [TL] },
  { group: "Team lead", label: "Assigned Team Members", to: "/employees", icon: Users, roles: [TL] },
  { group: "Team OKRs", label: "All OKRs", to: "/okrs", icon: Target, roles: [TL] },
  { group: "Team OKRs", label: "Plant", to: "/okrs?level=plant", icon: Factory, roles: [TL] },
  { group: "Team OKRs", label: "Department", to: "/okrs?level=department", icon: GitBranch, roles: [TL] },
  { group: "Team OKRs", label: "Team", to: "/okrs?level=team", icon: Users, roles: [TL] },
  { group: "Team OKRs", label: "Validations (0)", to: "/okrs?view=validations", icon: CheckCircle2, roles: [TL] },
  { group: "Team lead", label: "OKR Creation Approvals", to: "/approvals?type=okr_creation", icon: CheckCircle2, roles: [TL] },
  { group: "Team lead", label: "Progress Validation Queue", to: "/approvals?type=progress", icon: CheckCircle2, roles: [TL] },
  { group: "Team lead", label: "Team Check-In Inbox", to: "/reviews?view=inbox", icon: MessageCircle, roles: [TL] },
  { group: "Team lead", label: "Team Progress", to: "/progress", icon: TrendingUp, roles: [TL] },
  { group: "Team lead", label: "Team Alignment", to: "/alignment", icon: Network, roles: [TL] },
  { group: "Team lead", label: "Insights", to: "/insights", icon: Lightbulb, roles: [TL] },
];
