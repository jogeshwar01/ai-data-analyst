# ReAct Agent Implementation

> Legacy note: the app no longer uses this implementation. The current backend uses LangChain `create_agent` with structured tool calling; see [structured-agent.md](structured-agent.md).

## What Changed and Why

The original agent used LangChain's tool-calling interface (`create_tool_calling_agent`). In that mode the model picks a tool via the function-calling API - one structured JSON object per step, no intermediate text. It works well with models tuned for function-calling (Kimi K2.6, GPT-4o), but the reasoning is opaque: you see which tool ran and what it returned, but not *why* the model chose it.

ReAct (**Re**ason + **Act**) is a text-based loop where the model writes its thought out loud before every action:

```
Thought: I need to find total TRx for Q4 2024. The fact_rx table has trx and period_date columns.
Action: run_sql
Action Input: SELECT SUM(trx) FROM fact_rx WHERE period_date BETWEEN '2024-10-01' AND '2024-12-31'
Observation: {"columns":["sum"],"rows":[[1842.0]]}
Thought: I now know the final answer
Final Answer: Total TRx for Q4 2024 was 1,842 units.
```

Every Thought is streamed to the frontend and shown as a collapsible reasoning trace. Users can see not just what SQL ran but why the agent wrote that query.

---

## LangChain Setup

```python
from langchain.agents import create_react_agent, AgentExecutor

agent = create_react_agent(llm, tools, react_prompt)
executor = AgentExecutor(
    agent=agent,
    tools=tools,
    max_iterations=10,
    handle_parsing_errors=True,
)
```

`create_react_agent` wraps the LLM with `ReActSingleInputOutputParser`, which parses the `Action:` / `Action Input:` / `Final Answer:` text pattern out of each model response. `handle_parsing_errors=True` lets LangChain inject a correction prompt when the parser fails instead of crashing.

The prompt is a `PromptTemplate` with four required variables: `{tools}`, `{tool_names}`, `{input}`, `{agent_scratchpad}`. LangChain fills `agent_scratchpad` with the accumulated Thought/Action/Observation history each iteration.

---

## Prompt Format

The prompt instructs the model to follow an exact format with no deviations:

```
Thought: your reasoning
Action: one of [run_sql, list_schema, run_python, make_chart]
Action Input: the tool input
Observation: <filled by LangChain>
... repeat ...
Thought: I now know the final answer
Final Answer: your complete answer
```

`Action Input` is a plain string for `run_sql` and `run_python` (the raw SQL or Python code), and a JSON object for `make_chart`. This matters because `ReActSingleInputOutputParser` first tries `json.loads()` on the Action Input and falls back to a plain string if that fails.

---

## Streaming Quirk: `input` is Always `{}`

`AgentExecutor.astream_events(version="v2")` fires `on_tool_start` events, but for ReAct agents the `event["data"]["input"]` field is **always** `{}`. This is a known LangChain behaviour: the structured input isn't available at the streaming hook point for text-parsed agents.

The workaround: the server buffers every streamed token in `thought_buf`. When `on_tool_start` fires, the buffer contains the full `Thought: ... Action: run_sql\nAction Input: SELECT ...` text. The server extracts the Action Input from the buffer before clearing it:

```python
def _extract_thought_and_input(buf: str) -> tuple[str, str]:
    text = buf.strip()
    thought, action_input = text, ""
    for sep in ("\nAction:", "Action:"):
        if sep in text:
            idx = text.index(sep)
            thought = text[:idx]
            rest = text[idx + len(sep):]
            for ai_sep in ("\nAction Input:", "Action Input:"):
                if ai_sep in rest:
                    action_input = rest[rest.index(ai_sep) + len(ai_sep):].strip()
                    break
            break
    if thought.startswith("Thought:"):
        thought = thought[len("Thought:"):].strip()
    return thought, action_input
```

This extracted string becomes the `input` shown in the tool trace UI.

---

## `_Exception` Tool Suppression

When `handle_parsing_errors=True` and the parser fails (e.g. the model forgets `Action:` or adds extra text), LangChain dispatches an internal tool named `_Exception` with the parser error as its input. This is normal - it injects a self-correction prompt and the agent retries.

`_Exception` events are filtered in the SSE handler so they never reach the frontend:

```python
if tool_name.startswith("_"):
    current_tool = None
    continue
```

---

## "Final Answer:" Detection

ReAct doesn't have a separate streaming signal for "the answer starts here". The model just writes `Final Answer: <text>`. The server watches the token buffer for this marker:

```python
_FINAL_MARKER = "Final Answer:"

if _FINAL_MARKER in thought_buf:
    in_answer = True
    idx = thought_buf.index(_FINAL_MARKER)
    thought, _ = _extract_thought_and_input(thought_buf[:idx])
    post = thought_buf[idx + _MARKER_LEN:].lstrip("\n ")
    thought_buf = ""
    if thought:
        yield _sse("thought", {"text": thought})
    if post:
        yield _sse("token", {"text": post})
```

Once `in_answer` is true, all subsequent tokens go directly to `token` events (the answer bubble) instead of `thought_buf`.

If the model never writes "Final Answer:" (rare, usually on very short answers), the buffer contents are emitted as the answer at the end of the stream.

---

## Frontend: Interleaved Steps

The earlier tool-calling design put all reasoning at the top of a message and tool calls below. ReAct produces interleaved sequences (Thought → Tool → Thought → Tool → Final Answer), so the frontend needs to preserve that order.

`Message.steps` is a flat array of `ThoughtStep | ToolStep` entries, appended in arrival order:

```typescript
type ThoughtStep = { type: "thought"; text: string };
type ToolStep    = { type: "tool"; name: string; input?: any; output?: string; status: "running" | "done" };
```

When a `thought` SSE event arrives, a `ThoughtStep` is pushed. When `tool_start` arrives, a `ToolStep` with `status: "running"` is pushed. When `tool_end` arrives, the last matching running `ToolStep` is updated in place with the output and `status: "done"`.

Both step types render as collapsible rows - thoughts in a slightly darker grey, tool calls with the tool name and a status dot.

---

## `make_chart` Single-Argument Workaround

`make_chart` takes two parameters (`data_json` and `vega_lite_spec`). The `ReActSingleInputOutputParser` tries to parse Action Input as JSON; when the model passes a full object with both keys nested inside `data_json`, Pydantic rejects the call because `vega_lite_spec` is missing.

Fix: `vega_lite_spec` defaults to `"{}"`. Inside the tool, if the default is detected and `data_json` looks like an object containing both keys, they're unpacked before calling the chart builder:

```python
@tool
def make_chart(data_json: str, vega_lite_spec: str = "{}") -> str:
    if not vega_lite_spec or vega_lite_spec == "{}":
        try:
            payload = json.loads(data_json)
            if isinstance(payload, dict) and "vega_lite_spec" in payload:
                d = payload.get("data_json", "[]")
                v = payload.get("vega_lite_spec", "{}")
                ...
                return build_chart(d, v)
        except (json.JSONDecodeError, TypeError):
            pass
    return build_chart(data_json, vega_lite_spec)
```

---

## Model Choice

ReAct requires a model that reliably follows the text-based `Thought / Action / Action Input` format. Models trained primarily for function-calling (e.g. Kimi K2.6) tend to output API-style JSON blobs instead of the text pattern, causing repeated parser failures.

The current model is configured via `OPENROUTER_MODEL` in `.env`. Models confirmed to work well with this format: `qwen/qwen3-6b-flash`, `openai/gpt-4o-mini`, `google/gemini-flash` variants. Set `OPENROUTER_FALLBACK_MODEL` for automatic fallback on 429s or 5xx errors.
