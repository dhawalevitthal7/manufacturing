/**
 * Function lens + edge legend for constellation (CEO / functional-head views)
 */

import React from 'react';
import type { FunctionArea } from '@/types/constellation.types';
import {
  FUNCTION_AREAS,
  FUNCTION_AREA_LABELS,
  FUNCTION_AREA_COLORS,
  getFunctionAreaLabel,
  isCeoRole,
  isFunctionalHeadRole,
} from '@/utils/functionArea';
import type { SystemRole } from '@/lib/api';

interface Props {
  userRole?: SystemRole | string;
  functionArea?: FunctionArea;
  groupByFunction?: boolean;
  onFunctionAreaChange?: (area: FunctionArea | undefined) => void;
  onGroupByFunctionChange?: (enabled: boolean) => void;
}

export const ConstellationFunctionControls: React.FC<Props> = ({
  userRole,
  functionArea,
  groupByFunction,
  onFunctionAreaChange,
  onGroupByFunctionChange,
}) => {
  const isCeo = isCeoRole(userRole);
  const isFunctionalHead = isFunctionalHeadRole(userRole);
  const showLens = isCeo || isFunctionalHead;

  if (!showLens) return null;

  return (
    <div className="absolute top-4 right-4 z-20 flex flex-col gap-2 max-w-xs">
      <div className="rounded-xl bg-slate-900/70 backdrop-blur-xl border border-white/10 p-3 shadow-lg space-y-2">
        <p className="text-[10px] uppercase tracking-wider text-slate-500 font-medium">Function lens</p>
        {isCeo ? (
          <select
            value={functionArea ?? ''}
            onChange={(e) =>
              onFunctionAreaChange?.(
                e.target.value ? (e.target.value as FunctionArea) : undefined,
              )
            }
            className="w-full text-sm rounded-lg bg-slate-800 border border-slate-600 text-slate-200 px-2 py-1.5"
          >
            <option value="">All functions</option>
            {FUNCTION_AREAS.map((a) => (
              <option key={a} value={a}>
                {FUNCTION_AREA_LABELS[a]}
              </option>
            ))}
          </select>
        ) : (
          <div className="flex items-center gap-2 text-sm text-slate-200">
            <span
              className="w-2.5 h-2.5 rounded-full shrink-0"
              style={{ backgroundColor: functionArea ? FUNCTION_AREA_COLORS[functionArea] : '#64748b' }}
            />
            {functionArea ? getFunctionAreaLabel(functionArea) : 'Your function'}
          </div>
        )}

        {isCeo && (
          <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer pt-1">
            <input
              type="checkbox"
              checked={!!groupByFunction}
              onChange={(e) => onGroupByFunctionChange?.(e.target.checked)}
              className="rounded border-slate-600"
            />
            Group by function
          </label>
        )}
      </div>

      <div className="rounded-xl bg-slate-900/60 backdrop-blur-xl border border-white/10 px-3 py-2 shadow-lg">
        <p className="text-[10px] uppercase tracking-wider text-slate-500 font-medium mb-1.5">Edges</p>
        <div className="flex flex-col gap-1 text-[11px] text-slate-300">
          <div className="flex items-center gap-2">
            <span className="w-8 h-0 border-t-2 border-cyan-400/80" />
            Cascade (line hierarchy)
          </div>
          <div className="flex items-center gap-2">
            <span className="w-8 h-0 border-t-2 border-dashed border-violet-400/80" />
            Functional (dotted-line)
          </div>
        </div>
        {isCeo && (
          <div className="mt-2 pt-2 border-t border-white/5 flex flex-wrap gap-x-2 gap-y-1">
            {FUNCTION_AREAS.slice(0, 4).map((a) => (
              <span key={a} className="inline-flex items-center gap-1 text-[10px] text-slate-400">
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: FUNCTION_AREA_COLORS[a] }} />
                {FUNCTION_AREA_LABELS[a].split(' ')[0]}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
