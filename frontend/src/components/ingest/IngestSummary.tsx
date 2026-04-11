/**
 * Post-ingestion summary showing results and statistics.
 *
 * Displayed when a task reaches "completed" or "cancelled" (with
 * partial results).  Shows:
 *
 *   1. Summary cards  — succeeded / skipped / failed counts + duration
 *   2. Results table  — blotter-style per-filing details
 *   3. Action button  — "Ingest More Filings" to reset to idle
 */

"use client";

import { type ElementType } from "react";
import {
  CheckCircle2,
  SkipForward,
  XCircle,
  Clock,
  Upload,
} from "lucide-react";
import { Button } from "@/components/ui";
import type { WsFilingResult } from "@/lib/types";
import type { FilingEvent } from "@/hooks/useIngest";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface IngestSummaryProps {
  /** Successfully ingested filing results. */
  results: WsFilingResult[];
  /** Summary counts from the completed message. */
  summary: {
    total: number;
    succeeded: number;
    skipped: number;
    failed: number;
  };
  /** All filing events in chronological order (includes skipped/failed). */
  filingEvents: FilingEvent[];
  /** Wall-clock start time. */
  startedAt: Date | null;
  /** Wall-clock end time. */
  completedAt: Date | null;
  /** Called when the user wants to start a new ingestion. */
  onReset: () => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDuration(
  startedAt: Date | null,
  completedAt: Date | null,
): string {
  if (!startedAt || !completedAt) return "\u2014";
  const seconds = Math.round(
    (completedAt.getTime() - startedAt.getTime()) / 1000,
  );
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return `${minutes}m ${remaining}s`;
}

type Tone = "pos" | "warn" | "neg" | "accent";

const TONE_ICON_CLASS: Record<Tone, string> = {
  pos: "text-pos",
  warn: "text-warn",
  neg: "text-neg",
  accent: "text-accent",
};

const STATUS_CHIP_CLASS: Record<FilingEvent["type"], string> = {
  done: "border-pos/40 bg-pos/10 text-pos",
  skipped: "border-warn/40 bg-warn/10 text-warn",
  failed: "border-neg/40 bg-neg/10 text-neg",
  eviction: "border-hairline bg-surface text-fg-muted",
};

const STATUS_CHIP_LABEL: Record<FilingEvent["type"], string> = {
  done: "Ok",
  skipped: "Skip",
  failed: "Fail",
  eviction: "Evict",
};

// ---------------------------------------------------------------------------
// Sub-component
// ---------------------------------------------------------------------------

const TONE_BADGE_CLASS: Record<Tone, string> = {
  pos: "bg-pos/10 text-pos",
  warn: "bg-warn/10 text-warn",
  neg: "bg-neg/10 text-neg",
  accent: "bg-accent/10 text-accent",
};

function SummaryCard({
  label,
  value,
  icon: Icon,
  tone,
}: {
  label: string;
  value: number | string;
  icon: ElementType;
  tone: Tone;
}) {
  return (
    <div className="group relative overflow-hidden rounded-2xl border border-hairline bg-card/80 p-6 shadow-sm backdrop-blur-sm transition-all hover:-translate-y-0.5 hover:border-accent/40 hover:shadow-lg hover:shadow-accent/5">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-fg-muted">{label}</span>
        <span
          className={`flex h-9 w-9 items-center justify-center rounded-lg ${TONE_BADGE_CLASS[tone]}`}
        >
          <Icon className={`h-4 w-4 ${TONE_ICON_CLASS[tone]}`} aria-hidden="true" />
        </span>
      </div>
      <p className="mt-4 text-4xl font-semibold tracking-tight tabular-nums text-fg">
        {value}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Constants (shared with FilingTable blotter)
// ---------------------------------------------------------------------------

const HEADER_CELL =
  "px-5 py-3.5 text-xs font-semibold uppercase tracking-wider text-fg-subtle";
const BODY_CELL = "px-5 py-3.5 text-sm";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function IngestSummary({
  summary,
  filingEvents,
  startedAt,
  completedAt,
  onReset,
}: IngestSummaryProps) {
  const duration = formatDuration(startedAt, completedAt);
  const rows = filingEvents.filter((e) => e.type !== "eviction");

  return (
    <div className="space-y-6">
      {/* ---- Summary cards ---- */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryCard
          label="Succeeded"
          value={summary.succeeded}
          icon={CheckCircle2}
          tone="pos"
        />
        <SummaryCard
          label="Skipped"
          value={summary.skipped}
          icon={SkipForward}
          tone="warn"
        />
        <SummaryCard
          label="Failed"
          value={summary.failed}
          icon={XCircle}
          tone="neg"
        />
        <SummaryCard
          label="Duration"
          value={duration}
          icon={Clock}
          tone="accent"
        />
      </div>

      {/* ---- Results table ---- */}
      {rows.length > 0 && (
        <div className="overflow-x-auto rounded-2xl border border-hairline bg-card/80 shadow-sm backdrop-blur-sm">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-hairline bg-surface/40">
                <th className={HEADER_CELL}>Status</th>
                <th className={HEADER_CELL}>Ticker</th>
                <th className={HEADER_CELL}>Form</th>
                <th className={HEADER_CELL}>Date</th>
                <th className={`${HEADER_CELL} text-right`}>Segments</th>
                <th className={`${HEADER_CELL} text-right`}>Chunks</th>
                <th className={`${HEADER_CELL} text-right`}>Time</th>
                <th className={HEADER_CELL}>Detail</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((event, index) => (
                <tr
                  key={index}
                  className="border-b border-hairline/70 transition-colors last:border-b-0 hover:bg-surface/70"
                >
                  <td className={BODY_CELL}>
                    <span
                      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold tabular-nums ${STATUS_CHIP_CLASS[event.type]}`}
                    >
                      {STATUS_CHIP_LABEL[event.type]}
                    </span>
                  </td>
                  <td
                    className={`${BODY_CELL} font-semibold tabular-nums text-fg`}
                  >
                    {event.ticker}
                  </td>
                  <td className={BODY_CELL}>
                    <span className="inline-flex items-center rounded-md border border-hairline bg-surface px-2 py-0.5 text-xs font-medium tabular-nums text-fg-muted">
                      {event.form_type}
                    </span>
                  </td>
                  <td
                    className={`${BODY_CELL} tabular-nums text-fg-muted`}
                  >
                    {event.filing_date ?? "\u2014"}
                  </td>
                  <td
                    className={`${BODY_CELL} text-right tabular-nums text-fg-muted`}
                  >
                    {event.type === "done" ? event.segments : "\u2014"}
                  </td>
                  <td
                    className={`${BODY_CELL} text-right tabular-nums text-fg-muted`}
                  >
                    {event.type === "done" ? event.chunks : "\u2014"}
                  </td>
                  <td
                    className={`${BODY_CELL} text-right tabular-nums text-fg-muted`}
                  >
                    {event.type === "done"
                      ? `${event.time?.toFixed(1)}s`
                      : "\u2014"}
                  </td>
                  <td
                    className={`${BODY_CELL} text-xs tabular-nums text-fg-subtle`}
                  >
                    {event.type === "skipped" && event.reason}
                    {event.type === "failed" && (
                      <span className="text-neg">{event.error}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ---- Action button ---- */}
      <div className="flex justify-end">
        <Button size="lg" onClick={onReset}>
          <Upload className="mr-2 h-4 w-4" />
          Ingest More Filings
        </Button>
      </div>
    </div>
  );
}
