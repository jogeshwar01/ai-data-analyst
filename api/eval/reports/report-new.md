# Gazyva Eval Report

**Score: 11/11** (100%)

| # | ID | Pass | Time | Detail |
|---|---|---|---|---|
| Q1_hcp_count | ✓ | 5.2s | found 90.0 (expected 90.0 ±1.0%) |
| Q2_q4_2024_trx | ✓ | 4.4s | found 4563.0 (expected 4563.0 ±1.0%) |
| Q3_top5_hcps | ✓ | 5.4s | 5/5 found (need 4): ['Dr Sage Jackson', 'Dr Blake Garcia', ' |
| Q4_best_territory | ✓ | 5.0s | all expected strings found |
| Q5_mom_growth | ✓ | 17.4s | all expected strings found |
| Q7_uncalled_tier_a | ✓ | 8.8s | 5/5 found (need 3): ['Dr Rowan Davis', 'Dr Drew Lee', 'Dr Ro |
| Q8_best_rep | ✓ | 9.7s | all expected strings found |
| Q9_medicare_shifts | ✓ | 7.1s | 3/3 found (need 2): ['Bay Clinic', 'Bay Hospital', 'Valley H |
| Q10_ambiguity | ✓ | 6.4s | The answer explicitly states the assumption by defining "bes |
| Q11_what_if | ✓ | 7.3s | The answer provides a numeric projection of 9,845 TRx with a |
| Q12_anomalies | ✓ | 21.7s | The answer identifies three specific anomalies with actual n |

## Answers

### ✓ Q1_hcp_count
**Q:** How many distinct HCPs prescribed GAZYVA?  
**Grade:** found 90.0 (expected 90.0 ±1.0%)  

**Trace:**
```
→ run_sql({"query": "SELECT COUNT(DISTINCT hcp_id) FROM fact_rx WHERE brand_code = 'GAZYVA';"})
← {"columns": ["count"], "rows": [[90]], "row_count": 1, "truncated": false}
```

**Answer:** OK. 90 distinct HCPs have prescribed GAZYVA.

### ✓ Q2_q4_2024_trx
**Q:** What is the total TRx for Q4 2024?  
**Grade:** found 4563.0 (expected 4563.0 ±1.0%)  

**Trace:**
```
→ run_sql({"query": "SELECT SUM(trx_cnt) AS total_trx\nFROM v_rx_enriched\nWHERE year = 2024 AND quarter = 'Q4';"})
← {"columns": ["total_trx"], "rows": [[4563]], "row_count": 1, "truncated": false}
```

**Answer:** The total TRx for GAZYVA in Q4 2024 was **4,563**.

### ✓ Q3_top5_hcps
**Q:** Who are the top 5 HCPs by total TRx in the last 90 days?  
**Grade:** 5/5 found (need 4): ['Dr Sage Jackson', 'Dr Blake Garcia', 'Dr Cameron Clark', 'Dr Phoenix Lee', 'Dr Hayden Jackson']  

**Trace:**
```
→ run_sql({"query": "WITH bounds AS (\n    SELECT MAX(calendar_date) AS hi \n    FROM date_dim \n    WHERE date_id IN (SELECT date…)
← {"columns": ["hcp_name", "specialty", "tier", "total_trx"], "rows": [["Dr Sage Jackson", "Internal Medicine", "B", 86], ["Dr Blake Garcia", "Rheumatology", "C", 84], ["Dr Cameron Clark", "Rheumatology…
```

**Answer:** The top 5 HCPs by total TRx over the last 90 days are led by Dr. Sage Jackson (Internal Medicine) and Dr. Blake Garcia (Rheumatology). Interestingly, the top list includes a mix of Tier B and C providers, with only one Tier A provider (Dr. Hayden Jackson) appearing in the top five for this period.

| HCP Name | Specialty | Tier | Total TRx (Last 90 Days) |
| :--- | :--- | :--- | :--- |
| Dr Sage Jackson | Internal Medicine | B | 86 |
| Dr Blake Garcia | Rheumatology | C | 84 |
| Dr Cameron Clark…

### ✓ Q4_best_territory
**Q:** Which territory has the highest TRx per HCP?  
**Grade:** all expected strings found  

**Trace:**
```
→ run_sql({"query": "SELECT \n    territory_name, \n    SUM(trx_cnt) AS total_trx, \n    COUNT(DISTINCT hcp_id) AS hcp_count,\n   …)
← {"columns": ["territory_name", "total_trx", "hcp_count", "trx_per_hcp"], "rows": [["Territory 3", 8854, 30, 295.1333333333333], ["Territory 2", 8760, 30, 292.0], ["Territory 1", 8445, 30, 281.5]], "ro…
```

**Answer:** **Territory 3** has the highest TRx per HCP at **295.13**, followed closely by Territory 2. All three territories have an equal distribution of 30 HCPs each, making the comparison straightforward.

| Territory | Total TRx | HCP Count | TRx per HCP |
| :--- | :--- | :--- | :--- |
| **Territory 3** | 8,854 | 30 | **295.13** |
| Territory 2 | 8,760 | 30 | 292.00 |
| Territory 1 | 8,445 | 30 | 281.50 |

### ✓ Q5_mom_growth
**Q:** Show month-over-month TRx growth per territory.  
**Grade:** all expected strings found  

**Trace:**
```
→ run_sql({"query": "WITH monthly_data AS (\n    SELECT \n        territory_name, \n        DATE_TRUNC('month', calendar_date) AS …)
← {"columns": ["territory_name", "month", "total_trx", "mom_growth_pct"], "rows": [["Territory 1", "2024-08", 527, null], ["Territory 1", "2024-09", 441, -16.32], ["Territory 1", "2024-10", 496, 12.47],…
→ make_chart({"data_json": "[{\"territory_name\": \"Territory 1\", \"month\": \"2024-09\", \"mom_growth_pct\": -16.32}, {\"territory_…)
← {"__type": "chart", "spec": {"title": "Month-over-Month TRx Growth % by Territory", "width": 600, "height": 300, "mark": {"type": "line", "point": true}, "encoding": {"x": {"field": "month", "type": "…
```

**Answer:** The month-over-month TRx growth across the three territories shows significant volatility, with frequent swings between positive and negative growth. 

**Key Observations:**
*   **Territory 1** experienced the most dramatic fluctuations, notably a **23.46% drop** in February 2025 followed by a recovery, and another sharp **18.45% decline** in November 2025.
*   **Territory 2** maintained relatively more stable growth compared to Territory 1, though it still saw a notable **13.56% dip** in April …

### ✓ Q7_uncalled_tier_a
**Q:** Which tier-A HCPs have had zero completed rep calls in the last 60 days?  
**Grade:** 5/5 found (need 3): ['Dr Rowan Davis', 'Dr Drew Lee', 'Dr Rowan Martinez', 'Dr Drew Wilson', 'Dr Taylor Smith']  

**Trace:**
```
→ run_sql({"query": "WITH bounds AS (\n    SELECT MAX(calendar_date) AS hi \n    FROM date_dim \n    WHERE date_id IN (SELECT date…)
← {"columns": ["hcp_id", "hcp_name", "specialty", "territory_id"], "rows": [[3000000010, "Dr Blake Gonzalez", "Rheumatology", 3], [1000000028, "Dr Casey Miller", "Nephrology", 1], [3000000020, "Dr Drew …
```

**Answer:** There are 26 Tier-A HCPs who have had zero completed rep calls in the last 60 days. This represents a significant portion of the high-priority target list that has not been engaged recently.

The HCPs with no completed activity are:
*   **Dr Blake Gonzalez** (Rheumatology, Territory 3)
*   **Dr Casey Miller** (Nephrology, Territory 1)
*   **Dr Drew Brown** (Internal Medicine, Territory 3)
*   **Dr Drew Lee** (Nephrology, Territory 2)
*   **Dr Drew Thomas** (Rheumatology, Territory 1)
*   **Dr Dr…

### ✓ Q8_best_rep
**Q:** Which rep has the highest call-to-Rx conversion rate?  
**Grade:** all expected strings found  

**Trace:**
```
→ run_sql({"query": "SELECT \n    rep_name, \n    SUM(trx_cnt) AS total_trx, \n    COUNT(DISTINCT activity_id) AS total_calls,\n  …)
← {"columns": ["rep_name", "total_trx", "total_calls", "conversion_rate"], "rows": [["Morgan Chen", 43, 2, 21.5], ["River White", 139, 7, 19.857142857142858], ["Casey Gonzalez", 39, 2, 19.5], ["Sage Bro…
```

**Answer:** **Morgan Chen** has the highest call-to-Rx conversion rate at **21.5 TRx per call**, followed closely by **River White** at **19.86**. 

This metric is calculated by matching completed calls to the TRx volume generated by the same HCP on the same day. Note that while Morgan Chen leads in efficiency, River White has managed a significantly higher total volume (139 TRx) across more interactions.

| Rep Name | Total TRx (on call days) | Total Calls | Conversion Rate |
| :--- | :--- | :--- | :--- |
…

### ✓ Q9_medicare_shifts
**Q:** Which accounts have shifted more than 5 percentage points in Medicare payor mix quarter-over-quarter?  
**Grade:** 3/3 found (need 2): ['Bay Clinic', 'Bay Hospital', 'Valley Hospital']  

**Trace:**
```
→ run_sql({"query": "WITH quarterly_payor AS (\n    SELECT \n        a.name AS account_name,\n        d.year,\n        d.quarter,\…)
← {"columns": ["account_name", "year", "quarter", "prev_avg_medicare_pct", "avg_medicare_pct", "medicare_shift"], "rows": [["Mountain Clinic", 2025, "Q4", 67.3, 0.6, 66.7], ["Valley Hospital", 2025, "Q3…
```

**Answer:** Several accounts experienced significant shifts in their Medicare payor mix (defined as >5 percentage point change quarter-over-quarter). The most extreme volatility was observed at **Mountain Clinic** and **Valley Hospital**, both of which saw shifts exceeding 50 percentage points in 2025.

### Key Medicare Payor Mix Shifts (>5pp)
*   **Mountain Clinic:** Experienced a massive 66.7pp drop in Q4 2025 and a 50pp increase in Q3 2025.
*   **Valley Hospital:** Saw a 60.7pp increase in Q3 2025, follo…

### ✓ Q10_ambiguity
**Q:** Which doctors are best?  
**Grade:** The answer explicitly states the assumption by defining "best" as the doctors with the highest total TRx volume.  

**Trace:**
```
→ run_sql({"query": "WITH bounds AS (\n    SELECT MAX(calendar_date) AS hi \n    FROM date_dim \n    WHERE date_id IN (SELECT date…)
← {"columns": ["hcp_name", "specialty", "tier", "territory_name", "total_trx", "total_nrx"], "rows": [["Dr Sage Jackson", "Internal Medicine", "B", "Territory 2", 86, 23], ["Dr Phoenix Lee", "Rheumatolo…
```

**Answer:** The "best" doctors, defined as Tier A or B HCPs with the highest total TRx volume over the last 90 days, are led by **Dr. Sage Jackson** (86 TRx) and **Dr. Phoenix Lee** (79 TRx). The top 10 list is dominated by Internal Medicine and Rheumatology specialists, with Territory 2 and 3 appearing most frequently in the top ranks.

| HCP Name | Specialty | Tier | Territory | Total TRx | Total NRx |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Dr Sage Jackson | Internal Medicine | B | Territory 2 | 86…

### ✓ Q11_what_if
**Q:** If rep 3 doubled their completed calls to tier-B HCPs in their territory, what would the projected TRx lift be?  
**Grade:** The answer provides a numeric projection of 9,845 TRx with an uncertainty qualifier of a 95% confidence interval.  

**Trace:**
```
→ run_python({"code": "import numpy as np\nimport pandas as pd\n\n# 1. Calculate historical TRx per call ratio across all completed c…)
← Current completed calls by Rep 3 to Tier-B HCPs: 34 Additional calls (doubling): 34 Average TRx per call (Global Baseline): 289.54 Projected TRx Lift: 9844.51 (95% CI: ±353.92)
```

**Answer:** Based on historical performance across the fleet, doubling Rep 3's completed calls to Tier-B HCPs (an additional 34 calls) is projected to generate a significant TRx lift.

*   **Current Activity:** Rep 3 has completed 34 calls to Tier-B HCPs.
*   **Efficiency Baseline:** The average historical yield across all HCPs is approximately **289.54 TRx per completed call**.
*   **Projected Lift:** Doubling this activity is estimated to yield an additional **9,845 TRx** (95% CI: ±354).

This projection …

### ✓ Q12_anomalies
**Q:** Show me anomalies or unusual patterns in the dataset.  
**Grade:** The answer identifies three specific anomalies with actual names and numbers, including high-volume prescribers and significant payor volatility.  

**Trace:**
```
→ run_python({"code": "import pandas as pd\nimport numpy as np\n\n# 1. HCP TRx Outliers (Statistical)\nrx_data = query(\"\"\"\n    SE…)
← --- 1. HCP TRx Outliers (>2 Std Dev) ---          hcp_name  total_trx  Dr Quinn Johnson        360   Dr Blake Garcia        374     Dr Alex Patel        357 Dr Sydney Johnson        354    Dr Phoenix …
```

**Answer:** I have analyzed the dataset for statistical outliers and unusual patterns across prescribing behavior, field activity, and payor dynamics. Here are the key findings:

### 1. High-Volume Prescriber Outliers
Five HCPs are performing significantly above the mean (exceeding 2 standard deviations). These individuals are the primary drivers of GAZYVA volume:
*   **Dr. Blake Garcia** (374 TRx)
*   **Dr. Phoenix Lee** (363 TRx)
*   **Dr. Quinn Johnson** (360 TRx)
*   **Dr. Alex Patel** (357 TRx)
*   **D…
