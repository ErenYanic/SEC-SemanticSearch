/**
 * Collapsible filter panel for search refinement.
 *
 * ## Why collapsible?
 *
 * Most searches work fine without filters. Showing 5 filter inputs
 * all the time overwhelms the interface and pushes results below
 * the fold. The "Filters" button with an active-count badge gives
 * power users quick access without penalising casual users.
 *
 * ## State ownership
 *
 * The **parent page** owns all filter values. This component is
 * presentational — it renders inputs and calls `onFiltersChange`
 * when any value changes. This makes the parent the single source
 * of truth for the search request, which simplifies debugging.
 *
 * ## Multi-select filters
 *
 * Ticker and form type use chip-based multi-select (consistent with
 * the IngestForm ticker input style). Accession numbers are entered
 * as comma-separated text. All three filter fields map to arrays
 * in the API request.
 */

"use client";

import { useId, useState } from "react";
import { SlidersHorizontal, X } from "lucide-react";
import { Button, Badge } from "@/components/ui";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SearchFilterValues {
  tickers: string[];
  formTypes: string[];
  topK: number;
  minSimilarity: number;
  accessionNumbers: string[];
  startDate: string;
  endDate: string;
}

interface SearchFiltersProps {
  filters: SearchFilterValues;
  onFiltersChange: (filters: SearchFilterValues) => void;
  /** Available tickers for the dropdown (from status endpoint). */
  availableTickers: string[];
}

// ---------------------------------------------------------------------------
// Defaults
// ---------------------------------------------------------------------------

export const DEFAULT_FILTERS: SearchFilterValues = {
  tickers: [],
  formTypes: [],
  topK: 5,
  minSimilarity: 0,
  accessionNumbers: [],
  startDate: "",
  endDate: "",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Count how many filters differ from their defaults. */
export function countActiveFilters(filters: SearchFilterValues): number {
  let count = 0;
  if (filters.tickers.length > 0) count++;
  if (filters.formTypes.length > 0) count++;
  if (filters.topK !== DEFAULT_FILTERS.topK) count++;
  if (filters.minSimilarity !== DEFAULT_FILTERS.minSimilarity) count++;
  if (filters.accessionNumbers.length > 0) count++;
  if (filters.startDate) count++;
  if (filters.endDate) count++;
  return count;
}

// ---------------------------------------------------------------------------
// Chip styles (static Tailwind class maps — decision #30)
// ---------------------------------------------------------------------------

const CHIP_BASE =
  "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors cursor-pointer select-none";

const CHIP_ACTIVE =
  "border-blue-300 bg-blue-50 text-blue-700 hover:bg-blue-100 dark:border-blue-700 dark:bg-blue-950 dark:text-blue-300 dark:hover:bg-blue-900";

const CHIP_INACTIVE =
  "border-gray-300 bg-white text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-400 dark:hover:bg-gray-800";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SearchFilters({
  filters,
  onFiltersChange,
  availableTickers,
}: SearchFiltersProps) {
  const [isOpen, setIsOpen] = useState(false);
  const panelId = useId();
  const activeCount = countActiveFilters(filters);

  /** Update a single field, preserving the rest via object spread. */
  function update(patch: Partial<SearchFilterValues>) {
    onFiltersChange({ ...filters, ...patch });
  }

  /** Toggle a ticker in the selected list. */
  function toggleTicker(ticker: string) {
    const next = filters.tickers.includes(ticker)
      ? filters.tickers.filter((t) => t !== ticker)
      : [...filters.tickers, ticker];
    update({ tickers: next });
  }

  /** Toggle a form type in the selected list. */
  function toggleFormType(formType: string) {
    const next = filters.formTypes.includes(formType)
      ? filters.formTypes.filter((f) => f !== formType)
      : [...filters.formTypes, formType];
    update({ formTypes: next });
  }

  /** Parse comma-separated accession numbers from text input. */
  function handleAccessionChange(value: string) {
    if (!value.trim()) {
      update({ accessionNumbers: [] });
      return;
    }
    const parsed = value
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    update({ accessionNumbers: parsed });
  }

  return (
    <div>
      {/* ---- Toggle button ---- */}
      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setIsOpen(!isOpen)}
          aria-expanded={isOpen}
          aria-controls={panelId}
        >
          <SlidersHorizontal className="mr-1.5 h-4 w-4" />
          Filters
          {activeCount > 0 && (
            <Badge variant="blue" className="ml-1.5">
              {activeCount}
            </Badge>
          )}
        </Button>
        {activeCount > 0 && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onFiltersChange(DEFAULT_FILTERS)}
          >
            <X className="mr-1 h-3.5 w-3.5" />
            Clear
          </Button>
        )}
      </div>

      {/* ---- Collapsible filter panel ---- */}
      {isOpen && (
        <div
          id={panelId}
          role="region"
          aria-label="Search filters"
          className="mt-3 space-y-4 rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-950"
        >
          {/* Ticker multi-select chips */}
          {availableTickers.length > 0 && (
            <div className="space-y-1.5">
              <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
                Tickers
              </span>
              <div className="flex flex-wrap gap-1.5" role="group" aria-label="Ticker filters">
                {availableTickers.map((t) => {
                  const isActive = filters.tickers.includes(t);
                  return (
                    <button
                      key={t}
                      type="button"
                      onClick={() => toggleTicker(t)}
                      className={`${CHIP_BASE} ${isActive ? CHIP_ACTIVE : CHIP_INACTIVE}`}
                      aria-pressed={isActive}
                    >
                      {t}
                      {isActive && <X className="h-3 w-3" />}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Form type multi-select chips */}
          <div className="space-y-1.5">
            <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
              Form type
            </span>
            <div className="flex flex-wrap gap-1.5" role="group" aria-label="Form type filters">
              {["8-K", "10-K", "10-Q"].map((f) => {
                const isActive = filters.formTypes.includes(f);
                return (
                  <button
                    key={f}
                    type="button"
                    onClick={() => toggleFormType(f)}
                    className={`${CHIP_BASE} ${isActive ? CHIP_ACTIVE : CHIP_INACTIVE}`}
                    aria-pressed={isActive}
                  >
                    {f}
                    {isActive && <X className="h-3 w-3" />}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {/* Top K */}
            <label className="space-y-1">
              <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
                Results (top K)
              </span>
              <input
                type="number"
                min={1}
                max={100}
                value={filters.topK}
                onChange={(e) =>
                  update({ topK: Math.max(1, Math.min(100, Number(e.target.value) || 1)) })
                }
                className="w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
              />
            </label>

            {/* Min similarity */}
            <label className="space-y-1">
              <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
                Min similarity: {Math.round(filters.minSimilarity * 100)}%
              </span>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={filters.minSimilarity}
                onChange={(e) => update({ minSimilarity: Number(e.target.value) })}
                className="w-full accent-blue-600"
              />
            </label>

            {/* Accession numbers (comma-separated) */}
            <label className="space-y-1 sm:col-span-2 lg:col-span-1">
              <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
                Accession number(s)
              </span>
              <input
                type="text"
                value={filters.accessionNumbers.join(", ")}
                onChange={(e) => handleAccessionChange(e.target.value)}
                placeholder="e.g. 0000320193-24-000123, 0000320193-24-000456"
                className="w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 placeholder:text-gray-400 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100 dark:placeholder:text-gray-500"
              />
            </label>

            {/* Date range — From */}
            <label className="space-y-1">
              <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
                From date
              </span>
              <input
                type="date"
                value={filters.startDate}
                onChange={(e) => update({ startDate: e.target.value })}
                className="w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
              />
            </label>

            {/* Date range — To */}
            <label className="space-y-1">
              <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
                To date
              </span>
              <input
                type="date"
                value={filters.endDate}
                onChange={(e) => update({ endDate: e.target.value })}
                className="w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
              />
            </label>
          </div>
        </div>
      )}
    </div>
  );
}
