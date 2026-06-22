import type { ConstellationNode, OKRHealth } from '@/types/constellation.types';
import { formatTeamDisplayName } from '@/utils/orbitalLayout';
import { brightenHex, constellationTheme, darkenHex, healthColor } from '../theme/constellationTheme';
import { getRadialGradient } from './gradientCache';

export interface OrbitPlanetDrawOptions {
  progress: number;
  health?: OKRHealth | string;
  hovered?: boolean;
  selected?: boolean;
  dimmed?: boolean;
  zoom?: number;
  showProgressArc?: boolean;
  showProgressLabel?: boolean;
  moonCountBadge?: number | null;
  label?: string;
  radius?: number;
  opacity?: number;
}

export function planetRadiusForNode(node: ConstellationNode, selected = false): number {
  const weight = node.strategic_weight ?? 3;
  const t = constellationTheme.planet;
  const base = t.minRadius + ((weight - 1) / 4) * (t.maxRadius - t.minRadius);
  return selected ? base + 4 : base;
}

export function drawOrbitPlanet(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  node: ConstellationNode,
  opts: OrbitPlanetDrawOptions,
): void {
  const {
    progress,
    health = node.alignment_health,
    hovered,
    selected,
    dimmed,
    zoom = 1,
    showProgressArc = true,
    showProgressLabel = true,
    moonCountBadge,
    label,
    radius: radiusOverride,
    opacity = 1,
  } = opts;

  const color = healthColor(health);
  const radius = radiusOverride ?? planetRadiusForNode(node, !!selected);
  const alpha = (dimmed ? 0.5 : 1) * opacity;
  const glowBoost = hovered ? constellationTheme.planet.hoverGlowBoost : 1;

  ctx.save();
  ctx.globalAlpha = alpha;

  const haloR = radius + 22 * glowBoost;
  const halo = getRadialGradient(ctx, `halo-${color}-${hovered ? 'h' : 'n'}`, x, y, radius * 0.4, haloR, [
    [0, `${color}55`],
    [0.5, `${color}22`],
    [1, 'transparent'],
  ]);
  ctx.fillStyle = halo;
  ctx.beginPath();
  ctx.arc(x, y, haloR, 0, Math.PI * 2);
  ctx.fill();

  const body = getRadialGradient(
    ctx,
    `body-${color}-${radius}`,
    x - radius * 0.35,
    y - radius * 0.38,
    radius * 0.05,
    radius * 1.15,
    [
      [0, brightenHex(color, hovered ? 0.55 : 0.45)],
      [0.45, color],
      [1, darkenHex(color, 0.35)],
    ],
  );
  ctx.fillStyle = body;
  ctx.beginPath();
  ctx.arc(x, y, radius, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = 'rgba(255,255,255,0.2)';
  ctx.beginPath();
  ctx.ellipse(x - radius * 0.28, y - radius * 0.32, radius * 0.32, radius * 0.14, -0.35, 0, Math.PI * 2);
  ctx.fill();

  if (showProgressArc) {
    drawProgressArc(ctx, x, y, radius + 6, progress, color);
  }

  if (selected) {
    ctx.strokeStyle = constellationTheme.planet.selectedRing;
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.arc(x, y, radius + 10, 0, Math.PI * 2);
    ctx.stroke();
  }

  if (moonCountBadge != null && moonCountBadge > 0) {
    const badgeR = 10;
    const bx = x + radius * 0.65;
    const by = y - radius * 0.65;
    ctx.fillStyle = 'rgba(15, 23, 42, 0.92)';
    ctx.beginPath();
    ctx.arc(bx, by, badgeR, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = constellationTheme.moon.glowColor;
    ctx.lineWidth = 1.5;
    ctx.stroke();
    const fs = Math.min(10, 10 / Math.max(zoom, 0.45));
    ctx.font = `700 ${fs}px Inter, system-ui, sans-serif`;
    ctx.fillStyle = '#f8fafc';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(String(moonCountBadge), bx, by);
  }

  drawPlanetLabels(ctx, x, y, radius, node, progress, color, label, zoom, showProgressLabel);
  ctx.restore();
}

function drawProgressArc(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  arcR: number,
  progress: number,
  color: string,
): void {
  const t = constellationTheme.planet;
  const start = t.progressArcStart;
  const sweep = t.progressArcSweep;
  const end = start + (Math.max(0, Math.min(100, progress)) / 100) * sweep;

  ctx.lineCap = 'round';
  ctx.lineWidth = t.progressArcWidth;
  ctx.strokeStyle = t.trackStroke;
  ctx.beginPath();
  ctx.arc(x, y, arcR, start, start + sweep);
  ctx.stroke();

  ctx.strokeStyle = brightenHex(color, 0.25);
  ctx.beginPath();
  ctx.arc(x, y, arcR, start, end);
  ctx.stroke();
}

function drawPlanetLabels(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  radius: number,
  node: ConstellationNode,
  progress: number,
  color: string,
  labelOverride: string | undefined,
  zoom: number,
  showProgress: boolean,
): void {
  const rawName =
    labelOverride ||
    node.entity_name ||
    node.department_name ||
    node.plant_name ||
    node.region_name ||
    node.team_name ||
    node.objective;
  const name = node.level === 'team' ? formatTeamDisplayName(rawName) : rawName;
  const shortName =
    (name || 'OKR').length > 20 ? `${(name || 'OKR').slice(0, 18)}…` : name || 'OKR';

  const labelScale = 1 / Math.max(zoom, 0.45);
  const nameY = y + radius + 18 * labelScale;

  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  ctx.shadowColor = 'rgba(0,0,0,0.75)';
  ctx.shadowBlur = 6;

  ctx.font = constellationTheme.planet.nameFont.replace(/(\d+)px/, `${Math.min(15, 15 * labelScale)}px`);
  ctx.fillStyle = constellationTheme.planet.nameColor;
  ctx.fillText(shortName, x, nameY);

  if (showProgress) {
    ctx.font = constellationTheme.planet.progressFont.replace(/(\d+)px/, `${Math.min(14, 14 * labelScale)}px`);
    ctx.fillStyle = color;
    ctx.fillText(`${Math.round(progress)}%`, x, nameY + 18 * labelScale);
  }
  ctx.shadowBlur = 0;
}
