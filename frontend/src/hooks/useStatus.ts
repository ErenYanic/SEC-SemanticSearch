import { useQuery } from "@tanstack/react-query";
import { getStatus } from "@/lib/api";
import type { StatusResponse } from "@/lib/types";

/**
 * Fetches the database status overview.
 *
 * Wraps React Query's `useQuery` so page components don't couple
 * directly to the caching library. The query key `["status"]` lets
 * React Query cache, deduplicate, and invalidate this data globally —
 * any component calling `useStatus()` shares the same cache entry.
 */
export function useStatus() {
  return useQuery<StatusResponse>({
    queryKey: ["status"],
    queryFn: getStatus,
  });
}