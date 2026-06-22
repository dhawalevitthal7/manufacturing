/**
 * Role-scoped radial orbit layout.
 * Center = user's scope (org / region / plant / dept / team).
 * Orbit = child entities; distance from center ∝ progress (higher = closer).
 */

import type {
  CollapsedCluster,
  ConstellationEdge,
  ConstellationNode,
  OKRLevel,
  RoleScopeConfig,
  VisibleGraph,
} from "@/types/constellation.types";
import { clusterLevelFromId } from "@/utils/constellationExpansion";
import { getHealthColor } from "@/utils/nodeColor";

export const ORBIT_RADII = {
  onTrack: 110,
  progressing: 190,
  needsAttention: 270,
} as const;

export type OrbitBand = "onTrack" | "progressing" | "needsAttention";

export function normalizeOkrLevel(level: string): OKRLevel {
  const l = (level || "").toLowerCase();
  if (l === "individual" || l === "employee") return "employee";
  if (l === "organization" || l === "region" || l === "plant" || l === "department" || l === "team") {
    return l;
  }
  return "employee";
}

export function progressToOrbitBand(progress: number): OrbitBand {
  if (progress >= 70) return "onTrack";
  if (progress >= 40) return "progressing";
  return "needsAttention";
}

/** Continuous radius: 100% progress → inner ring, 0% → outer ring */
export function orbitRadiusForProgress(progress: number): number {
  const minR = ORBIT_RADII.onTrack;
  const maxR = ORBIT_RADII.needsAttention;
  const t = Math.max(0, Math.min(100, progress)) / 100;
  return maxR - t * (maxR - minR);
}

export function progressColor(progress: number): string {
  if (progress >= 70) return "#22d3ee";
  if (progress >= 40) return "#fbbf24";
  return "#f87171";
}

export function formatTeamDisplayName(name: string | null | undefined): string {
  if (!name) return "Team";
  const trimmed = name.trim();
  const teamIdx = trimmed.lastIndexOf(" Team ");
  if (teamIdx >= 0) {
    return trimmed.slice(teamIdx + 1);
  }
  return trimmed;
}

export function levelLabel(level: string): string {
  const map: Record<string, string> = {
    organization: "Organization OKR",
    region: "Regional OKR",
    plant: "Plant OKR",
    department: "Department OKR",
    team: "Team OKR",
    employee: "Employee OKR",
  };
  return map[normalizeOkrLevel(level)] || "OKR";
}

export interface PlacedOrbitNode {
  node: ConstellationNode;
  x: number;
  y: number;
  radius: number;
  band: OrbitBand;
  angle: number;
}

export interface ScopedOrbitalOptions {
  scopeConfig: RoleScopeConfig;
  scopeId?: string | null;
  organizationName?: string;
  scopeEntityName?: string;
}

function avgProgress(nodes: ConstellationNode[]): number {
  if (!nodes.length) return 0;
  const sum = nodes.reduce((s, n) => s + (n.final_progress ?? n.progress ?? 0), 0);
  return Math.round(sum / nodes.length);
}

function entityKey(node: ConstellationNode, childLevel: OKRLevel): string | null {
  switch (childLevel) {
    case "region":
      return node.region || null;
    case "plant":
      return node.plant || null;
    case "department":
      return node.department || null;
    case "team":
      if (node.team) return node.team;
      return normalizeOkrLevel(node.level) === "team" ? node.id : null;
    case "employee":
      return node.owner_id || node.owner_name || node.id;
    default:
      return node.id;
  }
}

function entityDisplayName(
  node: ConstellationNode,
  childLevel: OKRLevel,
): string {
  if (node.entity_name) return node.entity_name;
  switch (childLevel) {
    case "region":
      return node.region_name || node.objective;
    case "plant":
      return node.plant_name || node.objective;
    case "department":
      return node.department_name || node.objective;
    case "team":
      return formatTeamDisplayName(node.team_name || node.entity_name || node.objective);
    case "employee":
      return node.owner_name || node.objective;
    default:
      return node.objective;
  }
}

function matchesScopeId(node: ConstellationNode, scopeLevel: OKRLevel, scopeId: string): boolean {
  switch (scopeLevel) {
    case "region":
      return node.region === scopeId || node.id === scopeId;
    case "plant":
      return node.plant === scopeId || node.id === scopeId;
    case "department":
      return node.department === scopeId || node.id === scopeId;
    case "team":
      return node.team === scopeId || node.id === scopeId;
    default:
      return true;
  }
}

function aggregateOrbitEntities(
  nodes: ConstellationNode[],
  childLevel: OKRLevel,
  scopeLevel: OKRLevel,
  scopeId?: string | null,
): ConstellationNode[] {
  const childNorm = childLevel;
  const childLevels: OKRLevel[] =
    childNorm === "employee" ? ["employee"] : [childNorm];

  let candidates = nodes.filter((n) => childLevels.includes(normalizeOkrLevel(n.level)));

  // Department view: roll individual OKRs into their team orbit bucket
  if (childNorm === "team") {
    const teamNodes = nodes.filter((n) => normalizeOkrLevel(n.level) === "team");
    const individualsWithTeam = nodes.filter(
      (n) => normalizeOkrLevel(n.level) === "employee" && n.team,
    );
    candidates = [...teamNodes, ...individualsWithTeam];
  }

  if (scopeId && scopeLevel !== "organization") {
    candidates = candidates.filter((n) => {
      if (scopeLevel === "region") return n.region === scopeId;
      if (scopeLevel === "plant") return n.plant === scopeId;
      if (scopeLevel === "department") return n.department === scopeId;
      if (scopeLevel === "team") return n.team === scopeId;
      return true;
    });
  }

  // Roll up plants into regions (CEO view when no REGION OKRs)
  if (!candidates.length && childNorm === "region") {
    const plants = nodes.filter(
      (n) => normalizeOkrLevel(n.level) === "plant" && n.region,
    );
    const byRegion = new Map<string, ConstellationNode[]>();
    for (const p of plants) {
      const rid = p.region!;
      if (!byRegion.has(rid)) byRegion.set(rid, []);
      byRegion.get(rid)!.push(p);
    }
    return Array.from(byRegion.entries()).map(([rid, group]) => {
      const progress = avgProgress(group);
      const name = group[0].region_name || "Region";
      return {
        ...group[0],
        id: `orbit-region-${rid}`,
        objective: name,
        entity_name: name,
        region: rid,
        progress,
        final_progress: progress,
        level: "region" as OKRLevel,
      };
    });
  }

  // Region head: orbit plants (level plant) scoped to this region
  if (!candidates.length && childNorm === "plant" && scopeLevel === "region" && scopeId) {
    const plants = nodes.filter(
      (n) =>
        normalizeOkrLevel(n.level) === "plant" &&
        (n.region === scopeId || n.plant),
    );
    if (plants.length) {
      candidates = plants;
    }
  }

  // Plant head: orbit departments under this plant
  if (!candidates.length && childNorm === "department" && scopeLevel === "plant" && scopeId) {
    candidates = nodes.filter(
      (n) =>
        normalizeOkrLevel(n.level) === "department" &&
        (n.plant === scopeId || n.department),
    );
  }

  // Dept head: orbit teams under this department
  if (!candidates.length && childNorm === "team" && scopeLevel === "department" && scopeId) {
    candidates = nodes.filter(
      (n) =>
        normalizeOkrLevel(n.level) === "team" &&
        (n.department === scopeId || n.team),
    );
  }

  // Exclude scope-level nodes from orbit (they belong at center)
  candidates = candidates.filter((n) => normalizeOkrLevel(n.level) === childNorm);

  const groups = new Map<string, ConstellationNode[]>();
  for (const n of candidates) {
    const key = entityKey(n, childNorm);
    if (key === null) continue;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(n);
  }

  return Array.from(groups.entries()).map(([key, group]) => {
    const rep = group.reduce((best, n) =>
      (n.final_progress ?? n.progress) > (best.final_progress ?? best.progress) ? n : best,
    );
    const progress = avgProgress(group);
    const name = entityDisplayName(rep, childNorm);
    return {
      ...rep,
      id: group.length === 1 ? rep.id : `orbit-${childNorm}-${key}`,
      objective: name,
      entity_name: name,
      progress,
      final_progress: progress,
      own_progress: progress,
      level: childNorm,
    };
  });
}

function pickCenterNode(
  nodes: ConstellationNode[],
  scopeLevel: OKRLevel,
  scopeId?: string | null,
): ConstellationNode | null {
  const scopeNorm = scopeLevel;
  let candidates = nodes.filter((n) => normalizeOkrLevel(n.level) === scopeNorm);

  if (scopeId && scopeNorm !== "organization") {
    const scoped = candidates.filter((n) => matchesScopeId(n, scopeNorm, scopeId));
    if (scoped.length) candidates = scoped;
  }

  if (!candidates.length) return null;

  return candidates.reduce((best, n) =>
    (n.strategic_weight ?? 0) > (best.strategic_weight ?? 0) ? n : best,
  );
}

function buildSyntheticCenter(
  label: string,
  progress: number,
  level: OKRLevel,
): ConstellationNode {
  return {
    id: `center-${level}`,
    objective: label,
    entity_name: label,
    owner_name: "",
    owner_role: "",
    level,
    progress,
    own_progress: progress,
    alignment_contribution: 0,
    final_progress: progress,
    alignment_health: progress >= 70 ? "healthy" : progress >= 40 ? "needs_attention" : "critical",
    confidence_score: 50,
    risk_level: progress < 40 ? "high" : "medium",
    trend_status: progress >= 60 ? "on_track" : "behind",
    strategic_weight: 5,
    is_orphaned: false,
  };
}

/**
 * Role-scoped layout: center = scope entity, orbit = child entities by progress.
 */
export function buildScopedOrbitalLayout(
  nodes: ConstellationNode[],
  centerX: number,
  centerY: number,
  options: ScopedOrbitalOptions,
): { center: ConstellationNode | null; orbit: PlacedOrbitNode[] } {
  const normalized = nodes.map((n) => ({
    ...n,
    level: normalizeOkrLevel(n.level),
  }));

  const scopeLevel = normalizeOkrLevel(options.scopeConfig.scopeLevel);
  const childLevel = normalizeOkrLevel(options.scopeConfig.childLevel);
  const { scopeId, organizationName, scopeEntityName } = options;

  let center = pickCenterNode(normalized, scopeLevel, scopeId);

  const orbitEntities = aggregateOrbitEntities(
    normalized,
    childLevel,
    scopeLevel,
    scopeId,
  );

  if (!center && scopeId && scopeLevel !== 'organization') {
    const syntheticId = `center-${scopeLevel}-${scopeId}`;
    center = normalized.find((n) => n.id === syntheticId) ?? null;
  }

  if (!center) {
    const centerLabel =
      scopeEntityName ||
      (scopeLevel === "organization"
        ? organizationName || "Organization"
        : options.scopeConfig.centerLabel.replace(" OKR", ""));
    const progress = orbitEntities.length ? avgProgress(orbitEntities) : 0;
    center = buildSyntheticCenter(centerLabel, progress, scopeLevel);
  } else if (scopeEntityName) {
    center = { ...center, objective: scopeEntityName, entity_name: scopeEntityName };
  }

  const count = orbitEntities.length || 1;
  const orbit: PlacedOrbitNode[] = orbitEntities.map((node, i) => {
    const progress = node.final_progress ?? node.progress ?? 0;
    const angle = (2 * Math.PI * i) / count - Math.PI / 2;
    const r = orbitRadiusForProgress(progress);
    return {
      node,
      x: centerX + r * Math.cos(angle),
      y: centerY + r * Math.sin(angle),
      radius: r,
      band: progressToOrbitBand(progress),
      angle,
    };
  });

  return { center, orbit };
}

const LEVEL_RANK: Record<OKRLevel, number> = {
  organization: 0,
  region: 1,
  plant: 2,
  department: 3,
  team: 4,
  employee: 5,
};

/**
 * Adaptive layout when filters change the visible hierarchy.
 * Picks the highest-level filtered node as center; others orbit by progress.
 */
export function buildFilteredOrbitalLayout(
  nodes: ConstellationNode[],
  centerX: number,
  centerY: number,
): { center: ConstellationNode | null; orbit: PlacedOrbitNode[] } {
  const normalized = nodes.map((n) => ({ ...n, level: normalizeOkrLevel(n.level) }));
  if (!normalized.length) return { center: null, orbit: [] };
  if (normalized.length === 1) {
    return {
      center: normalized[0],
      orbit: [],
    };
  }

  const sorted = [...normalized].sort(
    (a, b) => LEVEL_RANK[normalizeOkrLevel(a.level)] - LEVEL_RANK[normalizeOkrLevel(b.level)],
  );
  const center = sorted[0];
  const orbitEntities = sorted.slice(1);

  const count = orbitEntities.length || 1;
  const orbit: PlacedOrbitNode[] = orbitEntities.map((node, i) => {
    const progress = node.final_progress ?? node.progress ?? 0;
    const angle = (2 * Math.PI * i) / count - Math.PI / 2;
    const r = orbitRadiusForProgress(progress);
    return {
      node,
      x: centerX + r * Math.cos(angle),
      y: centerY + r * Math.sin(angle),
      radius: r,
      band: progressToOrbitBand(progress),
      angle,
    };
  });

  return { center, orbit };
}

export const EXPAND_RING_BASE = 140;
export const EXPAND_RING_STEP = 110;
const HUB_SCALE = 0.6;

/** Per-depth orbit band: higher progress → closer to parent (min distance). */
const ALIGNMENT_BANDS: Record<number, { min: number; max: number }> = {
  1: { min: 130, max: 280 },
  2: { min: 72, max: 148 },
  3: { min: 58, max: 118 },
  4: { min: 48, max: 100 },
  5: { min: 40, max: 86 },
};

const MIN_ANGLE_SEP = 0.52;
const HUB_PULL_FACTOR = 0.32;

/**
 * Radial distance from parent hub based on alignment progress.
 * 100% progress → inner orbit (close), 0% → outer orbit (drifted).
 */
export function alignmentOrbitDistance(progress: number, depth: number): number {
  const band = ALIGNMENT_BANDS[Math.min(Math.max(depth, 1), 5)] ?? ALIGNMENT_BANDS[5];
  const t = 1 - Math.max(0, Math.min(100, progress)) / 100;
  return band.min + t * (band.max - band.min);
}

export function alignmentOrbitBand(depth: number): { min: number; max: number } {
  return ALIGNMENT_BANDS[Math.min(Math.max(depth, 1), 5)] ?? ALIGNMENT_BANDS[5];
}

export type ExpandableNodeKind =
  | "center"
  | "cluster-collapsed"
  | "cluster-hub"
  | "leaf";

export interface PlacedExpandableNode {
  id: string;
  kind: ExpandableNodeKind;
  x: number;
  y: number;
  angle: number;
  depth: number;
  scale: number;
  cluster?: CollapsedCluster;
  node?: ConstellationNode;
  parentId: string | null;
  dimmed: boolean;
  displayColor: string;
  displaySize: number;
  label: string;
  progress: number;
  isExpandable: boolean;
  isExpanded: boolean;
  contributionScore?: number;
  parentX?: number;
  parentY?: number;
  orbitDistance?: number;
  sectorAngle?: number;
  sectorWidth?: number;
  levelAccent?: string;
}

export interface ExpandableOrbitalLayout {
  center: PlacedExpandableNode | null;
  placed: PlacedExpandableNode[];
  edges: Array<{
    source: string;
    target: string;
    color: string;
    dashed: boolean;
    contributionScore?: number;
  }>;
}

function expandableNodeSize(kind: ExpandableNodeKind, level?: OKRLevel): number {
  if (kind === "center") return 58;
  if (kind === "cluster-collapsed") return 32;
  if (kind === "cluster-hub") return 20;
  const sizes: Record<string, number> = {
    region: 28,
    plant: 26,
    department: 24,
    team: 22,
    employee: 18,
  };
  return sizes[level || "employee"] ?? 18;
}

/** Spread child angles with minimum separation to avoid collinear stacking. */
function distributeChildAngles(
  centerAngle: number,
  sectorWidth: number,
  count: number,
  depth: number,
): number[] {
  if (count <= 0) return [];
  if (count === 1) {
    const offset = (depth % 2 === 0 ? 1 : -1) * Math.min(0.35, sectorWidth * 0.22);
    return [centerAngle + offset];
  }
  const needed = count * MIN_ANGLE_SEP;
  const spread = Math.max(sectorWidth * 0.88, needed);
  const start = centerAngle - spread / 2;
  return Array.from({ length: count }, (_, i) =>
    start + (i / (count - 1)) * spread,
  );
}

function placeRelativeToParent(
  parentX: number,
  parentY: number,
  centerAngle: number,
  sectorWidth: number,
  index: number,
  count: number,
  distance: number,
  depth: number,
  subRing = 0,
): { x: number; y: number; angle: number } {
  const angles = distributeChildAngles(centerAngle, sectorWidth, count, depth);
  const angle = angles[index] ?? centerAngle;
  const subOffset = subRing * 36;
  const d = distance + subOffset;
  return {
    x: parentX + d * Math.cos(angle),
    y: parentY + d * Math.sin(angle),
    angle,
  };
}

function pullTowardParent(
  x: number,
  y: number,
  parentX: number,
  parentY: number,
  factor: number,
): { x: number; y: number } {
  return {
    x: x + (parentX - x) * factor,
    y: y + (parentY - y) * factor,
  };
}

function needsSubRing(count: number, sectorWidth: number): number {
  const slots = Math.floor(sectorWidth / MIN_ANGLE_SEP);
  if (count <= slots) return 0;
  if (count <= slots * 2) return 1;
  return 2;
}

function resolveCollisions(nodes: PlacedExpandableNode[], minGap = 44, passes = 5) {
  for (let p = 0; p < passes; p++) {
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i];
        const b = nodes[j];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.hypot(dx, dy) || 0.001;
        const need =
          a.displaySize * a.scale + b.displaySize * b.scale + minGap;
        if (dist < need) {
          const push = (need - dist) / 2;
          const nx = dx / dist;
          const ny = dy / dist;
          if (a.kind !== "center") {
            a.x -= nx * push;
            a.y -= ny * push;
          }
          if (b.kind !== "center") {
            b.x += nx * push;
            b.y += ny * push;
          }
        }
      }
    }
  }
}

/** Level accent for labels / rims (mockup-style distinct hierarchy). */
export function levelAccentColor(level?: string): string {
  const map: Record<string, string> = {
    region: "#38bdf8",
    plant: "#2dd4bf",
    department: "#a78bfa",
    team: "#fbbf24",
    employee: "#f472b6",
    organization: "#22d3ee",
  };
  return map[(level || "").toLowerCase()] ?? "#94a3b8";
}

/**
 * Depth-based ring layout with sector wedges for progressive expansion.
 */
export function buildExpandableOrbitalLayout(
  visibleGraph: VisibleGraph,
  expandedNodeIds: Set<string>,
  centerX: number,
  centerY: number,
  edges: ConstellationEdge[] = [],
  dimAncestorSiblings = true,
): ExpandableOrbitalLayout {
  const {
    clusters,
    centerNode,
    scopeCenterId,
    clusterRepresentatives,
    expandedLeaves,
    visibleClusterIds,
  } = visibleGraph;

  if (!centerNode) {
    return { center: null, placed: [], edges: [] };
  }

  const centerProgress = centerNode.final_progress ?? centerNode.progress ?? 0;
  const center: PlacedExpandableNode = {
    id: scopeCenterId,
    kind: "center",
    x: centerX,
    y: centerY,
    angle: 0,
    depth: 0,
    scale: 1,
    parentId: null,
    dimmed: false,
    node: centerNode,
    displayColor: getHealthColor(centerNode.alignment_health),
    displaySize: expandableNodeSize("center"),
    label: centerNode.entity_name || centerNode.objective,
    progress: centerProgress,
    isExpandable: false,
    isExpanded: false,
  };

  const placed: PlacedExpandableNode[] = [];
  const depth1Clusters = Array.from(clusters.values()).filter(
    (c) => c.depth === 1 && visibleClusterIds.has(c.id),
  );

  if (!depth1Clusters.length) {
    const directLeaves = visibleGraph.visibleNodes.filter((n) => n.id !== scopeCenterId);
    const count = Math.max(directLeaves.length, 1);
    directLeaves.forEach((node, i) => {
      const angle = (2 * Math.PI * i) / count - Math.PI / 2;
      const progress = node.final_progress ?? node.progress ?? 0;
      const orbitDistance = alignmentOrbitDistance(progress, 1);
      placed.push({
        id: node.id,
        kind: "leaf",
        x: centerX + orbitDistance * Math.cos(angle),
        y: centerY + orbitDistance * Math.sin(angle),
        angle,
        depth: 1,
        scale: 1,
        node,
        parentId: scopeCenterId,
        parentX: centerX,
        parentY: centerY,
        orbitDistance,
        sectorAngle: angle,
        dimmed: false,
        displayColor: getHealthColor(node.alignment_health),
        displaySize: expandableNodeSize("leaf", normalizeOkrLevel(node.level)),
        label: node.owner_name || node.objective,
        progress,
        isExpandable: false,
        isExpanded: false,
      });
    });
    return { center, placed, edges: [] };
  }

  const depth1Count = Math.max(depth1Clusters.length, 1);
  const sectorWidth = (2 * Math.PI) / depth1Count;

  const nodeAngles = new Map<string, number>();
  const nodeSectors = new Map<string, number>();

  const hasExpanded = expandedNodeIds.size > 0;

  depth1Clusters.forEach((cluster, i) => {
    const angle = (2 * Math.PI * i) / depth1Count - Math.PI / 2;
    const orbitDistance = alignmentOrbitDistance(cluster.avgProgress, 1);
    const x = centerX + orbitDistance * Math.cos(angle);
    const y = centerY + orbitDistance * Math.sin(angle);
    const isExpanded = expandedNodeIds.has(cluster.id);
    const dimmed =
      dimAncestorSiblings &&
      hasExpanded &&
      !isExpanded &&
      !Array.from(expandedNodeIds).some((eid) => {
        let cur: string | null = eid;
        while (cur) {
          const c = clusters.get(cur);
          if (cur === cluster.id) return true;
          cur = c?.parentClusterId ?? null;
        }
        return false;
      });

    nodeAngles.set(cluster.id, angle);
    nodeSectors.set(cluster.id, sectorWidth);

    if (!isExpanded) {
      placed.push({
        id: cluster.id,
        kind: "cluster-collapsed",
        x,
        y,
        angle,
        depth: 1,
        scale: 1,
        cluster,
        parentId: scopeCenterId,
        parentX: centerX,
        parentY: centerY,
        orbitDistance,
        sectorAngle: angle,
        sectorWidth,
        dimmed,
        displayColor: getHealthColor(cluster.health),
        displaySize: expandableNodeSize("cluster-collapsed"),
        label: cluster.label,
        progress: cluster.avgProgress,
        isExpandable: cluster.isExpandable,
        isExpanded: false,
        levelAccent: levelAccentColor(cluster.level),
      });
    } else {
      const rep = clusterRepresentatives.get(cluster.id);
      const hubPos = pullTowardParent(x, y, centerX, centerY, HUB_PULL_FACTOR);
      placed.push({
        id: cluster.id,
        kind: "cluster-hub",
        x: hubPos.x,
        y: hubPos.y,
        angle,
        depth: 1,
        scale: HUB_SCALE,
        cluster,
        node: rep,
        parentId: scopeCenterId,
        parentX: centerX,
        parentY: centerY,
        orbitDistance,
        sectorAngle: angle,
        sectorWidth,
        levelAccent: levelAccentColor(cluster.level),
        dimmed: false,
        displayColor: getHealthColor(cluster.health),
        displaySize: expandableNodeSize("cluster-hub"),
        label: cluster.label,
        progress: cluster.avgProgress,
        isExpandable: cluster.isExpandable,
        isExpanded: true,
      });
      layoutClusterChildren(
        cluster.id,
        hubPos.x,
        hubPos.y,
        angle,
        sectorWidth,
        2,
        clusters,
        visibleClusterIds,
        expandedNodeIds,
        clusterRepresentatives,
        expandedLeaves,
        placed,
        nodeAngles,
        nodeSectors,
        dimAncestorSiblings,
        hasExpanded,
      );
    }
  });

  const layoutEdges: ExpandableOrbitalLayout["edges"] = [];
  const posById = new Map<string, PlacedExpandableNode>();
  posById.set(center.id, center);
  for (const p of placed) posById.set(p.id, p);

  for (const edge of edges) {
    const src = typeof edge.source === "string" ? edge.source : edge.source;
    const tgt = typeof edge.target === "string" ? edge.target : edge.target;
    const from = posById.get(src);
    const to = posById.get(tgt);
    if (!from || !to) continue;
    layoutEdges.push({
      source: src,
      target: tgt,
      color: progressColor(edge.contribution_score ?? 50),
      dashed: !!edge.is_dashed,
      contributionScore: edge.contribution_score,
    });
  }

  for (const p of placed) {
    if (p.parentId && p.parentId !== scopeCenterId) {
      const parent = posById.get(p.parentId);
      if (parent) {
        layoutEdges.push({
          source: p.parentId,
          target: p.id,
          color: p.displayColor,
          dashed: p.node?.is_orphaned ?? false,
        });
      }
    } else if (p.parentId === scopeCenterId && p.kind !== "cluster-collapsed") {
      layoutEdges.push({
        source: scopeCenterId,
        target: p.id,
        color: p.displayColor,
        dashed: false,
      });
    }
  }

  for (const p of placed) {
    if (p.parentId === scopeCenterId && p.kind === "cluster-collapsed") {
      layoutEdges.push({
        source: scopeCenterId,
        target: p.id,
        color: p.displayColor,
        dashed: false,
      });
    }
  }

  resolveCollisions(placed, 56, 8);

  return { center, placed, edges: layoutEdges };
}

function layoutClusterChildren(
  parentClusterId: string,
  parentX: number,
  parentY: number,
  parentAngle: number,
  parentSector: number,
  depth: number,
  clusters: Map<string, CollapsedCluster>,
  visibleClusterIds: Set<string>,
  expandedNodeIds: Set<string>,
  clusterRepresentatives: Map<string, ConstellationNode>,
  expandedLeaves: Map<string, ConstellationNode[]>,
  placed: PlacedExpandableNode[],
  nodeAngles: Map<string, number>,
  nodeSectors: Map<string, number>,
  dimSiblings: boolean,
  hasExpanded: boolean,
) {
  const childSector = parentSector * 0.85;

  const childClusters = Array.from(clusters.values()).filter(
    (c) => c.parentClusterId === parentClusterId && visibleClusterIds.has(c.id),
  );
  const leaves = expandedLeaves.get(parentClusterId) || [];

  const items: Array<
    | { type: "cluster"; cluster: CollapsedCluster; progress: number }
    | { type: "leaf"; node: ConstellationNode; progress: number }
  > = [
    ...childClusters.map((c) => ({
      type: "cluster" as const,
      cluster: c,
      progress: c.avgProgress,
    })),
    ...leaves.map((n) => ({
      type: "leaf" as const,
      node: n,
      progress: n.final_progress ?? n.progress ?? 0,
    })),
  ];

  const count = items.length;
  const subRingCount = needsSubRing(count, childSector);
  const perRing = subRingCount > 0 ? Math.ceil(count / (subRingCount + 1)) : count;

  items.forEach((item, i) => {
    const orbitDistance = alignmentOrbitDistance(item.progress, depth);
    const ringIndex = subRingCount > 0 ? Math.floor(i / perRing) : 0;
    const idxInRing = subRingCount > 0 ? i % perRing : i;
    const countInRing = subRingCount > 0
      ? Math.min(perRing, count - ringIndex * perRing)
      : count;

    const pos = placeRelativeToParent(
      parentX,
      parentY,
      parentAngle,
      childSector,
      idxInRing,
      countInRing,
      orbitDistance,
      depth,
      ringIndex,
    );

    if (item.type === "cluster") {
      const cluster = item.cluster;
      const isExpanded = expandedNodeIds.has(cluster.id);
      const dimmed =
        dimSiblings &&
        hasExpanded &&
        !isExpanded &&
        cluster.parentClusterId !== parentClusterId;

      nodeAngles.set(cluster.id, pos.angle);
      nodeSectors.set(cluster.id, childSector);

      if (!isExpanded) {
        placed.push({
          id: cluster.id,
          kind: "cluster-collapsed",
          x: pos.x,
          y: pos.y,
          angle: pos.angle,
          depth,
          scale: 1,
          cluster,
          parentId: parentClusterId,
          parentX,
          parentY,
          orbitDistance,
          sectorAngle: parentAngle,
          sectorWidth: childSector,
          dimmed,
          displayColor: getHealthColor(cluster.health),
          displaySize: expandableNodeSize("cluster-collapsed"),
          label: cluster.label,
          progress: cluster.avgProgress,
          isExpandable: cluster.isExpandable,
          isExpanded: false,
          levelAccent: levelAccentColor(cluster.level),
        });
      } else {
        const rep = clusterRepresentatives.get(cluster.id);
        const hubPos = pullTowardParent(pos.x, pos.y, parentX, parentY, HUB_PULL_FACTOR);
        placed.push({
          id: cluster.id,
          kind: "cluster-hub",
          x: hubPos.x,
          y: hubPos.y,
          angle: pos.angle,
          depth,
          scale: HUB_SCALE,
          cluster,
          node: rep,
          parentId: parentClusterId,
          parentX,
          parentY,
          orbitDistance,
          sectorAngle: parentAngle,
          sectorWidth: childSector,
          levelAccent: levelAccentColor(cluster.level),
          dimmed: false,
          displayColor: getHealthColor(cluster.health),
          displaySize: expandableNodeSize("cluster-hub"),
          label: cluster.label,
          progress: cluster.avgProgress,
          isExpandable: cluster.isExpandable,
          isExpanded: true,
        });
        layoutClusterChildren(
          cluster.id,
          hubPos.x,
          hubPos.y,
          pos.angle,
          childSector,
          depth + 1,
          clusters,
          visibleClusterIds,
          expandedNodeIds,
          clusterRepresentatives,
          expandedLeaves,
          placed,
          nodeAngles,
          nodeSectors,
          dimSiblings,
          hasExpanded,
        );
      }
    } else {
      const node = item.node;
      placed.push({
        id: node.id,
        kind: "leaf",
        x: pos.x,
        y: pos.y,
        angle: pos.angle,
        depth,
        scale: 1,
        node,
        parentId: parentClusterId,
        parentX,
        parentY,
        orbitDistance,
        sectorAngle: parentAngle,
        sectorWidth: childSector,
        dimmed: false,
        displayColor: getHealthColor(node.alignment_health),
        displaySize: expandableNodeSize("leaf", normalizeOkrLevel(node.level)),
        label: node.owner_name || node.objective,
        progress: item.progress,
        isExpandable: false,
        isExpanded: false,
      });
    }
  });
}

/** @deprecated Use buildScopedOrbitalLayout with scopeConfig */
export function buildOrbitalLayout(
  nodes: ConstellationNode[],
  centerX: number,
  centerY: number,
): { center: ConstellationNode | null; orbit: PlacedOrbitNode[] } {
  return buildScopedOrbitalLayout(nodes, centerX, centerY, {
    scopeConfig: {
      title: "Organization Alignment",
      subtitle: "",
      centerLabel: "Organization OKR",
      orbitLabel: "Regions",
      scopeLevel: "organization",
      childLevel: "region",
      icon: "🌍",
    },
  });
}
