# Synthio Labs Take-Home — Implementation Plan

## Context

Synthio Labs (YC AI co.) take-home: build a tool that answers questions over a pharma commercial-analytics dataset (CSVs in [data/](data/)), brief in [assignment.md](assignment.md). They explicitly invited "maximum ideation" + offered API keys. This decides the next interview round, so it should look polished but not bloated.

The dataset is a clean star schema: 4 fact tables (Rx volume, rep activity, payor mix, market share) keyed to 5 dim tables (HCPs, accounts, reps, territories, dates). 16 months of data, single brand (GAZYVA), ~6K total fact rows — fits trivially in Postgres.

User constraints (locked in): clean stack, no over-engineering, minimal frontend. Keep code small.

---

## Stack (final)

| Layer | Choice | Why |
|---|---|---|
| Backend | **FastAPI** (Python 3.11) | Async, SSE-friendly, minimal boilerplate |
| DB | **Postgres 16** | Loaded once from CSVs at startup; analytics on 6K rows is trivial. No DuckDB needed |
| Cache | **Redis 7** | Cache the 6 insight cards (LLM-generated narratives are expensive to regen on every page load) |
| Agent | **LangChain** `create_tool_calling_agent` + `AgentExecutor` | Don't hand-roll a ReAct loop. Tool-calling, retries, streaming all built in |
| LLM | **OpenRouter** → `moonshotai/kimi-k2.6` (primary), `openai/gpt-4o-mini` fallback | Per user; LangChain `ChatOpenAI` points at OpenRouter base URL |
| Frontend | **Vite + React 18 + TypeScript** | No Next.js — overkill for this UI |
| Styling | **Tailwind + shadcn/ui** | Stock components, zero custom CSS |
| Streaming | **Server-Sent Events (SSE)** | Native FastAPI `StreamingResponse`, native browser `EventSource`. No socket.io |
| Orchestration | **docker-compose** | One `docker compose up` brings up api, web, postgres, redis |

No SQLAlchemy ORM (raw SQL via `psycopg` — the agent generates SQL anyway). No Celery, no Kafka, no vector DB, no auth, no Next.js, no DuckDB.

---

## Architecture

```
┌─────────────────────────┐    SSE    ┌─────────────────────────────┐
│ React + Tailwind        │ ────────► │ FastAPI                     │
│  - Insights cards (6)   │           │  POST /chat       (stream) │
│  - Chat                 │           │  GET  /insights            │
│  - Rep coach panel      │           │  GET  /coach/{rep_id}      │
└─────────────────────────┘           │  POST /eval                │
                                      └──────┬──────────────────────┘
                                             │
                                  ┌──────────┼─────────────┐
                                  ▼          ▼             ▼
                            LangChain    Postgres        Redis
                            tool agent   (CSVs           (insight
                            (4 tools)    loaded at       cache)
                                         startup)
                                  │
                                  ▼
                          OpenRouter (Kimi K2.6 / GPT-4o-mini fallback)
```

---

## File structure (target ~1500 LOC total)

```
synthio/
  data/                              # CSVs (read-only, already there)
  assignment.md
  README.md                          # 1 architecture diagram, eval badge, screenshot, demo link
  docker-compose.yml                 # api + web + postgres + redis
  Makefile                           # `make up`, `make eval`, `make seed`
  .env.example                       # OPENROUTER_API_KEY, DATABASE_URL, REDIS_URL

  api/
    Dockerfile
    pyproject.toml
    main.py                          # FastAPI app, routes inline (4 endpoints, ~80 lines)
    db.py                            # psycopg pool + bootstrap (loads CSVs into Postgres on startup)
    schema.sql                       # CREATE TABLE for each CSV + materialized views
    agent.py                         # LangChain tool-calling agent + 4 @tool funcs (~150 lines)
    insights.py                      # 6 canned analyses w/ narrative templates
    coach.py                         # Rep-coach endpoint logic
    prompts.py                       # System prompt + 5 few-shots, plain Python strings
    eval/
      golden.yaml                    # 12 Q&A pairs
      run.py                         # Iterates golden set, scores, writes report.md

  web/
    Dockerfile
    package.json
    vite.config.ts
    src/
      main.tsx
      App.tsx                        # Single page: insights cards + chat. Tab to switch to coach view
      api.ts                         # Typed fetch + SSE helpers
      components/
        InsightCard.tsx
        Chat.tsx                     # Message list + input + streaming
        ToolTrace.tsx                # Collapsible "show SQL / show data / show chart"
        Chart.tsx                    # vega-embed wrapper
        RepCoach.tsx                 # Dropdown + 3 recommendation cards
      lib/
        sse.ts                       # 30-line SSE client
```

Frontend is **one page**, ~5 components. Tab on the top toggles between "Ask anything" (insights + chat) and "Coach a rep". That's the whole UI.

---

## Agent loop (LangChain)

```python
# agent.py — sketch

llm = ChatOpenAI(
    model="moonshotai/kimi-k2.6",
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
    streaming=True,
)

@tool
def list_schema(table: str | None = None) -> str:
    """Return columns + 3 sample rows for a table, or all tables if none given."""

@tool
def run_sql(query: str) -> str:
    """Execute read-only SQL against Postgres. Returns first 50 rows + error msg verbatim on failure."""

@tool
def run_python(code: str) -> str:
    """Sandboxed pandas/numpy/statsmodels (subprocess, 5s timeout, no net). Use for stats/regression only."""

@tool
def make_chart(data_json: str, vega_lite_spec: dict) -> dict:
    """Validate Vega-Lite spec, return JSON for the frontend to render."""

agent = create_tool_calling_agent(llm, [list_schema, run_sql, run_python, make_chart], prompt)
executor = AgentExecutor(agent=agent, max_iterations=6, handle_parsing_errors=True)
```

**Prompt rules** ([api/prompts.py](api/prompts.py)):
- Full schema injected (~800 tokens, fits trivially).
- 5 few-shot Q→trace examples: simple agg, 3-table join, window function, ambiguity-stating, Python-required.
- "SQL for filter/join/group/rank/window. Python only for regression, correlation+significance, simulation."
- "If question is ambiguous, EITHER ask one clarifying question OR state your assumption explicitly before answering."

LangChain handles streaming, tool dispatch, retries, max-iteration cap. We don't write loop logic.

---

## Features (4 total — focused, not sprawling)

1. **Chat agent** (primary surface) — answers any question with transparent SQL/Python/chart trace.
2. **Proactive Insights Dashboard** — 6 cards on home, Redis-cached for 1 hour, "dig deeper" button seeds the chat input. Examples: biggest TRx decliners, reps with low call→Rx conversion, payor-mix shifts >5pp QoQ, tier-A HCPs with zero recent calls, top growth territories MoM, specialty Rx concentration.
3. **Rep Coaching view** — pick a rep → server returns 3 next-best-actions (under-covered HCPs by TRx potential, call→Rx conversion vs peers, suggested next visits). One server endpoint, one React component.
4. **Golden eval harness** — 12 Q&A pairs, `make eval` runs them and writes `eval/report.md`. Pass-rate badge in README.

What-if simulator dropped — the chat agent can answer "if rep 3 doubles calls, what's projected lift?" via `run_python` without a dedicated UI page.

---

## Golden eval set (12 questions)

| # | Question | Grading |
|---|---|---|
| 1 | How many distinct HCPs prescribed GAZYVA? | exact (= 90) |
| 2 | Total TRx for Q4 2024? | exact ±1% |
| 3 | Top 5 HCPs by TRx last 90 days | set overlap ≥4/5 |
| 4 | Territory with highest TRx per HCP? | exact (territory name) |
| 5 | MoM TRx growth per territory | shape + spot values |
| 6 | Does call frequency correlate with TRx? | r value ±0.1, mentions p-value |
| 7 | Tier-A HCPs with zero calls in last 60 days | set overlap |
| 8 | Rep with highest call→Rx conversion | exact rep name |
| 9 | Accounts shifting >5pp Medicare QoQ | set overlap |
| 10 | "Which doctors are best?" | LLM-judge: must clarify or state assumption |
| 11 | Projected TRx if rep 3 doubles calls to tier-B | number + CI present |
| 12 | Show me anomalies | LLM-judge w/ rubric |

Target ≥10/12 before shipping.

---

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| LLM hallucinates column names | LangChain auto-retries on tool errors; `run_sql` returns Postgres error verbatim → LLM fixes itself |
| OpenRouter 429 / Kimi outage | LangChain `with_fallbacks([gpt_4o_mini])` — one line |
| `run_python` arbitrary code | `subprocess.run(timeout=5)`, restricted env (`PYTHONNOUSERSITE=1`, no net via firewall not needed for subprocess), allowlist imports via wrapper script |
| Confidently-wrong answers on ambiguous Qs | Prompt forces explicit assumption-stating; eval Q10 is a regression test |
| Demo crashes | Try/except in route handlers; insights pre-warmed in Redis on startup; recorded 60s screen capture as backup |
| API key leak | `.env` gitignored; `.env.example` checked in; README warns |
| Postgres CSV load fails | Bootstrap script idempotent (`CREATE TABLE IF NOT EXISTS`, `TRUNCATE` then `COPY`); fail loud at startup |

---

## 5-day execution plan
la
- **Day 1** — `docker-compose.yml` (api, web, postgres, redis). Postgres bootstrap: schema + CSV load via `COPY`. FastAPI `/chat` SSE route + LangChain agent w/ `run_sql` + `list_schema` tools + Kimi K2.6. Vite + React + shadcn scaffold, basic chat UI streaming end-to-end. *Goal: one good answer in the browser.*
- **Day 2** — Add `run_python` (subprocess sandbox) + `make_chart` (Vega-Lite). System prompt v1 + 5 few-shots. Tool-trace UI (collapsible SQL/data/chart panels).
- **Day 3** — Insights dashboard: 6 canned analyses + narrative generator + Redis caching + cards on the home page. Rep coaching endpoint + view.
- **Day 4** — Golden eval harness, run it, fix prompts until ≥10/12 pass.
- **Day 5** — README (architecture diagram, eval badge, 1 screenshot), 60s Loom demo, dogfood for 30 min, polish top 3 paper-cuts, send the email.

Day 6-7 = buffer in case of slippage.

---

## Critical files

- [docker-compose.yml](docker-compose.yml)
- [api/main.py](api/main.py)
- [api/agent.py](api/agent.py) — LangChain agent + 4 tools
- [api/prompts.py](api/prompts.py) — system prompt + few-shots
- [api/insights.py](api/insights.py) — 6 canned analyses
- [api/eval/golden.yaml](api/eval/golden.yaml) — 12 Q&A pairs
- [web/src/App.tsx](web/src/App.tsx)
- [web/src/components/Chat.tsx](web/src/components/Chat.tsx)
- [web/src/components/ToolTrace.tsx](web/src/components/ToolTrace.tsx)
- [README.md](README.md)

---

## Verification

1. `docker compose up` brings everything up cleanly.
2. `make eval` runs the 12 golden questions, writes `api/eval/report.md`. ≥10/12 passing.
3. Manual smoke test: ask each golden question in the UI, confirm SQL + data + (where relevant) chart panels render. Load home page → 6 insight cards in <3s (cache warm). Switch to rep-coach tab → 3 recommendations.
4. Disconnect Wi-Fi mid-question to confirm graceful failure (no white screen).
5. README: architecture diagram, `eval: 10/12 ✓` badge, one screenshot, Loom link.
