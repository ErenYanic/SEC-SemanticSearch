/**
 * Search page — semantic search over ingested SEC filings.
 *
 * ## Architecture: state machine with two data sources
 *
 * This page manages two independent data flows:
 *
 *   1. **Status** (`useStatus`) — fetched on mount to populate the
 *      ticker dropdown and the filing inventory. This is a `useQuery`
 *      (automatic, cached, shared with Dashboard).
 *
 *   2. **Search** (`useSearch`) — fired on form submit. This is a
 *      `useMutation` (imperative, no cache, user-triggered).
 *
 * The search state machine:
 *
 *   idle (no search yet) → isPending (spinner) → data | error
 *
 * The page renders four possible states:
 *
 *   - **Idle**: SearchBar + Filters + FilingInventory (no results yet)
 *   - **Loading**: SearchBar + Filters + Spinner
 *   - **Error**: SearchBar + Filters + error message
 *   - **Results**: SearchBar + Filters + ResultList
 *
 * ## State ownership
 *
 * The page owns three pieces of state:
 *
 *   1. `query` (string) — the text in the search bar
 *   2. `filters` (SearchFilterValues) — the filter panel values
 *   3. Search mutation state (managed by React Query internally)
 *
 * Both `query` and `filters` are **controlled** — the page passes
 * them down to child components and receives changes back up.
 * This makes the page the single source of truth for what will
 * be sent to the API.
 *
 * ## Building the SearchRequest
 *
 * On submit, the page constructs a `SearchRequest` object from
 * `query` + `filters`. Empty filter strings become `undefined`
 * (so they're omitted from the JSON body — the API treats missing
 * fields as "no filter"). This conversion happens in `handleSearch`.
 */

"use client";

import { useState } from "react";
import { Search, Database, Upload } from "lucide-react";
import Link from "next/link";
import { useStatus } from "@/hooks/useStatus";
import { useSearch } from "@/hooks/useSearch";
import { extractApiError } from "@/lib/api";
import { Button, EmptyState } from "@/components/ui";
import {
  SearchBar,
  SearchFilters,
  SearchResultSkeleton,
  ResultList,
  FilingInventory,
  DEFAULT_FILTERS,
  type SearchFilterValues,
} from "@/components/search";

export default function SearchPage() {
  // ---- State ----
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<SearchFilterValues>(DEFAULT_FILTERS);

  // ---- Data sources ----
  const { data: status, isLoading: isStatusLoading } = useStatus();
  const {
    mutate: executeSearch,
    data: searchResponse,
    isPending: isSearching,
    isError,
    error,
  } = useSearch();

  // ---- Loading: status hasn't loaded yet ----
  if (isStatusLoading) {
    return <SearchResultSkeleton />;
  }

  // ---- Empty database: no filings to search ----
  if (status && status.filing_count === 0) {
    return (
      <EmptyState
        icon={Database}
        title="No filings to search"
        description="Ingest SEC filings first, then come back to search them."
        action={
          <Link href="/ingest">
            <Button>
              <Upload className="mr-2 h-4 w-4" />
              Ingest Filings
            </Button>
          </Link>
        }
      />
    );
  }

  // ---- Submit handler: builds SearchRequest from state ----
  function handleSearch(submittedQuery: string) {
    executeSearch({
      query: submittedQuery,
      top_k: filters.topK,
      min_similarity: filters.minSimilarity,
      // Convert empty strings to undefined so they're omitted from
      // the request body. The API treats missing fields as "no filter".
      ticker: filters.ticker || undefined,
      form_type: filters.formType || undefined,
      accession_number: filters.accessionNumber || undefined,
    });
  }

  return (
    <div className="space-y-4 [animation:fade-in_200ms_ease-out]">
      {/* Page header */}
      <div className="flex items-center gap-3">
        <Search className="h-8 w-8 text-blue-600 dark:text-blue-400" />
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          Search
        </h1>
      </div>

      {/* Search bar */}
      <SearchBar
        query={query}
        onQueryChange={setQuery}
        onSubmit={handleSearch}
        isSearching={isSearching}
      />

      {/* Filters */}
      <SearchFilters
        filters={filters}
        onFiltersChange={setFilters}
        availableTickers={status?.tickers ?? []}
      />

      {/* Error state */}
      {isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-950">
          <p className="text-sm font-medium text-red-800 dark:text-red-200">
            Search failed
          </p>
          <p className="mt-1 text-sm text-red-700 dark:text-red-300">
            {extractApiError(error).message}
          </p>
        </div>
      )}

      {/* Results */}
      {searchResponse && !isSearching && (
        <ResultList response={searchResponse} />
      )}

      {/* Filing inventory (shown when no results yet) */}
      {!searchResponse && !isSearching && status && (
        <FilingInventory status={status} />
      )}
    </div>
  );
}