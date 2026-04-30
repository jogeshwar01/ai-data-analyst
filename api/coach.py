"""Rep coaching logic - joins activity + Rx data to produce 3 next-best-actions."""

import db


def get_reps() -> list[dict]:
    _, rows = db.query(
        "SELECT rep_id, first_name || ' ' || last_name AS name, region FROM rep_dim ORDER BY rep_id"
    )
    return [{"rep_id": r[0], "name": r[1], "region": r[2]} for r in rows]


def get_coaching(rep_id: int) -> dict:
    # -- Rep summary --
    _, rep_rows = db.query(
        "SELECT rep_id, first_name || ' ' || last_name AS name, region FROM rep_dim WHERE rep_id = %s",
        (rep_id,),
    )
    if not rep_rows:
        return {"error": f"Rep {rep_id} not found"}
    rep_id_, rep_name, region = rep_rows[0]

    # -- Calls this rep completed --
    cols, call_rows = db.query(
        """
        SELECT hcp_id, COUNT(*) AS calls
        FROM v_activity_enriched
        WHERE rep_id = %s AND status = 'completed'
        GROUP BY hcp_id
    """,
        (rep_id,),
    )
    called_hcps = {r[0]: r[1] for r in call_rows}

    # -- All HCPs in this rep's territory with TRx potential --
    cols, hcp_rows = db.query(
        """
        WITH total_trx AS (
          SELECT hcp_id, SUM(trx_cnt) AS trx FROM fact_rx GROUP BY hcp_id
        )
        SELECT h.hcp_id, h.full_name, h.specialty, h.tier, h.territory_id,
               COALESCE(t.trx, 0) AS total_trx
        FROM hcp_dim h
        JOIN territory_dim td ON h.territory_id = td.territory_id
        LEFT JOIN total_trx t USING (hcp_id)
        WHERE td.name = %s
        ORDER BY total_trx DESC
    """,
        (region,),
    )

    # -- Compute trx_per_call across all reps for peer comparison --
    _, peer_rows = db.query("""
        WITH calls AS (
          SELECT rep_id, COUNT(*) FILTER (WHERE status='completed') AS calls_done
          FROM fact_rep_activity GROUP BY rep_id
        ),
        assoc_rx AS (
          SELECT a.rep_id, SUM(r.trx_cnt) AS rep_trx
          FROM fact_rep_activity a
          JOIN fact_rx r USING (hcp_id)
          WHERE a.status='completed'
          GROUP BY a.rep_id
        )
        SELECT c.rep_id,
               ROUND(COALESCE(rx.rep_trx,0)::numeric / NULLIF(c.calls_done,0), 2) AS trx_per_call
        FROM calls c LEFT JOIN assoc_rx rx ON c.rep_id = rx.rep_id
    """)
    peer_map = {r[0]: float(r[1]) for r in peer_rows}
    my_trx_per_call = peer_map.get(rep_id, 0)
    peer_avg = round(sum(peer_map.values()) / len(peer_map), 2) if peer_map else 0

    # -- Build next-best-actions --
    actions: list[dict] = []

    # 1. Under-covered high-potential HCPs (in territory, low calls, high TRx)
    under_covered = [
        r for r in hcp_rows if r[0] not in called_hcps or called_hcps[r[0]] < 3
    ]
    under_covered.sort(key=lambda r: -r[5])  # sort by TRx desc
    under_covered = under_covered[:3]
    if under_covered:
        names = ", ".join(f"{r[1]} ({r[3]}, {r[5]} TRx)" for r in under_covered[:3])
        actions.append(
            {
                "priority": 1,
                "action": "Cover high-potential under-visited HCPs",
                "detail": f"These HCPs in your territory have strong TRx but <3 completed calls from you: {names}.",
                "hcps": [
                    {
                        "hcp_id": r[0],
                        "name": r[1],
                        "tier": r[3],
                        "total_trx": r[5],
                        "your_calls": called_hcps.get(r[0], 0),
                    }
                    for r in under_covered
                ],
            }
        )

    # 2. Call-to-Rx conversion vs peers
    diff = round(my_trx_per_call - peer_avg, 2)
    if diff < 0:
        actions.append(
            {
                "priority": 2,
                "action": "Improve call-to-Rx conversion rate",
                "detail": f"Your TRx per completed call is {my_trx_per_call} vs team average of {peer_avg} ({abs(diff)} below average). Focus on meal meetings (higher conversion historically) with Tier-A HCPs.",
                "metric": {"your_trx_per_call": my_trx_per_call, "peer_avg": peer_avg},
            }
        )
    else:
        actions.append(
            {
                "priority": 2,
                "action": "Maintain strong conversion - share tactics with peers",
                "detail": f"Your TRx per completed call is {my_trx_per_call} vs team average of {peer_avg} (+{diff} above average).",
                "metric": {"your_trx_per_call": my_trx_per_call, "peer_avg": peer_avg},
            }
        )

    # 3. Tier-A HCPs with no recent call in 60 days
    _, dormant_rows = db.query(
        """
        WITH last_call AS (
          SELECT hcp_id, MAX(calendar_date) AS last_contact
          FROM v_activity_enriched
          WHERE rep_id = %s AND status = 'completed'
          GROUP BY hcp_id
        ),
        bounds AS (SELECT MAX(calendar_date) AS hi FROM date_dim)
        SELECT h.full_name, h.specialty, lc.last_contact,
               (bounds.hi - lc.last_contact) AS days_since
        FROM hcp_dim h
        JOIN territory_dim td ON h.territory_id = td.territory_id
        CROSS JOIN bounds
        LEFT JOIN last_call lc USING (hcp_id)
        WHERE h.tier = 'A' AND td.name = %s
          AND (lc.last_contact IS NULL OR (bounds.hi - lc.last_contact) > 60)
        ORDER BY days_since DESC NULLS FIRST
        LIMIT 5
    """,
        (rep_id, region),
    )

    if dormant_rows:
        names = ", ".join(f"{r[0]} ({r[3] or '60+'} days)" for r in dormant_rows[:3])
        actions.append(
            {
                "priority": 3,
                "action": "Re-engage dormant Tier-A HCPs",
                "detail": f"{len(dormant_rows)} Tier-A HCPs in your territory haven't had a call in 60+ days: {names}.",
                "hcps": [
                    {
                        "name": r[0],
                        "specialty": r[1],
                        "last_contact": str(r[2]) if r[2] else None,
                        "days_since": r[3],
                    }
                    for r in dormant_rows
                ],
            }
        )

    return {
        "rep_id": rep_id,
        "rep_name": rep_name,
        "region": region,
        "metrics": {
            "trx_per_call": my_trx_per_call,
            "peer_avg_trx_per_call": peer_avg,
            "total_hcps_in_territory": len(hcp_rows),
            "hcps_called": len(called_hcps),
        },
        "actions": sorted(actions, key=lambda a: a["priority"]),
    }
