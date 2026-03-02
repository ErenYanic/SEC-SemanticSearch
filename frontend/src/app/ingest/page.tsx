/**
 * Ingest page — start and monitor filing ingestion.
 *
 * ## Architecture: state machine driven by hook state
 *
 * This page owns no local state.  All state comes from `useIngest()`,
 * whose `status` field drives which component is rendered:
 *
 *   - **idle**       → IngestForm (configure and start)
 *   - **pending**    → ProgressTracker (waiting for GPU slot)
 *   - **running**    → ProgressTracker (live WebSocket progress)
 *   - **completed**  → IngestSummary (results + "Ingest More")
 *   - **failed**     → Error alert + "Try Again" button
 *   - **cancelled**  → Cancel notice + partial IngestSummary
 *
 * The page passes callbacks (`handleSubmit`, `handleCancel`, `reset`)
 * to child components.  Children are purely presentational — they
 * receive data and fire callbacks, nothing else.
 *
 * ## Active task recovery
 *
 * On mount, `useIngest` checks `GET /api/ingest/tasks` for running
 * tasks.  If found, it resumes with WebSocket streaming — so the user
 * can navigate away during ingestion and come back to see progress.
 */

"use client";

import { Upload, AlertCircle, XCircle } from "lucide-react";
import { useIngest } from "@/hooks/useIngest";
import { useToast } from "@/components/ui";
import { extractApiError } from "@/lib/api";
import { Button } from "@/components/ui";
import { IngestForm, ProgressTracker, IngestSummary } from "@/components/ingest";
import type { IngestRequest } from "@/lib/types";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function IngestPage() {
  const ingest = useIngest();
  const { addToast } = useToast();

  // ---- Submit handler ----
  async function handleSubmit(request: IngestRequest) {
    try {
      await ingest.startIngest(request);
    } catch (err) {
      addToast("error", extractApiError(err).message);
    }
  }

  // ---- Cancel handler ----
  async function handleCancel() {
    try {
      await ingest.cancel();
      addToast("info", "Cancellation requested");
    } catch (err) {
      addToast("error", extractApiError(err).message);
    }
  }

  // ---- Page header (always shown) ----
  const header = (
    <div className="flex items-center gap-3">
      <Upload className="h-8 w-8 text-blue-600 dark:text-blue-400" />
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
        Ingest
      </h1>
    </div>
  );

  // ---- State machine rendering ----
  switch (ingest.status) {
    case "idle":
      return (
        <div className="space-y-6">
          {header}
          <p className="text-gray-600 dark:text-gray-400">
            Fetch SEC filings, process them into chunks, and embed them for
            semantic search.
          </p>
          <IngestForm onSubmit={handleSubmit} isSubmitting={false} />
        </div>
      );

    case "pending":
    case "running":
      return (
        <div className="space-y-6">
          {header}
          <ProgressTracker
            progress={ingest.progress}
            filingEvents={ingest.filingEvents}
            canCancel={true}
            onCancel={handleCancel}
          />
        </div>
      );

    case "completed":
      return (
        <div className="space-y-6">
          {header}
          {ingest.summary && (
            <IngestSummary
              results={ingest.results}
              summary={ingest.summary}
              filingEvents={ingest.filingEvents}
              startedAt={ingest.startedAt}
              completedAt={ingest.completedAt}
              onReset={ingest.reset}
            />
          )}
        </div>
      );

    case "failed":
      return (
        <div className="space-y-6">
          {header}
          <div className="rounded-lg border border-red-200 bg-red-50 p-6 dark:border-red-900 dark:bg-red-950">
            <div className="flex items-center gap-3">
              <AlertCircle className="h-6 w-6 text-red-600 dark:text-red-400" />
              <h2 className="text-lg font-semibold text-red-800 dark:text-red-200">
                Ingestion Failed
              </h2>
            </div>
            <p className="mt-2 text-sm text-red-700 dark:text-red-300">
              {ingest.error || "An unexpected error occurred."}
            </p>
            {/* Show partial results if any filings were ingested before failure */}
            {ingest.filingEvents.length > 0 && ingest.summary && (
              <div className="mt-4">
                <IngestSummary
                  results={ingest.results}
                  summary={ingest.summary}
                  filingEvents={ingest.filingEvents}
                  startedAt={ingest.startedAt}
                  completedAt={ingest.completedAt}
                  onReset={ingest.reset}
                />
              </div>
            )}
            {ingest.filingEvents.length === 0 && (
              <Button className="mt-4" onClick={ingest.reset}>
                Try Again
              </Button>
            )}
          </div>
        </div>
      );

    case "cancelled":
      return (
        <div className="space-y-6">
          {header}
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-6 dark:border-amber-900 dark:bg-amber-950">
            <div className="flex items-center gap-3">
              <XCircle className="h-6 w-6 text-amber-600 dark:text-amber-400" />
              <h2 className="text-lg font-semibold text-amber-800 dark:text-amber-200">
                Ingestion Cancelled
              </h2>
            </div>
            <p className="mt-2 text-sm text-amber-700 dark:text-amber-300">
              The ingestion was cancelled. Any filings that were fully
              processed have been kept in the database.
            </p>
          </div>

          {/* Show partial results if any filings were ingested before cancel */}
          {ingest.filingEvents.length > 0 && ingest.summary && (
            <IngestSummary
              results={ingest.results}
              summary={ingest.summary}
              filingEvents={ingest.filingEvents}
              startedAt={ingest.startedAt}
              completedAt={ingest.completedAt}
              onReset={ingest.reset}
            />
          )}
          {ingest.filingEvents.length === 0 && (
            <div className="flex justify-center">
              <Button onClick={ingest.reset}>
                <Upload className="mr-2 h-4 w-4" />
                Ingest Again
              </Button>
            </div>
          )}
        </div>
      );
  }
}