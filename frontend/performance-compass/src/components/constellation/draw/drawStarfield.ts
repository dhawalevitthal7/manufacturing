import { constellationTheme } from '../theme/constellationTheme';

export interface Star {
  x: number;
  y: number;
  size: number;
  baseOpacity: number;
  twinklePhase: number;
  twinkleSpeed: number;
  driftVx: number;
  driftVy: number;
}

export function createStarfield(width: number, height: number, count?: number): Star[] {
  const n = count ?? constellationTheme.starfield.count;
  const stars: Star[] = [];
  for (let i = 0; i < n; i++) {
    const seed = hash(i * 9973 + 42);
    stars.push({
      x: seed * width,
      y: hash(i * 7919 + 17) * height,
      size:
        constellationTheme.starfield.minSize +
        hash(i * 6151) * (constellationTheme.starfield.maxSize - constellationTheme.starfield.minSize),
      baseOpacity: 0.25 + hash(i * 3571) * 0.65,
      twinklePhase: hash(i * 8831) * Math.PI * 2,
      twinkleSpeed: 0.4 + hash(i * 5113) * constellationTheme.starfield.twinkleSpeed,
      driftVx: (hash(i * 2711) - 0.5) * 0.08,
      driftVy: (hash(i * 3917) - 0.5) * 0.08,
    });
  }
  return stars;
}

function hash(n: number): number {
  const x = Math.sin(n * 12.9898 + 78.233) * 43758.5453;
  return x - Math.floor(x);
}

/** Full-canvas radial deep-space background (screen space). */
export function drawDeepSpaceBackground(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
): void {
  const cx = width / 2;
  const cy = height / 2;
  const r = Math.hypot(width, height) * 0.65;
  const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
  grad.addColorStop(0, constellationTheme.background.center);
  grad.addColorStop(0.55, '#120d22');
  grad.addColorStop(1, constellationTheme.background.edge);
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, width, height);

  const haze = ctx.createRadialGradient(cx, cy, r * 0.35, cx, cy, r);
  haze.addColorStop(0, 'rgba(139, 92, 246, 0.06)');
  haze.addColorStop(0.5, 'rgba(99, 102, 241, 0.03)');
  haze.addColorStop(1, 'transparent');
  ctx.fillStyle = haze;
  ctx.fillRect(0, 0, width, height);
}

/** Faint square grid in world space. */
export function drawGrid(
  ctx: CanvasRenderingContext2D,
  cameraX: number,
  cameraY: number,
  viewW: number,
  viewH: number,
  zoom: number,
): void {
  const spacing = constellationTheme.background.gridSpacing;
  const halfW = viewW / zoom / 2 + spacing;
  const halfH = viewH / zoom / 2 + spacing;
  const minX = Math.floor((cameraX - halfW) / spacing) * spacing;
  const maxX = Math.ceil((cameraX + halfW) / spacing) * spacing;
  const minY = Math.floor((cameraY - halfH) / spacing) * spacing;
  const maxY = Math.ceil((cameraY + halfH) / spacing) * spacing;

  ctx.save();
  ctx.strokeStyle = `rgba(148, 163, 184, ${constellationTheme.background.gridOpacity})`;
  ctx.lineWidth = 1 / zoom;
  ctx.beginPath();
  for (let x = minX; x <= maxX; x += spacing) {
    ctx.moveTo(x, minY);
    ctx.lineTo(x, maxY);
  }
  for (let y = minY; y <= maxY; y += spacing) {
    ctx.moveTo(minX, y);
    ctx.lineTo(maxX, y);
  }
  ctx.stroke();
  ctx.restore();
}

/** Animated twinkling stars with subtle parallax (screen space). */
export function drawStarfield(
  ctx: CanvasRenderingContext2D,
  stars: Star[],
  time: number,
  width: number,
  height: number,
  cameraX: number,
  cameraY: number,
  reducedMotion: boolean,
): void {
  const parallax = constellationTheme.starfield.parallaxFactor;
  ctx.save();
  for (const star of stars) {
    const twinkle = reducedMotion
      ? star.baseOpacity
      : star.baseOpacity * (0.55 + 0.45 * Math.sin(time * star.twinkleSpeed + star.twinklePhase));
    const dx = reducedMotion ? 0 : star.driftVx * time;
    const dy = reducedMotion ? 0 : star.driftVy * time;
    const px =
      ((star.x + dx + cameraX * parallax) % width + width) % width;
    const py =
      ((star.y + dy + cameraY * parallax) % height + height) % height;

    ctx.globalAlpha = twinkle;
    ctx.fillStyle = star.size > 1.5 ? '#f8fafc' : '#cbd5e1';
    ctx.beginPath();
    ctx.arc(px, py, star.size, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
  ctx.restore();
}
