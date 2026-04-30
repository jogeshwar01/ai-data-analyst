import {
  TrendingDown,
  UserMinus,
  ArrowLeftRight,
  AlertCircle,
  BarChart2,
  PieChart,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { useState } from "react";
import { cn } from "../lib/utils";

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  TrendingDown,
  UserMinus,
  ArrowLeftRight,
  AlertCircle,
  BarChart2,
  PieChart,
};

export type InsightData = {
  id: string;
  title: string;
  subtitle: string;
  icon: string;
  rows: Record<string, string | null>[];
  narrative: string;
  dig_deeper_prompt: string;
};

export function InsightCard({
  card,
  onDigDeeper,
}: {
  card: InsightData;
  onDigDeeper: (prompt: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const Icon = ICON_MAP[card.icon] ?? BarChart2;
  const hasRows = card.rows.length > 0;
  const cols = hasRows ? Object.keys(card.rows[0]) : [];

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 flex flex-col">
      <div className="px-4 pt-4 pb-3">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 p-2 rounded-md bg-zinc-800 shrink-0">
            <Icon className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="min-w-0">
            <div className="font-medium text-sm leading-tight">
              {card.title}
            </div>
            <div className="text-xs text-zinc-500 mt-0.5">{card.subtitle}</div>
          </div>
        </div>
        <p className="text-xs text-zinc-400 mt-3 leading-relaxed">
          {card.narrative}
        </p>
      </div>

      {hasRows && (
        <div className="border-t border-zinc-800">
          <button
            onClick={() => setExpanded((e) => !e)}
            className="w-full flex items-center justify-between px-4 py-2 text-xs text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50 transition"
          >
            <span>View data ({card.rows.length} rows)</span>
            {expanded ? (
              <ChevronUp className="w-3 h-3" />
            ) : (
              <ChevronDown className="w-3 h-3" />
            )}
          </button>
          {expanded && (
            <div className="overflow-x-auto border-t border-zinc-800">
              <table className="text-xs w-full border-collapse">
                <thead className="bg-zinc-800/50">
                  <tr>
                    {cols.map((c) => (
                      <th
                        key={c}
                        className="px-3 py-1.5 text-left font-medium text-zinc-300 border-b border-zinc-700"
                      >
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {card.rows.slice(0, 8).map((row, i) => (
                    <tr key={i} className="even:bg-zinc-800/20">
                      {cols.map((c) => (
                        <td
                          key={c}
                          className="px-3 py-1.5 text-zinc-400 font-mono"
                        >
                          {row[c] ?? <span className="text-zinc-600">-</span>}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <div className="mt-auto px-4 pb-4 pt-3">
        <button
          onClick={() => onDigDeeper(card.dig_deeper_prompt)}
          className="w-full text-xs px-3 py-2 rounded border border-zinc-700 hover:border-emerald-700 hover:bg-emerald-900/20 hover:text-emerald-400 transition text-zinc-400"
        >
          Dig deeper in chat →
        </button>
      </div>
    </div>
  );
}
