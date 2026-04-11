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
  idle: "Ready",
  pending: "Queued",
  running: "Streaming",
  completed: "Complete",
  failed: "Error",
  cancelled: "Cancelled",
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
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-3xl font-semibold tracking-tight text-fg sm:text-4xl">
          Ingest
        </h1>
        <span
          className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm font-medium ${STATUS_TONE[ingest.status]} ${
            ingest.status === "running" || ingest.status === "pending"
              ? "border-accent/40 bg-accent/10"
              : ingest.status === "completed"
                ? "border-pos/40 bg-pos/10"
                : ingest.status === "failed"
                  ? "border-neg/40 bg-neg/10"
                  : ingest.status === "cancelled"
                    ? "border-warn/40 bg-warn/10"
                    : "border-hairline bg-card/70"
          }`}
        >
          <span
            className={`h-1.5 w-1.5 rounded-full bg-current ${
              ingest.status === "running" || ingest.status === "pending"
                ? "animate-pulse"
                : ""
            }`}
            aria-hidden="true"
          />
          {STATUS_LABEL[ingest.status]}
        </span>
      </div>
    </div>
  );

  switch (ingest.status) {
    case "idle":
      return (
        <div className="space-y-8 [animation:fade-in_300ms_ease-out]">
          {header}
          <p className="max-w-2xl text-base text-fg-muted">
            Fetch SEC filings, process them into chunks, and embed them for
            semantic search.
          </p>
          <IngestForm onSubmit={handleSubmit} isSubmitting={false} />
        </div>
      );

    case "pending":
    case "running":
      return (
        <div className="space-y-8 [animation:fade-in_300ms_ease-out]">
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
        <div className="space-y-8 [animation:fade-in_300ms_ease-out]">
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
        <div className="space-y-8 [animation:fade-in_300ms_ease-out]">
          {header}
          <div className="rounded-2xl border border-neg/40 bg-neg/5 p-6 shadow-sm backdrop-blur-sm">
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-neg/10 text-neg">
                <AlertCircle className="h-5 w-5" />
              </span>
              <h2 className="text-lg font-semibold text-fg">
                Ingestion failed
              </h2>
            </div>
            <p className="mt-3 text-sm text-fg-muted">
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
              <Button className="mt-5" onClick={ingest.reset}>
                Try Again
              </Button>
            )}
          </div>
        </div>
      );

    case "cancelled":
      return (
        <div className="space-y-8 [animation:fade-in_300ms_ease-out]">
          {header}
          <div className="rounded-2xl border border-warn/40 bg-warn/5 p-6 shadow-sm backdrop-blur-sm">
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-warn/10 text-warn">
                <XCircle className="h-5 w-5" />
              </span>
              <h2 className="text-lg font-semibold text-fg">
                Ingestion cancelled
              </h2>
            </div>
            <p className="mt-3 text-sm text-fg-muted">
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
