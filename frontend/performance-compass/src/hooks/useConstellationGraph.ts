/**
 * useConstellationGraph Hook
 * ==========================
 * Manages constellation graph state, filters, insights, and drill-down.
 */

import { useEffect, useRef, useCallback, useState, useMemo } from 'react';
import { useConstellationStore } from '@/store/constellationStore';
import { constellationService } from '@/services/constellationTransform';
import { getConstellationData, getConstellationInsights } from '@/services/constellationApi';
import {
  ConstellationNode,
  ConstellationEdge,
  GraphStatistics,
  ExecutiveInsight,
  RoleScopeConfig,
  LineOfSightNode,
  AIPrescription,
  DisplayMode,
  ConstellationFilters,
  VisibleGraph,
} from '@/types/constellation.types';
import {
  getVisibleGraph,
  resolveScopeCenter,
  getExpansionBreadcrumbs,
  nodeIdToClusterId,
  SCOPE_CENTER_KEY,
} from '@/utils/constellationExpansion';
import { generateAlignmentInsights } from '@/utils/alignmentUtils';
import { filterConstellationGraph, needsServerRefetch, hasActiveFilters } from '@/utils/constellationFilterUtils';
import {
  getScopeConfigFromUserScope,
  getScopeConfigFromRole,
  getDefaultDisplayMode,
} from '@/utils/roleScopeConfig';
import { functionAreaForRole, isFunctionalHeadRole } from '@/utils/functionArea';
import { useAuthStore } from '@/lib/stores/auth-store';
import { useUIStore } from '@/lib/stores/ui-store';

interface UseConstellationGraphReturn {
  nodes: ConstellationNode[];
  edges: ConstellationEdge[];
  filteredNodes: ConstellationNode[];
  filteredEdges: ConstellationEdge[];
  isLoading: boolean;
  error: string | null;
  stats: GraphStatistics | null;
  insights: ExecutiveInsight[];
  aiPrescriptions: AIPrescription[];
  lineOfSight: LineOfSightNode[];
  scopeConfig: RoleScopeConfig;
  userScope: string | null;
  scopeId: string | null;
  organizationName: string | null;
  scopeEntityName: string | null;
  orphanedCount: number;
  brokenCount: number;
  displayMode: DisplayMode;
  matchedFilterCount: number;
  matchedNodeIds: Set<string>;
  visibleGraph: VisibleGraph | null;
  expansionBreadcrumbs: Array<{ id: string; label: string }>;
  expandedNodeIds: Set<string>;
  scopeCenterId: string | null;
  loadConstellationData: (orgId: string, force?: boolean) => Promise<void>;
  handleNodeClick: (nodeId: string) => void;
  handleNodeHover: (nodeId: string | null) => void;
  handleNodeDoubleClick: (nodeId: string) => void;
  handleClusterExpand: (clusterId: string) => void;
  handleClusterCollapse: (clusterId: string) => void;
  collapseAllClusters: () => void;
  expandAllClusters: () => void;
  handleFocusHere: (nodeId: string) => void;
  handleSearchChange: (query: string) => void;
  resetFilters: () => void;
  focusNode: (nodeId: string) => void;
  setDisplayMode: (mode: DisplayMode) => void;
  applyFilters: (filters: Partial<ConstellationFilters>) => Promise<void>;
  refresh: () => void;
  canvasRef: React.RefObject<HTMLCanvasElement | null>;
  graphRef: React.RefObject<any>;
}

export const useConstellationGraph = (orgId: string): UseConstellationGraphReturn => {
  const nodes = useConstellationStore((s) => s.nodes);
  const edges = useConstellationStore((s) => s.edges);
  const filters = useConstellationStore((s) => s.filters);
  const viewMode = useConstellationStore((s) => s.viewMode);
  const displayMode = useConstellationStore((s) => s.displayMode);
  const setNodes = useConstellationStore((s) => s.setNodes);
  const setEdges = useConstellationStore((s) => s.setEdges);
  const selectNode = useConstellationStore((s) => s.selectNode);
  const hoverNode = useConstellationStore((s) => s.hoverNode);
  const focusNodeStore = useConstellationStore((s) => s.focusNode);
  const updateFilters = useConstellationStore((s) => s.updateFilters);
  const setFilters = useConstellationStore((s) => s.setFilters);
  const setDisplayModeStore = useConstellationStore((s) => s.setDisplayMode);
  const pushDrillDown = useConstellationStore((s) => s.pushDrillDown);
  const expandedNodeIds = useConstellationStore((s) => s.expandedNodeIds);
  const toggleNodeExpansion = useConstellationStore((s) => s.toggleNodeExpansion);
  const collapseAll = useConstellationStore((s) => s.collapseAll);
  const collapseSubtree = useConstellationStore((s) => s.collapseSubtree);
  const resetExpansion = useConstellationStore((s) => s.resetExpansion);
  const setExpansionContext = useConstellationStore((s) => s.setExpansionContext);
  const setExpandedNodeIds = useConstellationStore((s) => s.setExpandedNodeIds);

  const savedExpansionRef = useRef<Set<string> | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const graphRef = useRef<any>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<GraphStatistics | null>(null);
  const [insights, setInsights] = useState<ExecutiveInsight[]>([]);
  const [aiPrescriptions, setAiPrescriptions] = useState<AIPrescription[]>([]);
  const [lineOfSight, setLineOfSight] = useState<LineOfSightNode[]>([]);
  const [userScope, setUserScope] = useState<string | null>(null);
  const [scopeId, setScopeId] = useState<string | null>(null);
  const [organizationName, setOrganizationName] = useState<string | null>(null);
  const [scopeEntityName, setScopeEntityName] = useState<string | null>(null);
  const [orphanedCount, setOrphanedCount] = useState(0);
  const [brokenCount, setBrokenCount] = useState(0);

  const isLoadingRef = useRef(false);
  const userRole = useAuthStore((s) => s.user?.system_role);
  const selectedCycleId = useUIStore((s) => s.selectedCycleId);

  const scopeConfig: RoleScopeConfig = userScope
    ? getScopeConfigFromUserScope(userScope)
    : getScopeConfigFromRole(userRole);

  const filteredGraph = useMemo(
    () => filterConstellationGraph(nodes, edges, filters, viewMode, true),
    [nodes, edges, filters, viewMode],
  );

  const filteredNodes = filteredGraph.nodes;
  const filteredEdges = filteredGraph.edges;
  const matchedFilterCount = filteredGraph.matchedCount;

  const filtersActive = hasActiveFilters(filters);

  const scopeCenter = useMemo(
    () =>
      resolveScopeCenter(
        nodes,
        scopeConfig.scopeLevel as ConstellationNode['level'],
        scopeId,
        organizationName ?? undefined,
        scopeEntityName ?? undefined,
      ),
    [nodes, scopeConfig.scopeLevel, scopeId, organizationName, scopeEntityName],
  );

  const visibleGraph = useMemo((): VisibleGraph | null => {
    if (displayMode !== 'orbit' || filtersActive || !nodes.length) return null;
    return getVisibleGraph(
      nodes,
      edges,
      expandedNodeIds,
      scopeCenter.centerId,
      scopeConfig.scopeLevel as ConstellationNode['level'],
      scopeId,
    );
  }, [
    displayMode,
    filtersActive,
    nodes,
    edges,
    expandedNodeIds,
    scopeCenter.centerId,
    scopeConfig.scopeLevel,
    scopeId,
  ]);

  const expansionBreadcrumbs = useMemo(() => {
    if (!visibleGraph) return [];
    const centerLabel =
      scopeEntityName ||
      organizationName ||
      scopeConfig.centerLabel.replace(' OKR', '');
    return getExpansionBreadcrumbs(expandedNodeIds, visibleGraph.clusters, centerLabel);
  }, [visibleGraph, expandedNodeIds, scopeEntityName, organizationName, scopeConfig.centerLabel]);

  useEffect(() => {
    if (scopeCenter.centerId) {
      setExpansionContext(
        scopeConfig.scopeLevel as ConstellationNode['level'],
        scopeCenter.centerId,
      );
    }
  }, [scopeCenter.centerId, scopeConfig.scopeLevel, setExpansionContext]);

  const prevDisplayModeRef = useRef(displayMode);
  useEffect(() => {
    if (displayMode === 'graph' && filtersActive) {
      savedExpansionRef.current = new Set(expandedNodeIds);
    }
    if (
      prevDisplayModeRef.current === 'graph' &&
      displayMode === 'orbit' &&
      !filtersActive &&
      savedExpansionRef.current
    ) {
      setExpandedNodeIds(savedExpansionRef.current);
      savedExpansionRef.current = null;
    }
    prevDisplayModeRef.current = displayMode;
  }, [filtersActive, displayMode, expandedNodeIds, setExpandedNodeIds]);

  const loadConstellationData = useCallback(
    async (org: string, force = false, overrideFilters?: ConstellationFilters) => {
      if (isLoadingRef.current) return;

      isLoadingRef.current = true;
      setIsLoading(true);
      setError(null);

      const activeFilters = overrideFilters ?? {
        ...filters,
        cycleId: filters.cycleId ?? selectedCycleId ?? undefined,
      };

      try {
        const data = await getConstellationData(org, activeFilters);

        if (data.metadata?.user_scope) {
          setUserScope(data.metadata.user_scope);
          if (!force) {
            setDisplayModeStore(getDefaultDisplayMode(data.metadata.user_scope));
          }
        }
        if (data.metadata?.scope_id) setScopeId(data.metadata.scope_id);
        if (data.metadata?.organization_name) setOrganizationName(data.metadata.organization_name);
        if (data.metadata?.scope_entity_name) setScopeEntityName(data.metadata.scope_entity_name);
        setOrphanedCount(data.metadata?.orphaned_count ?? 0);
        setBrokenCount(data.metadata?.broken_alignment_count ?? 0);
        setLineOfSight(data.metadata?.line_of_sight ?? []);

        resetExpansion();
        setNodes(data.nodes);
        setEdges(data.edges);
        setStats(constellationService.calculateGraphStatistics(data.nodes, data.edges));
        setInsights(generateAlignmentInsights(data.nodes, data.edges));

        const cycleForInsights = data.metadata?.cycle_id ?? activeFilters.cycleId;
        getConstellationInsights(org, cycleForInsights, activeFilters.functionArea)
          .then((insightData) => {
            if (insightData.rule_insights?.length) {
              setInsights(insightData.rule_insights);
            }
            setAiPrescriptions(insightData.ai_prescriptions ?? []);
          })
          .catch(() => {/* rule-based insights already set */});
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
        console.error('❌ [CONSTELLATION]', err);
      } finally {
        setIsLoading(false);
        isLoadingRef.current = false;
      }
    },
    [filters, selectedCycleId, setNodes, setEdges, setDisplayModeStore, resetExpansion],
  );

  const applyFilters = useCallback(
    async (next: Partial<ConstellationFilters>) => {
      const merged: ConstellationFilters = { ...filters, ...next };
      setFilters(merged);

      if (needsServerRefetch(merged) || hasActiveFilters(merged)) {
        setDisplayModeStore('graph');
      }

      if (
        needsServerRefetch(merged) ||
        next.functionArea !== undefined ||
        next.groupByFunction !== undefined
      ) {
        await loadConstellationData(orgId, true, {
          ...merged,
          cycleId: merged.cycleId ?? selectedCycleId ?? undefined,
        });
      }
    },
    [filters, setFilters, setDisplayModeStore, loadConstellationData, orgId, selectedCycleId],
  );

  const resetFilters = useCallback(() => {
    const area = functionAreaForRole(userRole);
    const empty: ConstellationFilters = {
      ...(isFunctionalHeadRole(userRole) && area ? { functionArea: area } : {}),
    };
    setFilters(empty);
    loadConstellationData(orgId, true, {
      ...empty,
      cycleId: selectedCycleId ?? undefined,
    });
  }, [setFilters, loadConstellationData, orgId, selectedCycleId, userRole]);

  const resolveClusterId = useCallback(
    (nodeId: string): string | null => {
      if (nodeId.startsWith('cluster-')) return nodeId;
      const fromSynthetic = nodeIdToClusterId(nodeId);
      if (fromSynthetic) return fromSynthetic;
      const node = nodes.find((n) => n.id === nodeId);
      if (!node) return visibleGraph?.clusters.has(nodeId) ? nodeId : null;
      if (visibleGraph?.clusters.has(nodeId)) return nodeId;
      for (const [cid, cluster] of visibleGraph?.clusters ?? []) {
        if (cluster.representativeNodeId === nodeId) return cid;
      }
      return nodeIdToClusterId(nodeId);
    },
    [nodes, visibleGraph],
  );

  const handleClusterExpand = useCallback(
    (clusterId: string) => {
      if (clusterId === SCOPE_CENTER_KEY) return;
      const cluster = visibleGraph?.clusters.get(clusterId);
      if (cluster && !cluster.isExpandable) return;
      toggleNodeExpansion(clusterId);
    },
    [toggleNodeExpansion, visibleGraph],
  );

  const handleClusterCollapse = useCallback(
    (clusterId: string) => {
      collapseSubtree(clusterId);
    },
    [collapseSubtree],
  );

  const collapseAllClusters = useCallback(() => collapseAll(), [collapseAll]);

  const expandAllClusters = useCallback(() => {
    if (!visibleGraph) return;
    const all = new Set<string>();
    for (const [id, c] of visibleGraph.clusters) {
      if (c.isExpandable) all.add(id);
    }
    setExpandedNodeIds(all);
  }, [visibleGraph, setExpandedNodeIds]);

  const handleNodeDoubleClick = useCallback(
    (nodeId: string) => {
      if (displayMode === 'orbit' && !filtersActive) {
        const clusterId = resolveClusterId(nodeId);
        if (clusterId && visibleGraph?.clusters.has(clusterId)) {
          const cluster = visibleGraph.clusters.get(clusterId)!;
          if (!cluster.isExpandable) return;
          if (expandedNodeIds.has(clusterId)) {
            handleClusterCollapse(clusterId);
          } else {
            handleClusterExpand(clusterId);
          }
          return;
        }
      }

      const node = nodes.find((n) => n.id === nodeId);
      if (!node) return;
      focusNodeStore(nodeId);
      if (graphRef.current) {
        const gNode = node as any;
        if (gNode.x != null) graphRef.current.centerAt(gNode.x, gNode.y, 1000);
      }
    },
    [
      displayMode,
      filtersActive,
      resolveClusterId,
      visibleGraph,
      expandedNodeIds,
      handleClusterCollapse,
      handleClusterExpand,
      nodes,
      focusNodeStore,
    ],
  );

  const handleFocusHere = useCallback(
    (nodeId: string) => {
      const node = nodes.find((n) => n.id === nodeId);
      if (!node) return;
      const label = node.entity_name || node.objective;
      focusNodeStore(nodeId);
      if (node.level === 'region' && node.region) {
        pushDrillDown({ scopeLevel: 'region', scopeId: node.region, label });
        setDisplayModeStore('graph');
      } else if (node.level === 'plant' && node.plant) {
        pushDrillDown({ scopeLevel: 'plant', scopeId: node.plant, label });
        setDisplayModeStore('graph');
      } else if (node.level === 'department' && node.department) {
        pushDrillDown({ scopeLevel: 'department', scopeId: node.department, label });
        setDisplayModeStore('graph');
      } else if (node.level === 'team' && node.team) {
        pushDrillDown({ scopeLevel: 'team', scopeId: node.team, label });
        setDisplayModeStore('graph');
      }
    },
    [nodes, focusNodeStore, pushDrillDown, setDisplayModeStore],
  );

  const handleSearchChange = useCallback(
    (query: string) => { updateFilters({ searchQuery: query }); },
    [updateFilters],
  );

  const refresh = useCallback(() => loadConstellationData(orgId, true), [loadConstellationData, orgId]);

  const handleNodeClick = useCallback((nodeId: string) => { selectNode(nodeId); }, [selectNode]);
  const handleNodeHover = useCallback((nodeId: string | null) => { hoverNode(nodeId); }, [hoverNode]);

  const focusNode = useCallback(
    (nodeId: string) => { handleFocusHere(nodeId); },
    [handleFocusHere],
  );

  const setDisplayMode = useCallback(
    (mode: DisplayMode) => setDisplayModeStore(mode),
    [setDisplayModeStore],
  );

  useEffect(() => {
    if (!orgId) return;
    resetExpansion();
    const area = functionAreaForRole(userRole);
    const initial: ConstellationFilters = {
      cycleId: selectedCycleId ?? undefined,
      ...(isFunctionalHeadRole(userRole) && area ? { functionArea: area } : {}),
    };
    if (isFunctionalHeadRole(userRole) && area) {
      setFilters(initial);
    }
    loadConstellationData(orgId, false, initial);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orgId, selectedCycleId, userRole]);

  return {
    nodes, edges, filteredNodes, filteredEdges,
    isLoading, error, stats, insights, aiPrescriptions, lineOfSight,
    scopeConfig, userScope, scopeId, organizationName, scopeEntityName,
    orphanedCount, brokenCount, displayMode, matchedFilterCount, matchedNodeIds: filteredGraph.matchedIds,
    visibleGraph, expansionBreadcrumbs, expandedNodeIds, scopeCenterId: scopeCenter.centerId,
    loadConstellationData, handleNodeClick, handleNodeHover,
    handleNodeDoubleClick, handleClusterExpand, handleClusterCollapse,
    collapseAllClusters, expandAllClusters, handleFocusHere,
    handleSearchChange, resetFilters, focusNode,
    setDisplayMode, applyFilters, refresh, canvasRef, graphRef,
  };
};

export const useNodeDetails = (
  nodeId: string | null,
  nodes: ConstellationNode[],
  edges: ConstellationEdge[],
) => {
  const selectedNode = nodes.find((n) => n.id === nodeId);
  const parentEdges = selectedNode ? edges.filter((e) => e.target === selectedNode.id) : [];
  const childEdges = selectedNode ? edges.filter((e) => e.source === selectedNode.id) : [];
  const parentNodes = parentEdges.map((e) => nodes.find((n) => n.id === e.source)).filter(Boolean) as ConstellationNode[];
  const childNodes = childEdges.map((e) => nodes.find((n) => n.id === e.target)).filter(Boolean) as ConstellationNode[];
  return { selectedNode, parentNodes, childNodes, parentEdges, childEdges };
};

export const useGraphZoomPan = (graphRef: React.RefObject<any>) => {
  const [zoom, setZoom] = useState(1);

  const handleZoom = useCallback((factor: number) => {
    const newZoom = Math.max(0.1, Math.min(5, zoom * factor));
    setZoom(newZoom);
    if (graphRef.current) graphRef.current.zoom(newZoom, 300);
  }, [zoom, graphRef]);

  const handleFitToScreen = useCallback(() => {
    if (graphRef.current) graphRef.current.zoomToFit(400);
  }, [graphRef]);

  const handleCenterGraph = useCallback(() => {
    if (graphRef.current) graphRef.current.centerAt(0, 0, 500);
  }, [graphRef]);

  return { zoom, handleZoom, handleFitToScreen, handleCenterGraph };
};

export const useConstellationKeyboard = (callbacks: {
  onSearch?: () => void;
  onReset?: () => void;
  onExport?: () => void;
  onToggleFilters?: () => void;
  onToggleInsights?: () => void;
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') { e.preventDefault(); callbacks.onSearch?.(); }
      if ((e.ctrlKey || e.metaKey) && e.key === 'r') { e.preventDefault(); callbacks.onReset?.(); }
      if ((e.ctrlKey || e.metaKey) && e.key === 'e') { e.preventDefault(); callbacks.onExport?.(); }
      if ((e.ctrlKey || e.metaKey) && e.key === 'f') { e.preventDefault(); callbacks.onToggleFilters?.(); }
      if ((e.ctrlKey || e.metaKey) && e.key === 'i') { e.preventDefault(); callbacks.onToggleInsights?.(); }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [callbacks]);
};
