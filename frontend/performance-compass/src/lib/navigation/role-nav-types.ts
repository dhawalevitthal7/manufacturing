/**
 * Canonical roles used for sidebar visibility (aligned with enterprise RBAC).
 * Legacy API roles are normalized in normalizeCanonicalRole().
 */
export type CanonicalRole =
  | "SUPER_ADMIN"
  | "CEO"
  | "VP_OPERATIONS"
  | "REGIONAL_HEAD"
  | "CFO"
  | "CMO"
  | "CTO"
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
    case "REGIONAL_HEAD":
      return "REGIONAL_HEAD";
    case "CFO":
      return "CFO";
    case "CMO":
      return "CMO";
    case "CTO":
      return "CTO";
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
