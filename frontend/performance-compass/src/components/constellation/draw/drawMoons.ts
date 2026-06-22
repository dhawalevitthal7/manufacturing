import { constellationTheme, healthColor } from '../theme/constellationTheme';
import { getRadialGradient } from './gradientCache';
import type { PlacedMoon, PlacedPlanet } from '../orbit/buildTwoLevelLayout';
import {
  resolveLabelCollisions,
  measureTextBox,
  type LabelBox,
} from '../orbit/labelCollision';
import type { LodOpacity } from '../orbit/orbitLod';

export function drawPlanetMoons(
  ctx: CanvasRenderingContext2D,
  planet: PlacedPlanet,
  time: number,
  reducedMotion: boolean,
  pauseOrbit: boolean,
  zoom: number,
  lod: LodOpacity,
): void {
  const { x: planetX, y: planetY, moons, moonOrbitRadius, moonBaseAngle, totalMoonCount } = planet;
  if (!moons.length) return;

  const moonR = constellationTheme.moon.radius;
  const speed = reducedMotion || pauseOrbit ? 0 : constellationTheme.moon.orbitSpeed;
  const rotation = moonBaseAngle + time * speed;

  const positions: Array<{
    moon: PlacedMoon;
    mx: number;
    my: number;
    outwardX: number;
    outwardY: number;
  }> = [];

  for (let i = 0; i < moons.length; i++) {
    const moon = moons[i];
    const angle = moonBaseAngle + rotation + moon.angle;
    const mx = planetX + moonOrbitRadius * Math.cos(angle);
    const my = planetY + moonOrbitRadius * Math.sin(angle);
    const dx = mx - planetX;
    const dy = my - planetY;
    const len = Math.hypot(dx, dy) || 1;
    positions.push({
      moon,
      mx,
      my,
      outwardX: dx / len,
      outwardY: dy / len,
    });
  }

  if (lod.moonDots <= 0 && lod.moonCountBadge <= 0) return;

  for (const pos of positions) {
    const { moon, mx, my } = pos;
    ctx.save();
    ctx.globalAlpha = lod.moonDots * (moon.isBadge ? 1 : 1);

    if (moon.isBadge) {
      drawBadgeMoon(ctx, mx, my, moon.data.name, moonR);
      ctx.restore();
      continue;
    }

    const tint = healthColor(moon.data.health);
    const glow = getRadialGradient(ctx, 'moon-glow', mx, my, 0, moonR + 10, [
      [0, `${constellationTheme.moon.glowColor}88`],
      [0.6, `${constellationTheme.moon.glowColor}33`],
      [1, 'transparent'],
    ]);
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(mx, my, moonR + 10, 0, Math.PI * 2);
    ctx.fill();

    const body = getRadialGradient(ctx, 'moon-body', mx - 2, my - 2, 0, moonR, [
      [0, '#c4b5fd'],
      [0.5, constellationTheme.moon.glowColor],
      [1, '#7c3aed'],
    ]);
    ctx.fillStyle = body;
    ctx.beginPath();
    ctx.arc(mx, my, moonR, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  if (lod.moonLabels <= 0) return;

  const labelScale = 1 / Math.max(zoom, 0.45);
  const nameFont = constellationTheme.moon.nameFont.replace(/(\d+)px/, `${Math.min(12, 12 * labelScale)}px`);
  const progFont = constellationTheme.moon.progressFont.replace(/(\d+)px/, `${Math.min(11, 11 * labelScale)}px`);

  const boxes: LabelBox[] = positions
    .filter((p) => !p.moon.isBadge)
    .map((p, idx) => {
      const shortName = p.moon.data.name.length > 12 ? `${p.moon.data.name.slice(0, 10)}…` : p.moon.data.name;
      const labelText = `${shortName} ${Math.round(p.moon.data.progress)}%`;
      const { w, h } = measureTextBox(ctx, labelText, nameFont, 0, 0);
      const offset = moonR + 10;
      const lx = p.mx + p.outwardX * offset;
      const ly = p.my + p.outwardY * offset;
      return {
        id: `moon-${idx}`,
        x: lx - w / 2,
        y: ly - h / 2,
        w,
        h,
        radialX: p.outwardX,
        radialY: p.outwardY,
        hidden: false,
      };
    });

  const resolved = resolveLabelCollisions(boxes);

  let labelIdx = 0;
  for (const pos of positions) {
    if (pos.moon.isBadge) continue;
    const box = resolved[labelIdx++];
    if (!box || box.hidden) continue;

    const shortName = pos.moon.data.name.length > 12 ? `${pos.moon.data.name.slice(0, 10)}…` : pos.moon.data.name;
    const tint = healthColor(pos.moon.data.health);
    const offset = moonR + 10;
    let lx = pos.mx + pos.outwardX * offset;
    let ly = pos.my + pos.outwardY * offset;
    lx += (box.x + box.w / 2 - lx) * 0.5;
    ly += (box.y + box.h / 2 - ly) * 0.5;

    ctx.save();
    ctx.globalAlpha = lod.moonLabels;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.shadowColor = 'rgba(0,0,0,0.7)';
    ctx.shadowBlur = 4;
    ctx.font = nameFont;
    ctx.fillStyle = constellationTheme.moon.nameColor;
    ctx.fillText(shortName, lx, ly - 6 * labelScale);
    ctx.font = progFont;
    ctx.fillStyle = tint;
    ctx.fillText(`${Math.round(pos.moon.data.progress)}%`, lx, ly + 6 * labelScale);
    ctx.shadowBlur = 0;
    ctx.restore();
  }

  void totalMoonCount;
}

function drawBadgeMoon(
  ctx: CanvasRenderingContext2D,
  mx: number,
  my: number,
  text: string,
  moonR: number,
): void {
  ctx.fillStyle = 'rgba(13, 10, 26, 0.9)';
  ctx.beginPath();
  ctx.arc(mx, my, moonR, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = constellationTheme.moon.glowColor;
  ctx.lineWidth = 1.5;
  ctx.stroke();
  ctx.font = '700 9px Inter, system-ui, sans-serif';
  ctx.fillStyle = '#f8fafc';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, mx, my);
}
