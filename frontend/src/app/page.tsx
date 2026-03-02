/**
 * Dashboard page — the landing page ("/").
 *
 * ## Architecture: the "smart component" pattern
 *
 * This page is the **data boundary**. It owns the data-fetching
 * lifecycle (loading → error → empty → success) and passes the
 * result down to presentational child components that only know
 * how to render.
 *
 * The state machine looks like this:
 *
 *   isLoading  → DashboardSkeleton (content-shaped placeholder)
 *   isError    → error message with retry hint
 *   data.filing_count === 0 → EmptyState (link to Ingest page)
 *   otherwise  → DashboardMetrics + FormChart + TickerTable (fade-in)
 *
 * ## Why `"use client"`?
 *
 * The page uses `useStatus()` (a React Query hook). Hooks only
 * work in Client Components. The child components that don't use
 * hooks (DashboardMetrics) could be Server Components, but since
 * they receive dynamic data as props from this Client Component
 * parent, they render on the client regardless. FormChart and
 * TickerTable are explicitly `"use client"` because they use
 * `useRouter()`.
 */

"use client";

import Link from "next/link";
import { LayoutDashboard, Database, Upload } from "lucide-react";
import { useStatus } from "@/hooks/useStatus";
import { Button, EmptyState } from "@/components/ui";
import {
  DashboardMetrics,
  DashboardSkeleton,
  FormChart,
  TickerTable,
} from "@/components/dashboard";

export default function DashboardPage() {
  const { data: status, isLoading, isError } = useStatus();

  // ---- Loading state ----
  // DashboardSkeleton mirrors the real layout (3 metric cards + chart +
  // table) so the user sees the page structure immediately. This feels
  // faster than a blank page with a spinner — the brain starts processing
  // the layout before data arrives.
  if (isLoading) {
    return <DashboardSkeleton />;
  }

  // ---- Error state ----
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

  // ---- Empty state: no filings ingested yet ----
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

  // ---- Data loaded: render dashboard ----
  // The fade-in animation (200ms) prevents the jarring "flash" when
  // the skeleton is replaced by real content. It's subtle but makes
  // the transition feel polished rather than abrupt.
  return (
    <div className="space-y-6 [animation:fade-in_200ms_ease-out]">
      {/* Page header */}
      <div className="flex items-center gap-3">
        <LayoutDashboard className="h-8 w-8 text-blue-600 dark:text-blue-400" />
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          Dashboard
        </h1>
      </div>

      {/* Metric cards */}
      <DashboardMetrics status={status} />

      {/* Charts and tables in a responsive grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        <FormChart formBreakdown={status.form_breakdown} />
        <TickerTable tickers={status.ticker_breakdown} />
      </div>
    </div>
  );
}