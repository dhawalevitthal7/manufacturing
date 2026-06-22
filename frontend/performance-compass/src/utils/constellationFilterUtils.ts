/**
 * Client-side constellation filter helpers
 */

import type {
  ConstellationFilters,
  ConstellationNode,
  ConstellationEdge,
  ViewMode,
} from '@/types/constellation.types';

export function hasActiveFilters(filters: ConstellationFilters): boolean {
  return Boolean(
    filters.levels?.length ||
    filters.regions?.length ||
    filters.plants?.length ||
    filters.departments?.length ||
    filters.functionArea ||
    filters.progressRange ||
    filters.healthStatus?.length ||
    filters.riskLevels?.length ||
    filters.orphanedOnly ||
    filters.strategicOnly ||
    filters.alignmentTypes?.length ||
    filters.searchQuery?.trim()
  );
}

/** Only these filters require a server refetch */
export function needsServerRefetch(filters: ConstellationFilters): boolean {
  return Boolean(
    filters.levels?.length ||
    filters.progressRange ||
    filters.functionArea ||
    filters.groupByFunction,
  );
}

export function applyViewModeFilter(node: ConstellationNode, viewMode: ViewMode): boolean {
  switch (viewMode) {
    case 'strategic':
      return node.strategic_weight >= 4;
    case 'risk':
      return (
        node.risk_level === 'critical' ||
        node.risk_level === 'high' ||
        node.progress < 60 ||
        node.alignment_health === 'critical' ||
        node.alignment_health === 'blocked'
      );
    case 'plant':
      return node.level === 'plant';
    case 'department':
      return node.level === 'department';
    case 'galaxy':
    default:
      return true;
  }
}

export function filterConstellationNodes(
  nodes: ConstellationNode[],
  filters: ConstellationFilters,
  viewMode: ViewMode = 'galaxy',
): ConstellationNode[] {
  return nodes.filter((node) => {
    if (!applyViewModeFilter(node, viewMode)) return false;

    if (filters.levels?.length && !filters.levels.includes(node.level)) return false;
    if (filters.regions?.length && !filters.regions.includes(node.region || '')) return false;
    if (filters.plants?.length && !filters.plants.includes(node.plant || '')) return false;
    if (filters.departments?.length && !filters.departments.includes(node.department || '')) return false;

    if (filters.functionArea && node.function_area !== filters.functionArea) return false;

    if (filters.progressRange) {
      const [min, max] = filters.progressRange;
      const prog = node.final_progress ?? node.progress;
      if (prog < min || prog > max) return false;
    }

    if (filters.healthStatus?.length && !filters.healthStatus.includes(node.alignment_health)) {
      return false;
    }

    if (filters.riskLevels?.length && !filters.riskLevels.includes(node.risk_level)) return false;
    if (filters.orphanedOnly && !node.is_orphaned) return false;
    if (filters.strategicOnly && node.strategic_weight < 4) return false;

    if (filters.searchQuery?.trim()) {
      const q = filters.searchQuery.toLowerCase();
      const matches =
        node.objective.toLowerCase().includes(q) ||
        node.owner_name.toLowerCase().includes(q) ||
        (node.plant_name || node.plant || '').toLowerCase().includes(q) ||
        (node.department_name || node.department || '').toLowerCase().includes(q) ||
        (node.region_name || node.region || '').toLowerCase().includes(q) ||
        (node.entity_name || '').toLowerCase().includes(q);
      if (!matches) return false;
    }

    return true;
  });
}

export interface FilteredGraphResult {
  nodes: ConstellationNode[];
  edges: ConstellationEdge[];
  /** Nodes that directly matched filter criteria (before alignment expansion) */
  matchedCount: number;
  /** Node IDs that directly matched filters */
  matchedIds: Set<string>;
}

/**
 * Filter nodes and keep alignment edges visible.
 * Includes edge partners (parents/children) so cascade lines still render in graph view.
 */
export function filterConstellationGraph(
  nodes: ConstellationNode[],
  edges: ConstellationEdge[],
  filters: ConstellationFilters,
  viewMode: ViewMode = 'galaxy',
  preserveAlignment = true,
): FilteredGraphResult {
  const matched = filterConstellationNodes(nodes, filters, viewMode);
  const matchedIds = new Set(matched.map((n) => n.id));

  if (matchedIds.size === 0) {
    return { nodes: [], edges: [], matchedCount: 0, matchedIds };
  }

  const visibleIds = new Set(matchedIds);

  if (preserveAlignment) {
    for (const edge of edges) {
      if (matchedIds.has(edge.source) || matchedIds.has(edge.target)) {
        visibleIds.add(edge.source);
        visibleIds.add(edge.target);
      }
    }
  }

  const visibleNodes = nodes.filter((n) => visibleIds.has(n.id));
  const visibleEdges = edges.filter((edge) => {
    if (!visibleIds.has(edge.source) || !visibleIds.has(edge.target)) return false;
    if (filters.alignmentTypes?.length && !filters.alignmentTypes.includes(edge.alignment_type)) {
      return false;
    }
    return true;
  });

  return {
    nodes: visibleNodes,
    edges: visibleEdges,
    matchedCount: matched.length,
    matchedIds,
  };
}

/** Map frontend level names to backend API level enum */
export function levelsToApiParam(levels: string[]): string {
  const map: Record<string, string> = {
    employee: 'INDIVIDUAL',
    organization: 'ORGANIZATION',
    region: 'REGION',
    plant: 'PLANT',
    department: 'DEPARTMENT',
    team: 'TEAM',
  };
  return levels.map((l) => map[l.toLowerCase()] || l.toUpperCase()).join(',');
}

/** Human-readable summary of active filters */
export function describeActiveFilters(filters: ConstellationFilters): string {
  const parts: string[] = [];
  if (filters.levels?.length) parts.push(`Levels: ${filters.levels.join(', ')}`);
  if (filters.healthStatus?.length) parts.push(`Health: ${filters.healthStatus.join(', ')}`);
  if (filters.riskLevels?.length) parts.push(`Risk: ${filters.riskLevels.join(', ')}`);
  if (filters.orphanedOnly) parts.push('Orphaned only');
  if (filters.strategicOnly) parts.push('Strategic only');
  if (filters.progressRange) parts.push(`Progress ${filters.progressRange[0]}–${filters.progressRange[1]}%`);
  if (filters.searchQuery?.trim()) parts.push(`Search: "${filters.searchQuery}"`);
  return parts.join(' · ') || 'Filtered view';
}
