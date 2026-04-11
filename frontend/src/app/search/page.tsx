/**
 * Search page — semantic search over ingested SEC filings.
 *
 * ## Layout (two-column workbench on lg+)
 *
 *   ┌────────────────────────────────────────────────────────────┐
 *   │  SEARCH › Semantic Query   12,483 filings · 892K chunks   │  header
 *   │  [  Search bar  ................................ [Search]]│  search
 *   ├──────────────┬─────────────────────────────────────────────┤
 *   │              │                                             │
 *   │  Filter rail │  Results OR idle content                   │
 *   │  (always     │  (SuggestedQueries + FilingInventory)      │
 *   │   visible)   │                                             │
 *   │              │                                             │
 *   └──────────────┴─────────────────────────────────────────────┘
 *
 * Below lg the rail collapses under the main column so the page
 * remains single-column on tablet and phone.
 *
 * ## Architecture: state machine with two data sources
 *
 *   1. **Status** (`useStatus`) — fetched on mount; populates the
 *      ticker rail, the placeholder chunk count, and the filing
 *      inventory.  Shared with Dashboard via React Query cache.
 *
 *   2. **Search** (`useSearch`) — fired on form submit. Imperative
 *      mutation, no cache.
 *
 * States:
 *   - **idle**     — rail + search bar + suggested queries + inventory
 *   - **loading**  — rail + search bar + spinner column
 *   - **error**    — rail + search bar + error banner
 *   - **results**  — rail + search bar + ResultList
 *
 * ## State ownership
 *
 * `query` and `filters` live on this page. They're passed down into
 * controlled child components (SearchBar, SearchFilters) so this
 * page is the single source of truth for what gets sent to the API.
 */

"use client";

import { useState } from "react";
import { Database, Upload } from "lucide-react";
import Link from "next/link";
import { useStatus } from "@/hooks/useStatus";
import { useSearch } from "@/hooks/useSearch";
import { extractApiError } from "@/lib/api";
import { Button, EmptyState, Spinner } from "@/components/ui";
import {
  SearchBar,
  SearchFilters,
  SearchResultSkeleton,
  ResultList,
  FilingInventory,
  SuggestedQueries,
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
      // Convert empty arrays/strings to undefined so they're omitted from
      // the request body. The API treats missing fields as "no filter".
      ticker: filters.tickers.length > 0 ? filters.tickers : undefined,
      form_type: filters.formTypes.length > 0 ? filters.formTypes : undefined,
      accession_number:
        filters.accessionNumbers.length > 0
          ? filters.accessionNumbers
          : undefined,
      start_date: filters.startDate || undefined,
      end_date: filters.endDate || undefined,
    });
  }

  // ---- Suggested query click: fills the box and submits ----
  function handleSuggestedQuery(example: string) {
    setQuery(example);
    handleSearch(example);
  }

  const filingCount = status?.filing_count ?? 0;
  const chunkCount = status?.chunk_count ?? 0;

  return (
    <div className="space-y-8 [animation:fade-in_300ms_ease-out]">
      {/* ---- Page header ---- */}
      <div className="space-y-3">
        <h1 className="text-3xl font-semibold tracking-tight text-fg sm:text-4xl">
          Search
        </h1>
        {status && (
          <p className="text-base text-fg-muted">
            Semantic search across{" "}
            <span className="font-semibold text-fg">
              {filingCount.toLocaleString()}
            </span>{" "}
            filing{filingCount !== 1 && "s"} ·{" "}
            <span className="font-semibold text-fg">
              {chunkCount.toLocaleString()}
            </span>{" "}
            chunks indexed
          </p>
        )}
      </div>

      {/* ---- Search bar ---- */}
      <SearchBar
        query={query}
        onQueryChange={setQuery}
        onSubmit={handleSearch}
        isSearching={isSearching}
        chunkCount={chunkCount}
        filingCount={filingCount}
      />

      {/* ---- Two-column workbench ---- */}
      <div className="grid gap-6 lg:grid-cols-[300px_1fr]">
        {/* Left rail — filters */}
        <SearchFilters
          filters={filters}
          onFiltersChange={setFilters}
          availableTickers={status?.tickers ?? []}
          alwaysOpen
        />

        {/* Main column */}
        <div className="min-w-0 space-y-5">
          {/* Error state */}
          {isError && (
            <div
              role="alert"
              className="rounded-2xl border border-neg/40 bg-neg/10 p-5"
            >
              <p className="text-base font-semibold text-neg">Search failed</p>
              <p className="mt-1 text-sm text-neg/90">
                {extractApiError(error).message}
              </p>
            </div>
          )}

          {/* Loading state */}
          {isSearching && (
            <div className="flex items-center justify-center rounded-2xl border border-hairline bg-card/60 py-20">
              <Spinner size="md" />
              <span className="ml-3 text-sm font-medium text-fg-muted">
                Running semantic search…
              </span>
            </div>
          )}

          {/* Results */}
          {searchResponse && !isSearching && (
            <ResultList response={searchResponse} query={query} />
          )}

          {/* Idle state: suggested queries + inventory */}
          {!searchResponse && !isSearching && !isError && status && (
            <>
              <SuggestedQueries onSelect={handleSuggestedQuery} />
              <FilingInventory status={status} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
