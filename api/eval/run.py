"""Golden eval harness. Run with: python -m eval.run"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import json
from langchain_openai import ChatOpenAI

# Ensure the api/ directory is on sys.path when run as a module.
sys.path.insert(0, str(Path(__file__).parent.parent))

import db
from agent import get_executor

GOLDEN_FILE = Path(__file__).parent / "golden.json"
REPORT_FILE = Path(__file__).parent / "report.md"

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
JUDGE_MODEL = os.environ.get("OPENROUTER_FALLBACK_MODEL", "openai/gpt-4o-mini")


# ---------- Graders ----------

def grade_exact_number(answer: str, expected: float, tolerance_pct: float = 1.0) -> tuple[bool, str]:
    nums = re.findall(r"[\d,]+(?:\.\d+)?", answer.replace(",", ""))
    for raw in nums:
        try:
            v = float(raw.replace(",", ""))
            if abs(v - expected) / max(expected, 1) * 100 <= tolerance_pct:
                return True, f"found {v} (expected {expected} ±{tolerance_pct}%)"
        except ValueError:
            pass
    return False, f"no number within {tolerance_pct}% of {expected} found in answer"


def grade_contains(answer: str, expected: list[str]) -> tuple[bool, str]:
    lower = answer.lower()
    missing = [e for e in expected if e.lower() not in lower]
    if missing:
        return False, f"missing: {missing}"
    return True, f"all expected strings found"


def grade_set_overlap(answer: str, expected: list[str], min_overlap: int) -> tuple[bool, str]:
    lower = answer.lower()
    found = [e for e in expected if e.lower() in lower]
    ok = len(found) >= min_overlap
    return ok, f"{len(found)}/{len(expected)} found (need {min_overlap}): {found}"


def grade_llm_judge(answer: str, rubric: str) -> tuple[bool, str]:
    llm = ChatOpenAI(
        model=JUDGE_MODEL,
        base_url=OPENROUTER_BASE,
        api_key=os.environ["OPENROUTER_API_KEY"],
        temperature=0,
    )
    prompt = (
        f"You are grading an AI agent's answer to an analytics question.\n\n"
        f"RUBRIC:\n{rubric.strip()}\n\n"
        f"ANSWER TO GRADE:\n{answer.strip()}\n\n"
        f"Reply with exactly one word on the first line: PASS or FAIL. "
        f"Then on the next line give a one-sentence reason."
    )
    response = llm.invoke(prompt).content.strip()
    lines = response.splitlines()
    verdict = lines[0].strip().upper()
    reason = lines[1].strip() if len(lines) > 1 else response
    passed = verdict.startswith("PASS")
    return passed, reason


def run_agent(question: str) -> tuple[str, float]:
    executor = get_executor()
    t0 = time.time()
    result = executor.invoke({"input": question})
    elapsed = round(time.time() - t0, 1)
    return result.get("output", ""), elapsed


def grade(case: dict[str, Any], answer: str) -> tuple[bool, str]:
    gt = case["grading"]
    if gt == "exact_number":
        return grade_exact_number(answer, float(case["expected"]), float(case.get("tolerance_pct", 1.0)))
    elif gt == "contains":
        return grade_contains(answer, case["expected"])
    elif gt == "set_overlap":
        return grade_set_overlap(answer, case["expected"], int(case["min_overlap"]))
    elif gt == "llm_judge":
        return grade_llm_judge(answer, case["rubric"])
    else:
        return False, f"unknown grading type: {gt}"


# ---------- Main ----------

def run_eval():
    db.pool.open()
    cases = json.loads(GOLDEN_FILE.read_text())
    results = []
    passed = 0

    print(f"\n{'='*60}")
    print(f"  Synthio Golden Eval — {len(cases)} questions")
    print(f"{'='*60}\n")

    for i, case in enumerate(cases, 1):
        qid = case["id"]
        question = case["question"]
        print(f"[{i:02d}/{len(cases)}] {qid}")
        print(f"  Q: {question}")

        try:
            answer, elapsed = run_agent(question)
            ok, detail = grade(case, answer)
        except Exception as e:
            answer = f"ERROR: {e}"
            ok, detail = False, str(e)
            elapsed = 0.0

        status = "✓ PASS" if ok else "✗ FAIL"
        if ok:
            passed += 1
        print(f"  {status}  ({elapsed}s)  {detail}")
        print(f"  A: {answer[:120].strip()}{'…' if len(answer) > 120 else ''}\n")

        results.append({
            "id": qid,
            "question": question,
            "answer": answer,
            "passed": ok,
            "detail": detail,
            "elapsed": elapsed,
        })

    total = len(cases)
    score = f"{passed}/{total}"
    print(f"\n{'='*60}")
    print(f"  RESULT: {score} passed")
    print(f"{'='*60}\n")

    # Write markdown report
    lines = [
        f"# Synthio Eval Report",
        f"",
        f"**Score: {score}** ({round(passed/total*100)}%)",
        f"",
        f"| # | ID | Pass | Time | Detail |",
        f"|---|---|---|---|---|",
    ]
    for r in results:
        icon = "✓" if r["passed"] else "✗"
        lines.append(f"| {r['id']} | {icon} | {r['elapsed']}s | {r['detail'][:60]} |")

    lines += ["", "## Answers", ""]
    for r in results:
        icon = "✓" if r["passed"] else "✗"
        lines += [
            f"### {icon} {r['id']}",
            f"**Q:** {r['question']}  ",
            f"**A:** {r['answer'][:500]}",
            f"**Grade:** {r['detail']}",
            "",
        ]

    REPORT_FILE.write_text("\n".join(lines))
    print(f"Report written to {REPORT_FILE}")
    return passed, total


if __name__ == "__main__":
    passed, total = run_eval()
    sys.exit(0 if passed >= 10 else 1)
