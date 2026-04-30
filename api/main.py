"""FastAPI entrypoint."""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

LOGS_FILE = Path(__file__).parent / "logs.md"


def _append_chat_log(message: str, tools: list[dict], answer: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"## {ts}", f"**Q:** {message}", ""]
    if tools:
        lines += ["**Trace:**", "```"]
        for t in tools:
            inp = json.dumps(t["input"], default=str) if not isinstance(t["input"], str) else t["input"]
            lines.append(f"→ {t['name']}({inp[:120]})")
            lines.append(f"← {t['output'][:200]}")
        lines += ["```", ""]
    lines += [f"**A:** {answer}", "", "---", ""]
    with LOGS_FILE.open("a") as f:
        f.write("\n".join(lines) + "\n")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import db
from agent import get_executor
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


app = FastAPI(title="Synthio QA", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


async def _stream_chat(message: str):
    if not os.environ.get("OPENROUTER_API_KEY"):
        yield _sse("error", {"message": "OPENROUTER_API_KEY not set on the server."})
        return

    executor = get_executor()
    answer_chunks: list[str] = []
    tool_log: list[dict] = []
    current_tool: dict | None = None
    try:
        async for event in executor.astream_events({"input": message}, version="v2"):
            kind = event["event"]
            if kind == "on_tool_start":
                current_tool = {"name": event["name"], "input": event["data"].get("input", {}), "output": ""}
                yield _sse("tool_start", {"name": current_tool["name"], "input": current_tool["input"]})
            elif kind == "on_tool_end":
                output = event["data"].get("output")
                if hasattr(output, "content"):
                    output = output.content
                out_str = str(output)[:8000]
                if current_tool:
                    current_tool["output"] = out_str
                    tool_log.append(current_tool)
                    current_tool = None
                yield _sse("tool_end", {"name": event["name"], "output": out_str})
            elif kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                token = getattr(chunk, "content", "") or ""
                if token:
                    answer_chunks.append(token)
                    yield _sse("token", {"text": token})
            await asyncio.sleep(0)
        answer = "".join(answer_chunks).strip()
        yield _sse("done", {"answer": answer})
        try:
            _append_chat_log(message, tool_log, answer)
        except Exception:
            pass
    except Exception as e:
        yield _sse("error", {"message": str(e)})


@app.post("/chat")
async def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(400, "Empty message")
    return StreamingResponse(_stream_chat(req.message), media_type="text/event-stream")


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
