/**
 * Placeholder for empty views — shown when there is no data to
 * display (no filings, no search results, no active tasks).
 *
 * ## Composition pattern
 *
 * The `action` prop accepts any `ReactNode` rather than a callback.
 * This lets the caller decide what the action should be — a Button,
 * a Link, or nothing — without EmptyState needing to know.
 *
 * ```tsx
 * // Dashboard — link to Ingest page
 * <EmptyState
 *   icon={Database}
 *   title="No filings yet"
 *   description="Ingest SEC filings to get started."
 *   action={<Link href="/ingest"><Button>Ingest Filings</Button></Link>}
 * />
 *
 * // Search — button to clear filters
 * <EmptyState
 *   icon={Search}
 *   title="No results found"
 *   action={<Button variant="secondary" onClick={clearFilters}>Clear Filters</Button>}
 * />
 * ```
 *
 * No `"use client"` needed — pure presentational component.
 */

import { type ElementType, type ReactNode } from "react";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface EmptyStateProps {
  /** Lucide icon component to display. */
  icon: ElementType;
  /** Primary message (e.g. "No filings yet"). */
  title: string;
  /** Optional secondary description. */
  description?: string;
  /** Optional action element (Button, Link, or any ReactNode). */
  action?: ReactNode;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      {/* ---- Icon in a muted circle ---- */}
      <div className="rounded-full bg-gray-100 p-4 dark:bg-gray-800">
        <Icon className="h-8 w-8 text-gray-400 dark:text-gray-500" />
      </div>

      {/* ---- Title ---- */}
      <h3 className="mt-4 text-lg font-semibold text-gray-900 dark:text-gray-100">
        {title}
      </h3>

      {/* ---- Description (optional) ---- */}
      {description && (
        <p className="mt-2 max-w-sm text-sm text-gray-600 dark:text-gray-400">
          {description}
        </p>
      )}

      {/* ---- Action (optional) ---- */}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}