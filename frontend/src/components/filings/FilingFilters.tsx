/**
 * FilingFilters — inline ticker and form type selects for the Filings page.
 *
 * Unlike the Search page's chip-based filter rail (many filters, hidden by
 * default), the Filings page has only 2 filters and they are the primary
 * navigation tool, so they live inline in the toolbar row as compact
 * selects.
 *
 * Both dropdowns are controlled — the parent page owns the state and
 * passes values + change handlers as props, making the page the single
 * source of truth for filter values (also used for URL sync + selection
 * clearing).
 */

"use client";

import { Filter, X } from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface FilingFiltersProps {
  /** Current ticker filter value. Empty string means "all tickers". */
  ticker: string;
  /** Current form type filter value. Empty string means "all forms". */
  formType: string;
  /** Called when the user selects a different ticker. */
  onTickerChange: (ticker: string) => void;
  /** Called when the user selects a different form type. */
  onFormTypeChange: (formType: string) => void;
  /** Tickers available in the database (for dropdown options). */
  availableTickers: string[];
  /** Form types available in the database (for dropdown options). */
  availableFormTypes: string[];
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const SELECT_CLASSES =
  "rounded-lg border border-hairline bg-card px-3.5 py-2 text-sm font-medium tabular-nums " +
  "text-fg outline-none transition-colors hover:border-accent/40 " +
  "focus:border-accent focus:ring-2 focus:ring-accent/25";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function FilingFilters({
  ticker,
  formType,
  onTickerChange,
  onFormTypeChange,
  availableTickers,
  availableFormTypes,
}: FilingFiltersProps) {
  const hasActive = ticker !== "" || formType !== "";

  return (
    <div className="flex flex-wrap items-center gap-3">
      <Filter className="h-4 w-4 shrink-0 text-fg-subtle" aria-hidden="true" />

      {/* Ticker dropdown */}
      <select
        value={ticker}
        onChange={(e) => onTickerChange(e.target.value)}
        className={SELECT_CLASSES}
        aria-label="Filter by ticker"
      >
        <option value="">All tickers</option>
        {availableTickers.map((t) => (
          <option key={t} value={t}>
            {t}
          </option>
        ))}
      </select>

      {/* Form type dropdown */}
      <select
        value={formType}
        onChange={(e) => onFormTypeChange(e.target.value)}
        className={SELECT_CLASSES}
        aria-label="Filter by form type"
      >
        <option value="">All form types</option>
        {availableFormTypes.map((f) => (
          <option key={f} value={f}>
            {f}
          </option>
        ))}
      </select>

      {/* Clear filters — only shown when at least one filter is active */}
      {hasActive && (
        <button
          type="button"
          onClick={() => {
            onTickerChange("");
            onFormTypeChange("");
          }}
          className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium text-fg-muted transition-colors hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          aria-label="Clear all filters"
        >
          <X className="h-3.5 w-3.5" />
          Clear
        </button>
      )}
    </div>
  );
}
