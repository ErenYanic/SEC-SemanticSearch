/**
 * Small coloured label — for status indicators, form types, and tags.
 *
 * Five colour variants:
 *   - **gray**   — neutral, default
 *   - **blue**   — active / running / informational
 *   - **green**  — success / completed
 *   - **amber**  — warning / pending
 *   - **red**    — error / failed / cancelled
 *
 * The colour pattern (`bg-{color}-50 text-{color}-700` in light mode,
 * `dark:bg-{color}-950 dark:text-{color}-300` in dark mode) mirrors
 * the active nav link styling established in Navbar.tsx.
 *
 * No `"use client"` needed — pure class computation and rendering.
 */

import { type ReactNode } from "react";
import type { TaskState } from "@/lib/types";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface BadgeProps {
  /** Colour variant. Defaults to `"gray"`. */
  variant?: "gray" | "blue" | "green" | "amber" | "red";
  /** Badge content (usually short text). */
  children: ReactNode;
  /** Additional CSS classes. */
  className?: string;
}

// ---------------------------------------------------------------------------
// Class mappings
// ---------------------------------------------------------------------------

/**
 * Base classes shared by all variants: inline layout, pill shape,
 * compact padding, and small bold text.
 */
const BASE = "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium";

/**
 * Each variant uses a light tinted background with darker text.
 * In dark mode, the background becomes very dark and the text
 * becomes lighter — maintaining contrast on both themes.
 *
 * All classes are written as full static strings so Tailwind v4's
 * class scanner can detect them at build time.
 */
const VARIANT_CLASSES: Record<NonNullable<BadgeProps["variant"]>, string> = {
  gray:
    "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  blue:
    "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  green:
    "bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-300",
  amber:
    "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  red:
    "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function Badge({ variant = "gray", children, className }: BadgeProps) {
  const classes = [BASE, VARIANT_CLASSES[variant], className]
    .filter(Boolean)
    .join(" ");

  return <span className={classes}>{children}</span>;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Maps a `TaskState` value from the API to the corresponding Badge
 * colour variant.
 *
 * This lives alongside Badge (rather than in a separate utils file)
 * because it is tightly coupled to Badge's variant set — if we add
 * or rename a variant, this function must update in tandem.
 *
 * Usage:
 * ```tsx
 * <Badge variant={taskStateToBadgeVariant(task.status)}>
 *   {task.status}
 * </Badge>
 * ```
 */
export function taskStateToBadgeVariant(
  state: TaskState,
): NonNullable<BadgeProps["variant"]> {
  switch (state) {
    case "pending":
      return "amber";
    case "running":
      return "blue";
    case "completed":
      return "green";
    case "failed":
      return "red";
    case "cancelled":
      return "red";
  }
}