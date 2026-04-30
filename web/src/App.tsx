import { Activity } from "lucide-react";
import { Chat } from "./components/Chat";

export default function App() {
  return (
    <div className="h-screen flex flex-col">
      <header className="border-b border-zinc-800 px-6 py-3 flex items-center gap-3">
        <Activity className="w-5 h-5 text-emerald-400" />
        <div className="font-semibold tracking-tight">Synthio</div>
        <div className="text-xs text-zinc-500">· GAZYVA commercial analytics</div>
      </header>
      <main className="flex-1 min-h-0">
        <Chat />
      </main>
    </div>
  );
}
