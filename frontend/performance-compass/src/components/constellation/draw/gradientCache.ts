/** Cache canvas gradients to avoid per-frame allocation. */

const cache = new Map<string, CanvasGradient>();

export function getRadialGradient(
  ctx: CanvasRenderingContext2D,
  key: string,
  cx: number,
  cy: number,
  innerR: number,
  outerR: number,
  stops: Array<[number, string]>,
): CanvasGradient {
  const cacheKey = `${key}:${cx.toFixed(1)}:${cy.toFixed(1)}:${innerR}:${outerR}`;
  let grad = cache.get(cacheKey);
  if (!grad) {
    grad = ctx.createRadialGradient(cx, cy, innerR, cx, cy, outerR);
    for (const [offset, color] of stops) {
      grad.addColorStop(offset, color);
    }
    cache.set(cacheKey, grad);
    if (cache.size > 400) {
      const first = cache.keys().next().value;
      if (first) cache.delete(first);
    }
  }
  return grad;
}

export function clearGradientCache(): void {
  cache.clear();
}
