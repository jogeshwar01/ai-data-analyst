import { useEffect, useRef, useState } from "react";
import { Activity, MessageSquare, Lightbulb, Users, Loader2 } from "lucide-react";
import { Chat } from "./components/Chat";
import { InsightCard, InsightData } from "./components/InsightCard";
import { RepCoach } from "./components/RepCoach";
import { API_URL } from "./api";
import { cn } from "./lib/utils";

type Tab = "chat" | "insights" | "coach";

export default function App() {
  const [tab, setTab] = useState<Tab>("chat");
  const [insights, setInsights] = useState<InsightData[]>([]);
  const [insightsLoading, setInsightsLoading] = useState(true);
  const [chatSeed, setChatSeed] = useState<string | undefined>(undefined);
  const chatSeedKey = useRef(0);

  useEffect(() => {
    fetch(`${API_URL}/insights`)
      .then((r) => r.json())
      .then((data) => {
        setInsights(data);
        setInsightsLoading(false);
      })
      .catch(() => setInsightsLoading(false));
  }, []);

  function handleDigDeeper(prompt: string) {
    chatSeedKey.current += 1;
    setChatSeed(prompt);
    setTab("chat");
  }

  const TABS: { id: Tab; label: string; Icon: React.ComponentType<{ className?: string }> }[] = [
    { id: "chat", label: "Ask Anything", Icon: MessageSquare },
    { id: "insights", label: "Insights", Icon: Lightbulb },
    { id: "coach", label: "Rep Coach", Icon: Users },
  ];

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-zinc-800 px-6 py-3 flex items-center">
        <div className="flex items-center gap-2 flex-1">
          <Activity className="w-5 h-5 text-emerald-400" />
          <span className="font-semibold tracking-tight">GAZYVA</span>
        </div>
        <nav className="flex items-center gap-1">
          {TABS.map(({ id, label, Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition",
                tab === id
                  ? "bg-zinc-800 text-zinc-100"
                  : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900",
              )}
            >
              <Icon className="w-3.5 h-3.5" />
              {label}
            </button>
          ))}
        </nav>
        <div className="flex-1" />
      </header>

      {/* Content */}
      <main className="flex-1 min-h-0 overflow-hidden">
        {/* Insights tab */}
        <div className={cn("h-full overflow-y-auto", tab !== "insights" && "hidden")}>
          <div className="max-w-5xl mx-auto px-6 py-8">
            <div className="mb-6">
              <h2 className="text-xl font-semibold">Proactive Insights</h2>
              <p className="text-zinc-400 text-sm mt-1">
                Auto-generated analyses across Rx, rep activity, and payor mix. Click any card to dig deeper in chat.
              </p>
            </div>
            {insightsLoading ? (
              <div className="flex items-center gap-2 text-zinc-500 text-sm">
                <Loader2 className="w-4 h-4 animate-spin" /> Loading insights…
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {insights.map((card) => (
                  <InsightCard key={card.id} card={card} onDigDeeper={handleDigDeeper} />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Chat tab */}
        <div className={cn("h-full", tab !== "chat" && "hidden")}>
          <Chat key={chatSeedKey.current} seedInput={chatSeed} />
        </div>

        {/* Coach tab */}
        <div className={cn("h-full overflow-y-auto", tab !== "coach" && "hidden")}>
          <RepCoach />
        </div>
      </main>
    </div>
  );
}
