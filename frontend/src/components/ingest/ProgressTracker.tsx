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
 * show an accent checkmark, the current step pulses, and upcoming steps
 * are muted.
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

type StepState = "completed" | "current" | "upcoming";

const STEP_CIRCLE_CLASSES: Record<StepState, string> = {
  completed: "border-accent/60 bg-accent/15 text-accent",
  current: "border-accent bg-accent text-accent-fg animate-pulse",
  upcoming: "border-hairline bg-card text-fg-subtle",
};

const STEP_LABEL_CLASSES: Record<StepState, string> = {
  completed: "text-accent",
  current: "text-fg",
  upcoming: "text-fg-subtle",
};

const STEP_LINE_CLASSES: Record<"completed" | "upcoming", string> = {
  completed: "bg-accent/60",
  upcoming: "bg-hairline",
};

const EVENT_CLASSES: Record<FilingEvent["type"], string> = {
  done: "text-pos",
  skipped: "text-warn",
  failed: "text-neg",
  eviction: "text-warn",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getStepState(stepIndex: number, currentIndex: number): StepState {
  if (stepIndex < currentIndex) return "completed";
  if (stepIndex === currentIndex) return "current";
  return "upcoming";
}

function EventIcon({ type }: { type: FilingEvent["type"] }) {
  switch (type) {
    case "done":
      return <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />;
    case "skipped":
      return <SkipForward className="h-3.5 w-3.5 shrink-0" />;
    case "failed":
      return <XCircle className="h-3.5 w-3.5 shrink-0" />;
    case "eviction":
      return <Trash2 className="h-3.5 w-3.5 shrink-0" />;
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
  const processed =
    progress.filings_done + progress.filings_skipped + progress.filings_failed;
  const progressPercent = hasTotal
    ? Math.round((processed / progress.filings_total) * 100)
    : 0;

  const statusText =
    progress.current_ticker && progress.current_form_type
      ? `Processing ${progress.current_ticker} ${progress.current_form_type}`
      : "Waiting to start\u2026";

  return (
    <div className="space-y-6 rounded-lg border border-hairline bg-surface p-6">
      {/* ---- Status header ---- */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <Loader2 className="h-4 w-4 animate-spin text-accent" />
          <span className="font-mono text-sm tabular-nums text-fg">
            {statusText}
          </span>
        </div>
        {hasTotal && (
          <span className="font-mono text-[11px] tabular-nums text-fg-muted">
            <span className="text-fg">{progressPercent}%</span>
          </span>
        )}
      </div>

      {/* ---- Overall progress bar ---- */}
      <div className="space-y-2">
        <div className="h-1 w-full overflow-hidden rounded-full bg-card">
          {hasTotal ? (
            <div
              className="h-full rounded-full bg-accent transition-all duration-500"
              style={{ width: `${progressPercent}%` }}
            />
          ) : (
            <div className="h-full w-1/3 animate-pulse rounded-full bg-accent/60" />
          )}
        </div>
        <div className="flex flex-wrap gap-3 font-mono text-[11px] tabular-nums text-fg-muted">
          {hasTotal && (
            <span>
              <span className="text-fg">{processed}</span>
              <span className="text-fg-subtle"> / </span>
              <span className="text-fg">{progress.filings_total}</span>
              <span className="text-fg-subtle"> filings</span>
            </span>
          )}
          {progress.filings_skipped > 0 && (
            <>
              <span className="text-fg-subtle">·</span>
              <span className="text-warn">
                {progress.filings_skipped} skipped
              </span>
            </>
          )}
          {progress.filings_failed > 0 && (
            <>
              <span className="text-fg-subtle">·</span>
              <span className="text-neg">{progress.filings_failed} failed</span>
            </>
          )}
        </div>
      </div>

      {/* ---- Step indicator (horizontal stepper) ---- */}
      <div className="flex items-center justify-between">
        {STEP_LABELS.map((label, index) => {
          const stepState = getStepState(index, progress.step_index);
          return (
            <div key={label} className="flex flex-1 items-center">
              <div className="flex flex-col items-center gap-1.5">
                <div
                  className={`flex h-7 w-7 items-center justify-center rounded-full border font-mono text-[11px] font-semibold tabular-nums ${STEP_CIRCLE_CLASSES[stepState]}`}
                >
                  {stepState === "completed" ? (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  ) : (
                    index + 1
                  )}
                </div>
                <span
                  className={`font-mono text-[10px] font-semibold uppercase tracking-widest ${STEP_LABEL_CLASSES[stepState]}`}
                >
                  {label}
                </span>
              </div>
              {index < STEP_LABELS.length - 1 && (
                <div
                  className={`mx-1 h-px flex-1 ${
                    STEP_LINE_CLASSES[
                      index < progress.step_index ? "completed" : "upcoming"
                    ]
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* ---- Filing event list ---- */}
      {filingEvents.length > 0 && (
        <div className="space-y-2">
          <div className="font-mono text-[10px] font-semibold uppercase tracking-widest text-fg-subtle">
            Event Log
          </div>
          <div className="max-h-64 overflow-y-auto rounded-md border border-hairline bg-card p-3">
            <ul className="space-y-1.5">
              {filingEvents.map((event, index) => (
                <li
                  key={index}
                  className={`flex items-start gap-2 font-mono text-xs tabular-nums ${EVENT_CLASSES[event.type]}`}
                >
                  <EventIcon type={event.type} />
                  <span>{formatEventText(event)}</span>
                </li>
              ))}
            </ul>
            <div ref={scrollRef} />
          </div>
        </div>
      )}

      {/* ---- Cancel button ---- */}
      {canCancel && (
        <div className="flex justify-end border-t border-hairline pt-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowCancelModal(true)}
            className="border border-neg/40 text-neg hover:bg-neg/10 hover:text-neg"
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
        <p className="text-sm text-fg-muted">
          The current filing will finish processing, but no new filings will
          start. Already-ingested filings will remain in the database.
        </p>
      </Modal>
    </div>
  );
}
