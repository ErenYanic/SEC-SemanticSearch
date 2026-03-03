/**
 * Search input with a submit button.
 *
 * ## Why `onSubmit` instead of `onChange`?
 *
 * An architectural decision documented in AGENT.md: "Search on submit,
 * not keystroke — prevents excessive API/GPU usage." Each search hits
 * the embedding model on the GPU. Firing on every keystroke would be
 * wasteful and could queue requests that overwhelm the GTX 1650.
 *
 * The component wraps input + button in a `<form>`, so the user can
 * press Enter or click the button. The `onSubmit` prop receives the
 * trimmed query string.
 *
 * ## Controlled vs uncontrolled input
 *
 * We use a **controlled** input (`value` + `onChange`). This lets the
 * parent clear the input programmatically (e.g. on reset) and lets us
 * disable the submit button when the input is empty.
 */

"use client";

import { type FormEvent, type KeyboardEvent } from "react";
import { Search } from "lucide-react";
import { Button, Spinner } from "@/components/ui";

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
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SearchBar({
  query,
  onQueryChange,
  onSubmit,
  isSearching,
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

  return (
    <form onSubmit={handleSubmit} className="flex gap-3">
      <div className="relative flex-1">
        {/* Search icon inside the input field */}
        <Search className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400" />
        <input
          type="text"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Search SEC filings..."
          className="w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-4 text-sm text-gray-900 outline-none transition-colors placeholder:text-gray-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-gray-700 dark:bg-gray-950 dark:text-gray-100 dark:placeholder:text-gray-500 dark:focus:border-blue-400 dark:focus:ring-blue-400/20"
          disabled={isSearching}
        />
      </div>
      <Button type="submit" disabled={!query.trim() || isSearching}>
        {isSearching ? (
          <>
            <Spinner size="sm" className="mr-2" />
            Searching...
          </>
        ) : (
          <>
            <Search className="mr-2 h-4 w-4" />
            Search
          </>
        )}
      </Button>
    </form>
  );
}