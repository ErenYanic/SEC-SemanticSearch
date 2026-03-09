/**
 * Centralised API client for the SEC Semantic Search backend.
 *
 * All HTTP communication with the FastAPI backend flows through this
 * module.  It provides:
 *   1. A pre-configured Axios instance with the base URL and error
 *      interceptor.
 *   2. One function per API endpoint, fully typed with the interfaces
 *      from `types.ts`.
 *
 * Components never call `axios.get()` directly — they use these
 * functions, which keeps API details (URLs, method, body shape) in
 * one place.
 */

import axios, { AxiosError } from "axios";
import type {
  ApiError,
  BulkDeleteRequest,
  BulkDeleteResponse,
  ClearAllResponse,
  DeleteByIdsRequest,
  DeleteByIdsResponse,
  DeleteResponse,
  Filing,
  FilingListResponse,
  GPUStatusResponse,
  GPUUnloadResponse,
  IngestRequest,
  SearchRequest,
  SearchResponse,
  StatusResponse,
  TaskListResponse,
  TaskResponse,
  TaskStatus,
} from "./types";

// ---------------------------------------------------------------------------
// Axios instance
// ---------------------------------------------------------------------------

/**
 * Pre-configured Axios instance.
 *
 * `baseURL` is empty because the Next.js dev server proxies `/api/*`
 * to the FastAPI backend (see `next.config.ts` rewrites).  In
 * production, the same relative paths work when FastAPI serves the
 * frontend or both sit behind a reverse proxy.
 */
const client = axios.create({
  headers: {
    "Content-Type": "application/json",
  },
});

// ---------------------------------------------------------------------------
// Error interceptor
// ---------------------------------------------------------------------------

/**
 * Extract a structured `ApiError` from an Axios error.
 *
 * The FastAPI backend always returns `{ error, message, details?, hint? }`
 * on 4xx/5xx responses.  If the response doesn't match that shape (e.g.
 * network failure), we construct a fallback error.
 */
export function extractApiError(err: unknown): ApiError {
  if (err instanceof AxiosError && err.response?.data) {
    const data = err.response.data;
    // The backend returns our ErrorResponse schema.
    if (typeof data === "object" && "message" in data) {
      return data as ApiError;
    }
    // FastAPI validation errors (422) have a different shape.
    if (typeof data === "object" && "detail" in data) {
      return {
        error: "ValidationError",
        message: Array.isArray(data.detail)
          ? data.detail.map((d: { msg: string }) => d.msg).join("; ")
          : String(data.detail),
      };
    }
  }

  // Network error or unexpected shape.
  const message =
    err instanceof Error ? err.message : "An unexpected error occurred";
  return { error: "NetworkError", message };
}

// ---------------------------------------------------------------------------
// Status
// ---------------------------------------------------------------------------

/** Fetch database overview. */
export async function getStatus(): Promise<StatusResponse> {
  const { data } = await client.get<StatusResponse>("/api/status/");
  return data;
}

// ---------------------------------------------------------------------------
// Filings
// ---------------------------------------------------------------------------

export interface FilingListParams {
  ticker?: string;
  form_type?: string;
  sort_by?: "filing_date" | "ticker" | "form_type" | "chunk_count" | "ingested_at";
  order?: "asc" | "desc";
}

/** List filings with optional filters. */
export async function getFilings(
  params?: FilingListParams,
): Promise<FilingListResponse> {
  const { data } = await client.get<FilingListResponse>("/api/filings/", {
    params,
  });
  return data;
}

/** Get a single filing by accession number. */
export async function getFiling(accessionNumber: string): Promise<Filing> {
  const { data } = await client.get<Filing>(
    `/api/filings/${encodeURIComponent(accessionNumber)}`,
  );
  return data;
}

/** Delete a single filing. */
export async function deleteFiling(
  accessionNumber: string,
): Promise<DeleteResponse> {
  const { data } = await client.delete<DeleteResponse>(
    `/api/filings/${encodeURIComponent(accessionNumber)}`,
  );
  return data;
}

/** Delete specific filings by accession numbers in a single request. */
export async function deleteFilingsByIds(
  accessionNumbers: string[],
): Promise<DeleteByIdsResponse> {
  const { data } = await client.post<DeleteByIdsResponse>(
    "/api/filings/delete-by-ids",
    { accession_numbers: accessionNumbers } satisfies DeleteByIdsRequest,
  );
  return data;
}

/** Bulk-delete filings by ticker and/or form type. */
export async function bulkDeleteFilings(
  body: BulkDeleteRequest,
): Promise<BulkDeleteResponse> {
  const { data } = await client.post<BulkDeleteResponse>(
    "/api/filings/bulk-delete",
    body,
  );
  return data;
}

/** Clear all filings (requires confirm=true). */
export async function clearAllFilings(): Promise<ClearAllResponse> {
  const { data } = await client.delete<ClearAllResponse>("/api/filings/", {
    params: { confirm: true },
  });
  return data;
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

/** Execute a semantic search query. */
export async function search(body: SearchRequest): Promise<SearchResponse> {
  const { data } = await client.post<SearchResponse>("/api/search/", body);
  return data;
}

// ---------------------------------------------------------------------------
// Ingest
// ---------------------------------------------------------------------------

/** Start a single-ticker ingestion task. */
export async function ingestAdd(body: IngestRequest): Promise<TaskResponse> {
  const { data } = await client.post<TaskResponse>("/api/ingest/add", body);
  return data;
}

/** Start a multi-ticker batch ingestion task. */
export async function ingestBatch(body: IngestRequest): Promise<TaskResponse> {
  const { data } = await client.post<TaskResponse>("/api/ingest/batch", body);
  return data;
}

/** List all ingestion tasks (active + recent). */
export async function getTasks(): Promise<TaskListResponse> {
  const { data } = await client.get<TaskListResponse>("/api/ingest/tasks");
  return data;
}

/** Get status of a specific task. */
export async function getTask(taskId: string): Promise<TaskStatus> {
  const { data } = await client.get<TaskStatus>(
    `/api/ingest/tasks/${encodeURIComponent(taskId)}`,
  );
  return data;
}

/** Cancel a running task. */
export async function cancelTask(taskId: string): Promise<void> {
  await client.delete(`/api/ingest/tasks/${encodeURIComponent(taskId)}`);
}

// ---------------------------------------------------------------------------
// GPU / Resources
// ---------------------------------------------------------------------------

/** Check GPU / embedding model status. */
export async function getGPUStatus(): Promise<GPUStatusResponse> {
  const { data } = await client.get<GPUStatusResponse>("/api/resources/gpu");
  return data;
}

/** Unload the embedding model to free VRAM. */
export async function unloadGPU(): Promise<GPUUnloadResponse> {
  const { data } = await client.delete<GPUUnloadResponse>("/api/resources/gpu");
  return data;
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

/** Simple liveness check. */
export async function healthCheck(): Promise<{ status: string; version: string }> {
  const { data } = await client.get<{ status: string; version: string }>(
    "/api/health",
  );
  return data;
}