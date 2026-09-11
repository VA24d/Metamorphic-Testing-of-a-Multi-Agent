"use client";

import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  AreaChart,
  Area,
} from "recharts";
import { money, type PipelineResponse } from "@/lib/api";

export default function TrendCharts({
  monthly,
}: {
  monthly: PipelineResponse["monthly"];
}) {
  if (!monthly?.length) {
    return (
      <div className="h-64 rounded-2xl border border-[#d5cdc0] bg-white/70 flex items-center justify-center text-[#5c6b76] text-sm">
        No trend series yet — ask a question in chat.
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="rounded-2xl border border-[#d5cdc0] bg-[#fffcf7]/90 p-5 shadow-sm">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
          <div>
            <h3 className="font-[family-name:var(--font-display)] text-lg text-[#14212b]">
              12-month median price & inventory
            </h3>
            <p className="text-xs text-[#5c6b76]">
              Real Zillow ZHVI (ZIP) + Redfin $/sqft · month-over-month in tooltip
            </p>
          </div>
        </div>
        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={monthly} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e8e0d4" vertical={false} />
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#5c6b76" }} stroke="#d5cdc0" />
              <YAxis
                yAxisId="left"
                tickFormatter={(v) => money(Number(v))}
                tick={{ fontSize: 11, fill: "#5c6b76" }}
                stroke="#d5cdc0"
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                tick={{ fontSize: 11, fill: "#5c6b76" }}
                stroke="#d5cdc0"
              />
              <Tooltip
                contentStyle={{
                  borderRadius: 12,
                  borderColor: "#d5cdc0",
                  background: "#fffcf7",
                }}
                formatter={(value: number, name: string) => {
                  if (name.includes("price") || name.includes("Median")) return [money(value), name];
                  if (name.includes("MoM")) return [`${value?.toFixed?.(2) ?? value}%`, name];
                  return [value, name];
                }}
              />
              <Legend />
              <Bar
                yAxisId="right"
                dataKey="active_count"
                name="Active listings"
                fill="rgba(20,33,43,0.35)"
                radius={[4, 4, 0, 0]}
              />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="median_price"
                name="Median price"
                stroke="#0f6e56"
                strokeWidth={3}
                dot={{ r: 3 }}
              />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="median_price_per_sqft"
                name="$/sqft"
                stroke="#c45c26"
                strokeWidth={2}
                strokeDasharray="5 4"
                dot={{ r: 2 }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-2xl border border-[#d5cdc0] bg-[#fffcf7]/90 p-5 shadow-sm">
        <h3 className="mb-3 font-[family-name:var(--font-display)] text-lg text-[#14212b]">
          Month-over-month % change
        </h3>
        <div className="h-52 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={monthly}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e8e0d4" vertical={false} />
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#5c6b76" }} />
              <YAxis tick={{ fontSize: 11, fill: "#5c6b76" }} unit="%" />
              <Tooltip />
              <Area
                type="monotone"
                dataKey="mom_pct_change"
                name="MoM %"
                stroke="#0f6e56"
                fill="rgba(15,110,86,0.18)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
