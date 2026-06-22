/**
 * Progressive expand/collapse for OKR Constellation orbit mode.
 * Operates on the full fetched graph — no extra API calls.
 */

import type {
  AlignmentHealth,
  CollapsedCluster,
  ConstellationEdge,
  ConstellationNode,
  HierarchyLevel,
  OKRLevel,
  VisibleGraph,
} from '@/types/constellation.types';
import { normalizeOkrLevel, formatTeamDisplayName } from '@/utils/orbitalLayout';

export const SCOPE_CENTER_KEY = '__scope_center__';

const LEVEL_ORDER: HierarchyLevel[] = [
  'organization',
  'region',
  'plant',
  'department',
  'team',
  'employee',
];

const LEVEL_RANK: Record<HierarchyLevel, number> = {
  organization: 0,
  region: 1,
  plant: 2,
  department: 3,
  team: 4,
  employee: 5,
};

export function childLevelOf(level: HierarchyLevel): HierarchyLevel | null {
  const idx = LEVEL_ORDER.indexOf(level);
  if (idx < 0 || idx >= LEVEL_ORDER.length - 1) return null;
  return LEVEL_ORDER[idx + 1];
}

export function clusterLevelFromId(clusterId: string): HierarchyLevel | null {
  if (clusterId === SCOPE_CENTER_KEY) return 'organization';
  const m = clusterId.match(/^cluster-(region|plant|department|team|employee)-/);
  if (!m) return null;
  const map: Record<string, HierarchyLevel> = {
    region: 'region',
    plant: 'plant',
    department: 'department',
    team: 'team',
    employee: 'employee',
  };
  return map[m[1]] ?? null;
}

export function clusterIdForLevel(level: HierarchyLevel, unitId: string): string {
  const prefix =
    level === 'region'
      ? 'region'
      : level === 'plant'
        ? 'plant'
        : level === 'department'
          ? 'department'
          : level === 'team'
            ? 'team'
            : 'employee';
  return `cluster-${prefix}-${unitId}`;
}

export function progressToHealth(progress: number): AlignmentHealth {
  if (progress >= 80) return 'healthy';
  if (progress >= 60) return 'needs_attention';
  if (progress >= 40) return 'critical';
  return 'blocked';
}

function avgProgress(nodes: ConstellationNode[]): number {
  if (!nodes.length) return 0;
  const sum = nodes.reduce((s, n) => s + (n.final_progress ?? n.progress ?? 0), 0);
  return Math.round(sum / nodes.length);
}

function leafDescendants(nodes: ConstellationNode[]): ConstellationNode[] {
  return nodes.filter((n) => normalizeOkrLevel(n.level) === 'employee');
}

function unitIdForClusterLevel(node: ConstellationNode, level: HierarchyLevel): string | null {
  switch (level) {
    case 'region':
      return node.region || null;
    case 'plant':
      return node.plant || null;
    case 'department':
      return node.department || null;
    case 'team':
      return node.team || (normalizeOkrLevel(node.level) === 'team' ? node.id : null);
    case 'employee':
      return node.owner_id || node.owner_name || node.id;
    default:
      return null;
  }
}

function labelForUnit(
  nodes: ConstellationNode[],
  level: HierarchyLevel,
): string {
  const rep = nodes[0];
  if (!rep) return level;
  if (rep.entity_name) return rep.entity_name;
  switch (level) {
    case 'region':
      return rep.region_name || rep.objective;
    case 'plant':
      return rep.plant_name || rep.objective;
    case 'department':
      return rep.department_name || rep.objective;
    case 'team':
      return formatTeamDisplayName(rep.team_name || rep.entity_name || rep.objective);
    case 'employee':
      return rep.owner_name || rep.objective;
    default:
      return rep.objective;
  }
}

/** Map synthetic orbit / center node ids to cluster keys */
export function nodeIdToClusterId(nodeId: string): string | null {
  const patterns: Array<[RegExp, (m: RegExpMatchArray) => string]> = [
    [/^region-orbit-(.+)$/, (m) => clusterIdForLevel('region', m[1])],
    [/^plant-orbit-(.+)$/, (m) => clusterIdForLevel('plant', m[1])],
    [/^dept-orbit-(.+)$/, (m) => clusterIdForLevel('department', m[1])],
    [/^team-orbit-(.+)$/, (m) => clusterIdForLevel('team', m[1])],
    [/^orbit-region-(.+)$/, (m) => clusterIdForLevel('region', m[1])],
    [/^orbit-plant-(.+)$/, (m) => clusterIdForLevel('plant', m[1])],
    [/^orbit-department-(.+)$/, (m) => clusterIdForLevel('department', m[1])],
    [/^orbit-team-(.+)$/, (m) => clusterIdForLevel('team', m[1])],
  ];
  for (const [re, fn] of patterns) {
    const m = nodeId.match(re);
    if (m) return fn(m);
  }
  return null;
}

export function resolveClusterIdForNode(
  node: ConstellationNode,
  scopeLevel: OKRLevel,
): string | null {
  const synthetic = nodeIdToClusterId(node.id);
  if (synthetic) return synthetic;

  const level = normalizeOkrLevel(node.level);
  const unitId = unitIdForClusterLevel(node, level);
  if (!unitId) return null;
  if (level === 'organization') return null;
  return clusterIdForLevel(level, unitId);
}

export function parentClusterKeyForNode(
  node: ConstellationNode,
  scopeLevel: OKRLevel,
): string {
  const level = normalizeOkrLevel(node.level);
  const scopeNorm = normalizeOkrLevel(scopeLevel);
  const nodeRank = LEVEL_RANK[level];
  const scopeRank = LEVEL_RANK[scopeNorm];

  if (nodeRank <= scopeRank) return SCOPE_CENTER_KEY;
  if (nodeRank === scopeRank + 1) return SCOPE_CENTER_KEY;

  const parentLevel = LEVEL_ORDER[nodeRank - 1];
  switch (parentLevel) {
    case 'region': {
      const rid = node.region;
      return rid ? clusterIdForLevel('region', rid) : SCOPE_CENTER_KEY;
    }
    case 'plant': {
      const pid = node.plant;
      return pid ? clusterIdForLevel('plant', pid) : SCOPE_CENTER_KEY;
    }
    case 'department': {
      const did = node.department;
      return did ? clusterIdForLevel('department', did) : SCOPE_CENTER_KEY;
    }
    case 'team': {
      const tid = node.team;
      return tid ? clusterIdForLevel('team', tid) : SCOPE_CENTER_KEY;
    }
    default:
      return SCOPE_CENTER_KEY;
  }
}

export interface ExpansionContext {
  scopeLevel: OKRLevel;
  scopeId: string | null;
  scopeCenterId: string;
}

export function resolveScopeCenter(
  nodes: ConstellationNode[],
  scopeLevel: OKRLevel,
  scopeId: string | null,
  organizationName?: string,
  scopeEntityName?: string,
): { centerNode: ConstellationNode; centerId: string } {
  const normalized = nodes.map((n) => ({ ...n, level: normalizeOkrLevel(n.level) }));
  const scopeNorm = normalizeOkrLevel(scopeLevel);

  let candidates = normalized.filter((n) => normalizeOkrLevel(n.level) === scopeNorm);
  if (scopeId && scopeNorm !== 'organization') {
    const scoped = candidates.filter((n) => {
      if (scopeNorm === 'region') return n.region === scopeId || n.id === scopeId;
      if (scopeNorm === 'plant') return n.plant === scopeId;
      if (scopeNorm === 'department') return n.department === scopeId;
      if (scopeNorm === 'team') return n.team === scopeId;
      return true;
    });
    if (scoped.length) candidates = scoped;
  }

  if (candidates.length) {
    const best = candidates.reduce((a, b) =>
      (a.strategic_weight ?? 0) > (b.strategic_weight ?? 0) ? a : b,
    );
    return { centerNode: best, centerId: best.id };
  }

  if (scopeId && scopeNorm !== 'organization') {
    const syntheticId = `center-${scopeNorm}-${scopeId}`;
    const syn = normalized.find((n) => n.id === syntheticId);
    if (syn) return { centerNode: syn, centerId: syn.id };
  }

  const label =
    scopeEntityName ||
    (scopeNorm === 'organization' ? organizationName || 'Organization' : scopeNorm);
  const synthetic: ConstellationNode = {
    id: scopeId ? `center-${scopeNorm}-${scopeId}` : `center-${scopeNorm}`,
    objective: label,
    entity_name: label,
    owner_name: '',
    owner_role: '',
    level: scopeNorm,
    progress: 0,
    own_progress: 0,
    alignment_contribution: 0,
    final_progress: 0,
    alignment_health: 'needs_attention',
    confidence_score: 50,
    risk_level: 'medium',
    trend_status: 'on_track',
    strategic_weight: 5,
    is_orphaned: false,
    region: scopeNorm === 'region' ? scopeId : undefined,
    plant: scopeNorm === 'plant' ? scopeId : undefined,
    department: scopeNorm === 'department' ? scopeId : undefined,
    team: scopeNorm === 'team' ? scopeId : undefined,
  };
  return { centerNode: synthetic, centerId: synthetic.id };
}

export interface ChildrenMapResult {
  childrenByCluster: Map<string, ConstellationNode[]>;
  clusterMeta: Map<string, { level: HierarchyLevel; unitId: string; nodes: ConstellationNode[] }>;
  descendantNodes: Map<string, ConstellationNode[]>;
}

export function buildChildrenMap(
  nodes: ConstellationNode[],
  ctx: ExpansionContext,
): ChildrenMapResult {
  const childrenByCluster = new Map<string, ConstellationNode[]>();
  const clusterMeta = new Map<string, { level: HierarchyLevel; unitId: string; nodes: ConstellationNode[] }>();
  const unitNodes = new Map<string, ConstellationNode[]>();

  const scopeNorm = normalizeOkrLevel(ctx.scopeLevel);

  for (const raw of nodes) {
    const node = { ...raw, level: normalizeOkrLevel(raw.level) };
    if (node.id === ctx.scopeCenterId) continue;

    const clusterId = resolveClusterIdForNode(node, scopeNorm);
    if (!clusterId) continue;

    const level = clusterLevelFromId(clusterId);
    if (!level) continue;

    const unitId = clusterId.split('-').slice(2).join('-');
    if (!unitNodes.has(clusterId)) unitNodes.set(clusterId, []);
    unitNodes.get(clusterId)!.push(node);

    const parentKey = parentClusterKeyForNode(node, scopeNorm);
    if (!childrenByCluster.has(parentKey)) childrenByCluster.set(parentKey, []);
    const siblings = childrenByCluster.get(parentKey)!;
    if (!siblings.some((n) => resolveClusterIdForNode(n, scopeNorm) === clusterId)) {
      const rep = pickRepresentative(unitNodes.get(clusterId)!, level);
      siblings.push(rep);
    }
  }

  for (const [clusterId, group] of unitNodes) {
    const level = clusterLevelFromId(clusterId)!;
    const unitId = clusterId.split('-').slice(2).join('-');
    clusterMeta.set(clusterId, { level, unitId, nodes: group });
  }

  const descendantNodes = new Map<string, ConstellationNode[]>();
  const computeDescendants = (clusterId: string): ConstellationNode[] => {
    if (descendantNodes.has(clusterId)) return descendantNodes.get(clusterId)!;
    const meta = clusterMeta.get(clusterId);
    const directChildren = childrenByCluster.get(clusterId) || [];
    const all: ConstellationNode[] = [...(meta?.nodes || [])];
    for (const child of directChildren) {
      const childCluster = resolveClusterIdForNode(child, scopeNorm);
      if (childCluster) {
        all.push(...computeDescendants(childCluster));
      }
    }
    descendantNodes.set(clusterId, all);
    return all;
  };

  for (const clusterId of clusterMeta.keys()) {
    computeDescendants(clusterId);
  }

  return { childrenByCluster, clusterMeta, descendantNodes };
}

function pickRepresentative(nodes: ConstellationNode[], level: HierarchyLevel): ConstellationNode {
  const synthetic = nodes.find((n) => nodeIdToClusterId(n.id));
  if (synthetic) return synthetic;
  const atLevel = nodes.filter((n) => normalizeOkrLevel(n.level) === level);
  const pool = atLevel.length ? atLevel : nodes;
  return pool.reduce((best, n) =>
    (n.final_progress ?? n.progress) > (best.final_progress ?? best.progress) ? n : best,
  );
}

function buildCollapsedCluster(
  clusterId: string,
  meta: { level: HierarchyLevel; unitId: string; nodes: ConstellationNode[] },
  childrenByCluster: Map<string, ConstellationNode[]>,
  descendantNodes: Map<string, ConstellationNode[]>,
  parentClusterId: string | null,
  depth: number,
): CollapsedCluster {
  const directChildClusters = childrenByCluster.get(clusterId) || [];
  const leaves = leafDescendants(descendantNodes.get(clusterId) || meta.nodes);
  const progressSource = leaves.length ? leaves : meta.nodes;
  const avg = avgProgress(progressSource);
  const childLevel = childLevelOf(meta.level);
  const hasSubClusters = directChildClusters.length > 0;
  const employeeCount = meta.nodes.filter((n) => normalizeOkrLevel(n.level) === 'employee').length;
  const hasEmployeeLeaves = childLevel === 'employee' && employeeCount > 0;

  return {
    id: clusterId,
    label: labelForUnit(meta.nodes, meta.level),
    level: meta.level,
    depth,
    childCount: hasSubClusters ? directChildClusters.length : employeeCount,
    descendantCount: (descendantNodes.get(clusterId) || meta.nodes).length,
    avgProgress: avg,
    health: progressToHealth(avg),
    parentClusterId,
    isExpandable:
      childLevel !== null &&
      (hasSubClusters || hasEmployeeLeaves || childLevel !== 'employee'),
    representativeNodeId: pickRepresentative(meta.nodes, meta.level).id,
  };
}

function clusterDepth(clusterId: string, scopeLevel: OKRLevel): number {
  const level = clusterLevelFromId(clusterId);
  if (!level) return 1;
  return LEVEL_RANK[level] - LEVEL_RANK[normalizeOkrLevel(scopeLevel)];
}

export function getVisibleGraph(
  nodes: ConstellationNode[],
  edges: ConstellationEdge[],
  expandedNodeIds: Set<string>,
  scopeCenterId: string,
  scopeLevel: OKRLevel = 'organization',
  scopeId: string | null = null,
): VisibleGraph {
  const scopeNorm = normalizeOkrLevel(scopeLevel);
  const ctx: ExpansionContext = { scopeLevel: scopeNorm, scopeId, scopeCenterId };

  const centerEntry = nodes.find((n) => n.id === scopeCenterId);
  const centerNode =
    centerEntry ||
    resolveScopeCenter(nodes, scopeNorm, scopeId).centerNode;

  if (scopeNorm === 'team') {
    const employees = nodes.filter(
      (n) =>
        normalizeOkrLevel(n.level) === 'employee' &&
        (!scopeId || n.team === scopeId),
    );
    const visibleNodeIds = new Set([scopeCenterId, ...employees.map((e) => e.id)]);
    const visibleEdges = edges.filter(
      (e) => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target),
    );
    return {
      visibleNodes: [centerNode, ...employees],
      visibleEdges,
      clusters: new Map(),
      centerNode,
      scopeCenterId,
      clusterRepresentatives: new Map(),
      expandedLeaves: new Map(),
      ancestorClusterOf: new Map(),
      visibleClusterIds: new Set(),
    };
  }

  const { childrenByCluster, clusterMeta, descendantNodes } = buildChildrenMap(nodes, ctx);

  const clusters = new Map<string, CollapsedCluster>();
  for (const [clusterId, meta] of clusterMeta) {
    const parentKey = parentClusterKeyForNode(meta.nodes[0], scopeLevel);
    const parentId = parentKey === SCOPE_CENTER_KEY ? null : parentKey;
    const depth = Math.max(1, clusterDepth(clusterId, scopeLevel));
    clusters.set(
      clusterId,
      buildCollapsedCluster(clusterId, meta, childrenByCluster, descendantNodes, parentId, depth),
    );
  }

  const visibleNodeIds = new Set<string>([scopeCenterId]);
  const visibleClusterIds = new Set<string>();
  const expandedLeaves = new Map<string, ConstellationNode[]>();
  const clusterRepresentatives = new Map<string, ConstellationNode>();
  const ancestorClusterOf = new Map<string, string | null>();

  ancestorClusterOf.set(scopeCenterId, null);

  const depth1 = childrenByCluster.get(SCOPE_CENTER_KEY) || [];
  const depth1ClusterIds = new Set<string>();
  for (const child of depth1) {
    const cid = resolveClusterIdForNode(child, scopeLevel);
    if (cid) depth1ClusterIds.add(cid);
  }

  const queue: Array<{ clusterId: string; expanded: boolean }> = [];
  for (const cid of depth1ClusterIds) {
    queue.push({ clusterId: cid, expanded: expandedNodeIds.has(cid) });
  }

  for (const cid of depth1ClusterIds) {
    visibleClusterIds.add(cid);
    const meta = clusterMeta.get(cid);
    if (meta) {
      clusterRepresentatives.set(cid, pickRepresentative(meta.nodes, meta.level));
    }
    ancestorClusterOf.set(cid, null);
  }

  const processExpanded = (clusterId: string) => {
    const meta = clusterMeta.get(clusterId);
    if (!meta) return;
    const rep = pickRepresentative(meta.nodes, meta.level);
    visibleNodeIds.add(rep.id);
    clusterRepresentatives.set(clusterId, rep);

    const childLevel = childLevelOf(meta.level);
    const childClusters = childrenByCluster.get(clusterId) || [];
    const childClusterIds = new Set<string>();
    for (const c of childClusters) {
      const ccid = resolveClusterIdForNode(c, scopeLevel);
      if (ccid) childClusterIds.add(ccid);
    }

    if (childLevel === 'employee') {
      const employees = meta.nodes.filter((n) => normalizeOkrLevel(n.level) === 'employee');
      expandedLeaves.set(clusterId, employees);
      for (const emp of employees) {
        visibleNodeIds.add(emp.id);
        ancestorClusterOf.set(emp.id, clusterId);
      }
    }

    for (const ccid of childClusterIds) {
      visibleClusterIds.add(ccid);
      ancestorClusterOf.set(ccid, clusterId);
      const childExpanded = expandedNodeIds.has(ccid);
      if (childExpanded) {
        processExpanded(ccid);
      } else {
        const cmeta = clusterMeta.get(ccid);
        if (cmeta) {
          clusterRepresentatives.set(ccid, pickRepresentative(cmeta.nodes, cmeta.level));
        }
      }
    }
  };

  for (const cid of depth1ClusterIds) {
    if (expandedNodeIds.has(cid)) {
      processExpanded(cid);
    }
  }

  const visibleNodes: ConstellationNode[] = [centerNode];
  for (const id of visibleNodeIds) {
    if (id === scopeCenterId) continue;
    const n = nodes.find((x) => x.id === id);
    if (n) visibleNodes.push(n);
  }

  const nodeToVisibleTarget = new Map<string, string>();
  const registerTarget = (nodeId: string, targetId: string) => {
    nodeToVisibleTarget.set(nodeId, targetId);
  };

  registerTarget(scopeCenterId, scopeCenterId);
  for (const cid of visibleClusterIds) {
    if (!expandedNodeIds.has(cid)) {
      registerTarget(cid, cid);
      const rep = clusterRepresentatives.get(cid);
      if (rep) registerTarget(rep.id, cid);
    } else {
      const rep = clusterRepresentatives.get(cid);
      if (rep) registerTarget(rep.id, rep.id);
    }
  }
  for (const n of visibleNodes) {
    if (!nodeToVisibleTarget.has(n.id)) {
      registerTarget(n.id, n.id);
    }
  }

  const findVisibleAncestor = (nodeId: string): string | null => {
    if (nodeToVisibleTarget.has(nodeId)) return nodeToVisibleTarget.get(nodeId)!;
    const node = nodes.find((n) => n.id === nodeId);
    if (!node) return null;
    const parentKey = parentClusterKeyForNode(node, scopeLevel);
    if (parentKey === SCOPE_CENTER_KEY) return scopeCenterId;
    if (visibleClusterIds.has(parentKey) && !expandedNodeIds.has(parentKey)) {
      return parentKey;
    }
    if (expandedNodeIds.has(parentKey)) {
      const rep = clusterRepresentatives.get(parentKey);
      return rep?.id ?? parentKey;
    }
    const meta = clusterMeta.get(parentKey);
    if (meta) return findVisibleAncestor(meta.nodes[0].id);
    return scopeCenterId;
  };

  const visibleEdges: ConstellationEdge[] = [];
  const edgeKeys = new Set<string>();

  for (const edge of edges) {
    let src = findVisibleAncestor(edge.source);
    let tgt = findVisibleAncestor(edge.target);
    if (!src || !tgt || src === tgt) continue;

    const srcVisible =
      visibleNodeIds.has(src) || visibleClusterIds.has(src);
    const tgtVisible =
      visibleNodeIds.has(tgt) || visibleClusterIds.has(tgt);
    if (!srcVisible || !tgtVisible) continue;

    const key = `${src}->${tgt}:${edge.alignment_type}`;
    if (edgeKeys.has(key)) continue;
    edgeKeys.add(key);

    const retargeted =
      edge.source !== src || edge.target !== tgt;
    visibleEdges.push({
      ...edge,
      source: src,
      target: tgt,
      is_dashed: edge.is_dashed || retargeted,
    });
  }

  return {
    visibleNodes,
    visibleEdges,
    clusters,
    centerNode,
    scopeCenterId,
    clusterRepresentatives,
    expandedLeaves,
    ancestorClusterOf,
    visibleClusterIds,
  };
}

/** All descendant cluster ids for collapseSubtree */
export function getDescendantClusterIds(
  clusterId: string,
  childrenByCluster: Map<string, ConstellationNode[]>,
  scopeLevel: OKRLevel,
): string[] {
  const result: string[] = [];
  const walk = (cid: string) => {
    const children = childrenByCluster.get(cid) || [];
    for (const child of children) {
      const childCid = resolveClusterIdForNode(child, scopeLevel);
      if (childCid && childCid !== cid) {
        result.push(childCid);
        walk(childCid);
      }
    }
  };
  walk(clusterId);
  return result;
}

export function getExpansionBreadcrumbs(
  expandedNodeIds: Set<string>,
  clusters: Map<string, CollapsedCluster>,
  centerLabel: string,
): Array<{ id: string; label: string }> {
  if (!expandedNodeIds.size) return [{ id: SCOPE_CENTER_KEY, label: centerLabel }];

  const expanded = Array.from(expandedNodeIds)
    .map((id) => clusters.get(id))
    .filter(Boolean) as CollapsedCluster[];

  expanded.sort((a, b) => a.depth - b.depth || a.label.localeCompare(b.label));

  const crumbs: Array<{ id: string; label: string }> = [
    { id: SCOPE_CENTER_KEY, label: centerLabel },
  ];

  const path: CollapsedCluster[] = [];
  const pickNext = (parentId: string | null): CollapsedCluster | undefined =>
    expanded.find(
      (c) =>
        c.parentClusterId === parentId &&
        !path.some((p) => p.id === c.id),
    );

  let parent: string | null = null;
  for (;;) {
    const next = pickNext(parent);
    if (!next) break;
    path.push(next);
    parent = next.id;
  }

  for (const c of path) {
    crumbs.push({ id: c.id, label: c.label });
  }

  return crumbs;
}
