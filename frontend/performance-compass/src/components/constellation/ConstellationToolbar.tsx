/**
 * ConstellationToolbar Component
 * =============================
 * Top toolbar with controls for the constellation visualization.
 * Adapts view mode options based on user's role scope.
 */

import React, { useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  Search,
  Filter,
  ZoomIn,
  ZoomOut,
  Home,
  Download,
  Eye,
  Settings,
  Sparkles,
} from 'lucide-react';
import { ViewMode, RoleScopeConfig } from '@/types/constellation.types';
import { colorPalette } from '@/utils/nodeColor';

interface ConstellationToolbarProps {
  viewMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;
  onToggleFilters: () => void;
  onToggleInsights: () => void;
  onSearch: (query: string) => void;
  onZoomIn?: () => void;
  onZoomOut?: () => void;
  onReset?: () => void;
  onExport?: () => void;
  searchQuery?: string;
  /** View modes available for this user's scope */
  availableViewModes?: string[];
  /** Scope configuration for role-aware labels */
  scopeConfig?: RoleScopeConfig;
}

export const ConstellationToolbar: React.FC<ConstellationToolbarProps> = ({
  viewMode,
  onViewModeChange,
  onToggleFilters,
  onToggleInsights,
  onSearch,
  onZoomIn,
  onZoomOut,
  onReset,
  onExport,
  searchQuery = '',
  availableViewModes,
  scopeConfig,
}) => {
  const handleSearchChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      onSearch(e.target.value);
    },
    [onSearch]
  );

  // All possible view modes with their config
  const allViewModes: Array<{ value: ViewMode; label: string; icon: React.ReactNode }> = [
    { value: 'galaxy', label: 'Galaxy', icon: <Sparkles size={16} /> },
    { value: 'strategic', label: 'Strategic', icon: <Settings size={16} /> },
    { value: 'risk', label: 'Risk', icon: <Eye size={16} /> },
    { value: 'plant', label: 'Plant', icon: <Eye size={16} /> },
    { value: 'department', label: 'Department', icon: <Eye size={16} /> },
  ];

  // Filter view modes based on what's available for this user's scope
  const viewModes = availableViewModes
    ? allViewModes.filter((m) => availableViewModes.includes(m.value))
    : allViewModes;

  // Dynamic search placeholder based on scope
  const searchPlaceholder = scopeConfig
    ? `Search ${scopeConfig.orbitLabel.toLowerCase()}, OKRs, owners...`
    : 'Search OKRs, owners, plants...';

  return (
    <motion.div
      initial={{ y: -60, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      className="flex items-center gap-3 p-3 bg-slate-900 border-b border-slate-700 flex-wrap"
    >
      {/* Search Box */}
      <div className="flex-1 min-w-64 flex items-center gap-2 bg-slate-800 rounded-lg px-3 py-2 border border-slate-700">
        <Search size={18} className="text-slate-500" />
        <input
          type="text"
          placeholder={searchPlaceholder}
          value={searchQuery}
          onChange={handleSearchChange}
          className="flex-1 bg-transparent text-slate-100 outline-none placeholder-slate-500 text-sm"
        />
      </div>

      {/* View Mode Selector */}
      <div className="flex items-center gap-2 bg-slate-800 rounded-lg p-1">
        {viewModes.map((mode) => (
          <button
            key={mode.value}
            onClick={() => onViewModeChange(mode.value)}
            title={mode.label}
            className={`p-2 rounded transition-colors ${
              viewMode === mode.value
                ? 'bg-cyan-600 text-white'
                : 'text-slate-400 hover:text-slate-300 hover:bg-slate-700'
            }`}
          >
            {mode.icon}
          </button>
        ))}
      </div>

      {/* Control Buttons */}
      <div className="flex items-center gap-1 bg-slate-800 rounded-lg p-1">
        {onZoomIn && (
          <ToolbarButton onClick={onZoomIn} title="Zoom In" icon={<ZoomIn size={18} />} />
        )}
        {onZoomOut && (
          <ToolbarButton onClick={onZoomOut} title="Zoom Out" icon={<ZoomOut size={18} />} />
        )}
        {onReset && (
          <ToolbarButton
            onClick={onReset}
            title="Reset View"
            icon={<Home size={18} />}
            variant="secondary"
          />
        )}
      </div>

      {/* Panel Toggles */}
      <div className="flex items-center gap-1 bg-slate-800 rounded-lg p-1">
        <ToolbarButton
          onClick={onToggleFilters}
          title="Filters"
          icon={<Filter size={18} />}
          variant="secondary"
        />
        <ToolbarButton
          onClick={onToggleInsights}
          title="Insights"
          icon={<Sparkles size={18} />}
          variant="secondary"
        />
      </div>

      {/* Export Button */}
      {onExport && (
        <ToolbarButton
          onClick={onExport}
          title="Export"
          icon={<Download size={18} />}
          variant="secondary"
        />
      )}

      {/* Legend - role-aware labels */}
      <div className="hidden lg:flex items-center gap-3 ml-auto pl-4 border-l border-slate-700 text-xs">
        <LegendItem color={colorPalette.healthy} label="On Track" />
        <LegendItem color={colorPalette.needsAttention} label="Attention" />
        <LegendItem color={colorPalette.critical} label="Critical" />
        <LegendItem color={colorPalette.blocked} label="Blocked" />
      </div>
    </motion.div>
  );
};

// ============================================================================
// HELPER COMPONENTS
// ============================================================================

interface ToolbarButtonProps {
  onClick: () => void;
  title: string;
  icon: React.ReactNode;
  variant?: 'primary' | 'secondary';
}

const ToolbarButton: React.FC<ToolbarButtonProps> = ({
  onClick,
  title,
  icon,
  variant = 'primary',
}) => (
  <button
    onClick={onClick}
    title={title}
    className={`p-2 rounded transition-colors ${
      variant === 'primary'
        ? 'text-slate-300 hover:text-white hover:bg-slate-700'
        : 'text-slate-400 hover:text-slate-300 hover:bg-slate-700'
    }`}
  >
    {icon}
  </button>
);

interface LegendItemProps {
  color: string;
  label: string;
}

const LegendItem: React.FC<LegendItemProps> = ({ color, label }) => (
  <div className="flex items-center gap-2">
    <div
      className="w-2 h-2 rounded-full"
      style={{ backgroundColor: color }}
    />
    <span className="text-slate-400">{label}</span>
  </div>
);
