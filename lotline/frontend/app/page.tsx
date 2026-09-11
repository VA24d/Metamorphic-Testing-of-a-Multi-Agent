"use client";

import { useEffect, useState } from "react";
import { Activity, Database, Cpu } from "lucide-react";
import ChatPanel, { type ChatMessage } from "@/components/ChatPanel";
import SideAnalytics from "@/components/SideAnalytics";
import {
  chatAsk,
  fetchHealth,
  fetchSnapshot,
  type PipelineResponse,
  type Snapshot,
} from "@/lib/api";

type Tab = "trends" | "agents" | "breakdown" | "listings" | "market" | "mrs";

export default function HomePage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState("auto");
  const [health, setHealth] = useState<any>(null);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [result, setResult] = useState<PipelineResponse | null>(null);
  const [tab, setTab] = useState<Tab>("trends");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch(() => setError("Backend offline — start FastAPI on :8000"));
    fetchSnapshot()
      .then(setSnapshot)
      .catch(() => undefined);
  }, []);

  async function onSend(text: string) {
    setError(null);
    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      text,
    };
    setMessages((m) => [...m, userMsg]);
    setLoading(true);
    try {
      const data = await chatAsk(text, mode, 3);
      setResult(data);
      setTab("trends");
      setMessages((m) => [
        ...m,
        {
          id: `a-${Date.now()}`,
          role: "assistant",
          text: data.headline,
          interpretation: data.interpretation,
        },
      ]);
    } catch (e: any) {
      setError(e?.message || "Request failed");
      setMessages((m) => [
        ...m,
        {
          id: `a-${Date.now()}`,
          role: "assistant",
          text: "Sorry — I could not complete that analysis. Is the API running on port 8000?",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-[1600px] flex-col px-4 py-5 md:px-6">
      <header className="mb-5 flex flex-wrap items-end justify-between gap-4 border-b border-[#d5cdc0] pb-4">
        <div>
          <h1 className="font-[family-name:var(--font-display)] text-4xl tracking-tight text-[#14212b]">
            Metro<span className="text-[#0f6e56]">Morph</span>
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-[#5c6b76]">
            Metamorphic testing of a multi-agent DFW housing-trends system — ask in plain English,
            inspect Critic feedback loops, explore analytics, and run MR tests in the UI.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-[#d5cdc0] bg-white/80 px-3 py-1.5">
            <Database className="h-3.5 w-3.5 text-[#0f6e56]" />
            {health?.listings?.toLocaleString?.() ?? "—"} listings
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-[#d5cdc0] bg-white/80 px-3 py-1.5">
            <Cpu className="h-3.5 w-3.5 text-[#c45c26]" />
            Ollama {health?.ollama ? "online" : "offline"}
          </span>
          <label className="inline-flex items-center gap-2 rounded-full border border-[#d5cdc0] bg-white/80 px-3 py-1.5">
            <Activity className="h-3.5 w-3.5" />
            Mode
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value)}
              className="bg-transparent text-[#14212b] outline-none"
            >
              <option value="auto">auto</option>
              <option value="mock">mock</option>
              <option value="ollama">ollama</option>
            </select>
          </label>
        </div>
      </header>

      {error && (
        <div className="mb-4 rounded-xl border border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-900">
          {error}
        </div>
      )}

      <div className="grid flex-1 gap-4 lg:grid-cols-[380px_minmax(0,1fr)] xl:grid-cols-[400px_minmax(0,1fr)]">
        <ChatPanel
          messages={messages}
          loading={loading}
          examples={health?.examples || []}
          onSend={onSend}
        />
        <SideAnalytics tab={tab} setTab={setTab} result={result} snapshot={snapshot} />
      </div>
    </div>
  );
}
