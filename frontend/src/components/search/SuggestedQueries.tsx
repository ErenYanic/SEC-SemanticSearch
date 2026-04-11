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
      className="rounded-2xl border border-hairline bg-card/70 p-6 backdrop-blur-sm"
    >
      <div className="mb-4 flex items-center gap-2.5">
        <Sparkles className="h-4 w-4 text-accent" />
        <span className="text-base font-semibold text-fg">Try asking</span>
      </div>

      <ul className="flex flex-wrap gap-2.5">
        {EXAMPLES.map((example) => (
          <li key={example}>
            <button
              type="button"
              onClick={() => onSelect(example)}
              className="
                inline-flex items-center rounded-lg border border-hairline
                bg-card px-4 py-2 text-sm text-fg-muted
                transition-all
                hover:border-accent/50 hover:bg-accent/10 hover:text-fg
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
