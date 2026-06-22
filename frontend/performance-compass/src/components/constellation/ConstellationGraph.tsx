/**
 * ConstellationGraph Component
 * ===========================
 * Main graph rendering component using react-force-graph-2d
 * OPTIMIZED: Map lookups instead of O(N) finds, reduced logging, faster canvas draw
 */

import React, { useEffect, useRef, useMemo, useCallback } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { useConstellationStore } from '@/store/constellationStore';
import {
  ConstellationNode,
  ConstellationEdge,
  GraphNode,
  GraphEdge,
} from '@/types/constellation.types';
import { getForceGraphConfig } from '@/utils/graphLayout';
import {
  getHealthColor,
  getHealthGlow,
  getAlignmentTypeColor,
  colorPalette,
} from '@/utils/nodeColor';

interface ConstellationGraphProps {
  nodes: ConstellationNode[];
  edges: ConstellationEdge[];
  graphRef?: React.MutableRefObject<any>;
  matchedNodeIds?: Set<string>;
  selectedNodeId?: string | null;
  hoveredNodeId?: string | null;
  onNodeClick?: (nodeId: string) => void;
  onNodeHover?: (nodeId: string | null) => void;
  onNodeDoubleClick?: (nodeId: string) => void;
  onNodeRightClick?: (nodeId: string, event: MouseEvent) => void;
  width?: number;
  height?: number;
  showLabels?: boolean;
  animationDuration?: number;
}

export const ConstellationGraph: React.FC<ConstellationGraphProps> = ({
  nodes,
  edges,
  graphRef: externalGraphRef,
  matchedNodeIds,
  selectedNodeId = null,
  hoveredNodeId = null,
  onNodeClick,
  onNodeHover,
  onNodeDoubleClick,
  onNodeRightClick,
  width = 1200,
  height = 800,
  showLabels = true,
  animationDuration = 300,
}) => {
  const internalGraphRef = useRef<any>(null);
  const graphRef = externalGraphRef ?? internalGraphRef;
  const store = useConstellationStore();

  // Transform nodes for graph + build lookup Map (O(1) access)
  const { graphNodes, nodeMap } = useMemo(() => {
    const result = nodes.map((node) => ({
      ...node,
      displaySize: calculateNodeDisplaySize(node),
      displayColor: getHealthColor(node.alignment_health),
      glowColor: getHealthGlow(node.alignment_health),
    })) as GraphNode[];

    const map = new Map<string, GraphNode>();
    result.forEach((n) => map.set(n.id, n));

    return { graphNodes: result, nodeMap: map };
  }, [nodes]);

  // Pre-compute connected node sets for selection highlighting
  const connectedToSelected = useMemo(() => {
    if (!selectedNodeId) return new Set<string>();
    const connected = new Set<string>();
    edges.forEach((e) => {
      if (e.source === selectedNodeId || e.target === selectedNodeId) {
        connected.add(e.source as string);
        connected.add(e.target as string);
      }
    });
    return connected;
  }, [selectedNodeId, edges]);

  // Transform edges for graph — uses nodeMap for O(1) lookup
  const graphEdges = useMemo<GraphEdge[]>(() => {
    return edges.map((edge) => ({
      ...edge,
      displayWidth: Math.max(0.5, edge.contribution_weight * 1.2),
      displayColor: getEdgeDisplayColor(edge, selectedNodeId, hoveredNodeId),
      displayDash:
        edge.edge_type === 'FUNCTIONAL' || edge.is_dashed
          ? [6, 4]
          : edge.is_broken
            ? [5, 5]
            : undefined,
    }));
  }, [edges, selectedNodeId, hoveredNodeId]);

  // Force graph configuration — memoized on node count
  const config = useMemo(() => getForceGraphConfig(nodes.length), [nodes.length]);

  // Handle node click
  const handleNodeClick = useCallback(
    (node: any) => {
      onNodeClick?.(node.id);
      store.selectNode(node.id);
    },
    [onNodeClick, store]
  );

  // Handle node hover
  const handleNodeHover = useCallback(
    (node: any | null) => {
      onNodeHover?.(node?.id || null);
      store.hoverNode(node?.id || null);
    },
    [onNodeHover, store]
  );

  // OPTIMIZED: Custom node renderer — no array.find() calls
  const nodeCanvasObject = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const x = node.x || 0;
      const y = node.y || 0;
      const size = node.displaySize || 20;

      // Determine visibility (dimmed if something else is selected)
      const isSelected = selectedNodeId === node.id;
      const isHovered = hoveredNodeId === node.id;
      const isConnected = connectedToSelected.has(node.id);
      const isContextOnly = matchedNodeIds && matchedNodeIds.size > 0 && !matchedNodeIds.has(node.id);
      const shouldDim = isContextOnly || (selectedNodeId && !isSelected && !isConnected);
      const drawSize = shouldDim ? size * 0.6 : size;

      // Draw glow for selected/hovered
      if (isSelected || isHovered) {
        ctx.fillStyle = node.glowColor || 'rgba(34, 211, 238, 0.3)';
        ctx.beginPath();
        ctx.arc(x, y, drawSize + 15, 0, Math.PI * 2);
        ctx.fill();

        // Animated glow pulse
        const pulse = Math.sin(Date.now() * 0.003) * 0.3 + 0.7;
        ctx.fillStyle = (node.glowColor || 'rgba(34, 211, 238, 0.3)').replace(/[\d.]+\)/, `${pulse * 0.4})`);
        ctx.beginPath();
        ctx.arc(x, y, drawSize + 20, 0, Math.PI * 2);
        ctx.fill();
      }

      // Draw node circle
      ctx.globalAlpha = shouldDim ? 0.3 : 1;
      ctx.fillStyle = node.displayColor || colorPalette.orphaned;
      ctx.beginPath();
      ctx.arc(x, y, drawSize, 0, Math.PI * 2);
      ctx.fill();

      // Draw border
      ctx.strokeStyle = isSelected ? colorPalette.text : colorPalette.border;
      ctx.lineWidth = isSelected ? 3 : 1;
      ctx.stroke();

      // Draw label if enabled and space allows
      if (showLabels && drawSize > 15) {
        ctx.fillStyle = colorPalette.text;
        ctx.font = `${Math.max(8, drawSize * 0.4)}px sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        const labelMap: Record<string, string> = {
          organization: 'ORG', ORGANIZATION: 'ORG',
          region: 'RGN', REGION: 'RGN',
          plant: 'PLT', PLANT: 'PLT',
          department: 'DPT', DEPARTMENT: 'DPT',
          team: 'TM', TEAM: 'TM',
          employee: 'EMP', EMPLOYEE: 'EMP', INDIVIDUAL: 'EMP',
        };
        const label = labelMap[node.level] || (node.level || '').substring(0, 3).toUpperCase();
        ctx.fillText(label, x, y);

        // Progress indicator ring
        if (drawSize > 20) {
          const progressRadius = drawSize + 5;
          const progressAngle = ((node.progress || 0) / 100) * Math.PI * 2;
          ctx.strokeStyle = getProgressColor(node.progress || 0);
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.arc(x, y, progressRadius, -Math.PI / 2, progressAngle - Math.PI / 2);
          ctx.stroke();
        }
      }

      ctx.globalAlpha = 1;
    },
    [selectedNodeId, hoveredNodeId, connectedToSelected, showLabels, matchedNodeIds]
  );

  // OPTIMIZED: Custom link renderer
  const linkCanvasObject = useCallback(
    (link: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const source = link.source;
      const target = link.target;
      if (!source || !target) return;

      const sourceX = typeof source === 'object' ? source.x : 0;
      const sourceY = typeof source === 'object' ? source.y : 0;
      const targetX = typeof target === 'object' ? target.x : 0;
      const targetY = typeof target === 'object' ? target.y : 0;

      const isConnectedToSelected =
        selectedNodeId &&
        (source.id === selectedNodeId || target.id === selectedNodeId);

      ctx.strokeStyle = link.displayColor || 'rgba(107, 114, 128, 0.3)';
      ctx.lineWidth = isConnectedToSelected
        ? (link.displayWidth || 1) * 2
        : link.displayWidth || 1;
      ctx.globalAlpha = isConnectedToSelected ? 0.9 : (selectedNodeId ? 0.15 : 0.5);

      if (link.displayDash) {
        ctx.setLineDash(link.displayDash);
      }

      ctx.beginPath();
      ctx.moveTo(sourceX, sourceY);
      ctx.lineTo(targetX, targetY);
      ctx.stroke();

      if (link.displayDash) {
        ctx.setLineDash([]);
      }

      ctx.globalAlpha = 1;
    },
    [selectedNodeId]
  );

  useEffect(() => {
    if (graphRef.current) {
      graphRef.current.d3Force('charge')?.strength(config.chargeStrength);
      graphRef.current.d3Force('link')?.distance(config.linkDistance);
    }
  }, [config, graphRef]);

  // Re-fit when filtered graph data changes
  useEffect(() => {
    if (!graphRef.current || nodes.length === 0) return;
    const t = window.setTimeout(() => {
      graphRef.current?.zoomToFit?.(400, 50);
    }, 400);
    return () => window.clearTimeout(t);
  }, [nodes, edges, graphRef]);

  return (
    <div className="relative w-full h-full bg-[#030712] overflow-hidden">
      <ForceGraph2D
        ref={graphRef}
        graphData={{ nodes: graphNodes, links: graphEdges }}
        key={`graph-${graphNodes.length}-${graphEdges.length}`}
        nodeCanvasObject={nodeCanvasObject}
        linkCanvasObject={linkCanvasObject}
        onNodeClick={handleNodeClick}
        onNodeHover={handleNodeHover}
        onNodeRightClick={(node: any, event: any) => {
          onNodeRightClick?.(node.id, event);
        }}
        width={width}
        height={height}
        nodeAutoColorBy={() => 'level'}
        d3AlphaDecay={config.alphaDecay}
        d3VelocityDecay={config.velocityDecay}
        warmupTicks={config.warmupTicks}
        cooldownTicks={(config as any).cooldownTicks}
        enableNodeDrag={true}
        enablePanInteraction={true}
        enablePointerInteraction={true}
      />
    </div>
  );
};

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

const calculateNodeDisplaySize = (node: ConstellationNode): number => {
  const baseSizes: Record<string, number> = {
    organization: 60, ORGANIZATION: 60,
    region: 48, REGION: 48,
    plant: 38, PLANT: 38,
    department: 30, DEPARTMENT: 30,
    team: 24, TEAM: 24,
    employee: 18, EMPLOYEE: 18,
    INDIVIDUAL: 18,
  };
  const base = baseSizes[node.level] || 20;
  return base * (1 + (node.strategic_weight - 1) * 0.15);
};

const getEdgeDisplayColor = (
  edge: ConstellationEdge,
  selectedNodeId: string | null,
  hoveredNodeId: string | null,
): string => {
  const baseAlpha = Math.max(0.2, edge.contribution_score / 100);
  const baseColor = getAlignmentTypeColor(edge.alignment_type);

  // Highlight if connected to selected node
  if (selectedNodeId && (edge.source === selectedNodeId || edge.target === selectedNodeId)) {
    return baseColor.replace(/[\d.]+\)/, '0.9)');
  }

  // Fade if something else is selected
  if (selectedNodeId && edge.source !== selectedNodeId && edge.target !== selectedNodeId) {
    return baseColor.replace(/[\d.]+\)/, '0.15)');
  }

  return baseColor;
};

const getProgressColor = (progress: number): string => {
  if (progress >= 80) return colorPalette.healthy;
  if (progress >= 60) return colorPalette.needsAttention;
  if (progress >= 40) return colorPalette.critical;
  return colorPalette.blocked;
};
