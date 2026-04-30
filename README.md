#  GAZYVA Commercial Analytics

Natural language analytics over a pharma commercial dataset. Ask anything — the agent writes SQL or Python, runs it against Postgres, and explains the result with transparent tool traces.

## Architecture

```
React (Vite) ──SSE──► FastAPI ──► LangChain Agent
                                      │
                          ┌───────────┼───────────┐
                          ▼           ▼           ▼
                       Postgres    run_python   OpenRouter
                       (CSV data   (pandas /    Kimi K2.6
                        loaded at  numpy        primary,
                        startup)   sandbox)     GPT-4o-mini
                          │                    fallback
                       Redis
                      (insight
                        cache)
```

**Stack:** FastAPI · Postgres 16 · Redis 7 · LangChain · React 18 · Tailwind · shadcn/ui · Docker Compose · OpenRouter

## Features

### Ask Anything
Natural language → SQL or Python → answer with full tool trace. The agent:
- Writes and self-corrects SQL via `run_sql` (retries on Postgres errors)
- Runs pandas/numpy via a sandboxed subprocess for simulation questions
- Renders Vega-Lite charts inline via `make_chart`
- States assumptions explicitly on ambiguous questions

### Proactive Insights
Six pre-computed analyses load on startup (Redis-cached, 1hr TTL):
- Biggest TRx decliners vs prior quarter
- Reps with low call→Rx conversion
- Accounts with >5pp payor mix shifts
- Tier-A HCPs with no recent rep contact
- Territory MoM TRx growth
- Rx concentration by specialty

Each card has a "dig deeper →" button that seeds the chat with the relevant question.

### Rep Coach
Pick any rep → get 3 prioritized next-best-actions backed by real data: under-covered high-potential HCPs, conversion rate vs peers, dormant Tier-A HCPs to re-engage.

### Eval Harness
11 golden Q&A pairs with automatic grading (exact match, set overlap, LLM-judge).

## Quick Start

```bash
cp .env.example .env
# Add your OPENROUTER_API_KEY to .env
docker compose up --build
```

- Frontend: http://localhost:5173
- API: http://localhost:8000
- API docs: http://localhost:8000/docs

## Eval

```bash
# Fast — 5 core questions, ~2 min
docker compose exec api python3 -m eval.run --quick

# Full — 11 questions, ~8 min, writes api/eval/report.md
docker compose exec api python3 -m eval.run
```

## Dataset

10 CSVs in `data/` — pharma commercial star schema:

| Table | Description |
|---|---|
| `fact_rx` | Daily Rx volume per HCP (TRx, NRx) |
| `fact_rep_activity` | Sales rep calls and meetings |
| `fact_payor_mix` | Monthly insurance mix by account |
| `fact_ln_metrics` | Quarterly market share (HCP + account) |
| `hcp_dim` | 90 HCPs with specialty + tier |
| `account_dim` | 24 hospitals/clinics |
| `rep_dim` | 9 sales reps |
| `territory_dim` | 3 territories |
| `date_dim` | 2024-08-01 → 2025-12-31 |

## Project Structure

```
api/
  main.py          FastAPI routes + SSE streaming + chat logger
  insights.py      6 canned analyses (Redis-cached)
  coach.py         Rep next-best-actions
  agent/
    core.py        LangChain agent + 4 tool definitions
    prompts.py     System prompt + few-shot examples
    tools.py       Python sandbox + Vega-Lite chart builder
  db/
    __init__.py    Postgres pool + CSV bootstrap
    schema.sql     DDL + convenience views
  eval/
    golden.json    11 Q&A pairs (full)
    quick.json     5 Q&A pairs (fast)
    extended.json  6 harder Q&A pairs
    run.py         Eval runner with step traces

web/src/
  App.tsx          3-tab layout (Ask Anything · Insights · Rep Coach)
  components/
    Chat.tsx       Streaming chat with tool traces
    InsightCard.tsx Collapsible insight cards
    RepCoach.tsx   Rep selector + action cards
    Chart.tsx      Vega-Lite renderer
```

## Security Note

`run_python` uses subprocess isolation with a 10s timeout. Suitable for local demo use; production deployments should use a proper sandbox (E2B, Modal, or gVisor).
