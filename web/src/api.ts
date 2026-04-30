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
};
