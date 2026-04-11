/**
 * Loading spinner — wraps lucide's `Loader2` with consistent sizing
 * and accessibility attributes.
 *
 * Two exports:
 *   - `Spinner`          — inline spinner (inside buttons, next to text)
 *   - `FullPageSpinner`  — centred in the viewport (for initial page loads)
 *
 * No `"use client"` needed — this is pure SVG rendering with a CSS
 * animation (`animate-spin` is a Tailwind utility, not a React hook).
 */

import { Loader2 } from "lucide-react";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface SpinnerProps {
  /** Spinner diameter. Defaults to `"md"`. */
  size?: "sm" | "md" | "lg" | "xl";
  /** Additional CSS classes (e.g. to override the colour). */
  className?: string;
}

// ---------------------------------------------------------------------------
// Size mapping
// ---------------------------------------------------------------------------

/**
 * Maps size names to Tailwind dimension classes.  These match the
 * icon sizes used elsewhere in the project:
 *   - sm  = h-4 w-4  (inside buttons, inline indicators)
 *   - md  = h-5 w-5  (standalone spinners, Navbar icons)
 *   - lg  = h-8 w-8  (page-level indicators)
 *   - xl  = h-12 w-12 (full-page loading states)
 */
const SIZE_CLASSES: Record<NonNullable<SpinnerProps["size"]>, string> = {
  sm: "h-4 w-4",
  md: "h-5 w-5",
  lg: "h-8 w-8",
  xl: "h-12 w-12",
};

// ---------------------------------------------------------------------------
// Components
// ---------------------------------------------------------------------------

/**
 * Inline spinner for use inside buttons, next to labels, or as a
 * compact loading indicator.
 *
 * The wrapping `<span>` carries `role="status"` so screen readers
 * announce "Loading" without the user needing to see the animation.
 */
export function Spinner({ size = "md", className }: SpinnerProps) {
  return (
    <span role="status" aria-label="Loading">
      <Loader2
        className={[
          SIZE_CLASSES[size],
          "animate-spin text-accent",
          className,
        ]
          .filter(Boolean)
          .join(" ")}
      />
    </span>
  );
}

/**
 * Full-page spinner — vertically centred with generous whitespace.
 *
 * Use this for initial data fetches where the entire page content
 * depends on the response (e.g. Dashboard loading status data).
 * `min-h-[50vh]` ensures the spinner sits roughly in the middle of
 * the viewport without pushing the footer off-screen.
 */
export function FullPageSpinner() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <Spinner size="xl" />
    </div>
  );
}