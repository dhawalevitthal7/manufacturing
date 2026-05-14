import type { OrgNode } from "./api";

/** Walk nested org tree (single root or multi-root) into a flat list. */
export function flattenOrgNodes(tree: OrgNode | { roots: OrgNode[] }): OrgNode[] {
  const out: OrgNode[] = [];

  function walk(node: OrgNode) {
    const { children, ...rest } = node;
    out.push(rest as OrgNode);
    for (const ch of children || []) walk(ch);
  }

  if (tree && typeof tree === "object" && "roots" in tree && Array.isArray((tree as { roots: OrgNode[] }).roots)) {
    for (const r of (tree as { roots: OrgNode[] }).roots) walk(r);
  } else if (tree && typeof tree === "object" && "id" in tree) {
    walk(tree as OrgNode);
  }

  return out;
}
