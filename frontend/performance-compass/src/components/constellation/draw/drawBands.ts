import { ORBIT_RADII } from '@/utils/orbitalLayout';
import { constellationTheme } from '../theme/constellationTheme';

export interface BandRing {
  r: number;
  fill: string;
  label: string;
}

const BAND_RINGS: BandRing[] = [
  { r: ORBIT_RADII.needsAttention, fill: constellationTheme.bands.needsAttention.fill, label: constellationTheme.bands.needsAttention.label },
  { r: ORBIT_RADII.progressing, fill: constellationTheme.bands.progressing.fill, label: constellationTheme.bands.progressing.label },
  { r: ORBIT_RADII.onTrack, fill: constellationTheme.bands.onTrack.fill, label: constellationTheme.bands.onTrack.label },
];

/** Three translucent concentric discs with labels and crosshairs. */
export function drawProgressBands(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  bandLabelOpacity = 1,
): void {
  const sorted = [...BAND_RINGS].sort((a, b) => b.r - a.r);

  for (let i = 0; i < sorted.length; i++) {
    const band = sorted[i];
    const innerR = i < sorted.length - 1 ? sorted[i + 1].r : 0;

    ctx.beginPath();
    ctx.arc(cx, cy, band.r, 0, Math.PI * 2);
    if (innerR > 0) {
      ctx.arc(cx, cy, innerR, 0, Math.PI * 2, true);
    }
    ctx.fillStyle = band.fill;
    ctx.fill('evenodd');

    drawBandLabel(ctx, cx, cy, band.r, band.label, bandLabelOpacity);
  }

  const innerR = ORBIT_RADII.onTrack;
  ctx.save();
  ctx.strokeStyle = constellationTheme.bands.crosshairColor;
  ctx.lineWidth = 1;
  ctx.setLineDash([6, 8]);
  ctx.beginPath();
  ctx.moveTo(cx - innerR, cy);
  ctx.lineTo(cx + innerR, cy);
  ctx.moveTo(cx, cy - innerR);
  ctx.lineTo(cx, cy + innerR);
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.beginPath();
  ctx.arc(cx, cy, innerR, 0, Math.PI * 2);
  ctx.strokeStyle = constellationTheme.bands.innerRingOutline;
  ctx.lineWidth = 1;
  ctx.stroke();
  ctx.restore();
}

function drawBandLabel(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  radius: number,
  text: string,
  opacity: number,
): void {
  const angle = -Math.PI / 4;
  const lx = cx + radius * 0.72 * Math.cos(angle);
  const ly = cy + radius * 0.72 * Math.sin(angle);

  ctx.save();
  ctx.globalAlpha = opacity;
  ctx.font = constellationTheme.bands.labelFont;
  ctx.fillStyle = constellationTheme.bands.labelColor;
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, lx, ly);
  ctx.restore();
}
