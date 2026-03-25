/**
 * Form for configuring and starting an ingestion task.
 *
 * ## State ownership
 *
 * Unlike the Search page (where query + filters are lifted to the page
 * for persistence across searches), the ingest form manages its own
 * local state.  The values are one-shot — submit builds an
 * `IngestRequest` and the form disappears, replaced by the progress
 * tracker.  No reason to burden the page with ephemeral form state.
 *
 * ## Sub-sections
 *
 *   1. Ticker tag input  — Enter/comma adds, X removes
 *   2. Form type chips   — toggleable 10-K / 10-Q
 *   3. Count mode radio  — latest / total / per_form
 *   4. Date filters      — collapsible year, start_date, end_date
 *   5. Submit button     — disabled until valid
 */

"use client";

import { type FormEvent, type KeyboardEvent, useId, useState } from "react";
import { Upload, X, ChevronDown, ChevronUp, Calendar } from "lucide-react";
import { Button, useToast } from "@/components/ui";
import type { IngestRequest } from "@/lib/types";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface IngestFormProps {
  /** Called when the user submits the form with a valid request. */
  onSubmit: (request: IngestRequest) => void;
  /** True while the API call is in-flight (disables the submit button). */
  isSubmitting: boolean;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const FORM_TYPES = ["10-K", "10-Q"] as const;

/** Descriptions shown beneath each count mode radio option. */
const COUNT_MODE_INFO: Record<string, { label: string; description: string }> = {
  latest: {
    label: "Latest",
    description: "1 filing per form type per ticker",
  },
  total: {
    label: "Total",
    description: "N filings shared across all form types",
  },
  per_form: {
    label: "Per form",
    description: "N filings per form type",
  },
};

// Static Tailwind class maps — never interpolated.
const CHIP_CLASSES: Record<"active" | "inactive", string> = {
  active:
    "border-blue-300 bg-blue-100 text-blue-800 dark:border-blue-700 dark:bg-blue-900 dark:text-blue-200",
  inactive:
    "border-gray-300 bg-gray-100 text-gray-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-500",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function IngestForm({ onSubmit, isSubmitting }: IngestFormProps) {
  const { addToast } = useToast();

  // ---- Ticker tag state ----
  const [tickers, setTickers] = useState<string[]>([]);
  const [tickerInput, setTickerInput] = useState("");

  // ---- Form type chips ----
  const [formTypes, setFormTypes] = useState<Set<string>>(
    new Set(FORM_TYPES),
  );

  // ---- Count mode ----
  const [countMode, setCountMode] = useState<"latest" | "total" | "per_form">(
    "latest",
  );
  const [count, setCount] = useState("");

  // ---- Date filters (collapsible) ----
  const [showDateFilters, setShowDateFilters] = useState(false);
  const dateFiltersPanelId = useId();
  const [year, setYear] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  // ---- Ticker helpers ----

  /** Add a ticker tag, rejecting empty strings and duplicates. */
  function addTicker(raw: string) {
    const ticker = raw.toUpperCase().trim();
    if (!ticker) return;
    if (tickers.includes(ticker)) return;
    setTickers((prev) => [...prev, ticker]);
    setTickerInput("");
  }

  function removeTicker(ticker: string) {
    setTickers((prev) => prev.filter((t) => t !== ticker));
  }

  function handleTickerKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addTicker(tickerInput);
    }
    // Backspace on empty input removes the last tag.
    if (e.key === "Backspace" && !tickerInput && tickers.length > 0) {
      setTickers((prev) => prev.slice(0, -1));
    }
  }

  function handleTickerBlur() {
    if (tickerInput.trim()) {
      addTicker(tickerInput);
    }
  }

  // ---- Form type chip toggle ----

  function toggleFormType(formType: string) {
    // Guard before the state updater — calling addToast (which sets
    // ToastProvider state) inside setFormTypes's updater would violate
    // React's "no setState during another component's render" rule.
    if (formTypes.has(formType) && formTypes.size === 1) {
      addToast("info", "At least one form type must be selected.");
      return;
    }
    setFormTypes((prev) => {
      const next = new Set(prev);
      if (next.has(formType)) {
        next.delete(formType);
      } else {
        next.add(formType);
      }
      return next;
    });
  }

  // ---- Submit ----

  const canSubmit = tickers.length > 0 && formTypes.size > 0 && !isSubmitting;

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;

    const request: IngestRequest = {
      tickers,
      form_types: Array.from(formTypes),
      count_mode: countMode,
      // "latest" mode always sends 1 per form (backend default), no count needed.
      count: countMode === "latest" ? undefined : (Number(count) || undefined),
      year: Number(year) || undefined,
      start_date: startDate || undefined,
      end_date: endDate || undefined,
    };

    onSubmit(request);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* ---- Ticker tag input ---- */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
          Tickers
        </label>
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-gray-300 bg-white p-2 focus-within:border-blue-500 focus-within:ring-1 focus-within:ring-blue-500 dark:border-gray-700 dark:bg-gray-900">
          {/* Existing tags */}
          {tickers.map((ticker) => (
            <span
              key={ticker}
              className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-3 py-1 text-sm font-medium text-blue-800 dark:bg-blue-900 dark:text-blue-200"
            >
              {ticker}
              <button
                type="button"
                onClick={() => removeTicker(ticker)}
                className="ml-0.5 rounded-full p-0.5 text-blue-600 hover:bg-blue-200 hover:text-blue-800 dark:text-blue-300 dark:hover:bg-blue-800 dark:hover:text-blue-100"
                aria-label={`Remove ${ticker}`}
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
          {/* Text input */}
          <input
            type="text"
            value={tickerInput}
            onChange={(e) => setTickerInput(e.target.value)}
            onKeyDown={handleTickerKeyDown}
            onBlur={handleTickerBlur}
            placeholder={
              tickers.length === 0 ? "Type a ticker and press Enter..." : ""
            }
            className="min-w-[120px] flex-1 border-0 bg-transparent p-1 text-sm text-gray-900 outline-none placeholder:text-gray-400 dark:text-gray-100 dark:placeholder:text-gray-500"
          />
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400">
          Press Enter or comma to add. Backspace removes the last tag.
        </p>
      </div>

      {/* ---- Form type chips ---- */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
          Form types
        </label>
        <div className="flex gap-2">
          {FORM_TYPES.map((ft) => {
            const isActive = formTypes.has(ft);
            return (
              <button
                key={ft}
                type="button"
                onClick={() => toggleFormType(ft)}
                className={`rounded-full border px-4 py-1.5 text-sm font-medium transition-colors ${CHIP_CLASSES[isActive ? "active" : "inactive"]}`}
              >
                {ft}
              </button>
            );
          })}
        </div>
      </div>

      {/* ---- Count mode radio ---- */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
          Count mode
        </label>
        <div className="grid gap-3 sm:grid-cols-3">
          {(Object.keys(COUNT_MODE_INFO) as Array<"latest" | "total" | "per_form">).map(
            (mode) => {
              const info = COUNT_MODE_INFO[mode];
              const isSelected = countMode === mode;
              return (
                <label
                  key={mode}
                  className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors ${
                    isSelected
                      ? "border-blue-300 bg-blue-50 dark:border-blue-700 dark:bg-blue-950"
                      : "border-gray-200 bg-white hover:border-gray-300 dark:border-gray-700 dark:bg-gray-900 dark:hover:border-gray-600"
                  }`}
                >
                  <input
                    type="radio"
                    name="countMode"
                    value={mode}
                    checked={isSelected}
                    onChange={() => setCountMode(mode)}
                    className="mt-0.5 accent-blue-600"
                  />
                  <div>
                    <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                      {info.label}
                    </span>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {info.description}
                    </p>
                  </div>
                </label>
              );
            },
          )}
        </div>

        {/* Count input — visible only for total / per_form modes */}
        {countMode !== "latest" && (
          <div className="mt-2">
            <label className="space-y-1">
              <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
                Number of filings
              </span>
              <input
                type="number"
                min={1}
                max={20}
                value={count}
                onChange={(e) => setCount(e.target.value)}
                placeholder="e.g. 3"
                className="w-32 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 placeholder:text-gray-400 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100 dark:placeholder:text-gray-500"
              />
            </label>
          </div>
        )}
      </div>

      {/* ---- Date filters (collapsible) ---- */}
      <div>
        <button
          type="button"
          onClick={() => setShowDateFilters(!showDateFilters)}
          aria-expanded={showDateFilters}
          aria-controls={dateFiltersPanelId}
          className="flex items-center gap-2 text-sm font-medium text-gray-600 transition-colors hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200"
        >
          <Calendar className="h-4 w-4" />
          Date Filters
          {showDateFilters ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </button>

        {showDateFilters && (
          <div
            id={dateFiltersPanelId}
            role="region"
            aria-label="Date filters"
            className="mt-3 grid gap-4 rounded-lg border border-gray-200 bg-white p-4 sm:grid-cols-3 dark:border-gray-800 dark:bg-gray-950"
          >
            {/* Year */}
            <label className="space-y-1">
              <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
                Year
              </span>
              <input
                type="number"
                min={1993}
                max={new Date().getFullYear()}
                value={year}
                onChange={(e) => setYear(e.target.value)}
                placeholder="e.g. 2024"
                className="w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 placeholder:text-gray-400 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100 dark:placeholder:text-gray-500"
              />
            </label>

            {/* Start date */}
            <label className="space-y-1">
              <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
                Start date
              </span>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
              />
            </label>

            {/* End date */}
            <label className="space-y-1">
              <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
                End date
              </span>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
              />
            </label>
          </div>
        )}
      </div>

      {/* ---- Submit button ---- */}
      <Button
        type="submit"
        disabled={!canSubmit}
        loading={isSubmitting}
      >
        <Upload className="mr-2 h-4 w-4" />
        {tickers.length <= 1 ? "Start Ingestion" : `Ingest ${tickers.length} Tickers`}
      </Button>
    </form>
  );
}