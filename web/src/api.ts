export const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export type ToolCall = {
  name: string;
  input?: any;
  output?: string;
  status: "running" | "done";
};

export type Message = {
  role: "user" | "assistant";
  text: string;
  toolCalls?: ToolCall[];
  chart?: object; // Vega-Lite spec, set when agent calls make_chart
};
