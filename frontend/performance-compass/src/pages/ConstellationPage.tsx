/**
 * OKR Constellation — immersive visual alignment map
 */

import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useConstellationGraph } from '@/hooks/useConstellationGraph';
import { OrbitalConstellationView, OrbitalViewHandle } from '@/components/constellation/OrbitalConstellationView';
import { ConstellationGraph } from '@/components/constellation/ConstellationGraph';
import { ConstellationFloatingControls } from '@/components/constellation/ConstellationFloatingControls';
import { ConstellationFunctionControls } from '@/components/constellation/ConstellationFunctionControls';
import { ConstellationBreadcrumb } from '@/components/constellation/ConstellationBreadcrumb';
import { NodeDetailPanel } from '@/components/constellation/NodeDetailPanel';
import { LineOfSightView } from '@/components/constellation/LineOfSightView';
import { useConstellationStore } from '@/store/constellationStore';
import { useAuthStore } from '@/lib/stores/auth-store';

interface ConstellationPageProps {
  orgId: string;
}

export const ConstellationPage: React.FC<ConstellationPageProps> = ({ orgId }) => {
  const graph = useConstellationGraph(orgId);
  const showDetailPanel = useConstellationStore((s) => s.showDetailPanel);
  const toggleDetailPanel = useConstellationStore((s) => s.toggleDetailPanel);
  const selectedNodeId = useConstellationStore((s) => s.selectedNodeId);
  const storeNodes = useConstellationStore((s) => s.nodes);
  const filters = useConstellationStore((s) => s.filters);
  const userRole = useAuthStore((s) => s.user?.system_role);

  const containerRef = useRef<HTMLDivElement>(null);
  const orbitalRef = useRef<OrbitalViewHandle>(null);
  const forceGraphRef = useRef<any>(null);
  const [windowSize, setWindowSize] = useState({ width: 1200, height: 700 });

  const displayNodes = graph.filteredNodes;
  const displayEdges = graph.filteredEdges;
  const drillDownStack = useConstellationStore((s) => s.drillDownStack);
  const resetDrillDown = useConstellationStore((s) => s.resetDrillDown);
  const popDrillDown = useConstellationStore((s) => s.popDrillDown);

  const selectedCluster = graph.visibleGraph?.clusters.get(selectedNodeId ?? '') ?? null;

  const avgProgress =
    displayNodes.length > 0
      ? Math.round(
          displayNodes.reduce((s, n) => s + (n.final_progress ?? n.progress ?? 0), 0) /
            displayNodes.length,
        )
      : 0;

  useEffect(() => {
    const handleResize = () => {
      const panelOffset = showDetailPanel && selectedNodeId ? 340 : 0;
      setWindowSize({
        width: Math.max(640, (containerRef.current?.clientWidth ?? window.innerWidth) - panelOffset),
        height: Math.max(480, window.innerHeight - 80),
      });
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [showDetailPanel, selectedNodeId]);

  const handleZoomIn = useCallback(() => {
    if (graph.displayMode === 'orbit') {
      orbitalRef.current?.zoomIn();
    } else if (graph.displayMode === 'graph' && forceGraphRef.current) {
      const current = forceGraphRef.current.zoom?.() ?? 1;
      forceGraphRef.current.zoom(current * 1.3, 300);
    }
  }, [graph.displayMode]);

  const handleZoomOut = useCallback(() => {
    if (graph.displayMode === 'orbit') {
      orbitalRef.current?.zoomOut();
    } else if (graph.displayMode === 'graph' && forceGraphRef.current) {
      const current = forceGraphRef.current.zoom?.() ?? 1;
      forceGraphRef.current.zoom(current / 1.3, 300);
    }
  }, [graph.displayMode]);

  const handleResetView = useCallback(() => {
    graph.resetFilters();
    if (graph.displayMode === 'orbit') {
      orbitalRef.current?.resetView();
    } else if (graph.displayMode === 'graph' && forceGraphRef.current) {
      forceGraphRef.current.zoomToFit?.(400, 40);
    }
  }, [graph]);

  const handleExport = useCallback(() => {
    const canvas = containerRef.current?.querySelector('canvas');
    if (!canvas) return;
    const link = document.createElement('a');
    link.download = `constellation-${orgId}-${Date.now()}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
  }, [orgId]);

  if (graph.isLoading && !graph.nodes.length) {
    return (
      <div className="flex items-center justify-center w-full min-h-[70vh] bg-[#030712]">
        <div className="flex flex-col items-center gap-4">
          <div className="h-12 w-12 rounded-full border-2 border-cyan-500/30 border-t-cyan-400 animate-spin" />
          <p className="text-slate-400 text-sm tracking-wide">Loading constellation…</p>
        </div>
      </div>
    );
  }

  if (graph.error && !graph.nodes.length) {
    return (
      <div className="flex flex-col items-center justify-center w-full min-h-[50vh] bg-[#030712] p-8 gap-4">
        <p className="text-red-400 text-sm">{graph.error}</p>
        <button
          type="button"
          onClick={graph.refresh}
          className="px-4 py-2 text-sm rounded-xl bg-slate-800/80 text-slate-200 hover:bg-slate-700 border border-white/10"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="relative w-full min-h-[calc(100vh-4rem)] bg-[#030712] overflow-hidden rounded-xl"
    >
      {/* Ambient background glow */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/4 left-1/3 w-96 h-96 bg-cyan-600/5 rounded-full blur-[120px]" />
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-violet-600/5 rounded-full blur-[100px]" />
      </div>

      <div className="relative z-10 w-full h-full min-h-[calc(100vh-4rem)]">
        {graph.displayMode === 'orbit' && displayNodes.length > 0 && (
          <>
            {drillDownStack.length > 0 && (
              <div className="absolute top-0 left-0 right-0 z-20">
                <ConstellationBreadcrumb
                  crumbs={[
                    {
                      id: '__root__',
                      label: graph.organizationName || 'Organization',
                    },
                    ...drillDownStack.map((e) => ({
                      id: `${e.scopeLevel}-${e.scopeId}`,
                      label: e.label,
                    })),
                  ]}
                  onCrumbClick={(_crumbId, index) => {
                    if (index === 0) {
                      resetDrillDown();
                      return;
                    }
                    const pops = drillDownStack.length - index;
                    for (let i = 0; i < pops; i++) popDrillDown();
                  }}
                />
              </div>
            )}
            <OrbitalConstellationView
              ref={orbitalRef}
              nodes={displayNodes}
              edges={graph.visibleGraph?.visibleEdges ?? displayEdges}
              visibleGraph={graph.visibleGraph}
              expandedNodeIds={graph.expandedNodeIds}
              width={windowSize.width}
              height={windowSize.height}
              scopeConfig={graph.scopeConfig}
              scopeId={graph.scopeId}
              organizationName={graph.organizationName ?? undefined}
              scopeEntityName={graph.scopeEntityName ?? undefined}
              selectedNodeId={selectedNodeId}
              onNodeClick={(id) => {
                graph.handleNodeClick(id);
                if (!showDetailPanel) toggleDetailPanel();
              }}
              onNodeDoubleClick={graph.handleNodeDoubleClick}
              onClusterExpand={graph.handleClusterExpand}
              showLegend={false}
              showChrome={false}
            />
          </>
        )}

        {graph.displayMode === 'graph' && displayNodes.length > 0 && (
          <ConstellationGraph
            graphRef={forceGraphRef}
            nodes={displayNodes}
            edges={displayEdges}
            selectedNodeId={selectedNodeId}
            onNodeClick={(id) => {
              graph.handleNodeClick(id);
              if (!showDetailPanel) toggleDetailPanel();
            }}
            onNodeHover={graph.handleNodeHover}
            onNodeDoubleClick={graph.handleNodeDoubleClick}
            width={windowSize.width}
            height={windowSize.height}
          />
        )}

        {graph.displayMode === 'line-of-sight' && (
          <LineOfSightView
            chain={graph.lineOfSight}
            organizationName={graph.organizationName ?? undefined}
          />
        )}

        {displayNodes.length === 0 && graph.displayMode !== 'line-of-sight' && (
          <div className="flex flex-col items-center justify-center h-full min-h-[400px] text-slate-400">
            <p className="text-lg font-medium text-slate-300">No OKRs in scope</p>
            <button
              type="button"
              onClick={graph.refresh}
              className="mt-4 px-4 py-2 text-sm rounded-xl bg-slate-800/60 border border-white/10 hover:bg-slate-700"
            >
              Refresh
            </button>
          </div>
        )}
      </div>

      <ConstellationFloatingControls
        displayMode={graph.displayMode}
        onDisplayModeChange={graph.setDisplayMode}
        onZoomIn={handleZoomIn}
        onZoomOut={handleZoomOut}
        onReset={handleResetView}
        onExport={handleExport}
        orgName={graph.organizationName ?? undefined}
        avgProgress={avgProgress}
        showExpansionControls={graph.displayMode === 'orbit' && !!graph.visibleGraph}
        onExpandAll={graph.expandAllClusters}
        onCollapseAll={graph.collapseAllClusters}
      />

      <ConstellationFunctionControls
        userRole={userRole}
        functionArea={filters.functionArea}
        groupByFunction={filters.groupByFunction}
        onFunctionAreaChange={(area) => graph.applyFilters({ functionArea: area })}
        onGroupByFunctionChange={(enabled) => graph.applyFilters({ groupByFunction: enabled })}
      />

      <NodeDetailPanel
        node={storeNodes.find((n) => n.id === selectedNodeId) || null}
        cluster={selectedCluster}
        edges={displayEdges}
        allNodes={graph.nodes}
        isOpen={showDetailPanel && !!selectedNodeId}
        onClose={toggleDetailPanel}
        onExpandCluster={graph.handleClusterExpand}
        onFocusHere={graph.handleFocusHere}
      />
    </div>
  );
};
