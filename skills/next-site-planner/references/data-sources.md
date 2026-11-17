# Data sources, periods and the baseline

Start every answer with the data used. `python scripts/nsp.py about` returns the current speed-test quarter, its dates and the time of the check.

## Sources

| What | Source | Period or vintage | Used for | Licence |
|---|---|---|---|---|
| Mobile speeds | Speedtest by Ookla open data (crowdsourced tests from real devices) | One quarter, e.g. 2026 Q3 = 1 Jul–30 Sep 2026 (13 weeks); trends use 2023 Q1 onwards | Typical speed, chance below 10 / 25 Mbps | CC BY-NC-SA 4.0 (non-commercial) |
| Population | Kontur population 2023 on H3 resolution 8 | 2023 | People per hexagon | CC BY 4.0 |
| Population cross-check | WorldPop 2020, constrained 100 m | 2020 | Second estimate; site plans use the smaller of the two | CC BY 4.0 |
| Built-up land | ESA WorldCover 2021 v200, 10 m | 2021 | Ground check: is there built-up land at a site | CC BY 4.0 |
| Terrain | Copernicus DEM GLO-30 | — | Ground check: elevation and slope at a site point | Copernicus DEM licence |
| Places | Overture Maps places | 2026 release | Only the KPI baseline's "places" KPI | CDLA-Permissive 2.0 |

## How "chance below 25 Mbps" is made

- **Tested hexagons:** the quarter's speed tests (13 weeks) are combined after separating test noise from real differences; the result is a typical speed and how uncertain it is. The chance is the share of that uncertainty below the bar.
- **Untested hexagons** (`tested: false`): speed is estimated from nearby tested hexagons (kriging), with a wider uncertainty, so the chance is less certain.
- Say it as: "From speed tests between 1 July and 30 September 2026, there is an 84% chance that typical speed here is below 25 Mbps."

## The baseline: KPI ranking

- **What it is:** each populated hexagon gets a score that adds three KPIs with equal weight, each standardised (z-score): slow typical speed (minus log speed), log population and log number of places. Hexagons are taken from the highest score down until the budget is spent.
- **Why it is the baseline:** it is how many site lists are built today, ranking by a composite KPI score. Weighted scores agreed in planning meetings cannot be reproduced, so equal weights are the fair, repeatable stand-in. It gets the same budget, population, exclusions and ground checks as the plan.
- **Its numbers:** baseline people lifted = `plan_people_lifted / (1 + plan_gain_vs_kpi)`.

| Country | Plan: people lifted (central; range) | KPI ranking | Gain | Budget (tower-equivalents) |
|---|---|---|---|---|
| Indonesia | 122,506 (0–253,527) | 42,933 | +185% | 1,000 |
| Malaysia | 10,540 (0–25,120) | 2,944 | +258% | 1,000 |
| Philippines | 279,483 (0–556,164) | 119,382 | +134% | 1,000 |
| Germany | 97,127 (5,429–189,034) | 64,875 | +50% | 1,000 |
| France | 37,568 (1,201–96,260) | 23,525 | +60% | 1,000 |
| United States | 4,447 (0–58,194) | 2,203 | +102% | 1,000 |
| UAE | 311 (0–643) | 82 | +281% | 29.3 (all 29 likely-slow candidates) |

The ranges come from the measured share of people a new site or added capacity lifts; where its interval includes zero, the low end is zero. Quote the central figure and say it is an estimate with a wide range. Source: ADR-008 (checked plans, 2026 Q3).

## Why the plan picks a hexagon or not

The plan is a budgeted optimiser: it picks the set of sites that lifts the most people above 25 Mbps for the budget. A hexagon is left out for one of these reasons, in this order:

1. **Nobody to lift:** its chance below 25 Mbps is about 0%, so a site there lifts no one.
2. **Better value elsewhere:** people × chance below 25 Mbps × lift share, divided by cost, is lower than for the sites chosen before the budget ran out.
3. **Failed the ground check:** less than 1,000 m² of built-up land in the hexagon (about seven village houses). Steep (slope above 20°) or high (above 2,500 m) sites are flagged for the planner, not rejected.
4. **Not populated or not estimated:** no people, or no speed estimate.

Use the first reason that the API's numbers support, and say which numbers show it.

## What would sharpen a shortlist

The plan uses public data only. To turn it into an investment case, ask for: CAPEX and OPEX per site type, existing sites and co-location options, market share and subscribers in the area, revenue per user, the operator's commercial strategy (which areas and segments matter), and permits or land constraints.
