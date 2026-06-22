import { Link } from "@tanstack/react-router";
import { useConstellationGraph } from "@/hooks/useConstellationGraph";
import { OrbitalConstellationView } from "@/components/constellation/OrbitalConstellationView";
import { Loader2, ArrowRight, AlertTriangle } from "lucide-react";

interface Props {
  orgId: string;
  height?: number;
}

export function DashboardConstellation({ orgId, height = 480 }: Props) {
  const graph = useConstellationGraph(orgId);

  if (graph.isLoading) {
    return (
      <div
        className="flex items-center justify-center rounded-xl border border-border bg-card"
        style={{ height }}
      >
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (graph.error) {
    return (
      <div
        className="flex items-center justify-center rounded-xl border border-dashed border-border bg-card p-6 text-sm text-muted-foreground"
        style={{ height }}
      >
        Alignment map unavailable. Open Alignment from the menu when OKRs exist.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-muted/30">
        <div className="flex items-center gap-3 text-xs">
          <span className="text-muted-foreground">
            {graph.nodes.length} OKRs · {graph.edges.length} links
          </span>
          {graph.orphanedCount > 0 && (
            <span className="flex items-center gap-1 text-amber-600">
              <AlertTriangle size={12} />
              {graph.orphanedCount} unaligned
            </span>
          )}
          {graph.brokenCount > 0 && (
            <span className="text-red-500">{graph.brokenCount} weak</span>
          )}
        </div>
        <Link
          to="/alignment"
          className="flex items-center gap-1 text-xs text-primary hover:underline"
        >
          Open full view
          <ArrowRight size={12} />
        </Link>
      </div>
      <div style={{ height: height - 40 }} className="w-full min-h-[520px]">
      <OrbitalConstellationView
        nodes={graph.nodes}
        edges={graph.visibleGraph?.visibleEdges ?? graph.edges}
        visibleGraph={graph.visibleGraph}
        expandedNodeIds={graph.expandedNodeIds}
        height={height - 40}
        showLegend={false}
        showChrome={false}
        scopeConfig={graph.scopeConfig}
        scopeId={graph.scopeId}
        organizationName={graph.organizationName ?? undefined}
        scopeEntityName={graph.scopeEntityName ?? undefined}
        selectedNodeId={null}
        onNodeClick={graph.handleNodeClick}
        onNodeDoubleClick={graph.handleNodeDoubleClick}
        onClusterExpand={graph.handleClusterExpand}
      />
      </div>
    </div>
  );
}
