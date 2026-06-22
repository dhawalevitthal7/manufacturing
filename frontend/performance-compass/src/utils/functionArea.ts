/**
 * Corporate function_area constants — mirrors backend function_area_service.py
 */

import type { SystemRole } from '@/lib/api';
import type { FunctionArea } from '@/types/constellation.types';

export const FUNCTION_AREAS: FunctionArea[] = [
  'OPERATIONS',
  'FINANCE',
  'HR',
  'SALES_MARKETING',
  'PROCUREMENT',
  'TECHNICAL',
  'REGIONS',
];

export const FUNCTION_AREA_LABELS: Record<FunctionArea, string> = {
  OPERATIONS: 'Operations',
  FINANCE: 'Finance',
  HR: 'HR & IR',
  SALES_MARKETING: 'Sales & Marketing',
  PROCUREMENT: 'Procurement & SCM',
  TECHNICAL: 'Technical / Quality / HSE',
  REGIONS: 'Regions',
};

/** One accent color per function for constellation grouping */
export const FUNCTION_AREA_COLORS: Record<FunctionArea, string> = {
  OPERATIONS: '#06b6d4',
  FINANCE: '#22c55e',
  HR: '#a855f7',
  SALES_MARKETING: '#ec4899',
  PROCUREMENT: '#f59e0b',
  TECHNICAL: '#6366f1',
  REGIONS: '#14b8a6',
};

const ROLE_TO_FUNCTION_AREA: Partial<Record<SystemRole, FunctionArea>> = {
  COO: 'OPERATIONS',
  CFO: 'FINANCE',
  CHRO: 'HR',
  HR_HEAD: 'HR',
  CMO: 'SALES_MARKETING',
  CPO: 'PROCUREMENT',
  CSO: 'TECHNICAL',
  CRO: 'REGIONS',
};

const FUNCTIONAL_HEAD_ROLES: SystemRole[] = [
  'COO',
  'CFO',
  'CHRO',
  'HR_HEAD',
  'CMO',
  'CPO',
  'CSO',
  'CRO',
  'FUNCTIONAL_SUB_HEAD',
];

export function functionAreaForRole(role: SystemRole | string | undefined): FunctionArea | undefined {
  if (!role) return undefined;
  return ROLE_TO_FUNCTION_AREA[role as SystemRole];
}

export function isFunctionalHeadRole(role: SystemRole | string | undefined): boolean {
  if (!role) return false;
  return FUNCTIONAL_HEAD_ROLES.includes(role as SystemRole);
}

export function isCeoRole(role: SystemRole | string | undefined): boolean {
  if (!role) return false;
  const r = role.toUpperCase();
  return r === 'CEO' || r === 'SUPER_ADMIN';
}

export function getFunctionAreaColor(area: FunctionArea | string | undefined): string {
  if (!area) return '#64748b';
  return FUNCTION_AREA_COLORS[area as FunctionArea] ?? '#64748b';
}

export function getFunctionAreaLabel(area: FunctionArea | string | undefined): string {
  if (!area) return 'Unknown';
  return FUNCTION_AREA_LABELS[area as FunctionArea] ?? area;
}
