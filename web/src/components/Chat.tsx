import { useEffect, useRef, useState } from "react";
import { Send, Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Chart } from "./Chart";
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
		scrollRef.current?.scrollTo({
			top: scrollRef.current.scrollHeight,
			behavior: "smooth",
		});
	}, [messages]);

	async function send(text: string) {
		if (!text.trim() || busy) return;
		setBusy(true);
		setInput("");

		const userMsg: Message = { role: "user", text };
		const asstMsg: Message = { role: "assistant", text: "", toolCalls: [] };
		setMessages((m) => [...m, userMsg, asstMsg]);

		try {
			await streamSSE(
				`${API_URL}/chat`,
				{ message: text },
				(event, data) => {
					setMessages((m) => {
						const last = m[m.length - 1];
						if (last.role !== "assistant") return m;
						const updated = {
							...last,
							toolCalls: [...(last.toolCalls || [])],
						};

						if (event === "tool_start") {
							updated.toolCalls!.push({
								name: data.name,
								input: data.input,
								status: "running",
							});
						} else if (event === "tool_end") {
							const idx = [...updated.toolCalls!]
								.reverse()
								.findIndex(
									(tc) =>
										tc.name === data.name &&
										tc.status === "running",
								);
							if (idx >= 0) {
								const realIdx =
									updated.toolCalls!.length - 1 - idx;
								updated.toolCalls![realIdx] = {
									...updated.toolCalls![realIdx],
									output: data.output,
									status: "done",
								};
							}
							// Hoist chart spec to message level for prominent rendering.
							if (data.name === "make_chart" && data.output) {
								try {
									const parsed = JSON.parse(data.output);
									if (parsed.__type === "chart") updated.chart = parsed.spec;
								} catch { /* ignore */ }
							}
						} else if (event === "token") {
							// Suppress leading whitespace so the bubble stays in "thinking..." state until real text arrives.
							if (!updated.text && !data.text.trim()) return m;
							updated.text += data.text;
						} else if (event === "done") {
							if (!updated.text) updated.text = data.answer || "";
						} else if (event === "error") {
							updated.text = `Error: ${data.message}`;
						}
						return [...m.slice(0, -1), updated];
					});
				},
			);
		} catch (e: any) {
			setMessages((m) => {
				const last = m[m.length - 1];
				return [
					...m.slice(0, -1),
					{ ...last, text: `Error: ${e.message}` },
				];
			});
		} finally {
			setBusy(false);
		}
	}

	return (
		<div className="flex flex-col h-full">
			<div
				ref={scrollRef}
				className="flex-1 overflow-y-auto px-6 py-6 space-y-6"
			>
				{messages.length === 0 && (
					<div className="max-w-2xl mx-auto mt-12">
						<h2 className="text-2xl font-semibold mb-2">
							Ask anything about the GAZYVA dataset.
						</h2>
						<p className="text-zinc-400 mb-6">
							I&apos;ll write SQL or Python, run it against
							Postgres, and explain the results.
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
						{busy ? (
							<Loader2 className="w-4 h-4 animate-spin" />
						) : (
							<Send className="w-4 h-4" />
						)}
					</button>
				</form>
			</div>
		</div>
	);
}

function MessageBubble({ msg }: { msg: Message }) {
	const hasText = msg.text.trim().length > 0;
	return (
		<div className={cn("max-w-3xl mx-auto", msg.role === "user" ? "ml-auto" : "")}>
			<div
				className={cn(
					"rounded-lg px-4 py-3",
					msg.role === "user"
						? "bg-emerald-900/40 border border-emerald-800/50"
						: "bg-zinc-900 border border-zinc-800",
				)}
			>
				{msg.toolCalls && msg.toolCalls.length > 0 && (
					<div className="space-y-2 mb-3">
						{msg.toolCalls.map((tc, j) => (
							<ToolCallView key={j} tc={tc} />
						))}
					</div>
				)}
				{msg.role === "assistant" ? (
					hasText ? (
						<div className="text-sm leading-relaxed space-y-2">
							<ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
								{msg.text}
							</ReactMarkdown>
						</div>
					) : (
						<em className="text-zinc-500 text-sm">thinking…</em>
					)
				) : (
					<div className="text-sm whitespace-pre-wrap leading-relaxed">{msg.text}</div>
				)}
				{msg.chart && <Chart spec={msg.chart} />}
			</div>
		</div>
	);
}

const mdComponents = {
	table: (props: any) => (
		<div className="overflow-x-auto my-2">
			<table className="text-xs border-collapse" {...props} />
		</div>
	),
	thead: (props: any) => <thead className="bg-zinc-800/50" {...props} />,
	th: (props: any) => (
		<th
			className="border border-zinc-700 px-2 py-1 text-left font-medium text-zinc-300"
			{...props}
		/>
	),
	td: (props: any) => (
		<td
			className="border border-zinc-800 px-2 py-1 text-zinc-300"
			{...props}
		/>
	),
	code: (props: any) => (
		<code
			className="bg-zinc-800 px-1 py-0.5 rounded text-[11px] font-mono"
			{...props}
		/>
	),
	pre: (props: any) => (
		<pre
			className="bg-zinc-950 p-2 rounded text-xs font-mono overflow-x-auto my-2"
			{...props}
		/>
	),
	p: (props: any) => <p className="my-1 leading-relaxed" {...props} />,
	ul: (props: any) => (
		<ul className="my-1 ml-5 list-disc space-y-0.5" {...props} />
	),
	ol: (props: any) => (
		<ol className="my-1 ml-5 list-decimal space-y-0.5" {...props} />
	),
	strong: (props: any) => (
		<strong className="font-semibold text-zinc-100" {...props} />
	),
	h1: (props: any) => (
		<h1 className="text-lg font-semibold mt-3 mb-1" {...props} />
	),
	h2: (props: any) => (
		<h2 className="text-base font-semibold mt-3 mb-1" {...props} />
	),
	h3: (props: any) => (
		<h3 className="text-sm font-semibold mt-2 mb-1" {...props} />
	),
};

// ---------- Tool call rendering ----------

function ToolCallView({ tc }: { tc: ToolCall }) {
	const [open, setOpen] = useState(false);
	const inputObj =
		typeof tc.input === "string"
			? (safeParse(tc.input) ?? tc.input)
			: (tc.input ?? {});
	const sql: string | undefined = inputObj?.query;
	const code: string | undefined = inputObj?.code;
	const tableArg: string | undefined = inputObj?.table;

	const preview = (sql ?? code ?? tableArg ?? JSON.stringify(inputObj) ?? "")
		.replace(/\s+/g, " ")
		.trim()
		.slice(0, 90);

	const parsedOutput = tc.output ? safeParse(tc.output) : null;
	const isErrorOutput =
		typeof tc.output === "string" && tc.output.trim().startsWith("ERROR");

	return (
		<div className="rounded border border-zinc-800 bg-zinc-950/40 text-xs">
			<button
				onClick={() => setOpen((o) => !o)}
				className="w-full text-left px-3 py-2 flex items-center gap-2 hover:bg-zinc-900/60"
			>
				<span
					className={cn(
						"w-1.5 h-1.5 rounded-full shrink-0",
						tc.status === "running"
							? "bg-yellow-400 animate-pulse"
							: isErrorOutput
								? "bg-red-500"
								: "bg-emerald-500",
					)}
				/>
				<span className="font-mono text-zinc-300 shrink-0">
					{tc.name}
				</span>
				<span className="text-zinc-500 truncate">{preview}</span>
			</button>
			{open && (
				<div className="px-3 py-3 border-t border-zinc-800 space-y-3">
					{sql && <CodeBlock label="sql" content={sql.trim()} />}
					{code && <CodeBlock label="python" content={code.trim()} />}
					{!sql && !code && tableArg && (
						<CodeBlock
							label="argument"
							content={`table = ${tableArg}`}
						/>
					)}
					{!sql &&
						!code &&
						!tableArg &&
						Object.keys(inputObj).length > 0 && (
							<CodeBlock
								label="input"
								content={JSON.stringify(inputObj, null, 2)}
							/>
						)}

					{tc.output && (
						<div>
							<div className="text-zinc-500 mb-1 uppercase tracking-wide text-[10px]">
								result
							</div>
							{parsedOutput &&
							Array.isArray(parsedOutput.columns) &&
							Array.isArray(parsedOutput.rows) ? (
								<ResultTable
									columns={parsedOutput.columns}
									rows={parsedOutput.rows}
									truncated={parsedOutput.truncated}
									rowCount={parsedOutput.row_count}
								/>
							) : (
								<pre
									className={cn(
										"font-mono whitespace-pre-wrap break-words max-h-64 overflow-y-auto p-2 rounded",
										isErrorOutput
											? "text-red-300 bg-red-950/30"
											: "text-zinc-300 bg-zinc-950",
									)}
								>
									{tc.output}
								</pre>
							)}
						</div>
					)}
				</div>
			)}
		</div>
	);
}

function CodeBlock({ label, content }: { label: string; content: string }) {
	return (
		<div>
			<div className="text-zinc-500 mb-1 uppercase tracking-wide text-[10px]">
				{label}
			</div>
			<pre className="font-mono text-zinc-300 whitespace-pre-wrap break-words bg-zinc-950 p-2 rounded max-h-72 overflow-y-auto">
				{content}
			</pre>
		</div>
	);
}

function ResultTable({
	columns,
	rows,
	truncated,
	rowCount,
}: {
	columns: string[];
	rows: any[][];
	truncated?: boolean;
	rowCount?: number;
}) {
	return (
		<div className="overflow-x-auto rounded border border-zinc-800">
			<table className="text-xs border-collapse w-full">
				<thead className="bg-zinc-800/50">
					<tr>
						{columns.map((c) => (
							<th
								key={c}
								className="px-2 py-1 text-left font-medium text-zinc-300 border-b border-zinc-800"
							>
								{c}
							</th>
						))}
					</tr>
				</thead>
				<tbody>
					{rows.map((r, i) => (
						<tr key={i} className="even:bg-zinc-900/40">
							{r.map((v, j) => (
								<td
									key={j}
									className="px-2 py-1 text-zinc-300 border-b border-zinc-900 font-mono"
								>
									{v === null ? (
										<span className="text-zinc-600">
											null
										</span>
									) : (
										String(v)
									)}
								</td>
							))}
						</tr>
					))}
				</tbody>
			</table>
			<div className="px-2 py-1 text-[10px] text-zinc-500 bg-zinc-950">
				{rowCount ?? rows.length} row
				{(rowCount ?? rows.length) === 1 ? "" : "s"}
				{truncated ? " · truncated to 50" : ""}
			</div>
		</div>
	);
}

function safeParse(s: any): any {
	if (typeof s !== "string") return null;
	try {
		return JSON.parse(s);
	} catch {
		return null;
	}
}
