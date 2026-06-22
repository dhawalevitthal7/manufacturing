import type { PlacedExpandableNode } from '@/utils/orbitalLayout';
import { levelAccentColor } from '@/utils/orbitalLayout';
import { constellationTheme, healthColor } from '../theme/constellationTheme';
import { drawCenterNode } from './drawCenterNode';
import { drawOrbitPlanet, planetRadiusForNode } from './drawPlanetNode';
import { getRadialGradient } from './gradientCache';

function screenFont(ctx: CanvasRenderingContext2D, px: number, zoom: number, weight = '600'): void {
  const size = Math.max(9, Math.min(16, px / Math.max(zoom, 0.35)));
  ctx.font = `${weight} ${size}px Inter, system-ui, sans-serif`;
}

export function drawExpandableNode(
  ctx: CanvasRenderingContext2D,
  placed: PlacedExpandableNode,
  x: number,
  y: number,
  opts: {
    pulse: number;
    selected: boolean;
    hovered: boolean;
    zoom: number;
  },
): void {
  const { pulse, selected, hovered, zoom } = opts;
  const level =
    placed.kind === 'center'
      ? 'organization'
      : placed.cluster?.level ?? placed.node?.level;

  if (placed.kind === 'center' && placed.node) {
    drawCenterNode(ctx, x, y, placed.node, { pulse, hovered, selected, zoom });
    return;
  }

  if (placed.kind === 'cluster-collapsed') {
    drawCollapsedCluster(ctx, x, y, placed, selected, hovered, zoom);
    return;
  }

  if (placed.kind === 'cluster-hub') {
    drawExpandedHub(ctx, x, y, placed, selected, hovered, zoom);
    return;
  }

  if (placed.node) {
    drawOrbitPlanet(ctx, x, y, placed.node, {
      progress: placed.progress,
      health: placed.node.alignment_health,
      hovered,
      selected,
      dimmed: placed.dimmed,
      zoom,
      label: placed.label,
      radius: placed.displaySize * placed.scale,
    });
  }
}

function drawCollapsedCluster(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  placed: PlacedExpandableNode,
  selected: boolean,
  hovered: boolean,
  zoom: number,
): void {
  const radius = placed.displaySize * placed.scale;
  const color = healthColor(placed.cluster?.health);
  const alpha = placed.dimmed ? 0.55 : 1;
  const accent = placed.levelAccent ?? levelAccentColor(placed.cluster?.level);

  ctx.save();
  ctx.globalAlpha = alpha;

  const glow = getRadialGradient(ctx, `cluster-glow-${color}`, x, y, radius * 0.4, radius + 24, [
    [0, `${color}44`],
    [1, 'transparent'],
  ]);
  ctx.fillStyle = glow;
  ctx.beginPath();
  ctx.arc(x, y, radius + 24, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = 'rgba(13, 10, 26, 0.88)';
  ctx.beginPath();
  ctx.arc(x, y, radius, 0, Math.PI * 2);
  ctx.fill();

  ctx.strokeStyle = hovered ? color : accent;
  ctx.lineWidth = hovered ? 4 : 3;
  ctx.stroke();

  const badge = placed.cluster?.isExpandable
    ? `+${placed.cluster.childCount || placed.cluster.descendantCount}`
    : null;
  if (badge) {
    screenFont(ctx, 11, zoom, '700');
    ctx.fillStyle = '#f8fafc';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(badge, x, y);
  }

  drawClusterLabel(ctx, x, y, radius, placed.label, accent, placed.progress, zoom);
  if (selected) drawSelectionRing(ctx, x, y, radius);
  ctx.restore();
}

function drawExpandedHub(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  placed: PlacedExpandableNode,
  selected: boolean,
  hovered: boolean,
  zoom: number,
): void {
  const radius = placed.displaySize * placed.scale;
  const accent = placed.levelAccent ?? '#0d9488';
  const color = healthColor(placed.cluster?.health);

  ctx.save();
  const glow = getRadialGradient(ctx, 'hub-glow', x, y, radius * 0.2, radius + 18, [
    [0, 'rgba(45, 212, 191, 0.4)'],
    [1, 'transparent'],
  ]);
  ctx.fillStyle = glow;
  ctx.beginPath();
  ctx.arc(x, y, radius + 18, 0, Math.PI * 2);
  ctx.fill();

  const body = getRadialGradient(ctx, `hub-${radius}`, x - radius * 0.2, y - radius * 0.2, 0, radius, [
    [0, '#5eead4'],
    [0.6, '#0d9488'],
    [1, '#115e59'],
  ]);
  ctx.fillStyle = body;
  ctx.beginPath();
  ctx.arc(x, y, radius, 0, Math.PI * 2);
  ctx.fill();

  ctx.strokeStyle = hovered ? color : accent;
  ctx.lineWidth = 2.5;
  ctx.stroke();

  screenFont(ctx, 11, zoom, '700');
  ctx.fillStyle = '#fff';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(`${Math.round(placed.progress)}%`, x, y);

  drawClusterLabel(ctx, x, y, radius, placed.label, accent, placed.progress, zoom);
  if (selected) drawSelectionRing(ctx, x, y, radius);
  ctx.restore();
}

function drawClusterLabel(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  radius: number,
  label: string,
  accent: string,
  progress: number,
  zoom: number,
): void {
  const short = label.length > 24 ? `${label.slice(0, 22)}…` : label;
  const labelY = y + radius + 10 / Math.max(zoom, 0.4);
  screenFont(ctx, 12, zoom, '600');
  ctx.fillStyle = accent;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  ctx.shadowColor = 'rgba(0,0,0,0.75)';
  ctx.shadowBlur = 5;
  ctx.fillText(short, x, labelY);
  screenFont(ctx, 10, zoom, '700');
  ctx.fillStyle = accent;
  ctx.fillText(`${Math.round(progress)}%`, x, labelY + 14 / Math.max(zoom, 0.4));
  ctx.shadowBlur = 0;
}

function drawSelectionRing(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  radius: number,
): void {
  ctx.strokeStyle = constellationTheme.planet.selectedRing;
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  ctx.arc(x, y, radius + 6, 0, Math.PI * 2);
  ctx.stroke();
}

export function expandableHitRadius(placed: PlacedExpandableNode): number {
  if (placed.kind === 'center') return constellationTheme.center.radius + 8;
  return placed.displaySize * placed.scale + (placed.kind === 'cluster-collapsed' ? 14 : 8);
}

export { planetRadiusForNode };
