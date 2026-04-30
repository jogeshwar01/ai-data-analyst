"""LangChain tool-calling agent over Postgres."""

import json
import os
from typing import Any

from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

import db
from . import prompts

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
PRIMARY_MODEL = os.environ.get("OPENROUTER_MODEL", "moonshotai/kimi-k2.6")
FALLBACK_MODEL = os.environ.get("OPENROUTER_FALLBACK_MODEL", "openai/gpt-4o-mini")
MAX_ROWS_RETURNED = 50


def _build_llm(model: str) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        base_url=OPENROUTER_BASE,
        api_key=os.environ["OPENROUTER_API_KEY"],
        temperature=0,
        streaming=True,
        max_retries=2,
    )


# ---------- Tools ----------


@tool
def list_schema(table: str | None = None) -> str:
    """List columns + 3 sample rows for a table. If table is None, list all table names with row counts."""
    if not table:
        cols, rows = db.query("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        out = []
        for (t,) in rows:
            _, c = db.query(f"SELECT COUNT(*) FROM {t}")
            out.append(f"- {t}: {c[0][0]} rows")
        out.append("\nViews available: v_rx_enriched, v_activity_enriched")
        return "\n".join(out)

    table = table.strip().lower()
    if not table.replace("_", "").isalnum():
        return f"Invalid table name: {table!r}"
    _, type_rows = db.query(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name = %s ORDER BY ordinal_position",
        (table,),
    )
    if not type_rows:
        return f"Table or view not found: {table}"
    col_names, sample = db.query(f"SELECT * FROM {table} LIMIT 3")
    lines = [f"Table: {table}", "Columns:"]
    for cname, ctype in type_rows:
        lines.append(f"  - {cname}: {ctype}")
    lines.append("Sample rows:")
    for row in sample:
        lines.append(f"  {dict(zip(col_names, [_jsonable(v) for v in row]))}")
    return "\n".join(lines)


@tool
def run_sql(query: str) -> str:
    """Execute a read-only SQL query against the Postgres database. Returns up to 50 rows as JSON. On error, returns the Postgres error verbatim - fix and retry."""
    q = query.strip().rstrip(";")
    lowered = q.lower()
    forbidden = (
        "insert ",
        "update ",
        "delete ",
        "drop ",
        "alter ",
        "truncate ",
        "create ",
        "grant ",
        "revoke ",
    )
    if any(tok in lowered for tok in forbidden):
        return "ERROR: write/DDL statements are not allowed. Use SELECT only."
    try:
        cols, rows = db.query(
            f"SELECT * FROM ({q}) _wrapped LIMIT {MAX_ROWS_RETURNED + 1}"
        )
    except Exception as e:
        return f"ERROR: {e}"
    truncated = len(rows) > MAX_ROWS_RETURNED
    rows = rows[:MAX_ROWS_RETURNED]
    payload = {
        "columns": cols,
        "rows": [[_jsonable(v) for v in r] for r in rows],
        "row_count": len(rows),
        "truncated": truncated,
    }
    return json.dumps(payload, default=str)


@tool
def run_python(code: str) -> str:
    """Run Python (pandas/numpy pre-imported, plus a `query(sql)` helper that returns a DataFrame). 10s timeout. Use ONLY for simulation or multi-step computation that SQL can't express. Print results - anything not printed is lost."""
    from .tools import run_python_sandbox

    return run_python_sandbox(code)


@tool
def make_chart(data_json: str, vega_lite_spec: str = "{}") -> str:
    """Render a Vega-Lite chart for the user. data_json is a JSON array of records; vega_lite_spec is a JSON string of the Vega-Lite spec (without the `data` field - it will be injected). Returns a confirmation; the chart is shown to the user automatically."""
    from .tools import build_chart

    # Handle case where model embeds both data_json and vega_lite_spec in a single JSON object
    if not vega_lite_spec or vega_lite_spec == "{}":
        try:
            payload = json.loads(data_json)
            if isinstance(payload, dict) and "vega_lite_spec" in payload:
                d = payload.get("data_json", "[]")
                v = payload.get("vega_lite_spec", "{}")
                if isinstance(d, (list, dict)):
                    d = json.dumps(d)
                if isinstance(v, dict):
                    v = json.dumps(v)
                return build_chart(d, v)
        except (json.JSONDecodeError, TypeError):
            pass

    return build_chart(data_json, vega_lite_spec)


def _jsonable(v: Any) -> Any:
    from datetime import date, datetime
    from decimal import Decimal

    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


# ---------- Agent ----------

TOOLS = [list_schema, run_sql, run_python, make_chart]

_REACT_PROMPT = PromptTemplate.from_template(
    prompts.ASSISTANT_PROMPT
    + """
Available tools:
{tools}

Use EXACTLY this format — no deviations:

Thought: your reasoning (which table/view/column to use and why)
Action: one of [{tool_names}]
Action Input: the tool input (plain SQL string for run_sql; plain Python for run_python; JSON object for make_chart)
Observation: the tool result
... (repeat Thought/Action/Action Input/Observation as needed, up to 10 times)
Thought: I now know the final answer
Final Answer: your complete answer

Begin!

Question: {input}
Thought:{agent_scratchpad}"""
)


def build_executor() -> AgentExecutor:
    primary = _build_llm(PRIMARY_MODEL)
    fallback = _build_llm(FALLBACK_MODEL)
    llm = primary.with_fallbacks([fallback])
    agent = create_react_agent(llm, TOOLS, _REACT_PROMPT)
    return AgentExecutor(
        agent=agent,
        tools=TOOLS,
        max_iterations=10,
        handle_parsing_errors=True,
        return_intermediate_steps=True,
        verbose=False,
    )


_executor: AgentExecutor | None = None


def get_executor() -> AgentExecutor:
    global _executor
    if _executor is None:
        _executor = build_executor()
    return _executor
