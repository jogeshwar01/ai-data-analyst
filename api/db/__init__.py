"""Postgres connection pool + one-shot CSV bootstrap."""

import os
from pathlib import Path

from psycopg_pool import ConnectionPool

DATABASE_URL = os.environ["DATABASE_URL"]
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
SCHEMA_FILE = Path(__file__).parent / "schema.sql"

# Order matters: dims before facts (for FK resolution).
LOAD_ORDER = [
    "territory_dim",
    "rep_dim",
    "account_dim",
    "hcp_dim",
    "date_dim",
    "fact_rx",
    "fact_rep_activity",
    "fact_payor_mix",
    "fact_ln_metrics",
]

pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=8, open=False)


def bootstrap(force: bool = False) -> None:
    """Create schema + load CSVs. Idempotent — skips load if fact_rx already populated."""
    pool.open()
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(SCHEMA_FILE.read_text())
        cur.execute("SELECT COUNT(*) FROM fact_rx")
        already_loaded = cur.fetchone()[0] > 0
        if already_loaded and not force:
            print(f"[bootstrap] fact_rx has rows; skipping CSV load (force=False).")
            return

        for table in LOAD_ORDER:
            csv_path = DATA_DIR / f"{table}.csv"
            if not csv_path.exists():
                raise FileNotFoundError(f"Missing CSV: {csv_path}")
            cur.execute(f"TRUNCATE {table} CASCADE")
            with open(csv_path, "rb") as f, cur.copy(
                f"COPY {table} FROM STDIN WITH (FORMAT CSV, HEADER, NULL '')"
            ) as copy:
                while data := f.read(65536):
                    copy.write(data)
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            n = cur.fetchone()[0]
            print(f"[bootstrap] loaded {table}: {n} rows")
        conn.commit()


def query(sql: str, params: tuple = ()) -> tuple[list[str], list[tuple]]:
    """Run a read-only query, return (column_names, rows)."""
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d.name for d in cur.description] if cur.description else []
        rows = cur.fetchall() if cur.description else []
    return cols, rows
