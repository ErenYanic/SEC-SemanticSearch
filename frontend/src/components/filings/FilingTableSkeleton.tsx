/**
 * Filing table loading skeleton — mirrors `FilingTable` with its
 * checkbox column, 5 data columns, action column, and pagination footer.
 *
 * The skeleton renders 5 placeholder rows (half a default page of 10).
 * Using fewer rows than the real page prevents the skeleton from being
 * taller than the real content, which would cause a noticeable layout
 * shrink on load.
 */

import { Skeleton } from "@/components/ui";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Number of placeholder rows to show. */
const ROW_COUNT = 5;

/** Column header labels — matches `FilingTable.COLUMNS` ordering. */
const HEADER_WIDTHS = ["w-14", "w-12", "w-20", "w-14", "w-16"];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function FilingTableSkeleton() {
  return (
    <div className="space-y-3">
      {/* Table container */}
      <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-950">
        <table className="w-full text-left text-sm">
          {/* ---- Header ---- */}
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-900">
              {/* Checkbox column */}
              <th className="w-10 px-4 py-3">
                <Skeleton className="h-4 w-4 rounded" />
              </th>
              {/* Data columns */}
              {HEADER_WIDTHS.map((w, i) => (
                <th key={i} className="px-4 py-3">
                  <Skeleton className={`h-4 ${w}`} />
                </th>
              ))}
              {/* Actions column */}
              <th className="w-16 px-4 py-3" />
            </tr>
          </thead>

          {/* ---- Body rows ---- */}
          <tbody>
            {Array.from({ length: ROW_COUNT }, (_, i) => (
              <tr
                key={i}
                className="border-t border-gray-100 dark:border-gray-800"
              >
                {/* Checkbox */}
                <td className="px-4 py-3">
                  <Skeleton className="h-4 w-4 rounded" />
                </td>
                {/* Ticker */}
                <td className="px-4 py-3">
                  <Skeleton className="h-4 w-12" />
                </td>
                {/* Form type badge */}
                <td className="px-4 py-3">
                  <Skeleton className="h-5 w-12 rounded-full" />
                </td>
                {/* Filing date */}
                <td className="px-4 py-3">
                  <Skeleton className="h-4 w-24" />
                </td>
                {/* Chunk count */}
                <td className="px-4 py-3 text-right">
                  <Skeleton className="ml-auto h-4 w-10" />
                </td>
                {/* Ingested at */}
                <td className="px-4 py-3">
                  <Skeleton className="h-4 w-20" />
                </td>
                {/* Action button */}
                <td className="px-4 py-3">
                  <Skeleton className="h-7 w-7 rounded-md" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ---- Pagination footer ---- */}
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-4 w-20" />
        <div className="flex items-center gap-2">
          <Skeleton className="h-7 w-7 rounded-md" />
          <Skeleton className="h-4 w-12" />
          <Skeleton className="h-7 w-7 rounded-md" />
        </div>
      </div>
    </div>
  );
}