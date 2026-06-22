import { ListChecks, Target, Users } from "lucide-react";

import type { NavDefinition } from "../nav-definition";

const AREA_SALES_MANAGER = "AREA_SALES_MANAGER" as const;

/** Area sales manager — team-level OKR creation (mirrors manager nav subset). */
export const AREA_SALES_MANAGER_NAV: NavDefinition[] = [
  { group: "Sales team", label: "Team OKRs", to: "/okrs?level=team", icon: Users, roles: [AREA_SALES_MANAGER] },
  { group: "Sales team", label: "Individual OKRs", to: "/okrs?level=individual", icon: Target, roles: [AREA_SALES_MANAGER] },
  { group: "Sales team", label: "Approval Queue", to: "/approvals", icon: ListChecks, roles: [AREA_SALES_MANAGER] },
];
