# Dataset Overview

## What is this data?

This is a simulated pharma commercial dataset for a single drug called **GAZYVA**. It covers ~16 months of activity (August 2024 to December 2025) across the US sales operation.

Think of it as the data a pharma company's commercial analytics team would use to answer questions like: *Which doctors are prescribing the most? Are our sales reps calling the right people? Where are we losing market share?*

---

## The Cast of Characters

**90 HCPs (Healthcare Practitioners)** — the doctors who prescribe GAZYVA. Each has:
- A specialty (Rheumatology, Nephrology, or Internal Medicine)
- A tier (A = highest potential, B = medium, C = lower)
- A territory they belong to

**24 Accounts** — the hospitals and clinics where doctors work. Split between Hospitals and Clinics.

**9 Sales Reps** — the people who visit doctors to promote GAZYVA. Each rep covers one of 3 territories.

**3 Territories** — geographic groupings (Territory 1, 2, 3). Each rep belongs to a territory; each HCP and account does too.

---

## The Data Tables

### What doctors prescribed (`fact_rx`)
~1,530 rows. One row per doctor per month showing how many GAZYVA prescriptions they wrote.

- **TRx** (Total Rx) — all prescriptions written that month
- **NRx** (New Rx) — first-time prescriptions only (new patients starting the drug)

*Example: Dr Blake Garcia wrote 11 total prescriptions in August 2024, 5 of which were for new patients.*

### What reps did (`fact_rep_activity`)
~2,960 rows. Every sales call or lunch meeting a rep had with a doctor.

- Type: `call` (short visit) or `lunch_meeting` (longer, over food)
- Status: `completed` or `cancelled`
- Includes duration and time of day

*Example: Rep Morgan Chen had a 20-minute call with a doctor at Mountain Hospital on Aug 1.*

### How patients pay (`fact_payor_mix`)
~480 rows. Monthly snapshot per account showing what percentage of patients use each type of insurance.

- Insurance types: Commercial, Medicare, Medicaid, Other
- Percentages add up to 100 for each account each month

*Example: Mountain Hospital in Oct 2024 — 52.7% Medicare, 8.2% Commercial.*

### Market share (`fact_ln_metrics`)
~570 rows. Quarterly estimate of GAZYVA's share of the market, for both individual doctors and accounts.

- `ln_patient_cnt` — estimated number of patients on GAZYVA
- `est_market_share` — GAZYVA's share of eligible patients (0–100%)

*Example: Dr Blake Garcia in Q4 2024 had 56 estimated patients with a 6.7% market share.*

---

## How It All Connects

```
territory_dim
     │
     ├── rep_dim (reps cover a territory)
     ├── account_dim (accounts are in a territory)
     └── hcp_dim (doctors are in a territory)
              │
              ├── fact_rx (doctor → prescriptions per month)
              ├── fact_rep_activity (rep visits to a doctor at an account)
              ├── fact_ln_metrics (doctor's market share per quarter)
              └── account_dim → fact_payor_mix (account's insurance mix)
```

---

## Key Numbers at a Glance

| | |
|---|---|
| Drug | GAZYVA (single brand) |
| Date range | Aug 2024 – Dec 2025 |
| Doctors | 90 |
| Accounts | 24 |
| Sales reps | 9 |
| Territories | 3 |
| Total rows across all tables | ~6,100 |

---

## Typical Questions This Data Can Answer

- Which doctors are prescribing the most? Least? Growing fastest?
- Which reps have the best call-to-prescription conversion?
- Which high-value doctors haven't been visited recently?
- Where is Medicare share growing — and does that affect our volume?
- Which accounts are gaining or losing market share?
