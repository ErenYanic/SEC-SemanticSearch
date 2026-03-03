/**
 * FilingFilters — inline ticker and form type dropdowns for the Filings page.
 *
 * Unlike the Search page's collapsible filter panel (5 filters, hidden by
 * default), the Filings page has only 2 filters and they are the primary
 * navigation tool, so they are always visible in a horizontal row.
 *
 * Both dropdowns are **controlled components**: the page owns the state
 * and passes values + change handlers as props. This makes the page the
 * single source of truth for filter values, which it also uses for:
 *   - the `useFilings` hook (API call parameters)
 *   - URL query parameter synchronisation
 *   - clearing the selection set on filter change
 *
 * Available options come from `useStatus()` data (passed down by the page),
 * so the dropdowns only show tickers/forms that actually exist in the
 * database — no hardcoded lists.
 */

"use client";

import { Filter } from "lucide-react";

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
// Shared class string — matches the <select> styling in SearchFilters.tsx
// ---------------------------------------------------------------------------

const SELECT_CLASSES =
  "w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100";

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
  return (
    <div className="flex items-center gap-3">
      <Filter className="h-4 w-4 shrink-0 text-gray-400 dark:text-gray-500" />

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
    </div>
  );
}