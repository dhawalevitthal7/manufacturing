/** Which hierarchy fields appear on employee onboarding for each system role. */
export type OnboardScopeField = "region" | "plant" | "department" | "team";

const SCOPE_BY_ROLE: Record<string, OnboardScopeField[]> = {
  REGIONAL_HEAD: ["region"],
  PLANT_HEAD: ["region", "plant"],
  DEPT_HEAD: ["region", "plant", "department"],
  MANAGER: ["region", "plant", "department"],
  SUPERVISOR: ["region", "plant", "department"],
  TEAM_LEAD: ["region", "plant", "department", "team"],
  EMPLOYEE: ["region", "plant", "department", "team"],
};

export function onboardScopeFieldsForRole(role: string): OnboardScopeField[] {
  return SCOPE_BY_ROLE[role] ?? [];
}

export function onboardScopeNeedsField(role: string, field: OnboardScopeField): boolean {
  return onboardScopeFieldsForRole(role).includes(field);
}

/** Roles that require a selection (not "none") for the deepest visible scope field. */
export function onboardRequiredFields(
  role: string,
  hasRegions: boolean,
): OnboardScopeField[] {
  const fields = onboardScopeFieldsForRole(role).filter(
    (f) => f !== "region" || hasRegions,
  );
  if (fields.length === 0) return [];
  return [fields[fields.length - 1]!];
}
