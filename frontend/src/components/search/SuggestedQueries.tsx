/**
 * Suggested queries — example prompts shown in the Search page's
 * idle state to help new users get started.
 *
 * ## Why hardcoded?
 *
 * These are curated examples that demonstrate the range of questions
 * the semantic search can answer (revenue analysis, risk factors,
 * liquidity, guidance, M&A). They're not personalised, so there's
 * no reason to fetch them from the backend.
 *
 * ## Interaction
 *
 * Clicking a chip fills the search box via the parent's callback.
 * The parent decides whether to auto-submit or wait for the user.
 * This keeps the component stateless.
 */

"use client";

import { Sparkles } from "lucide-react";

// ---------------------------------------------------------------------------
// Curated example queries
// ---------------------------------------------------------------------------

const EXAMPLES: readonly string[] = [
  "Revenue outlook and forward guidance",
  "Material risk factors related to supply chain",
  "Changes in cash and short-term investments",
  "Segment revenue by geography",
  "Stock-based compensation expense trends",
];

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface SuggestedQueriesProps {
  /** Called when a chip is clicked — parent should set its query state. */
  onSelect: (query: string) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SuggestedQueries({ onSelect }: SuggestedQueriesProps) {
  return (
    <section
      aria-label="Suggested queries"
      className="rounded-lg border border-hairline bg-surface p-5"
    >
      <div className="mb-3 flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-fg-muted" />
        <span className="font-mono text-[11px] font-semibold uppercase tracking-widest text-fg-muted">
          Try asking
        </span>
      </div>

      <ul className="flex flex-wrap gap-2">
        {EXAMPLES.map((example) => (
          <li key={example}>
            <button
              type="button"
              onClick={() => onSelect(example)}
              className="
                inline-flex items-center rounded-md border border-hairline
                bg-card px-3 py-1.5 text-xs text-fg-muted
                transition-colors
                hover:border-accent/60 hover:bg-accent/10 hover:text-fg
                focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent
              "
            >
              {example}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
