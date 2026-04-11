/**
 * Dashboard page — the landing page ("/").
 *
 * ## Architecture
 *
 * This page is the **data boundary**. It owns the data-fetching
 * lifecycle (loading → error → empty → success) and passes the
 * result down to presentational child components.
 *
 *   isLoading  → DashboardSkeleton
 *   isError    → error message with retry
 *   data.filing_count === 0 → EmptyState (link to Ingest page)
 *   otherwise  → header + KPI strip + chart/table workbench
 *
 * ## Layout
 *
 *   ┌──────────────────────────────────────────────────────────┐
 *   │  Dashboard          5 filings · 1,500 chunks · 2 tickers │
 *   ├─────────┬─────────┬─────────┬────────────────────────────┤
 *   │ Filings │ Chunks  │ Tickers │ Avg chunks/filing          │  KPI strip
 *   ├─────────┴─────────┴─────────┴────────────────────────────┤
 *   │                                                          │
 *   │  FormChart (1.4fr)          │  TickerTable (1fr)         │
 *   │                                                          │
 *   └──────────────────────────────────────────────────────────┘
 *
 * FormChart is lazy-loaded via `next/dynamic` with `ssr: false` to
 * keep Recharts (~150 KB gzipped) out of the initial page bundle.
 */

"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { Database, Upload } from "lucide-react";
import { useStatus } from "@/hooks/useStatus";
import { Button, EmptyState, Skeleton } from "@/components/ui";
import {
  DashboardMetrics,
  DashboardSkeleton,
  TickerTable,
} from "@/components/dashboard";

const FormChart = dynamic(
  () =>
    import("@/components/dashboard/FormChart").then((mod) => mod.FormChart),
  {
    ssr: false,
    loading: () => (
      <div className="rounded-2xl border border-hairline bg-card/80">
        <div className="border-b border-hairline px-6 py-4">
          <Skeleton className="h-5 w-40" />
        </div>
        <div className="flex h-72 items-end gap-6 p-6 pb-10">
          <Skeleton className="h-3/4 flex-1 rounded-t-lg" />
          <Skeleton className="h-1/2 flex-1 rounded-t-lg" />
          <Skeleton className="h-5/6 flex-1 rounded-t-lg" />
        </div>
      </div>
    ),
  },
);

export default function DashboardPage() {
  const { data: status, isLoading, isError } = useStatus();

  if (isLoading) {
    return <DashboardSkeleton />;
  }

  if (isError || !status) {
    return (
      <EmptyState
        icon={Database}
        title="Unable to load dashboard"
        description="The API server may be offline. Make sure the FastAPI backend is running on port 8000."
        action={
          <Button onClick={() => window.location.reload()}>
            Retry
          </Button>
        }
      />
    );
  }

  if (status.filing_count === 0) {
    return (
      <EmptyState
        icon={Database}
        title="No filings yet"
        description="Ingest SEC filings to populate the dashboard with statistics and charts."
        action={
          <Link href="/ingest">
            <Button>
              <Upload className="mr-2 h-4 w-4" />
              Ingest Filings
            </Button>
          </Link>
        }
      />
    );
  }

  const filingCount = status.filing_count;
  const chunkCount = status.chunk_count;
  const tickerCount = status.tickers.length;

  return (
    <div className="space-y-8 [animation:fade-in_300ms_ease-out]">
      {/* ---- Page header ---- */}
      <div className="space-y-3">
        <h1 className="text-3xl font-semibold tracking-tight text-fg sm:text-4xl">
          Dashboard
        </h1>
        <p className="text-base text-fg-muted">
          <span className="font-semibold text-fg">
            {filingCount.toLocaleString()}
          </span>{" "}
          filing{filingCount !== 1 && "s"} ·{" "}
          <span className="font-semibold text-fg">
            {chunkCount.toLocaleString()}
          </span>{" "}
          chunks indexed across{" "}
          <span className="font-semibold text-fg">
            {tickerCount.toLocaleString()}
          </span>{" "}
          ticker{tickerCount !== 1 && "s"}
        </p>
      </div>

      {/* ---- KPI strip ---- */}
      <DashboardMetrics status={status} />

      {/* ---- Workbench: chart + ticker table ---- */}
      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <FormChart formBreakdown={status.form_breakdown} />
        <TickerTable tickers={status.ticker_breakdown} />
      </div>
    </div>
  );
}
