"use client";

import { money, type PipelineResponse, type Snapshot } from "@/lib/api";
import TrendCharts from "@/components/TrendCharts";
import AnalyticsPanels from "@/components/AnalyticsPanels";
import AgentTraceViewer from "@/components/AgentTraceViewer";
import MrPanel from "@/components/MrPanel";

type Tab = "trends" | "agents" | "breakdown" | "listings" | "market" | "mrs";

export default function SideAnalytics({
  tab,
  setTab,
  result,
  snapshot,
}: {
  tab: Tab;
  setTab: (t: Tab) => void;
  result: PipelineResponse | null;
  snapshot: Snapshot | null;
}) {
  const tabs: { id: Tab; label: string }[] = [
    { id: "trends", label: "Trends" },
    { id: "agents", label: "Agents" },
    { id: "breakdown", label: "Breakdown" },
    { id: "listings", label: "ZIP panel" },
    { id: "market", label: "Market" },
    { id: "mrs", label: "MR tests" },
  ];

  const kpis = result?.analytics.kpis;
  const yoy = result?.trend.yoy_pct_change;

  return (
    <div className="flex h-full min-h-[520px] flex-col rounded-2xl border border-[#d5cdc0] bg-[#fffcf7]/80 shadow-sm">
      <div className="flex flex-wrap gap-1 border-b border-[#d5cdc0] p-2">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
              tab === t.id
                ? "bg-[#0f6e56] text-white"
                : "text-[#5c6b76] hover:bg-white"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {result && (
          <div className="mb-4 grid grid-cols-2 gap-3 xl:grid-cols-4">
            <Kpi label="Matched" value={String(result.filtered_count)} hint={`cov ${result.trend.coverage_score.toFixed(2)}`} />
            <Kpi
              label="Latest median"
              value={money(result.monthly.at(-1)?.median_price || 0)}
              hint={yoy != null ? `${yoy >= 0 ? "+" : ""}${yoy.toFixed(1)}% YoY` : "—"}
            />
            <Kpi label="$/sqft" value={money(result.monthly.at(-1)?.median_price_per_sqft || 0)} hint="latest month" />
            <Kpi label="ZIPs used" value={String(kpis?.zips ?? "—")} hint={`mode ${result.mode}`} />
          </div>
        )}

        {tab === "trends" && (
          <div className="space-y-3">
            {result ? (
              <>
                <h2 className="font-[family-name:var(--font-display)] text-xl text-[#14212b]">
                  {result.headline}
                </h2>
                <p className="text-sm text-[#5c6b76]">{result.narrative}</p>
                <TrendCharts monthly={result.monthly} />
              </>
            ) : snapshot ? (
              <TrendCharts
                monthly={snapshot.monthly.map((m) => ({
                  month: m.list_month,
                  median_price: m.median_price,
                  median_price_per_sqft: 0,
                  active_count: m.active_count,
                  mom_pct_change: null,
                }))}
              />
            ) : (
              <Empty />
            )}
          </div>
        )}

        {tab === "agents" && (
          <AgentTraceViewer steps={result?.agent_steps || []} />
        )}

        {tab === "breakdown" && result && (
          <AnalyticsPanels analytics={result.analytics} />
        )}
        {tab === "breakdown" && !result && <Empty text="Ask a question to unlock matched-set breakdowns." />}

        {tab === "listings" && (
          <div className="overflow-auto rounded-xl border border-[#d5cdc0]">
            {result?.listings_preview?.length ? (
              <table className="min-w-full text-left text-xs">
                <thead className="bg-[#14212b] text-white">
                  <tr>
                    {["listing_id", "price", "ppsf", "zip", "locality", "list_month", "data_origin"].map((h) => (
                      <th key={h} className="px-3 py-2 font-medium">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.listings_preview.map((row, i) => (
                    <tr key={i} className="odd:bg-white even:bg-[#f7f3ea]">
                      {["listing_id", "price", "ppsf", "zip", "locality", "list_month", "data_origin"].map((h) => (
                        <td key={h} className="px-3 py-2 text-[#14212b]">
                          {String(row[h] ?? "")}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <Empty text="No matched ZIP-month rows yet." />
            )}
          </div>
        )}

        {tab === "market" && snapshot && (
          <div className="space-y-5">
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <Kpi label="ZIP-month rows" value={snapshot.total_listings.toLocaleString()} />
              <Kpi label="ZIP coverage" value={String(snapshot.zip_count)} />
              <Kpi label="Months" value={String(snapshot.month_span)} />
              <Kpi label="Median ZHVI" value={money(snapshot.median_price)} />
            </div>
            <AnalyticsPanels
              analytics={{
                kpis: {
                  listings: snapshot.total_listings,
                  median_price: snapshot.median_price,
                  median_ppsf: 0,
                  median_sqft: 0,
                  zips: snapshot.zip_count,
                  localities: snapshot.localities.length,
                },
                by_zip: snapshot.top_zips,
                by_beds: snapshot.beds,
                by_price_tier: snapshot.price_tiers || [],
                price_histogram: snapshot.price_hist,
                locality_share: snapshot.localities,
              }}
            />
          </div>
        )}

        {tab === "mrs" && <MrPanel />}
      </div>
    </div>
  );
}

function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-[#d5cdc0] bg-white/80 p-3">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-[#5c6b76]">{label}</div>
      <div className="mt-1 font-[family-name:var(--font-display)] text-2xl text-[#14212b]">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-[#5c6b76]">{hint}</div>}
    </div>
  );
}

function Empty({ text = "Waiting for analysis…" }: { text?: string }) {
  return (
    <div className="rounded-xl border border-dashed border-[#d5cdc0] p-8 text-center text-sm text-[#5c6b76]">
      {text}
    </div>
  );
}
