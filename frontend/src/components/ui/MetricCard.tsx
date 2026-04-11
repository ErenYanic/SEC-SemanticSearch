/**
 * Dashboard KPI card — compact, terminal-style tile with a mono label,
 * a large tabular number, and an optional capacity bar.
 *
 * Layout is vertical-tight: label row on top, value below, capacity
 * (when present) at the bottom. Numbers use `tabular-nums` so that
 * counts in a row of cards align across the strip, which is the
 * single most effective density signal for a data dashboard.
 *
 * The capacity bar's fill is a dynamic percentage, so its width must
 * be set via inline `style` — Tailwind class names are static.
 */

import { type ElementType } from "react";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface MetricCardProps {
  /** Card title shown above the value (e.g. "Filings", "Chunks"). */
  label: string;
  /** The prominent value to display (number or formatted string). */
  value: number | string;
  /** Lucide icon component (passed as a reference, not rendered). */
  icon: ElementType;
  /** Optional capacity indicator with a progress bar. */
  capacity?: {
    /** Current count (e.g. number of filings stored). */
    current: number;
    /** Maximum allowed (e.g. DB_MAX_FILINGS). */
    max: number;
  };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MetricCard({ label, value, icon: Icon, capacity }: MetricCardProps) {
  const percent = capacity
    ? Math.min(Math.round((capacity.current / capacity.max) * 100), 100)
    : null;

  return (
    <div className="group relative overflow-hidden rounded-2xl border border-hairline bg-card/80 p-6 shadow-sm backdrop-blur-sm transition-all hover:-translate-y-0.5 hover:border-accent/40 hover:shadow-lg hover:shadow-accent/5">
      {/* subtle top highlight for depth */}
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/30 to-transparent opacity-0 transition-opacity group-hover:opacity-100"
        aria-hidden="true"
      />
      {/* ---- Header: label + icon ---- */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-fg-muted">{label}</span>
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent/10 text-accent">
          <Icon className="h-4 w-4" aria-hidden="true" />
        </span>
      </div>

      {/* ---- Value ---- */}
      <p className="mt-4 text-4xl font-semibold tracking-tight tabular-nums text-fg">
        {value}
      </p>

      {/* ---- Capacity bar (optional) ---- */}
      {capacity && percent !== null && (
        <div className="mt-5 space-y-2">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface">
            <div
              className="h-full rounded-full bg-gradient-to-r from-accent/70 to-accent transition-all"
              style={{ width: `${percent}%` }}
            />
          </div>
          <p className="flex items-baseline gap-1.5 text-sm tabular-nums text-fg-muted">
            <span className="font-medium text-fg">
              {capacity.current.toLocaleString()}
            </span>
            <span className="text-fg-subtle">of</span>
            <span>{capacity.max.toLocaleString()}</span>
            <span className="ml-auto font-medium text-accent">{percent}%</span>
          </p>
        </div>
      )}
    </div>
  );
}
