/**
 * Strict two-level solar-system layout: center + planets + moons only.
 * Collision-free spacing with band radius adjustment.
 */

import type { ConstellationNode, OKRLevel, RoleScopeConfig } from '@/types/constellation.types';
import {
  buildScopedOrbitalLayout,
  normalizeOkrLevel,
  orbitRadiusForProgress,
  progressToOrbitBand,
  type OrbitBand,
} from '@/utils/orbitalLayout';
import { constellationTheme } from '../theme/constellationTheme';
import { collectMoonsForPlanet, type MoonData } from '../draw/moonUtils';
import type { OrbitFocus } from './orbitFocus';
import { planetRadiusForNode } from '../draw/drawPlanetNode';

const LABEL_WIDTH = 72;
const MAX_VISIBLE_MOONS = 5;
const MOON_ORBIT_OFFSET = 22;

export interface PlacedMoon {
  data: MoonData;
  angle: number;
  isBadge: boolean;
}

export interface PlacedPlanet {
  node: ConstellationNode;
  x: number;
  y: number;
  angle: number;
  orbitRadius: number;
  visualRadius: number;
  band: OrbitBand;
  moons: PlacedMoon[];
  moonOrbitRadius: number;
  moonBaseAngle: number;
  totalMoonCount: number;
  planetIndex: number;
}

export interface TwoLevelLayout {
  center: ConstellationNode;
  planets: PlacedPlanet[];
}

/**
 * Ensure different progress bands sit on separated rings.
 * Planets sharing the same band (and thus the same progress radius) stay
 * on one circle — equal progress always means equal distance from center.
 */
function enforceBandSeparation(
  placed: Array<{ band: OrbitBand; visualR: number }>,
  radii: number[],
): void {
  if (placed.length <= 1) return;

  const minDelta = Math.max(...placed.map((p) => p.visualR)) * 2.5;
  const bandGroups = new Map<OrbitBand, number[]>();

  for (let i = 0; i < placed.length; i++) {
    const b = placed[i].band;
    if (!bandGroups.has(b)) bandGroups.set(b, []);
    bandGroups.get(b)!.push(i);
  }

  const bandMeans = [...bandGroups.entries()]
    .map(([band, indices]) => ({
      band,
      indices,
      mean: indices.reduce((s, i) => s + radii[i], 0) / indices.length,
    }))
    .sort((a, b) => a.mean - b.mean);

  for (let i = 1; i < bandMeans.length; i++) {
    const prev = bandMeans[i - 1];
    const cur = bandMeans[i];
    if (cur.mean - prev.mean >= minDelta) continue;

    const push = prev.mean + minDelta - cur.mean;
    for (const idx of cur.indices) {
      radii[idx] += push;
    }
    cur.mean += push;
  }
}

function adjustRadiiForSpacing(
  placed: Array<{ angle: number; r: number; visualR: number; band: OrbitBand }>,
): number[] {
  const n = placed.length;
  if (n <= 1) return placed.map((p) => p.r);

  const radii = placed.map((p) => p.r);

  const byBand = new Map<OrbitBand, number[]>();
  for (let i = 0; i < n; i++) {
    const b = placed[i].band;
    if (!byBand.has(b)) byBand.set(b, []);
    byBand.get(b)!.push(i);
  }

  for (const indices of byBand.values()) {
    if (indices.length < 2) continue;
    const avgR = indices.reduce((s, i) => s + radii[i], 0) / indices.length;
    const arcSep = (2 * Math.PI) / n;
    const vr = placed[indices[0]].visualR;
    const needChord = vr * 2 + LABEL_WIDTH;
    const needAngle = 2 * Math.asin(Math.min(1, needChord / (2 * avgR)));

    if (arcSep < needAngle) {
      const scale = needAngle / arcSep;
      const push = avgR * (scale - 1) * 0.85;
      for (const i of indices) {
        radii[i] += push;
      }
    }
  }

  enforceBandSeparation(placed, radii);

  // Normalize: planets with identical progress must share the exact same radius
  const byProgress = new Map<number, number[]>();
  for (let i = 0; i < n; i++) {
    const key = Math.round(placed[i].r * 100) / 100;
    if (!byProgress.has(key)) byProgress.set(key, []);
    byProgress.get(key)!.push(i);
  }
  for (const indices of byProgress.values()) {
    if (indices.length < 2) continue;
    const mean = indices.reduce((s, i) => s + radii[i], 0) / indices.length;
    for (const i of indices) radii[i] = mean;
  }

  return radii;
}

function buildMoons(
  planetNode: ConstellationNode,
  planetIndex: number,
  planetVisualR: number,
  childLevel: OKRLevel,
  allNodes: ConstellationNode[],
): {
  moons: PlacedMoon[];
  moonOrbitRadius: number;
  moonBaseAngle: number;
  totalMoonCount: number;
} {
  const all = collectMoonsForPlanet(planetNode, allNodes, childLevel);
  const totalMoonCount = all.length;
  const moonOrbitRadius = planetVisualR + MOON_ORBIT_OFFSET;
  const moonBaseAngle = planetIndex * 0.7;

  const slotCount = Math.min(totalMoonCount, MAX_VISIBLE_MOONS);
  const showBadge = totalMoonCount > MAX_VISIBLE_MOONS;
  const realCount = showBadge ? MAX_VISIBLE_MOONS - 1 : slotCount;
  const visible = all.slice(0, realCount);

  const moons: PlacedMoon[] = visible.map((data, i) => ({
    data,
    angle: (2 * Math.PI * i) / Math.max(realCount, 1),
    isBadge: false,
  }));

  if (showBadge) {
    moons.push({
      data: {
        id: `badge-${planetNode.id}`,
        name: `+${totalMoonCount - realCount}`,
        progress: 0,
        health: 'healthy',
      },
      angle: (2 * Math.PI * realCount) / Math.max(realCount + 1, 1),
      isBadge: true,
    });
  }

  return { moons, moonOrbitRadius, moonBaseAngle, totalMoonCount };
}

export function buildTwoLevelLayout(
  nodes: ConstellationNode[],
  focus: OrbitFocus,
  organizationName?: string,
): TwoLevelLayout {
  const scopeConfig: RoleScopeConfig = {
    title: '',
    subtitle: '',
    centerLabel: `${focus.label} OKR`,
    orbitLabel: focus.childLevel,
    scopeLevel: focus.scopeLevel,
    childLevel: focus.childLevel,
    icon: '',
  };

  const { center, orbit } = buildScopedOrbitalLayout(nodes, 0, 0, {
    scopeConfig,
    scopeId: focus.scopeId,
    organizationName,
    scopeEntityName: focus.label,
  });

  if (!center) {
    throw new Error('Two-level layout requires a center node');
  }

  const count = Math.max(orbit.length, 1);
  const draft = orbit.map((p, i) => {
    const progress = p.node.final_progress ?? p.node.progress ?? 0;
    const visualR = planetRadiusForNode(p.node);
    const angle = (2 * Math.PI * i) / count - Math.PI / 2;
    return {
      angle,
      r: orbitRadiusForProgress(progress),
      visualR,
      band: progressToOrbitBand(progress),
      node: p.node,
    };
  });

  const adjustedRadii = adjustRadiiForSpacing(draft);

  const planets: PlacedPlanet[] = draft.map((d, i) => {
    const r = adjustedRadii[i];
    const x = r * Math.cos(d.angle);
    const y = r * Math.sin(d.angle);
    const moonPack = buildMoons(d.node, i, d.visualR, focus.childLevel, nodes);

    return {
      node: d.node,
      x,
      y,
      angle: d.angle,
      orbitRadius: r,
      visualRadius: d.visualR,
      band: d.band,
      planetIndex: i,
      ...moonPack,
    };
  });

  return { center, planets };
}

export function interpolateLayout(
  from: TwoLevelLayout,
  to: TwoLevelLayout,
  t: number,
  focalPlanetId?: string,
): TwoLevelLayout {
  const ease = easeInOutCubic(t);
  const center = ease < 0.4 ? from.center : to.center;
  const fromMap = new Map(from.planets.map((p) => [p.node.id, p]));
  const focal = focalPlanetId ? from.planets.find((p) => p.node.id === focalPlanetId) : null;

  const planets: PlacedPlanet[] = to.planets.map((tp) => {
    if (focal && focalPlanetId === tp.node.id) {
      return {
        ...tp,
        x: lerp(focal.x, tp.x, ease),
        y: lerp(focal.y, tp.y, ease),
        visualRadius: lerp(focal.visualRadius * 1.4, tp.visualRadius, ease),
      };
    }
    const fp = fromMap.get(tp.node.id);
    if (fp) {
      return { ...tp, x: lerp(fp.x, tp.x, ease), y: lerp(fp.y, tp.y, ease) };
    }
    const alpha = Math.max(0, (ease - 0.35) / 0.65);
    return { ...tp, x: tp.x * alpha, y: tp.y * alpha };
  });

  if (focal && ease < 0.55) {
    const fade = 1 - ease / 0.55;
    for (const fp of from.planets) {
      if (fp.node.id === focalPlanetId) continue;
      if (!to.planets.some((p) => p.node.id === fp.node.id)) {
        planets.push({
          ...fp,
          x: fp.x * fade,
          y: fp.y * fade,
        });
      }
    }
  }

  return { center, planets };
}

function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2;
}

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}
