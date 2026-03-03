/**
 * Displays a single search result: rank, similarity, metadata,
 * section path, and expandable content with a copy button.
 *
 * ## Why expandable content?
 *
 * SEC filing chunks can be 500+ tokens. Showing all that text for
 * every result would make the page a wall of text. Instead, we
 * show a 300-character preview (matching the CLI's truncation) and
 * a "Show more" toggle. This keeps the results scannable while
 * giving access to full content.
 *
 * ## The `useToast` integration
 *
 * The copy button uses the Clipboard API (`navigator.clipboard`)
 * to copy the full chunk text to the clipboard. Since clipboard
 * access is async and can fail (e.g. if the page isn't focused),
 * we show a toast notification for success or failure feedback.
 *
 * ## Content type badge
 *
 * The API returns `content_type` as "text", "textsmall", or "table".
 * Tables are stored as pipe-delimited text — they look different
 * from prose. Showing a badge helps the user understand why a
 * result might look like raw data rather than a readable paragraph.
 */

"use client";

import { useState } from "react";
import {
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  FileText,
  Calendar,
  Hash,
} from "lucide-react";
import { SimilarityBadge, Badge, useToast } from "@/components/ui";
import type { SearchResult } from "@/lib/types";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Maximum characters to show before truncating. Matches CLI behaviour. */
const PREVIEW_LENGTH = 300;

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ResultCardProps {
  result: SearchResult;
  /** 1-based rank in the results list. */
  rank: number;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ResultCard({ result, rank }: ResultCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [justCopied, setJustCopied] = useState(false);
  const { addToast } = useToast();

  const needsTruncation = result.content.length > PREVIEW_LENGTH;
  const displayContent =
    isExpanded || !needsTruncation
      ? result.content
      : result.content.slice(0, PREVIEW_LENGTH) + "…";

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(result.content);
      setJustCopied(true);
      addToast("success", "Copied to clipboard");
      setTimeout(() => setJustCopied(false), 2000);
    } catch {
      addToast("error", "Failed to copy — try selecting the text manually");
    }
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-950">
      {/* ---- Header: rank + similarity + metadata ---- */}
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-gray-100 text-xs font-bold text-gray-600 dark:bg-gray-800 dark:text-gray-400">
            {rank}
          </span>
          <SimilarityBadge similarity={result.similarity} />
          <Badge variant="blue">{result.form_type}</Badge>
          {result.content_type === "table" && (
            <Badge variant="amber">Table</Badge>
          )}
        </div>

        {/* Copy button */}
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200"
          title="Copy content to clipboard"
        >
          {justCopied ? (
            <Check className="h-3.5 w-3.5 text-green-600" />
          ) : (
            <Copy className="h-3.5 w-3.5" />
          )}
          {justCopied ? "Copied" : "Copy"}
        </button>
      </div>

      {/* ---- Metadata row ---- */}
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500 dark:text-gray-400">
        <span className="flex items-center gap-1">
          <FileText className="h-3.5 w-3.5" />
          {result.ticker}
        </span>
        {result.filing_date && (
          <span className="flex items-center gap-1">
            <Calendar className="h-3.5 w-3.5" />
            {result.filing_date}
          </span>
        )}
        {result.accession_number && (
          <span className="flex items-center gap-1">
            <Hash className="h-3.5 w-3.5" />
            {result.accession_number}
          </span>
        )}
      </div>

      {/* ---- Section path ---- */}
      {result.path && (
        <p className="mt-2 text-xs font-medium text-gray-600 dark:text-gray-400">
          {result.path}
        </p>
      )}

      {/* ---- Content ---- */}
      <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-gray-800 dark:text-gray-200">
        {displayContent}
      </p>

      {/* ---- Expand / Collapse toggle ---- */}
      {needsTruncation && (
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="mt-2 flex items-center gap-1 rounded text-xs font-medium text-blue-600 hover:text-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500 dark:text-blue-400 dark:hover:text-blue-300"
        >
          {isExpanded ? (
            <>
              <ChevronUp className="h-3.5 w-3.5" />
              Show less
            </>
          ) : (
            <>
              <ChevronDown className="h-3.5 w-3.5" />
              Show more
            </>
          )}
        </button>
      )}
    </div>
  );
}