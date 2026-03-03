/**
 * DeleteDialog — shared confirmation modal for all filing delete operations.
 *
 * Uses a discriminated union (`DeleteTarget`) to render different content
 * depending on what the user is deleting: a single filing, a set of
 * selected filings, or the entire database.
 *
 * The component wraps the shared `Modal` from `ui/` and always uses
 * `confirmVariant="destructive"` (red confirm button) since all actions
 * are irreversible data deletions.
 *
 * ## Usage
 *
 * The page component controls the dialog by setting `target`:
 *   - `{ kind: "single", filing }` → "Delete AAPL 10-K?"
 *   - `{ kind: "selected", count, totalChunks }` → "Delete 3 selected?"
 *   - `{ kind: "all", count }` → "Delete ALL 15 filings?"
 *   - `null` → dialog is closed
 */

"use client";

import type { Filing } from "@/lib/types";
import { Modal } from "@/components/ui";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/**
 * Discriminated union describing what the user wants to delete.
 *
 * TypeScript narrows the type based on `kind`, so inside a
 * `kind === "single"` branch you can safely access `target.filing`.
 */
export type DeleteTarget =
  | { kind: "single"; filing: Filing }
  | { kind: "selected"; count: number; totalChunks: number }
  | { kind: "all"; count: number };

interface DeleteDialogProps {
  /** What to delete. `null` means the dialog is closed. */
  target: DeleteTarget | null;
  /** Called when the user cancels or clicks the backdrop. */
  onClose: () => void;
  /** Called when the user confirms the deletion. */
  onConfirm: () => void;
  /** True while the delete operation is in progress. */
  isDeleting: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getTitle(target: DeleteTarget): string {
  switch (target.kind) {
    case "single":
      return "Delete Filing";
    case "selected":
      return "Delete Selected Filings";
    case "all":
      return "Delete All Filings";
  }
}

function getConfirmLabel(target: DeleteTarget): string {
  switch (target.kind) {
    case "single":
      return "Delete";
    case "selected":
      return `Delete ${target.count} Filing${target.count === 1 ? "" : "s"}`;
    case "all":
      return "Delete All";
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DeleteDialog({
  target,
  onClose,
  onConfirm,
  isDeleting,
}: DeleteDialogProps) {
  if (!target) return null;

  return (
    <Modal
      open
      onClose={onClose}
      onConfirm={onConfirm}
      title={getTitle(target)}
      confirmLabel={getConfirmLabel(target)}
      confirmVariant="destructive"
      confirmLoading={isDeleting}
      confirmDisabled={isDeleting}
    >
      <div className="text-sm text-gray-600 dark:text-gray-400">
        {target.kind === "single" && (
          <p>
            Delete{" "}
            <span className="font-semibold text-gray-900 dark:text-gray-100">
              {target.filing.ticker} {target.filing.form_type}
            </span>{" "}
            (filed {target.filing.filing_date})? This will remove{" "}
            {target.filing.chunk_count.toLocaleString()} chunk
            {target.filing.chunk_count === 1 ? "" : "s"} from the database.
          </p>
        )}

        {target.kind === "selected" && (
          <>
            <p>
              Delete{" "}
              <span className="font-semibold text-gray-900 dark:text-gray-100">
                {target.count} selected filing
                {target.count === 1 ? "" : "s"}
              </span>
              ? This will remove approximately{" "}
              {target.totalChunks.toLocaleString()} chunks.
            </p>
            <p className="mt-2 text-red-600 dark:text-red-400">
              This action cannot be undone.
            </p>
          </>
        )}

        {target.kind === "all" && (
          <>
            <p>
              Delete{" "}
              <span className="font-semibold text-gray-900 dark:text-gray-100">
                all {target.count} filing{target.count === 1 ? "" : "s"}
              </span>
              ? This will clear the entire database.
            </p>
            <p className="mt-2 text-red-600 dark:text-red-400">
              This action cannot be undone.
            </p>
          </>
        )}
      </div>
    </Modal>
  );
}