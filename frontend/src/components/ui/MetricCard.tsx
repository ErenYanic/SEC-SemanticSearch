/**
 * Dashboard metric card — displays a large number with a label,
 * an icon, and an optional capacity progress bar.
 *
 * Used on the Dashboard page (W3.1) to show:
 *   - Filing count (with capacity bar: current / max)
 *   - Chunk count
 *   - Ticker count
 *
 * ## Why `ElementType` for the icon?
 *
 * This is the same pattern used in `Navbar.tsx` for nav item icons:
 * you pass the Lucide component reference (e.g. `FileText`), and
 * MetricCard renders it with the right size and colour classes.
 * `ElementType` is React's type for "any component that can be
 * rendered as JSX".
 *
 * ## Why the capacity bar uses inline `style`
 *
 * The fill width is dynamic (e.g. 45%).  Tailwind classes like
 * `w-[45%]` must exist in source code at build time — they can't
 * be computed at runtime.  Inline `style={{ width: "45%" }}` is
 * the correct approach for dynamic values.
 *
 * No `"use client"` needed — pure presentational component.
 */

import { type ElementType } from "react";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface MetricCardProps {
  /** Card title shown below the icon (e.g. "Filings", "Chunks"). */
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
  // Calculate the fill percentage for the capacity bar.
  // `Math.min` caps at 100% so the bar never overflows.
  const percent = capacity
    ? Math.min(Math.round((capacity.current / capacity.max) * 100), 100)
    : null;

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-gray-950">
      {/* ---- Header: icon + label ---- */}
      <div className="flex items-center gap-3">
        {/* Icon sits in a tinted rounded box for visual emphasis */}
        <div className="rounded-md bg-blue-50 p-2 dark:bg-blue-950">
          <Icon className="h-5 w-5 text-blue-600 dark:text-blue-400" />
        </div>
        <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
          {label}
        </span>
      </div>

      {/* ---- Value ---- */}
      <p className="mt-3 text-3xl font-bold text-gray-900 dark:text-gray-100">
        {value}
      </p>

      {/* ---- Capacity bar (optional) ---- */}
      {capacity && percent !== null && (
        <div className="mt-3">
          {/* Track — the full-width background bar */}
          <div className="h-2 w-full rounded-full bg-gray-100 dark:bg-gray-800">
            {/* Fill — width is set via inline style (dynamic value) */}
            <div
              className="h-full rounded-full bg-blue-600 transition-all dark:bg-blue-400"
              style={{ width: `${percent}%` }}
            />
          </div>
          {/* Caption below the bar */}
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            {capacity.current} / {capacity.max}
          </p>
        </div>
      )}
    </div>
  );
}