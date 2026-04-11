/**
 * Search input — the primary entry point for semantic queries.
 *
 * ## Why `onSubmit` instead of `onChange`?
 *
 * Documented in AGENT.md: "Search on submit, not keystroke — prevents
 * excessive API/GPU usage." Each search hits the embedding model on
 * the GPU. Firing on every keystroke would be wasteful and could
 * queue requests that overwhelm the GTX 1650.
 *
 * ## Integrated submit
 *
 * The button lives inside the input's relative container (absolute
 * right) rather than as a sibling. This reads as "one control" and
 * matches the institutional-terminal aesthetic — fewer visual breaks.
 * Users still submit with Enter (form onSubmit) or click.
 *
 * ## Keyboard hints
 *
 * Small `<kbd>` chips inside the field remind users of Enter/Esc.
 * They're decorative (aria-hidden) — the behaviour is real but
 * communicated through native form semantics for screen readers.
 */

"use client";

import { type FormEvent, type KeyboardEvent } from "react";
import { ArrowRight, Search } from "lucide-react";
import { Spinner } from "@/components/ui";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface SearchBarProps {
  /** Current query text (controlled). */
  query: string;
  /** Called when the user types. */
  onQueryChange: (query: string) => void;
  /** Called when the user submits (Enter or button click). */
  onSubmit: (query: string) => void;
  /** True while a search request is in-flight. */
  isSearching: boolean;
  /**
   * Optional total chunk count shown in the placeholder. When provided,
   * the placeholder becomes e.g. "Search 892,143 chunks across 12,483
   * filings…" — instant communication of corpus scale.
   */
  chunkCount?: number;
  /** Optional filing count for the placeholder hint. */
  filingCount?: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatPlaceholder(chunks?: number, filings?: number): string {
  if (typeof chunks === "number" && typeof filings === "number") {
    return `Search ${chunks.toLocaleString()} chunks across ${filings.toLocaleString()} filings…`;
  }
  return "Search SEC filings — ask anything about 10-K, 10-Q, 8-K…";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SearchBar({
  query,
  onQueryChange,
  onSubmit,
  isSearching,
  chunkCount,
  filingCount,
}: SearchBarProps) {
  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = query.trim();
    if (trimmed) {
      onSubmit(trimmed);
    }
  }

  /** Escape clears the input and blurs — standard text field shortcut. */
  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Escape") {
      onQueryChange("");
      (e.target as HTMLInputElement).blur();
    }
  }

  const canSubmit = !!query.trim() && !isSearching;

  return (
    <form onSubmit={handleSubmit} className="relative">
      {/* Leading search icon */}
      <Search
        className="pointer-events-none absolute left-5 top-1/2 h-5 w-5 -translate-y-1/2 text-fg-subtle"
        aria-hidden="true"
      />

      <input
        type="text"
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={formatPlaceholder(chunkCount, filingCount)}
        aria-label="Search SEC filings"
        disabled={isSearching}
        className="
          h-16 w-full rounded-2xl border border-hairline bg-card/80 pl-14 pr-44
          text-base text-fg outline-none backdrop-blur-sm shadow-sm
          placeholder:text-fg-subtle
          transition-all duration-150
          focus:border-accent focus:ring-4 focus:ring-accent/15 focus:shadow-lg focus:shadow-accent/10
          disabled:cursor-not-allowed disabled:opacity-60
        "
      />

      {/* Trailing kbd hints (hidden while input is empty or mid-search) */}
      <div
        className="pointer-events-none absolute right-28 top-1/2 hidden -translate-y-1/2 items-center gap-1.5 md:flex"
        aria-hidden="true"
      >
        {query.trim() && !isSearching && (
          <Kbd>⏎</Kbd>
        )}
        {query && !isSearching && <Kbd>ESC</Kbd>}
      </div>

      {/* Integrated submit button */}
      <button
        type="submit"
        disabled={!canSubmit}
        aria-label="Submit search"
        className="
          absolute right-2.5 top-1/2 flex h-11 -translate-y-1/2 items-center
          gap-2 rounded-xl bg-accent px-5 text-sm font-medium
          text-accent-fg shadow-sm shadow-accent/20
          transition-all duration-150
          hover:brightness-110 hover:shadow-md hover:shadow-accent/30
          focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent
          disabled:cursor-not-allowed disabled:opacity-50
        "
      >
        {isSearching ? (
          <>
            <Spinner size="sm" />
            <span>Searching</span>
          </>
        ) : (
          <>
            <span>Search</span>
            <ArrowRight className="h-4 w-4" />
          </>
        )}
      </button>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Sub-component: Kbd
// ---------------------------------------------------------------------------

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="rounded-md border border-hairline bg-surface px-2 py-1 font-mono text-xs font-medium text-fg-muted">
      {children}
    </kbd>
  );
}
