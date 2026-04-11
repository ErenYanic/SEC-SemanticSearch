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
// Status meta strip
// ---------------------------------------------------------------------------

const STATUS_LABEL: Record<string, string> = {
  idle: "READY",
  pending: "QUEUED",
  running: "STREAMING",
  completed: "COMPLETE",
  failed: "ERROR",
  cancelled: "CANCELLED",
};

const STATUS_TONE: Record<string, string> = {
  idle: "text-fg-muted",
  pending: "text-warn",
  running: "text-accent",
  completed: "text-pos",
  failed: "text-neg",
  cancelled: "text-warn",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function IngestPage() {
  const ingest = useIngest();
  const { addToast } = useToast();

  async function handleSubmit(request: IngestRequest) {
    try {
      await ingest.startIngest(request);
    } catch (err) {
      addToast("error", extractApiError(err).message);
    }
  }

  async function handleCancel() {
    try {
      await ingest.cancel();
      addToast("info", "Cancellation requested");
    } catch (err) {
      addToast("error", extractApiError(err).message);
    }
  }

  const header = (
    <div className="flex flex-wrap items-baseline justify-between gap-3">
      <h1 className="text-2xl font-semibold tracking-tight text-fg">Ingest</h1>
      <div className="flex items-baseline gap-2 font-mono text-[11px] uppercase tabular-nums text-fg-muted">
        <span className="text-fg-subtle">status</span>
        <span className={`font-semibold ${STATUS_TONE[ingest.status]}`}>
          {STATUS_LABEL[ingest.status]}
        </span>
      </div>
    </div>
  );

  switch (ingest.status) {
    case "idle":
      return (
        <div className="space-y-5 [animation:fade-in_200ms_ease-out]">
          {header}
          <p className="max-w-2xl text-sm text-fg-muted">
            Fetch SEC filings, process them into chunks, and embed them for
            semantic search.
          </p>
          <IngestForm onSubmit={handleSubmit} isSubmitting={false} />
        </div>
      );

    case "pending":
    case "running":
      return (
        <div className="space-y-5 [animation:fade-in_200ms_ease-out]">
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
        <div className="space-y-5 [animation:fade-in_200ms_ease-out]">
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
        <div className="space-y-5 [animation:fade-in_200ms_ease-out]">
          {header}
          <div className="rounded-lg border border-neg/40 bg-neg/5 p-5">
            <div className="flex items-center gap-2.5">
              <AlertCircle className="h-4 w-4 text-neg" />
              <h2 className="font-mono text-[11px] font-semibold uppercase tracking-widest text-neg">
                Ingestion Failed
              </h2>
            </div>
            <p className="mt-2 text-sm text-fg-muted">
              {ingest.error || "An unexpected error occurred."}
            </p>
            {ingest.filingEvents.length > 0 && ingest.summary && (
              <div className="mt-5">
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
        <div className="space-y-5 [animation:fade-in_200ms_ease-out]">
          {header}
          <div className="rounded-lg border border-warn/40 bg-warn/5 p-5">
            <div className="flex items-center gap-2.5">
              <XCircle className="h-4 w-4 text-warn" />
              <h2 className="font-mono text-[11px] font-semibold uppercase tracking-widest text-warn">
                Ingestion Cancelled
              </h2>
            </div>
            <p className="mt-2 text-sm text-fg-muted">
              The ingestion was cancelled. Any filings that were fully
              processed have been kept in the database.
            </p>
          </div>

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
            <div className="flex justify-end">
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
