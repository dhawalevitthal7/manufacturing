/**
 * OKR Constellation Visualization - TypeScript Types
 * ===================================================
 * Comprehensive type definitions for the constellation system
 */

// ============================================================================
// BACKEND API TYPES
// ============================================================================

export type OKRLevel = 'organization' | 'region' | 'plant' | 'department' | 'team' | 'employee';

export type FunctionArea =
  | 'OPERATIONS'
  | 'FINANCE'
  | 'HR'
  | 'SALES_MARKETING'
  | 'PROCUREMENT'
  | 'TECHNICAL'
  | 'REGIONS';

export type NodeKind =
  | 'ORG'
  | 'FUNCTIONAL_VERTICAL'
  | 'PLANT'
  | 'DEPARTMENT'
  | 'TEAM'
  | 'INDIVIDUAL';

export type EdgeType = 'CASCADE' | 'FUNCTIONAL' | 'SUPPORTS' | 'DEPENDS_ON' | 'RELATED_TO';
/** Hierarchy level used for cluster expansion (alias of OKRLevel) */
export type HierarchyLevel = OKRLevel;
export type AlignmentHealth = OKRHealth;
export type OKRHealth = 'healthy' | 'needs_attention' | 'critical' | 'blocked';
export type TrendStatus = 'ahead' | 'on_track' | 'behind' | 'critical_delay';
export type AlignmentType = 'strategic' | 'operational' | 'support' | 'dependency' | 'cross-functional';
export type RiskLevel = 'critical' | 'high' | 'medium' | 'low';
export type ViewMode = 'galaxy' | 'strategic' | 'risk' | 'plant' | 'department';
export type DisplayMode = 'orbit' | 'graph' | 'line-of-sight';

/**
 * Constellation Node - Represents an OKR in the graph
 */
export interface ConstellationNode {
  // Identity
  id: string;
  objective: string;
  
  // Ownership & Scope
  owner_id?: string;
  owner_name: string;
  owner_role: string;
  level: OKRLevel;
  
  // Progress Metrics
  progress: number;
  own_progress: number;
  alignment_contribution: number;
  final_progress: number;
  
  // Health & Confidence
  alignment_health: OKRHealth;
  confidence_score: number;
  risk_level: RiskLevel;
  trend_status: TrendStatus;
  
  // Strategic Information
  strategic_weight: number; // 1-5
  is_orphaned: boolean;
  
  // Scope Information (optional)
  department?: string | null;
  region?: string | null;
  plant?: string | null;
  team?: string | null;
  /** Resolved display name for org unit (region, plant, etc.) */
  entity_name?: string | null;
  region_name?: string | null;
  plant_name?: string | null;
  department_name?: string | null;
  team_name?: string | null;

  /** Corporate function tag (vertical / functionally-aligned OKRs) */
  function_area?: FunctionArea | null;
  function_area_label?: string | null;
  node_kind?: NodeKind | null;
  function_cluster?: FunctionArea | string | null;
  
  // Additional Data
  created_at?: string;
  updated_at?: string;
  key_results_count?: number;
}

/**
 * Constellation Edge - Represents alignment between OKRs
 */
export interface ConstellationEdge {
  source: string; // OKR ID
  target: string; // OKR ID
  contribution_weight: number; // 1-5
  alignment_type: AlignmentType;
  edge_type?: EdgeType;
  contribution_score: number; // 0-100
  is_strong?: boolean;
  is_broken?: boolean;
  is_dashed?: boolean;
  is_upstream?: boolean;
}

/**
 * Constellation API Response
 */
export interface ConstellationAPIResponse {
  nodes: ConstellationNode[];
  edges: ConstellationEdge[];
  metadata?: {
    total_okrs: number;
    total_users: number;
    organization_name: string;
    user_scope: string;
    scope_id: string;
    scope_entity_name?: string;
    generated_at: string;
    query_time_ms?: number;
    total_time_ms?: number;
    from_cache?: boolean;
    cycle_id?: string;
    orphaned_count?: number;
    broken_alignment_count?: number;
    line_of_sight?: LineOfSightNode[];
    function_area_filter?: FunctionArea | null;
    group_by?: 'function' | null;
    function_area_stats?: Record<
      string,
      { count: number; avg_progress: number; functional_edges: number }
    >;
    cascade_edge_count?: number;
    functional_edge_count?: number;
  };
}

export interface LineOfSightNode {
  id: string;
  title: string;
  level: string;
  progress: number;
}

export interface AIPrescription {
  title: string;
  description: string;
  priority: 'critical' | 'high' | 'medium' | 'low';
}

/**
 * Role-based scope configuration for constellation display
 * Maps user role to what the constellation should show as center/orbiting entities
 */
export interface RoleScopeConfig {
  /** Title for the constellation page */
  title: string;
  /** Subtitle / description */
  subtitle: string;
  /** The center node label (e.g., "Organization OKR", "Region OKR") */
  centerLabel: string;
  /** What the orbiting nodes represent */
  orbitLabel: string;
  /** The primary entity being shown */
  scopeLevel: string;
  /** What children are displayed as orbiting entities */
  childLevel: string;
  /** Icon emoji for the scope */
  icon: string;
}

// ============================================================================
// VISUALIZATION & UI TYPES
// ============================================================================

/**
 * Graph Node for react-force-graph rendering
 */
export interface GraphNode extends ConstellationNode {
  // Rendering properties
  x?: number;
  y?: number;
  z?: number;
  vx?: number;
  vy?: number;
  vz?: number;
  fx?: number;
  fy?: number;
  fz?: number;
  
  // Computed properties
  displaySize: number;
  displayColor: string;
  glowColor: string;
  isSelected?: boolean;
  isHovered?: boolean;
  isConnected?: boolean;
  clusterGroup?: string;
}

/**
 * Graph Edge for react-force-graph rendering
 */
export interface GraphEdge extends Omit<ConstellationEdge, 'source' | 'target'> {
  source: string | GraphNode;
  target: string | GraphNode;
  displayWidth: number;
  displayColor: string;
  displayDash?: number[];
}

/**
 * Node detail information for side panel
 */
export interface NodeDetails {
  node: ConstellationNode;
  childContributions: Array<{
    childId: string;
    childTitle: string;
    contribution: number;
  }>;
  parentNodes: ConstellationNode[];
  childNodes: ConstellationNode[];
  keyResults?: Array<{
    id: string;
    title: string;
    progress: number;
  }>;
  blockedDependencies?: Array<{
    dependencyId: string;
    dependencyTitle: string;
    reason: string;
  }>;
}

/**
 * Executive Insight
 */
export interface ExecutiveInsight {
  id: string;
  type: 'bottleneck' | 'orphan' | 'weak_alignment' | 'strong_contributor' | 'risk_propagation' | 'top_aligned';
  severity: 'critical' | 'high' | 'medium' | 'low';
  title: string;
  description: string;
  affectedNodes?: string[];
  impact?: number; // percentage
  actionable?: boolean;
  actionText?: string;
}

/**
 * Filter state
 */
export interface ConstellationFilters {
  levels?: OKRLevel[];
  regions?: string[];
  plants?: string[];
  departments?: string[];
  /** Server-side filter — CEO can pick any; functional heads are locked to their function */
  functionArea?: FunctionArea;
  /** CEO: cluster constellation orbits by corporate function */
  groupByFunction?: boolean;
  progressRange?: [number, number];
  healthStatus?: OKRHealth[];
  riskLevels?: RiskLevel[];
  orphanedOnly?: boolean;
  strategicOnly?: boolean;
  alignmentTypes?: AlignmentType[];
  quarter?: string;
  cycleId?: string;
  searchQuery?: string;
}

/**
 * Collapsed cluster bubble shown in progressive-disclosure orbit mode
 */
export interface CollapsedCluster {
  id: string;
  label: string;
  level: HierarchyLevel;
  depth: number;
  childCount: number;
  descendantCount: number;
  avgProgress: number;
  health: AlignmentHealth;
  parentClusterId: string | null;
  isExpandable: boolean;
  representativeNodeId?: string;
}

/**
 * Result of client-side visibility computation for expandable orbit mode
 */
export interface VisibleGraph {
  visibleNodes: ConstellationNode[];
  visibleEdges: ConstellationEdge[];
  clusters: Map<string, CollapsedCluster>;
  centerNode: ConstellationNode | null;
  scopeCenterId: string;
  /** cluster id → representative OKR node used when expanded as hub */
  clusterRepresentatives: Map<string, ConstellationNode>;
  /** cluster id → direct leaf OKRs rendered inside an expanded cluster */
  expandedLeaves: Map<string, ConstellationNode[]>;
  /** node/cluster id → nearest visible ancestor cluster (for dimming) */
  ancestorClusterOf: Map<string, string | null>;
  /** cluster ids currently visible in the orbit (collapsed or expanded) */
  visibleClusterIds: Set<string>;
}

/**
 * Graph statistics
 */
export interface GraphStatistics {
  totalNodes: number;
  totalEdges: number;
  orphanedNodes: number;
  avgAlignment: number;
  avgConfidence: number;
  healthDistribution: Record<OKRHealth, number>;
  riskDistribution: Record<RiskLevel, number>;
  levelDistribution: Record<OKRLevel, number>;
}

/**
 * Constellation Store State
 */
export interface ConstellationState {
  // Data
  nodes: ConstellationNode[];
  edges: ConstellationEdge[];
  graphNodes: Map<string, GraphNode>;
  graphEdges: GraphEdge[];
  
  // UI State
  viewMode: ViewMode;
  displayMode: DisplayMode;
  drillDownStack: Array<{ scopeLevel: string; scopeId: string; label: string }>;
  selectedNodeId: string | null;
  hoveredNodeId: string | null;
  focusedNodeId: string | null;
  filters: ConstellationFilters;
  
  // Panels
  showDetailPanel: boolean;
  showInsightsPanel: boolean;
  showFiltersPanel: boolean;
  
  // Graph State
  isSimulating: boolean;
  graphCenter: { x: number; y: number };
  zoom: number;

  // Progressive expansion (orbit mode)
  expandedNodeIds: Set<string>;
  expansionScopeLevel: OKRLevel;
  expansionScopeCenterId: string;
  
  // Actions
  setNodes: (nodes: ConstellationNode[]) => void;
  setEdges: (edges: ConstellationEdge[]) => void;
  setViewMode: (mode: ViewMode) => void;
  setDisplayMode: (mode: DisplayMode) => void;
  pushDrillDown: (entry: { scopeLevel: string; scopeId: string; label: string }) => void;
  popDrillDown: () => void;
  resetDrillDown: () => void;
  selectNode: (nodeId: string | null) => void;
  hoverNode: (nodeId: string | null) => void;
  focusNode: (nodeId: string | null) => void;
  updateFilters: (filters: Partial<ConstellationFilters>) => void;
  setFilters: (filters: ConstellationFilters) => void;
  toggleDetailPanel: () => void;
  toggleInsightsPanel: () => void;
  toggleFiltersPanel: () => void;
  setSimulating: (simulating: boolean) => void;
  setZoom: (zoom: number) => void;
  toggleNodeExpansion: (clusterId: string) => void;
  collapseAll: () => void;
  collapseSubtree: (clusterId: string) => void;
  resetExpansion: () => void;
  setExpandedNodeIds: (ids: Set<string>) => void;
  setExpansionContext: (scopeLevel: OKRLevel, scopeCenterId: string) => void;
}

/**
 * Mini map settings
 */
export interface MiniMapSettings {
  width: number;
  height: number;
  scale: number;
  borderColor: string;
}

/**
 * Export options
 */
export interface ExportOptions {
  format: 'png' | 'svg' | 'pdf';
  width: number;
  height: number;
  includeMetadata: boolean;
  quality: 'low' | 'medium' | 'high';
}
