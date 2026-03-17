/**
 * BulkActions — "Delete Selected" and "Delete All" action bar.
 *
 * Sits between the filters and the table. The "Delete Selected" button
 * is filled red (existing `variant="destructive"`) and disabled when
 * nothing is selected. The "Delete All" button uses a red outline style
 * via className override on a ghost button — avoids modifying the shared
 * Button component for a single use case.
 *
 * Both buttons trigger callbacks that open the DeleteDialog (they don't
 * perform the deletion directly).
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
    <div className="flex items-center gap-3">
      {/* Delete Selected — filled red, disabled when nothing selected */}
      <Button
        variant="destructive"
        size="sm"
        onClick={onDeleteSelected}
        disabled={selectedCount === 0 || isDeleting}
      >
        <Trash2 className="mr-1.5 h-3.5 w-3.5" />
        Delete Selected{selectedCount > 0 ? ` (${selectedCount})` : ""}
      </Button>

      {/* Delete All — red outline style via className on ghost button */}
      <Button
        variant="ghost"
        size="sm"
        onClick={onDeleteAll}
        disabled={totalFilings === 0 || isDeleting}
        className="border border-red-300 text-red-600 hover:bg-red-50 hover:text-red-700 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-950 dark:hover:text-red-300"
      >
        <Trash2 className="mr-1.5 h-3.5 w-3.5" />
        Delete All
      </Button>
    </div>
  );
}