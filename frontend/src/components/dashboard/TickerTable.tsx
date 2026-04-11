/**
 * Terminal-style table listing each ticker with its filing count,
 * chunk count, and the form types filed. Clicking a row navigates
 * to the Filings page with a pre-applied ticker filter.
 *
 * Columns are arranged with the identifier on the left (mono,
 * tabular) and numeric columns right-aligned, mirroring how
 * Bloomberg/Reuters terminals display quote tables. Row height is
 * tight so ~10 rows fit in the column next to the chart without
 * dominating the layout.
 */

"use client";

import { useRouter } from "next/navigation";
import type { TickerBreakdown } from "@/lib/types";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface TickerTableProps {
  tickers: TickerBreakdown[];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TickerTable({ tickers }: TickerTableProps) {
  const router = useRouter();

  if (tickers.length === 0) return null;

  return (
    <div className="rounded-2xl border border-hairline bg-card/80 shadow-sm backdrop-blur-sm">
      {/* ---- Header ---- */}
      <div className="flex items-baseline justify-between border-b border-hairline px-6 py-4">
        <h2 className="text-base font-semibold text-fg">Tickers</h2>
        <span className="text-sm text-fg-subtle">Click a row to filter</span>
      </div>

      {/* ---- Table ---- */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-hairline bg-surface/40">
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wide text-fg-subtle">
                Ticker
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wide text-fg-subtle">
                Filings
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wide text-fg-subtle">
                Chunks
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wide text-fg-subtle">
                Forms
              </th>
            </tr>
          </thead>
          <tbody>
            {tickers.map((t) => (
              <tr
                key={t.ticker}
                onClick={() => router.push(`/filings?ticker=${t.ticker}`)}
                className="cursor-pointer border-b border-hairline/50 transition-colors last:border-b-0 hover:bg-surface/60"
              >
                <td className="px-6 py-3.5 text-sm font-semibold text-fg">
                  {t.ticker}
                </td>
                <td className="px-6 py-3.5 text-right text-sm tabular-nums text-fg-muted">
                  {t.filings}
                </td>
                <td className="px-6 py-3.5 text-right text-sm tabular-nums text-fg-muted">
                  {t.chunks.toLocaleString()}
                </td>
                <td className="px-6 py-3.5">
                  <div className="flex flex-wrap gap-1.5">
                    {t.forms.map((form) => (
                      <span
                        key={form}
                        className="inline-flex items-center rounded-md border border-hairline bg-surface px-2 py-0.5 text-xs font-medium text-fg-muted"
                      >
                        {form}
                      </span>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
