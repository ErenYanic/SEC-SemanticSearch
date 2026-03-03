/**
 * Bar chart showing the number of filings per form type (e.g. 10-K, 10-Q).
 *
 * Uses **Recharts**, a composable charting library built on React components.
 * Instead of a monolithic `<Chart options={...} />` API (like Chart.js),
 * Recharts lets you compose a chart from individual building blocks:
 *
 *   <BarChart data={data}>        ← The coordinate system
 *     <XAxis dataKey="form" />    ← What goes on the horizontal axis
 *     <Bar dataKey="count" />     ← What the bars represent
 *   </BarChart>
 *
 * This composable pattern is very React-idiomatic — each piece is a
 * component with its own props, and you can add/remove features by
 * adding/removing child components.
 *
 * ## Why `ResponsiveContainer`?
 *
 * Recharts needs an explicit width/height. `ResponsiveContainer`
 * watches its parent's size and passes it down, so the chart
 * automatically resizes when the viewport changes.
 *
 * ## Per-bar colours via data
 *
 * Recharts 3.x deprecated the `<Cell>` component. The modern
 * approach is to embed the colour directly in each data point
 * (e.g. `{ form: "10-K", count: 5, fill: "#2563eb" }`) and
 * reference it with `<Bar fill` pointing to a data key.  But
 * since we only have 2–3 form types, an even simpler approach
 * is to use a single brand colour for all bars.
 *
 * ## Clickable bars
 *
 * Each bar has an `onClick` handler that navigates to the Filings
 * page with a pre-applied `form_type` filter. We use Next.js's
 * `useRouter().push()` for client-side navigation.
 */

"use client";

import { useRouter } from "next/navigation";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface FormChartProps {
  /** Map of form type → filing count, e.g. { "10-K": 5, "10-Q": 12 } */
  formBreakdown: Record<string, number>;
}

/** Shape of each data point passed to Recharts. */
interface FormDataPoint {
  form: string;
  count: number;
  fill: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Colour palette for chart bars — blue shades that work in both themes. */
const BAR_COLOURS = ["#2563eb", "#3b82f6", "#60a5fa", "#93c5fd"];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function FormChart({ formBreakdown }: FormChartProps) {
  const router = useRouter();

  // Transform the Record into an array Recharts can iterate over.
  // Recharts needs `[{ form: "10-K", count: 5, fill: "..." }, ...]`.
  // Each data point carries its own colour — the modern Recharts 3.x
  // replacement for the deprecated <Cell> component.
  const data: FormDataPoint[] = Object.entries(formBreakdown).map(
    ([form, count], index) => ({
      form,
      count,
      fill: BAR_COLOURS[index % BAR_COLOURS.length],
    }),
  );

  if (data.length === 0) return null;

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-gray-950">
      <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-gray-100">
        Filings by Form Type
      </h2>

      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            margin={{ top: 8, right: 8, bottom: 8, left: 0 }}
          >
            <XAxis
              dataKey="form"
              tick={{ fill: "#9ca3af", fontSize: 13 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              allowDecimals={false}
              tick={{ fill: "#9ca3af", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
              width={32}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#1f2937",
                border: "none",
                borderRadius: "0.5rem",
                color: "#f3f4f6",
                fontSize: "0.875rem",
              }}
              cursor={{ fill: "rgba(59, 130, 246, 0.08)" }}
            />
            <Bar
              dataKey="count"
              name="Filings"
              radius={[6, 6, 0, 0]}
              cursor="pointer"
              onClick={(_data, index) => {
                const point = data[index];
                if (point) {
                  router.push(`/filings?form_type=${point.form}`);
                }
              }}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <p className="mt-2 text-center text-xs text-gray-500 dark:text-gray-400">
        Click a bar to view filings
      </p>
    </div>
  );
}