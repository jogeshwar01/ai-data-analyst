# AI Analyst for Your Data

Ask questions in plain English over your data. The agent inspects the schema, writes SQL, runs Python analysis when needed, creates charts, and explains the result.

## Architecture

```
React -> FastAPI SSE -> LangChain create_agent -> OpenRouter (configurable)
                                  |
                           +------+------+
                           |             |
                        Postgres       Redis
```

The frontend sends your question to a FastAPI backend over SSE. A LangChain `create_agent` runtime uses structured tool calling to inspect schema, run SQL, run Python, or build charts against Postgres, then streams tool events and answer tokens back to the UI.

The stack: React + Vite on the frontend, FastAPI + LangChain on the backend, Postgres for the data, Redis to cache the insight cards and last five chat turns, OpenRouter for the LLM (model configurable via `OPENROUTER_MODEL` in `.env`).

## Agent

The agent uses LangChain's newer `create_agent` API. Tools are called through provider-native structured tool calling with Pydantic argument schemas instead of the old text pattern where the model had to emit `Thought:`, `Action:`, `Action Input:`, and `Final Answer:` markers.

Primary model is set via `OPENROUTER_MODEL` in `.env` (default `moonshotai/kimi-k2.6`). `OPENROUTER_FALLBACK_MODEL` is tried automatically on 429s or 5xx errors. See [docs/structured-agent.md](docs/structured-agent.md) for implementation details.

| Tool          | What it does                                                                                                                                                                            |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `run_sql`     | Executes a read-only SELECT against Postgres, returns up to 50 rows. On error, returns the raw Postgres message so the agent can self-correct and retry.                                |
| `list_schema` | Returns column names and sample rows for any table or view. Called when the agent needs to verify a column before writing a query.                                                      |
| `run_python`  | Runs Python in a sandboxed subprocess (10s timeout). pandas and numpy are pre-imported plus a `query()` helper returning a DataFrame. Used for what-if projections and multi-step math. |
| `make_chart`  | Takes a data array and a Vega-Lite spec, embeds the data, and returns a chart the frontend renders inline.                                                                              |

## Example Queries

**Q1 - `run_sql`: Which rep has the highest call-to-Rx conversion rate?**

![q1-1](docs/images/q1-1.png)
![q1-2](docs/images/q1-2.png)

**Q2 - `list_schema`: What data do we have on each account?**

![q2-1](docs/images/q2-1.png)
![q2-2](docs/images/q2-2.png)

**Q3 - `run_python`: If rep 3 doubled their completed calls to tier-B HCPs, what would the projected TRx lift be?**

![q3-1](docs/images/q3-1.png)
![q3-2](docs/images/q3-2.png)
![q3-3](docs/images/q3-3.png)

**Q4 - `make_chart`: Show me monthly TRx per territory as a chart**

![q4-1](docs/images/q4-1.png)
![q4-2](docs/images/q4-2.png)
![q4-3](docs/images/q4-3.png)
![q4-4](docs/images/q4-4.png)
![q4-5](docs/images/q4-5.png)
![q4-6](docs/images/q4-6.png)

## Features

**Ask Anything** is the main tab. Type any question and get an answer backed by real data. The agent self-corrects if it writes bad SQL. For ambiguous questions it states its assumption before answering.

**Insights** shows six pre-computed analyses that run on startup and cache for an hour. Things like biggest TRx decliners, reps with low conversion, tier-A doctors with no recent visits. Each card has a button to ask a follow-up in chat.

**Rep Coach** lets you pick a rep and get three prioritized actions: which high-potential doctors they're under-visiting, how their conversion compares to peers, and which tier-A doctors have gone cold.

**Eval** is a set of golden Q&A pairs you can run to check the agent is working correctly.

## Setup

```bash
cp .env.example .env
# fill in OPENROUTER_API_KEY
docker compose up --build
```

App runs at http://localhost:5173. API at http://localhost:8000.

Data loads automatically on first startup from the CSVs in `data/`.

## Running the eval

```bash
# quick check, 5 questions, about 2 minutes
docker compose exec api python3 -m eval.run --quick

# full suite, 11 questions, writes api/eval/report.md
docker compose exec api python3 -m eval.run
```

## Notes

Chat logs are saved to `api/logs.md` after each conversation. Chat memory is session-scoped: the browser sends a stable `session_id`, and the API stores the last five completed Q&A turns in Redis with an in-memory fallback. The agent is explained in detail in `assignment/agent.md`.

## Production Improvements

### Code Sandbox

`run_python` currently uses a subprocess with a 10s timeout. That works for a local demo but is not safe for production - a malicious or buggy input could exhaust resources or escape the process. The right fix is a proper isolated execution environment like [E2B](https://e2b.dev), Modal, or gVisor. These give you network isolation, memory limits, and per-execution containers.

### Multiple LLM Providers

Right now we have one primary (Kimi K2.6) and one fallback (GPT-4o-mini), both via OpenRouter. For production you'd want a more robust routing layer - retrying across multiple providers, falling back based on latency not just errors, and tracking per-provider success rates. OpenRouter itself handles some of this, but libraries like LiteLLM give you finer control and a unified interface across Anthropic, OpenAI, Google, and others.

### Vector DB for Schema Routing

A vector DB would not help much here because the full schema fits in the system prompt (~300 tokens). Where it would matter is if the dataset grew to hundreds of tables - at that point you'd want semantic search to retrieve only the relevant tables and columns for a given question rather than dumping everything. Tools like pgvector (runs inside Postgres itself) or Qdrant would handle this. For this dataset size, it would be over-engineering.

### Conversation Memory

Chat requests include a browser-generated `session_id`. The API stores the last five completed Q&A turns in Redis and passes them back to LangChain as alternating `user` and `assistant` messages, so users can ask follow-ups like "now filter that by territory 2" without restating the full context.
