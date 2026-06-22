import type { ConstellationNode, OKRLevel } from '@/types/constellation.types';
import { formatTeamDisplayName } from '@/utils/orbitalLayout';
import { constellationTheme } from '../theme/constellationTheme';

const NEXT_LEVEL: Partial<Record<OKRLevel, OKRLevel>> = {
  region: 'plant',
  plant: 'department',
  department: 'team',
  team: 'employee',
};

function normalizeLevel(level: string): OKRLevel {
  const l = (level || '').toLowerCase();
  if (l === 'individual' || l === 'employee') return 'employee';
  if (
    l === 'organization' ||
    l === 'region' ||
    l === 'plant' ||
    l === 'department' ||
    l === 'team'
  ) {
    return l;
  }
  return 'employee';
}

export interface MoonData {
  id: string;
  name: string;
  progress: number;
  health: string;
}

function matchesPlanet(node: ConstellationNode, moon: ConstellationNode, orbitChildLevel: OKRLevel): boolean {
  switch (orbitChildLevel) {
    case 'region':
      return !!moon.region && (moon.region === node.region || node.id.includes(moon.region));
    case 'plant':
      return !!moon.plant && (moon.plant === node.plant || node.id.includes(moon.plant));
    case 'department':
      return (
        !!moon.department &&
        (moon.department === node.department || node.id.includes(moon.department))
      );
    case 'team':
      return !!moon.team && (moon.team === node.team || node.id.includes(moon.team));
    default:
      return false;
  }
}

function moonDisplayName(moon: ConstellationNode): string {
  if (moon.owner_name) return moon.owner_name;
  if (moon.entity_name) return moon.entity_name;
  if (moon.team_name) return formatTeamDisplayName(moon.team_name);
  const obj = moon.objective || 'OKR';
  return obj.length > 14 ? `${obj.slice(0, 12)}…` : obj;
}

/** Collect child-level nodes for a planet from the raw payload (no API calls). */
export function collectMoonsForPlanet(
  planetNode: ConstellationNode,
  allNodes: ConstellationNode[],
  orbitChildLevel: OKRLevel,
): MoonData[] {
  const moonLevel = NEXT_LEVEL[orbitChildLevel];
  if (!moonLevel) return [];

  const moons: MoonData[] = [];
  for (const n of allNodes) {
    if (normalizeLevel(n.level) !== moonLevel) continue;
    if (!matchesPlanet(planetNode, n, orbitChildLevel)) continue;
    moons.push({
      id: n.id,
      name: moonDisplayName(n),
      progress: n.final_progress ?? n.progress ?? 0,
      health: n.alignment_health,
    });
    if (moons.length >= constellationTheme.moon.maxPerPlanet) break;
  }
  return moons;
}
