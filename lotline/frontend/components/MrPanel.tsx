"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  fetchMrList,
  fetchMrSummary,
  runMrs,
  type MrCase,
  type MrCatalogEntry,
  type MrListResponse,
  type MrRunResponse,
  type MrResultRow,
  type MrSeries,
  type MrAgentPipeline,
} from "@/lib/api";
import AgentTraceViewer from "@/components/AgentTraceViewer";

export default function MrPanel() {
  const [catalogInfo, setCatalogInfo] = useState<MrListResponse | null>(null);
  const [payload, setPayload] = useState<MrRunResponse | null>(null);
  const [n, setN] = useState(10);
  const [seed, setSeed] = useState(7);
  const [runningId, setRunningId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [inspect, setInspect] = useState<{ mrId: string; caseIdx: number } | null>(null);
  const inspectRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    fetchMrList()
      .then(setCatalogInfo)
      .catch(() => undefined);
    fetchMrSummary()
      .then((data) => {
        if (data.available) setPayload(data);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!expanded) return;
    const t = window.setTimeout(() => {
      inspectRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);
    return () => window.clearTimeout(t);
  }, [expanded, inspect?.caseIdx, payload]);

  async function onRun(mrId: string | "ALL") {
    setError(null);
    setRunningId(mrId);
    try {
      const mrs = mrId === "ALL" ? null : [mrId];
      const data = await runMrs({
        n,
        seed,
        mrs,
        verbose: true,
        agent_trace_cases: Math.min(Math.max(n, 1), 5),
      });
      setPayload(data);
      const first = data.results?.[0];
      if (first) {
        setExpanded(first.mr_id);
        setInspect({ mrId: first.mr_id, caseIdx: 0 });
      }
    } catch (e: any) {
      setError(e?.message || "MR run failed");
    } finally {
      setRunningId(null);
    }
  }

  function openInspect(mrId: string, caseIdx = 0) {
    setExpanded(mrId);
    setInspect({ mrId, caseIdx });
  }

  const resultsById = useMemo(() => {
    const map = new Map<string, MrResultRow>();
    for (const r of payload?.results || []) map.set(r.mr_id, r);
    return map;
  }, [payload]);

  const expandedRow = expanded ? resultsById.get(expanded) : undefined;
  const cases = expandedRow?.cases;
  const caseIdx = inspect?.mrId === expanded && inspect ? inspect.caseIdx : 0;
  const activeCase: MrCase | null =
    cases && cases.length > 0
      ? cases[Math.min(caseIdx, cases.length - 1)] ?? cases[0]
      : null;

  const catalog = catalogInfo?.catalog || [];

  return (
    <div className="space-y-4">
      <div>
        <h2 className="font-[family-name:var(--font-display)] text-xl text-[#14212b]">
          Metamorphic relations
        </h2>
        <p className="mt-1 text-sm text-[#5c6b76]">
          Run all 8 MRs or one transform at a time. Transforms (reorder, duplicate, scale, …)
          happen only in memory — frozen ZHVI/Redfin CSVs are never modified. Each case
          returns metrics for the check (source vs follow-up).
        </p>
      </div>

      <div className="rounded-xl border border-[#d5cdc0] bg-white/80 p-3 text-xs leading-relaxed text-[#5c6b76]">
        <div className="font-semibold uppercase tracking-wide text-[#14212b]">Data under test</div>
        <p className="mt-1">
          {catalogInfo?.data?.panel || "Frozen Zillow ZHVI + Redfin Dallas metro"} ·{" "}
          {catalogInfo?.data?.rows ?? "—"} ZIP-month rows · {catalogInfo?.data?.zips ?? 16} ZIPs.
          Criteria seed randomizes queries only.{" "}
          <span className="font-medium text-[#14212b]">
            Safe to re-run anytime — source panel stays unchanged.
          </span>
        </p>
        {catalogInfo?.metrics_glossary && (
          <div className="mt-2 grid gap-1 md:grid-cols-2">
            {Object.entries(catalogInfo.metrics_glossary).map(([k, v]) => (
              <div key={k}>
                <span className="font-medium text-[#14212b]">{k}</span> — {v}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-[#d5cdc0] bg-white/80 p-3">
        <label className="text-xs font-semibold text-[#5c6b76]">
          Base queries (n)
          <input
            type="number"
            min={1}
            max={50}
            value={n}
            onChange={(e) => setN(Number(e.target.value) || 1)}
            className="mt-1 block w-20 rounded-lg border border-[#d5cdc0] bg-white px-2 py-1.5 text-sm"
          />
        </label>
        <label className="text-xs font-semibold text-[#5c6b76]">
          Criteria seed
          <input
            type="number"
            value={seed}
            onChange={(e) => setSeed(Number(e.target.value) || 0)}
            className="mt-1 block w-20 rounded-lg border border-[#d5cdc0] bg-white px-2 py-1.5 text-sm"
          />
        </label>
        <button
          type="button"
          onClick={() => onRun("ALL")}
          disabled={!!runningId}
          className="rounded-lg bg-[#0f6e56] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
        >
          {runningId === "ALL" ? "Running all…" : "Run all 8 MRs"}
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {error}
        </div>
      )}

      {expanded && (
        <div ref={inspectRef} className="scroll-mt-4">
          {activeCase && cases && cases.length > 0 ? (
            <CaseInspector
              mrId={expanded}
              cases={cases}
              selected={activeCase.case}
              onSelect={(idx) => openInspect(expanded, idx)}
              active={activeCase}
              onClose={() => {
                setExpanded(null);
                setInspect(null);
              }}
            />
          ) : (
            <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">
              <div className="font-semibold">{expanded} — no case metrics in this payload</div>
              <p className="mt-1 text-xs">
                Summary rates are present, but per-case A/B metrics were not saved. Click{" "}
                <span className="font-semibold">Run</span> on this MR (or Run all 8) to regenerate
                detailed metrics, then open Metrics again.
              </p>
              <button
                type="button"
                className="mt-3 rounded-lg bg-[#14212b] px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                disabled={!!runningId}
                onClick={() => onRun(expanded)}
              >
                {runningId === expanded ? "Running…" : `Re-run ${expanded}`}
              </button>
            </div>
          )}
        </div>
      )}

      <div className="grid gap-2 sm:grid-cols-2">
        {catalog.map((entry) => (
          <MrCard
            key={entry.id}
            entry={entry}
            result={resultsById.get(entry.id)}
            busy={runningId === entry.id}
            disabled={!!runningId}
            onRun={() => onRun(entry.id)}
            onOpenCases={() => openInspect(entry.id, 0)}
          />
        ))}
      </div>

      {payload?.smoke && (
        <div className="text-xs text-[#5c6b76]">
          Smoke:{" "}
          <span className={payload.smoke.passed ? "text-[#0f6e56]" : "text-[#c45c26]"}>
            {payload.smoke.passed ? "passed" : "failed"}
          </span>
          {payload.saved_to ? ` · saved ${payload.saved_to}` : ""}
        </div>
      )}

      {(payload?.results?.length ?? 0) > 0 && (
        <div className="overflow-auto rounded-xl border border-[#d5cdc0]">
          <table className="min-w-full text-left text-xs">
            <thead className="bg-[#14212b] text-white">
              <tr>
                {["MR", "n", "viol", "rate", "95% CI", "inspect"].map((h) => (
                  <th key={h} className="px-3 py-2 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(payload?.results || []).map((row) => {
                const [lo, hi] = row.ci95 || [0, 0];
                const ok = row.violations === 0;
                const hasCases = (row.cases?.length ?? 0) > 0;
                return (
                  <tr key={row.mr_id} className="odd:bg-white even:bg-[#f7f3ea]">
                    <td className="px-3 py-2 font-medium">{row.mr_id}</td>
                    <td className="px-3 py-2">{row.n}</td>
                    <td className={`px-3 py-2 font-semibold ${ok ? "text-[#0f6e56]" : "text-[#c45c26]"}`}>
                      {row.violations}
                    </td>
                    <td className="px-3 py-2">{row.violation_rate.toFixed(3)}</td>
                    <td className="px-3 py-2">
                      [{lo.toFixed(3)}, {hi.toFixed(3)}]
                    </td>
                    <td className="px-3 py-2">
                      <button
                        type="button"
                        className="text-[#0f6e56] underline"
                        onClick={() => openInspect(row.mr_id, 0)}
                      >
                        {hasCases ? "Metrics" : "Metrics (re-run needed)"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function MrCard({
  entry,
  result,
  busy,
  disabled,
  onRun,
  onOpenCases,
}: {
  entry: MrCatalogEntry;
  result?: MrResultRow;
  busy: boolean;
  disabled: boolean;
  onRun: () => void;
  onOpenCases: () => void;
}) {
  const hasCases = (result?.cases?.length ?? 0) > 0;
  return (
    <div className="rounded-xl border border-[#d5cdc0] bg-white/90 p-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-wide text-[#5c6b76]">
            {entry.family}
          </div>
          <div className="font-semibold text-[#14212b]">
            {entry.id} · {entry.title}
          </div>
        </div>
        {result && (
          <span
            className={`rounded px-2 py-0.5 text-[10px] font-bold ${
              result.violations === 0 ? "bg-emerald-50 text-[#0f6e56]" : "bg-orange-50 text-[#c45c26]"
            }`}
          >
            {result.violations}/{result.n} viol
          </span>
        )}
      </div>
      <p className="mt-1 text-xs text-[#5c6b76]">
        <span className="font-medium text-[#14212b]">Transform:</span> {entry.transform}
      </p>
      <p className="mt-0.5 text-xs text-[#5c6b76]">
        <span className="font-medium text-[#14212b]">Metrics:</span> {entry.metrics.join(", ")}
      </p>
      <p className="mt-0.5 text-xs text-[#5c6b76]">
        <span className="font-medium text-[#14212b]">Expect:</span> {entry.expect}
      </p>
      {(entry.agents?.length || 0) > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {entry.agents!.map((a) => (
            <span
              key={a}
              className="rounded-full border border-[#0f6e56]/40 bg-[#0f6e56]/10 px-2 py-0.5 text-[10px] font-semibold text-[#0f6e56]"
            >
              {a}
            </span>
          ))}
        </div>
      )}
      {entry.agent_rationale && (
        <p className="mt-1 text-[11px] leading-snug text-[#5c6b76]">{entry.agent_rationale}</p>
      )}
      <div className="mt-2 flex gap-2">
        <button
          type="button"
          onClick={onRun}
          disabled={disabled}
          className="rounded-lg bg-[#14212b] px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
        >
          {busy ? "Running…" : "Run"}
        </button>
        {result && (
          <button
            type="button"
            onClick={onOpenCases}
            className="rounded-lg border border-[#d5cdc0] px-3 py-1.5 text-xs font-semibold text-[#14212b]"
          >
            {hasCases ? "View metrics" : "Open inspect"}
          </button>
        )}
      </div>
    </div>
  );
}

function CaseInspector({
  mrId,
  cases,
  selected,
  onSelect,
  active,
  onClose,
}: {
  mrId: string;
  cases: MrCase[];
  selected: number;
  onSelect: (idx: number) => void;
  active: MrCase;
  onClose: () => void;
}) {
  const m = active.metrics || {};
  const checks = m.checks || {};
  const agents = (m.agents as string[]) || [];
  const rationale = String(m.agent_rationale || "");
  const pipeline = m.agent_pipeline as MrAgentPipeline | undefined;
  return (
    <div className="space-y-3 rounded-xl border-2 border-[#0f6e56] bg-[#fffcf7] p-3 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-[family-name:var(--font-display)] text-lg text-[#14212b]">
          {mrId} — case metrics
        </h3>
        <div className="flex items-center gap-2">
          <select
            value={selected}
            onChange={(e) => onSelect(Number(e.target.value))}
            className="rounded-lg border border-[#d5cdc0] bg-white px-2 py-1 text-xs"
          >
            {cases.map((c) => (
              <option key={c.case} value={c.case}>
                Case {c.case} · {c.passed ? "PASS" : "FAIL"}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-[#d5cdc0] px-2 py-1 text-xs text-[#5c6b76]"
          >
            Close
          </button>
        </div>
      </div>

      <div
        className={`text-sm font-semibold ${active.passed ? "text-[#0f6e56]" : "text-[#c45c26]"}`}
      >
        {active.passed ? "PASS" : "FAIL"} — {active.detail}
      </div>

      {active.criteria && (
        <div className="text-xs text-[#5c6b76]">
          Query: ${Number(active.criteria.price_min).toLocaleString()}–$
          {Number(active.criteria.price_max).toLocaleString()} · ZIPs{" "}
          {(active.criteria.zips || []).slice(0, 6).join(", ")}
          {(active.criteria.zips || []).length > 6 ? "…" : ""} · window{" "}
          {active.criteria.window_end}
        </div>
      )}

      <div className="text-xs text-[#5c6b76]">
        <div>
          <span className="font-medium text-[#14212b]">Transform:</span> {String(m.transform || "—")}
        </div>
        <div>
          <span className="font-medium text-[#14212b]">Expect:</span> {String(m.expect || "—")}
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {Object.entries(checks).map(([k, v]) => (
          <span
            key={k}
            className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
              v ? "bg-emerald-50 text-[#0f6e56]" : "bg-orange-50 text-[#c45c26]"
            }`}
          >
            {k}: {v ? "ok" : "fail"}
          </span>
        ))}
      </div>

      <div className="rounded-xl border border-[#d5cdc0] bg-white/90 p-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-[#14212b]">
          Agents under test
        </div>
        <div className="mt-2 flex flex-wrap gap-1">
          {(agents.length ? agents : ["(see catalog)"]).map((a) => (
            <span
              key={a}
              className="rounded-full border border-[#0f6e56]/40 bg-[#0f6e56]/10 px-2 py-0.5 text-[10px] font-semibold text-[#0f6e56]"
            >
              {a}
            </span>
          ))}
        </div>
        {rationale && <p className="mt-2 text-xs text-[#5c6b76]">{rationale}</p>}
        <p className="mt-2 text-[11px] text-[#5c6b76]">
          MR pass/fail uses deterministic Analyst metrics. The timeline below is the same
          mock multi-agent loop (Criteria → Scanner → Analyst → Critic → Report) for this
          case’s query.
        </p>
        {pipeline?.agent_steps?.length ? (
          <div className="mt-3">
            <div className="mb-2 text-xs text-[#5c6b76]">
              Pipeline mode <span className="font-semibold text-[#14212b]">{pipeline.mode}</span>
              {" · "}
              {pipeline.iterations} iteration(s)
              {pipeline.headline ? ` · ${pipeline.headline}` : ""}
            </div>
            <AgentTraceViewer
              steps={pipeline.agent_steps}
              emptyText="No agent steps captured for this case."
            />
          </div>
        ) : (
          <div className="mt-3 rounded-lg border border-dashed border-[#d5cdc0] p-3 text-xs text-[#5c6b76]">
            No agent timeline on this case (traces are attached for the first few cases).
            Pick an earlier case in the dropdown, or re-run with a smaller n.
          </div>
        )}
      </div>

      {m.source && m.followup ? (
        <MetricsCompare source={m.source as MrSeries} followup={m.followup as MrSeries} />
      ) : (
        <div className="rounded-lg border border-dashed border-[#d5cdc0] p-3 text-xs text-[#5c6b76]">
          No source/follow-up series on this case. Re-run the MR to capture A/B monthly metrics.
        </div>
      )}
    </div>
  );
}

function MetricsCompare({ source, followup }: { source: MrSeries; followup: MrSeries }) {
  const months = source.months?.length ? source.months : followup.months || [];
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
        <MiniKpi label="Source listings" value={String(source.total_listings ?? "—")} />
        <MiniKpi label="Follow-up listings" value={String(followup.total_listings ?? "—")} />
        <MiniKpi
          label="Source YoY %"
          value={source.yoy_pct_change == null ? "—" : Number(source.yoy_pct_change).toFixed(3)}
        />
        <MiniKpi
          label="Follow-up YoY %"
          value={followup.yoy_pct_change == null ? "—" : Number(followup.yoy_pct_change).toFixed(3)}
        />
      </div>
      <div className="max-h-64 overflow-auto rounded-lg border border-[#d5cdc0]">
        <table className="min-w-full text-left text-[11px]">
          <thead className="sticky top-0 bg-[#14212b] text-white">
            <tr>
              <th className="px-2 py-1.5">Month</th>
              <th className="px-2 py-1.5">Price A</th>
              <th className="px-2 py-1.5">Price B</th>
              <th className="px-2 py-1.5">Δ price</th>
              <th className="px-2 py-1.5">$/sqft A</th>
              <th className="px-2 py-1.5">$/sqft B</th>
              <th className="px-2 py-1.5">Count A</th>
              <th className="px-2 py-1.5">Count B</th>
            </tr>
          </thead>
          <tbody>
            {months.map((month, i) => {
              const pa = source.median_price?.[i] ?? 0;
              const pb = followup.median_price?.[i] ?? 0;
              const ca = source.active_count?.[i] ?? 0;
              const cb = followup.active_count?.[i] ?? 0;
              return (
                <tr key={`${month}-${i}`} className="odd:bg-white even:bg-[#f7f3ea]">
                  <td className="px-2 py-1 font-medium">{month}</td>
                  <td className="px-2 py-1">{fmtMoney(pa)}</td>
                  <td className="px-2 py-1">{fmtMoney(pb)}</td>
                  <td className="px-2 py-1">{fmtMoney(pb - pa)}</td>
                  <td className="px-2 py-1">{Number(source.median_ppsf?.[i] ?? 0).toFixed(2)}</td>
                  <td className="px-2 py-1">{Number(followup.median_ppsf?.[i] ?? 0).toFixed(2)}</td>
                  <td className="px-2 py-1">{ca}</td>
                  <td className="px-2 py-1">{cb}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function MiniKpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[#d5cdc0] bg-white px-2 py-1.5">
      <div className="text-[10px] uppercase text-[#5c6b76]">{label}</div>
      <div className="font-semibold text-[#14212b]">{value}</div>
    </div>
  );
}

function fmtMoney(n: number) {
  if (!Number.isFinite(n)) return "—";
  if (Math.abs(n) >= 1000) return `$${(n / 1000).toFixed(1)}k`;
  return `$${n.toFixed(0)}`;
}
