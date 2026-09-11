"use client";

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { money, type PipelineResponse } from "@/lib/api";

const PIE_COLORS = ["#0f6e56", "#1f8a6d", "#c45c26", "#8b6b4a", "#334155", "#5c6b76", "#a3b18a", "#bc6c25"];

export default function AnalyticsPanels({
  analytics,
}: {
  analytics: PipelineResponse["analytics"];
}) {
  if (!analytics) return null;

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <div className="rounded-2xl border border-[#d5cdc0] bg-[#fffcf7]/90 p-5 shadow-sm">
        <h3 className="mb-1 font-[family-name:var(--font-display)] text-lg">ZIP / locality ranking</h3>
        <p className="mb-4 text-xs text-[#5c6b76]">Median price by ZIP in the matched set</p>
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={analytics.by_zip.slice(0, 10)}
              layout="vertical"
              margin={{ left: 8, right: 12 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#e8e0d4" horizontal={false} />
              <XAxis type="number" tickFormatter={(v) => money(Number(v))} tick={{ fontSize: 11 }} />
              <YAxis
                type="category"
                dataKey="zip"
                width={58}
                tick={{ fontSize: 11 }}
              />
              <Tooltip
                formatter={(v: number) => money(v)}
                labelFormatter={(_, payload) => {
                  const p = payload?.[0]?.payload;
                  return p ? `${p.zip} · ${p.locality}` : "";
                }}
              />
              <Bar dataKey="median_price" name="Median price" fill="#0f6e56" radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-2xl border border-[#d5cdc0] bg-[#fffcf7]/90 p-5 shadow-sm">
        <h3 className="mb-1 font-[family-name:var(--font-display)] text-lg">Price tier mix</h3>
        <p className="mb-4 text-xs text-[#5c6b76]">
          ZIP-month rows by ZHVI band (bedroom counts are not in Zillow ZHVI / Redfin metro feeds)
        </p>
        <div className="h-72 w-full">
          {(analytics.by_price_tier?.length ?? 0) > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={analytics.by_price_tier}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e8e0d4" vertical={false} />
                <XAxis dataKey="tier" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={50} />
                <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  tickFormatter={(v) => money(Number(v))}
                  tick={{ fontSize: 11 }}
                />
                <Tooltip
                  formatter={(v: number, name: string) =>
                    name === "Median price" ? money(v) : v
                  }
                />
                <Bar yAxisId="left" dataKey="listings" name="ZIP-months" fill="rgba(20,33,43,0.45)" radius={[6, 6, 0, 0]} />
                <Bar yAxisId="right" dataKey="median_price" name="Median price" fill="#c45c26" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-full items-center justify-center rounded-xl border border-dashed border-[#d5cdc0] text-sm text-[#5c6b76]">
              No price-tier rows in this matched set.
            </div>
          )}
        </div>
      </div>

      <div className="rounded-2xl border border-[#d5cdc0] bg-[#fffcf7]/90 p-5 shadow-sm">
        <h3 className="mb-1 font-[family-name:var(--font-display)] text-lg">Price distribution</h3>
        <p className="mb-4 text-xs text-[#5c6b76]">Histogram of matched list prices</p>
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={analytics.price_histogram}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e8e0d4" vertical={false} />
              <XAxis dataKey="bucket" hide />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" name="Listings" fill="#1f8a6d" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-2xl border border-[#d5cdc0] bg-[#fffcf7]/90 p-5 shadow-sm">
        <h3 className="mb-1 font-[family-name:var(--font-display)] text-lg">Locality share</h3>
        <p className="mb-4 text-xs text-[#5c6b76]">Top localities in the matched sample</p>
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={analytics.locality_share}
                dataKey="listings"
                nameKey="locality"
                innerRadius={55}
                outerRadius={95}
                paddingAngle={2}
              >
                {analytics.locality_share.map((_, i) => (
                  <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          {analytics.locality_share.slice(0, 6).map((l, i) => (
            <span
              key={l.locality}
              className="rounded-full border border-[#d5cdc0] px-2.5 py-1 text-[11px] text-[#14212b]"
            >
              <span
                className="mr-1.5 inline-block h-2 w-2 rounded-full"
                style={{ background: PIE_COLORS[i % PIE_COLORS.length] }}
              />
              {l.locality} ({l.share_pct.toFixed(0)}%)
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
