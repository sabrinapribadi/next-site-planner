# ADR-002: Validation Strategy and Gates for Every Phase

**Status:** Proposed — gates written before any analysis; amended by ADR-003 (2026-10-13) before P1 ran
**Date:** 2026-10-13
**Deciders:** Sabrina Pribadi

---

## Context and Problem Statement

Spatial data breaks the usual validation habits: neighbouring hexagons are similar, so random splits make models look better than they are; thousands of hotspot tests produce false alarms; and "sites near high speeds" does not prove that sites raise speeds. Each phase needs a test that would catch these traps, fixed before the results exist.

The question: **"How will each phase be judged, and what would make it fail?"**

## SOTA comparison (methods judged in this project)

| Phase | Method family | Chosen | Tested head-to-head | Cited, not tested (why) |
|---|---|---|---|---|
| P1 hotspots | Local spatial statistics | Getis–Ord Gi* with false-discovery control (Ord & Getis 1995; Caldas de Castro & Singer 2006) | Gi* with vs without FDR (count of false hotspots on shuffled data) | Spatial scan statistics (circular windows suit disease clusters, not continuous speed surfaces) |
| P2 validation | Model evaluation | Spatial block cross-validation (Roberts et al. 2017) + leave-one-country-out + area of applicability (Meyer & Pebesma 2021) | Random vs spatial-block CV on the same models, to show the gap (Ploton et al. 2020) | Design-based accuracy with probability sampling (Wadoux et al. 2021): needs a random sample of locations, which crowdsourced tests are not; the counter-view is reported |
| P2 model | Spatial prediction | Gradient boosting with spatial features | Ordinary kriging (baseline), regression-kriging | Graph neural networks and learned location encoders: candidates for a later arm if gradient boosting fails the gate; recorded in the P2 ADR |
| P3 effect | Staggered difference-in-differences | Callaway & Sant'Anna (2021) | Borusyak, Jaravel & Spiess (2024) imputation estimator; two-way fixed effects shown only to illustrate its bias | Synthetic difference-in-differences (needs a balanced panel; Ookla tiles come and go) |
| P4 optimiser | Facility location | Maximal covering location (Church & ReVelle 1974), solved exactly (integer programming) | Greedy (guaranteed within 63% of optimal) and a KPI-style ranking baseline | Metaheuristics (genetic algorithms, particle swarm): unnecessary when an exact solver finishes; recorded if it does not |

Each later phase ADR repeats this table in detail for its own method (rule R2).

## Pre-registered gates

| Phase | Gate | Fails if |
|---|---|---|
| P0 | ≥ 99% of each country's Kontur population and ≥ 99% of its speed tests assigned to an H3 r8 cell in the right country; data-contract tests pass; snapshot manifest (SHA-256 per input) written | Assignment loses > 1% of people or tests in any country; any contract fails |
| P1 | Shares below 10 and 25 Mbps per country, raw and density-adjusted, with bootstrap 95% intervals (resampling tiles); Gi* hotspots at FDR 5%; every populated hexagon has a morphology class (Degree of Urbanisation) and a gap type (coverage / capacity / unmeasured); shares also by morphology and gap type, and at 100 Mbps (ADR-003) | No intervals; hotspots without FDR control; or any populated hexagon untyped |
| P2 | Gradient boosting RMSE of log download ≤ **0.90 ×** ordinary kriging under spatial block CV; leave-one-country-out errors reported for all seven; area of applicability mapped | Gain < 10%: keep kriging, report the negative result |
| P3 | Event-study pre-trend estimates (quarters −4 to −1) have 95% intervals that include 0; post-site effect on tile speed within 500 m reported with a 95% interval, Germany and US separately | Pre-trends fail: no causal claim; report as association |
| P4 | At the same **cost** budget in new-tower equivalents (central budget and a range), the optimiser lifts ≥ **10%** more people above 25 Mbps than ranking hexagons by a composite gap score; reported co-location-first and greenfield-only, across the ADR-003 cost ranges; CSV / GeoJSON / KML exports pass format checks | Gain < 10%: report that ranking is good enough; any export fails its check |
| P5 | API contract tests and the LLM evaluation set pass in CI; cost and latency within R13 budgets | Any contract or evaluation fails in CI |
| P6 | The Databricks job reproduces the local P1 country shares exactly (to the reported decimal) | Any share differs |
| P7 | Results page and technical walkthrough live; browser tests pass in three display modes | Any test fails |

Checks reported but not gated (ADR-003): urban-centre population share vs published Degree of Urbanisation figures where available (> 10 points apart is investigated).

## Deviations from the pre-registered plan (logged when found, with evidence)

| Date | Phase | Pre-registered | Found | Changed to | Evidence |
|---|---|---|---|---|---|
| 2026-10-13 | P1 | 95% intervals by Poisson bootstrap over speed tiles | Intervals miss their own estimate in Germany, France and the US (Germany below 10 Mbps: estimate 5.21%, interval 5.57–5.92%). 64% of German measured hexagons have one tile; dropping or reweighting tiles pushes hexagons across the bar more often downwards than upwards, so every resample is biased upwards (mean 5.73%; 6.25% if no hexagon is dropped) | **Spatial block bootstrap**: H3 resolution-5 blocks (~250 km²) with Poisson(1) weights; resolution 4 as sensitivity. Gate: each interval must contain its estimate | Tile intervals still computed and published next to the block intervals |
| 2026-10-13 | P1 | Gi* p-values (method not stated; normal approximation used) | On spatially shuffled data, FDR still flagged 259 false slow hotspots in Indonesia (912 on real data): with 1–6 neighbours and skewed speeds, the normal approximation is wrong in the tails | **Exact conditional randomisation**: the neighbours' sum is compared with the k-fold convolution of the country's empirical distribution, so tail p-values are exact enough for FDR over 100,000+ tests | Both versions' counts on real and shuffled data are published |

## Falsification

| Result | Diagnosis | Next action |
|---|---|---|
| Random CV ≫ spatial CV | Spatial leakage | Report both; only spatial CV counts |
| Model fails in an unseen country | Domain shift between markets | Report per country; restrict claims to the area of applicability |
| New-site effect ≈ 0 | Sites added for capacity in already-served areas, or data noise | Report; P4 uses a range including small effects |
| Optimiser ≈ ranking | Gaps are spatially separate, so greedy ranking is near optimal | Report; keep ranking for simplicity |

## Evidence (OpenAlex, retrieved 2026-10-13)

| Reference | Venue | Peer-reviewed | Year | Citations | Per year | Used for |
|---|---|---|---|---|---|---|
| The maximal covering location problem | Papers of the Regional Science Association | yes | 1974 | 2,710 | 51.1 | covering optimiser (P4) |
| Local spatial autocorrelation statistics: distributional issues and an application | Geographical Analysis | yes | 1995 | 3,649 | 114.0 | Gi* hotspot statistic (P1) |
| Controlling the false discovery rate: a new application to account for multiple and dependent tests in local statistics of spatial association | Geographical Analysis | yes | 2006 | 330 | 15.7 | false-discovery control (P1) |
| Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure | Ecography | yes | 2016 | 3,316 | 301.5 | spatial block CV (P2) |
| Spatial validation reveals poor predictive performance of large-scale ecological mapping models | Nature Communications | yes | 2020 | 864 | 123.4 | random CV overstates spatial models (P2) |
| Spatial cross-validation is not the right way to evaluate map accuracy | Ecological Modelling | yes | 2021 | 310 | 51.7 | counter-view (P2) |
| Predicting into unknown space? Estimating the area of applicability of spatial prediction models | Methods in Ecology and Evolution | yes | 2021 | 515 | 85.8 | area of applicability (P2) |
| Difference-in-differences with multiple time periods | Journal of Econometrics | yes | 2020 | 8,775 | 1,253.6 | staggered DiD (P3) |
| Revisiting event-study designs: robust and efficient estimation | Review of Economic Studies | yes | 2024 | 2,120 | 706.7 | imputation estimator, head-to-head (P3) |

Generated by `scripts/evidence.py` from `docs/references.yaml`; counts change over time.

## Consequences

- Positive: every phase can fail visibly, and a failure is still a result
- Negative: spatial CV gives lower (honest) scores than random CV; the page explains why

## Related Decisions

- ADR-001 (framing, unit, metrics)
- ADR-003 (industry alignment; amends P0, P1, P4)
