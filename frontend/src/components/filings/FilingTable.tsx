/**
 * FilingTable — sortable, paginated table with row selection and per-row
 * delete buttons.
 *
 * ## Three sub-features
 *
 * **Sortable columns:** Each column header is a `<button>` for keyboard
 * accessibility. Clicking the active column toggles asc/desc; clicking a
 * different column activates it with `desc` default. Sort parameters are
 * sent to the backend — the hook refetches when they change.
 *
 * **Client-side pagination:** The backend returns all filings (max ~100).
 * The table slices the array into pages locally. Page resets to 0 when
 * `filings.length` changes (filter change or deletion).
 *
 * **Row selection:** Checkboxes in the first column, "Select All" header
 * checkbox applies to the current page only. Selection state lives in the
 * page component (not here) because BulkActions also reads it.
 */

"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight, Trash2 } from "lucide-react";
import type { Filing } from "@/lib/types";
import type { FilingListParams } from "@/lib/api";
import { Badge, Button } from "@/components/ui";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type SortColumn = NonNullable<FilingListParams["sort_by"]>;

interface FilingTableProps {
  /** Filings to display (already server-sorted). */
  filings: Filing[];
  /** Current sort column. */
  sortBy: SortColumn;
  /** Current sort direction. */
  order: "asc" | "desc";
  /** Called when the user clicks a column header. */
  onSortChange: (sortBy: SortColumn, order: "asc" | "desc") => void;
  /** Currently selected accession numbers. */
  selected: Set<string>;
  /** Called when the selection changes. */
  onSelectionChange: (selected: Set<string>) => void;
  /** Called when the user clicks a per-row Remove button. */
  onDeleteFiling: (filing: Filing) => void;
  /** Disable Remove buttons while a deletion is in progress. */
  isDeleting: boolean;
}

// ---------------------------------------------------------------------------
// Column definitions
// ---------------------------------------------------------------------------

/**
 * Column metadata. `key` maps to a `Filing` field or a backend sort column.
 * `sortKey` is sent to the backend; `null` means the column is not sortable.
 */
interface Column {
  label: string;
  sortKey: SortColumn | null;
  align?: "right";
}

const COLUMNS: Column[] = [
  { label: "Ticker", sortKey: "ticker" },
  { label: "Form", sortKey: "form_type" },
  { label: "Filing Date", sortKey: "filing_date" },
  { label: "Chunks", sortKey: "chunk_count", align: "right" },
  { label: "Ingested", sortKey: "ingested_at" },
];

// ---------------------------------------------------------------------------
// Page size options
// ---------------------------------------------------------------------------

const PAGE_SIZES = [10, 25, 50] as const;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function FilingTable({
  filings,
  sortBy,
  order,
  onSortChange,
  selected,
  onSelectionChange,
  onDeleteFiling,
  isDeleting,
}: FilingTableProps) {
  // ---- Pagination state (local to the table) ----
  const [rawPage, setPage] = useState(0);
  const [pageSize, setPageSize] = useState<number>(10);

  // ---- Derived pagination values ----
  // Clamp the page during render instead of resetting via useEffect.
  // If a filter change or deletion reduces the data so the current page
  // is beyond the end, we fall back to page 0. This avoids the React 19
  // lint rule "no setState in effects" and eliminates the cascading
  // render that an effect-based reset would cause.
  const totalPages = Math.max(1, Math.ceil(filings.length / pageSize));
  const page = rawPage >= totalPages ? 0 : rawPage;
  const startIndex = page * pageSize;
  const endIndex = Math.min(startIndex + pageSize, filings.length);
  const visibleFilings = filings.slice(startIndex, endIndex);

  // ---- Selection helpers ----
  const visibleAccessions = visibleFilings.map((f) => f.accession_number);
  const allVisibleSelected =
    visibleFilings.length > 0 &&
    visibleFilings.every((f) => selected.has(f.accession_number));
  const someVisibleSelected =
    !allVisibleSelected &&
    visibleFilings.some((f) => selected.has(f.accession_number));

  function toggleAll() {
    const next = new Set(selected);
    if (allVisibleSelected) {
      // Deselect all visible
      for (const acc of visibleAccessions) {
        next.delete(acc);
      }
    } else {
      // Select all visible
      for (const acc of visibleAccessions) {
        next.add(acc);
      }
    }
    onSelectionChange(next);
  }

  function toggleOne(accessionNumber: string) {
    const next = new Set(selected);
    if (next.has(accessionNumber)) {
      next.delete(accessionNumber);
    } else {
      next.add(accessionNumber);
    }
    onSelectionChange(next);
  }

  // ---- Sort handler ----
  function handleSort(column: SortColumn) {
    if (column === sortBy) {
      // Same column: toggle direction
      onSortChange(column, order === "asc" ? "desc" : "asc");
    } else {
      // Different column: activate with desc default
      onSortChange(column, "desc");
    }
  }

  // ---- Render sort indicator ----
  function sortIndicator(column: SortColumn) {
    if (column === sortBy) {
      return (
        <span className="ml-1 text-blue-600 dark:text-blue-400">
          {order === "asc" ? "\u25B2" : "\u25BC"}
        </span>
      );
    }
    return (
      <span className="ml-1 text-gray-300 dark:text-gray-600">
        {"\u25B4\u25BE"}
      </span>
    );
  }

  // ---- Format ingested_at for display ----
  function formatIngestedAt(iso: string): string {
    const date = new Date(iso);
    return date.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  }

  // ---- Empty state (filters active but no matches) ----
  if (filings.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-8 text-center dark:border-gray-800 dark:bg-gray-950">
        <p className="text-sm text-gray-500 dark:text-gray-400">
          No filings match the current filters.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-950">
        <table className="w-full text-left text-sm">
          {/* ---- Header ---- */}
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-900">
              {/* Checkbox column */}
              <th className="w-10 px-4 py-3">
                <input
                  type="checkbox"
                  checked={allVisibleSelected}
                  ref={(el) => {
                    if (el) el.indeterminate = someVisibleSelected;
                  }}
                  onChange={toggleAll}
                  aria-label="Select all filings on this page"
                  className="h-4 w-4 rounded border-gray-300 text-blue-600 focus-visible:ring-blue-500 dark:border-gray-600"
                />
              </th>

              {/* Data columns */}
              {COLUMNS.map((col) => (
                <th
                  key={col.label}
                  aria-sort={
                    col.sortKey === sortBy
                      ? order === "asc"
                        ? "ascending"
                        : "descending"
                      : col.sortKey
                        ? "none"
                        : undefined
                  }
                  className={`px-4 py-3 font-medium text-gray-500 dark:text-gray-400 ${
                    col.align === "right" ? "text-right" : ""
                  }`}
                >
                  {col.sortKey ? (
                    <button
                      type="button"
                      onClick={() => handleSort(col.sortKey!)}
                      className="inline-flex items-center rounded hover:text-gray-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500 dark:hover:text-gray-100"
                    >
                      {col.label}
                      {sortIndicator(col.sortKey)}
                    </button>
                  ) : (
                    col.label
                  )}
                </th>
              ))}

              {/* Actions column */}
              <th className="w-16 px-4 py-3">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>

          {/* ---- Body ---- */}
          <tbody>
            {visibleFilings.map((filing) => (
              <tr
                key={filing.accession_number}
                className="border-t border-gray-100 hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-gray-900"
              >
                {/* Checkbox */}
                <td className="px-4 py-3">
                  <input
                    type="checkbox"
                    checked={selected.has(filing.accession_number)}
                    onChange={() => toggleOne(filing.accession_number)}
                    aria-label={`Select ${filing.ticker} ${filing.form_type}`}
                    className="h-4 w-4 rounded border-gray-300 text-blue-600 focus-visible:ring-blue-500 dark:border-gray-600"
                  />
                </td>

                {/* Ticker */}
                <td className="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">
                  {filing.ticker}
                </td>

                {/* Form type */}
                <td className="px-4 py-3">
                  <Badge variant="blue">{filing.form_type}</Badge>
                </td>

                {/* Filing date */}
                <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                  {filing.filing_date}
                </td>

                {/* Chunk count */}
                <td className="px-4 py-3 text-right tabular-nums text-gray-600 dark:text-gray-400">
                  {filing.chunk_count.toLocaleString()}
                </td>

                {/* Ingested at */}
                <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                  {formatIngestedAt(filing.ingested_at)}
                </td>

                {/* Remove button */}
                <td className="px-4 py-3">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onDeleteFiling(filing)}
                    disabled={isDeleting}
                    className="text-red-500 hover:bg-red-50 hover:text-red-700 dark:text-red-400 dark:hover:bg-red-950 dark:hover:text-red-300"
                    aria-label={`Delete ${filing.ticker} ${filing.form_type}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ---- Pagination footer ---- */}
      <div className="flex items-center justify-between text-sm text-gray-600 dark:text-gray-400">
        {/* Left: showing range */}
        <span>
          Showing {startIndex + 1}–{endIndex} of{" "}
          {filings.length.toLocaleString()} filing
          {filings.length === 1 ? "" : "s"}
        </span>

        {/* Centre: page size selector */}
        <div className="flex items-center gap-2">
          <label htmlFor="page-size" className="text-xs">
            Rows:
          </label>
          <select
            id="page-size"
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setPage(0);
            }}
            className="rounded border border-gray-300 bg-white px-2 py-1 text-xs dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
          >
            {PAGE_SIZES.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </div>

        {/* Right: previous/next buttons */}
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            aria-label="Previous page"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="px-2 text-xs">
            {page + 1} / {totalPages}
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            aria-label="Next page"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}