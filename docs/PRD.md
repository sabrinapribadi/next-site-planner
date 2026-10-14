PRODUCT REQUIREMENT DOCUMENT (PRD)
Project: Next Site Planner — Where Would One More Mobile Site Help the Most People?
Version: 0.6 (P4 nominals checked against a second population map, land cover and terrain, ADR-008 amendments 1–2; US pending its WorldPop file)
Author: Sabrina Pribadi
Date: October 14, 2026
Status: Active — P0, P1 passed; P2 gate failed (kriging deployed; ADR-006 retest pending 2026 Q4); P3 done; P4 done (original gate passed; checked plans pass in 6 of 6 checked countries, US pending); P5 next


1. EXECUTIVE SUMMARY

Problem: Mobile operators decide every year where to add sites. Plans are often built by
ranking candidate locations on many indicators at once (traffic, congestion, devices,
revenue), with weights agreed in meetings. That answers "which sites score highest?",
not "where would one more site improve the experience of the most people, per unit of
budget?" — and nobody checks afterwards whether new sites actually lifted speeds nearby.

Solution: A reproducible, public-data planner for seven countries (Indonesia, Malaysia,
Philippines, Germany, France, United States, United Arab Emirates). It maps measured mobile
experience (Ookla open speed tiles, 15 quarters) against where people live (Kontur population,
cross-checked with WorldPop), with places (Overture) as context, on one H3 hexagon grid; benchmarks countries fairly at
equal population density; predicts speed where tests are sparse with spatially validated
models; measures what a new site does to nearby speeds from cell first-seen dates
(OpenCelliD, all seven countries, one rule); and chooses a budget of sites and added capacity
with an exact optimiser instead of a ranking, checking every nominal against a second
population source, land cover and terrain. Served as a web map, an API and MCP tools, refreshed
quarterly on Databricks.

Value Proposition: Replace "rank sites by KPIs" with "measure the gap, measure what sites
do, then optimise the set" — every number reproducible from public data.

Success Metrics (pre-registered — see ADR-002):
- P0: ≥ 99% of each country's population and ≥ 99% of its speed tests land on the H3 grid — **passed**
- P1: population share below 10 and 25 Mbps per country, raw and density-adjusted, with 95% intervals; every populated hexagon typed by morphology and gap (coverage / capacity) — **passed** after two logged deviations
- P2: the spatial model beats ordinary kriging by ≥ 10% (RMSE of log speed) under spatial block cross-validation — **failed: 7% (ratio 0.929); kriging deployed**
- P3: new-site effect with a 95% interval and a passing pre-trend (placebo) test — **passed in Germany, France, US, Philippines; failed in Indonesia and the UAE; Malaysia has too few new sites**
- P4: the optimiser lifts ≥ 10% more people above 25 Mbps than a KPI-style ranking at the same cost budget (new-tower equivalents) — **original plan passed in 6 of 7 (+56% to +776%); checked plans pass in 6 of 6 checked countries (+50% to +281%); US pending**
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
5. Operations research: budgeted site selection (exact 0/1 knapsack; maximal covering as a sensitivity)
6. MLOps: Spark on Databricks, quarterly refresh job, drift checks, model registry, CI
7. GenAI: grounded site rationales and MCP tools, with cost and latency budgets


3. SCOPE

In scope: seven countries; mobile and fixed speed tiles 2023 Q1–2026 Q3; H3 resolution 8;
residential population (Kontur 2023) and daytime places (Overture 2026-09); cell locations
(OpenCelliD snapshot 2026-10-13); boundaries (OCHA kecamatan for Indonesia, geoBoundaries elsewhere).

Out of scope: site-specific radio propagation modelling (3GPP evaluation inter-site distances are used
instead, ADR-003); absolute costs in currency (relative costs in new-tower equivalents, varied over a range);
any operator's private data; naming operators; compliance testing against licence obligations.

Known data limits (measured, plan §9):
- Ookla tiles exist only where people ran tests; only ~20% of Indonesian mobile tiles appear in all 15 quarters
- OpenCelliD dates: records "created" in 2025–26 are mostly one-off sightings; only cells first seen
  up to 2024 and seen for months afterwards count as new sites. Indonesia has ~1.3k such cells, Germany ~40k, the US (MCC 310) ~61k
- Ookla licence is CC BY-NC-SA 4.0: derived maps are published under the same licence


4. USER PERSONAS AND STORIES

| Persona | Need | Today |
|---|---|---|
| Network planner | A costed list of interventions (co-locate, small cell, new site) by gap type and morphology, as CSV / GeoJSON / KML | Sites ranked by composite KPI scores |
| Regulator / policy analyst | Where coverage is worst for the most people, compared fairly with peer countries | Raw national medians that mix cities and islands |
| Capex reviewer | Evidence that new sites improve experience nearby | Before/after checks rarely done |
| GIS analyst | The same answer at kecamatan, district or hexagon level | Manual joins in desktop GIS |
| AI assistant | Typed tools: gap at a place, top sites for a budget, why this site | None |

User stories:
- As a planner, I give a country, a budget (new-tower equivalents) and a speed bar, and get a site list — gap type, morphology,
  intervention, cost, people lifted — plus a cost–benefit curve, ready for GIS and planning tools.
- As a policy analyst, I compare Indonesia with six markets at equal population density.
- As a reviewer, I see how much a new site lifted nearby speeds, with an interval.
- As an AI agent (via MCP), I can call gap_at(place), top_sites(country, k), explain_site(h3) and compare_countries().


5. FUNCTIONAL REQUIREMENTS

Module A: Data foundation on H3 resolution 8; snapshot manifest; data contracts — ADR-001, ADR-003 (P0)
Module B: Experience-gap map, fair benchmark, morphology and gap typing, regulatory benchmarks — ADR-003 (P1)
Module C: Speed where nobody tested (kriging deployed; LightGBM compared), measurement noise and shrinkage — ADR-004, ADR-005 (P2)
Module D: New-site effect, all seven countries — ADR-007 (P3)
Module E: Budgeted site plan — new sites and added capacity, costed, exact, planner exports — ADR-008 (P4)
Module F: API, MCP tools, grounded rationales — P5 (ADR to be written)
Module G: Databricks quarterly job, registry, drift — P6 (ADR to be written; R15 justification in ADR-001)


7. DATA STRATEGY

| Source | Licence | Use |
|---|---|---|
| Ookla open performance tiles, mobile + fixed, 2023 Q1–2026 Q3 | CC BY-NC-SA 4.0 | Measured download, upload, latency, tests and devices per ~610 m tile |
| Kontur population 2023-11-01, H3 resolution 8 | CC BY 4.0 | Residential population per hexagon |
| Overture Maps places, release 2026-09-23.1 | CDLA-Permissive 2.0 | Speed-model input (compared, not deployed); KPI baseline; place count reported per nominal. Not counted as demand: benefit counts residents only, because place counts are not people and their completeness differs by country |
| OpenCelliD full database, 2026-10-13 | CC BY-SA 4.0 | Cell locations, radio type, first and last seen |
| OCHA COD-AB Indonesia; geoBoundaries gbOpen | CC BY-IGO; CC BY 4.0 / ODbL | Kecamatan and district reporting |
| Natural Earth admin-0 | Public domain | Assign tiles and hexagons to countries |
| WorldPop 2020 constrained, UN-adjusted, 100 m, all seven countries | CC BY 4.0 | Second population source: cross-check of Kontur; plans count the smaller of the two per hexagon (ADR-008 amendment 1) |
| ESA WorldCover 2021 v200, 10 m | CC BY 4.0 | Built-up land per nominal (≥ 1,000 m²); site point on built land |
| Copernicus DEM GLO-30 | Free licence | Elevation and slope at each site point (flags) |

Raw data lives in `GEO_DATA_DIR` (OneDrive `github_project/data/geo`), never in the repository.
`scripts/acquire_public_data.py` rebuilds it; sources that change (OpenCelliD, Overture) are kept as dated snapshots.


9. IMPLEMENTATION PLAN

| Phase | Goal | Gate / exit criterion (ADR-002) |
|---|---|---|
| P0 | Seven-country data foundation on H3 r8 | ≥ 99% of population and of speed tests assigned to the grid; contract tests pass — **passed** |
| P1 | Experience-gap map; fair cross-country benchmark; hotspots; gap types and morphology | Shares below 10 / 25 Mbps with 95% intervals, raw and density-adjusted; Gi* hotspots at FDR 5%; every populated hexagon typed — **passed** |
| P2 | Speed where nobody tested | LightGBM ≤ 0.9 × best kriging RMSE (log speed) under resolution-6 block CV; transfer to an unseen country reported — **failed (0.929); kriging deployed** |
| P3 | Effect of new sites (all seven countries, same rule) | Parallel pre-trends; effect with 95% interval — **done**: slow places lifted above 25 Mbps +12.1 pts (France) and +12.6 (Germany) as pre-set; cautious values after regression-to-the-mean checks +12.1 (France), +5.2 (Germany), +1.5 (US); average speed ≈ 0 except the US |
| P4 | Budgeted site optimiser | ≥ 10% more people lifted above 25 Mbps than KPI ranking at equal cost; exports pass format checks — **done**: original 6 of 7; checked nominals (two population maps, ≥ 1,000 m² of buildings, terrain) 6 of 6 checked countries, US pending; CSV / GeoJSON / KML per country with site points |
| P5 | API + MCP + grounded rationales | Contract tests and LLM evaluation pass in CI; R13 budgets met |
| P6 | Databricks quarterly job + registry + drift | Databricks reproduces local P1 numbers exactly |
| P7 | Results page + technical walkthrough + web map | Both pages live and browser-tested (R10, R12, R14, R17) — pages live and updated each phase |


11. RISKS AND MITIGATIONS

| Risk | Mitigation |
|---|---|
| Speed tests are not a random sample (people test when it is slow or new) | Report tests and devices per tile; weight by population, not tests; state the bias on the page |
| Sparse tiles in rural areas | P2 predicts with intervals; area-of-applicability flags where predictions are unreliable (95% of untested people inside) |
| Measurement noise: most hexagons rest on 1–2 tests; one test varies 3–5× | ADR-005: noise model, shrinkage toward the neighbourhood, checked on the next quarter (28–44% closer); corrected shares marked credible or provisional |
| OpenCelliD first-seen dates are noisy | Use only cells first seen ≤ 2024 and observed ≥ 180 days; placebo test |
| Effect estimated abroad may not hold in Indonesia | State it as an assumption; sensitivity range in P4 |
| Population maps disagree where data is thin (27–37% in poorly served places in Southeast Asia and the UAE) | Two maps; plans count the smaller; headline counts shown as ranges (ADR-001, ADR-008 amendment 1) |
| A nominal falls in forest, water or empty land | Built-up check (≥ 1,000 m², WorldCover) and a site point on built land; terrain flags (ADR-008 amendment 1) |
| "New site" relies on OpenCelliD, which misses most towers in Southeast Asia | Recorded cells shown on the nominal map; planners check new-site nominals against an operator's site list |
| Free Edition cannot read Ookla's S3 | Test first; else upload country extracts (as in CHN-1) |
| Cost ratios come from one regulator (US, 2017) | Relative units, not currency; P4 reports results across ranges; local cost data recommended before use |
| OpenCelliD cells are not tower positions | Ring-1 search, ring-0 sensitivity; co-location counts are a proxy |
| 8 GB development machine | DuckDB locally with out-of-core execution; Spark on Databricks for the full refresh |


14. APPENDIX — References

- Ookla Open Data, Speedtest by Ookla Global Fixed and Mobile Network Performance Maps (AWS Open Data Registry)
- Church, R. & ReVelle, C. (1974). The maximal covering location problem. Papers of the Regional Science Association 32
- Khuller, S., Moss, A. & Naor, J. (1999). The budgeted maximum coverage problem. Information Processing Letters 70(1)
- Huangfu, Q. & Hall, J. A. J. (2018). Parallelizing the dual revised simplex method. Mathematical Programming Computation 10 (HiGHS)
- Stevens, F. R. et al. (2015). Disaggregating census data for population mapping using random forests with remotely-sensed and ancillary data. PLoS ONE 10(2) (WorldPop)
- Zanaga, D. et al. (2022). ESA WorldCover 10 m 2021 v200. Zenodo, doi:10.5281/zenodo.7254221
- European Space Agency (2021). Copernicus DEM GLO-30, doi:10.5270/ESA-c5d3d65
- Horn, B. K. P. (1981). Hill shading and the reflectance map. Proceedings of the IEEE 69(1)
- Ord, J. K. & Getis, A. (1995). Local spatial autocorrelation statistics. Geographical Analysis 27(4)
- Meyer, H. & Pebesma, E. (2021). Predicting into unknown space? Estimating the area of applicability of spatial prediction models. Methods in Ecology and Evolution (arXiv 2005.07939)
- Callaway, B. & Sant'Anna, P. (2021). Difference-in-differences with multiple time periods. Journal of Econometrics 225(2)
- Stratifying the digital divide: socio-economic influences on Internet performance (2026). arXiv 2605.30809
- Uber H3 hexagonal hierarchical spatial index (h3geo.org)
- Hengl, T. et al. (2018). Random forest as a generic framework for predictive modeling of spatial and spatio-temporal variables. PeerJ
- Sekulić, A. et al. (2020). Random Forest Spatial Interpolation. Remote Sensing 12(10)
- Ke, G. et al. (2017). LightGBM: A Highly Efficient Gradient Boosting Decision Tree. NeurIPS
- Linnenbrink, J. et al. (2024). kNNDM CV. Geoscientific Model Development 17
- Milà, C. et al. (2022). Nearest neighbour distance matching Leave-One-Out Cross-Validation. Methods in Ecology and Evolution
- Pebesma, E. (2004). Multivariable geostatistics in S: the gstat package. Computers & Geosciences 30
- Cressie, N. (1985). Fitting variogram models by weighted least squares. Mathematical Geology 17
- Fay, R. & Herriot, R. (1979). Estimates of income for small places. Journal of the American Statistical Association 74
- Ghosh, M. & Rao, J. N. K. (1994). Small Area Estimation: An Appraisal. Statistical Science 9
- Eurostat, FAO, ILO, OECD, UN-Habitat, World Bank (2021). Applying the Degree of Urbanisation: a methodological manual
- Dijkstra, L. et al. (2021). Applying the Degree of Urbanisation to the globe. Journal of Urban Economics 125
- 3GPP TR 38.901. Study on channel model for frequencies from 0.5 to 100 GHz, §7.2 (evaluation scenarios)
- FCC 17-126 (2017). Twentieth Mobile Wireless Competition Report, para. 46
- Bundesnetzagentur (4 Sep 2019). Press release: assignment of 5G spectrum (coverage obligations)
- Decision (EU) 2022/2481. Digital Decade Policy Programme 2030
- ITU-R M.2410-0 (2017). Minimum requirements related to technical performance for IMT-2020 radio interfaces
