"use client";

/**
 * Confirmation dialog — a focused modal for destructive or important
 * actions (delete filing, clear all, bulk delete).
 *
 * `"use client"` is required because we use:
 *   - `useEffect` for focus trapping, Escape key handling, and scroll lock
 *   - `useSyncExternalStore` for an SSR-safe mount guard (`createPortal`
 *     needs `document.body`, which doesn't exist during server rendering)
 *   - `createPortal` to render above all other content via `document.body`
 *
 * ## Accessibility
 *
 * - `role="dialog"` + `aria-modal="true"` announce the dialog.
 * - `aria-labelledby` connects the dialog to its title element.
 * - Focus is trapped between the Cancel and Confirm buttons.
 * - Escape key dismisses the modal.
 * - Background scroll is locked while the modal is open.
 * - Clicking the backdrop (the dark overlay) dismisses the modal.
 */

import { useEffect, useId, useRef, useSyncExternalStore, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Button } from "./Button";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface ModalProps {
  /** Whether the modal is visible. */
  open: boolean;
  /** Called when the user requests closing (Escape, backdrop, Cancel). */
  onClose: () => void;
  /** Called when the user clicks the confirm button. */
  onConfirm: () => void;
  /** Modal title displayed at the top. */
  title: string;
  /** Modal body content — usually a description of what will happen. */
  children: ReactNode;
  /** Label for the confirm button. Defaults to `"Confirm"`. */
  confirmLabel?: string;
  /** Variant for the confirm button. Defaults to `"primary"`. */
  confirmVariant?: "primary" | "destructive";
  /** Disable the confirm button (e.g. while waiting for a response). */
  confirmDisabled?: boolean;
  /** Show a loading spinner on the confirm button. */
  confirmLoading?: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function Modal({
  open,
  onClose,
  onConfirm,
  title,
  children,
  confirmLabel = "Confirm",
  confirmVariant = "primary",
  confirmDisabled = false,
  confirmLoading = false,
}: ModalProps) {
  // ---- SSR guard ----
  // `createPortal` needs `document.body`, which doesn't exist during
  // server-side rendering.  `useSyncExternalStore` is the React 19
  // pattern for values that differ between server and client — the
  // same approach used in ThemeProvider.tsx.  No state, no effect,
  // no cascading render.
  const mounted = useSyncExternalStore(
    () => () => {},     // subscribe: no-op (value never changes)
    () => true,         // getSnapshot: client is mounted
    () => false,        // getServerSnapshot: server has no DOM
  );

  // ---- Unique ID for aria-labelledby ----
  // `useId()` generates a stable, SSR-safe ID.  We use it to connect
  // the dialog's `aria-labelledby` to the title element so screen
  // readers announce the title when the modal opens.
  const titleId = useId();

  // ---- Refs for focus management ----
  const cancelRef = useRef<HTMLButtonElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);

  // ---- Escape key + scroll lock + initial focus ----
  useEffect(() => {
    if (!open) return;

    // Lock background scroll by hiding overflow on <body>.
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    // Move focus to the Cancel button when the modal opens.
    // Cancel is focused first (not Confirm) as a safety measure —
    // the non-destructive action should be the default focus target.
    cancelRef.current?.focus();

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }

      // ---- Focus trap ----
      // Tab and Shift+Tab cycle between Cancel and Confirm.
      // This prevents keyboard users from tabbing to elements
      // behind the modal overlay.
      if (e.key === "Tab") {
        e.preventDefault();
        if (document.activeElement === cancelRef.current) {
          confirmRef.current?.focus();
        } else {
          cancelRef.current?.focus();
        }
      }
    }

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = originalOverflow;
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, onClose]);

  // Don't render anything when closed or before client-side mount.
  if (!mounted || !open) return null;

  return createPortal(
    // ---- Backdrop ----
    // `fixed inset-0` covers the entire viewport.
    // `z-50` ensures the modal sits above all other content.
    // Clicking the backdrop (but not the dialog itself) closes the modal.
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 dark:bg-black/70"
      onClick={onClose}
      aria-hidden="true"
    >
      {/* ---- Dialog ---- */}
      {/* `onClick={e => e.stopPropagation()}` prevents clicks inside   */}
      {/* the dialog from bubbling up to the backdrop's onClick handler. */}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="relative mx-4 w-full max-w-md rounded-lg bg-white p-6 shadow-xl dark:bg-gray-900"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Title */}
        <h2
          id={titleId}
          className="text-lg font-semibold text-gray-900 dark:text-gray-100"
        >
          {title}
        </h2>

        {/* Body */}
        <div className="mt-3 text-sm text-gray-600 dark:text-gray-400">
          {children}
        </div>

        {/* Actions */}
        <div className="mt-6 flex justify-end gap-3">
          <Button
            ref={cancelRef}
            variant="secondary"
            onClick={onClose}
          >
            Cancel
          </Button>
          <Button
            ref={confirmRef}
            variant={confirmVariant}
            onClick={onConfirm}
            disabled={confirmDisabled}
            loading={confirmLoading}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}