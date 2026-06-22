/**
 * Canvas rendering for constellation orbit mode — reference-mockup visuals.
 */

export interface PlanetDrawOptions {
  progress: number;
  color: string;
  label: string;
  levelType?: string;
  dimmed?: boolean;
  selected?: boolean;
  showBadge?: string;
  isSun?: boolean;
  isCollapsedCluster?: boolean;
  isExpandedHub?: boolean;
  levelAccent?: string;
  pulse?: number;
  showRing?: boolean;
  zoom?: number;
}

function lighten(hex: string, amount: number): string {
  const m = hex.match(/^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i);
  if (!m) return hex;
  const r = Math.min(255, parseInt(m[1], 16) + 255 * amount);
  const g = Math.min(255, parseInt(m[2], 16) + 255 * amount);
  const b = Math.min(255, parseInt(m[3], 16) + 255 * amount);
  return `rgb(${r | 0},${g | 0},${b | 0})`;
}

function darken(hex: string, amount: number): string {
  const m = hex.match(/^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i);
  if (!m) return hex;
  const r = Math.max(0, parseInt(m[1], 16) * (1 - amount));
  const g = Math.max(0, parseInt(m[2], 16) * (1 - amount));
  const b = Math.max(0, parseInt(m[3], 16) * (1 - amount));
  return `rgb(${r | 0},${g | 0},${b | 0})`;
}

/** Keep text readable on screen regardless of canvas zoom */
function screenFont(ctx: CanvasRenderingContext2D, px: number, zoom: number, weight = '600') {
  const size = Math.max(9, Math.min(16, px / Math.max(zoom, 0.35)));
  ctx.font = `${weight} ${size}px Inter, system-ui, sans-serif`;
}

export function drawAlignmentBeam(
  ctx: CanvasRenderingContext2D,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  childProgress: number,
  color: string,
  dashed = false,
) {
  const strength = Math.max(0.35, childProgress / 100);
  ctx.save();
  ctx.globalAlpha = 0.55 + strength * 0.35;
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.strokeStyle = color.startsWith('#') ? color : color;
  ctx.lineWidth = 1.2 + strength * 1.8;
  if (dashed) ctx.setLineDash([6, 8]);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.restore();
}

export function drawOrbitLane(
  ctx: CanvasRenderingContext2D,
  px: number,
  py: number,
  minR: number,
  maxR: number,
  centerAngle: number,
  sectorWidth: number,
) {
  const start = centerAngle - sectorWidth / 2;
  const end = centerAngle + sectorWidth / 2;

  ctx.save();
  ctx.globalAlpha = 0.22;
  ctx.strokeStyle = 'rgba(148, 163, 184, 0.7)';
  ctx.lineWidth = 1.2;
  ctx.setLineDash([5, 12]);

  for (const r of [minR, maxR]) {
    ctx.beginPath();
    ctx.arc(px, py, r, start, end);
    ctx.stroke();
  }
  ctx.setLineDash([]);
  ctx.restore();
}

export function drawSunAlignmentRings(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  rings: Array<{ r: number; color: string; glow: string; fill?: string; label?: string }>,
) {
  const sorted = [...rings].sort((a, b) => b.r - a.r);

  for (let i = 0; i < sorted.length; i++) {
    const ring = sorted[i];
    const innerR = i < sorted.length - 1 ? sorted[i + 1].r : 0;

    if (ring.fill) {
      ctx.beginPath();
      ctx.arc(cx, cy, ring.r, 0, Math.PI * 2);
      if (innerR > 0) {
        ctx.arc(cx, cy, innerR, 0, Math.PI * 2, true);
      }
      ctx.fillStyle = ring.fill;
      ctx.fill('evenodd');
    }

    ctx.beginPath();
    ctx.arc(cx, cy, ring.r + 3, 0, Math.PI * 2);
    ctx.strokeStyle = ring.glow;
    ctx.lineWidth = 6;
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(cx, cy, ring.r, 0, Math.PI * 2);
    ctx.strokeStyle = ring.color;
    ctx.lineWidth = 1.2;
    ctx.setLineDash([3, 14]);
    ctx.stroke();
    ctx.setLineDash([]);
  }
}

function drawNodeLabels(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  radius: number,
  label: string,
  levelType: string | undefined,
  accent: string,
  zoom: number,
  progress: number,
  showPercentInside: boolean,
) {
  if (showPercentInside) {
    screenFont(ctx, 13, zoom, '700');
    ctx.fillStyle = '#ffffff';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.shadowColor = 'rgba(0,0,0,0.6)';
    ctx.shadowBlur = 4 / Math.max(zoom, 0.5);
    ctx.fillText(`${Math.round(progress)}%`, x, y);
    ctx.shadowBlur = 0;
  }

  const shortLabel = label.length > 28 ? `${label.slice(0, 26)}…` : label;
  let labelY = y + radius + 10 / Math.max(zoom, 0.4);

  if (levelType) {
    screenFont(ctx, 9, zoom, '700');
    ctx.fillStyle = accent;
    ctx.globalAlpha = 0.85;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillText(levelType.toUpperCase(), x, labelY);
    ctx.globalAlpha = 1;
    labelY += 12 / Math.max(zoom, 0.4);
  }

  screenFont(ctx, 12, zoom, '600');
  ctx.fillStyle = accent || '#e2e8f0';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  ctx.shadowColor = 'rgba(0,0,0,0.75)';
  ctx.shadowBlur = 6 / Math.max(zoom, 0.5);
  ctx.fillText(shortLabel, x, labelY);
  ctx.shadowBlur = 0;
}

export function drawPlanetNode(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  radius: number,
  opts: PlanetDrawOptions,
) {
  const {
    progress,
    color,
    label,
    levelType,
    dimmed,
    selected,
    showBadge,
    isSun,
    isCollapsedCluster,
    isExpandedHub,
    levelAccent = '#94a3b8',
    pulse = 0,
    showRing,
    zoom = 1,
  } = opts;

  const alpha = dimmed ? 0.62 : 1;
  ctx.globalAlpha = alpha;

  if (isSun) {
    const coronaR = radius + 18 + pulse * 10;
    const outer = ctx.createRadialGradient(x, y, radius * 0.1, x, y, coronaR + 40);
    outer.addColorStop(0, 'rgba(34, 211, 238, 0.55)');
    outer.addColorStop(0.35, 'rgba(34, 211, 238, 0.18)');
    outer.addColorStop(1, 'transparent');
    ctx.fillStyle = outer;
    ctx.beginPath();
    ctx.arc(x, y, coronaR + 40, 0, Math.PI * 2);
    ctx.fill();

    const core = ctx.createRadialGradient(x - radius * 0.2, y - radius * 0.25, 0, x, y, radius);
    core.addColorStop(0, '#ecfeff');
    core.addColorStop(0.25, '#22d3ee');
    core.addColorStop(0.65, '#0891b2');
    core.addColorStop(1, '#0e7490');
    ctx.fillStyle = core;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = 'rgba(255,255,255,0.35)';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    drawNodeLabels(ctx, x, y, radius, label, levelType || 'Organization', '#22d3ee', zoom, progress, true);
  } else if (isCollapsedCluster) {
    const glow = ctx.createRadialGradient(x, y, radius * 0.5, x, y, radius + 22);
    glow.addColorStop(0, `${color}44`);
    glow.addColorStop(1, 'transparent');
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(x, y, radius + 22, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = color;
    ctx.lineWidth = 3.5;
    ctx.stroke();

    ctx.strokeStyle = 'rgba(255,255,255,0.2)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(x, y, radius - 4, 0, Math.PI * 2);
    ctx.stroke();

    if (showBadge) {
      ctx.fillStyle = '#0f172a';
      ctx.beginPath();
      ctx.arc(x, y, radius * 0.42, 0, Math.PI * 2);
      ctx.fill();
      screenFont(ctx, 11, zoom, '700');
      ctx.fillStyle = '#f8fafc';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(showBadge, x, y);
    } else {
      drawNodeLabels(ctx, x, y, radius, label, levelType, levelAccent, zoom, progress, !showBadge);
    }

    if (showBadge) {
      drawNodeLabels(ctx, x, y, radius, label, levelType, levelAccent, zoom, progress, false);
    }
  } else if (isExpandedHub) {
    const hubColor = '#0d9488';
    const glow = ctx.createRadialGradient(x, y, radius * 0.3, x, y, radius + 18);
    glow.addColorStop(0, 'rgba(45, 212, 191, 0.35)');
    glow.addColorStop(1, 'transparent');
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(x, y, radius + 18, 0, Math.PI * 2);
    ctx.fill();

    const body = ctx.createRadialGradient(x - radius * 0.25, y - radius * 0.25, 0, x, y, radius);
    body.addColorStop(0, lighten(hubColor, 0.4));
    body.addColorStop(0.6, hubColor);
    body.addColorStop(1, '#115e59');
    ctx.fillStyle = body;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = levelAccent;
    ctx.lineWidth = 2.5;
    ctx.stroke();

    drawNodeLabels(ctx, x, y, radius, label, levelType, levelAccent, zoom, progress, true);
  } else {
    const atmo = ctx.createRadialGradient(x, y, radius * 0.35, x, y, radius + 28);
    atmo.addColorStop(0, `${color}88`);
    atmo.addColorStop(0.5, `${color}33`);
    atmo.addColorStop(1, 'transparent');
    ctx.fillStyle = atmo;
    ctx.beginPath();
    ctx.arc(x, y, radius + 28, 0, Math.PI * 2);
    ctx.fill();

    const body = ctx.createRadialGradient(
      x - radius * 0.35,
      y - radius * 0.38,
      radius * 0.05,
      x + radius * 0.12,
      y + radius * 0.1,
      radius * 1.15,
    );
    body.addColorStop(0, lighten(color, 0.55));
    body.addColorStop(0.45, color);
    body.addColorStop(1, darken(color, 0.35));
    ctx.fillStyle = body;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = 'rgba(255,255,255,0.22)';
    ctx.beginPath();
    ctx.ellipse(x - radius * 0.28, y - radius * 0.32, radius * 0.35, radius * 0.16, -0.35, 0, Math.PI * 2);
    ctx.fill();

    if (showRing) {
      ctx.strokeStyle = 'rgba(251, 191, 36, 0.55)';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.ellipse(x, y, radius + 8, radius * 0.32, Math.PI / 7, 0, Math.PI * 2);
      ctx.stroke();
      ctx.strokeStyle = 'rgba(255,255,255,0.18)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.ellipse(x, y, radius + 5, radius * 0.26, Math.PI / 7, 0, Math.PI * 2);
      ctx.stroke();
    }

    drawNodeLabels(ctx, x, y, radius, label, levelType, levelAccent, zoom, progress, true);
  }

  if (selected) {
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.arc(x, y, radius + 6, 0, Math.PI * 2);
    ctx.stroke();
  }

  ctx.globalAlpha = 1;
}

export function levelTypeLabel(level?: string): string {
  const map: Record<string, string> = {
    organization: 'Organization',
    region: 'Region',
    plant: 'Plant',
    department: 'Department',
    team: 'Team',
    employee: 'Employee',
  };
  return map[(level || '').toLowerCase()] ?? '';
}
