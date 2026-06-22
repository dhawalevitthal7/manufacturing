import { ListChecks, Network, Target } from "lucide-react";

import type { NavDefinition } from "../nav-definition";

const FUNCTIONAL_SUB_HEAD = "FUNCTIONAL_SUB_HEAD" as const;

/** Corporate sub-heads under a functional vertical. */
export const FUNCTIONAL_SUB_HEAD_NAV: NavDefinition[] = [
  { group: "Functional vertical", label: "Vertical OKRs", to: "/okrs?level=vertical", icon: Target, roles: [FUNCTIONAL_SUB_HEAD] },
  { group: "Functional vertical", label: "Department OKRs", to: "/okrs?level=department", icon: Target, roles: [FUNCTIONAL_SUB_HEAD] },
  { group: "Functional vertical", label: "Alignment Dashboard", to: "/alignment", icon: Network, roles: [FUNCTIONAL_SUB_HEAD] },
  { group: "Functional vertical", label: "Approval Queue", to: "/approvals", icon: ListChecks, roles: [FUNCTIONAL_SUB_HEAD] },
];
