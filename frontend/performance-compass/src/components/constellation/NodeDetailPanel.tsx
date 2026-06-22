/**
 * NodeDetailPanel Component
 * ========================
 * Side panel showing detailed information about selected OKR node
 */

import React, { useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, TrendingUp, AlertCircle, Target, Users, Link2 } from 'lucide-react';
import { ConstellationNode, ConstellationEdge, CollapsedCluster } from '@/types/constellation.types';
import { colorPalette, getHealthColor, getTrendColor } from '@/utils/nodeColor';
import { getFunctionAreaColor, getFunctionAreaLabel } from '@/utils/functionArea';

interface NodeDetailPanelProps {
  node: ConstellationNode | null;
  cluster?: CollapsedCluster | null;
  edges: ConstellationEdge[];
  allNodes: ConstellationNode[];
  isOpen: boolean;
  onClose: () => void;
  onExpandCluster?: (clusterId: string) => void;
  onFocusHere?: (nodeId: string) => void;
}

export const NodeDetailPanel: React.FC<NodeDetailPanelProps> = ({
  node,
  cluster = null,
  edges,
  allNodes,
  isOpen,
  onClose,
  onExpandCluster,
  onFocusHere,
}) => {
  // Calculate related nodes — split cascade vs functional alignment
  const { parentNodes, childNodes, childContributions, functionalParents, functionalChildren } =
    useMemo(() => {
    if (!node) {
      return {
        parentNodes: [],
        childNodes: [],
        childContributions: [],
        functionalParents: [],
        functionalChildren: [],
      };
    }

    const parentEdges = edges.filter(
      (e) => e.target === node.id && e.edge_type !== 'FUNCTIONAL',
    );
    const childEdges = edges.filter(
      (e) => e.source === node.id && e.edge_type !== 'FUNCTIONAL',
    );
    const functionalParentEdges = edges.filter(
      (e) => e.target === node.id && e.edge_type === 'FUNCTIONAL',
    );
    const functionalChildEdges = edges.filter(
      (e) => e.source === node.id && e.edge_type === 'FUNCTIONAL',
    );

    const parents = parentEdges
      .map((e) => allNodes.find((n) => n.id === e.source))
      .filter(Boolean) as ConstellationNode[];

    const children = childEdges
      .map((e) => allNodes.find((n) => n.id === e.target))
      .filter(Boolean) as ConstellationNode[];

    const funcParents = functionalParentEdges
      .map((e) => allNodes.find((n) => n.id === e.source))
      .filter(Boolean) as ConstellationNode[];

    const funcChildren = functionalChildEdges
      .map((e) => allNodes.find((n) => n.id === e.target))
      .filter(Boolean) as ConstellationNode[];

    const contributions = childEdges.map((e) => ({
      childId: e.target,
      contribution: e.contribution_score,
      weight: e.contribution_weight,
    }));

    return {
      parentNodes: parents,
      childNodes: children,
      childContributions: contributions,
      functionalParents: funcParents,
      functionalChildren: funcChildren,
    };
  }, [node, edges, allNodes]);

  if (!node && !cluster) return null;

  if (cluster && !node) {
    return (
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ x: 400, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 400, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            className="fixed right-4 top-20 bottom-4 w-80 rounded-2xl bg-slate-900/85 backdrop-blur-xl border border-white/10 z-50 flex flex-col overflow-hidden shadow-[0_8px_40px_rgba(0,0,0,0.6)]"
          >
            <div className="p-4 border-b border-slate-700 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-slate-100">Cluster Summary</h3>
              <button onClick={onClose} className="p-1 hover:bg-slate-800 rounded transition">
                <X size={20} className="text-slate-400" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto space-y-4 p-4">
              <div>
                <h2 className="text-xl font-bold text-slate-100 leading-tight mb-2">
                  {cluster.label}
                </h2>
                <p className="text-sm text-slate-400 capitalize">{cluster.level} cluster</p>
              </div>
              <div className="bg-slate-800 rounded-lg p-3 space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-500">Direct children</span>
                  <span className="text-slate-200 font-medium">{cluster.childCount}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Total descendants</span>
                  <span className="text-slate-200 font-medium">{cluster.descendantCount}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Avg progress</span>
                  <span className="text-slate-200 font-medium">{cluster.avgProgress}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Health</span>
                  <span
                    className="font-medium capitalize"
                    style={{ color: getHealthColor(cluster.health) }}
                  >
                    {cluster.health.replace('_', ' ')}
                  </span>
                </div>
              </div>
              <div className="flex flex-col gap-2">
                {cluster.isExpandable && onExpandCluster && (
                  <button
                    type="button"
                    onClick={() => onExpandCluster(cluster.id)}
                    className="w-full py-2 px-3 rounded-lg bg-cyan-600/20 text-cyan-300 border border-cyan-500/30 hover:bg-cyan-600/30 text-sm font-medium transition"
                  >
                    Expand cluster
                  </button>
                )}
                {cluster.representativeNodeId && onFocusHere && (
                  <button
                    type="button"
                    onClick={() => onFocusHere(cluster.representativeNodeId!)}
                    className="w-full py-2 px-3 rounded-lg bg-slate-800 text-slate-300 border border-slate-600 hover:bg-slate-700 text-sm font-medium transition"
                  >
                    Focus here
                  </button>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    );
  }

  if (!node) return null;

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ x: 400, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 400, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
          className="fixed right-4 top-20 bottom-4 w-80 rounded-2xl bg-slate-900/85 backdrop-blur-xl border border-white/10 z-50 flex flex-col overflow-hidden shadow-[0_8px_40px_rgba(0,0,0,0.6)]"
        >
          {/* Header */}
          <div className="p-4 border-b border-slate-700 flex items-center justify-between">
            <h3 className="text-lg font-semibold text-slate-100">OKR Details</h3>
            <button
              onClick={onClose}
              className="p-1 hover:bg-slate-800 rounded transition"
            >
              <X size={20} className="text-slate-400" />
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto space-y-4 p-4">
            {/* Title & Owner */}
            <div>
              <h2 className="text-xl font-bold text-slate-100 leading-tight mb-2">
                {node.objective}
              </h2>
              <div className="space-y-1 text-sm">
                <p className="text-slate-400">
                  <span className="text-slate-500">Owner:</span>{' '}
                  <span className="text-slate-200">{node.owner_name}</span>
                </p>
                <p className="text-slate-400">
                  <span className="text-slate-500">Role:</span>{' '}
                  <span className="text-slate-200">{node.owner_role}</span>
                </p>
              </div>
            </div>

            {/* Scope Information */}
            <div className="bg-slate-800 rounded-lg p-3 space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <span className="w-24 text-slate-500">Level:</span>
                <span className="text-slate-200 capitalize font-medium">{node.level}</span>
              </div>
              {node.node_kind && (
                <div className="flex items-center gap-2">
                  <span className="w-24 text-slate-500">Kind:</span>
                  <span className="text-slate-200 font-medium">
                    {node.node_kind.replace(/_/g, ' ')}
                  </span>
                </div>
              )}
              {node.function_area && (
                <div className="flex items-center gap-2">
                  <span className="w-24 text-slate-500">Function:</span>
                  <span
                    className="inline-flex items-center gap-1.5 text-slate-200 font-medium"
                  >
                    <span
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: getFunctionAreaColor(node.function_area) }}
                    />
                    {node.function_area_label || getFunctionAreaLabel(node.function_area)}
                  </span>
                </div>
              )}
              {node.plant && (
                <div className="flex items-center gap-2">
                  <span className="w-24 text-slate-500">Plant:</span>
                  <span className="text-slate-200">{node.plant}</span>
                </div>
              )}
              {node.department && (
                <div className="flex items-center gap-2">
                  <span className="w-24 text-slate-500">Department:</span>
                  <span className="text-slate-200">{node.department}</span>
                </div>
              )}
              {node.region && (
                <div className="flex items-center gap-2">
                  <span className="w-24 text-slate-500">Region:</span>
                  <span className="text-slate-200">{node.region}</span>
                </div>
              )}
            </div>

            {/* Progress Metrics */}
            <div className="bg-slate-800 rounded-lg p-3 space-y-3">
              <h4 className="font-semibold text-slate-200 flex items-center gap-2">
                <Target size={16} />
                Progress
              </h4>

              <ProgressBar
                label="Overall Progress"
                value={node.progress}
                color={getHealthColor(node.alignment_health)}
              />
              <ProgressBar
                label="Own Progress"
                value={node.own_progress}
                color={colorPalette.operational}
              />
              <ProgressBar
                label="Alignment Contribution"
                value={node.alignment_contribution}
                color={colorPalette.strategic}
              />
              <ProgressBar
                label="Confidence Score"
                value={node.confidence_score}
                color={colorPalette.healthy}
              />
            </div>

            {/* Health & Risk */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-slate-800 rounded-lg p-3 text-center">
                <div className="text-xs text-slate-500 mb-1">Health</div>
                <div
                  className="text-sm font-bold px-2 py-1 rounded capitalize"
                  style={{
                    backgroundColor: `${getHealthColor(node.alignment_health)}20`,
                    color: getHealthColor(node.alignment_health),
                  }}
                >
                  {node.alignment_health.replace('_', ' ')}
                </div>
              </div>
              <div className="bg-slate-800 rounded-lg p-3 text-center">
                <div className="text-xs text-slate-500 mb-1">Trend</div>
                <div
                  className="text-sm font-bold px-2 py-1 rounded capitalize flex items-center justify-center gap-1"
                  style={{
                    backgroundColor: `${getTrendColor(node.trend_status)}20`,
                    color: getTrendColor(node.trend_status),
                  }}
                >
                  <TrendingUp size={14} />
                  {node.trend_status.replace('_', ' ')}
                </div>
              </div>
            </div>

            {/* Cascade parent OKRs */}
            {parentNodes.length > 0 && (
              <div>
                <h4 className="font-semibold text-slate-200 flex items-center gap-2 mb-2">
                  <Link2 size={16} />
                  Cascade — Aligned To ({parentNodes.length})
                </h4>
                <div className="space-y-2">
                  {parentNodes.map((parent) => {
                    const edge = edges.find((e) => e.source === parent.id && e.target === node.id);
                    return (
                      <div
                        key={parent.id}
                        className="bg-slate-800 rounded p-2 text-sm border-l-2"
                        style={{
                          borderColor: getHealthColor(parent.alignment_health),
                        }}
                      >
                        <div className="text-slate-200 font-medium truncate">{parent.objective}</div>
                        <div className="text-xs text-slate-500 mt-1">
                          Level: <span className="capitalize text-slate-300">{parent.level}</span>
                        </div>
                        {edge && (
                          <div className="text-xs mt-1">
                            <span className="text-slate-500">Alignment:</span>{' '}
                            <span className="text-slate-300 font-mono">{edge.contribution_score}%</span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Cascade child OKRs */}
            {childNodes.length > 0 && (
              <div>
                <h4 className="font-semibold text-slate-200 flex items-center gap-2 mb-2">
                  <Users size={16} />
                  Cascade — Supported By ({childNodes.length})
                </h4>
                <div className="space-y-2">
                  {childNodes.map((child) => {
                    const edge = edges.find((e) => e.source === node.id && e.target === child.id);
                    return (
                      <div
                        key={child.id}
                        className="bg-slate-800 rounded p-2 text-sm border-l-2"
                        style={{
                          borderColor: getHealthColor(child.alignment_health),
                        }}
                      >
                        <div className="text-slate-200 font-medium truncate">{child.objective}</div>
                        <div className="text-xs text-slate-500 mt-1">
                          Level: <span className="capitalize text-slate-300">{child.level}</span>
                        </div>
                        {edge && (
                          <div className="text-xs mt-1">
                            <span className="text-slate-500">Contribution:</span>{' '}
                            <span className="text-slate-300 font-mono">{edge.contribution_score}%</span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {(functionalParents.length > 0 || functionalChildren.length > 0) && (
              <div className="space-y-3 pt-1 border-t border-slate-700/80">
                {functionalParents.length > 0 && (
                  <div>
                    <h4 className="font-semibold text-violet-300 flex items-center gap-2 mb-2 text-sm">
                      <Link2 size={14} className="opacity-80" />
                      Functional — Aligned To ({functionalParents.length})
                    </h4>
                    <div className="space-y-2">
                      {functionalParents.map((parent) => (
                        <div
                          key={parent.id}
                          className="bg-slate-800/80 rounded p-2 text-sm border-l-2 border-dashed border-violet-400/60"
                        >
                          <div className="text-slate-200 font-medium truncate">{parent.objective}</div>
                          <div className="text-xs text-slate-500 mt-1 capitalize">
                            {parent.node_kind?.replace(/_/g, ' ') || parent.level}
                            {parent.function_area && (
                              <> · {getFunctionAreaLabel(parent.function_area)}</>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {functionalChildren.length > 0 && (
                  <div>
                    <h4 className="font-semibold text-violet-300 flex items-center gap-2 mb-2 text-sm">
                      <Users size={14} className="opacity-80" />
                      Functional — Supports ({functionalChildren.length})
                    </h4>
                    <div className="space-y-2">
                      {functionalChildren.map((child) => (
                        <div
                          key={child.id}
                          className="bg-slate-800/80 rounded p-2 text-sm border-l-2 border-dashed border-violet-400/60"
                        >
                          <div className="text-slate-200 font-medium truncate">{child.objective}</div>
                          <div className="text-xs text-slate-500 mt-1 capitalize">
                            {child.plant_name || child.plant || child.level}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {onFocusHere && node.level !== 'employee' && (
              <button
                type="button"
                onClick={() => onFocusHere(node.id)}
                className="w-full py-2 px-3 rounded-lg bg-slate-800 text-slate-300 border border-slate-600 hover:bg-slate-700 text-sm font-medium transition"
              >
                Focus here
              </button>
            )}

            {/* Orphaned Warning */}
            {node.is_orphaned && (
              <div className="bg-red-500/20 border border-red-500/50 rounded-lg p-3 flex items-start gap-2">
                <AlertCircle size={16} className="text-red-400 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-red-200">
                  This OKR has no alignment to higher-level objectives. Consider reviewing its strategic alignment.
                </div>
              </div>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

// ============================================================================
// HELPER COMPONENTS
// ============================================================================

interface ProgressBarProps {
  label: string;
  value: number;
  color: string;
}

const ProgressBar: React.FC<ProgressBarProps> = ({ label, value, color }) => (
  <div>
    <div className="flex items-center justify-between mb-1">
      <span className="text-xs text-slate-400">{label}</span>
      <span className="text-xs font-mono text-slate-200">{Math.round(value)}%</span>
    </div>
    <div className="w-full h-2 bg-slate-700 rounded-full overflow-hidden">
      <div
        className="h-full transition-all duration-300"
        style={{
          width: `${Math.min(100, value)}%`,
          backgroundColor: color,
        }}
      />
    </div>
  </div>
);
