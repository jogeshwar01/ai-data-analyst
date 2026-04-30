"""FastAPI entrypoint."""
from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import db
from agent import get_executor


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.bootstrap(force=False)
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
    try:
        async for event in executor.astream_events({"input": message}, version="v2"):
            kind = event["event"]
            if kind == "on_tool_start":
                yield _sse("tool_start", {
                    "name": event["name"],
                    "input": event["data"].get("input", {}),
                })
            elif kind == "on_tool_end":
                output = event["data"].get("output")
                if hasattr(output, "content"):
                    output = output.content
                yield _sse("tool_end", {
                    "name": event["name"],
                    "output": str(output)[:8000],
                })
            elif kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                token = getattr(chunk, "content", "") or ""
                if token:
                    answer_chunks.append(token)
                    yield _sse("token", {"text": token})
            await asyncio.sleep(0)
        yield _sse("done", {"answer": "".join(answer_chunks).strip()})
    except Exception as e:
        yield _sse("error", {"message": str(e)})


@app.post("/chat")
async def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(400, "Empty message")
    return StreamingResponse(_stream_chat(req.message), media_type="text/event-stream")


@app.get("/health")
async def health():
    cols, rows = db.query("SELECT COUNT(*) FROM fact_rx")
    return {"status": "ok", "fact_rx_rows": rows[0][0]}
