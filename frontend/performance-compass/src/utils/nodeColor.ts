/**
 * Node Coloring Utilities
 * =======================
 * Color schemes and styling for constellation nodes
 */

import { OKRHealth, RiskLevel, TrendStatus } from '@/types/constellation.types';

// Color Palette - Space Observatory + Bloomberg Terminal Theme
export const colorPalette = {
  // Health Colors
  healthy: '#10b981', // Emerald
  healthyGlow: 'rgba(16, 185, 129, 0.6)',
  healthyLight: '#d1fae5',

  needsAttention: '#f59e0b', // Amber
  needsAttentionGlow: 'rgba(245, 158, 11, 0.6)',
  needsAttentionLight: '#fef3c7',

  critical: '#f97316', // Orange
  criticalGlow: 'rgba(249, 115, 22, 0.6)',
  criticalLight: '#fed7aa',

  blocked: '#ef4444', // Red
  blockedGlow: 'rgba(239, 68, 68, 0.6)',
  blockedLight: '#fee2e2',

  orphaned: '#6b7280', // Gray
  orphanedGlow: 'rgba(107, 114, 128, 0.6)',
  orphanedLight: '#f3f4f6',

  // Alignment Type Colors
  strategic: '#06b6d4', // Cyan
  operational: '#22c55e', // Green
  support: '#a855f7', // Purple
  dependency: '#f97316', // Orange
  crossFunctional: '#ec4899', // Pink

  // Background
  dark: '#0f172a',
  darkPanel: '#1e293b',
  border: '#334155',

  // Text
  text: '#f1f5f9',
  textMuted: '#cbd5e1',

  // Risk
  riskCritical: '#dc2626',
  riskHigh: '#f97316',
  riskMedium: '#f59e0b',
  riskLow: '#10b981',
};

/**
 * Get color for node based on health
 */
export const getHealthColor = (health: OKRHealth): string => {
  const colorMap: Record<OKRHealth, string> = {
    healthy: colorPalette.healthy,
    needs_attention: colorPalette.needsAttention,
    critical: colorPalette.critical,
    blocked: colorPalette.blocked,
  };
  return colorMap[health] || colorPalette.orphaned;
};

/**
 * Get glow color for node
 */
export const getHealthGlow = (health: OKRHealth): string => {
  const colorMap: Record<OKRHealth, string> = {
    healthy: colorPalette.healthyGlow,
    needs_attention: colorPalette.needsAttentionGlow,
    critical: colorPalette.criticalGlow,
    blocked: colorPalette.blockedGlow,
  };
  return colorMap[health] || colorPalette.orphanedGlow;
};

/**
 * Get color for edge based on alignment type
 */
export const getAlignmentTypeColor = (alignmentType: string): string => {
  const colorMap: Record<string, string> = {
    strategic: colorPalette.strategic,
    operational: colorPalette.operational,
    support: colorPalette.support,
    dependency: colorPalette.dependency,
    'cross-functional': colorPalette.crossFunctional,
  };
  return colorMap[alignmentType] || colorPalette.operational;
};

/**
 * Get color for risk level
 */
export const getRiskColor = (riskLevel: RiskLevel): string => {
  const colorMap: Record<RiskLevel, string> = {
    critical: colorPalette.riskCritical,
    high: colorPalette.riskHigh,
    medium: colorPalette.riskMedium,
    low: colorPalette.riskLow,
  };
  return colorMap[riskLevel] || colorPalette.riskMedium;
};

/**
 * Get color for trend status
 */
export const getTrendColor = (trend: TrendStatus): string => {
  const colorMap: Record<TrendStatus, string> = {
    ahead: colorPalette.healthy,
    on_track: colorPalette.operational,
    behind: colorPalette.needsAttention,
    critical_delay: colorPalette.blocked,
  };
  return colorMap[trend] || colorPalette.textMuted;
};

/**
 * Get status badge styling
 */
export const getStatusBadgeStyle = (
  health: OKRHealth
): { bg: string; text: string; border: string } => {
  const styles: Record<OKRHealth, { bg: string; text: string; border: string }> = {
    healthy: {
      bg: 'bg-emerald-500/20',
      text: 'text-emerald-400',
      border: 'border-emerald-500/30',
    },
    needs_attention: {
      bg: 'bg-amber-500/20',
      text: 'text-amber-400',
      border: 'border-amber-500/30',
    },
    critical: {
      bg: 'bg-orange-500/20',
      text: 'text-orange-400',
      border: 'border-orange-500/30',
    },
    blocked: {
      bg: 'bg-red-500/20',
      text: 'text-red-400',
      border: 'border-red-500/30',
    },
  };
  return styles[health] || styles.needs_attention;
};

/**
 * Get animated glow effect CSS
 */
export const getGlowEffect = (health: OKRHealth, intensity: number = 1): string => {
  const glowColor = getHealthGlow(health);
  const spread = 20 * intensity;
  return `0 0 ${spread}px ${glowColor}, 0 0 ${spread * 2}px ${glowColor}`;
};

/**
 * Get progress bar gradient
 */
export const getProgressGradient = (progress: number, health: OKRHealth): string => {
  const colors = {
    healthy: ['#10b981', '#06b6d4'],
    needs_attention: ['#f59e0b', '#fbbf24'],
    critical: ['#f97316', '#fb923c'],
    blocked: ['#ef4444', '#f87171'],
  };

  const [start, end] = colors[health] || colors.blocked;
  return `linear-gradient(90deg, ${start}, ${end})`;
};

export const nodeColorUtils = {
  colorPalette,
  getHealthColor,
  getHealthGlow,
  getAlignmentTypeColor,
  getRiskColor,
  getTrendColor,
  getStatusBadgeStyle,
  getGlowEffect,
  getProgressGradient,
};
