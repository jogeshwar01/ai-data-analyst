"""Short-term chat history stored in Redis with an in-memory fallback."""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import redis

HISTORY_TURNS = int(os.environ.get("CHAT_HISTORY_TURNS", "5"))
HISTORY_TTL_SECONDS = int(os.environ.get("CHAT_HISTORY_TTL_SECONDS", str(7 * 24 * 60 * 60)))
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

_QUESTION_CHARS = 500
_ANSWER_CHARS = 1500

_r: Optional[redis.Redis] = None
_memory_history: Dict[str, List[Dict[str, str]]] = {}


def get_chat_history(session_id: Optional[str]) -> List[Dict[str, str]]:
    if not session_id:
        return []
    try:
        raw_items = _redis_client().lrange(_history_key(session_id), -HISTORY_TURNS, -1)
        turns = [_decode_turn(item) for item in raw_items]
        return [turn for turn in turns if turn is not None]
    except redis.RedisError:
        return list(_memory_history.get(session_id, []))[-HISTORY_TURNS:]


def save_chat_turn(session_id: Optional[str], question: str, answer: str) -> None:
    if not session_id or not question.strip() or not answer.strip():
        return

    turn = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "question": _clip(question.strip(), _QUESTION_CHARS),
        "answer": _clip(answer.strip(), _ANSWER_CHARS),
    }
    encoded = json.dumps(turn, default=str)

    try:
        pipe = _redis_client().pipeline()
        key = _history_key(session_id)
        pipe.rpush(key, encoded)
        pipe.ltrim(key, -HISTORY_TURNS, -1)
        pipe.expire(key, HISTORY_TTL_SECONDS)
        pipe.execute()
    except redis.RedisError:
        turns = _memory_history.setdefault(session_id, [])
        turns.append(turn)
        del turns[:-HISTORY_TURNS]


def format_chat_history(turns: List[Dict[str, str]]) -> str:
    if not turns:
        return "No prior questions in this session."

    lines = [
        "Last completed turns in this session. Use them only to resolve follow-up references; answer the current question directly."
    ]
    for idx, turn in enumerate(turns, 1):
        question = turn.get("question", "").strip()
        answer = turn.get("answer", "").strip()
        if not question and not answer:
            continue
        lines.append(f"{idx}. User: {question}")
        lines.append(f"   Assistant: {answer}")
    return "\n".join(lines)


def _redis_client() -> redis.Redis:
    global _r
    if _r is None:
        _r = redis.from_url(REDIS_URL, decode_responses=True)
    return _r


def _history_key(session_id: str) -> str:
    return f"chat:history:{session_id}"


def _decode_turn(item: Any) -> Optional[Dict[str, str]]:
    try:
        turn = json.loads(item)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(turn, dict):
        return None
    return {
        "ts": str(turn.get("ts", "")),
        "question": str(turn.get("question", "")),
        "answer": str(turn.get("answer", "")),
    }


def _clip(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "..."
