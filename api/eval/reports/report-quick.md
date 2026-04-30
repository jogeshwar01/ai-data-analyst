# Synthio Eval Report

**Score: 5/5** (100%)

| # | ID | Pass | Time | Detail |
|---|---|---|---|---|
| Q1_hcp_count | ✓ | 17.0s | found 90.0 (expected 90.0 ±1.0%) |
| Q2_q4_2024_trx | ✓ | 25.9s | found 4563.0 (expected 4563.0 ±1.0%) |
| Q4_best_territory | ✓ | 31.4s | all expected strings found |
| Q8_best_rep | ✓ | 514.7s | all expected strings found |
| Q7_uncalled_tier_a | ✓ | 123.1s | 5/5 found (need 3): ['Dr Rowan Davis', 'Dr Drew Lee', 'Dr Ro |

## Answers

### ✓ Q1_hcp_count
**Q:** How many distinct HCPs prescribed GAZYVA?  
**Grade:** found 90.0 (expected 90.0 ±1.0%)  

**Trace:**
```
→ run_sql({"query": "SELECT COUNT(DISTINCT hcp_id) AS distinct_hcp_count FROM fact_rx WHERE brand_code = 'GAZYVA'"})
← {"columns": ["distinct_hcp_count"], "rows": [[90]], "row_count": 1, "truncated": false}
```

**Answer:**  90 distinct HCPs have prescribed GAZYVA in the dataset.

### ✓ Q2_q4_2024_trx
**Q:** What is the total TRx for Q4 2024?  
**Grade:** found 4563.0 (expected 4563.0 ±1.0%)  

**Trace:**
```
→ run_sql({"query": "SELECT SUM(trx_cnt) AS total_trx_q4_2024 FROM v_rx_enriched WHERE quarter = '2024Q4'"})
← {"columns": ["total_trx_q4_2024"], "rows": [[null]], "row_count": 1, "truncated": false}
→ run_sql({"query": "SELECT DISTINCT quarter FROM v_rx_enriched ORDER BY quarter"})
← {"columns": ["quarter"], "rows": [["Q1"], ["Q2"], ["Q3"], ["Q4"]], "row_count": 4, "truncated": false}
→ run_sql({"query": "SELECT SUM(trx_cnt) AS total_trx_q4_2024 FROM v_rx_enriched WHERE year = 2024 AND quarter = 'Q4'"})
← {"columns": ["total_trx_q4_2024"], "rows": [[4563]], "row_count": 1, "truncated": false}
```

**Answer:**  The total TRx for Q4 2024 is **4,563**.

### ✓ Q4_best_territory
**Q:** Which territory has the highest TRx per HCP?  
**Grade:** all expected strings found  

**Trace:**
```
→ run_sql({"query": "SELECT territory_name, SUM(trx_cnt) AS total_trx, COUNT(DISTINCT hcp_id) AS hcp_cnt, ROUND(SUM(trx_cnt)::nume…)
← {"columns": ["territory_name", "total_trx", "hcp_cnt", "trx_per_hcp"], "rows": [["Territory 3", 8854, 30, 295.13], ["Territory 2", 8760, 30, 292.0], ["Territory 1", 8445, 30, 281.5]], "row_count": 3, …
```

**Answer:**  **Territory 3** has the highest TRx per HCP at **295.13**, just slightly ahead of Territory 2 (292.00) and Territory 1 (281.50). All three territories have the same number of HCPs (30), so the ranking is driven purely by total TRx volume.

### ✓ Q8_best_rep
**Q:** Which rep has the highest call-to-Rx conversion rate?  
**Grade:** all expected strings found  

**Trace:**
```
→ list_schema({"table": "v_activity_enriched"})
← Table: v_activity_enriched Columns:   - activity_id: integer   - rep_id: integer   - rep_name: text   - region: text   - hcp_id: bigint   - hcp_name: text   - specialty: text   - tier: text   - territ…
→ run_sql({"query": "SELECT hcp_id, COUNT(DISTINCT rep_id) AS rep_cnt FROM fact_rep_activity WHERE status='completed' GROUP BY 1 H…)
← {"columns": ["hcp_id", "rep_cnt"], "rows": [[1000000001, 3], [1000000002, 3], [1000000003, 3], [1000000004, 3], [1000000005, 3], [1000000006, 3], [1000000007, 3], [1000000008, 3], [1000000009, 3], [10…
→ run_sql({"query": "\nWITH rep_calls AS (\n    SELECT rep_id, rep_name, COUNT(*) AS completed_calls\n    FROM v_activity_enriched…)
← {"columns": ["rep_name", "completed_calls", "total_trx", "trx_per_call"], "rows": [["River Miller", 183, 54546, 298.07], ["Taylor Wilson", 202, 59675, 295.42], ["Sage Brown", 215, 63060, 293.3], ["Tay…
→ run_sql({"query": "\nWITH rep_calls AS (\n    SELECT rep_id, rep_name, COUNT(*) AS completed_calls\n    FROM v_activity_enriched…)
← {"columns": ["rep_name", "completed_calls", "total_trx", "trx_per_call"], "rows": [["River Miller", 183, 8854.0, 48.38], ["Reese Miller", 189, 8854.0, 46.85], ["Taylor Kim", 193, 8854.0, 45.88], ["Jam…
→ run_sql({"query": "\nSELECT \n    (SELECT SUM(trx_cnt) FROM v_rx_enriched) AS total_trx,\n    (SELECT COUNT(*) FROM v_activity_e…)
← {"columns": ["total_trx", "total_calls", "rx_hcps", "called_hcps"], "rows": [[26059, 1786, 90, 90]], "row_count": 1, "truncated": false}
→ run_sql({"query": "\nSELECT hcp_id, calendar_date, COUNT(*) AS calls_per_day\nFROM v_activity_enriched\nWHERE status='completed'…)
← {"columns": ["hcp_id", "calendar_date", "calls_per_day"], "rows": [[2000000026, "2025-06-02", 3], [2000000024, "2024-09-23", 2], [1000000020, "2024-09-23", 2], [1000000024, "2025-01-07", 2], [10000000…
→ run_sql({"query": "\nWITH rep_calls AS (\n    SELECT rep_id, rep_name, COUNT(*) AS completed_calls\n    FROM v_activity_enriched…)
← {"columns": ["rep_name", "completed_calls", "total_trx", "trx_per_call"], "rows": [["River White", 216, 188, 0.87], ["River Miller", 183, 121, 0.66], ["Jamie Thomas", 185, 95, 0.51], ["Taylor Kim", 19…
→ run_sql({"query": "\nWITH rep_calls AS (\n    SELECT rep_id, rep_name, COUNT(*) AS completed_calls\n    FROM v_activity_enriched…)
← {"columns": ["rep_name", "completed_calls", "total_trx", "trx_per_call"], "rows": [["River White", 216, 188, 0.87], ["River Miller", 183, 121, 0.66], ["Jamie Thomas", 185, 95, 0.51], ["Taylor Kim", 19…
```

**Answer:**                  **River White** has the highest call-to-Rx conversion rate at **0.87 TRx per completed call** (188 TRx on the same day as 216 completed calls).

Here are all 9 reps ranked by same-day conversion rate:

| Rank | Rep | Completed Calls | Same-Day TRx | TRx per Call |
|------|------|-----------------|--------------|--------------|
| 1 | **River White** | 216 | 188 | **0.87** |
| 2 | River Miller | 183 | 121 | 0.66 |
| 3 | Jamie Thomas | 185 | 95 | 0.51 |
| 4 | Taylor Kim | 193 | 93 …

### ✓ Q7_uncalled_tier_a
**Q:** Which tier-A HCPs have had zero completed rep calls in the last 60 days?  
**Grade:** 5/5 found (need 3): ['Dr Rowan Davis', 'Dr Drew Lee', 'Dr Rowan Martinez', 'Dr Drew Wilson', 'Dr Taylor Smith']  

**Trace:**
```
→ run_sql({"query": "WITH bounds AS (\n    SELECT MAX(calendar_date) AS hi \n    FROM date_dim \n    WHERE date_id IN (SELECT date…)
← {"columns": ["hcp_id", "full_name", "specialty", "territory_id"], "rows": [[1000000028, "Dr Casey Miller", "Nephrology", 1], [1000000026, "Dr Drew Thomas", "Rheumatology", 1], [1000000030, "Dr Drew Wi…
```

**Answer:**  26 tier-A HCPs have had zero completed rep calls in the last 60 days (from the latest Rx date in the dataset):

**Territory 1**
- Dr Casey Miller (Nephrology)
- Dr Drew Thomas (Rheumatology)
- Dr Drew Wilson (Internal Medicine)
- Dr Hayden Jackson (Internal Medicine)
- Dr River Martinez (Nephrology)
- Dr Rowan Davis (Internal Medicine)
- Dr Sage White (Rheumatology)
- Dr Taylor Davis (Nephrology)

**Territory 2**
- Dr Drew Lee (Nephrology)
- Dr Jordan Garcia (Rheumatology)
- Dr Morgan Rodriguez…
