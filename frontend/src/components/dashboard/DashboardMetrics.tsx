/**
 * Three metric cards for the Dashboard: Filings, Chunks, Tickers.
 *
 * This is a **presentational component** — it receives data via props
 * and renders it. It has no data-fetching logic, no hooks, no state.
 * The parent page is responsible for fetching and passing the data.
 *
 * Why this separation? It makes the component:
 *   1. Easy to test — pass props, assert output
 *   2. Easy to reuse — doesn't care where data comes from
 *   3. Easy to read — rendering logic only, no async concerns
 */

import { FileText, Layers, Building2 } from "lucide-react";
import { MetricCard } from "@/components/ui";
import type { StatusResponse } from "@/lib/types";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface DashboardMetricsProps {
  status: StatusResponse;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DashboardMetrics({ status }: DashboardMetricsProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <MetricCard
        label="Filings"
        value={status.filing_count}
        icon={FileText}
        capacity={{
          current: status.filing_count,
          max: status.max_filings,
        }}
      />
      <MetricCard
        label="Chunks"
        value={status.chunk_count.toLocaleString()}
        icon={Layers}
      />
      <MetricCard
        label="Tickers"
        value={status.tickers.length}
        icon={Building2}
      />
    </div>
  );
}