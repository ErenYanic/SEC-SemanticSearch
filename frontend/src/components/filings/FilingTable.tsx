/**
 * FilingTable — sortable, paginated blotter-style table with row
 * selection and per-row delete.
 *
 * ## Sub-features
 *
 * **Sortable columns:** Each column header is a `<button>` for keyboard
 * access. Clicking the active column toggles asc/desc; clicking a new
 * column activates it with `desc` default. Sort params are sent to the
 * backend — the hook refetches on change.
 *
 * **Client-side pagination:** The backend returns all filings (max
 * ~100); the table slices locally. If a filter change or deletion
 * leaves the current page beyond the end, we fall back to page 0 via
 * a render-time clamp (no useEffect — React 19 lint rule).
 *
 * **Row selection:** Checkboxes in the first column; the header
 * checkbox applies to the current page only. Selection lives in the
 * page component (not here) because BulkActions also reads it.
 *
 * ## Visual language
 *
 * Terminal blotter: mono uppercase headers in subtle text, `font-mono
 * tabular-nums` on every numeric/identifier column so digits align
 * perfectly across rows. Hover uses the `surface` token so the row
 * "lights up" on pointer without introducing competing hues.
 */

"use client";

import { useCallback, useMemo, useState } from "react";
import {
  Check,
  ChevronLeft,
  ChevronRight,
  ChevronsUpDown,
  Copy,
  Trash2,
} from "lucide-react";
import type { Filing } from "@/lib/types";
import type { FilingListParams } from "@/lib/api";
import { Button, useToast } from "@/components/ui";

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

interface Column {
  label: string;
  sortKey: SortColumn | null;
  align?: "right";
}

const COLUMNS: Column[] = [
  { label: "Ticker", sortKey: "ticker" },
  { label: "Form", sortKey: "form_type" },
  { label: "Accession No.", sortKey: null },
  { label: "Filing Date", sortKey: "filing_date" },
  { label: "Chunks", sortKey: "chunk_count", align: "right" },
  { label: "Ingested", sortKey: "ingested_at" },
];

// ---------------------------------------------------------------------------
// Page size options
// ---------------------------------------------------------------------------

const PAGE_SIZES = [10, 25, 50] as const;

// ---------------------------------------------------------------------------
// Shared atoms
// ---------------------------------------------------------------------------

const HEADER_CELL =
  "px-5 py-3.5 text-xs font-semibold uppercase tracking-wider text-fg-subtle";

const BODY_CELL = "px-5 py-3.5 text-sm";

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
  // ---- Copy-to-clipboard state ----
  const { addToast } = useToast();
  const [copiedAccession, setCopiedAccession] = useState<string | null>(null);

  const handleCopyAccession = useCallback(
    async (accession: string) => {
      try {
        await navigator.clipboard.writeText(accession);
        setCopiedAccession(accession);
        addToast("success", "Copied to clipboard");
        setTimeout(() => setCopiedAccession(null), 2000);
      } catch {
        addToast("error", "Failed to copy — try selecting the text manually");
      }
    },
    [addToast],
  );

  // ---- Pagination state (local to the table) ----
  const [rawPage, setPage] = useState(0);
  const [pageSize, setPageSize] = useState<number>(10);

  // Render-time clamp — if filters/deletions shrink the list, fall back
  // to page 0 rather than resetting via useEffect.
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
      for (const acc of visibleAccessions) next.delete(acc);
    } else {
      for (const acc of visibleAccessions) next.add(acc);
    }
    onSelectionChange(next);
  }

  function toggleOne(accessionNumber: string) {
    const next = new Set(selected);
    if (next.has(accessionNumber)) next.delete(accessionNumber);
    else next.add(accessionNumber);
    onSelectionChange(next);
  }

  // ---- Sort handler ----
  function handleSort(column: SortColumn) {
    if (column === sortBy) {
      onSortChange(column, order === "asc" ? "desc" : "asc");
    } else {
      onSortChange(column, "desc");
    }
  }

  // ---- Sort indicator (upward / downward / neutral chevrons) ----
  function sortIndicator(column: SortColumn) {
    if (column === sortBy) {
      return (
        <span className="ml-1 text-accent" aria-hidden="true">
          {order === "asc" ? "\u25B2" : "\u25BC"}
        </span>
      );
    }
    return (
      <ChevronsUpDown
        className="ml-1 h-3 w-3 text-fg-subtle/50"
        aria-hidden="true"
      />
    );
  }

  // ---- Memoised date formatting for the visible page ----
  const formattedDates = useMemo(() => {
    const opts: Intl.DateTimeFormatOptions = {
      year: "numeric",
      month: "short",
      day: "numeric",
    };
    const map = new Map<string, string>();
    for (const f of visibleFilings) {
      map.set(
        f.accession_number,
        new Date(f.ingested_at).toLocaleDateString(undefined, opts),
      );
    }
    return map;
  }, [visibleFilings]);

  // ---- Empty state: filters active but no matches ----
  if (filings.length === 0) {
    return (
      <div className="rounded-2xl border border-hairline bg-card/70 p-12 text-center shadow-sm backdrop-blur-sm">
        <p className="text-base text-fg-muted">
          No filings match the current filters
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* ---- Table ---- */}
      <div className="overflow-x-auto rounded-2xl border border-hairline bg-card/80 shadow-sm backdrop-blur-sm">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-hairline bg-surface/40">
              {/* Checkbox column */}
              <th className="w-10 px-5 py-3.5">
                <input
                  type="checkbox"
                  checked={allVisibleSelected}
                  ref={(el) => {
                    if (el) el.indeterminate = someVisibleSelected;
                  }}
                  onChange={toggleAll}
                  aria-label="Select all filings on this page"
                  className="h-4 w-4 rounded border-hairline text-accent accent-[var(--accent)] focus-visible:ring-2 focus-visible:ring-accent/30"
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
                  className={`${HEADER_CELL} ${col.align === "right" ? "text-right" : ""}`}
                >
                  {col.sortKey ? (
                    <button
                      type="button"
                      onClick={() => handleSort(col.sortKey!)}
                      className={`inline-flex items-center rounded transition-colors hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
                        col.sortKey === sortBy ? "text-fg" : ""
                      }`}
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
              <th className="w-14 px-5 py-3.5">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>

          <tbody>
            {visibleFilings.map((filing) => {
              const isSelected = selected.has(filing.accession_number);
              return (
                <tr
                  key={filing.accession_number}
                  className={`border-b border-hairline/70 transition-colors last:border-b-0 ${
                    isSelected
                      ? "bg-accent/[0.08] hover:bg-accent/[0.12]"
                      : "hover:bg-surface/50"
                  }`}
                >
                  {/* Checkbox */}
                  <td className="px-5 py-3.5">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleOne(filing.accession_number)}
                      aria-label={`Select ${filing.ticker} ${filing.form_type}`}
                      className="h-4 w-4 rounded border-hairline accent-[var(--accent)] focus-visible:ring-2 focus-visible:ring-accent/30"
                    />
                  </td>

                  {/* Ticker */}
                  <td className={`${BODY_CELL} text-base font-semibold tabular-nums text-fg`}>
                    {filing.ticker}
                  </td>

                  {/* Form type */}
                  <td className={BODY_CELL}>
                    <span className="inline-flex items-center rounded-md border border-hairline bg-surface px-2 py-0.5 text-xs font-medium tabular-nums text-fg-muted">
                      {filing.form_type}
                    </span>
                  </td>

                  {/* Accession number */}
                  <td className={BODY_CELL}>
                    <span className="inline-flex items-center gap-2">
                      <span className="font-mono text-xs tabular-nums text-fg-muted">
                        {filing.accession_number}
                      </span>
                      <button
                        type="button"
                        onClick={() =>
                          handleCopyAccession(filing.accession_number)
                        }
                        className="rounded-md p-1 text-fg-subtle transition-colors hover:bg-surface hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                        title="Copy accession number to clipboard"
                        aria-label={`Copy accession number ${filing.accession_number}`}
                      >
                        {copiedAccession === filing.accession_number ? (
                          <Check className="h-3.5 w-3.5 text-pos" />
                        ) : (
                          <Copy className="h-3.5 w-3.5" />
                        )}
                      </button>
                    </span>
                  </td>

                  {/* Filing date */}
                  <td className={`${BODY_CELL} tabular-nums text-fg-muted`}>
                    {filing.filing_date}
                  </td>

                  {/* Chunk count */}
                  <td className={`${BODY_CELL} text-right tabular-nums text-fg-muted`}>
                    {filing.chunk_count.toLocaleString()}
                  </td>

                  {/* Ingested at */}
                  <td className={`${BODY_CELL} tabular-nums text-fg-muted`}>
                    {formattedDates.get(filing.accession_number)}
                  </td>

                  {/* Remove button */}
                  <td className="px-5 py-3.5">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onDeleteFiling(filing)}
                      disabled={isDeleting}
                      className="text-fg-subtle hover:bg-neg/10 hover:text-neg"
                      aria-label={`Delete ${filing.ticker} ${filing.form_type}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* ---- Pagination footer ---- */}
      <div className="flex flex-wrap items-center justify-between gap-4 px-2">
        <span className="text-sm tabular-nums text-fg-muted">
          <span className="font-semibold text-fg">{startIndex + 1}</span>
          <span className="text-fg-subtle">–</span>
          <span className="font-semibold text-fg">{endIndex}</span>
          <span className="text-fg-subtle"> of </span>
          <span className="font-semibold text-fg">
            {filings.length.toLocaleString()}
          </span>
          <span className="text-fg-subtle">
            {" "}filing{filings.length === 1 ? "" : "s"}
          </span>
        </span>

        {/* Centre: page size selector */}
        <div className="flex items-center gap-2.5">
          <label
            htmlFor="page-size"
            className="text-sm font-medium text-fg-muted"
          >
            Rows
          </label>
          <select
            id="page-size"
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setPage(0);
            }}
            className="rounded-lg border border-hairline bg-card px-3 py-1.5 text-sm tabular-nums text-fg outline-none transition-colors hover:border-accent/40 focus:border-accent focus:ring-2 focus:ring-accent/25"
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
            className="text-fg-muted hover:text-fg"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="px-3 text-sm tabular-nums text-fg-muted">
            <span className="font-semibold text-fg">{page + 1}</span>
            <span className="text-fg-subtle"> / </span>
            <span>{totalPages}</span>
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            aria-label="Next page"
            className="text-fg-muted hover:text-fg"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
