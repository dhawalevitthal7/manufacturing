/**
 * Minimal floating controls — view mode + zoom only (visual-first constellation)
 */

import React from 'react';
import { Orbit, Network, Eye, ZoomIn, ZoomOut, Home, Download, ChevronsDownUp, ChevronsUpDown } from 'lucide-react';
import type { DisplayMode } from '@/types/constellation.types';

interface Props {
  displayMode: DisplayMode;
  onDisplayModeChange: (mode: DisplayMode) => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
  onExport?: () => void;
  orgName?: string;
  avgProgress?: number;
  showExpansionControls?: boolean;
  onExpandAll?: () => void;
  onCollapseAll?: () => void;
}

export const ConstellationFloatingControls: React.FC<Props> = ({
  displayMode,
  onDisplayModeChange,
  onZoomIn,
  onZoomOut,
  onReset,
  onExport,
  orgName,
  avgProgress,
  showExpansionControls,
  onExpandAll,
  onCollapseAll,
}) => {
  const modes: Array<{ id: DisplayMode; icon: React.ReactNode; label: string }> = [
    { id: 'orbit', icon: <Orbit size={16} />, label: 'Orbit' },
    { id: 'graph', icon: <Network size={16} />, label: 'Graph' },
    { id: 'line-of-sight', icon: <Eye size={16} />, label: 'Line of Sight' },
  ];

  return (
    <>
      {/* Top-left: subtle org label */}
      {orgName && (
        <div className="absolute top-4 left-4 z-20 pointer-events-none">
          <p className="text-[11px] uppercase tracking-[0.2em] text-cyan-500/70 font-medium">
            Alignment
          </p>
          <p className="text-sm font-semibold text-white/90 drop-shadow-lg">{orgName}</p>
          {avgProgress != null && (
            <div className="mt-2 flex items-center gap-2">
              <div className="h-1 w-24 rounded-full bg-white/10 overflow-hidden backdrop-blur-sm">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-teal-400 transition-all duration-700"
                  style={{ width: `${Math.min(100, avgProgress)}%` }}
                />
              </div>
              <span className="text-xs font-bold text-cyan-300">{avgProgress}%</span>
            </div>
          )}
        </div>
      )}

      {/* Bottom-center: glass control pill */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20 flex items-center gap-1 px-2 py-1.5 rounded-2xl bg-slate-900/60 backdrop-blur-xl border border-white/10 shadow-[0_8px_32px_rgba(0,0,0,0.5)]">
        <div className="flex items-center gap-0.5 pr-1 border-r border-white/10">
          {modes.map((m) => (
            <button
              key={m.id}
              type="button"
              title={m.label}
              onClick={() => onDisplayModeChange(m.id)}
              className={`p-2 rounded-xl transition-all duration-200 ${
                displayMode === m.id
                  ? 'bg-cyan-500/25 text-cyan-300 shadow-[0_0_12px_rgba(34,211,238,0.3)]'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
              }`}
            >
              {m.icon}
            </button>
          ))}
        </div>

        {showExpansionControls && (
          <div className="flex items-center gap-0.5 pr-1 border-r border-white/10">
            <button type="button" onClick={onExpandAll} title="Expand all" className={btnClass}>
              <ChevronsUpDown size={16} />
            </button>
            <button type="button" onClick={onCollapseAll} title="Collapse all" className={btnClass}>
              <ChevronsDownUp size={16} />
            </button>
          </div>
        )}

        <button type="button" onClick={onZoomOut} title="Zoom out" className={btnClass}>
          <ZoomOut size={16} />
        </button>
        <button type="button" onClick={onZoomIn} title="Zoom in" className={btnClass}>
          <ZoomIn size={16} />
        </button>
        <button type="button" onClick={onReset} title="Reset view" className={btnClass}>
          <Home size={16} />
        </button>
        {onExport && (
          <button type="button" onClick={onExport} title="Export" className={btnClass}>
            <Download size={16} />
          </button>
        )}
      </div>

      {/* Bottom-right: interaction hint */}
      <p className="absolute bottom-4 right-4 z-20 text-[10px] text-slate-500/80 pointer-events-none hidden sm:block">
        Scroll to zoom · Drag to pan · Click cluster to expand
      </p>
    </>
  );
};

const btnClass =
  'p-2 rounded-xl text-slate-400 hover:text-cyan-300 hover:bg-white/5 transition-all duration-200';
