# Gazyva Eval Report

**Score: 9/12** (75%)

| #                  | ID  | Pass   | Time                                                         | Detail |
| ------------------ | --- | ------ | ------------------------------------------------------------ | ------ |
| Q1_hcp_count       | ✓   | 30.4s  | found 90.0 (expected 90.0 ±1.0%)                             |
| Q2_q4_2024_trx     | ✓   | 45.5s  | found 4563.0 (expected 4563.0 ±1.0%)                         |
| Q3_top5_hcps       | ✓   | 23.8s  | 5/5 found (need 4): ['Dr Sage Jackson', 'Dr Blake Garcia', ' |
| Q4_best_territory  | ✓   | 53.0s  | all expected strings found                                   |
| Q5_mom_growth      | ✓   | 176.9s | all expected strings found                                   |
| Q6_correlation     | ✓   | 112.9s | The reported Pearson r (0.130) and p-value (0.222) fall with |
| Q7_uncalled_tier_a | ✗   | 116.0s | 1/5 found (need 3): ['Dr Drew Lee']                          |
| Q8_best_rep        | ✓   | 75.1s  | all expected strings found                                   |
| Q9_medicare_shifts | ✓   | 188.4s | 2/3 found (need 2): ['Bay Clinic', 'Valley Hospital']        |
| Q10_ambiguity      | ✓   | 41.8s  | The agent explicitly defined "best" as "by total TRx" in the |
| Q11_what_if        | ✗   | 281.9s | The agent stopped without providing a numeric projection or  |
| Q12_anomalies      | ✗   | 286.8s | The answer contains no specific data-backed findings or anom |

## Answers

### ✓ Q1_hcp_count

**Q:** How many distinct HCPs prescribed GAZYVA?  
**A:** **90 distinct HCPs** prescribed GAZYVA in the dataset.

```sql
SELECT COUNT(DISTINCT hcp_id) AS distinct_hcp_count
FROM fact_rx
WHERE brand_code = 'GAZYVA';
```

**Grade:** found 90.0 (expected 90.0 ±1.0%)

### ✓ Q2_q4_2024_trx

**Q:** What is the total TRx for Q4 2024?  
**A:** Total TRx for Q4 2024 is **4,563**.
**Grade:** found 4563.0 (expected 4563.0 ±1.0%)

### ✓ Q3_top5_hcps

**Q:** Who are the top 5 HCPs by total TRx in the last 90 days?  
**A:** The top 5 HCPs by total TRx in the last 90 days are:

| Rank | HCP Name          | Specialty         | Tier | Total TRx |
| ---- | ----------------- | ----------------- | ---- | --------- |
| 1    | Dr Sage Jackson   | Internal Medicine | B    | 86        |
| 2    | Dr Blake Garcia   | Rheumatology      | C    | 84        |
| 3    | Dr Cameron Clark  | Rheumatology      | C    | 83        |
| 4    | Dr Phoenix Lee    | Rheumatology      | B    | 79        |
| 5    | Dr Hayden Jackson | Internal Medicine | A    | 77        |

Notably, the list is split between Internal Medicine and Rheumatology, and includes a mix
**Grade:** 5/5 found (need 4): ['Dr Sage Jackson', 'Dr Blake Garcia', 'Dr Cameron Clark', 'Dr Phoenix Lee', 'Dr Hayden Jackson']

### ✓ Q4_best_territory

**Q:** Which territory has the highest TRx per HCP?  
**A:** **Territory 3** has the highest TRx per HCP at **295.13** (8,854 total TRx across 30 HCPs).
**Grade:** all expected strings found

### ✓ Q5_mom_growth

**Q:** Show month-over-month TRx growth per territory.  
**A:** **Month-over-month TRx growth by territory** (Aug 2024 – Dec 2025):

| Territory       | Notable swings                                                                                                       | Latest month (Dec 2025)                      |
| --------------- | -------------------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| **Territory 1** | Volatile; sharp drops in Feb 2025 (‑23%) and Nov 2025 (‑18%), strong rebounds in Dec 2024 (+22%) and Sep 2025 (+18%) | **+11%** (513 TRx)                           |
| **Territory 2** | Most stable; steady climb through late 2025 with only mild contractions                                              | **+10%** (593 TRx) - highest absolute volume |

| **Territory 3**
**Grade:** all expected strings found

### ✓ Q6_correlation

**Q:** Does call frequency correlate with TRx? Give the Pearson r value and p-value.  
**A:** There is **no statistically significant correlation** between completed call frequency per HCP and total TRx per HCP.

- **Pearson r = 0.130**
- **p-value = 0.222**

The very weak positive linear relationship is not significant (p > 0.05), meaning call count alone does not explain TRx variation across HCPs in this dataset.
**Grade:** The reported Pearson r (0.130) and p-value (0.222) fall within the acceptable ranges and the answer correctly concludes the correlation is weak and not statistically significant.

### ✗ Q7_uncalled_tier_a

**Q:** Which tier-A HCPs have had zero completed rep calls in the last 60 days?  
**A:** **26 tier-A HCPs** have had zero completed rep calls in the last 60 days (measured from the latest Rx date in the dataset).

**Breakdown by territory:**

- **Territory 1:** 8 HCPs (e.g., Dr Casey Miller, Dr Drew Thomas, Dr Hayden Jackson)
- **Territory 2:** 7 HCPs (e.g., Dr Drew Lee, Dr Jordan Garcia, Dr Morgan Rodriguez)
- **Territory 3:** 11 HCPs (e.g., Dr Blake Gonzalez, Dr Drew Brown, Dr Jordan Clark)

These span all three specialties (Internal Medicine, Nephrology, Rheumatology) and represe
**Grade:** 1/5 found (need 3): ['Dr Drew Lee']

### ✓ Q8_best_rep

**Q:** Which rep has the highest call-to-Rx conversion rate?  
**A:** **River Miller** (Territory 3) has the highest call-to-Rx conversion rate at **18.81 TRx per completed call**.

### Assumption

Because every HCP is called on by multiple reps, Rx cannot be cleanly attributed to a single rep. I defined conversion rate as: **total TRx written within 30 days after a rep’s completed call**, divided by that rep’s **total completed calls**. This is a standard “attributed Rx” approach when call coverage overlaps.

### Full Ranking

| Rep | Region | Completed Calls | At
**Grade:** all expected strings found

### ✓ Q9_medicare_shifts

**Q:** Which accounts have shifted more than 5 percentage points in Medicare payor mix quarter-over-quarter?  
**A:** **All 24 accounts in the dataset experienced at least one quarter-over-quarter Medicare payor mix shift greater than 5 percentage points.** The volatility is widespread, with several accounts showing extreme swings:

| Account                    | # of Shifts >5pp | Largest Single Shift |
| -------------------------- | ---------------- | -------------------- |
| Pacific Hospital (ID 1020) | 3                | **70.1 pp**          |
| Pacific Clinic (ID 1014)   | 4                | **67.1 pp**          |
| Mountain Clinic (ID 1018)  | 4                | **66.7 pp**          |
| Valley Hospital (ID 1022)  | 4                | **60.7 pp**          |

| Bay Clinic (ID 1021)
**Grade:** 2/3 found (need 2): ['Bay Clinic', 'Valley Hospital']

### ✓ Q10_ambiguity

**Q:** Which doctors are best?  
**A:** **Top 10 "best" HCPs by total TRx in the last 90 days (Tier A & B only):**

| Rank | HCP Name           | Specialty         | Tier | Territory   | TRx | NRx |
| ---- | ------------------ | ----------------- | ---- | ----------- | --- | --- |
| 1    | Dr Sage Jackson    | Internal Medicine | B    | Territory 2 | 86  | 23  |
| 2    | Dr Phoenix Lee     | Rheumatology      | B    | Territory 3 | 79  | 29  |
| 3    | Dr Hayden Jackson  | Internal Medicine | A    | Territory 1 | 77  | 28  |
| 4    | Dr Taylor Gonzalez | Rheumatology      | A    | Territory 2 | 75  | 31  |
| 5    | Dr Sydney          |

**Grade:** The agent explicitly defined "best" as "by total TRx" in the header before presenting the data.

### ✗ Q11_what_if

**Q:** If rep 3 doubled their completed calls to tier-B HCPs in their territory, what would the projected TRx lift be?  
**A:** Agent stopped due to max iterations.
**Grade:** The agent stopped without providing a numeric projection or uncertainty acknowledgment.

### ✗ Q12_anomalies

**Q:** Show me anomalies or unusual patterns in the dataset.  
**A:** Agent stopped due to max iterations.
**Grade:** The answer contains no specific data-backed findings or anomalies, only stating that the agent stopped due to max iterations.
