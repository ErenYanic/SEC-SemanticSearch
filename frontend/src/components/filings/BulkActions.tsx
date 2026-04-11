/**
 * BulkActions — "Delete Selected" and "Delete All" action bar.
 *
 * Sits in the Filings toolbar row next to the filters. The "Delete
 * Selected" button uses the shared destructive button variant and is
 * disabled when nothing is selected. "Delete All" uses a ghost button
 * with a `neg`-token outline so it reads as destructive but visually
 * subordinate to the primary destructive action.
 *
 * Both buttons trigger callbacks that open the DeleteDialog — they do
 * not perform the deletion themselves.
 */

"use client";

import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface BulkActionsProps {
  /** Number of currently selected filings. */
  selectedCount: number;
  /** Total filings matching the current filters. */
  totalFilings: number;
  /** Called when the user clicks "Delete Selected". */
  onDeleteSelected: () => void;
  /** Called when the user clicks "Delete All". */
  onDeleteAll: () => void;
  /** Disable buttons while a deletion is in progress. */
  isDeleting: boolean;
  /** Whether the current user has admin access. Hides bulk/clear buttons when false. */
  isAdmin: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function BulkActions({
  selectedCount,
  totalFilings,
  onDeleteSelected,
  onDeleteAll,
  isDeleting,
  isAdmin,
}: BulkActionsProps) {
  if (!isAdmin) {
    return null;
  }

  return (
    <div className="flex items-center gap-2">
      {/* Delete Selected — primary destructive */}
      <Button
        variant="destructive"
        size="sm"
        onClick={onDeleteSelected}
        disabled={selectedCount === 0 || isDeleting}
      >
        <Trash2 className="mr-1.5 h-3.5 w-3.5" />
        Delete Selected
        {selectedCount > 0 && (
          <span className="ml-1 font-mono tabular-nums">({selectedCount})</span>
        )}
      </Button>

      {/* Delete All — ghost button with neg-token outline */}
      <Button
        variant="ghost"
        size="sm"
        onClick={onDeleteAll}
        disabled={totalFilings === 0 || isDeleting}
        className="border border-neg/40 text-neg hover:bg-neg/10 hover:text-neg"
      >
        <Trash2 className="mr-1.5 h-3.5 w-3.5" />
        Delete All
      </Button>
    </div>
  );
}
