/**
 * Deep-space constellation visual theme — tweakable constants for orbit rendering.
 */

import type { OKRHealth } from '@/types/constellation.types';

export const constellationTheme = {
  background: {
    edge: '#0d0a1a',
    center: '#1a1230',
    gridOpacity: 0.04,
    gridSpacing: 48,
  },

  starfield: {
    count: 220,
    minSize: 0.7,
    maxSize: 2,
    twinkleSpeed: 0.6,
    parallaxFactor: 0.015,
  },

  bands: {
    onTrack: {
      fill: 'rgba(34, 211, 238, 0.06)',
      label: 'On Track',
    },
    progressing: {
      fill: 'rgba(251, 191, 36, 0.05)',
      label: 'Progressing',
    },
    needsAttention: {
      fill: 'rgba(248, 113, 113, 0.045)',
      label: 'Needs Attention',
    },
    labelColor: 'rgba(255, 255, 255, 0.25)',
    labelFont: '500 13px Inter, system-ui, sans-serif',
    crosshairColor: 'rgba(34, 211, 238, 0.12)',
    innerRingOutline: 'rgba(34, 211, 238, 0.18)',
  },

  center: {
    radius: 55,
    coreColor: '#22d3ee',
    hotCore: '#ffffff',
    outerGlow: 'rgba(34, 211, 238, 0.35)',
    titleFont: '700 20px Inter, system-ui, sans-serif',
    titleColor: '#ffffff',
    subtitleFont: '400 14px Inter, system-ui, sans-serif',
    subtitleColor: 'rgba(148, 163, 184, 0.85)',
    pulseAmplitude: 10,
    pulseSpeed: 0.8,
  },

  planet: {
    minRadius: 26,
    maxRadius: 34,
    progressArcWidth: 4,
    progressArcSweep: Math.PI * 1.5,
    progressArcStart: -Math.PI * 0.75,
    trackStroke: 'rgba(15, 23, 42, 0.65)',
    nameFont: '700 15px Inter, system-ui, sans-serif',
    nameColor: '#ffffff',
    progressFont: '700 14px Inter, system-ui, sans-serif',
    hoverGlowBoost: 1.45,
    selectedRing: '#ffffff',
  },

  moon: {
    radius: 8, // 7–9px visual range
    glowColor: '#a78bfa',
    orbitRadius: 52,
    nameFont: '500 12px Inter, system-ui, sans-serif',
    nameColor: 'rgba(203, 213, 225, 0.75)',
    progressFont: '700 11px Inter, system-ui, sans-serif',
    orbitSpeed: 0.05,
    maxPerPlanet: 8,
  },

  edges: {
    defaultOpacity: 0.06,
    hoverOpacity: 0.35,
    brokenHoverColor: 'rgba(239, 68, 68, 0.55)',
    defaultColor: 'rgba(34, 211, 238, 0.5)',
    functionalColor: 'rgba(167, 139, 250, 0.65)',
  },

  health: {
    healthy: '#34d399',
    needs_attention: '#fbbf24',
    critical: '#fb923c',
    blocked: '#ef4444',
  } satisfies Record<OKRHealth, string>,

  animation: {
    moonOrbitSpeed: 0.05,
  },
} as const;

export function healthColor(health: OKRHealth | string | undefined): string {
  const key = (health || 'healthy') as OKRHealth;
  return constellationTheme.health[key] ?? constellationTheme.health.healthy;
}

export function brightenHex(hex: string, amount: number): string {
  const m = hex.match(/^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i);
  if (!m) return hex;
  const r = Math.min(255, parseInt(m[1], 16) + 255 * amount);
  const g = Math.min(255, parseInt(m[2], 16) + 255 * amount);
  const b = Math.min(255, parseInt(m[3], 16) + 255 * amount);
  return `rgb(${r | 0},${g | 0},${b | 0})`;
}

export function darkenHex(hex: string, amount: number): string {
  const m = hex.match(/^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i);
  if (!m) return hex;
  const r = Math.max(0, parseInt(m[1], 16) * (1 - amount));
  const g = Math.max(0, parseInt(m[2], 16) * (1 - amount));
  const b = Math.max(0, parseInt(m[3], 16) * (1 - amount));
  return `rgb(${r | 0},${g | 0},${b | 0})`;
}
