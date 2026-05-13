import type { NavDefinition } from "../nav-definition";
import { CEO_NAV } from "./ceo";
import { DEPT_HEAD_NAV } from "./dept-head";
import { EMPLOYEE_NAV } from "./employee";
import { HR_HEAD_NAV } from "./hr-head";
import { MANAGER_NAV } from "./manager";
import { PLANT_HEAD_NAV } from "./plant-head";
import { SUPER_ADMIN_NAV } from "./super-admin";
import { SUPERVISOR_NAV } from "./supervisor";
import { TEAM_LEAD_NAV } from "./team-lead";
import { VP_OPERATIONS_NAV } from "./vp-operations";

/** Full navigation catalog (filtered by role at runtime). */
export const ALL_NAV_DEFINITIONS: NavDefinition[] = [
  ...SUPER_ADMIN_NAV,
  ...CEO_NAV,
  ...VP_OPERATIONS_NAV,
  ...PLANT_HEAD_NAV,
  ...DEPT_HEAD_NAV,
  ...MANAGER_NAV,
  ...TEAM_LEAD_NAV,
  ...SUPERVISOR_NAV,
  ...EMPLOYEE_NAV,
  ...HR_HEAD_NAV,
];
