/**
 * Table listing each ticker with its filing count, chunk count, and
 * form types. Clicking a row navigates to `/filings?ticker=AAPL`.
 *
 * ## Design pattern: presentational + navigation
 *
 * This component receives data (no fetching), renders a table, and
 * handles one interaction — row clicks that navigate to the Filings
 * page. It uses `useRouter()` for that, which makes it a Client
 * Component (`"use client"`).
 *
 * ## Why <Badge> for form types?
 *
 * Each ticker can have multiple form types (["10-K", "10-Q"]).
 * Badges are a compact, scannable way to show categorical data.
 * We use the existing `Badge` component from `components/ui/`.
 *
 * ## Accessibility: `cursor-pointer` + `hover:` styles
 *
 * Rows look and behave like clickable elements. The pointer cursor
 * signals interactivity, and the hover background provides feedback.
 */

"use client";

import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui";
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
    <div className="rounded-lg border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-950">
      <div className="px-6 py-4">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          Tickers
        </h2>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-t border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-900">
              <th className="px-6 py-3 font-medium text-gray-600 dark:text-gray-400">
                Ticker
              </th>
              <th className="px-6 py-3 font-medium text-gray-600 dark:text-gray-400">
                Filings
              </th>
              <th className="px-6 py-3 font-medium text-gray-600 dark:text-gray-400">
                Chunks
              </th>
              <th className="px-6 py-3 font-medium text-gray-600 dark:text-gray-400">
                Forms
              </th>
            </tr>
          </thead>
          <tbody>
            {tickers.map((t) => (
              <tr
                key={t.ticker}
                onClick={() => router.push(`/filings?ticker=${t.ticker}`)}
                className="cursor-pointer border-t border-gray-200 transition-colors hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-gray-900"
              >
                <td className="px-6 py-3 font-semibold text-gray-900 dark:text-gray-100">
                  {t.ticker}
                </td>
                <td className="px-6 py-3 text-gray-700 dark:text-gray-300">
                  {t.filings}
                </td>
                <td className="px-6 py-3 text-gray-700 dark:text-gray-300">
                  {t.chunks.toLocaleString()}
                </td>
                <td className="px-6 py-3">
                  <div className="flex gap-1.5">
                    {t.forms.map((form) => (
                      <Badge key={form} variant="blue">
                        {form}
                      </Badge>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="px-6 py-3 text-xs text-gray-500 dark:text-gray-400">
        Click a row to view filings
      </p>
    </div>
  );
}