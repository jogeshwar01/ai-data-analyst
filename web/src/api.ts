export const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export type ThoughtStep = { type: "thought"; text: string };
export type ToolStep = {
  type: "tool";
  name: string;
  input?: any;
  output?: string;
  status: "running" | "done";
};
export type MessageStep = ThoughtStep | ToolStep;

export type Message = {
  role: "user" | "assistant";
  text: string;
  steps?: MessageStep[];
  chart?: object;
};
