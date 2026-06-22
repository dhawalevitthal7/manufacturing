import React from 'react';
import { Orbit, Network, Eye, RefreshCw } from 'lucide-react';
import type { DisplayMode, RoleScopeConfig } from '@/types/constellation.types';

interface Props {
  scopeConfig: RoleScopeConfig;
  displayMode: DisplayMode;
  onDisplayModeChange: (mode: DisplayMode) => void;
  orphanedCount?: number;
  brokenCount?: number;
  lastUpdated?: string;
  onRefresh?: () => void;
}

export const ConstellationHeader: React.FC<Props> = ({
  scopeConfig,
  displayMode,
  onDisplayModeChange,
  orphanedCount = 0,
  brokenCount = 0,
  onRefresh,
}) => {
  const modes: Array<{ id: DisplayMode; label: string; icon: React.ReactNode }> = [
    { id: 'orbit', label: 'Orbit', icon: <Orbit size={16} /> },
    { id: 'graph', label: 'Graph', icon: <Network size={16} /> },
    { id: 'line-of-sight', label: 'Line of Sight', icon: <Eye size={16} /> },
  ];

  return (
    <div className="flex items-center justify-between gap-4 px-4 py-3 bg-slate-900 border-b border-slate-700">
      <div className="min-w-0">
        <h1 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
          <span>{scopeConfig.icon}</span>
          {scopeConfig.title}
        </h1>
        <p className="text-xs text-slate-400 truncate">{scopeConfig.subtitle}</p>
      </div>

      <div className="flex items-center gap-3 shrink-0">
        {orphanedCount > 0 && (
          <span className="px-2 py-1 text-xs rounded bg-amber-500/20 text-amber-300">
            {orphanedCount} unaligned
          </span>
        )}
        {brokenCount > 0 && (
          <span className="px-2 py-1 text-xs rounded bg-red-500/20 text-red-300">
            {brokenCount} weak links
          </span>
        )}

        <div className="flex rounded-lg bg-slate-800 p-0.5 border border-slate-700">
          {modes.map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() => onDisplayModeChange(m.id)}
              title={m.label}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition ${
                displayMode === m.id
                  ? 'bg-cyan-600 text-white'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {m.icon}
              <span className="hidden sm:inline">{m.label}</span>
            </button>
          ))}
        </div>

        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800"
            title="Refresh"
          >
            <RefreshCw size={16} />
          </button>
        )}
      </div>
    </div>
  );
};
