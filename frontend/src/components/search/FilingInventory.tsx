/**
 * Compact collapsible summary of what's in the database.
 *
 * ## Why this component exists
 *
 * When a user arrives at the Search page, their first question is
 * often: "What can I search?" This panel answers that by showing
 * the available tickers and form types — the database's inventory.
 *
 * It's collapsible because once you know what's available, you
 * don't need it taking up space. The default state is collapsed.
 *
 * ## Data source
 *
 * Uses the same `useStatus()` hook as the Dashboard. Because of
 * React Query's cache deduplication, if the user just came from
 * the Dashboard, the data is already cached — no extra API call.
 */

"use client";

import { useId, useState } from "react";
import { ChevronDown, ChevronUp, Database } from "lucide-react";
import { Badge } from "@/components/ui";
import type { StatusResponse } from "@/lib/types";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface FilingInventoryProps {
  status: StatusResponse;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function FilingInventory({ status }: FilingInventoryProps) {
  const [isOpen, setIsOpen] = useState(false);
  const panelId = useId();

  if (status.filing_count === 0) return null;

  return (
    <div className="rounded-2xl border border-hairline bg-card/70 backdrop-blur-sm">
      <button
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        aria-controls={panelId}
        className="flex w-full items-center justify-between px-5 py-4 text-sm text-fg-muted transition-colors hover:bg-surface/60 hover:text-fg"
      >
        <span className="flex items-center gap-2.5">
          <Database className="h-4 w-4" />
          <span className="font-semibold text-fg">{status.filing_count}</span>
          filing{status.filing_count !== 1 && "s"}
          <span className="text-fg-subtle">·</span>
          <span className="font-semibold text-fg">{status.tickers.length}</span>
          ticker{status.tickers.length !== 1 && "s"}
        </span>
        {isOpen ? (
          <ChevronUp className="h-4 w-4" />
        ) : (
          <ChevronDown className="h-4 w-4" />
        )}
      </button>

      {isOpen && (
        <div
          id={panelId}
          role="region"
          aria-label="Filing inventory"
          className="border-t border-hairline px-5 py-4"
        >
          <div className="flex flex-wrap gap-x-4 gap-y-3">
            {status.ticker_breakdown.map((t) => (
              <span
                key={t.ticker}
                className="inline-flex items-center gap-1.5 text-sm text-fg-muted"
              >
                <span className="font-semibold text-fg">{t.ticker}</span>
                {t.forms.map((form) => (
                  <Badge key={form} variant="blue">
                    {form}
                  </Badge>
                ))}
                <span className="text-fg-subtle">({t.filings})</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}