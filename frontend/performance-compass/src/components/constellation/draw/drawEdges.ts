import type { ConstellationEdge } from '@/types/constellation.types';
import { constellationTheme } from '../theme/constellationTheme';

export function drawOrbitEdge(
  ctx: CanvasRenderingContext2D,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  edge: ConstellationEdge,
  hovered: boolean,
): void {
  const isFunctional = edge.edge_type === 'FUNCTIONAL' || edge.is_dashed;
  const isBroken = edge.is_broken;
  let opacity: number = constellationTheme.edges.defaultOpacity;
  let color: string = isFunctional
    ? constellationTheme.edges.functionalColor ?? '#a78bfa'
    : constellationTheme.edges.defaultColor;

  if (hovered) {
    opacity = constellationTheme.edges.hoverOpacity;
    if (isFunctional || isBroken) {
      color = constellationTheme.edges.brokenHoverColor;
    }
  }

  ctx.save();
  ctx.globalAlpha = opacity;
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.strokeStyle = color;
  ctx.lineWidth = isFunctional ? 1.25 : 1;
  if (isFunctional) ctx.setLineDash([5, 5]);
  else if (isBroken && hovered) ctx.setLineDash([4, 6]);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.restore();
}

export function drawExpandableEdge(
  ctx: CanvasRenderingContext2D,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  dashed: boolean,
  hovered: boolean,
): void {
  ctx.save();
  ctx.globalAlpha = hovered ? constellationTheme.edges.hoverOpacity : constellationTheme.edges.defaultOpacity;
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.strokeStyle = dashed && hovered
    ? constellationTheme.edges.brokenHoverColor
    : constellationTheme.edges.defaultColor;
  ctx.lineWidth = 1;
  if (dashed && hovered) ctx.setLineDash([4, 6]);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.restore();
}
