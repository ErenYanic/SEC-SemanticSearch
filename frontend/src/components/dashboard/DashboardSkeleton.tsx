/**
 * Dashboard loading skeleton — mirrors the two-row workbench layout
 * of `DashboardMetrics` + `FormChart` + `TickerTable` so placeholders
 * land in the same positions as the real content. This preserves
 * spatial continuity when the data resolves — the user starts
 * processing the layout before the numbers arrive.
 */

import { Skeleton } from "@/components/ui";

// ---------------------------------------------------------------------------
// Sub-components (private to this module)
// ---------------------------------------------------------------------------

function MetricCardSkeleton({ showBar = false }: { showBar?: boolean }) {
  return (
    <div className="rounded-2xl border border-hairline bg-card/80 p-6">
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-9 w-9 rounded-lg" />
      </div>
      <Skeleton className="mt-4 h-10 w-24" />
      {showBar && (
        <div className="mt-5 space-y-2">
          <Skeleton className="h-1.5 w-full rounded-full" />
          <Skeleton className="h-4 w-28" />
        </div>
      )}
    </div>
  );
}

function ChartSkeleton() {
  return (
    <div className="rounded-2xl border border-hairline bg-card/80">
      <div className="flex items-baseline justify-between border-b border-hairline px-6 py-4">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-4 w-24" />
      </div>
      <div className="flex h-72 items-end gap-6 p-6 pb-10">
        <Skeleton className="h-3/4 flex-1 rounded-t-lg" />
        <Skeleton className="h-1/2 flex-1 rounded-t-lg" />
        <Skeleton className="h-5/6 flex-1 rounded-t-lg" />
        <Skeleton className="h-2/3 flex-1 rounded-t-lg" />
      </div>
    </div>
  );
}

function TableSkeleton() {
  return (
    <div className="rounded-2xl border border-hairline bg-card/80">
      <div className="flex items-baseline justify-between border-b border-hairline px-6 py-4">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-4 w-24" />
      </div>
      <div className="flex gap-4 border-b border-hairline bg-surface/60 px-6 py-3">
        <Skeleton className="h-4 w-16" />
        <Skeleton className="ml-auto h-4 w-12" />
        <Skeleton className="h-4 w-14" />
        <Skeleton className="h-4 w-16" />
      </div>
      {Array.from({ length: 4 }, (_, i) => (
        <div
          key={i}
          className="flex items-center gap-4 border-b border-hairline/70 px-6 py-3.5 last:border-b-0"
        >
          <Skeleton className="h-5 w-16" />
          <Skeleton className="ml-auto h-4 w-8" />
          <Skeleton className="h-4 w-12" />
          <div className="flex gap-1.5">
            <Skeleton className="h-5 w-12 rounded-md" />
            <Skeleton className="h-5 w-12 rounded-md" />
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
    <div className="space-y-8">
      {/* Header placeholder */}
      <div className="space-y-3">
        <Skeleton className="h-9 w-48" />
        <Skeleton className="h-5 w-80" />
      </div>

      {/* KPI strip — 4 tiles */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCardSkeleton showBar />
        <MetricCardSkeleton />
        <MetricCardSkeleton />
        <MetricCardSkeleton />
      </div>

      {/* Workbench row */}
      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <ChartSkeleton />
        <TableSkeleton />
      </div>
    </div>
  );
}
