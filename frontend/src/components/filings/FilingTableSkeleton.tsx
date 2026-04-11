/**
 * Filing table loading skeleton — mirrors `FilingTable` with its
 * checkbox column, 6 data columns, action column, and pagination footer.
 *
 * 5 placeholder rows (half a default page of 10) keeps the skeleton
 * shorter than the real content so the transition doesn't shrink
 * visibly when data arrives.
 */

import { Skeleton } from "@/components/ui";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ROW_COUNT = 5;
const HEADER_WIDTHS = ["w-12", "w-10", "w-28", "w-16", "w-14", "w-16"];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function FilingTableSkeleton() {
  return (
    <div className="space-y-3">
      {/* ---- Table container ---- */}
      <div className="overflow-x-auto rounded-lg border border-hairline bg-card">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-hairline bg-surface/60">
              <th className="w-10 px-4 py-2.5">
                <Skeleton className="h-3.5 w-3.5 rounded" />
              </th>
              {HEADER_WIDTHS.map((w, i) => (
                <th key={i} className="px-4 py-2.5">
                  <Skeleton className={`h-3 ${w}`} />
                </th>
              ))}
              <th className="w-14 px-4 py-2.5" />
            </tr>
          </thead>

          <tbody>
            {Array.from({ length: ROW_COUNT }, (_, i) => (
              <tr
                key={i}
                className="border-b border-hairline/70 last:border-b-0"
              >
                {/* Checkbox */}
                <td className="px-4 py-2.5">
                  <Skeleton className="h-3.5 w-3.5 rounded" />
                </td>
                {/* Ticker */}
                <td className="px-4 py-2.5">
                  <Skeleton className="h-4 w-12" />
                </td>
                {/* Form type */}
                <td className="px-4 py-2.5">
                  <Skeleton className="h-4 w-10 rounded" />
                </td>
                {/* Accession number */}
                <td className="px-4 py-2.5">
                  <Skeleton className="h-3 w-32" />
                </td>
                {/* Filing date */}
                <td className="px-4 py-2.5">
                  <Skeleton className="h-3 w-20" />
                </td>
                {/* Chunks */}
                <td className="px-4 py-2.5 text-right">
                  <Skeleton className="ml-auto h-3 w-10" />
                </td>
                {/* Ingested at */}
                <td className="px-4 py-2.5">
                  <Skeleton className="h-3 w-20" />
                </td>
                {/* Action button */}
                <td className="px-4 py-2.5">
                  <Skeleton className="h-6 w-6 rounded-md" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ---- Pagination footer ---- */}
      <div className="flex items-center justify-between gap-3 px-1">
        <Skeleton className="h-3 w-40" />
        <Skeleton className="h-3 w-20" />
        <div className="flex items-center gap-2">
          <Skeleton className="h-7 w-7 rounded-md" />
          <Skeleton className="h-3 w-10" />
          <Skeleton className="h-7 w-7 rounded-md" />
        </div>
      </div>
    </div>
  );
}
