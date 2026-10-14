# ADR-001: Framing — Measured Experience per Person on an H3 Grid, Seven Countries

**Status:** Accepted — implemented in P0 and P1 (2026-10-13)
**Date:** 2026-10-13
**Deciders:** Sabrina Pribadi

---

## Context and Problem Statement

Site plans are often built by ranking candidate locations on many indicators with agreed weights. That answers *which sites score highest*, not *where one more site would improve experience for the most people, per unit of budget*. Comparisons between countries usually quote national median speeds, which mix dense cities with remote islands and say nothing about how many people are poorly served.

The question this project must answer is: **"Where do the most people live with poor measured mobile experience, how does that compare fairly across countries, and which budgeted set of new sites would lift the most of them?"**

## Decision Drivers

- Measured experience, not claimed coverage: speed tests from real devices
- Count **people**, not tiles or tests: weight by where people live and gather
- One analysis unit that is equal-area across latitudes, so Indonesia (equator) and Germany (51° N) compare fairly
- Public, licence-compatible data only (R1), reproducible by a script
- Spark and Databricks only if measured volume or operations justify them (R15)

## Considered Options

**How experience is measured**

| Option | Status | Why |
|---|---|---|
| Operator coverage maps | Rejected | Claimed coverage, not measured experience; not public in a common format for seven countries |
| Drive tests | Rejected | Not public |
| Radio propagation model from site configurations | Rejected | Needs antenna heights, power, spectrum: private |
| **Crowdsourced speed tests (Ookla open tiles), weighted by population** | **Chosen** | Public, quarterly, global, consistent method; bias (people test when it is slow or new) stated and reported per tile |
| Other crowdsourced panels (e.g. commercial app panels) | Rejected | Not open data |

**Analysis unit**

| Option | Status | Why |
|---|---|---|
| Ookla's native quadkey tiles (zoom 16) | Rejected as the unit | Area shrinks with latitude (~610 m at the equator, ~380 m in Germany): unfair across countries |
| Administrative units (kecamatan, counties) | Reporting level only | Very unequal sizes; aggregation hides gaps (modifiable areal unit problem) |
| 1 km square raster | Rejected | Not hierarchical; no native support in Spark/Databricks |
| **H3 resolution 8 (~0.74 km² hexagons)** | **Chosen** | Near equal-area worldwide; hierarchical (roll up to r7/r6, down to r9); native H3 functions in Databricks SQL; the population layer is already on r8 |

**Population layer**

| Option | Status | Why |
|---|---|---|
| **Kontur population 2023 (H3 r8, built from GHSL, Meta HRSL and OSM)** | **Chosen** | One global, consistent layer for all seven countries, already on the analysis grid; CC BY 4.0 |
| WorldPop constrained 100 m (random-forest dasymetric mapping, Stevens et al. 2015) | Cross-check, all seven countries (ADR-008 amendment 1) | Strong method, independent of Kontur's inputs; its server is slow (the US file, 494 MB, takes hours) |
| Census tables only | Rejected | Admin-level only; no sub-district detail |

## Decision Outcome

- **Countries:** Indonesia, Malaysia, Philippines, Germany, France (metropolitan), United States (lower 48), United Arab Emirates. Overseas territories, Alaska and Hawaii are excluded and stated.
- **Grid:** each Ookla tile centre is assigned to its H3 r8 cell; a hexagon's speed is the test-weighted mean over its tiles of log download speed (speeds are right-skewed). Population and places are aggregated to the same cells.
- **Headline metric:** share of a country's population living in hexagons whose measured median mobile download is below **10 Mbps** and below **25 Mbps** (sensitivity at 5 and 50). Reported alongside the share of population in hexagons **with no measurement**, never silently dropped.
- **Fair comparison:** shares are also reported **density-adjusted** — computed within population-density deciles and re-weighted to a common density distribution — so archipelagos and dense cities are compared like for like.
- **Period:** latest quarter (2026 Q3) for maps; 2023 Q1–2026 Q3 for trends and for the new-site study.
- **Spark / Databricks (R15), measured:** ~49M speed-tile rows kept (13.8M mobile + 34.7M fixed) from 152M read for 15 quarters (53.7M mobile + 98.5M fixed; counted from the files' metadata on 2026-10-14, correcting an earlier "~300M"), plus 6.4M population hexagons and 29.8M places, joined spatially. Spark is justified for the full refresh; Databricks for the quarterly job, registry and drift checks (P6). **Outcome (ADR-010):** P6 runs Indonesia only. It reads the global files at the source (53.7M mobile rows) and keeps 2.4M; Indonesia alone fits DuckDB, so there operations justify Databricks, not size. Exploration runs locally on DuckDB.

## Evidence (OpenAlex, retrieved 2026-10-13)

| Reference | Venue | Peer-reviewed | Year | Citations | Per year | Used for |
|---|---|---|---|---|---|---|
| Disaggregating Census Data for Population Mapping Using Random Forests with Remotely-Sensed and Ancillary Data | PLoS ONE | yes | 2015 | 1,066 | 88.8 | WorldPop cross-check |
| Stratifying the Digital Divide: Analysis of Socio-Economic Influences on Internet Performance | arXiv 2605.30809 | no (preprint) | 2026 | 0 | 0.0 | context: recent use of Ookla tiles for inequality |

Data sources without papers (vendor or agency documentation): Ookla open data, Kontur population, Overture Maps, OpenCelliD, H3 (h3geo.org), OCHA COD-AB, geoBoundaries, Natural Earth.

## Falsification

| Result | Diagnosis | Next action |
|---|---|---|
| Large share of population in unmeasured hexagons (> 20% in a country) | Speed tests too sparse there | Report it as a finding; P2 predicts speed with intervals; flag the country |
| Density adjustment changes no country's rank | Density does not explain differences | Report raw and adjusted side by side; say so |
| Kontur and WorldPop disagree by > 10% on Indonesia's population in poorly served hexagons | Population layer uncertainty | Report both; carry the range into P4 |

## Outcome and open items (audit 2026-10-14)

- **Implemented as decided:** H3 resolution 8, people-weighted shares below 10/25 Mbps (sensitivity 5/50/100), density-adjusted comparison, untested people reported.
- **Unmeasured above 20%:** true in six of seven countries (14–47% of people). As planned, P2 now predicts their speed (ADR-004, ADR-005).
- **Density adjustment changes ranks:** yes. The Philippines and Indonesia fall further behind at equal density.
- **WorldPop cross-check (falsification row 3), run for all seven countries.** It was meant to run before P4 used population totals; it did not, and was caught by inspecting the nominal map. This is disclosed in ADR-008 amendment 1, which ran it before re-planning. Results for all seven countries:

| Country | Total: Kontur / WorldPop | People in poorly served hexagons: difference | People where the maps differ > 3× | Expected below 25 Mbps: Kontur / WorldPop / smaller | Untested, likely below 25 Mbps: Kontur / WorldPop | Row 3 (> 10%) |
|---|---|---|---|---|---|---|
| Indonesia | 269.7M / 273.5M | -26.6% | 17.7% | 49.1M / 39.5M / 22.3M | 30.3M / 21.8M | triggered |
| Malaysia | 33.3M / 32.4M | -27.9% | 6.0% | 1.3M / 0.9M / 0.5M | 0.8M / 0.5M | triggered |
| Philippines | 107.9M / 95.0M | -36.7% | 23.5% | 33.4M / 22.3M / 13.9M | 23.4M / 13.3M | triggered |
| Germany | 83.3M / 83.8M | -6.9% | 1.0% | 9.5M / 8.9M / 7.2M | 5.5M / 4.8M | no |
| France | 63.9M / 65.2M | -8.5% | 0.7% | 4.1M / 3.9M / 2.8M | 3.4M / 3.1M | no |
| United States | 332.2M / 307.7M | -17.3% | 0.3% | 7.0M / 5.4M / 4.5M | 4.7M / 3.2M | triggered |
| UAE | 9.0M / 9.9M | -31.6% | 24.2% | 39k / 21k / 11k | 34k / 13k | triggered |

  - **Germany and France:** the maps agree; Kontur stays the population for P1–P3.
  - **Indonesia, Malaysia, the Philippines, the UAE and the US:** row 3 is triggered (the US at −17%, with only 0.3% of people where the maps differ more than 3×). As pre-set, both are reported and the range is carried forward. Headline counts become Kontur–WorldPop ranges, and plans count the smaller of the two per hexagon (ADR-008 amendment 1).
  - **Pattern:** compared with WorldPop, Kontur places 17–37% more people in poorly served hexagons in these countries. Neither map is ground truth: Kontur spreads people over rural land surfaces, while WorldPop drops people where no settlement was detected (its Philippines total is 12% below the UN figure).

## Consequences

- Positive: every number is about people, comparable across latitudes, and reproducible from public data
- Negative: speed tests are not a random sample; results describe tested experience. Stated on every page
- Negative: the CC BY-NC-SA licence of Ookla data carries over to published derived maps

## Related Decisions

- ADR-002 (validation and gates for every phase)
