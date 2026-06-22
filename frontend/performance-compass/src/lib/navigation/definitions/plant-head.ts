import {
  Building2,
  ClipboardCheck,
  Factory,
  GitBranch,
  LayoutDashboard,
  MessageCircle,
  Network,
  Target,
  Users,
  CheckCircle2,
} from "lucide-react";

import type { NavDefinition } from "../nav-definition";

const PH = "PLANT_HEAD" as const;

/** Plant Head — "Can See" list. */
export const PLANT_HEAD_NAV: NavDefinition[] = [
  { group: "Plant", label: "Plant Dashboard", to: "/", icon: LayoutDashboard, roles: [PH] },
  { group: "Plant", label: "Plant Alignment Dashboard", to: "/alignment", icon: Network, roles: [PH] },
  { group: "Plant OKRs", label: "All OKRs", to: "/okrs", icon: Target, roles: [PH] },
  { group: "Plant OKRs", label: "Regional", to: "/okrs?level=region", icon: Network, roles: [PH] },
  { group: "Plant OKRs", label: "Plant", to: "/okrs?level=plant", icon: Factory, roles: [PH] },
  { group: "Plant OKRs", label: "Department", to: "/okrs?level=department", icon: GitBranch, roles: [PH] },
  { group: "Plant OKRs", label: "Team", to: "/okrs?level=team", icon: Users, roles: [PH] },
  { group: "Plant OKRs", label: "Validations (0)", to: "/okrs?view=validations", icon: CheckCircle2, roles: [PH] },
  { group: "Plant execution", label: "Team Check-In Inbox", to: "/reviews?view=inbox", icon: MessageCircle, roles: [PH] },
  { group: "Plant execution", label: "AI Performance Reviews", to: "/reviews?view=reviews", icon: ClipboardCheck, roles: [PH] },
  { group: "Plant execution", label: "Line OKR Approvals", to: "/approvals?type=okr_creation&stage=line", icon: CheckCircle2, roles: [PH] },
  { group: "Plant execution", label: "Line Progress Queue", to: "/approvals?type=progress&stage=line", icon: CheckCircle2, roles: [PH] },
  { group: "Plant analytics", label: "Team Alignment Visibility", to: "/alignment", icon: Network, roles: [PH] },
];
