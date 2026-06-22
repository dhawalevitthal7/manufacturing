import type { Objective } from "@/lib/api";

type AuthUser = { id: string; system_role: string } | null | undefined;

/** Whether the user may submit KR progress on this OKR (mirrors backend rules). */
export function canSubmitOkrProgress(okr: Objective, user: AuthUser): boolean {
  if (!user?.id) return false;
  if (okr.owner_id !== user.id) return false;

  const level = (okr.level || "").toUpperCase();
  const role = user.system_role;

  if (level === "INDIVIDUAL") {
    return ["EMPLOYEE", "TEAM_LEAD", "SUPERVISOR", "MANAGER"].includes(role);
  }
  if (level === "TEAM") {
    return ["TEAM_LEAD", "SUPERVISOR"].includes(role);
  }
  if (level === "DEPARTMENT") {
    return ["DEPT_HEAD", "PLANT_HEAD", "MANAGER"].includes(role);
  }
  if (level === "PLANT") {
    return ["PLANT_HEAD", "VP_OPERATIONS", "VP_MANUFACTURING", "CEO"].includes(role);
  }
  if (level === "REGION") {
    return ["REGIONAL_HEAD", "VP_OPERATIONS", "VP_MANUFACTURING", "CEO"].includes(role);
  }
  if (level === "ORGANIZATION") {
    return ["CEO", "CFO", "CMO", "CTO"].includes(role);
  }
  return false;
}

/** Whether the user may add KRs / manage OKR structure (draft creators). */
export function canManageOkrStructure(
  okr: Objective,
  user: AuthUser,
  canCreateAtLevel: boolean,
): boolean {
  if (!user?.id || !canCreateAtLevel) return false;
  if (okr.owner_id === user.id) return true;
  if (okr.assigned_by_id === user.id) return true;
  return ["MANAGER", "DEPT_HEAD", "PLANT_HEAD", "TEAM_LEAD", "CEO", "SUPER_ADMIN"].includes(
    user.system_role,
  );
}

/** Functional (dotted-line) parent is only valid for department-level OKRs. */
export function canSetFunctionalParent(level: string, teamId?: string): boolean {
  return level.toUpperCase() === "DEPARTMENT" && !teamId;
}

/** Roles that may validate KR progress submissions (matches backend pending-validations). */
const PROGRESS_VALIDATOR_ROLES = [
  "SUPER_ADMIN",
  "CEO",
  "COO",
  "CRO",
  "VP_OPERATIONS",
  "VP_MANUFACTURING",
  "REGIONAL_HEAD",
  "PLANT_HEAD",
  "PLANT_MANAGER",
  "DEPT_HEAD",
  "MANAGER",
  "TEAM_LEAD",
  "SUPERVISOR",
] as const;

export function canValidateOkrProgress(user: AuthUser): boolean {
  if (!user?.system_role) return false;
  return PROGRESS_VALIDATOR_ROLES.includes(
    user.system_role as (typeof PROGRESS_VALIDATOR_ROLES)[number],
  );
}
