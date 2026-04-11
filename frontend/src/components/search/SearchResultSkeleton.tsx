/**
 * Loading skeleton shown while the Search page's initial status
 * (ticker list, filing inventory) is fetching.
 *
 * Mirrors the two-column terminal layout of the redesigned Search
 * page: left rail (filters) and main column with search bar + result
 * rows. The `shimmer` animation keyframe lives in globals.css; the
 * `Skeleton` component below applies it via a background gradient.
 *
 * A minimum of one skeleton element uses the `shimmer` class so that
 * tests scanning HTML for "shimmer" can detect the loading state.
 */

import { Skeleton } from "@/components/ui";

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Mirrors the new row-style ResultCard: left gutter + main column. */
function ResultRowSkeleton() {
  return (
    <div className="grid grid-cols-[56px_1fr_auto] gap-4 border-b border-hairline px-4 py-3.5">
      {/* Left gutter: rank + sim + bar */}
      <div className="flex flex-col items-start gap-1.5">
        <Skeleton className="h-3 w-6" />
        <Skeleton className="h-4 w-10" />
        <Skeleton className="h-1 w-full rounded-full" />
      </div>

      {/* Main column: metadata + path + snippet */}
      <div className="min-w-0 space-y-2">
        <div className="flex gap-2">
          <Skeleton className="h-3 w-12" />
          <Skeleton className="h-3 w-10" />
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-3 w-32" />
        </div>
        <Skeleton className="h-3 w-2/3" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-[92%]" />
      </div>

      {/* Right gutter: action slot */}
      <div>
        <Skeleton className="h-7 w-7 rounded-md" />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

const ROW_COUNT = 4;

export function SearchResultSkeleton() {
  return (
    <div className="space-y-4">
      {/* Page title placeholder */}
      <div className="flex items-center gap-3">
        <Skeleton className="h-7 w-24" />
      </div>

      {/* Search bar placeholder */}
      <Skeleton className="h-14 w-full rounded-lg" />

      {/* Two-column layout: rail + main */}
      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        {/* Rail placeholder */}
        <div className="space-y-3 rounded-lg border border-hairline bg-surface p-5">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-5/6" />
          <div className="pt-2">
            <Skeleton className="h-4 w-20" />
          </div>
          <Skeleton className="h-8 w-full rounded-md" />
        </div>

        {/* Results column placeholder */}
        <div className="rounded-lg border border-hairline bg-surface">
          {/* Meta header */}
          <div className="flex items-center justify-between border-b border-hairline px-4 py-2.5">
            <Skeleton className="h-3 w-48" />
            <Skeleton className="h-3 w-32" />
          </div>
          {Array.from({ length: ROW_COUNT }, (_, i) => (
            <ResultRowSkeleton key={i} />
          ))}
        </div>
      </div>
    </div>
  );
}
