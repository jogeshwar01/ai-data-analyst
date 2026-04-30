"""Python sandbox + Vega-Lite chart builder — used by agent tools."""

import json
import os
import subprocess
import textwrap


# ---------- Python sandbox ----------

_PREAMBLE = textwrap.dedent("""\
    import os, sys
    import pandas as pd
    import numpy as np

    def query(sql: str) -> pd.DataFrame:
        \"\"\"Run read-only SQL against the database, return a DataFrame.\"\"\"
        import psycopg
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                cols = [d.name for d in cur.description]
                rows = cur.fetchall()
        return pd.DataFrame(rows, columns=cols)

""")


def run_python_sandbox(code: str) -> str:
    full = _PREAMBLE + code
    try:
        result = subprocess.run(
            ["python3", "-c", full],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        if result.returncode != 0:
            return f"ERROR:\n{result.stderr[:3000]}"
        out = result.stdout.strip()
        if not out:
            return "(no output printed — remember to print() your results)"
        return out[:6000]
    except subprocess.TimeoutExpired:
        return "ERROR: execution timed out (10s limit)"
    except Exception as e:
        return f"ERROR: {e}"


# ---------- Chart builder ----------

def build_chart(data_json: str, vega_lite_spec: str) -> str:
    """Validate spec + embed data. Returns a JSON envelope the frontend detects."""
    try:
        data = json.loads(data_json) if isinstance(data_json, str) else data_json
        spec = json.loads(vega_lite_spec) if isinstance(vega_lite_spec, str) else vega_lite_spec
    except json.JSONDecodeError as e:
        return f"ERROR: invalid JSON — {e}"

    if not isinstance(data, list):
        return "ERROR: data_json must be a JSON array of record objects"

    spec = dict(spec)
    spec["data"] = {"values": data}
    spec.setdefault("$schema", "https://vega.github.io/schema/vega-lite/v5.json")
    spec.setdefault("background", "transparent")

    return json.dumps({"__type": "chart", "spec": spec})
