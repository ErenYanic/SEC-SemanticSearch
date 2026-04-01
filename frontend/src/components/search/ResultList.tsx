/**
 * Renders the search results list with a summary header,
 * or an empty state when there are no results.
 *
 * ## Why a separate component for the list?
 *
 * The page component handles the state machine (idle → loading →
 * error → results). But within the "results" state, there's still
 * a decision: "are there zero results or some?" Putting that logic
 * here keeps the page component focused on top-level orchestration.
 *
 * ## The summary header
 *
 * Shows "{n} results for '{query}' in {time}ms" — echoing back
 * the query and timing gives the user confidence the system
 * understood their request and is performing well.
 *
 * The query text comes from the page's local state, **not** from the
 * API response — the search endpoint intentionally omits the query
 * to avoid echoing sensitive input over the wire (see §F4).
 */

import { SearchX } from "lucide-react";
import { EmptyState } from "@/components/ui";
import { ResultCard } from "./ResultCard";
import type { SearchResponse } from "@/lib/types";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ResultListProps {
  response: SearchResponse;
  query: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ResultList({ response, query }: ResultListProps) {
  if (response.results.length === 0) {
    return (
      <EmptyState
        icon={SearchX}
        title="No results found"
        description="Try broadening your query, removing filters, or lowering the similarity threshold."
      />
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary header */}
      <p className="text-sm text-gray-600 dark:text-gray-400">
        {response.total_results} result{response.total_results !== 1 && "s"}{" "}
        for &ldquo;{query}&rdquo; in{" "}
        {response.search_time_ms.toFixed(0)} ms
      </p>

      {/* Result cards */}
      {response.results.map((result, index) => (
        <ResultCard
          key={result.chunk_id ?? index}
          result={result}
          rank={index + 1}
        />
      ))}
    </div>
  );
}