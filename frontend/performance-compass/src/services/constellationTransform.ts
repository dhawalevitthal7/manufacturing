/**
 * Constellation Transform Service
 * ================================
 * Transforms backend API data into constellation visualization format
 */

import {
  ConstellationAPIResponse,
  ConstellationNode,
  ConstellationEdge,
  GraphNode,
  GraphEdge,
  GraphStatistics,
} from '@/types/constellation.types';
import {
  calculateNodeSize,
  getNodeColor,
  getGlowColor,
} from '@/store/constellationStore';
import {
  findOrphanedOKRs,
  findBottlenecks,
  calculateNetworkAlignmentHealth,
} from '@/utils/alignmentUtils';

/**
 * Transform API response to graph nodes and edges
 */
export const transformConstellationData = (
  response: ConstellationAPIResponse
): { nodes: GraphNode[]; edges: GraphEdge[] } => {
  const graphNodes = transformNodes(response.nodes);
  const graphEdges = transformEdges(response.edges, new Map(graphNodes.map((n) => [n.id, n])));

  return { nodes: graphNodes, edges: graphEdges };
};

/**
 * Transform constellation nodes to graph nodes
 */
export const transformNodes = (nodes: ConstellationNode[]): GraphNode[] => {
  return nodes.map((node) => ({
    ...node,
    displaySize: calculateNodeSize(node.level, node.strategic_weight),
    displayColor: getNodeColor(node.alignment_health, node.progress),
    glowColor: getGlowColor(node.alignment_health),
    clusterGroup: node.plant || node.region || 'orphaned',
  }));
};

/**
 * Transform constellation edges to graph edges
 */
export const transformEdges = (edges: ConstellationEdge[], nodeMap: Map<string, GraphNode>): GraphEdge[] => {
  return edges
    .filter((edge) => nodeMap.has(edge.source) && nodeMap.has(edge.target))
    .map((edge) => ({
      ...edge,
      displayWidth: Math.max(0.5, edge.contribution_weight * 0.8),
      displayColor: getEdgeColorByAlignment(edge.alignment_type, edge.contribution_score),
      displayDash: edge.is_broken ? [5, 5] : undefined,
    }));
};

/**
 * Get edge color based on alignment type and score
 */
export const getEdgeColorByAlignment = (alignmentType: string, score: number): string => {
  const baseAlpha = Math.max(0.2, score / 100);

  const colorMap: Record<string, string> = {
    strategic: `rgba(34, 211, 238, ${baseAlpha})`, // Cyan
    operational: `rgba(34, 197, 94, ${baseAlpha})`, // Green
    support: `rgba(168, 85, 247, ${baseAlpha})`, // Purple
    dependency: `rgba(249, 115, 22, ${baseAlpha})`, // Orange
    'cross-functional': `rgba(236, 72, 153, ${baseAlpha})`, // Pink
  };

  return colorMap[alignmentType] || `rgba(107, 114, 128, ${baseAlpha})`;
};

/**
 * Calculate graph statistics from data
 */
export const calculateGraphStatistics = (
  nodes: ConstellationNode[],
  edges: ConstellationEdge[]
): GraphStatistics => {
  const orphanedNodes = findOrphanedOKRs(nodes, edges);
  const bottlenecks = findBottlenecks(nodes, edges);
  const { score: avgAlignment } = calculateNetworkAlignmentHealth(nodes, edges);

  const healthDistribution = {
    healthy: nodes.filter((n) => n.alignment_health === 'healthy').length,
    needs_attention: nodes.filter((n) => n.alignment_health === 'needs_attention').length,
    critical: nodes.filter((n) => n.alignment_health === 'critical').length,
    blocked: nodes.filter((n) => n.alignment_health === 'blocked').length,
  };

  const riskDistribution = {
    critical: nodes.filter((n) => n.risk_level === 'critical').length,
    high: nodes.filter((n) => n.risk_level === 'high').length,
    medium: nodes.filter((n) => n.risk_level === 'medium').length,
    low: nodes.filter((n) => n.risk_level === 'low').length,
  };

  const levelDistribution = {
    organization: nodes.filter((n) => n.level === 'organization').length,
    region: nodes.filter((n) => n.level === 'region').length,
    plant: nodes.filter((n) => n.level === 'plant').length,
    department: nodes.filter((n) => n.level === 'department').length,
    team: nodes.filter((n) => n.level === 'team').length,
    employee: nodes.filter((n) => n.level === 'employee').length,
  };

  const avgConfidence = nodes.length
    ? nodes.reduce((sum, n) => sum + n.confidence_score, 0) / nodes.length
    : 0;

  return {
    totalNodes: nodes.length,
    totalEdges: edges.length,
    orphanedNodes: orphanedNodes.length,
    avgAlignment,
    avgConfidence: Math.round(avgConfidence),
    healthDistribution,
    riskDistribution,
    levelDistribution,
  };
};

/**
 * Filter nodes and edges based on criteria
 */
export const filterConstellationData = (
  nodes: ConstellationNode[],
  edges: ConstellationEdge[],
  filters: {
    levels?: string[];
    plants?: string[];
    departments?: string[];
    progressMin?: number;
    progressMax?: number;
    healthStatus?: string[];
    riskLevels?: string[];
    searchQuery?: string;
  }
): { nodes: ConstellationNode[]; edges: ConstellationEdge[] } => {
  let filteredNodes = [...nodes];

  // Level filter
  if (filters.levels?.length) {
    filteredNodes = filteredNodes.filter((n) => filters.levels!.includes(n.level));
  }

  // Plant filter
  if (filters.plants?.length) {
    filteredNodes = filteredNodes.filter((n) => filters.plants!.includes(n.plant || ''));
  }

  // Department filter
  if (filters.departments?.length) {
    filteredNodes = filteredNodes.filter((n) => filters.departments!.includes(n.department || ''));
  }

  // Progress range filter
  if (filters.progressMin !== undefined || filters.progressMax !== undefined) {
    const min = filters.progressMin ?? 0;
    const max = filters.progressMax ?? 100;
    filteredNodes = filteredNodes.filter((n) => n.progress >= min && n.progress <= max);
  }

  // Health filter
  if (filters.healthStatus?.length) {
    filteredNodes = filteredNodes.filter((n) => filters.healthStatus!.includes(n.alignment_health));
  }

  // Risk filter
  if (filters.riskLevels?.length) {
    filteredNodes = filteredNodes.filter((n) => filters.riskLevels!.includes(n.risk_level));
  }

  // Search filter
  if (filters.searchQuery) {
    const q = filters.searchQuery.toLowerCase();
    filteredNodes = filteredNodes.filter((n) =>
      n.objective.toLowerCase().includes(q) ||
      n.owner_name.toLowerCase().includes(q) ||
      n.plant?.toLowerCase().includes(q) ||
      n.department?.toLowerCase().includes(q)
    );
  }

  // Filter edges to only include those between visible nodes
  const visibleNodeIds = new Set(filteredNodes.map((n) => n.id));
  const filteredEdges = edges.filter(
    (e) => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target)
  );

  return { nodes: filteredNodes, edges: filteredEdges };
};

/**
 * Export graph as data URL (PNG)
 */
export const exportGraphAsImage = async (
  canvasRef: HTMLCanvasElement,
  format: 'png' | 'svg' | 'pdf' = 'png'
): Promise<string> => {
  if (!canvasRef) throw new Error('Canvas reference not available');

  switch (format) {
    case 'png':
      return canvasRef.toDataURL('image/png');
    case 'svg':
      // For SVG, would need to reconstruct from graph structure
      // This is a simplified implementation
      return canvasRef.toDataURL('image/svg+xml');
    case 'pdf':
      // Would need pdf-lib or similar
      return canvasRef.toDataURL('image/png');
    default:
      return canvasRef.toDataURL('image/png');
  }
};

/**
 * Cache key generator for API requests
 */
export const getCacheKey = (org_id: string, filters?: Record<string, any>): string => {
  const filterStr = filters ? JSON.stringify(filters) : '';
  return `constellation:${org_id}:${filterStr}`;
};

/**
 * Transform node for detail panel display
 */
export const prepareNodeDetailsDisplay = (
  node: ConstellationNode,
  relatedNodes: ConstellationNode[],
  edges: ConstellationEdge[]
) => {
  const parentEdges = edges.filter((e) => e.target === node.id);
  const childEdges = edges.filter((e) => e.source === node.id);

  const parentNodes = parentEdges
    .map((e) => relatedNodes.find((n) => n.id === e.source))
    .filter(Boolean) as ConstellationNode[];

  const childNodes = childEdges
    .map((e) => relatedNodes.find((n) => n.id === e.target))
    .filter(Boolean) as ConstellationNode[];

  return {
    node,
    parents: parentNodes,
    children: childNodes,
    childContributions: childEdges.map((e) => ({
      childId: e.target,
      contribution: e.contribution_score,
    })),
  };
};

export const constellationService = {
  transformConstellationData,
  transformNodes,
  transformEdges,
  calculateGraphStatistics,
  filterConstellationData,
  exportGraphAsImage,
  getCacheKey,
  prepareNodeDetailsDisplay,
};
