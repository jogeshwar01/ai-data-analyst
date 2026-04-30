"""Six canned analyses that run at startup and are Redis-cached for 1 hour."""

import json
import os
from typing import Any

import redis as _redis

import db

CACHE_TTL = 3600  # 1 hour
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

_r: _redis.Redis | None = None


def _redis_client() -> _redis.Redis:
    global _r
    if _r is None:
        _r = _redis.from_url(REDIS_URL, decode_responses=True)
    return _r


# ---------- Canned analyses ----------


def _q(sql: str) -> list[dict]:
    cols, rows = db.query(sql)
    return [
        dict(zip(cols, [str(v) if v is not None else None for v in r])) for r in rows
    ]


ANALYSES: list[dict[str, Any]] = [
    {
        "id": "top_decliners",
        "title": "Biggest TRx Decliners",
        "subtitle": "HCPs whose Rx dropped most vs prior quarter",
        "icon": "TrendingDown",
        "sql": """
            WITH q AS (
              SELECT hcp_name, specialty, tier,
                     SUM(trx_cnt) FILTER (WHERE quarter = (SELECT MAX(quarter) FROM date_dim WHERE year=(SELECT MAX(year) FROM date_dim))) AS curr,
                     SUM(trx_cnt) FILTER (WHERE quarter = (
                       SELECT quarter FROM date_dim GROUP BY quarter ORDER BY MAX(calendar_date) DESC LIMIT 1 OFFSET 1
                     )) AS prev
              FROM v_rx_enriched
              GROUP BY 1,2,3
            )
            SELECT hcp_name, specialty, tier,
                   COALESCE(curr,0) AS curr_trx, COALESCE(prev,0) AS prev_trx,
                   COALESCE(curr,0) - COALESCE(prev,0) AS delta
            FROM q
            WHERE COALESCE(prev,0) > 0
            ORDER BY delta ASC LIMIT 5
        """,
        "narrative_template": "HCPs with the steepest TRx decline vs prior quarter. {top} dropped by {delta} scripts - worth prioritizing for rep engagement.",
    },
    {
        "id": "low_conversion_reps",
        "title": "Low Call→Rx Conversion Reps",
        "subtitle": "Reps whose calls aren't translating to prescriptions",
        "icon": "UserMinus",
        "sql": """
            WITH calls AS (
              SELECT rep_id, rep_name, COUNT(*) FILTER (WHERE status='completed') AS calls_done
              FROM v_activity_enriched GROUP BY 1,2
            ),
            rx AS (
              SELECT a.rep_id, SUM(r.trx_cnt) AS rep_trx
              FROM fact_rep_activity a
              JOIN fact_rx r USING (hcp_id)
              WHERE a.status = 'completed'
              GROUP BY 1
            )
            SELECT c.rep_name, c.calls_done, COALESCE(rx.rep_trx,0) AS associated_trx,
                   ROUND(COALESCE(rx.rep_trx,0)::numeric / NULLIF(c.calls_done,0), 1) AS trx_per_call
            FROM calls c LEFT JOIN rx ON c.rep_id = rx.rep_id
            ORDER BY trx_per_call ASC LIMIT 5
        """,
        "narrative_template": "Reps with the lowest TRx per completed call. {top} averages only {val} scripts per call - coaching opportunity.",
    },
    {
        "id": "payor_mix_shifts",
        "title": "Payor Mix Shifts >5pp",
        "subtitle": "Accounts with notable Medicare/Commercial swings",
        "icon": "ArrowLeftRight",
        "sql": """
            WITH monthly AS (
              SELECT account_id, date_id, payor_type, pct_of_volume,
                     LAG(pct_of_volume) OVER (PARTITION BY account_id, payor_type ORDER BY date_id) AS prev_pct
              FROM fact_payor_mix
            ),
            shifts AS (
              SELECT a.name AS account_name, m.payor_type,
                     m.pct_of_volume AS curr_pct, m.prev_pct,
                     ABS(m.pct_of_volume - m.prev_pct) AS shift_pp
              FROM monthly m JOIN account_dim a USING (account_id)
              WHERE ABS(m.pct_of_volume - COALESCE(m.prev_pct,m.pct_of_volume)) > 5
            )
            SELECT account_name, payor_type, ROUND(curr_pct,1) AS curr_pct,
                   ROUND(prev_pct,1) AS prev_pct, ROUND(shift_pp,1) AS shift_pp
            FROM shifts ORDER BY shift_pp DESC LIMIT 6
        """,
        "narrative_template": "{n} account-payor combinations shifted >5pp MoM. {top} saw the largest swing - check formulary access.",
    },
    {
        "id": "uncalled_tier_a",
        "title": "Tier-A HCPs - No Recent Call",
        "subtitle": "High-value doctors with zero rep contact in 60 days",
        "icon": "AlertCircle",
        "sql": """
            WITH last_call AS (
              SELECT hcp_id, MAX(calendar_date) AS last_contact
              FROM v_activity_enriched
              WHERE status = 'completed'
              GROUP BY hcp_id
            ),
            bounds AS (SELECT MAX(calendar_date) AS hi FROM date_dim)
            SELECT h.full_name AS hcp_name, h.specialty, t.name AS territory,
                   lc.last_contact,
                   (bounds.hi - lc.last_contact) AS days_since
            FROM hcp_dim h
            JOIN territory_dim t USING (territory_id)
            CROSS JOIN bounds
            LEFT JOIN last_call lc USING (hcp_id)
            WHERE h.tier = 'A'
              AND (lc.last_contact IS NULL OR (bounds.hi - lc.last_contact) > 60)
            ORDER BY days_since DESC NULLS FIRST
            LIMIT 8
        """,
        "narrative_template": "{n} Tier-A HCPs haven't had a completed rep call in 60+ days. These are your highest-priority targets.",
    },
    {
        "id": "territory_growth",
        "title": "Territory TRx Growth (MoM)",
        "subtitle": "Which territories are gaining or losing script momentum",
        "icon": "BarChart2",
        "sql": """
            WITH monthly AS (
              SELECT territory_name,
                     DATE_TRUNC('month', calendar_date) AS month,
                     SUM(trx_cnt) AS trx
              FROM v_rx_enriched GROUP BY 1, 2
            ),
            growth AS (
              SELECT territory_name, month, trx,
                     ROUND(
                       100.0*(trx - LAG(trx) OVER (PARTITION BY territory_name ORDER BY month))
                       / NULLIF(LAG(trx) OVER (PARTITION BY territory_name ORDER BY month),0), 1
                     ) AS mom_pct
              FROM monthly
            )
            SELECT territory_name, TO_CHAR(month,'Mon YYYY') AS period,
                   trx, mom_pct
            FROM growth
            WHERE month >= (SELECT MAX(month) FROM (SELECT DATE_TRUNC('month', calendar_date) AS month FROM v_rx_enriched) m) - INTERVAL '5 months'
              AND mom_pct IS NOT NULL
            ORDER BY territory_name, month
        """,
        "narrative_template": "Last 6 months of MoM TRx growth by territory. Look for diverging trends as an early signal.",
    },
    {
        "id": "specialty_concentration",
        "title": "Rx Concentration by Specialty",
        "subtitle": "Where scripts are concentrated across specialties",
        "icon": "PieChart",
        "sql": """
            SELECT specialty,
                   COUNT(DISTINCT hcp_id) AS hcp_count,
                   SUM(trx_cnt) AS total_trx,
                   ROUND(100.0*SUM(trx_cnt)/SUM(SUM(trx_cnt)) OVER (), 1) AS pct_of_total
            FROM v_rx_enriched
            GROUP BY specialty
            ORDER BY total_trx DESC
        """,
        "narrative_template": "{top} accounts for {pct}% of all GAZYVA scripts. Specialty mix informs targeting strategy.",
    },
]


def _narrative(analysis: dict, rows: list[dict]) -> str:
    """Fill in the template with real values from the query results."""
    tpl = analysis["narrative_template"]
    if not rows:
        return "No data returned for this analysis."
    first = rows[0]
    top = (
        first.get("hcp_name")
        or first.get("rep_name")
        or first.get("account_name")
        or first.get("territory_name")
        or first.get("specialty")
        or "-"
    )
    val = (
        first.get("trx_per_call")
        or first.get("delta")
        or first.get("shift_pp")
        or first.get("pct_of_total")
        or "-"
    )
    n = str(len(rows))
    pct = first.get("pct_of_total", "-")
    delta = first.get("delta", "-")
    return tpl.format(top=top, val=val, n=n, pct=pct, delta=delta)


def get_insights(force: bool = False) -> list[dict]:
    r = _redis_client()
    cache_key = "insights:v1"
    if not force:
        cached = r.get(cache_key)
        if cached:
            return json.loads(cached)

    results = []
    for a in ANALYSES:
        try:
            rows = _q(a["sql"])
            narrative = _narrative(a, rows)
            results.append(
                {
                    "id": a["id"],
                    "title": a["title"],
                    "subtitle": a["subtitle"],
                    "icon": a["icon"],
                    "rows": rows,
                    "narrative": narrative,
                    "dig_deeper_prompt": a["title"] + " - " + a["subtitle"],
                }
            )
        except Exception as e:
            results.append(
                {
                    "id": a["id"],
                    "title": a["title"],
                    "subtitle": a["subtitle"],
                    "icon": a["icon"],
                    "rows": [],
                    "narrative": f"Error: {e}",
                    "dig_deeper_prompt": a["title"],
                }
            )

    r.setex(cache_key, CACHE_TTL, json.dumps(results, default=str))
    return results
