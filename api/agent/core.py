"""LangChain tool-calling agent over Postgres."""

import json
import os
from dataclasses import dataclass
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

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


class ListSchemaInput(BaseModel):
    table: str | None = Field(
        default=None,
        description="Optional table or view name. If omitted, list available tables/views.",
    )


class RunSQLInput(BaseModel):
    query: str = Field(
        description=(
            "A single read-only Postgres SELECT query. Do not include INSERT, "
            "UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, GRANT, REVOKE, "
            "or multiple statements."
        )
    )


class RunPythonInput(BaseModel):
    code: str = Field(
        description="Python code to run in the sandbox. Must print the final result."
    )


class MakeChartInput(BaseModel):
    data_json: str = Field(description="JSON array of chart-ready records.")
    vega_lite_spec: str = Field(
        description="Vega-Lite spec without the data field; the tool injects data."
    )


@tool(args_schema=ListSchemaInput)
def list_schema(table: str | None = None) -> str:
    """Inspect database schema. Use when unsure about available tables, views, columns, or sample values."""
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


@tool(args_schema=RunSQLInput)
def run_sql(query: str) -> str:
    """Run a read-only Postgres SQL query. Best for factual data questions, counts, sums, joins, filters, rankings, trends, and aggregations. Returns up to 50 rows as JSON."""
    q = query.strip().rstrip(";")
    if not q:
        return "ERROR: query is empty."
    if ";" in q:
        return "ERROR: multiple SQL statements are not allowed. Use one SELECT query."
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
    if not (lowered.startswith("select ") or lowered.startswith("with ")):
        return "ERROR: only SELECT queries are allowed."
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


@tool(args_schema=RunPythonInput)
def run_python(code: str) -> str:
    """Run sandboxed Python. Use only for simulations, forecasting, statistical calculations, or multi-step dataframe analysis that SQL cannot express cleanly."""
    from .tools import run_python_sandbox

    return run_python_sandbox(code)


@tool(args_schema=MakeChartInput)
def make_chart(data_json: str, vega_lite_spec: str) -> str:
    """Create a Vega-Lite chart from already-computed data. Use only after SQL or Python has produced chart-ready records."""
    from .tools import build_chart

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


@dataclass
class ToolTraceAction:
    tool: str
    tool_input: Any


def extract_final_answer(messages: list[Any]) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage) and not getattr(message, "tool_calls", None):
            return _message_text(message.content)
    return ""


def extract_intermediate_steps(messages: list[Any]) -> list[tuple[ToolTraceAction, str]]:
    steps: list[tuple[ToolTraceAction, str]] = []
    pending: dict[str, ToolTraceAction] = {}

    for message in messages:
        for call in getattr(message, "tool_calls", []) or []:
            call_id = call.get("id")
            name = call.get("name", "?")
            args = call.get("args", {})
            if call_id:
                pending[call_id] = ToolTraceAction(tool=name, tool_input=args)

        tool_call_id = getattr(message, "tool_call_id", None)
        if tool_call_id and tool_call_id in pending:
            steps.append((pending.pop(tool_call_id), _message_text(message.content)))

    return steps


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "".join(parts)
    return str(content) if content is not None else ""


def build_agent():
    primary = _build_llm(PRIMARY_MODEL)
    fallback = _build_llm(FALLBACK_MODEL)
    llm = primary.with_fallbacks([fallback])
    return create_agent(
        model=llm,
        tools=TOOLS,
        system_prompt=prompts.ASSISTANT_PROMPT,
    )


_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent
