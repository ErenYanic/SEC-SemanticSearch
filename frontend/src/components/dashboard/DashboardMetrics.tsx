/**
 * KPI strip for the Dashboard: four compact cards showing Filings,
 * Chunks, Tickers, and Avg chunks/filing.
 *
 * The fourth "Avg chunks/filing" card is a derived stat — it's cheap
 * to compute from the existing payload and adds a useful signal about
 * corpus density (how rich each filing is once chunked).
 */

import { FileText, Layers, Building2, Gauge } from "lucide-react";
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
  const avgChunks =
    status.filing_count > 0
      ? Math.round(status.chunk_count / status.filing_count)
      : 0;

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
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
      <MetricCard
        label="Avg chunks / filing"
        value={avgChunks.toLocaleString()}
        icon={Gauge}
      />
    </div>
  );
}
