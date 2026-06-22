import type { NavDefinition } from "../nav-definition";
import { AREA_SALES_MANAGER_NAV } from "./area-sales-manager";
import { CHRO_NAV } from "./chro";
import { COO_NAV } from "./coo";
import { CPO_NAV } from "./cpo";
import { CRO_NAV } from "./cro";
import { CSO_NAV } from "./cso";
import { CEO_NAV } from "./ceo";
import { CFO_NAV } from "./cfo";
import { CMO_NAV } from "./cmo";
import { CTO_NAV } from "./cto";
import { DEPT_HEAD_NAV } from "./dept-head";
import { EMPLOYEE_NAV } from "./employee";
import { FUNCTIONAL_SUB_HEAD_NAV } from "./functional-sub-head";
import { HR_HEAD_NAV } from "./hr-head";
import { MANAGER_NAV } from "./manager";
import { PLANT_HEAD_NAV } from "./plant-head";
import { REGIONAL_HEAD_NAV } from "./regional-head";
import { SUPER_ADMIN_NAV } from "./super-admin";
import { SUPERVISOR_NAV } from "./supervisor";
import { TEAM_LEAD_NAV } from "./team-lead";
import { VP_OPERATIONS_NAV } from "./vp-operations";

/** Full navigation catalog (filtered by role at runtime). */
export const ALL_NAV_DEFINITIONS: NavDefinition[] = [
  ...SUPER_ADMIN_NAV,
  ...CEO_NAV,
  ...COO_NAV,
  ...CRO_NAV,
  ...VP_OPERATIONS_NAV,
  ...REGIONAL_HEAD_NAV,
  ...CFO_NAV,
  ...CMO_NAV,
  ...CTO_NAV,
  ...CPO_NAV,
  ...CSO_NAV,
  ...CHRO_NAV,
  ...FUNCTIONAL_SUB_HEAD_NAV,
  ...AREA_SALES_MANAGER_NAV,
  ...PLANT_HEAD_NAV,
  ...DEPT_HEAD_NAV,
  ...MANAGER_NAV,
  ...TEAM_LEAD_NAV,
  ...SUPERVISOR_NAV,
  ...EMPLOYEE_NAV,
  ...HR_HEAD_NAV,
];
