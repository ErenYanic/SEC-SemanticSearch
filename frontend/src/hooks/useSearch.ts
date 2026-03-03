import { useMutation } from "@tanstack/react-query";
import { search } from "@/lib/api";
import type { SearchRequest, SearchResponse } from "@/lib/types";

/**
 * Triggers a semantic search via `POST /api/search/`.
 *
 * ## Why `useMutation` instead of `useQuery`?
 *
 * `useQuery` is for data that should be fetched automatically (on mount,
 * on focus, on interval). Search is an **imperative action** — the user
 * types a query and clicks "Search". We want:
 *
 *   1. Nothing happens until the user explicitly submits.
 *   2. The loading indicator shows only during that submission.
 *   3. Previous results stay visible until new ones arrive.
 *
 * `useMutation` gives us exactly this lifecycle:
 *
 *   idle → mutate(request) → isPending → data | error
 *
 * The caller invokes `mutate({ query, top_k, ... })` on form submit.
 *
 * ## Returned values
 *
 * - `mutate(request)` — fire the search
 * - `data` — the `SearchResponse` (undefined until first search)
 * - `isPending` — true while the request is in-flight
 * - `isError` / `error` — if the request failed
 * - `reset()` — clear results (e.g. when the user clears the form)
 */
export function useSearch() {
  return useMutation<SearchResponse, Error, SearchRequest>({
    mutationFn: search,
  });
}