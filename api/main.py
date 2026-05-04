"""FastAPI entrypoint."""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from uuid import UUID

LOGS_FILE = Path(__file__).parent / "logs.md"


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
                inp = json.dumps(entry["input"], default=str) if not isinstance(entry["input"], str) else entry["input"]
                lines.append(f"→ {entry['name']}({inp[:120]})")
                lines.append(f"← {entry['output'][:200]}")
        lines.append("")
    lines += [f"**A:** {answer}", "", "---", ""]
    with LOGS_FILE.open("a") as f:
        f.write("\n".join(lines) + "\n")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import db
from agent import get_executor
import conversation
import insights as insights_mod
import coach as coach_mod


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


_FINAL_MARKER = "Final Answer:"
_MARKER_LEN = len(_FINAL_MARKER)


def _extract_thought_and_input(buf: str) -> tuple[str, str]:
    """Split ReAct buffer into (thought_text, action_input).

    Separates the Thought reasoning from the Action/Action Input lines.
    Returns both so thought goes to reasoning UI and action_input becomes tool_input.
    """
    text = buf.strip()
    thought = text
    action_input = ""

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
    else:
        thought = thought.strip()

    return thought, action_input


async def _stream_chat(message: str, session_id: str | None):
    if not os.environ.get("OPENROUTER_API_KEY"):
        yield _sse("error", {"message": "OPENROUTER_API_KEY not set on the server."})
        return

    executor = get_executor()
    history = conversation.get_chat_history(session_id)
    chat_history = conversation.format_chat_history(history)
    answer_chunks: list[str] = []
    trace: list[dict] = []
    current_tool: dict | None = None
    thought_buf = ""
    in_answer = False

    def _emit_thought(text: str) -> None:
        if text:
            trace.append({"type": "thought", "text": text})

    try:
        async for event in executor.astream_events(
            {"input": message, "chat_history": chat_history},
            version="v2",
        ):
            kind = event["event"]
            if kind == "on_tool_start":
                tool_name = event["name"]
                # Flush buffered thought; also extract Action Input (never in event["data"] for ReAct)
                thought_text, extracted_input = _extract_thought_and_input(thought_buf)
                thought_buf = ""
                if thought_text:
                    _emit_thought(thought_text)
                    yield _sse("thought", {"text": thought_text})
                # Skip internal AgentExecutor error-handling tools
                if tool_name.startswith("_"):
                    current_tool = None
                    continue
                # astream_events v2 always sends input={} for ReAct; use extracted Action Input
                raw = event["data"].get("input") or None
                tool_input = raw if (raw and raw != {}) else (extracted_input or {})
                current_tool = {"name": tool_name, "input": tool_input, "output": ""}
                yield _sse("tool_start", {"name": tool_name, "input": tool_input})
            elif kind == "on_tool_end":
                if event["name"].startswith("_") or current_tool is None:
                    current_tool = None
                    continue
                output = event["data"].get("output")
                if hasattr(output, "content"):
                    output = output.content
                out_str = str(output)[:8000]
                current_tool["output"] = out_str
                trace.append({"type": "tool", **current_tool})
                current_tool = None
                yield _sse("tool_end", {"name": event["name"], "output": out_str})
            elif kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                token = getattr(chunk, "content", "") or ""
                if token:
                    if in_answer:
                        answer_chunks.append(token)
                        yield _sse("token", {"text": token})
                    else:
                        thought_buf += token
                        if _FINAL_MARKER in thought_buf:
                            in_answer = True
                            idx = thought_buf.index(_FINAL_MARKER)
                            thought, _ = _extract_thought_and_input(thought_buf[:idx])
                            post = thought_buf[idx + _MARKER_LEN:].lstrip("\n ")
                            thought_buf = ""
                            if thought:
                                _emit_thought(thought)
                                yield _sse("thought", {"text": thought})
                            if post:
                                answer_chunks.append(post)
                                yield _sse("token", {"text": post})
            await asyncio.sleep(0)

        # Fallback: model didn't write "Final Answer:" — emit buffered content as answer
        if thought_buf.strip() and not in_answer:
            answer_chunks.append(thought_buf.strip())
            yield _sse("token", {"text": thought_buf.strip()})

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
