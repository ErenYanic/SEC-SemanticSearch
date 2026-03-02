/**
 * Displays a similarity score as a colour-coded badge.
 *
 * Colour thresholds are calibrated to `google/embeddinggemma-300m`
 * (the project's embedding model).  Cosine similarity scores from
 * this model cluster in the 0.2–0.5 range for SEC filings, so:
 *
 *   - **Green  (>= 40%)**  — strong match
 *   - **Amber  (>= 25%)**  — moderate match
 *   - **Red    (< 25%)**   — weak match / noise
 *
 * These match the CLI's colour thresholds (see `cli/search.py`).
 * If the embedding model changes, update the thresholds here — this
 * is the single source of truth for the frontend.
 *
 * No `"use client"` needed — pure computation and rendering.
 */

import { Badge, type BadgeProps } from "./Badge";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface SimilarityBadgeProps {
  /** Similarity score from 0 to 1 (as returned by the API). */
  similarity: number;
  /** Additional CSS classes. */
  className?: string;
}

// ---------------------------------------------------------------------------
// Thresholds
// ---------------------------------------------------------------------------

/** Minimum similarity for a "green" (strong) badge. */
const GREEN_THRESHOLD = 0.40;
/** Minimum similarity for an "amber" (moderate) badge. */
const AMBER_THRESHOLD = 0.25;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Converts a 0–1 similarity score to a Badge colour variant.
 *
 * Extracted as a named function (rather than inline ternary) so it
 * can be unit-tested independently if needed.
 */
function similarityToVariant(
  similarity: number,
): NonNullable<BadgeProps["variant"]> {
  if (similarity >= GREEN_THRESHOLD) return "green";
  if (similarity >= AMBER_THRESHOLD) return "amber";
  return "red";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SimilarityBadge({ similarity, className }: SimilarityBadgeProps) {
  const percentage = Math.round(similarity * 100);
  const variant = similarityToVariant(similarity);

  return (
    <Badge variant={variant} className={className}>
      {percentage}%
    </Badge>
  );
}