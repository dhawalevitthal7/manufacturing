/**
 * Resolve current orbit focus from drill-down stack + initial scope.
 */

import type { ConstellationNode, OKRLevel, RoleScopeConfig } from '@/types/constellation.types';
import { childLevelOf } from '@/utils/constellationExpansion';
import { normalizeOkrLevel } from '@/utils/orbitalLayout';

export interface OrbitFocus {
  scopeLevel: OKRLevel;
  scopeId: string | null;
  label: string;
  childLevel: OKRLevel;
}

export function resolveOrbitFocus(
  drillDownStack: Array<{ scopeLevel: string; scopeId: string; label: string }>,
  scopeConfig: RoleScopeConfig,
  scopeId: string | null,
  organizationName?: string,
  scopeEntityName?: string,
): OrbitFocus {
  if (drillDownStack.length > 0) {
    const top = drillDownStack[drillDownStack.length - 1];
    const level = normalizeOkrLevel(top.scopeLevel);
    const child = childLevelOf(level) ?? normalizeOkrLevel(scopeConfig.childLevel);
    return {
      scopeLevel: level,
      scopeId: top.scopeId,
      label: top.label,
      childLevel: child,
    };
  }

  return {
    scopeLevel: normalizeOkrLevel(scopeConfig.scopeLevel),
    scopeId,
    label:
      scopeEntityName ||
      (scopeConfig.scopeLevel === 'organization'
        ? organizationName || 'Organization'
        : scopeConfig.centerLabel.replace(' OKR', '')),
    childLevel: normalizeOkrLevel(scopeConfig.childLevel),
  };
}

/** Whether double-clicking this planet should drill deeper. */
export function resolveDrillTarget(
  node: ConstellationNode,
): { scopeLevel: OKRLevel; scopeId: string; label: string } | null {
  const level = normalizeOkrLevel(node.level);
  const child = childLevelOf(level);
  if (!child) return null;

  const label =
    node.entity_name ||
    node.department_name ||
    node.plant_name ||
    node.region_name ||
    node.team_name ||
    node.objective;

  switch (level) {
    case 'region':
      if (node.region) return { scopeLevel: 'region', scopeId: node.region, label };
      break;
    case 'plant':
      if (node.plant) return { scopeLevel: 'plant', scopeId: node.plant, label };
      break;
    case 'department':
      if (node.department) return { scopeLevel: 'department', scopeId: node.department, label };
      break;
    case 'team':
      if (node.team) return { scopeLevel: 'team', scopeId: node.team, label };
      break;
    default:
      break;
  }

  const synth = node.id.match(/^orbit-(region|plant|department|team)-(.+)$/);
  if (synth) {
    return { scopeLevel: synth[1] as OKRLevel, scopeId: synth[2], label };
  }
  return null;
}
