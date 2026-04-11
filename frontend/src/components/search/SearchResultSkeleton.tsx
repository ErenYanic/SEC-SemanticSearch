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

function ResultRowSkeleton() {
  return (
    <div className="grid grid-cols-[64px_1fr_auto] gap-5 border-b border-hairline px-6 py-5">
      <div className="flex flex-col items-start gap-2">
        <Skeleton className="h-4 w-8" />
        <Skeleton className="h-5 w-12" />
        <Skeleton className="h-1 w-full rounded-full" />
      </div>

      <div className="min-w-0 space-y-2.5">
        <div className="flex gap-2">
          <Skeleton className="h-4 w-14" />
          <Skeleton className="h-4 w-12" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-40" />
        </div>
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-5 w-full" />
        <Skeleton className="h-5 w-[92%]" />
      </div>

      <div>
        <Skeleton className="h-9 w-9 rounded-lg" />
      </div>
    </div>
  );
}

const ROW_COUNT = 4;

export function SearchResultSkeleton() {
  return (
    <div className="space-y-8">
      {/* Page header placeholder */}
      <div className="space-y-3">
        <Skeleton className="h-9 w-32" />
        <Skeleton className="h-5 w-80" />
      </div>

      {/* Search bar placeholder */}
      <Skeleton className="h-16 w-full rounded-2xl" />

      {/* Two-column layout */}
      <div className="grid gap-6 lg:grid-cols-[300px_1fr]">
        {/* Rail placeholder */}
        <div className="space-y-4 rounded-2xl border border-hairline bg-card/70 p-6">
          <Skeleton className="h-5 w-24" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
          <div className="pt-2">
            <Skeleton className="h-5 w-24" />
          </div>
          <Skeleton className="h-10 w-full rounded-lg" />
        </div>

        {/* Results column placeholder */}
        <div className="rounded-2xl border border-hairline bg-card/70">
          <div className="flex items-center justify-between border-b border-hairline px-6 py-4">
            <Skeleton className="h-5 w-52" />
            <Skeleton className="h-5 w-36" />
          </div>
          {Array.from({ length: ROW_COUNT }, (_, i) => (
            <ResultRowSkeleton key={i} />
          ))}
        </div>
      </div>
    </div>
  );
}
