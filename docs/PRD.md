PRODUCT REQUIREMENT DOCUMENT (PRD)
Project: Next Site Planner — Where Would One More Mobile Site Help the Most People?
Version: 0.1 (design: framing, validation, gates — before any analysis)
Author: Sabrina Pribadi
Date: October 13, 2026
Status: Proposed — P0 next


1. EXECUTIVE SUMMARY

Problem: Mobile operators decide every year where to add sites. Plans are often built by
ranking candidate locations on many indicators at once (traffic, congestion, devices,
revenue), with weights agreed in meetings. That answers "which sites score highest?",
not "where would one more site improve the experience of the most people, per unit of
budget?" — and nobody checks afterwards whether new sites actually lifted speeds nearby.

Solution: A reproducible, public-data planner for seven countries (Indonesia, Malaysia,
Philippines, Germany, France, United States, United Arab Emirates). It maps measured mobile
experience (Ookla open speed tiles, 15 quarters) against where people live and gather
(Kontur population, Overture places) on one H3 hexagon grid; benchmarks countries fairly at
equal population density; predicts speed where tests are sparse with spatially validated
models; measures what a new site does to nearby speeds where cell history exists
(OpenCelliD, Germany and the US); and chooses a budget of new sites with a covering
optimiser instead of a ranking. Served as a web map, an API and MCP tools, refreshed
quarterly on Databricks.

Value Proposition: Replace "rank sites by KPIs" with "measure the gap, measure what sites
do, then optimise the set" — every number reproducible from public data.

Success Metrics (pre-registered — see ADR-002):
- P0: ≥ 99% of each country's population and ≥ 99% of its speed tests land on the H3 grid
- P1: population share below 10 and 25 Mbps per country, raw and density-adjusted, with 95% intervals
- P2: the spatial model beats ordinary kriging by ≥ 10% (RMSE of log speed) under spatial block cross-validation
- P3: new-site effect with a 95% interval and a passing pre-trend (placebo) test
- P4: the optimiser lifts ≥ 10% more people above 25 Mbps than a KPI-style ranking at the same budget
- P5: API contracts and the LLM evaluation set pass in CI; cost and latency within budget (R13)
- P6: the Databricks job reproduces the local P1 numbers exactly
- P7: two live pages (results and technical walkthrough), browser-tested


2. PROJECT CONTEXT AND BACKGROUND

Portfolio project GEO-1 (roles: GIS + MLOps). It rebuilds, from public data only, a kind of
planning that is usually done inside an operator with private network counters. Skills shown:
1. Spatial data engineering: ~49M speed-tile rows, millions of population hexagons and places, joined on H3
2. Spatial statistics: hotspot tests (Getis–Ord Gi* with false-discovery control), kriging
3. Spatial machine learning: gradient boosting with spatial block cross-validation and an area-of-applicability check
4. Causal estimation: event study of new sites on nearby speeds (staggered difference-in-differences)
5. Operations research: maximal covering location under a budget
6. MLOps: Spark on Databricks, quarterly refresh job, drift checks, model registry, CI
7. GenAI: grounded site rationales and MCP tools, with cost and latency budgets


3. SCOPE

In scope: seven countries; mobile and fixed speed tiles 2023 Q1–2026 Q3; H3 resolution 8;
residential population (Kontur 2023) and daytime places (Overture 2026-09); cell locations
(OpenCelliD snapshot 2026-10-13); boundaries (OCHA kecamatan for Indonesia, geoBoundaries elsewhere).

Out of scope: radio propagation modelling; spectrum, backhaul and site-rental costs (a flat
cost per site is assumed and varied); any operator's private data; naming operators.

Known data limits (measured, plan §9):
- Ookla tiles exist only where people ran tests; only ~20% of Indonesian mobile tiles appear in all 15 quarters
- OpenCelliD dates: records "created" in 2025–26 are mostly one-off sightings; only cells first seen
  up to 2024 and seen for months afterwards count as new sites. Indonesia has ~1.3k such cells, Germany ~40k, the US (MCC 310) ~61k
- Ookla licence is CC BY-NC-SA 4.0: derived maps are published under the same licence


4. USER PERSONAS AND STORIES

| Persona | Need | Today |
|---|---|---|
| Network planner | A budgeted list of locations that lifts the most people above a speed bar | Sites ranked by composite KPI scores |
| Regulator / policy analyst | Where coverage is worst for the most people, compared fairly with peer countries | Raw national medians that mix cities and islands |
| Capex reviewer | Evidence that new sites improve experience nearby | Before/after checks rarely done |
| GIS analyst | The same answer at kecamatan, district or hexagon level | Manual joins in desktop GIS |
| AI assistant | Typed tools: gap at a place, top sites for a budget, why this site | None |

User stories:
- As a planner, I give a country, a budget (K sites) and a speed bar, and get K locations with the people each would lift.
- As a policy analyst, I compare Indonesia with six markets at equal population density.
- As a reviewer, I see how much a new site lifted nearby speeds, with an interval.
- As an AI agent (via MCP), I can call gap_at(place), top_sites(country, k), explain_site(h3) and compare_countries().


5. FUNCTIONAL REQUIREMENTS

Module A: Data foundation on H3 resolution 8 — ADR-001 (P0)
Module B: Experience-gap map and fair benchmark — P1
Module C: Spatial speed model — P2 (ADR pending)
Module D: New-site effect — P3 (ADR pending)
Module E: Budgeted site optimiser — P4 (ADR pending)
Module F: API, MCP tools, grounded rationales — P5 (ADR pending)
Module G: Databricks quarterly job, registry, drift — P6 (ADR pending; R15 justification in ADR-001)


7. DATA STRATEGY

| Source | Licence | Use |
|---|---|---|
| Ookla open performance tiles, mobile + fixed, 2023 Q1–2026 Q3 | CC BY-NC-SA 4.0 | Measured download, upload, latency, tests and devices per ~610 m tile |
| Kontur population 2023-11-01, H3 resolution 8 | CC BY 4.0 | Residential population per hexagon |
| Overture Maps places, release 2026-09-23.1 | CDLA-Permissive 2.0 | Daytime demand proxy |
| OpenCelliD full database, 2026-10-13 | CC BY-SA 4.0 | Cell locations, radio type, first and last seen |
| OCHA COD-AB Indonesia; geoBoundaries gbOpen | CC BY-IGO; CC BY 4.0 / ODbL | Kecamatan and district reporting |
| Natural Earth admin-0 | Public domain | Assign tiles and hexagons to countries |
| WorldPop Indonesia 2020 | CC BY 4.0 | Cross-check of Kontur in Indonesia |

Raw data lives in `GEO_DATA_DIR` (OneDrive `github_project/data/geo`), never in the repository.
`scripts/acquire_public_data.py` rebuilds it; sources that change (OpenCelliD, Overture) are kept as dated snapshots.


9. IMPLEMENTATION PLAN

| Phase | Goal | Gate / exit criterion (ADR-002) |
|---|---|---|
| P0 | Seven-country data foundation on H3 r8 | ≥ 99% of population and of speed tests assigned to the grid; contract tests pass |
| P1 | Experience-gap map; fair cross-country benchmark; hotspots | Shares below 10 / 25 Mbps with 95% intervals, raw and density-adjusted; Gi* hotspots at FDR 5% |
| P2 | Spatial speed model where tests are sparse | GBM ≤ 0.9 × kriging RMSE (log speed) under spatial block CV; transfer to an unseen country reported |
| P3 | Effect of new sites (Germany, US) | Pre-trend placebo interval includes 0; effect with 95% interval; transfer to Indonesia stated as an assumption |
| P4 | Budgeted site optimiser | ≥ 10% more people lifted above 25 Mbps than KPI ranking at equal K |
| P5 | API + MCP + grounded rationales | Contract tests and LLM evaluation pass in CI; R13 budgets met |
| P6 | Databricks quarterly job + registry + drift | Databricks reproduces local P1 numbers exactly |
| P7 | Results page + technical walkthrough + web map | Both pages live and browser-tested (R10, R12, R14) |


11. RISKS AND MITIGATIONS

| Risk | Mitigation |
|---|---|
| Speed tests are not a random sample (people test when it is slow or new) | Report tests and devices per tile; weight by population, not tests; state the bias on the page |
| Sparse tiles in rural areas | P2 predicts with intervals; area-of-applicability flags where predictions are unreliable |
| OpenCelliD first-seen dates are noisy | Use only cells first seen ≤ 2024 and observed ≥ 180 days; placebo test |
| Effect estimated abroad may not hold in Indonesia | State it as an assumption; sensitivity range in P4 |
| Free Edition cannot read Ookla's S3 | Test first; else upload country extracts (as in CHN-1) |
| 8 GB development machine | DuckDB locally with out-of-core execution; Spark on Databricks for the full refresh |


14. APPENDIX — References

- Ookla Open Data, Speedtest by Ookla Global Fixed and Mobile Network Performance Maps (AWS Open Data Registry)
- Church, R. & ReVelle, C. (1974). The maximal covering location problem. Papers of the Regional Science Association 32
- Ord, J. K. & Getis, A. (1995). Local spatial autocorrelation statistics. Geographical Analysis 27(4)
- Meyer, H. & Pebesma, E. (2021). Predicting into unknown space? Estimating the area of applicability of spatial prediction models. Methods in Ecology and Evolution (arXiv 2005.07939)
- Callaway, B. & Sant'Anna, P. (2021). Difference-in-differences with multiple time periods. Journal of Econometrics 225(2)
- Stratifying the digital divide: socio-economic influences on Internet performance (2026). arXiv 2605.30809
- A user-demand-driven approach for 5G base station location selection (2025). Journal of Computer Research and Development 62(3)
- Uber H3 hexagonal hierarchical spatial index (h3geo.org)
