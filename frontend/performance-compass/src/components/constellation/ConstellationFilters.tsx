/**
 * ConstellationFilters Component
 * =============================
 * Advanced filtering panel for constellation visualization
 */

import React, { useState, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, ChevronDown } from 'lucide-react';
import { useConstellationStore } from '@/store/constellationStore';
import { ConstellationFilters as FilterType, OKRLevel, OKRHealth, RiskLevel, AlignmentType, FunctionArea } from '@/types/constellation.types';
import { colorPalette } from '@/utils/nodeColor';
import { FUNCTION_AREAS, FUNCTION_AREA_LABELS, FUNCTION_AREA_COLORS, isCeoRole, isFunctionalHeadRole } from '@/utils/functionArea';
import { useAuthStore } from '@/lib/stores/auth-store';

interface ConstellationFiltersProps {
  isOpen: boolean;
  onClose: () => void;
  onApply?: (filters: FilterType) => void;
}

export const ConstellationFilters: React.FC<ConstellationFiltersProps> = ({
  isOpen,
  onClose,
  onApply,
}) => {
  const store = useConstellationStore();
  const userRole = useAuthStore((s) => s.user?.system_role);
  const canPickFunction = isCeoRole(userRole);
  const functionLocked = isFunctionalHeadRole(userRole);
  const [localFilters, setLocalFilters] = useState<FilterType>(store.filters);
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    levels: true,
    function: true,
    health: true,
    risk: true,
    progress: false,
    scope: true,
    alignment: true,
  });

  useEffect(() => {
    if (isOpen) {
      setLocalFilters(store.filters);
    }
  }, [isOpen, store.filters]);

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  const updateFilter = (key: keyof FilterType, value: any) => {
    setLocalFilters((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleApply = useCallback(() => {
    onApply?.(localFilters);
  }, [localFilters, onApply]);

  const handleReset = useCallback(() => {
    const resetFilters: FilterType = {};
    setLocalFilters(resetFilters);
    onApply?.(resetFilters);
  }, [onApply]);

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/50 z-40"
          />

          {/* Filter Panel */}
          <motion.div
            initial={{ x: -400, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: -400, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            className="fixed left-0 top-0 h-full w-96 bg-slate-900 border-r border-slate-700 z-50 flex flex-col overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-slate-700">
              <h3 className="text-lg font-semibold text-slate-100">Filters</h3>
              <button
                onClick={onClose}
                className="p-1 hover:bg-slate-800 rounded transition"
              >
                <X size={20} className="text-slate-400" />
              </button>
            </div>

            {/* Filters Content */}
            <div className="flex-1 overflow-y-auto space-y-1 p-4">
              {/* OKR Level Filter */}
              <FilterSection
                title="OKR Level"
                expanded={expandedSections.levels}
                onToggle={() => toggleSection('levels')}
              >
                <div className="space-y-2">
                  {(['organization', 'region', 'plant', 'department', 'team', 'employee'] as OKRLevel[]).map((level) => (
                    <label key={level} className="flex items-center gap-2 text-sm cursor-pointer">
                      <input
                        type="checkbox"
                        checked={(localFilters.levels || []).includes(level)}
                        onChange={(e) => {
                          const levels = localFilters.levels || [];
                          updateFilter(
                            'levels',
                            e.target.checked
                              ? [...levels, level]
                              : levels.filter((l) => l !== level)
                          );
                        }}
                        className="w-4 h-4 rounded border-slate-600"
                      />
                      <span className="text-slate-300 capitalize">{level}</span>
                    </label>
                  ))}
                </div>
              </FilterSection>

              {(canPickFunction || functionLocked) && (
                <FilterSection
                  title="Corporate Function"
                  expanded={expandedSections.function ?? true}
                  onToggle={() => toggleSection('function')}
                >
                  {canPickFunction ? (
                    <select
                      value={localFilters.functionArea ?? ''}
                      onChange={(e) =>
                        updateFilter(
                          'functionArea',
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
                    <div className="flex items-center gap-2 text-sm text-slate-300">
                      <span
                        className="w-3 h-3 rounded-full"
                        style={{
                          backgroundColor: localFilters.functionArea
                            ? FUNCTION_AREA_COLORS[localFilters.functionArea]
                            : '#64748b',
                        }}
                      />
                      {localFilters.functionArea
                        ? FUNCTION_AREA_LABELS[localFilters.functionArea]
                        : 'Your function (auto)'}
                    </div>
                  )}
                  {canPickFunction && (
                    <label className="flex items-center gap-2 text-sm cursor-pointer mt-2">
                      <input
                        type="checkbox"
                        checked={localFilters.groupByFunction || false}
                        onChange={(e) => updateFilter('groupByFunction', e.target.checked)}
                        className="w-4 h-4 rounded border-slate-600"
                      />
                      <span className="text-slate-300">Group by function</span>
                    </label>
                  )}
                </FilterSection>
              )}

              {/* Health Status Filter */}
              <FilterSection
                title="Health Status"
                expanded={expandedSections.health}
                onToggle={() => toggleSection('health')}
              >
                <div className="space-y-2">
                  {(['healthy', 'needs_attention', 'critical', 'blocked'] as OKRHealth[]).map((health) => (
                    <label key={health} className="flex items-center gap-2 text-sm cursor-pointer">
                      <input
                        type="checkbox"
                        checked={(localFilters.healthStatus || []).includes(health)}
                        onChange={(e) => {
                          const healthStatus = localFilters.healthStatus || [];
                          updateFilter(
                            'healthStatus',
                            e.target.checked
                              ? [...healthStatus, health]
                              : healthStatus.filter((h) => h !== health)
                          );
                        }}
                        className="w-4 h-4 rounded border-slate-600"
                      />
                      <div className="flex items-center gap-2">
                        <span className={`w-3 h-3 rounded-full`} style={{
                          backgroundColor: getHealthColor(health),
                        }} />
                        <span className="text-slate-300 capitalize">{health.replace('_', ' ')}</span>
                      </div>
                    </label>
                  ))}
                </div>
              </FilterSection>

              {/* Risk Level Filter */}
              <FilterSection
                title="Risk Level"
                expanded={expandedSections.risk}
                onToggle={() => toggleSection('risk')}
              >
                <div className="space-y-2">
                  {(['critical', 'high', 'medium', 'low'] as RiskLevel[]).map((risk) => (
                    <label key={risk} className="flex items-center gap-2 text-sm cursor-pointer">
                      <input
                        type="checkbox"
                        checked={(localFilters.riskLevels || []).includes(risk)}
                        onChange={(e) => {
                          const riskLevels = localFilters.riskLevels || [];
                          updateFilter(
                            'riskLevels',
                            e.target.checked
                              ? [...riskLevels, risk]
                              : riskLevels.filter((r) => r !== risk)
                          );
                        }}
                        className="w-4 h-4 rounded border-slate-600"
                      />
                      <span className="text-slate-300 capitalize">{risk}</span>
                    </label>
                  ))}
                </div>
              </FilterSection>

              {/* Progress Range Filter */}
              <FilterSection
                title="Progress Range"
                expanded={expandedSections.progress ?? false}
                onToggle={() => toggleSection('progress')}
              >
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs text-slate-400 mb-2">Min: {localFilters.progressRange?.[0] || 0}%</label>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={localFilters.progressRange?.[0] || 0}
                      onChange={(e) => {
                        const min = parseInt(e.target.value);
                        const max = localFilters.progressRange?.[1] || 100;
                        updateFilter('progressRange', [min, max]);
                      }}
                      className="w-full h-2 bg-slate-700 rounded accent-cyan-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-400 mb-2">Max: {localFilters.progressRange?.[1] || 100}%</label>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={localFilters.progressRange?.[1] || 100}
                      onChange={(e) => {
                        const max = parseInt(e.target.value);
                        const min = localFilters.progressRange?.[0] || 0;
                        updateFilter('progressRange', [min, max]);
                      }}
                      className="w-full h-2 bg-slate-700 rounded accent-cyan-500"
                    />
                  </div>
                </div>
              </FilterSection>

              {/* Alignment Type Filter */}
              <FilterSection
                title="Alignment Types"
                expanded={expandedSections.alignment}
                onToggle={() => toggleSection('alignment')}
              >
                <div className="space-y-2">
                  {(['strategic', 'operational', 'support', 'dependency', 'cross-functional'] as AlignmentType[]).map((type) => (
                    <label key={type} className="flex items-center gap-2 text-sm cursor-pointer">
                      <input
                        type="checkbox"
                        checked={(localFilters.alignmentTypes || []).includes(type)}
                        onChange={(e) => {
                          const types = localFilters.alignmentTypes || [];
                          updateFilter(
                            'alignmentTypes',
                            e.target.checked
                              ? [...types, type]
                              : types.filter((t) => t !== type)
                          );
                        }}
                        className="w-4 h-4 rounded border-slate-600"
                      />
                      <span className="text-slate-300 capitalize">{type}</span>
                    </label>
                  ))}
                </div>
              </FilterSection>

              {/* Toggle Filters */}
              <div className="space-y-2 pt-4 border-t border-slate-700 mt-4">
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="checkbox"
                    checked={localFilters.orphanedOnly || false}
                    onChange={(e) => updateFilter('orphanedOnly', e.target.checked)}
                    className="w-4 h-4 rounded border-slate-600"
                  />
                  <span className="text-slate-300">Orphaned OKRs Only</span>
                </label>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="checkbox"
                    checked={localFilters.strategicOnly || false}
                    onChange={(e) => updateFilter('strategicOnly', e.target.checked)}
                    className="w-4 h-4 rounded border-slate-600"
                  />
                  <span className="text-slate-300">Strategic Only (Weight ≥ 4)</span>
                </label>
              </div>
            </div>

            {/* Footer Actions */}
            <div className="flex gap-2 p-4 border-t border-slate-700">
              <button
                onClick={handleReset}
                className="flex-1 px-3 py-2 bg-slate-800 hover:bg-slate-700 rounded text-sm text-slate-300 transition"
              >
                Reset
              </button>
              <button
                onClick={handleApply}
                className="flex-1 px-3 py-2 bg-cyan-600 hover:bg-cyan-700 rounded text-sm text-white transition font-medium"
              >
                Apply Filters
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

// ============================================================================
// HELPER COMPONENTS
// ============================================================================

interface FilterSectionProps {
  title: string;
  expanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}

const FilterSection: React.FC<FilterSectionProps> = ({ title, expanded, onToggle, children }) => (
  <div className="bg-slate-800 rounded border border-slate-700">
    <button
      onClick={onToggle}
      className="w-full flex items-center justify-between p-3 hover:bg-slate-750 transition"
    >
      <span className="text-sm font-medium text-slate-200">{title}</span>
      <ChevronDown
        size={16}
        className={`text-slate-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
      />
    </button>
    <AnimatePresence>
      {expanded && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          className="border-t border-slate-700 p-3 bg-slate-800/50"
        >
          {children}
        </motion.div>
      )}
    </AnimatePresence>
  </div>
);

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

const getHealthColor = (health: OKRHealth): string => {
  const colorMap: Record<OKRHealth, string> = {
    healthy: colorPalette.healthy,
    needs_attention: colorPalette.needsAttention,
    critical: colorPalette.critical,
    blocked: colorPalette.blocked,
  };
  return colorMap[health] || colorPalette.orphaned;
};
