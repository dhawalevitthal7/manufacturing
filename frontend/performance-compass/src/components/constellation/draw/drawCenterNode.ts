import type { ConstellationNode } from '@/types/constellation.types';
import { levelLabel } from '@/utils/orbitalLayout';
import { constellationTheme } from '../theme/constellationTheme';
import { getRadialGradient } from './gradientCache';

export interface CenterNodeDrawOptions {
  pulse: number;
  hovered?: boolean;
  selected?: boolean;
  zoom?: number;
}

export function drawCenterNode(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  node: ConstellationNode,
  opts: CenterNodeDrawOptions,
): void {
  const { pulse, hovered, selected, zoom = 1 } = opts;
  const t = constellationTheme.center;
  const radius = t.radius;
  const glowExtra = pulse * t.pulseAmplitude + (hovered ? 8 : 0);
  const coronaR = radius + 25 + glowExtra;

  const outerGlow = getRadialGradient(
    ctx,
    hovered ? 'center-outer-h' : 'center-outer',
    x,
    y,
    radius * 0.2,
    coronaR + 35,
    [
      [0, hovered ? 'rgba(34, 211, 238, 0.5)' : t.outerGlow],
      [0.4, 'rgba(34, 211, 238, 0.12)'],
      [1, 'transparent'],
    ],
  );
  ctx.fillStyle = outerGlow;
  ctx.beginPath();
  ctx.arc(x, y, coronaR + 35, 0, Math.PI * 2);
  ctx.fill();

  const core = getRadialGradient(
    ctx,
    'center-core',
    x - radius * 0.15,
    y - radius * 0.15,
    0,
    radius,
    [
      [0, t.hotCore],
      [0.25, '#67e8f9'],
      [0.55, t.coreColor],
      [0.85, '#0891b2'],
      [1, 'rgba(8, 145, 178, 0.6)'],
    ],
  );
  ctx.fillStyle = core;
  ctx.beginPath();
  ctx.arc(x, y, radius, 0, Math.PI * 2);
  ctx.fill();

  if (selected) {
    ctx.strokeStyle = constellationTheme.planet.selectedRing;
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.arc(x, y, radius + 5, 0, Math.PI * 2);
    ctx.stroke();
  }

  const scopeTitle = levelLabel(node.level);
  const subtitle =
    (node.objective?.length ?? 0) > 48
      ? `${node.objective.slice(0, 46)}…`
      : node.objective || '';

  const labelScale = 1 / Math.max(zoom, 0.45);
  const titleY = y + radius + 22 * labelScale;

  ctx.save();
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  ctx.font = t.titleFont.replace(/(\d+)px/, `${Math.min(20, 20 * labelScale)}px`);
  ctx.fillStyle = t.titleColor;
  ctx.shadowColor = 'rgba(0,0,0,0.8)';
  ctx.shadowBlur = 8;
  ctx.fillText(scopeTitle, x, titleY);

  if (subtitle) {
    ctx.font = t.subtitleFont.replace(/(\d+)px/, `${Math.min(14, 14 * labelScale)}px`);
    ctx.fillStyle = t.subtitleColor;
    ctx.fillText(subtitle, x, titleY + 24 * labelScale);
  }
  ctx.shadowBlur = 0;
  ctx.restore();
}

export function centerHitRadius(): number {
  return constellationTheme.center.radius + 8;
}
