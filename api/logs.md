## 2026-04-30 13:26:55

**Q:** Top 5 HCPs by TRx in the last 90 days

**Trace:**

```
→ run_sql({"query": "WITH bounds AS (SELECT MAX(calendar_date) AS hi FROM date_dim WHERE date_id IN (SELECT date_id FROM fact_rx)))
← {"columns": ["hcp_name", "specialty", "tier", "total_trx"], "rows": [["Dr Sage Jackson", "Internal Medicine", "B", 86], ["Dr Blake Garcia", "Rheumatology", "C", 84], ["Dr Cameron Clark", "Rheumatology
```

**A:** Here are the top 5 HCPs by total TRx in the last 90 days:

| Rank | HCP Name          | Specialty         | Tier | Total TRx |
| ---- | ----------------- | ----------------- | ---- | --------- |
| 1    | Dr Sage Jackson   | Internal Medicine | B    | 86        |
| 2    | Dr Blake Garcia   | Rheumatology      | C    | 84        |
| 3    | Dr Cameron Clark  | Rheumatology      | C    | 83        |
| 4    | Dr Phoenix Lee    | Rheumatology      | B    | 79        |
| 5    | Dr Hayden Jackson | Internal Medicine | A    | 77        |

**Note:** The top two HCPs by volume are tier B and C, respectively, and the list includes a mix of Internal Medicine and Rheumatology specialties.

---

## 2026-04-30 13:29:41

**Q:** What data do we have for each account?

**Trace:**

```
→ list_schema({"table": "fact_ln_metrics"})
← Table: account_dim
Columns:
  - account_id: integer
  - name: text
  - account_type: text
  - address: text
  - territory_id: integer
Sample rows:
  {'account_id': 1000, 'name': 'Mountain Hospital', '
→ list_schema({"table": "fact_rep_activity"})
← Table: fact_rep_activity
Columns:
  - activity_id: integer
  - rep_id: integer
  - hcp_id: bigint
  - account_id: integer
  - date_id: integer
  - activity_type: text
  - status: text
  - time_of_day:
```

**A:** For each account, we have four categories of data:

**1. Static profile (account_dim)**

- `name`, `account_type` (Hospital or Clinic), `address`, `territory_id`

**2. Payor mix snapshots (fact_payor_mix)**

- Monthly breakdown of `payor_type` (Commercial, Medicare, Medicaid, Other) as `pct_of_volume` (0–100)

**3. Market metrics (fact_ln_metrics)**

- Quarterly `ln_patient_cnt` and `est_market_share` (filter `entity_type = 'A'`)

**4. Rep activity (fact_rep_activity)**

- All activities tied to the account: `activity_type` (call / lunch_meeting), `status` (completed / cancelled), `time_of_day`, `duration_min`, plus the `rep_id` and `hcp_id` involved

_Note:_ Prescription volume (fact_rx) is tracked at the **HCP level**, not directly by account. To attribute Rx to an account you would need to join through the rep-activity bridge or map HCPs to accounts via territory.

---

## 2026-04-30 13:37:08

**Q:** If rep 3 doubled their completed calls to tier-B HCPs, what would be the projected TRx lift be?

**Trace:**

```
→ run_python({"code": "import numpy as np\n\n# 1. Historical TRx per completed call ratio (per HCP)\ndf = query(\"\"\"\n    SELECT a.)
← Rep 3 current completed calls to tier-B HCPs: 56
Extra calls if doubled: 56
Average TRx per call (across all HCPs): 17.03
Std dev TRx per call: 1.82
Number of tier-B HCPs rep 3 calls: 8
Estimated TRx
```

**A:** If Rep 3 doubled their completed calls to tier-B HCPs, the projected TRx lift is **+954 TRx** (95% CI: ±10).

**Methodology & assumptions:**

- Rep 3 currently makes **56 completed calls** to **8 tier-B HCPs**. Doubling means adding 56 extra calls.
- I calculated the historical TRx-per-completed-call ratio for each HCP across the dataset (mean = **17.03 TRx per call**, std dev = 1.82).
- I assumed the incremental calls would perform at the same average rate and applied the standard error across the 8 HCPs to build the confidence interval.

_Note: This assumes a linear relationship and that the additional calls reach HCPs with similar responsiveness to the historical average._

---

## 2026-04-30 13:38:46

**Q:** what did i ask

**A:** This appears to be the start of our conversation - I don’t see a previous question. I’m ready to help you with the GAZYVA dataset (e.g., Rx trends, HCP performance, rep activity, payor mix, market share, or what-if scenarios). What would you like to know?

---

## 2026-04-30 13:43:12

**Q:** Show me monthly TRx per territory as a chart.

**Trace:**

```
→ run_sql({"query": "SELECT territory_name, DATE_TRUNC('month', calendar_date)::date AS month, SUM(trx_cnt) AS trx FROM v_rx_enric)
← {"columns": ["territory_name", "month", "trx"], "rows": [["Territory 1", "2024-08-01", 527], ["Territory 2", "2024-08-01", 524], ["Territory 3", "2024-08-01", 479], ["Territory 1", "2024-09-01", 441],
→ run_sql({"query": "SELECT territory_name, DATE_TRUNC('month', calendar_date)::date AS month, SUM(trx_cnt) AS trx FROM v_rx_enric)
← {"columns": ["territory_name", "month", "trx"], "rows": [["Territory 1", "2025-12-01", 513], ["Territory 2", "2025-12-01", 593], ["Territory 3", "2025-12-01", 483]], "row_count": 3, "truncated": false
→ run_python({"code": "import json\n\ndf = query(\"\"\"\n    SELECT \n        territory_name, \n        DATE_TRUNC('month', calendar_)
← [{"territory_name":"Territory 1","month":"2024-08-01","trx":527},{"territory_name":"Territory 2","month":"2024-08-01","trx":524},{"territory_name":"Territory 3","month":"2024-08-01","trx":479},{"terri
→ make_chart({"data_json": "[{\"territory_name\":\"Territory 1\",\"month\":\"2024-08-01\",\"trx\":527},{\"territory_name\":\"Territor)
← {"__type": "chart", "spec": {"$schema": "https://vega.github.io/schema/vega-lite/v5.json", "title": "Monthly TRx by Territory", "width": 600, "height": 300, "mark": {"type": "line", "point": true}, "e
```

**A:** Here is the monthly TRx trend by territory:

**Key takeaways:**

- All three territories operate in a similar band (~450–600 TRx/month).
- **Territory 1** is the most volatile, swinging from a high of 601 (Jan 2025) to lows of 434 (Nov 2024) and 454 (Apr 2025).
- **Territory 2** finished the year strongest at **593 TRx in Dec 2025**, though it had a soft patch in mid-2025 (449 in Jun).
- **Territory 3** showed solid momentum in Q3–Q4 2025, peaking at 575 in Sep, but dipped to 441 in Aug and 483 in Dec.

---
