/**
 * Dashboard loading skeleton — mirrors the layout of `DashboardMetrics`,
 * `FormChart`, and `TickerTable` with shimmer placeholders.
 *
 * ## Why match the real layout exactly?
 *
 * Skeletons work because of **spatial continuity**: the user sees
 * placeholder shapes in the same positions where real content will
 * appear.  When data arrives, each placeholder is replaced by its
 * real counterpart without any layout shift.  This is why skeletons
 * feel faster than spinners — the user's brain is already processing
 * the page structure before the data arrives.
 *
 * ## Layout (mirrors `page.tsx` data branch)
 *
 *   1. Page header (icon + title) — static, no skeleton needed
 *   2. 3 MetricCard skeletons in a responsive grid
 *   3. 2-column grid: chart skeleton + table skeleton
 */

import { Skeleton } from "@/components/ui";

// ---------------------------------------------------------------------------
// Sub-components (private to this module)
// ---------------------------------------------------------------------------

/** Mirrors `MetricCard`: icon box + label + large value + optional bar. */
function MetricCardSkeleton({ showBar = false }: { showBar?: boolean }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-gray-950">
      {/* Icon + label row */}
      <div className="flex items-center gap-3">
        <Skeleton className="h-9 w-9 rounded-md" />
        <Skeleton className="h-4 w-16" />
      </div>
      {/* Large value */}
      <Skeleton className="mt-3 h-9 w-20" />
      {/* Capacity bar (only on the first card) */}
      {showBar && (
        <div className="mt-3">
          <Skeleton className="h-2 w-full rounded-full" />
          <Skeleton className="mt-1 h-3 w-16" />
        </div>
      )}
    </div>
  );
}

/** Mirrors `FormChart`: title + chart area. */
function ChartSkeleton() {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-gray-950">
      <Skeleton className="mb-4 h-6 w-48" />
      {/* Chart area with vertical bar placeholders */}
      <div className="flex h-64 items-end gap-6 px-4 pb-8">
        <Skeleton className="h-3/4 flex-1 rounded-t-md" />
        <Skeleton className="h-1/2 flex-1 rounded-t-md" />
        <Skeleton className="h-5/6 flex-1 rounded-t-md" />
      </div>
    </div>
  );
}

/** Mirrors `TickerTable`: title + header row + body rows. */
function TableSkeleton() {
  return (
    <div className="rounded-lg border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-950">
      <div className="px-6 py-4">
        <Skeleton className="h-6 w-24" />
      </div>
      {/* Header row */}
      <div className="flex gap-4 border-t border-gray-200 bg-gray-50 px-6 py-3 dark:border-gray-800 dark:bg-gray-900">
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-4 w-14" />
        <Skeleton className="h-4 w-14" />
        <Skeleton className="h-4 w-20" />
      </div>
      {/* Body rows */}
      {Array.from({ length: 3 }, (_, i) => (
        <div
          key={i}
          className="flex items-center gap-4 border-t border-gray-200 px-6 py-3 dark:border-gray-800"
        >
          <Skeleton className="h-4 w-14" />
          <Skeleton className="h-4 w-8" />
          <Skeleton className="h-4 w-12" />
          <div className="flex gap-1.5">
            <Skeleton className="h-5 w-12 rounded-full" />
            <Skeleton className="h-5 w-12 rounded-full" />
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

export function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      {/* Page header (static — matches real page) */}
      <div className="flex items-center gap-3">
        <Skeleton className="h-8 w-8 rounded-md" />
        <Skeleton className="h-7 w-36" />
      </div>

      {/* 3 metric cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <MetricCardSkeleton showBar />
        <MetricCardSkeleton />
        <MetricCardSkeleton />
      </div>

      {/* Chart + table in responsive 2-column grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        <ChartSkeleton />
        <TableSkeleton />
      </div>
    </div>
  );
}