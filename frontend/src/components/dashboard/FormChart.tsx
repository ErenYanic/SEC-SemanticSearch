/**
 * Bar chart showing the number of filings per form type (e.g. 10-K, 10-Q).
 *
 * Styling is driven entirely by CSS custom properties (`var(--accent)`,
 * `var(--fg-muted)`, etc.) so the chart automatically re-colours when
 * the user switches to dark mode — no `dark:` variants, no runtime
 * theme detection, no duplicated palette.
 *
 * Bars use a single accent colour with stepped `fillOpacity` to hint
 * at ordering without introducing competing hues. Clicking a bar
 * navigates to the Filings page with a pre-applied `form_type` filter.
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
  CartesianGrid,
} from "recharts";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface FormChartProps {
  /** Map of form type → filing count, e.g. { "10-K": 5, "10-Q": 12 } */
  formBreakdown: Record<string, number>;
}

interface FormDataPoint {
  form: string;
  count: number;
  fill: string;
  fillOpacity: number;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

// Stepped opacity per bar index — single hue, different weights. With
// four steps the weakest bar is still readable (0.55) while the
// strongest stays fully saturated.
const BAR_OPACITIES = [1, 0.82, 0.68, 0.55];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function FormChart({ formBreakdown }: FormChartProps) {
  const router = useRouter();

  const data: FormDataPoint[] = Object.entries(formBreakdown).map(
    ([form, count], index) => ({
      form,
      count,
      fill: "var(--accent)",
      fillOpacity: BAR_OPACITIES[index % BAR_OPACITIES.length],
    }),
  );

  if (data.length === 0) return null;

  return (
    <div className="flex h-full flex-col rounded-2xl border border-hairline bg-card/80 shadow-sm backdrop-blur-sm">
      {/* ---- Header ---- */}
      <div className="flex items-baseline justify-between border-b border-hairline px-6 py-4">
        <h2 className="text-base font-semibold text-fg">Filings by form type</h2>
        <span className="text-sm text-fg-subtle">Click a bar to filter</span>
      </div>

      {/* ---- Chart body ---- */}
      <div className="min-h-[18rem] flex-1 p-6">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
          >
            <CartesianGrid
              vertical={false}
              stroke="var(--hairline)"
              strokeDasharray="2 4"
            />
            <XAxis
              dataKey="form"
              tick={{ fill: "var(--fg-muted)", fontSize: 13 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              allowDecimals={false}
              tick={{ fill: "var(--fg-subtle)", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
              width={32}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "var(--elev)",
                border: "1px solid var(--hairline)",
                borderRadius: "0.75rem",
                color: "var(--fg)",
                fontSize: "13px",
                padding: "8px 12px",
                boxShadow: "0 10px 30px rgba(0,0,0,0.25)",
              }}
              labelStyle={{
                color: "var(--fg-subtle)",
                fontSize: "12px",
                marginBottom: "2px",
              }}
              itemStyle={{ color: "var(--fg)" }}
              cursor={{ fill: "var(--surface)", fillOpacity: 0.6 }}
            />
            <Bar
              dataKey="count"
              name="Filings"
              radius={[8, 8, 0, 0]}
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
    </div>
  );
}
