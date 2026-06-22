/**
 * OKR Constellation Store - Zustand State Management
 * ====================================================
 * Centralized state management for constellation visualization
 */

import { create } from 'zustand';
import {
  ConstellationState,
  ConstellationNode,
  ConstellationEdge,
  ConstellationFilters,
  ViewMode,
  DisplayMode,
  GraphNode,
  GraphEdge,
  OKRLevel,
} from '@/types/constellation.types';
import {
  buildChildrenMap,
  getDescendantClusterIds,
  SCOPE_CENTER_KEY,
} from '@/utils/constellationExpansion';
import { getFunctionAreaColor } from '@/utils/functionArea';

const createInitialState = () => ({
  nodes: [],
  edges: [],
  graphNodes: new Map<string, GraphNode>(),
  graphEdges: [],
  viewMode: 'galaxy' as ViewMode,
  displayMode: 'orbit' as DisplayMode,
  drillDownStack: [] as Array<{ scopeLevel: string; scopeId: string; label: string }>,
  selectedNodeId: null,
  hoveredNodeId: null,
  focusedNodeId: null,
  filters: {},
  showDetailPanel: false,
  showInsightsPanel: false,
  showFiltersPanel: false,
  isSimulating: true,
  graphCenter: { x: 0, y: 0 },
  zoom: 1,
  expandedNodeIds: new Set<string>(),
  expansionScopeLevel: 'organization' as OKRLevel,
  expansionScopeCenterId: '',
});

export const useConstellationStore = create<ConstellationState>((set, get) => ({
  ...createInitialState(),

  // Data Actions
  setNodes: (nodes: ConstellationNode[]) => {
    const graphNodes = new Map<string, GraphNode>();
    nodes.forEach((node) => {
      const baseColor = node.function_area
        ? getFunctionAreaColor(node.function_area)
        : getNodeColor(node.alignment_health, node.progress);
      graphNodes.set(node.id, {
        ...node,
        displaySize: calculateNodeSize(node.level, node.strategic_weight),
        displayColor: baseColor,
        glowColor: node.function_area
          ? `${getFunctionAreaColor(node.function_area)}88`
          : getGlowColor(node.alignment_health),
      });
    });
    set({ nodes, graphNodes, expandedNodeIds: new Set<string>() });
  },

  setEdges: (edges: ConstellationEdge[]) => {
    const graphEdges = edges.map((edge) => ({
      ...edge,
      displayWidth: calculateEdgeWidth(edge.contribution_weight),
      displayColor: getEdgeColor(edge.alignment_type, edge.contribution_score),
      displayDash:
        edge.edge_type === 'FUNCTIONAL' || edge.is_dashed
          ? [6, 4]
          : edge.is_broken
            ? [5, 5]
            : undefined,
    }));
    set({ edges, graphEdges });
  },

  // UI Actions
  setViewMode: (viewMode: ViewMode) => set({ viewMode }),

  setDisplayMode: (displayMode: DisplayMode) => set({ displayMode }),

  pushDrillDown: (entry) => {
    set((state) => ({ drillDownStack: [...state.drillDownStack, entry] }));
  },

  popDrillDown: () => {
    set((state) => ({ drillDownStack: state.drillDownStack.slice(0, -1) }));
  },

  resetDrillDown: () => set({ drillDownStack: [] }),

  selectNode: (nodeId: string | null) => {
    set({ selectedNodeId: nodeId, showDetailPanel: !!nodeId });
  },

  hoverNode: (nodeId: string | null) => {
    set({ hoveredNodeId: nodeId });
  },

  focusNode: (nodeId: string | null) => {
    set({ focusedNodeId: nodeId });
  },

  updateFilters: (filters: Partial<ConstellationFilters>) => {
    const current = get().filters;
    set({ filters: { ...current, ...filters } });
  },

  setFilters: (filters: ConstellationFilters) => {
    set({ filters });
  },

  toggleDetailPanel: () => {
    set((state) => ({ showDetailPanel: !state.showDetailPanel }));
  },

  toggleInsightsPanel: () => {
    set((state) => ({ showInsightsPanel: !state.showInsightsPanel }));
  },

  toggleFiltersPanel: () => {
    set((state) => ({ showFiltersPanel: !state.showFiltersPanel }));
  },

  setSimulating: (isSimulating: boolean) => {
    set({ isSimulating });
  },

  setZoom: (zoom: number) => {
    set({ zoom: Math.max(0.1, Math.min(5, zoom)) });
  },

  toggleNodeExpansion: (clusterId: string) => {
    if (clusterId === SCOPE_CENTER_KEY) return;
    set((state) => {
      const ctx = {
        scopeLevel: state.expansionScopeLevel,
        scopeId: null,
        scopeCenterId: state.expansionScopeCenterId,
      };
      const { childrenByCluster } = buildChildrenMap(state.nodes, ctx);
      const next = new Set(state.expandedNodeIds);
      if (next.has(clusterId)) {
        next.delete(clusterId);
        for (const desc of getDescendantClusterIds(clusterId, childrenByCluster, state.expansionScopeLevel)) {
          next.delete(desc);
        }
      } else {
        next.add(clusterId);
      }
      return { expandedNodeIds: next };
    });
  },

  collapseAll: () => set({ expandedNodeIds: new Set<string>() }),

  collapseSubtree: (clusterId: string) => {
    set((state) => {
      const ctx = {
        scopeLevel: state.expansionScopeLevel,
        scopeId: null,
        scopeCenterId: state.expansionScopeCenterId,
      };
      const { childrenByCluster } = buildChildrenMap(state.nodes, ctx);
      const next = new Set(state.expandedNodeIds);
      next.delete(clusterId);
      for (const desc of getDescendantClusterIds(clusterId, childrenByCluster, state.expansionScopeLevel)) {
        next.delete(desc);
      }
      return { expandedNodeIds: next };
    });
  },

  resetExpansion: () => set({ expandedNodeIds: new Set<string>() }),

  setExpandedNodeIds: (ids: Set<string>) => set({ expandedNodeIds: ids }),

  setExpansionContext: (scopeLevel: OKRLevel, scopeCenterId: string) => {
    set({ expansionScopeLevel: scopeLevel, expansionScopeCenterId: scopeCenterId });
  },
}));

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

export const calculateNodeSize = (level: string, weight: number = 1): number => {
  const baseSizes: Record<string, number> = {
    organization: 60,
    region: 48,
    plant: 38,
    department: 30,
    team: 24,
    employee: 18,
  };
  const base = baseSizes[level] || 20;
  return base * (1 + (weight - 1) * 0.15); // Weight 1-5 gives 1-1.6x multiplier
};

export const getNodeColor = (health: string, progress: number): string => {
  if (health === 'healthy' || progress >= 80) {
    return '#10b981'; // Green
  } else if (health === 'needs_attention' || progress >= 60) {
    return '#f59e0b'; // Amber
  } else if (health === 'critical' || progress >= 40) {
    return '#f97316'; // Orange
  } else if (health === 'blocked' || progress < 40) {
    return '#ef4444'; // Red
  }
  return '#6b7280'; // Gray (orphaned)
};

export const getGlowColor = (health: string): string => {
  const colors: Record<string, string> = {
    healthy: 'rgba(16, 185, 129, 0.5)',
    needs_attention: 'rgba(245, 158, 11, 0.5)',
    critical: 'rgba(249, 115, 22, 0.5)',
    blocked: 'rgba(239, 68, 68, 0.5)',
  };
  return colors[health] || 'rgba(107, 114, 128, 0.5)';
};

export const getEdgeColor = (alignmentType: string, score: number): string => {
  const baseAlpha = Math.max(0.3, score / 100);

  const colors: Record<string, string> = {
    strategic: `rgba(34, 211, 238, ${baseAlpha})`, // Cyan
    operational: `rgba(34, 197, 94, ${baseAlpha})`, // Green
    support: `rgba(168, 85, 247, ${baseAlpha})`, // Purple
    dependency: `rgba(249, 115, 22, ${baseAlpha})`, // Orange
    'cross-functional': `rgba(236, 72, 153, ${baseAlpha})`, // Pink
  };

  return colors[alignmentType] || `rgba(107, 114, 128, ${baseAlpha})`;
};

export const calculateEdgeWidth = (weight: number): number => {
  return Math.max(0.5, weight * 0.8); // Weight 1-5 = thickness 0.8-4
};

// Selectors
export const selectFilteredNodes = (state: ConstellationState): ConstellationNode[] => {
  const { nodes, filters } = state;

  return nodes.filter((node) => {
    // Level filter
    if (filters.levels?.length && !filters.levels.includes(node.level)) {
      return false;
    }

    // Region filter
    if (filters.regions?.length && !filters.regions.includes(node.region || '')) {
      return false;
    }

    // Plant filter
    if (filters.plants?.length && !filters.plants.includes(node.plant || '')) {
      return false;
    }

    // Department filter
    if (filters.departments?.length && !filters.departments.includes(node.department || '')) {
      return false;
    }

    if (filters.functionArea && node.function_area !== filters.functionArea) {
      return false;
    }

    // Progress range filter
    if (filters.progressRange) {
      const [min, max] = filters.progressRange;
      if (node.progress < min || node.progress > max) {
        return false;
      }
    }

    // Health status filter
    if (filters.healthStatus?.length && !filters.healthStatus.includes(node.alignment_health)) {
      return false;
    }

    // Risk level filter
    if (filters.riskLevels?.length && !filters.riskLevels.includes(node.risk_level)) {
      return false;
    }

    // Orphaned filter
    if (filters.orphanedOnly && !node.is_orphaned) {
      return false;
    }

    // Strategic only filter
    if (filters.strategicOnly && node.strategic_weight < 4) {
      return false;
    }

    // Search filter
    if (filters.searchQuery) {
      const query = filters.searchQuery.toLowerCase();
      const matchesTitle = node.objective.toLowerCase().includes(query);
      const matchesOwner = node.owner_name.toLowerCase().includes(query);
      const matchesPlant = node.plant?.toLowerCase().includes(query);
      const matchesDept = node.department?.toLowerCase().includes(query);

      if (!matchesTitle && !matchesOwner && !matchesPlant && !matchesDept) {
        return false;
      }
    }

    return true;
  });
};

export const selectFilteredEdges = (
  state: ConstellationState,
  filteredNodeIds: Set<string>
): ConstellationEdge[] => {
  const { edges, filters } = state;

  return edges.filter((edge) => {
    // Must connect two visible nodes
    if (!filteredNodeIds.has(edge.source) || !filteredNodeIds.has(edge.target)) {
      return false;
    }

    // Alignment type filter
    if (filters.alignmentTypes?.length && !filters.alignmentTypes.includes(edge.alignment_type)) {
      return false;
    }

    return true;
  });
};
