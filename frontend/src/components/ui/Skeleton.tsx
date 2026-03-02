/**
 * Skeleton loading placeholder — shows a shimmer animation where
 * content will appear.
 *
 * Two exports:
 *   - `Skeleton`     — single block (cards, images, badges)
 *   - `SkeletonText` — multiple lines of varying width (paragraphs)
 *
 * ## How the shimmer works
 *
 * The element has a linear-gradient background with three colour stops:
 *   transparent → semi-white → transparent
 *
 * `background-size: 200% 100%` makes the gradient twice as wide as
 * the element, so the bright band can sweep from right to left.
 * The `shimmer` keyframe (defined in `globals.css`) animates
 * `background-position` from `200% 0` → `-200% 0`.
 *
 * ## Why no `"use client"`?
 *
 * Skeletons are pure presentational — no hooks, no state, no browser
 * APIs.  They render server-side (or client-side when placed inside
 * a Client Component parent) with zero JavaScript overhead.
 */

// ---------------------------------------------------------------------------
// Skeleton block
// ---------------------------------------------------------------------------

interface SkeletonProps {
  /** Additional classes for width/height (e.g. `"h-6 w-32"`). */
  className?: string;
}

/**
 * A single skeleton block with a shimmer animation.
 *
 * The caller controls dimensions via `className`:
 *
 * ```tsx
 * <Skeleton className="h-6 w-32" />          // badge placeholder
 * <Skeleton className="h-10 w-full" />        // full-width bar
 * <Skeleton className="h-40 w-full rounded-lg" /> // card placeholder
 * ```
 */
export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={[
        // Base shape: rounded, grey background
        "rounded-md bg-gray-200 dark:bg-gray-700",
        // Shimmer gradient overlay
        "bg-gradient-to-r from-transparent via-gray-300/50 dark:via-gray-600/50 to-transparent",
        // Animation: sweep the gradient across (defined in globals.css)
        "bg-[length:200%_100%] [animation:shimmer_1.5s_ease-in-out_infinite]",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    />
  );
}

// ---------------------------------------------------------------------------
// Skeleton text (multiple lines)
// ---------------------------------------------------------------------------

interface SkeletonTextProps {
  /** Number of text lines to render. Defaults to `3`. */
  lines?: number;
  /** Additional classes for the wrapper `<div>`. */
  className?: string;
}

/**
 * Multiple skeleton lines mimicking a paragraph.
 *
 * Line widths cycle through 100% → 90% → 75% to look natural.
 * The last line is always shorter (60%) to mimic a paragraph ending
 * mid-line.
 *
 * ```tsx
 * <SkeletonText lines={4} />
 * ```
 */
const LINE_WIDTHS = ["w-full", "w-[90%]", "w-3/4"];

export function SkeletonText({ lines = 3, className }: SkeletonTextProps) {
  return (
    <div className={["space-y-2", className].filter(Boolean).join(" ")}>
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton
          key={i}
          className={[
            "h-4",
            i === lines - 1
              ? "w-3/5" // last line is shorter
              : LINE_WIDTHS[i % LINE_WIDTHS.length],
          ].join(" ")}
        />
      ))}
    </div>
  );
}