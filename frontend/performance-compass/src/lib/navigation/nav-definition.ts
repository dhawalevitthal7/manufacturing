import type { LucideIcon } from "lucide-react";

import type { CanonicalRole } from "./role-nav-types";

/** One sidebar row: label + route + icon + which canonical roles may see it. */
export interface NavDefinition {
  group: string;
  label: string;
  to: string;
  icon: LucideIcon;
  roles: readonly CanonicalRole[];
}
