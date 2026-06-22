/**
 * Canonical roles used for sidebar visibility (aligned with enterprise RBAC).
 * Legacy API roles are normalized in normalizeCanonicalRole().
 */
export type CanonicalRole =
  | "SUPER_ADMIN"
  | "CEO"
  | "VP_OPERATIONS"
  | "COO"
  | "CRO"
  | "REGIONAL_HEAD"
  | "CFO"
  | "CMO"
  | "CTO"
  | "CPO"
  | "CSO"
  | "CHRO"
  | "FUNCTIONAL_SUB_HEAD"
  | "AREA_SALES_MANAGER"
  | "PLANT_HEAD"
  | "DEPT_HEAD"
  | "MANAGER"
  | "TEAM_LEAD"
  | "SUPERVISOR"
  | "EMPLOYEE"
  | "HR_HEAD";

/** Maps API / legacy role strings to the canonical role used for navigation. */
export function normalizeCanonicalRole(systemRole: string): CanonicalRole {
  switch (systemRole) {
    case "SUPER_ADMIN":
      return "SUPER_ADMIN";
    case "CEO":
      return "CEO";
    case "VP_OPERATIONS":
      return "VP_OPERATIONS";
    case "COO":
      return "COO";
    case "CRO":
      return "CRO";
    case "REGIONAL_HEAD":
      return "REGIONAL_HEAD";
    case "CFO":
      return "CFO";
    case "CMO":
      return "CMO";
    case "CTO":
      return "CTO";
    case "CPO":
      return "CPO";
    case "CSO":
      return "CSO";
    case "CHRO":
      return "CHRO";
    case "FUNCTIONAL_SUB_HEAD":
      return "FUNCTIONAL_SUB_HEAD";
    case "AREA_SALES_MANAGER":
      return "AREA_SALES_MANAGER";
    case "PLANT_HEAD":
    case "PLANT_MANAGER":
      return "PLANT_HEAD";
    case "DEPT_HEAD":
      return "DEPT_HEAD";
    case "MANAGER":
      return "MANAGER";
    case "TEAM_LEAD":
      return "TEAM_LEAD";
    case "SUPERVISOR":
      return "SUPERVISOR";
    case "EMPLOYEE":
      return "EMPLOYEE";
    case "HR_HEAD":
    case "HR_ADMIN":
      return "HR_HEAD";
    default:
      return "EMPLOYEE";
  }
}
