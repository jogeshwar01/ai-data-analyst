# How the Agent Works

## Overview

The agent is a LangChain `create_agent` graph runtime backed by a configurable model via OpenRouter. It receives a natural language question, calls structured tools against Postgres, and returns a written answer - all streamed to the frontend in real time.

The implementation uses the newer LangChain agent API, which runs on LangGraph under the hood. Tool calls are provider-native structured calls with Pydantic schemas, so the server no longer parses `Action:` / `Action Input:` / `Final Answer:` text. LangChain handles dispatch, retries, and the iteration loop. See [structured-agent.md](structured-agent.md) for the full implementation breakdown.

---

## Tools

The agent has 4 tools:

### `run_sql(query)`
Executes a read-only SELECT against Postgres and returns up to 50 rows as JSON. If the query errors, the raw Postgres error is returned verbatim - which the model uses to self-correct and retry. Write/DDL statements are blocked.

### `list_schema(table?)`
Returns column names + data types + 3 sample rows for a table or view. The agent calls this proactively when it's unsure about column names rather than guessing and failing.

### `run_python(code)`
Runs Python in a subprocess sandbox (10s timeout). `pandas` and `numpy` are pre-imported. A `query(sql)` helper is injected that returns a DataFrame. Used only for multi-step computation SQL can't express - e.g. what-if projections (average TRx per call × extra calls + std dev CI).

### `make_chart(data_json, vega_lite_spec)`
Takes a JSON array of records and a Vega-Lite spec, embeds the data into the spec, and returns a `{"__type": "chart", "spec": {...}}` envelope. The frontend detects this in the `tool_end` SSE event and renders it with vega-embed.

---

## Prompt Design

The system prompt has three parts:

**Schema doc** (~300 tokens): every table, column, and data type listed explicitly. The two convenience views (`v_rx_enriched`, `v_activity_enriched`) are listed with their exact column names - this prevents the model from guessing wrong aliases (e.g. `full_name` vs `hcp_name`).

**Rules** (10 rules): key behaviours injected as instructions:
- Use SQL first; Python only for simulation/projection
- On ambiguous questions, state your assumption before answering
- Never truncate lists with "e.g." or "…" - list every name
- What-if questions: one Python call, not split across multiple
- Anomaly questions: one Python script with multiple checks

**Few-shot examples** (5 examples): worked traces showing the exact tool call → output → answer pattern for: simple count, window function (MoM growth), what-if projection (ratio + CI), anomaly detection (batched numpy checks), and ambiguity handling.

---

## Streaming

The FastAPI `/chat` endpoint passes native LangGraph message state to `agent.astream_events(version="v2")`. The server translates LangChain events into frontend-safe SSE events:

| LangChain event | SSE event | Frontend action |
|---|---|---|
| `on_tool_start` | `tool_start` | Push running tool trace row |
| `on_tool_end` | `tool_end` | Fill trace with SQL/output/chart |
| `on_chat_model_stream` | `token` | Append to answer bubble |
| _(stream ends)_ | `done` | Finalize answer, write to logs.md |

The frontend uses a `fetch`-based SSE client (not `EventSource`) because `EventSource` doesn't support POST requests.

---

## Self-Correction

The agent self-corrects on SQL errors without any special logic. Because `run_sql` returns the Postgres error verbatim, the model sees exactly what went wrong (e.g. `column "full_name" does not exist`) and issues a corrected query. If it fails twice, the prompt instructs it to call `list_schema` first to verify column names before retrying.

Structured tool validation catches malformed inputs before tool execution. The SQL tool also enforces read-only, single-statement `SELECT`/`WITH` queries in code.

---

## Fallback

Primary model: `moonshotai/kimi-k2.6` via OpenRouter.
Fallback: `openai/gpt-4o-mini` via the same base URL.

LangChain's `.with_fallbacks([fallback_llm])` handles this in one line - if the primary returns a 429 or 5xx, the fallback is tried automatically.

---

## What the Agent Does NOT Do

- No vector search or semantic retrieval - the schema fits in the prompt (~300 tokens)
- No memory across sessions - each `/chat` call is stateless
- No write access - SQL tool blocks INSERT/UPDATE/DROP
- No internet access in the Python sandbox - subprocess environment has no network
