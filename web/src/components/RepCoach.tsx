import { useEffect, useState } from "react";
import { Loader2, ChevronDown } from "lucide-react";
import { API_URL } from "../api";

type Rep = { rep_id: number; name: string; region: string };
type Action = {
  priority: number;
  action: string;
  detail: string;
  metric?: Record<string, number>;
  hcps?: {
    name: string;
    specialty?: string;
    tier?: string;
    total_trx?: number;
    your_calls?: number;
    days_since?: number | string;
  }[];
};
type Coaching = {
  rep_id: number;
  rep_name: string;
  region: string;
  metrics: Record<string, number>;
  actions: Action[];
};

const PRIORITY_COLORS = [
  "bg-red-500/20 border-red-800",
  "bg-yellow-500/10 border-yellow-800",
  "bg-zinc-800 border-zinc-700",
];

export function RepCoach() {
  const [reps, setReps] = useState<Rep[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [coaching, setCoaching] = useState<Coaching | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/coach/reps`)
      .then((r) => r.json())
      .then((data) => {
        setReps(data);
        if (data.length) setSelectedId(data[0].rep_id);
      })
      .catch(console.error);
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setLoading(true);
    setCoaching(null);
    fetch(`${API_URL}/coach/${selectedId}`)
      .then((r) => r.json())
      .then(setCoaching)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [selectedId]);

  return (
    <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Rep Coaching</h2>
        <p className="text-zinc-400 text-sm mt-1">
          Next-best-actions based on call activity vs Rx potential.
        </p>
      </div>

      {/* Rep selector */}
      <div className="relative inline-block">
        <select
          value={selectedId ?? ""}
          onChange={(e) => setSelectedId(Number(e.target.value))}
          className="appearance-none bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-2 pr-10 text-sm focus:outline-none focus:border-zinc-500 cursor-pointer"
        >
          {reps.map((r) => (
            <option key={r.rep_id} value={r.rep_id}>
              {r.name} - {r.region}
            </option>
          ))}
        </select>
        <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500 pointer-events-none" />
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-zinc-500 text-sm">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading coaching data…
        </div>
      )}

      {coaching && (
        <>
          {/* Metric strip */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: "TRx / call", value: coaching.metrics.trx_per_call },
              {
                label: "Team avg TRx / call",
                value: coaching.metrics.peer_avg_trx_per_call,
              },
              {
                label: "HCPs in territory",
                value: coaching.metrics.total_hcps_in_territory,
              },
              { label: "HCPs called", value: coaching.metrics.hcps_called },
            ].map((m) => (
              <div
                key={m.label}
                className="rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-3"
              >
                <div className="text-xs text-zinc-500">{m.label}</div>
                <div className="text-xl font-semibold mt-1">{m.value}</div>
              </div>
            ))}
          </div>

          {/* Action cards */}
          <div className="space-y-4">
            {coaching.actions.map((a, i) => (
              <div
                key={i}
                className={`rounded-lg border p-4 ${PRIORITY_COLORS[i] ?? PRIORITY_COLORS[2]}`}
              >
                <div className="flex items-start gap-3">
                  <span className="shrink-0 w-6 h-6 rounded-full bg-zinc-800 border border-zinc-600 flex items-center justify-center text-xs font-semibold text-zinc-300">
                    {a.priority}
                  </span>
                  <div className="min-w-0">
                    <div className="font-medium text-sm">{a.action}</div>
                    <p className="text-xs text-zinc-400 mt-1 leading-relaxed">
                      {a.detail}
                    </p>
                    {a.hcps && a.hcps.length > 0 && (
                      <div className="mt-3 space-y-1">
                        {a.hcps.slice(0, 4).map((h, j) => (
                          <div
                            key={j}
                            className="flex items-center gap-2 text-xs text-zinc-400 font-mono"
                          >
                            <span className="text-zinc-300">{h.name}</span>
                            {h.tier && (
                              <span className="px-1 rounded bg-zinc-700 text-zinc-400">
                                T{h.tier}
                              </span>
                            )}
                            {h.total_trx !== undefined && (
                              <span>{h.total_trx} TRx</span>
                            )}
                            {h.your_calls !== undefined && (
                              <span>{h.your_calls} calls</span>
                            )}
                            {h.days_since !== undefined && (
                              <span className="text-yellow-500">
                                {h.days_since}d since contact
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
