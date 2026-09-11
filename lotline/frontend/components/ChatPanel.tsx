"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { SendHorizonal, Sparkles } from "lucide-react";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  interpretation?: string;
};

export default function ChatPanel({
  messages,
  loading,
  examples,
  onSend,
}: {
  messages: ChatMessage[];
  loading: boolean;
  examples: string[];
  onSend: (text: string) => void;
}) {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  function submit(e?: FormEvent) {
    e?.preventDefault();
    const t = input.trim();
    if (!t || loading) return;
    setInput("");
    onSend(t);
  }

  return (
    <div className="flex h-full min-h-[520px] flex-col rounded-2xl border border-[#d5cdc0] bg-[#fffcf7]/95 shadow-sm">
      <div className="border-b border-[#d5cdc0] px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-[#14212b]">
          <Sparkles className="h-4 w-4 text-[#0f6e56]" />
          Ask MetroMorph
        </div>
        <p className="text-xs text-[#5c6b76]">
          Natural language → multi-agent DFW housing trend analysis
        </p>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <div className="space-y-3">
            <p className="text-sm text-[#5c6b76]">
              Try a question, or pick an example:
            </p>
            <div className="flex flex-col gap-2">
              {examples.slice(0, 5).map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => onSend(q)}
                  className="rounded-xl border border-[#d5cdc0] bg-white/80 px-3 py-2 text-left text-sm text-[#14212b] transition hover:border-[#0f6e56] hover:bg-[#eef6f2]"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m) => (
          <div
            key={m.id}
            className={`max-w-[92%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
              m.role === "user"
                ? "ml-auto bg-[#0f6e56] text-white"
                : "bg-white border border-[#d5cdc0] text-[#14212b]"
            }`}
          >
            <div className="whitespace-pre-wrap">{m.text}</div>
            {m.interpretation && (
              <div className="mt-2 border-t border-[#e8e0d4] pt-2 text-xs text-[#5c6b76]">
                {m.interpretation}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="rounded-2xl border border-[#d5cdc0] bg-white px-3.5 py-2.5 text-sm text-[#5c6b76]">
            Agents running: Criteria → Scanner → Analyst → Critic…
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={submit} className="border-t border-[#d5cdc0] p-3">
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            rows={2}
            placeholder="e.g. 3-bed homes under $450k in Plano last 12 months"
            className="min-h-[56px] flex-1 resize-none rounded-xl border border-[#d5cdc0] bg-white px-3 py-2 text-sm outline-none ring-[#0f6e56] focus:ring-2"
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-[#0f6e56] text-white transition hover:bg-[#0c5a46] disabled:opacity-40"
          >
            <SendHorizonal className="h-4 w-4" />
          </button>
        </div>
      </form>
    </div>
  );
}
