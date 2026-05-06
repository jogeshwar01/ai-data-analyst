"""FastAPI entrypoint."""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import db
from agent import get_agent
import conversation
import insights as insights_mod
import coach as coach_mod


LOGS_FILE = Path(__file__).parent / "logs.md"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.bootstrap(force=False)
    # Pre-warm insight cache in the background so first /insights is instant.
    try:
        insights_mod.get_insights()
    except Exception as e:
        print(f"[insights] pre-warm failed: {e}")
    yield


app = FastAPI(title="Gazyva", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    session_id: UUID | None = None


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _append_chat_log(message: str, trace: list[dict], answer: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"## {ts}", f"**Q:** {message}", ""]
    if trace:
        lines.append("**Trace:**")
        for entry in trace:
            if entry["type"] == "thought":
                preview = entry["text"].replace("\n", " ").strip()[:200]
                lines.append(f"> {preview}")
            else:
                inp = (
                    json.dumps(entry["input"], default=str)
                    if not isinstance(entry["input"], str)
                    else entry["input"]
                )
                lines.append(f"→ {entry['name']}({inp[:120]})")
                lines.append(f"← {entry['output'][:200]}")
        lines.append("")
    lines += [f"**A:** {answer}", "", "---", ""]
    with LOGS_FILE.open("a") as f:
        f.write("\n".join(lines) + "\n")


def _event_text(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "content"):
        return _event_text(value.content)
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
                elif "text" in item:
                    parts.append(str(item.get("text", "")))
        return "".join(parts)
    return str(value)


async def _stream_chat(message: str, session_id: str | None):
    if not os.environ.get("OPENROUTER_API_KEY"):
        yield _sse("error", {"message": "OPENROUTER_API_KEY not set on the server."})
        return

    history = conversation.get_chat_history(session_id)
    messages = conversation.build_messages(history, message)
    agent = get_agent()
    answer_chunks: list[str] = []
    trace: list[dict] = []
    pending_tools: dict[str, dict] = {}

    try:
        async for event in agent.astream_events(
            {"messages": messages},
            version="v2",
        ):
            kind = event.get("event")
            if kind == "on_tool_start":
                tool_name = event["name"]
                if tool_name.startswith("_"):
                    continue
                tool_input = event.get("data", {}).get("input") or {}
                run_id = event.get("run_id") or tool_name
                pending_tools[run_id] = {
                    "name": tool_name,
                    "input": tool_input,
                    "output": "",
                }
                yield _sse("tool_start", {"name": tool_name, "input": tool_input})
            elif kind == "on_tool_end":
                tool_name = event["name"]
                if tool_name.startswith("_"):
                    continue
                run_id = event.get("run_id") or tool_name
                current_tool = pending_tools.pop(
                    run_id,
                    {"name": tool_name, "input": {}, "output": ""},
                )
                output = event["data"].get("output")
                out_str = _event_text(output)[:8000]
                current_tool["output"] = out_str
                trace.append({"type": "tool", **current_tool})
                yield _sse("tool_end", {"name": tool_name, "output": out_str})
            elif kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                token = _event_text(chunk)
                if token:
                    answer_chunks.append(token)
                    yield _sse("token", {"text": token})
            await asyncio.sleep(0)

        answer = "".join(answer_chunks).strip()
        yield _sse("done", {"answer": answer})
        conversation.save_chat_turn(session_id, message, answer)
        try:
            _append_chat_log(message, trace, answer)
        except Exception:
            pass
    except Exception as e:
        yield _sse("error", {"message": str(e)})


@app.post("/chat")
async def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(400, "Empty message")
    session_id = str(req.session_id) if req.session_id else None
    return StreamingResponse(
        _stream_chat(req.message, session_id),
        media_type="text/event-stream",
    )


@app.get("/insights")
async def get_insights(force: bool = False):
    return insights_mod.get_insights(force=force)


@app.get("/coach/reps")
async def list_reps():
    return coach_mod.get_reps()


@app.get("/coach/{rep_id}")
async def get_coach(rep_id: int):
    result = coach_mod.get_coaching(rep_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@app.post("/eval")
async def run_eval_endpoint():
    """Run the golden eval set. Returns pass/fail per question."""
    import asyncio
    from eval.run import run_eval
    loop = asyncio.get_event_loop()
    passed, total = await loop.run_in_executor(None, run_eval)
    from eval.run import REPORT_FILE
    report = REPORT_FILE.read_text() if REPORT_FILE.exists() else ""
    return {"passed": passed, "total": total, "score": f"{passed}/{total}", "report_md": report}


@app.get("/health")
async def health():
    cols, rows = db.query("SELECT COUNT(*) FROM fact_rx")
    return {"status": "ok", "fact_rx_rows": rows[0][0]}
