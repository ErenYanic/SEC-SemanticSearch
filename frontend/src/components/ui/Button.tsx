/**
 * Reusable button with variant and size support.
 *
 * No `"use client"` needed — this is a pure presentational component.
 * The parent component that passes `onClick` will be the client
 * component; the button itself is just props in, JSX out.
 *
 * Four variants follow the project's colour conventions:
 *   - **primary** (blue)      — default actions: submit, save, search
 *   - **destructive** (red)   — dangerous actions: delete, clear
 *   - **secondary** (grey)    — cancel, dismiss, low-emphasis
 *   - **ghost** (transparent)  — icon-only buttons, subtle actions
 *
 * The `loading` prop renders a spinner and disables the button,
 * preventing double-submissions.
 */

import { type ButtonHTMLAttributes, type ReactNode, type Ref } from "react";
import { Loader2 } from "lucide-react";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

/**
 * Extends the native `<button>` attributes so callers can pass any
 * valid button prop (`type`, `disabled`, `aria-label`, `onClick`, etc.)
 * without us having to declare each one manually.
 */
export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Visual style. Defaults to `"primary"`. */
  variant?: "primary" | "destructive" | "secondary" | "ghost";
  /** Button size. Defaults to `"md"`. */
  size?: "sm" | "md" | "lg";
  /** When true, shows a spinner and disables the button. */
  loading?: boolean;
  /** Button content (text, icons, or both). */
  children: ReactNode;
  /**
   * Ref forwarded to the underlying `<button>` element.
   *
   * React 19 treats `ref` as a regular prop, but TypeScript's
   * `ButtonHTMLAttributes` doesn't include it — `ref` lives in
   * the separate `RefAttributes` type.  We add it explicitly so
   * callers (like Modal) can pass refs to Button.
   */
  ref?: Ref<HTMLButtonElement>;
}

// ---------------------------------------------------------------------------
// Class mappings
// ---------------------------------------------------------------------------

/**
 * Classes shared by every variant: layout, shape, font, focus ring,
 * disabled state, and transition.
 *
 * `focus-visible` (not `focus`) ensures the outline only appears on
 * keyboard navigation — mouse clicks won't show it.
 */
const BASE =
  "inline-flex items-center justify-center gap-2 rounded-md font-medium " +
  "transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 " +
  "disabled:pointer-events-none disabled:opacity-50";

/**
 * Each variant is a complete, static string so Tailwind's class
 * scanner can detect every class at build time.  Dynamic
 * interpolation (e.g. `bg-${color}-600`) would silently break.
 */
const VARIANT_CLASSES: Record<NonNullable<ButtonProps["variant"]>, string> = {
  primary:
    "bg-blue-600 text-white hover:bg-blue-700 " +
    "focus-visible:outline-blue-600 " +
    "dark:bg-blue-500 dark:hover:bg-blue-600",
  destructive:
    "bg-red-600 text-white hover:bg-red-700 " +
    "focus-visible:outline-red-600 " +
    "dark:bg-red-500 dark:hover:bg-red-600",
  secondary:
    "bg-gray-100 text-gray-700 hover:bg-gray-200 " +
    "focus-visible:outline-gray-500 " +
    "dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700",
  ghost:
    "text-gray-600 hover:bg-gray-100 hover:text-gray-900 " +
    "focus-visible:outline-gray-500 " +
    "dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-100",
};

/**
 * Size classes control padding and font size.  The values are chosen
 * to match the existing spacing scale in the Navbar (px-3 py-2 for
 * nav links, p-2 for the icon button).
 */
const SIZE_CLASSES: Record<NonNullable<ButtonProps["size"]>, string> = {
  sm: "px-2.5 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
  lg: "px-6 py-3 text-base",
};

/**
 * Spinner sizes match the text size of each button size so the
 * spinner feels proportional.
 */
const SPINNER_SIZES: Record<NonNullable<ButtonProps["size"]>, string> = {
  sm: "h-3 w-3",
  md: "h-4 w-4",
  lg: "h-5 w-5",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  children,
  className,
  disabled,
  ref,
  ...rest
}: ButtonProps) {
  // Compose the final class string.  The caller's `className` (if any)
  // is appended last so it can override specific styles.
  const classes = [
    BASE,
    VARIANT_CLASSES[variant],
    SIZE_CLASSES[size],
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      ref={ref}
      className={classes}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading && (
        <Loader2 className={`${SPINNER_SIZES[size]} animate-spin`} />
      )}
      {children}
    </button>
  );
}