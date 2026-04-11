/**
 * Renders the search results list with a summary header,
 * keyboard navigation, and an empty state when there are no results.
 *
 * ## Keyboard navigation
 *
 * When the user focuses any row (or the first row after results
 * arrive), they can navigate with:
 *
 *   - `j` / `↓`     — next row
 *   - `k` / `↑`     — previous row
 *   - `Enter` / `Space` — toggle expansion of the selected row
 *   - `c`           — copy the selected row's content to the clipboard
 *
 * This matches the keyboard bible of terminal-style apps (mutt, less,
 * Gmail). Mouse users still get click-to-expand; keyboard shortcuts
 * are an additive power-user feature, not a requirement.
 *
 * ## Why selection state lives here
 *
 * The list owns `selectedIndex` and `expanded: Set<number>`:
 *
 *   - `selectedIndex`: drives which row is highlighted and focused
 *   - `expanded`:     drives which rows show full content
 *
 * Both are kept here (not in each ResultCard) so keyboard shortcuts
 * can toggle them uniformly across rows without component gymnastics.
 *
 * ## The summary header
 *
 * Shows "{n} results · {ms}ms · sim ≥ {threshold}" in monospace —
 * echoes query scale, performance, and the active relevance floor.
 *
 * The query text comes from the page's local state, not from the
 * API response — the search endpoint intentionally omits the query
 * to avoid echoing sensitive input over the wire (see §F4).
 */

"use client";

import {
  useCallback,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { SearchX } from "lucide-react";
import { EmptyState, useToast } from "@/components/ui";
import { ResultCard } from "./ResultCard";
import type { SearchResponse } from "@/lib/types";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ResultListProps {
  response: SearchResponse;
  query: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ResultList({ response, query }: ResultListProps) {
  const { addToast } = useToast();
  const results = response.results;

  // -------------------------------------------------------------------
  // Selection + expansion state
  //
  // We reset selection and expansion whenever a new response arrives.
  // React's documented pattern for "adjust state when a prop changes"
  // is a render-time identity compare, NOT a useEffect — the effect
  // version triggers an extra render and is flagged by the
  // react-hooks/set-state-in-effect rule.
  // -------------------------------------------------------------------
  const [prevResponse, setPrevResponse] = useState(response);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [expanded, setExpanded] = useState<Set<number>>(() => new Set());

  if (prevResponse !== response) {
    setPrevResponse(response);
    setSelectedIndex(0);
    setExpanded(new Set());
  }

  // Refs for focusing rows on keyboard navigation
  const rowRefs = useRef<(HTMLDivElement | null)[]>([]);

  const toggleExpand = useCallback((i: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  }, []);

  // -------------------------------------------------------------------
  // Keyboard handler (bound to the list container)
  // -------------------------------------------------------------------
  function handleKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (results.length === 0) return;

    // Don't hijack keys while typing in an input (e.g. if a row ever
    // contains a form control) — let the browser handle it.
    const target = e.target as HTMLElement;
    if (target.tagName === "INPUT" || target.tagName === "TEXTAREA") return;

    switch (e.key) {
      case "j":
      case "ArrowDown": {
        e.preventDefault();
        const next = Math.min(selectedIndex + 1, results.length - 1);
        setSelectedIndex(next);
        rowRefs.current[next]?.focus();
        break;
      }
      case "k":
      case "ArrowUp": {
        e.preventDefault();
        const next = Math.max(selectedIndex - 1, 0);
        setSelectedIndex(next);
        rowRefs.current[next]?.focus();
        break;
      }
      case "c": {
        // Only trigger if no modifier — let Ctrl/Cmd+C copy text selection
        if (e.ctrlKey || e.metaKey || e.altKey) return;
        e.preventDefault();
        const result = results[selectedIndex];
        if (!result) return;
        navigator.clipboard
          .writeText(result.content)
          .then(() => addToast("success", "Copied to clipboard"))
          .catch(() =>
            addToast("error", "Failed to copy — try selecting the text manually"),
          );
        break;
      }
      // Enter / Space on the row are handled inside ResultCard since
      // the row element is the focus target.
    }
  }

  // -------------------------------------------------------------------
  // Empty state
  // -------------------------------------------------------------------
  if (results.length === 0) {
    return (
      <EmptyState
        icon={SearchX}
        title="No results found"
        description="Try broadening your query, removing filters, or lowering the similarity threshold."
      />
    );
  }

  // -------------------------------------------------------------------
  // Results render
  // -------------------------------------------------------------------
  return (
    <div
      role="region"
      aria-label="Search results"
      onKeyDown={handleKeyDown}
      className="rounded-lg border border-hairline bg-surface"
    >
      {/* ---- Meta header ---- */}
      <header className="flex flex-wrap items-baseline justify-between gap-3 border-b border-hairline px-4 py-2.5">
        <div className="flex items-baseline gap-2 font-mono text-[11px] tabular-nums text-fg-muted">
          <span className="font-semibold text-fg">
            {response.total_results}
          </span>
          <span>result{response.total_results !== 1 && "s"}</span>
          <Separator />
          <span className="font-semibold text-fg">
            {response.search_time_ms.toFixed(0)}
          </span>
          <span>ms</span>
          <span className="hidden sm:inline">
            <Separator />
            for &ldquo;<span className="text-fg">{query}</span>&rdquo;
          </span>
        </div>
        <div
          className="hidden items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-fg-subtle md:flex"
          aria-hidden="true"
        >
          <KbdHint>j</KbdHint>
          <KbdHint>k</KbdHint>
          <span>navigate</span>
          <KbdHint>⏎</KbdHint>
          <span>expand</span>
          <KbdHint>c</KbdHint>
          <span>copy</span>
        </div>
      </header>

      {/* ---- Rows ---- */}
      <div>
        {results.map((result, index) => (
          <ResultCard
            key={result.chunk_id ?? index}
            ref={(el) => {
              rowRefs.current[index] = el;
            }}
            result={result}
            rank={index + 1}
            isSelected={index === selectedIndex}
            isExpanded={expanded.has(index)}
            onSelect={() => setSelectedIndex(index)}
            onToggleExpand={() => toggleExpand(index)}
          />
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tiny presentational helpers
// ---------------------------------------------------------------------------

function Separator() {
  return <span className="text-fg-subtle">·</span>;
}

function KbdHint({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="rounded border border-hairline bg-card px-1 py-0.5 font-mono text-[9px] text-fg-muted">
      {children}
    </kbd>
  );
}
