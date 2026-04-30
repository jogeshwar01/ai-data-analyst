import { useEffect, useRef, useState } from "react";
import { Send, Loader2 } from "lucide-react";
import { API_URL, Message, ToolCall } from "../api";
import { streamSSE } from "../lib/sse";
import { cn } from "../lib/utils";

const SUGGESTIONS = [
  "Top 5 HCPs by TRx in the last 90 days",
  "Does call frequency correlate with TRx?",
  "Which territory has the highest TRx per HCP?",
  "Show MoM TRx growth per territory",
];

export function Chat({ seedInput }: { seedInput?: string }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (seedInput) setInput(seedInput);
  }, [seedInput]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function send(text: string) {
    if (!text.trim() || busy) return;
    setBusy(true);
    setInput("");

    const userMsg: Message = { role: "user", text };
    const asstMsg: Message = { role: "assistant", text: "", toolCalls: [] };
    setMessages((m) => [...m, userMsg, asstMsg]);

    try {
      await streamSSE(`${API_URL}/chat`, { message: text }, (event, data) => {
        setMessages((m) => {
          const last = m[m.length - 1];
          if (last.role !== "assistant") return m;
          const updated = { ...last, toolCalls: [...(last.toolCalls || [])] };

          if (event === "tool_start") {
            updated.toolCalls!.push({ name: data.name, input: data.input, status: "running" });
          } else if (event === "tool_end") {
            const idx = [...updated.toolCalls!].reverse().findIndex(
              (tc) => tc.name === data.name && tc.status === "running",
            );
            if (idx >= 0) {
              const realIdx = updated.toolCalls!.length - 1 - idx;
              updated.toolCalls![realIdx] = {
                ...updated.toolCalls![realIdx],
                output: data.output,
                status: "done",
              };
            }
          } else if (event === "token") {
            updated.text += data.text;
          } else if (event === "done") {
            if (!updated.text) updated.text = data.answer || "";
          } else if (event === "error") {
            updated.text = `Error: ${data.message}`;
          }
          return [...m.slice(0, -1), updated];
        });
      });
    } catch (e: any) {
      setMessages((m) => {
        const last = m[m.length - 1];
        return [...m.slice(0, -1), { ...last, text: `Error: ${e.message}` }];
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
        {messages.length === 0 && (
          <div className="max-w-2xl mx-auto mt-12">
            <h2 className="text-2xl font-semibold mb-2">Ask anything about the GAZYVA dataset.</h2>
            <p className="text-zinc-400 mb-6">
              I&apos;ll write SQL or Python, run it against Postgres, and explain the results.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="text-left px-4 py-3 rounded-lg border border-zinc-800 bg-zinc-900 hover:bg-zinc-800 transition text-sm"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <MessageBubble key={i} msg={m} />
        ))}
      </div>

      <div className="border-t border-zinc-800 px-6 py-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
          className="flex gap-2 max-w-3xl mx-auto"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about Rx volume, rep activity, payor mix…"
            className="flex-1 px-4 py-3 rounded-lg bg-zinc-900 border border-zinc-800 focus:outline-none focus:border-zinc-600 text-sm"
            disabled={busy}
          />
          <button
            type="submit"
            disabled={busy || !input.trim()}
            className="px-4 py-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-800 disabled:text-zinc-500 transition text-sm font-medium flex items-center gap-2"
          >
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </form>
      </div>
    </div>
  );
}

function MessageBubble({ msg }: { msg: Message }) {
  return (
    <div className={cn("max-w-3xl mx-auto", msg.role === "user" ? "ml-auto" : "")}>
      <div
        className={cn(
          "rounded-lg px-4 py-3",
          msg.role === "user" ? "bg-emerald-900/40 border border-emerald-800/50" : "bg-zinc-900 border border-zinc-800",
        )}
      >
        {msg.toolCalls && msg.toolCalls.length > 0 && (
          <div className="space-y-2 mb-3">
            {msg.toolCalls.map((tc, j) => (
              <ToolCallView key={j} tc={tc} />
            ))}
          </div>
        )}
        <div className="text-sm whitespace-pre-wrap leading-relaxed">{msg.text || (msg.role === "assistant" && <em className="text-zinc-500">thinking…</em>)}</div>
      </div>
    </div>
  );
}

function ToolCallView({ tc }: { tc: ToolCall }) {
  const [open, setOpen] = useState(false);
  const inputStr = typeof tc.input === "string" ? tc.input : JSON.stringify(tc.input);
  return (
    <div className="rounded border border-zinc-800 bg-zinc-950/40 text-xs">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full text-left px-3 py-2 flex items-center gap-2 hover:bg-zinc-900/60"
      >
        <span className={cn("w-1.5 h-1.5 rounded-full", tc.status === "running" ? "bg-yellow-400 animate-pulse" : "bg-emerald-500")} />
        <span className="font-mono text-zinc-300">{tc.name}</span>
        <span className="text-zinc-500 truncate flex-1">{inputStr?.slice(0, 80)}</span>
      </button>
      {open && (
        <div className="px-3 py-2 border-t border-zinc-800 space-y-2">
          <div>
            <div className="text-zinc-500 mb-1">input</div>
            <pre className="font-mono text-zinc-300 whitespace-pre-wrap break-all">{inputStr}</pre>
          </div>
          {tc.output && (
            <div>
              <div className="text-zinc-500 mb-1">output</div>
              <pre className="font-mono text-zinc-300 whitespace-pre-wrap break-all max-h-64 overflow-y-auto">{tc.output}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
