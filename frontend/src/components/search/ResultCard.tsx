/**
 * A single search result, rendered as a dense row (not a card).
 *
 * ## Why a row?
 *
 * Analysts scan search results like they scan a data table: eye
 * travels down the left column of identifiers (ticker, date, sim),
 * pauses on a snippet that looks relevant, expands for detail, then
 * continues. Vertical cards waste horizontal space and break that
 * left-column rhythm. A row with fixed gutters (rank/sim on left,
 * actions on right) reads as a Bloomberg-style terminal list.
 *
 * ## Row anatomy
 *
 *   ┌─────┬──────────────────────────────────────────┬────────┐
 *   │ 01  │  AAPL  10-K  2024-09-28  Item 7 · MD&A   │ copy   │
 *   │ 92% │  "Cash and equivalents decreased by…"    │ expand │
 *   │ ▓▓▓ │                                          │        │
 *   └─────┴──────────────────────────────────────────┴────────┘
 *     gutter               main                       actions
 *
 * ## Interaction
 *
 *   - Click anywhere on the row → toggles expansion (set via parent)
 *   - Focus via Tab → selects the row (keyboard nav in ResultList)
 *   - Enter / Space (when focused) → toggles expansion
 *   - Copy button → writes full content to clipboard, toasts result
 *
 * ## State ownership
 *
 * Expansion and selection are controlled by the parent (ResultList)
 * so that keyboard shortcuts (j/k/Enter/c) in the list can drive
 * them uniformly across rows.
 */

"use client";

import { useState, type KeyboardEvent, type Ref } from "react";
import { Copy, Check } from "lucide-react";
import { useToast } from "@/components/ui";
import type { SearchResult } from "@/lib/types";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Maximum characters to show before truncating. */
const PREVIEW_LENGTH = 300;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Map a 0–1 similarity to a {bar-color, label-color} pair.
 *
 * Thresholds match SimilarityBadge:
 *   ≥ 0.40 → strong match (pos/emerald)
 *   ≥ 0.25 → moderate     (warn/amber)
 *   <  0.25 → weak        (neg/red)
 */
function similarityColors(similarity: number): { bar: string; text: string } {
  if (similarity >= 0.4) return { bar: "bg-pos", text: "text-pos" };
  if (similarity >= 0.25) return { bar: "bg-warn", text: "text-warn" };
  return { bar: "bg-neg", text: "text-neg" };
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ResultCardProps {
  result: SearchResult;
  /** 1-based rank in the results list. */
  rank: number;
  /** Currently selected (keyboard-highlighted) row. */
  isSelected?: boolean;
  /** Currently expanded (full content shown). */
  isExpanded?: boolean;
  /** Called when the row is focused/clicked — parent updates selection. */
  onSelect?: () => void;
  /** Called when the user toggles expansion (click row, Enter). */
  onToggleExpand?: () => void;
  /** Ref forwarded to the row element — used by ResultList for j/k focus. */
  ref?: Ref<HTMLDivElement>;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ResultCard({
  result,
  rank,
  isSelected = false,
  isExpanded = false,
  onSelect,
  onToggleExpand,
  ref,
}: ResultCardProps) {
  const { addToast } = useToast();
  const [justCopied, setJustCopied] = useState(false);

  const needsTruncation = result.content.length > PREVIEW_LENGTH;
  const displayContent =
    isExpanded || !needsTruncation
      ? result.content
      : result.content.slice(0, PREVIEW_LENGTH) + "…";

  const percentage = Math.round(result.similarity * 100);
  const colors = similarityColors(result.similarity);

  async function handleCopy(e: React.MouseEvent) {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(result.content);
      setJustCopied(true);
      addToast("success", "Copied to clipboard");
      setTimeout(() => setJustCopied(false), 2000);
    } catch {
      addToast("error", "Failed to copy — try selecting the text manually");
    }
  }

  function handleRowKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    // Enter / Space on the row itself toggles expansion. j/k are
    // handled higher up in ResultList so selection moves between rows.
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onToggleExpand?.();
    }
  }

  return (
    <div
      ref={ref}
      role="button"
      tabIndex={isSelected ? 0 : -1}
      aria-expanded={isExpanded}
      aria-label={`Result ${rank}: ${result.ticker} ${result.form_type}, ${percentage}% similarity`}
      onClick={() => {
        onSelect?.();
        onToggleExpand?.();
      }}
      onFocus={() => onSelect?.()}
      onKeyDown={handleRowKeyDown}
      className={`
        group relative grid cursor-pointer grid-cols-[64px_1fr_auto]
        gap-5 border-b border-hairline px-6 py-5 outline-none
        transition-colors duration-150
        hover:bg-surface/40
        focus-visible:bg-surface/60
        ${isSelected ? "bg-surface/60" : ""}
      `}
    >
      {/* ---- Left gutter: rank + similarity ---- */}
      <div className="flex flex-col items-start gap-1.5">
        <span className="text-xs font-semibold tabular-nums text-fg-subtle">
          {String(rank).padStart(2, "0")}
        </span>
        <span
          className={`text-base font-semibold tabular-nums ${colors.text}`}
        >
          {percentage}%
        </span>
        <div
          className="mt-1 h-1 w-full overflow-hidden rounded-full bg-hairline"
          aria-hidden="true"
        >
          <div
            className={`h-full ${colors.bar}`}
            style={{ width: `${Math.min(100, percentage)}%` }}
          />
        </div>
      </div>

      {/* ---- Main column: metadata + snippet ---- */}
      <div className="min-w-0">
        {/* Metadata row */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-sm text-fg-muted">
          <span className="text-base font-semibold text-fg">{result.ticker}</span>
          <span className="inline-flex items-center rounded-md border border-hairline bg-card px-2 py-0.5 text-xs font-medium text-fg-muted">
            {result.form_type}
          </span>
          {result.filing_date && <span className="tabular-nums">{result.filing_date}</span>}
          {result.accession_number && (
            <span className="text-fg-subtle tabular-nums">{result.accession_number}</span>
          )}
          {result.content_type === "table" && (
            <span className="inline-flex items-center rounded-md border border-warn/40 bg-warn/10 px-2 py-0.5 text-xs font-medium text-warn">
              Table
            </span>
          )}
        </div>

        {/* Section path */}
        {result.path && (
          <p className="mt-1.5 truncate text-sm font-medium text-fg-muted">
            {result.path}
          </p>
        )}

        {/* Snippet */}
        <p
          className={`mt-2 whitespace-pre-wrap text-[15px] leading-relaxed text-fg ${
            isExpanded ? "" : "line-clamp-3"
          }`}
        >
          {displayContent}
        </p>

        {/* Expand hint */}
        {needsTruncation && !isExpanded && (
          <p className="mt-2 text-xs text-fg-subtle">Press Enter to expand</p>
        )}
      </div>

      {/* ---- Right gutter: copy action ---- */}
      <div className="flex flex-col items-end gap-1.5">
        <button
          type="button"
          onClick={handleCopy}
          onKeyDown={(e) => e.stopPropagation()}
          aria-label="Copy content to clipboard"
          title="Copy content"
          className="
            flex h-9 w-9 items-center justify-center rounded-lg
            text-fg-subtle opacity-0 transition-all duration-150
            hover:bg-card hover:text-fg
            focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent
            focus-visible:opacity-100
            group-hover:opacity-100
          "
        >
          {justCopied ? (
            <Check className="h-4 w-4 text-pos" />
          ) : (
            <Copy className="h-4 w-4" />
          )}
        </button>
      </div>
    </div>
  );
}
