# Structured Agent Implementation

## What Changed and Why

The agent uses LangChain's `create_agent` API instead of the older text ReAct helper:

```python
from langchain.agents import create_agent

agent = create_agent(
    model=llm,
    tools=[list_schema, run_sql, run_python, make_chart],
    system_prompt=prompts.ASSISTANT_PROMPT,
)
```

`create_agent` builds a graph-based runtime on LangGraph under the hood. The model calls tools structurally, so the backend no longer depends on text markers like `Thought:`, `Action:`, `Action Input:`, or `Final Answer:`.

## Tool Contracts

Each tool has three layers:

- System prompt: global domain strategy, safety rules, and response style.
- Tool docstring: when to use that specific tool.
- Pydantic `args_schema`: the exact structured input contract.

The schema helps the model serialize tool calls correctly, and the implementation still enforces safety in code.

## Streaming

The `/chat` endpoint streams LangChain events and translates them to the existing frontend SSE contract:

| LangChain event | SSE event | Purpose |
|---|---|---|
| `on_tool_start` | `tool_start` | Show the tool name and structured input |
| `on_tool_end` | `tool_end` | Show the output and render chart envelopes |
| `on_chat_model_stream` | `token` | Append answer text |
| stream completion | `done` | Persist the final answer |
| exception | `error` | Show an error message |

Because structured tool calls include `event["data"]["input"]`, there is no buffering or Action Input extraction.

## Message State

The app calls the compiled agent with LangGraph's native message-state shape:

```python
agent.astream_events(
    {"messages": messages},
    version="v2",
)
```

`conversation.build_messages(...)` converts the last saved chat turns into alternating `user` and `assistant` messages, then appends the current user message. Evals use the same native shape with a single user message.

For eval reports, `api/agent/core.py` exposes small helpers that read the returned message list and reconstruct the final answer plus tool steps from AI tool calls and matching tool messages.

## Model Choice

The current model is configured via `OPENROUTER_MODEL` in `.env`; the default is `moonshotai/kimi-k2.6`. `OPENROUTER_FALLBACK_MODEL` is tried through LangChain `.with_fallbacks([fallback])`.

Use models that support tool calling through OpenAI-compatible chat completions. The old requirement that models follow a precise text ReAct format no longer applies.
