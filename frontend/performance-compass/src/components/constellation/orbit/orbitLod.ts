/**
 * Semantic zoom / Level-of-Detail for orbit view.
 */

export type LodTier = 'far' | 'mid' | 'near';

export const ZOOM_MIN = 0.5;
export const ZOOM_MAX = 3;

export function clampOrbitZoom(z: number): number {
  return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, z));
}

export function zoomToLodTier(zoom: number): LodTier {
  if (zoom < 0.8) return 'far';
  if (zoom < 1.4) return 'mid';
  return 'near';
}

export interface LodOpacity {
  moonDots: number;
  moonLabels: number;
  planetProgress: number;
  progressArcs: number;
  bandLabels: number;
  moonCountBadge: number;
}

const LOD_TARGETS: Record<LodTier, LodOpacity> = {
  far: {
    moonDots: 0,
    moonLabels: 0,
    planetProgress: 0,
    progressArcs: 0,
    bandLabels: 1,
    moonCountBadge: 1,
  },
  mid: {
    moonDots: 1,
    moonLabels: 0,
    planetProgress: 1,
    progressArcs: 1,
    bandLabels: 1,
    moonCountBadge: 0,
  },
  near: {
    moonDots: 1,
    moonLabels: 1,
    planetProgress: 1,
    progressArcs: 1,
    bandLabels: 0,
    moonCountBadge: 0,
  },
};

export function lerpLodOpacity(current: LodOpacity, target: LodOpacity, t: number): LodOpacity {
  const k = Math.min(1, Math.max(0, t));
  const out = {} as LodOpacity;
  for (const key of Object.keys(target) as (keyof LodOpacity)[]) {
    out[key] = current[key] + (target[key] - current[key]) * k;
  }
  return out;
}

export function getLodTargets(tier: LodTier): LodOpacity {
  return { ...LOD_TARGETS[tier] };
}

export const LOD_FADE_MS = 200;
