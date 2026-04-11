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
    <div className="space-y-8">
      {/* ---- Page header placeholder ---- */}
      <div className="space-y-3">
        <Skeleton className="h-9 w-32" />
        <Skeleton className="h-5 w-72" />
      </div>

      {/* ---- Toolbar placeholder ---- */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Skeleton className="h-10 w-40 rounded-lg" />
          <Skeleton className="h-10 w-44 rounded-lg" />
        </div>
        <Skeleton className="h-10 w-48 rounded-lg" />
      </div>

      {/* ---- Table container ---- */}
      <div className="overflow-x-auto rounded-2xl border border-hairline bg-card/80 shadow-sm backdrop-blur-sm">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-hairline bg-surface/40">
              <th className="w-10 px-5 py-3.5">
                <Skeleton className="h-4 w-4 rounded" />
              </th>
              {HEADER_WIDTHS.map((w, i) => (
                <th key={i} className="px-5 py-3.5">
                  <Skeleton className={`h-3.5 ${w}`} />
                </th>
              ))}
              <th className="w-14 px-5 py-3.5" />
            </tr>
          </thead>

          <tbody>
            {Array.from({ length: ROW_COUNT }, (_, i) => (
              <tr
                key={i}
                className="border-b border-hairline/70 last:border-b-0"
              >
                {/* Checkbox */}
                <td className="px-5 py-3.5">
                  <Skeleton className="h-4 w-4 rounded" />
                </td>
                {/* Ticker */}
                <td className="px-5 py-3.5">
                  <Skeleton className="h-5 w-14" />
                </td>
                {/* Form type */}
                <td className="px-5 py-3.5">
                  <Skeleton className="h-5 w-12 rounded-md" />
                </td>
                {/* Accession number */}
                <td className="px-5 py-3.5">
                  <Skeleton className="h-4 w-36" />
                </td>
                {/* Filing date */}
                <td className="px-5 py-3.5">
                  <Skeleton className="h-4 w-24" />
                </td>
                {/* Chunks */}
                <td className="px-5 py-3.5 text-right">
                  <Skeleton className="ml-auto h-4 w-12" />
                </td>
                {/* Ingested at */}
                <td className="px-5 py-3.5">
                  <Skeleton className="h-4 w-24" />
                </td>
                {/* Action button */}
                <td className="px-5 py-3.5">
                  <Skeleton className="h-8 w-8 rounded-lg" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ---- Pagination footer ---- */}
      <div className="flex items-center justify-between gap-4 px-2">
        <Skeleton className="h-4 w-44" />
        <Skeleton className="h-4 w-24" />
        <div className="flex items-center gap-2">
          <Skeleton className="h-8 w-8 rounded-lg" />
          <Skeleton className="h-4 w-12" />
          <Skeleton className="h-8 w-8 rounded-lg" />
        </div>
      </div>
    </div>
  );
}
