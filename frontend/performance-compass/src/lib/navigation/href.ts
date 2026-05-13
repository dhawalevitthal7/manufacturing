/** Split an internal href like `/reviews?view=a` into pathname + search record for TanStack Router `Link`. */
export function parseRouteHref(href: string): {
  pathname: string;
  search?: Record<string, string>;
} {
  const q = href.indexOf("?");
  if (q === -1) return { pathname: href };
  const pathname = href.slice(0, q);
  const search: Record<string, string> = {};
  new URLSearchParams(href.slice(q + 1)).forEach((v, k) => {
    search[k] = v;
  });
  return { pathname, search };
}

/** Whether this nav href matches the current location (pathname + required search keys). */
export function isNavHrefActive(
  href: string,
  pathname: string,
  currentSearch: Record<string, unknown> | undefined,
): boolean {
  const { pathname: targetPath, search: required } = parseRouteHref(href);
  if (pathname !== targetPath) return false;
  if (!required || Object.keys(required).length === 0) return true;
  const cur = currentSearch ?? {};
  for (const [k, v] of Object.entries(required)) {
    if (String(cur[k] ?? "") !== String(v)) return false;
  }
  return true;
}
