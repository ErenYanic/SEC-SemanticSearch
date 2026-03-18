/**
 * Post-ingestion summary showing results and statistics.
 *
 * Displayed when a task reaches "completed" or "cancelled" (with
 * partial results).  Shows:
 *
 *   1. Summary cards  — succeeded / skipped / failed counts + duration
 *   2. Results table  — per-filing details (success + skipped + failed)
 *   3. Action button  — "Ingest More Filings" to reset to idle
 *
 * ## Why not MetricCard?
 *
 * `MetricCard` always renders its icon in blue.  Here we need
 * green/amber/red icons per card.  Rather than modifying MetricCard
 * for a single use case, we inline a similar layout with per-card
 * colour control.  This avoids over-engineering the shared component.
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
import { Button, Badge } from "@/components/ui";
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

/** Format a duration in seconds to a human-readable string. */
function formatDuration(startedAt: Date | null, completedAt: Date | null): string {
  if (!startedAt || !completedAt) return "\u2014";
  const seconds = Math.round((completedAt.getTime() - startedAt.getTime()) / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return `${minutes}m ${remaining}s`;
}

// Static class maps for Badge variants per event type.
const EVENT_BADGE_VARIANT: Record<FilingEvent["type"], "green" | "amber" | "red" | "blue"> = {
  done: "green",
  skipped: "amber",
  failed: "red",
  eviction: "blue",
};

const EVENT_BADGE_LABEL: Record<FilingEvent["type"], string> = {
  done: "Success",
  skipped: "Skipped",
  failed: "Failed",
  eviction: "Eviction",
};

// Summary card colour classes — static maps, never interpolated.
const CARD_ICON_BG: Record<string, string> = {
  green: "bg-green-50 dark:bg-green-950",
  amber: "bg-amber-50 dark:bg-amber-950",
  red: "bg-red-50 dark:bg-red-950",
  blue: "bg-blue-50 dark:bg-blue-950",
};

const CARD_ICON_TEXT: Record<string, string> = {
  green: "text-green-600 dark:text-green-400",
  amber: "text-amber-600 dark:text-amber-400",
  red: "text-red-600 dark:text-red-400",
  blue: "text-blue-600 dark:text-blue-400",
};

// ---------------------------------------------------------------------------
// Sub-component
// ---------------------------------------------------------------------------

/** A summary metric card with configurable icon colour. */
function SummaryCard({
  label,
  value,
  icon: Icon,
  colour,
}: {
  label: string;
  value: number | string;
  icon: ElementType;
  colour: "green" | "amber" | "red" | "blue";
}) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-gray-950">
      <div className="flex items-center gap-3">
        <div className={`rounded-md p-2 ${CARD_ICON_BG[colour]}`}>
          <Icon className={`h-5 w-5 ${CARD_ICON_TEXT[colour]}`} />
        </div>
        <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
          {label}
        </span>
      </div>
      <p className="mt-3 text-3xl font-bold text-gray-900 dark:text-gray-100">
        {value}
      </p>
    </div>
  );
}

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

  return (
    <div className="space-y-6">
      {/* ---- Summary cards ---- */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryCard
          label="Succeeded"
          value={summary.succeeded}
          icon={CheckCircle2}
          colour="green"
        />
        <SummaryCard
          label="Skipped"
          value={summary.skipped}
          icon={SkipForward}
          colour="amber"
        />
        <SummaryCard
          label="Failed"
          value={summary.failed}
          icon={XCircle}
          colour="red"
        />
        <SummaryCard
          label="Duration"
          value={duration}
          icon={Clock}
          colour="blue"
        />
      </div>

      {/* ---- Results table ---- */}
      {filingEvents.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-800">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-900">
              <tr>
                <th className="px-4 py-3 font-medium text-gray-700 dark:text-gray-300">
                  Status
                </th>
                <th className="px-4 py-3 font-medium text-gray-700 dark:text-gray-300">
                  Ticker
                </th>
                <th className="px-4 py-3 font-medium text-gray-700 dark:text-gray-300">
                  Form
                </th>
                <th className="px-4 py-3 font-medium text-gray-700 dark:text-gray-300">
                  Date
                </th>
                <th className="px-4 py-3 font-medium text-gray-700 dark:text-gray-300">
                  Segments
                </th>
                <th className="px-4 py-3 font-medium text-gray-700 dark:text-gray-300">
                  Chunks
                </th>
                <th className="px-4 py-3 font-medium text-gray-700 dark:text-gray-300">
                  Time
                </th>
                <th className="px-4 py-3 font-medium text-gray-700 dark:text-gray-300">
                  Detail
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
              {filingEvents.filter((e) => e.type !== "eviction").map((event, index) => (
                <tr
                  key={index}
                  className="bg-white dark:bg-gray-950"
                >
                  <td className="px-4 py-3">
                    <Badge variant={EVENT_BADGE_VARIANT[event.type]}>
                      {EVENT_BADGE_LABEL[event.type]}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">
                    {event.ticker}
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                    {event.form_type}
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                    {event.filing_date ?? "\u2014"}
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                    {event.type === "done" ? event.segments : "\u2014"}
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                    {event.type === "done" ? event.chunks : "\u2014"}
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                    {event.type === "done" ? `${event.time?.toFixed(1)}s` : "\u2014"}
                  </td>
                  <td className="px-4 py-3 text-gray-500 dark:text-gray-400">
                    {event.type === "skipped" && event.reason}
                    {event.type === "failed" && (
                      <span className="text-red-600 dark:text-red-400">
                        {event.error}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ---- Action button ---- */}
      <div className="flex justify-center">
        <Button onClick={onReset}>
          <Upload className="mr-2 h-4 w-4" />
          Ingest More Filings
        </Button>
      </div>
    </div>
  );
}