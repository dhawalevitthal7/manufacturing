import React from 'react';
import { ChevronRight, Home } from 'lucide-react';

export interface ExpansionCrumb {
  id: string;
  label: string;
}

interface Props {
  crumbs: ExpansionCrumb[];
  onCrumbClick?: (crumbId: string, index: number) => void;
}

export const ConstellationBreadcrumb: React.FC<Props> = ({ crumbs, onCrumbClick }) => {
  if (crumbs.length <= 1) return null;

  return (
    <nav className="flex items-center gap-1 text-xs text-slate-400 px-4 py-2 border-b border-slate-800 bg-slate-950/80 backdrop-blur-sm">
      <button
        type="button"
        onClick={() => onCrumbClick?.(crumbs[0].id, 0)}
        className="flex items-center gap-1 hover:text-cyan-400 transition"
        title="Collapse all"
      >
        <Home size={14} />
      </button>
      {crumbs.map((c, i) => (
        <React.Fragment key={c.id}>
          <ChevronRight size={12} className="text-slate-600" />
          <button
            type="button"
            onClick={() => onCrumbClick?.(c.id, i)}
            className={`hover:text-cyan-400 transition ${
              i === crumbs.length - 1 ? 'text-slate-200 font-medium' : ''
            }`}
          >
            {c.label}
          </button>
        </React.Fragment>
      ))}
    </nav>
  );
};
