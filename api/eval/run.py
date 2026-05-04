"""Eval harness. Run with: python -m eval.run [--quick]"""

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
QUICK_FILE = Path(__file__).parent / "quick.json"
REPORT_FILE = Path(__file__).parent / "report.md"

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
JUDGE_MODEL = os.environ.get("OPENROUTER_FALLBACK_MODEL", "openai/gpt-4o-mini")


# ---------- Graders ----------


def grade_exact_number(
    answer: str, expected: float, tolerance_pct: float = 1.0
) -> tuple[bool, str]:
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


def grade_set_overlap(
    answer: str, expected: list[str], min_overlap: int
) -> tuple[bool, str]:
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


def run_agent(question: str) -> tuple[str, float, list]:
    executor = get_executor()
    t0 = time.time()
    result = executor.invoke(
        {"input": question, "chat_history": "No prior questions in this eval run."}
    )
    elapsed = round(time.time() - t0, 1)
    steps = result.get("intermediate_steps", [])
    return result.get("output", ""), elapsed, steps


def _preview(value: Any, limit: int = 200) -> str:
    s = json.dumps(value, default=str) if not isinstance(value, str) else value
    s = s.replace("\n", " ").strip()
    return s[:limit] + "…" if len(s) > limit else s


def print_steps(steps: list) -> None:
    for action, output in steps:
        tool_name = getattr(action, "tool", "?")
        tool_input = getattr(action, "tool_input", "")
        print(f"    → {tool_name}({_preview(tool_input, 120)})")
        print(f"    ← {_preview(str(output), 160)}")


def grade(case: dict[str, Any], answer: str) -> tuple[bool, str]:
    gt = case["grading"]
    if gt == "exact_number":
        return grade_exact_number(
            answer, float(case["expected"]), float(case.get("tolerance_pct", 1.0))
        )
    elif gt == "contains":
        return grade_contains(answer, case["expected"])
    elif gt == "set_overlap":
        return grade_set_overlap(answer, case["expected"], int(case["min_overlap"]))
    elif gt == "llm_judge":
        return grade_llm_judge(answer, case["rubric"])
    else:
        return False, f"unknown grading type: {gt}"


# ---------- Main ----------


def run_eval(quick: bool = False):
    db.pool.open()
    source = QUICK_FILE if quick else GOLDEN_FILE
    cases = json.loads(source.read_text())
    label = "Quick Eval (5 Qs)" if quick else f"Golden Eval - {len(cases)} questions"
    results = []
    passed = 0

    print(f"\n{'='*60}")
    print(f"  Gazyva {label}")
    print(f"{'='*60}\n")

    for i, case in enumerate(cases, 1):
        qid = case["id"]
        question = case["question"]
        print(f"[{i:02d}/{len(cases)}] {qid}")
        print(f"  Q: {question}")

        try:
            answer, elapsed, steps = run_agent(question)
            print_steps(steps)
            ok, detail = grade(case, answer)
        except Exception as e:
            answer = f"ERROR: {e}"
            ok, detail = False, str(e)
            elapsed = 0.0
            steps = []

        status = "✓ PASS" if ok else "✗ FAIL"
        if ok:
            passed += 1
        print(f"  {status}  ({elapsed}s)  {detail}")
        print(f"  A: {answer[:200].strip()}{'…' if len(answer) > 200 else ''}\n")

        results.append(
            {
                "id": qid,
                "question": question,
                "answer": answer,
                "passed": ok,
                "detail": detail,
                "elapsed": elapsed,
                "steps": [
                    (getattr(a, "tool", "?"), getattr(a, "tool_input", ""), str(o))
                    for a, o in steps
                ],
            }
        )

    total = len(cases)
    score = f"{passed}/{total}"
    print(f"\n{'='*60}")
    print(f"  RESULT: {score} passed")
    print(f"{'='*60}\n")

    # Write markdown report
    lines = [
        f"# Gazyva Eval Report",
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
            f"**Grade:** {r['detail']}  ",
            "",
        ]
        if r["steps"]:
            lines.append("**Trace:**")
            lines.append("```")
            for tool_name, tool_input, output in r["steps"]:
                lines.append(f"→ {tool_name}({_preview(tool_input, 120)})")
                lines.append(f"← {_preview(output, 200)}")
            lines.append("```")
            lines.append("")
        lines += [
            f"**Answer:** {r['answer'][:500]}{'…' if len(r['answer']) > 500 else ''}",
            "",
        ]

    REPORT_FILE.write_text("\n".join(lines))
    print(f"Report written to {REPORT_FILE}")
    return passed, total


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    passed, total = run_eval(quick=quick)
    threshold = 4 if quick else 10
    sys.exit(0 if passed >= threshold else 1)
