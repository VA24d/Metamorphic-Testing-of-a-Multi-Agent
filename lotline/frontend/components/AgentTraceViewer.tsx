"use client";

import { useMemo, useState } from "react";
import type { AgentStep } from "@/lib/api";

const ORDER = ["Criteria", "Scanner", "Analyst", "Critic", "Report"] as const;

function badgeClass(status: string) {
  if (status === "pass") return "bg-emerald-100 text-emerald-800";
  if (status === "revise") return "bg-amber-100 text-amber-900";
  return "bg-slate-100 text-slate-700";
}

export default function AgentTraceViewer({
  steps,
  emptyText = "Agent timeline will appear after you ask a question.",
}: {
  steps: AgentStep[];
  emptyText?: string;
}) {
  const [openIdx, setOpenIdx] = useState<number | null>(0);

  const latest = useMemo(() => {
    const map: Record<string, AgentStep> = {};
    for (const s of steps) map[s.agent] = s;
    return map;
  }, [steps]);

  if (!steps?.length) {
    return (
      <div className="rounded-2xl border border-dashed border-[#d5cdc0] p-6 text-sm text-[#5c6b76]">
        {emptyText}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {ORDER.map((name) => {
          const s = latest[name];
          return (
            <div
              key={name}
              className="rounded-2xl border border-[#d5cdc0] bg-[#fffcf7] p-3 shadow-sm"
            >
              <div className="flex items-center justify-between gap-2">
                <div className="text-sm font-semibold text-[#0f6e56]">{name}</div>
                {s && (
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${badgeClass(s.status)}`}>
                    {s.status}
                  </span>
                )}
              </div>
              <p className="mt-2 line-clamp-4 text-xs leading-relaxed text-[#334155]">
                {s?.summary || "—"}
              </p>
              {s && (
                <p className="mt-2 text-[10px] uppercase tracking-wide text-[#5c6b76]">
                  iteration {s.iteration}
                </p>
              )}
            </div>
          );
        })}
      </div>

      <div className="rounded-2xl border border-[#d5cdc0] bg-[#122028] p-4 text-[#d7ece4]">
        <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-[#9fbfb4]">
          Full loop timeline (feedback visible here)
        </div>
        <div className="space-y-2">
          {steps.map((s, i) => (
            <button
              key={`${s.agent}-${s.iteration}-${i}`}
              type="button"
              onClick={() => setOpenIdx(openIdx === i ? null : i)}
              className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-left transition hover:bg-white/10"
            >
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="font-mono text-[#9fbfb4]">#{i + 1}</span>
                <span className="font-semibold text-white">{s.agent}</span>
                <span className="text-[#9fbfb4]">iter {s.iteration}</span>
                <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${badgeClass(s.status)}`}>
                  {s.status}
                </span>
              </div>
              <div className="mt-1 text-sm text-[#e8f5ef]">{s.summary}</div>
              {openIdx === i && (
                <pre className="mt-2 overflow-auto rounded-lg bg-black/30 p-2 text-[11px] text-[#b7d5c9]">
                  {JSON.stringify(s.details, null, 2)}
                </pre>
              )}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
