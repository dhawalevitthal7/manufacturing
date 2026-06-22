/**
 * Role-Based Scope Configuration for Constellation
 * ==================================================
 * Maps user roles to what they should see in the constellation view.
 *
 * CEO/Admin       → Org center + Regions orbiting
 * Regional Head   → Region center + Plants orbiting
 * Plant Head      → Plant center + Departments orbiting
 * Dept Head / Manager → Department center + Teams orbiting
 * Team Lead        → Team center + Employees orbiting
 * Employee        → Their OKRs only
 */

import { RoleScopeConfig, DisplayMode } from '@/types/constellation.types';
import type { SystemRole } from '@/lib/api';

/**
 * Map the backend `user_scope` string to a display config.
 * The backend returns: ORGANIZATION | REGION | PLANT | DEPARTMENT | TEAM | EMPLOYEE
 */
const SCOPE_CONFIGS: Record<string, RoleScopeConfig> = {
  ORGANIZATION: {
    title: 'Organization Alignment',
    subtitle: 'Regions aligned to the Organization — closer to center = higher progress',
    centerLabel: 'Organization OKR',
    orbitLabel: 'Regions',
    scopeLevel: 'organization',
    childLevel: 'region',
    icon: '🌍',
  },
  REGION: {
    title: 'Region Alignment',
    subtitle: 'Plants aligned to your Region — closer to center = higher progress',
    centerLabel: 'Region OKR',
    orbitLabel: 'Plants',
    scopeLevel: 'region',
    childLevel: 'plant',
    icon: '🗺️',
  },
  PLANT: {
    title: 'Plant Alignment',
    subtitle: 'Departments aligned to your Plant — closer to center = higher progress',
    centerLabel: 'Plant OKR',
    orbitLabel: 'Departments',
    scopeLevel: 'plant',
    childLevel: 'department',
    icon: '🏭',
  },
  DEPARTMENT: {
    title: 'Department Alignment',
    subtitle: 'Teams aligned to your Department — closer to center = higher progress',
    centerLabel: 'Department OKR',
    orbitLabel: 'Teams',
    scopeLevel: 'department',
    childLevel: 'team',
    icon: '🏢',
  },
  TEAM: {
    title: 'Team Alignment',
    subtitle: 'Employees aligned to your Team — closer to center = higher progress',
    centerLabel: 'Team OKR',
    orbitLabel: 'Employees',
    scopeLevel: 'team',
    childLevel: 'employee',
    icon: '👥',
  },
  EMPLOYEE: {
    title: 'My OKR Alignment',
    subtitle: 'Your personal OKR alignment map',
    centerLabel: 'My OKRs',
    orbitLabel: 'Key Results',
    scopeLevel: 'employee',
    childLevel: 'employee',
    icon: '👤',
  },
  FUNCTIONAL: {
    title: 'Function Alignment',
    subtitle: 'Your vertical OKRs and plant departments aligned across the network',
    centerLabel: 'Function OKR',
    orbitLabel: 'Aligned departments',
    scopeLevel: 'organization',
    childLevel: 'department',
    icon: '🏛️',
  },
};

/**
 * Get scope config from the backend's user_scope string
 */
export function getScopeConfigFromUserScope(userScope: string | undefined): RoleScopeConfig {
  if (!userScope) return SCOPE_CONFIGS.ORGANIZATION;
  return SCOPE_CONFIGS[userScope.toUpperCase()] || SCOPE_CONFIGS.ORGANIZATION;
}

/**
 * Get scope config from the frontend user's system_role
 * This is a fallback when metadata isn't available yet.
 */
export function getScopeConfigFromRole(role: SystemRole | string | undefined): RoleScopeConfig {
  if (!role) return SCOPE_CONFIGS.ORGANIZATION;

  const normalized = role.toUpperCase();

  switch (normalized) {
    case 'CEO':
    case 'SUPER_ADMIN':
      return SCOPE_CONFIGS.ORGANIZATION;
    case 'REGIONAL_HEAD':
    case 'VP_OPERATIONS':
      return SCOPE_CONFIGS.REGION;
    case 'PLANT_HEAD':
    case 'PLANT_MANAGER':
    case 'VP_MANUFACTURING':
      return SCOPE_CONFIGS.PLANT;
    case 'DEPT_HEAD':
    case 'MANAGER':
    case 'CFO':
    case 'CMO':
    case 'CTO':
    case 'COO':
    case 'CPO':
    case 'CSO':
    case 'CHRO':
    case 'CRO':
    case 'FUNCTIONAL_SUB_HEAD':
      return SCOPE_CONFIGS.FUNCTIONAL;
    case 'HR_HEAD':
      return SCOPE_CONFIGS.DEPARTMENT;
    case 'TEAM_LEAD':
    case 'SUPERVISOR':
      return SCOPE_CONFIGS.TEAM;
    case 'EMPLOYEE':
    default:
      return SCOPE_CONFIGS.EMPLOYEE;
  }
}

/**
 * Get the relevant view mode options for a given scope.
 * Higher-level roles get more view options.
 */
/** Default visualization mode per role scope */
export function getDefaultDisplayMode(userScope: string | undefined): DisplayMode {
  const scope = (userScope || 'ORGANIZATION').toUpperCase();
  if (scope === 'EMPLOYEE') return 'line-of-sight';
  if (scope === 'FUNCTIONAL') return 'orbit';
  if (scope === 'ORGANIZATION' || scope === 'REGION' || scope === 'PLANT' || scope === 'DEPARTMENT') {
    return 'orbit';
  }
  return 'graph';
}

export function getViewModesForScope(userScope: string | undefined): string[] {
  const scope = (userScope || 'ORGANIZATION').toUpperCase();

  switch (scope) {
    case 'ORGANIZATION':
      return ['galaxy', 'strategic', 'risk', 'plant', 'department'];
    case 'REGION':
      return ['galaxy', 'strategic', 'risk', 'plant', 'department'];
    case 'PLANT':
      return ['galaxy', 'strategic', 'risk', 'department'];
    case 'DEPARTMENT':
      return ['galaxy', 'strategic', 'risk'];
    case 'TEAM':
    case 'EMPLOYEE':
      return ['galaxy', 'risk'];
    case 'FUNCTIONAL':
      return ['galaxy', 'strategic', 'risk', 'department'];
    default:
      return ['galaxy', 'strategic', 'risk'];
  }
}
