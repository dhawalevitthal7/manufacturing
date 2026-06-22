/**
 * Simple label collision pass — nudge outward along radial vector or hide.
 */

export interface LabelBox {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  /** Radial unit vector from planet center */
  radialX: number;
  radialY: number;
  hidden: boolean;
}

function intersects(a: LabelBox, b: LabelBox): boolean {
  if (a.hidden || b.hidden) return false;
  return (
    a.x < b.x + b.w &&
    a.x + a.w > b.x &&
    a.y < b.y + b.h &&
    a.y + a.h > b.y
  );
}

export function resolveLabelCollisions(
  boxes: LabelBox[],
  maxIterations = 3,
  nudgePx = 14,
): LabelBox[] {
  const result = boxes.map((b) => ({ ...b }));

  for (let pass = 0; pass < maxIterations; pass++) {
    let moved = false;
    for (let i = 0; i < result.length; i++) {
      for (let j = 0; j < i; j++) {
        if (!intersects(result[i], result[j])) continue;
        result[i].x += result[i].radialX * nudgePx;
        result[i].y += result[i].radialY * nudgePx;
        moved = true;
        if (pass === maxIterations - 1) {
          result[i].hidden = true;
        }
      }
    }
    if (!moved) break;
  }
  return result;
}

export function measureTextBox(
  ctx: CanvasRenderingContext2D,
  text: string,
  font: string,
  x: number,
  y: number,
): { w: number; h: number } {
  ctx.font = font;
  const m = ctx.measureText(text);
  return { w: m.width + 4, h: 14 };
}
