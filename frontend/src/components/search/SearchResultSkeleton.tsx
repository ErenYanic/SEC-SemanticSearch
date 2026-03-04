/**
 * Search page loading skeleton — shows a search bar placeholder and
 * 3 result card placeholders.
 *
 * Used when the search page is loading its initial status data
 * (ticker list for filters, filing inventory).  Once status loads,
 * the real SearchBar and FilingInventory replace this skeleton.
 *
 * The result card shape mirrors `ResultCard`: rank circle on the left,
 * badge placeholders, metadata row with icons, and text lines.
 */

import { Skeleton } from "@/components/ui";

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Mirrors `ResultCard` layout: rank + badges + metadata + content. */
function ResultCardSkeleton() {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-950">
      <div className="flex gap-4">
        {/* Rank circle */}
        <Skeleton className="h-8 w-8 flex-shrink-0 rounded-full" />

        <div className="min-w-0 flex-1 space-y-3">
          {/* Badges row (similarity + form type) */}
          <div className="flex gap-2">
            <Skeleton className="h-5 w-16 rounded-full" />
            <Skeleton className="h-5 w-12 rounded-full" />
          </div>

          {/* Metadata row (ticker, date, accession) */}
          <div className="flex gap-4">
            <Skeleton className="h-4 w-12" />
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-4 w-36" />
          </div>

          {/* Section path */}
          <Skeleton className="h-4 w-2/3" />

          {/* Content preview (3 lines) */}
          <div className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-[90%]" />
            <Skeleton className="h-4 w-3/5" />
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

/** Number of placeholder result cards. */
const CARD_COUNT = 3;

export function SearchResultSkeleton() {
  return (
    <div className="space-y-4">
      {/* Page header */}
      <div className="flex items-center gap-3">
        <Skeleton className="h-8 w-8 rounded-md" />
        <Skeleton className="h-7 w-24" />
      </div>

      {/* Search bar placeholder */}
      <Skeleton className="h-11 w-full rounded-lg" />

      {/* Filter toggle placeholder */}
      <Skeleton className="h-9 w-36 rounded-md" />

      {/* Result cards */}
      <div className="space-y-3">
        {Array.from({ length: CARD_COUNT }, (_, i) => (
          <ResultCardSkeleton key={i} />
        ))}
      </div>
    </div>
  );
}