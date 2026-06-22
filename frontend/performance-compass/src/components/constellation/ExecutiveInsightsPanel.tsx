/**
 * ExecutiveInsightsPanel Component
 * ================================
 * Shows key insights about OKR alignment and health
 */

import React, { useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, AlertTriangle, TrendingDown, AlertCircle, Zap, CheckCircle, X } from 'lucide-react';
import { ExecutiveInsight, GraphStatistics, AIPrescription } from '@/types/constellation.types';
import { colorPalette } from '@/utils/nodeColor';

interface ExecutiveInsightsPanelProps {
  insights: ExecutiveInsight[];
  stats: GraphStatistics | null;
  aiPrescriptions?: AIPrescription[];
  isOpen: boolean;
  onClose: () => void;
  onInsightClick?: (insight: ExecutiveInsight) => void;
}

export const ExecutiveInsightsPanel: React.FC<ExecutiveInsightsPanelProps> = ({
  insights,
  stats,
  aiPrescriptions = [],
  isOpen,
  onClose,
  onInsightClick,
}) => {
  const sortedInsights = useMemo(() => {
    const severityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
    return [...insights].sort(
      (a, b) => severityOrder[a.severity] - severityOrder[b.severity]
    );
  }, [insights]);

  const criticalCount = insights.filter((i) => i.severity === 'critical').length;
  const highCount = insights.filter((i) => i.severity === 'high').length;

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ y: 400, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 400, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
          className="fixed bottom-0 left-0 right-0 max-h-96 bg-slate-900 border-t border-slate-700 z-40 flex flex-col overflow-hidden shadow-2xl"
        >
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-slate-700 bg-slate-800/50">
            <div className="flex items-center gap-2">
              <Zap size={20} className="text-amber-400" />
              <h3 className="text-lg font-semibold text-slate-100">Executive Insights</h3>
              {(criticalCount > 0 || highCount > 0) && (
                <div className="flex items-center gap-2 ml-4">
                  {criticalCount > 0 && (
                    <span className="px-2 py-1 bg-red-500/20 text-red-300 text-xs rounded font-medium">
                      {criticalCount} Critical
                    </span>
                  )}
                  {highCount > 0 && (
                    <span className="px-2 py-1 bg-orange-500/20 text-orange-300 text-xs rounded font-medium">
                      {highCount} High
                    </span>
                  )}
                </div>
              )}
            </div>
            <button
              onClick={onClose}
              className="p-1 hover:bg-slate-700 rounded transition"
            >
              <X size={20} className="text-slate-400" />
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto">
            {/* Statistics Summary */}
            {stats && (
              <div className="p-4 bg-slate-800/30 grid grid-cols-4 gap-2 text-xs border-b border-slate-700">
                <StatBox
                  label="Total OKRs"
                  value={stats.totalNodes}
                  color="text-slate-300"
                />
                <StatBox
                  label="Avg Alignment"
                  value={`${Math.round(stats.avgAlignment)}%`}
                  color={stats.avgAlignment >= 75 ? 'text-emerald-400' : stats.avgAlignment >= 60 ? 'text-amber-400' : 'text-red-400'}
                />
                <StatBox
                  label="Avg Confidence"
                  value={`${Math.round(stats.avgConfidence)}%`}
                  color={stats.avgConfidence >= 75 ? 'text-emerald-400' : 'text-amber-400'}
                />
                <StatBox
                  label="Orphaned"
                  value={stats.orphanedNodes}
                  color={stats.orphanedNodes > 0 ? 'text-red-400' : 'text-emerald-400'}
                />
              </div>
            )}

            {aiPrescriptions.length > 0 && (
              <div className="p-4 border-b border-slate-700 bg-indigo-950/20">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-indigo-300 mb-3">
                  AI Prescriptions
                </h4>
                <div className="space-y-2">
                  {aiPrescriptions.map((rx, i) => (
                    <div
                      key={`ai-${i}`}
                      className="rounded-lg border border-indigo-500/30 bg-indigo-500/5 p-3 text-sm"
                    >
                      <div className="font-medium text-indigo-200">{rx.title}</div>
                      <p className="text-slate-400 text-xs mt-1">{rx.description}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Insights List */}
            <div className="p-4 space-y-3">
              {sortedInsights.length === 0 ? (
                <div className="text-center py-8">
                  <CheckCircle size={32} className="mx-auto text-emerald-400 mb-2" />
                  <p className="text-slate-400 text-sm">All systems nominal. No insights to display.</p>
                </div>
              ) : (
                sortedInsights.map((insight, idx) => (
                  <InsightCard
                    key={insight.id}
                    insight={insight}
                    index={idx}
                    onClick={() => onInsightClick?.(insight)}
                  />
                ))
              )}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

// ============================================================================
// HELPER COMPONENTS
// ============================================================================

interface StatBoxProps {
  label: string;
  value: string | number;
  color: string;
}

const StatBox: React.FC<StatBoxProps> = ({ label, value, color }) => (
  <div className="text-center">
    <div className="text-slate-500 mb-1">{label}</div>
    <div className={`font-bold text-lg ${color}`}>{value}</div>
  </div>
);

interface InsightCardProps {
  insight: ExecutiveInsight;
  index: number;
  onClick?: () => void;
}

const InsightCard: React.FC<InsightCardProps> = ({ insight, index, onClick }) => {
  const [expanded, setExpanded] = React.useState(false);

  const severityColor: Record<string, string> = {
    critical: 'border-red-500 bg-red-500/10',
    high: 'border-orange-500 bg-orange-500/10',
    medium: 'border-amber-500 bg-amber-500/10',
    low: 'border-emerald-500 bg-emerald-500/10',
  };

  const severityIcon: Record<string, React.ReactNode> = {
    critical: <AlertTriangle size={16} className="text-red-400" />,
    high: <AlertTriangle size={16} className="text-orange-400" />,
    medium: <AlertCircle size={16} className="text-amber-400" />,
    low: <CheckCircle size={16} className="text-emerald-400" />,
  };

  const typeIcon: Record<string, React.ReactNode> = {
    bottleneck: <AlertCircle size={14} />,
    orphan: <TrendingDown size={14} />,
    weak_alignment: <AlertTriangle size={14} />,
    strong_contributor: <CheckCircle size={14} />,
    risk_propagation: <AlertTriangle size={14} />,
    top_aligned: <Zap size={14} />,
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      onClick={() => {
        onClick?.();
        setExpanded(!expanded);
      }}
      className={`border-l-4 rounded-lg p-3 cursor-pointer transition-all hover:bg-opacity-80 ${
        severityColor[insight.severity]
      }`}
    >
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 mt-1">{severityIcon[insight.severity]}</div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <div className="flex items-center gap-1 text-slate-300 text-sm">
              {typeIcon[insight.type]}
              <span className="font-semibold">{insight.title}</span>
            </div>
          </div>

          {expanded && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="mt-2 text-xs text-slate-300 space-y-2"
            >
              <p>{insight.description}</p>

              {insight.impact !== undefined && (
                <div className="text-slate-400">
                  <span>Impact: </span>
                  <span className="font-mono text-amber-300">{Math.round(insight.impact)}%</span>
                </div>
              )}

              {insight.actionable && insight.actionText && (
                <button className="mt-2 px-2 py-1 bg-blue-600 hover:bg-blue-700 rounded text-xs font-medium text-white transition">
                  {insight.actionText}
                </button>
              )}
            </motion.div>
          )}

          {!expanded && (
            <p className="text-xs text-slate-400 line-clamp-1">{insight.description}</p>
          )}
        </div>

        {expanded && <ChevronDown size={16} className="text-slate-500 flex-shrink-0 mt-1" />}
      </div>
    </motion.div>
  );
};
