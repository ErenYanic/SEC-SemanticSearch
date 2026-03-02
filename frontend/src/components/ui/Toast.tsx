"use client";

/**
 * Global toast notification system — three co-located pieces:
 *
 *   1. **`ToastProvider`** — context provider that holds the toast
 *      queue and exposes `addToast`.  Wraps the app in `Providers.tsx`.
 *
 *   2. **`useToast()`** — hook returning `{ addToast }` for any
 *      component to trigger a notification.
 *
 *   3. **`ToastContainer`** (internal) — renders visible toasts via
 *      `createPortal` at the bottom-right of the viewport.
 *
 * ## Why these three live in one file
 *
 * They are tightly coupled — the provider creates the state, the
 * hook reads it, and the container renders it.  Importing them
 * independently would be a mistake, so co-location prevents that.
 *
 * ## Usage
 *
 * ```tsx
 * // In any client component:
 * import { useToast } from "@/components/ui";
 *
 * function DeleteButton() {
 *   const { addToast } = useToast();
 *
 *   async function handleDelete() {
 *     await deleteFiling(accession);
 *     addToast("success", "Filing deleted successfully");
 *   }
 *
 *   return <Button onClick={handleDelete}>Delete</Button>;
 * }
 * ```
 *
 * `"use client"` is required because we use useState, useEffect,
 * useCallback, useContext, and createPortal.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { CheckCircle, XCircle, Info, X } from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Toast colour variants — maps to icon + colour scheme. */
type ToastVariant = "success" | "error" | "info";

/** Internal toast representation. */
interface Toast {
  /** Unique ID for React keys and removal. */
  id: string;
  /** Visual variant. */
  variant: ToastVariant;
  /** The notification message. */
  message: string;
}

/** The shape of the context value. */
interface ToastContextValue {
  /**
   * Show a toast notification.
   *
   * @param variant - "success" | "error" | "info"
   * @param message - The text to display
   */
  addToast: (variant: ToastVariant, message: string) => void;
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

/**
 * The context is created with `null` as the default value.  This
 * means calling `useToast()` outside of a `ToastProvider` will throw
 * a helpful error (see the hook below) rather than silently returning
 * undefined values.
 */
const ToastContext = createContext<ToastContextValue | null>(null);

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** How long a toast stays visible before auto-dismissing (ms). */
const AUTO_DISMISS_MS = 5_000;

/** Maximum toasts visible at once.  Oldest are dropped first. */
const MAX_VISIBLE = 5;

// ---------------------------------------------------------------------------
// ToastProvider
// ---------------------------------------------------------------------------

/**
 * Wrap the application with this provider to enable toast
 * notifications.  Added to `Providers.tsx` alongside React Query
 * and ThemeProvider.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  // `useCallback` ensures this function reference is stable across
  // re-renders, preventing unnecessary re-renders of consumers.
  const addToast = useCallback((variant: ToastVariant, message: string) => {
    const id = crypto.randomUUID();
    setToasts((prev) => {
      const next = [...prev, { id, variant, message }];
      // If we exceed MAX_VISIBLE, drop the oldest entries.
      // `slice(-MAX_VISIBLE)` keeps only the last N items.
      return next.length > MAX_VISIBLE ? next.slice(-MAX_VISIBLE) : next;
    });
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </ToastContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// useToast hook
// ---------------------------------------------------------------------------

/**
 * Access the toast system from any client component.
 *
 * Throws if called outside `ToastProvider` — this is intentional.
 * A missing provider is a programmer error, and an explicit error
 * message is better than mysterious `undefined` behaviour.
 */
export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast() must be used within a <ToastProvider>");
  }
  return context;
}

// ---------------------------------------------------------------------------
// ToastContainer (internal)
// ---------------------------------------------------------------------------

/**
 * Variant → Tailwind class mapping.  Each entry specifies border,
 * background, and text colours for light and dark mode.
 *
 * All classes are full static strings for Tailwind v4 scanner.
 */
const VARIANT_CLASSES: Record<ToastVariant, string> = {
  success:
    "border-green-200 bg-green-50 text-green-800 " +
    "dark:border-green-800 dark:bg-green-950 dark:text-green-200",
  error:
    "border-red-200 bg-red-50 text-red-800 " +
    "dark:border-red-800 dark:bg-red-950 dark:text-red-200",
  info:
    "border-blue-200 bg-blue-50 text-blue-800 " +
    "dark:border-blue-800 dark:bg-blue-950 dark:text-blue-200",
};

/** Variant → lucide icon component. */
const VARIANT_ICONS: Record<ToastVariant, typeof CheckCircle> = {
  success: CheckCircle,
  error: XCircle,
  info: Info,
};

interface ToastContainerProps {
  toasts: Toast[];
  onRemove: (id: string) => void;
}

function ToastContainer({ toasts, onRemove }: ToastContainerProps) {
  // SSR guard — `document.body` doesn't exist during server rendering.
  // `useSyncExternalStore` is the React 19 pattern for values that
  // differ between server and client (same approach as Modal and
  // ThemeProvider).
  const mounted = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );

  if (!mounted || toasts.length === 0) return null;

  return createPortal(
    <div
      role="region"
      aria-label="Notifications"
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2"
    >
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onRemove={onRemove} />
      ))}
    </div>,
    document.body,
  );
}

// ---------------------------------------------------------------------------
// ToastItem (internal)
// ---------------------------------------------------------------------------

interface ToastItemProps {
  toast: Toast;
  onRemove: (id: string) => void;
}

/**
 * Individual toast notification.
 *
 * Each toast auto-dismisses after `AUTO_DISMISS_MS`.  The timeout
 * is cleared on unmount or manual close, preventing stale removals.
 *
 * `role="alert"` causes screen readers to immediately announce the
 * toast content — no focus required.
 */
function ToastItem({ toast, onRemove }: ToastItemProps) {
  useEffect(() => {
    const timer = setTimeout(() => onRemove(toast.id), AUTO_DISMISS_MS);
    return () => clearTimeout(timer);
  }, [toast.id, onRemove]);

  const Icon = VARIANT_ICONS[toast.variant];

  return (
    <div
      role="alert"
      className={[
        "flex items-center gap-3 rounded-lg border px-4 py-3 shadow-lg",
        VARIANT_CLASSES[toast.variant],
      ].join(" ")}
    >
      <Icon className="h-5 w-5 shrink-0" />
      <p className="text-sm font-medium">{toast.message}</p>
      <button
        onClick={() => onRemove(toast.id)}
        className="ml-auto shrink-0 rounded-md p-1 opacity-70 transition-opacity hover:opacity-100"
        aria-label="Dismiss notification"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}