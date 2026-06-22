/**
 * Employee line-of-sight: upward chain from personal OKR to company goal.
 */

import React from 'react';
import { ArrowUp, Target } from 'lucide-react';
import type { LineOfSightNode } from '@/types/constellation.types';

interface Props {
  chain: LineOfSightNode[];
  organizationName?: string;
}

export const LineOfSightView: React.FC<Props> = ({ chain, organizationName }) => {
  if (!chain.length) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[400px] text-slate-400 p-8">
        <Target size={48} className="mb-4 opacity-40" />
        <p className="text-lg font-medium">No personal OKRs found</p>
        <p className="text-sm mt-2 text-center max-w-md">
          Create an individual OKR to see how your daily work connects to team and company goals.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-[500px] p-8 bg-slate-950">
      <h2 className="text-xl font-semibold text-slate-100 mb-2">Your Line of Sight</h2>
      <p className="text-sm text-slate-400 mb-8 text-center max-w-lg">
        How your work contributes to {organizationName ?? 'the organization'}
      </p>

      <div className="flex flex-col items-center gap-0 w-full max-w-md">
        {[...chain].reverse().map((node, idx, arr) => (
          <React.Fragment key={node.id}>
            <div
              className={`w-full rounded-xl border p-4 transition-all ${
                idx === arr.length - 1
                  ? 'border-cyan-500/50 bg-cyan-950/30 shadow-lg shadow-cyan-900/20'
                  : 'border-slate-700 bg-slate-900/80'
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <span className="text-xs uppercase tracking-wide text-slate-500">
                    {node.level}
                  </span>
                  <p className="text-sm font-medium text-slate-100 truncate mt-0.5">
                    {node.title}
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <span className="text-2xl font-bold text-cyan-400">{node.progress}%</span>
                </div>
              </div>
              <div className="mt-2 h-1.5 rounded-full bg-slate-800 overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-cyan-600 to-cyan-400"
                  style={{ width: `${Math.min(100, node.progress)}%` }}
                />
              </div>
            </div>
            {idx < arr.length - 1 && (
              <div className="flex flex-col items-center py-2 text-slate-600">
                <ArrowUp size={20} />
                <span className="text-[10px] uppercase tracking-wider">contributes to</span>
              </div>
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
};
