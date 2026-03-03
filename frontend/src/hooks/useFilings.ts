/**
 * useFilings — data hook for the Filings page.
 *
 * Bundles a parameterised query (filing list with filters/sort) and three
 * delete mutations (single, multi-select, clear-all) behind a single
 * hook interface. The page never touches React Query directly.
 *
 * ## Query key
 *
 *   `["filings", ticker, formType, sortBy, order]`
 *
 * Changing any parameter automatically triggers a refetch because React
 * Query treats each unique key combination as a separate cache entry.
 *
 * ## Cache strategy after deletions
 *
 *   - **Single delete:** optimistic removal — we know exactly which
 *     filing was deleted, so we splice it out of the cached list for
 *     instant visual feedback.
 *   - **Multi-select delete:** loops single delete sequentially.
 *     Each call optimistically removes its filing from the cache.
 *   - **Clear all:** sets the cache to `{ filings: [], total: 0 }`
 *     immediately (everything is gone).
 *
 * All mutations also invalidate `["status"]` so the Dashboard's counts
 * update without a manual refresh.
 */

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  Filing,
  FilingListResponse,
  DeleteResponse,
  ClearAllResponse,
} from "@/lib/types";
import {
  getFilings,
  deleteFiling,
  clearAllFilings,
  type FilingListParams,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Parameters controlling which filings to fetch and how to sort them. */
export interface FilingQueryParams {
  ticker: string;
  formType: string;
  sortBy: NonNullable<FilingListParams["sort_by"]>;
  order: "asc" | "desc";
}

export const DEFAULT_QUERY_PARAMS: FilingQueryParams = {
  ticker: "",
  formType: "",
  sortBy: "filing_date",
  order: "desc",
};

export interface UseFilingsReturn {
  /** Filings matching the current filters, server-sorted. */
  filings: Filing[];
  /** Total count of filings matching the current filters. */
  total: number;
  /** True while the filing list is loading. */
  isLoading: boolean;
  /** True if the fetch failed. */
  isError: boolean;
  /** Error object if the fetch failed. */
  error: Error | null;

  /** Delete a single filing by accession number. */
  deleteSingle: (accessionNumber: string) => Promise<DeleteResponse>;
  /** Delete multiple filings by accession number (sequential calls). */
  deleteSelected: (accessionNumbers: string[]) => Promise<DeleteResponse[]>;
  /** Delete ALL filings in the database. */
  clearAll: () => Promise<ClearAllResponse>;
  /** True while any deletion is in progress. */
  isDeleting: boolean;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useFilings(params: FilingQueryParams): UseFilingsReturn {
  const queryClient = useQueryClient();

  // The query key encodes every parameter so React Query refetches
  // automatically when the user changes a filter or sort column.
  const queryKey = [
    "filings",
    params.ticker,
    params.formType,
    params.sortBy,
    params.order,
  ];

  // ---- Query: fetch filing list ----
  const { data, isLoading, isError, error } = useQuery<FilingListResponse>({
    queryKey,
    queryFn: () =>
      getFilings({
        ticker: params.ticker || undefined,
        form_type: params.formType || undefined,
        sort_by: params.sortBy,
        order: params.order,
      }),
  });

  // ---- Mutation: delete a single filing ----
  const singleDelete = useMutation<DeleteResponse, Error, string>({
    mutationFn: deleteFiling,
    onSuccess: (_result, accessionNumber) => {
      // Optimistic removal: splice the deleted filing out of the
      // cached list. This gives instant visual feedback — the row
      // disappears without waiting for a refetch.
      queryClient.setQueryData<FilingListResponse>(queryKey, (old) => {
        if (!old) return old;
        const filtered = old.filings.filter(
          (f) => f.accession_number !== accessionNumber,
        );
        return { filings: filtered, total: filtered.length };
      });
      // Dashboard counts should update too.
      queryClient.invalidateQueries({ queryKey: ["status"] });
    },
  });

  // ---- Mutation: clear all filings ----
  const clearMutation = useMutation<ClearAllResponse, Error, void>({
    mutationFn: clearAllFilings,
    onSuccess: () => {
      // Everything is gone. Set the cache to empty immediately.
      queryClient.setQueryData<FilingListResponse>(queryKey, {
        filings: [],
        total: 0,
      });
      queryClient.invalidateQueries({ queryKey: ["status"] });
    },
  });

  // Multi-select delete: sequential single-delete calls.
  // The backend has no "delete by list" endpoint, so we loop.
  // Sequential (not parallel) avoids SQLite lock contention and
  // lets each optimistic cache removal build on the previous one.
  async function deleteSelected(
    accessionNumbers: string[],
  ): Promise<DeleteResponse[]> {
    const results: DeleteResponse[] = [];
    for (const accession of accessionNumbers) {
      const result = await singleDelete.mutateAsync(accession);
      results.push(result);
    }
    return results;
  }

  const isDeleting = singleDelete.isPending || clearMutation.isPending;

  return {
    filings: data?.filings ?? [],
    total: data?.total ?? 0,
    isLoading,
    isError,
    error: error ?? null,

    deleteSingle: (accession) => singleDelete.mutateAsync(accession),
    deleteSelected,
    clearAll: () => clearMutation.mutateAsync(),
    isDeleting,
  };
}