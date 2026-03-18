/**
 * Real-time progress display during an ingestion task.
 *
 * ## Design
 *
 * Purely presentational — receives all state from the parent via props.
 * The component renders four sections:
 *
 *   1. Status header   — what's currently being processed
 *   2. Progress bar    — overall filings done / total
 *   3. Step indicator  — 5-step horizontal stepper
 *   4. Filing events   — chronological log of results
 *   5. Cancel button   — with Modal confirmation
 *
 * ## Step indicator
 *
 * The pipeline has 5 fixed steps: Fetching → Parsing → Chunking →
 * Embedding → Storing.  The stepper uses `step_index` (0-based) from
 * `TaskProgress` to determine which step is current.  Completed steps
 * show a green checkmark, the current step pulses blue, and upcoming
 * steps are grey.
 */

"use client";

import { useEffect, useRef, useState } from "react";
import {
  CheckCircle2,
  SkipForward,
  XCircle,
  Loader2,
  Trash2,
} from "lucide-react";
import { Button, Modal } from "@/components/ui";
import type { TaskProgress } from "@/lib/types";
import type { FilingEvent } from "@/hooks/useIngest";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ProgressTrackerProps {
  /** Current progress counters from the WebSocket stream. */
  progress: TaskProgress;
  /** Filing events (done/skipped/failed) in chronological order. */
  filingEvents: FilingEvent[];
  /** Whether cancellation is allowed (task is pending or running). */
  canCancel: boolean;
  /** Called when the user confirms cancellation. */
  onCancel: () => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STEP_LABELS = ["Fetching", "Parsing", "Chunking", "Embedding", "Storing"];

// Static Tailwind class maps — never interpolated.
const STEP_CIRCLE_CLASSES: Record<"completed" | "current" | "upcoming", string> = {
  completed: "bg-green-500 text-white dark:bg-green-600",
  current: "bg-blue-500 text-white animate-pulse dark:bg-blue-600",
  upcoming: "bg-gray-200 text-gray-400 dark:bg-gray-700 dark:text-gray-500",
};

const STEP_LABEL_CLASSES: Record<"completed" | "current" | "upcoming", string> = {
  completed: "text-green-700 dark:text-green-400",
  current: "text-blue-700 font-medium dark:text-blue-400",
  upcoming: "text-gray-400 dark:text-gray-500",
};

const STEP_LINE_CLASSES: Record<"completed" | "upcoming", string> = {
  completed: "bg-green-500 dark:bg-green-600",
  upcoming: "bg-gray-200 dark:bg-gray-700",
};

const EVENT_CLASSES: Record<FilingEvent["type"], string> = {
  done: "text-green-600 dark:text-green-400",
  skipped: "text-amber-600 dark:text-amber-400",
  failed: "text-red-600 dark:text-red-400",
  eviction: "text-orange-600 dark:text-orange-400",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getStepState(
  stepIndex: number,
  currentIndex: number,
): "completed" | "current" | "upcoming" {
  if (stepIndex < currentIndex) return "completed";
  if (stepIndex === currentIndex) return "current";
  return "upcoming";
}

function EventIcon({ type }: { type: FilingEvent["type"] }) {
  switch (type) {
    case "done":
      return <CheckCircle2 className="h-4 w-4 shrink-0" />;
    case "skipped":
      return <SkipForward className="h-4 w-4 shrink-0" />;
    case "failed":
      return <XCircle className="h-4 w-4 shrink-0" />;
    case "eviction":
      return <Trash2 className="h-4 w-4 shrink-0" />;
  }
}

function formatEventText(event: FilingEvent): string {
  if (event.type === "eviction") {
    const count = event.filings_evicted ?? 0;
    const tickers = event.tickers_affected?.join(", ") ?? "";
    return `Evicted ${count} old filing${count === 1 ? "" : "s"} to make room${tickers ? ` (${tickers})` : ""}`;
  }
  const prefix = `${event.ticker} ${event.form_type}`;
  switch (event.type) {
    case "done":
      return `${prefix} (${event.filing_date}) \u2014 ${event.segments} segments, ${event.chunks} chunks, ${event.time?.toFixed(1)}s`;
    case "skipped":
      return `${prefix} \u2014 Skipped: ${event.reason ?? "already ingested"}`;
    case "failed":
      return `${prefix} \u2014 Failed: ${event.error ?? "unknown error"}`;
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ProgressTracker({
  progress,
  filingEvents,
  canCancel,
  onCancel,
}: ProgressTrackerProps) {
  const [showCancelModal, setShowCancelModal] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll the event list when new events arrive.
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [filingEvents.length]);

  // ---- Computed values ----
  const hasTotal = progress.filings_total > 0;
  const progressPercent = hasTotal
    ? Math.round(
        ((progress.filings_done + progress.filings_skipped + progress.filings_failed) /
          progress.filings_total) *
          100,
      )
    : 0;

  const statusText =
    progress.current_ticker && progress.current_form_type
      ? `Processing ${progress.current_ticker} ${progress.current_form_type}`
      : "Waiting to start\u2026";

  const counterParts: string[] = [];
  const processed = progress.filings_done + progress.filings_skipped + progress.filings_failed;
  if (hasTotal) {
    counterParts.push(`${processed} of ${progress.filings_total} filings`);
  }
  if (progress.filings_skipped > 0) {
    counterParts.push(`${progress.filings_skipped} skipped`);
  }
  if (progress.filings_failed > 0) {
    counterParts.push(`${progress.filings_failed} failed`);
  }

  return (
    <div className="space-y-6">
      {/* ---- Status header ---- */}
      <div className="flex items-center gap-3">
        <Loader2 className="h-5 w-5 animate-spin text-blue-600 dark:text-blue-400" />
        <span className="text-lg font-medium text-gray-900 dark:text-gray-100">
          {statusText}
        </span>
      </div>

      {/* ---- Overall progress bar ---- */}
      <div className="space-y-2">
        <div className="h-3 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
          {hasTotal ? (
            <div
              className="h-full rounded-full bg-blue-600 transition-all duration-500 dark:bg-blue-500"
              style={{ width: `${progressPercent}%` }}
            />
          ) : (
            // Indeterminate: animated shimmer when total is unknown.
            <div className="h-full w-1/3 animate-pulse rounded-full bg-blue-400 dark:bg-blue-600" />
          )}
        </div>
        {counterParts.length > 0 && (
          <p className="text-sm text-gray-600 dark:text-gray-400">
            {counterParts.join(" \u00B7 ")}
          </p>
        )}
      </div>

      {/* ---- Step indicator (horizontal stepper) ---- */}
      <div className="flex items-center justify-between">
        {STEP_LABELS.map((label, index) => {
          const stepState = getStepState(index, progress.step_index);
          return (
            <div key={label} className="flex flex-1 items-center">
              {/* Step circle */}
              <div className="flex flex-col items-center gap-1">
                <div
                  className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-medium ${STEP_CIRCLE_CLASSES[stepState]}`}
                >
                  {stepState === "completed" ? (
                    <CheckCircle2 className="h-4 w-4" />
                  ) : (
                    index + 1
                  )}
                </div>
                <span
                  className={`text-xs ${STEP_LABEL_CLASSES[stepState]}`}
                >
                  {label}
                </span>
              </div>

              {/* Connecting line (not after the last step) */}
              {index < STEP_LABELS.length - 1 && (
                <div
                  className={`mx-1 h-0.5 flex-1 ${STEP_LINE_CLASSES[index < progress.step_index ? "completed" : "upcoming"]}`}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* ---- Filing event list ---- */}
      {filingEvents.length > 0 && (
        <div className="space-y-1">
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Filing Progress
          </h3>
          <div className="max-h-64 overflow-y-auto rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-950">
            <ul className="space-y-2">
              {filingEvents.map((event, index) => (
                <li
                  key={index}
                  className={`flex items-start gap-2 text-sm ${EVENT_CLASSES[event.type]}`}
                >
                  <EventIcon type={event.type} />
                  <span>{formatEventText(event)}</span>
                </li>
              ))}
            </ul>
            {/* Scroll anchor — auto-scrolls to show new events. */}
            <div ref={scrollRef} />
          </div>
        </div>
      )}

      {/* ---- Cancel button ---- */}
      {canCancel && (
        <div className="flex justify-end">
          <Button
            variant="destructive"
            size="sm"
            onClick={() => setShowCancelModal(true)}
          >
            Cancel Ingestion
          </Button>
        </div>
      )}

      {/* ---- Cancel confirmation modal ---- */}
      <Modal
        open={showCancelModal}
        onClose={() => setShowCancelModal(false)}
        onConfirm={() => {
          setShowCancelModal(false);
          onCancel();
        }}
        title="Cancel Ingestion?"
        confirmLabel="Cancel Ingestion"
        confirmVariant="destructive"
      >
        <p className="text-sm text-gray-600 dark:text-gray-400">
          The current filing will finish processing, but no new filings will
          start. Already-ingested filings will remain in the database.
        </p>
      </Modal>
    </div>
  );
}