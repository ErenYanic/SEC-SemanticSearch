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
 * ## Why a `Filters` object instead of individual props?
 *
 * With 5 filter fields, passing 5 value props + 5 onChange callbacks
 * would be noisy. A single `filters` object + single `onFiltersChange`
 * keeps the interface clean. The trade-off is a shallow object spread
 * on every change, but that's negligible.
 */

"use client";

import { useId, useState } from "react";
import { SlidersHorizontal, X } from "lucide-react";
import { Button, Badge } from "@/components/ui";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SearchFilterValues {
  ticker: string;
  formType: string;
  topK: number;
  minSimilarity: number;
  accessionNumber: string;
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
  ticker: "",
  formType: "",
  topK: 5,
  minSimilarity: 0,
  accessionNumber: "",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Count how many filters differ from their defaults. */
export function countActiveFilters(filters: SearchFilterValues): number {
  let count = 0;
  if (filters.ticker) count++;
  if (filters.formType) count++;
  if (filters.topK !== DEFAULT_FILTERS.topK) count++;
  if (filters.minSimilarity !== DEFAULT_FILTERS.minSimilarity) count++;
  if (filters.accessionNumber) count++;
  return count;
}

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
          className="mt-3 grid gap-4 rounded-lg border border-gray-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-3 dark:border-gray-800 dark:bg-gray-950"
        >
          {/* Ticker */}
          <label className="space-y-1">
            <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
              Ticker
            </span>
            <select
              value={filters.ticker}
              onChange={(e) => update({ ticker: e.target.value })}
              className="w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
            >
              <option value="">All tickers</option>
              {availableTickers.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>

          {/* Form type */}
          <label className="space-y-1">
            <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
              Form type
            </span>
            <select
              value={filters.formType}
              onChange={(e) => update({ formType: e.target.value })}
              className="w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
            >
              <option value="">All forms</option>
              <option value="10-K">10-K</option>
              <option value="10-Q">10-Q</option>
            </select>
          </label>

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

          {/* Accession number */}
          <label className="space-y-1 sm:col-span-2 lg:col-span-2">
            <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
              Accession number
            </span>
            <input
              type="text"
              value={filters.accessionNumber}
              onChange={(e) => update({ accessionNumber: e.target.value })}
              placeholder="e.g. 0000320193-24-000123"
              className="w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 placeholder:text-gray-400 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100 dark:placeholder:text-gray-500"
            />
          </label>
        </div>
      )}
    </div>
  );
}