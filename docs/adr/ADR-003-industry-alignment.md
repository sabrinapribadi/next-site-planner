# ADR-003: Industry Alignment — Plan Sites the Way Network Planners Do

**Status:** Proposed — written before P1 runs; amends ADR-002 gates P0, P1, P4
**Date:** 2026-10-13
**Deciders:** Sabrina Pribadi

---

## Context and Problem Statement

ADR-001 and ADR-002 define a sound analysis, but a network planner would still ask:

- Is this a **coverage** gap (no usable signal) or a **capacity** gap (signal, but too many users)? They need different fixes.
- Is the area a city, a town or rural land? The area a single site serves depends on that.
- Can an **existing structure** be used first? Co-location is the default in the industry because it is cheaper and faster to approve.
- What does each option **cost**? A budget of "K sites" treats a rooftop small cell and a new rural tower as equal.
- How does the result compare with **regulators' targets**?
- Can the output go straight into a planning tool? Planners work with site lists and map files, not charts.

Portfolio rule R16 requires every project to be designed the way its industry works, not copied from an earlier project.

The question: **"What does a network-planning team expect from a site plan, and how does this project meet each expectation with public data?"**

## Decision Drivers

- Use the industry's terms and decision points: gap type, morphology, intervention type, cost, people lifted
- Base every assumption on a primary public source: standards bodies, regulators, statistical manuals (R6)
- Keep assumptions as config parameters with ranges, and carry those ranges into the results
- Fix everything before P1 runs, so the gates remain pre-registered

## Practitioner expectations and how they are met

| # | Expectation | Industry practice | This project (public data) | Primary source |
|---|---|---|---|---|
| E1 | Gap type | Coverage and capacity gaps are planned separately | Rule-based **gap type** for every populated hexagon below the bar (below) | — (definition stated here) |
| E2 | Morphology | Plans and link budgets differ for dense urban, urban, suburban and rural areas | **Degree of Urbanisation** (urban centre / urban cluster / rural) on the H3 grid | UN Statistical Commission–endorsed manual (Eurostat et al. 2021); Dijkstra et al. 2021 |
| E3 | Area served by one site | Taken from a link budget per morphology | Service radius = half the **3GPP evaluation inter-site distance** for the morphology | 3GPP TR 38.901, Tables 7.2-1 and 7.2-3 |
| E4 | Co-location first | Use existing structures before building new ones | Each candidate has an intervention: co-locate / small cell / new macro, cheapest feasible first | FCC 17-126 (2017), para. 46 |
| E5 | Cost | Budgets are money, not site counts | Cost in **new-tower equivalents** (new macro = 1.0); the budget is in the same unit | FCC 17-126, para. 46 |
| E6 | Regulatory benchmark | Coverage obligations and policy targets | Extra 100 Mbps bar (sensitivity); share of populated hexagons with a 5G cell nearby | BNetzA 2019 auction; EU Decision 2022/2481; ITU-R M.2410 |
| E7 | Planner-ready output | Site lists and map layers loaded into GIS and planning tools | CSV, GeoJSON and KML candidate lists; district roll-ups; cost–benefit curve | — (formats are open standards) |
| E8 | Post-launch check | Before and after review of new sites | Tracking table per chosen candidate; P3 method re-applied each quarter | ADR-002 (P3) |
| E9 | Operating cadence | Plans refreshed on a fixed cycle | Quarterly, after each Ookla release; a dated snapshot manifest per refresh | Ookla open data (quarterly) |

## Decisions

### E1 — Gap type (pre-registered rule)

Applied to populated hexagons only.

| Gap type | Rule | Typical fix |
|---|---|---|
| **Coverage gap** | Measured speed below the bar, and **no LTE or 5G cell** (OpenCelliD) within ring-1 (about 1.2 km) | New macro site |
| **Capacity gap** | Measured speed below the bar, with LTE or 5G cells within ring-1 | Co-location, sector or carrier add, or a small cell |
| **Unmeasured** | No speed tests in the latest quarter | P2 predicts speed with an interval; typed after P2 |
| No gap | Measured speed at or above the bar | — |

- **Load indicator** for capacity gaps: people per LTE/5G cell within ring-1. Reported, not used as a gate.
- **Caveat:** OpenCelliD positions are estimated from crowdsourced sightings, not surveyed tower positions. Errors of a few hundred metres are expected, which is why ring-1 is used rather than the hexagon itself.

### E2 — Morphology: Degree of Urbanisation on H3

**How the classes are assigned**

| Class | Rule (manual) | Applied here |
|---|---|---|
| Urban centre | Contiguous 1 km² cells, each ≥ 1,500 people/km², ≥ 50,000 people in total | Hexagon density = population ÷ hexagon area; H3 ring-1 contiguity |
| Urban cluster | Contiguous cells, each ≥ 300 people/km², ≥ 5,000 people in total; urban-centre cells removed | Same |
| Rural | All other cells | Same |

**Where the H3 version differs from the manual (stated, not hidden)**

- The cells are 0.74 km² hexagons, not 1 km² squares.
- Hexagons have 6 neighbours, so the manual's 4-point and 8-point contiguity rules collapse into one rule.
- No gap-filling or built-up-area additions.

**Options considered**

| Option | Status | Why |
|---|---|---|
| **Degree of Urbanisation thresholds on the H3 grid** | **Chosen** | Global, harmonised definition endorsed by the UN Statistical Commission (2020); one rule for all seven countries |
| Global Human Settlement Layer settlement-model raster (GHS-SMOD) | Cross-check if time allows | Official implementation, but on a 1 km Mollweide grid; resampling adds error |
| National urban/rural definitions | Rejected | Differ by country, so a fair comparison is impossible |
| Single density threshold | Rejected | Ignores contiguity, so a dense village would count as a city |

### E3 — Area served by one new site

Half the inter-site distance (ISD) of the 3GPP evaluation layout for each morphology. These are standard evaluation geometries, not a site-specific link budget; antenna height, power and spectrum are private (ADR-001).

| Morphology | 3GPP scenario | ISD | Service radius | Share of the H3 r8 hexagon served |
|---|---|---|---|---|
| Urban centre: macro | UMa | 500 m | 250 m | about 29% of its hexagon |
| Urban centre: small cell | UMi street canyon | 200 m | 100 m | about 5% of its hexagon |
| Urban cluster | UMa (upper end of the 200–500 m range allowed for evaluations) | 500 m | 250 m | about 29% of its hexagon |
| Rural | RMa | 1,732 m (5,000 m in sensitivity) | 866 m (2.5 km) | its hexagon plus ring-1 (about ring-3) |

- **Coverage share:** each site covers the area of its hexagonal cell, (√3/2) × ISD². In urban areas this is smaller than one H3 r8 hexagon, so a site lifts that fraction of the hexagon's people.
- **Uplift size:** how much speed a new site adds is not assumed. It comes from P3's measured effect and its interval.

### E4 and E5 — Interventions and cost

Costs are in **new-tower equivalents**: relative units, so no currency is converted across seven markets. The ratios come from a US regulator's 2017 report. Applying them to other countries is an assumption, so P4 reports results across the ranges below.

| Intervention | When it is feasible | Cost (new macro = 1.0) | Range tested | Source |
|---|---|---|---|---|
| Co-location on an existing structure | An LTE/5G cell (a proxy for a structure) lies within the service radius | 0.30 | 0.20–0.50 | FCC 17-126 para. 46: co-location is "about 30 percent of the total cost of a new tower" |
| Small cell | Urban-centre capacity gap | 0.50 | 0.25–0.50 | FCC 17-126 para. 46: small-cell per-site cost (capital and operating) is "less than half" of a macro site |
| New macro site (greenfield) | Always | 1.00 | — | Reference unit |

**Considered and not used**

| Option | Why not |
|---|---|
| Tower registers (e.g. the US antenna-structure registration database) as co-location candidates | US only; not comparable across seven countries. Possible later extension for the US |

### E6 — Regulatory and standards benchmarks (context, not gates)

- **Germany, BNetzA 2019 auction:** each licensee must supply at least 100 Mbit/s to 98% of households in every federal state by the end of 2022.
- **ITU-R M.2410:** IMT-2020 minimum user-experienced data rate of 100 Mbit/s downlink in the dense-urban test environment. It is defined at the 5th percentile of users, so a hexagon's average speed is a softer test than the standard.
- **New 100 Mbps bar:** added as a sensitivity alongside 5, 10, 25 and 50 Mbps.
- **EU Decision 2022/2481 (Digital Decade):** every populated area covered by high-speed networks at least equivalent to 5G by 2030.
  - New KPI: the **share of populated hexagons with a 5G (NR) cell within ring-1**, for all seven countries. OpenCelliD under-records cells, so this is a lower bound.
- **Caveat on every page:** obligations are tested by the regulator's own measurements and coverage maps. Crowdsourced average speeds are an outside view, **not** a compliance test.
- **Other countries:** targets for the other five countries are added only once a primary source (the regulator or the government gazette) has been checked.

### E7 — Planner-ready deliverables

**Candidate list**

- **Formats:** CSV, GeoJSON and KML, from the API and the results page.
- **Columns:** rank, country, district (kecamatan, county or similar), H3 cell, latitude/longitude, morphology, gap type, intervention, cost, people lifted (central and range), cumulative cost, cumulative people.

**Other outputs**

- **Cost–benefit curve:** people lifted against cumulative cost. Planners use it to pick the budget cut-off.
- **District roll-ups:** gap and plan results per district.

**Format checks (test-checked)**

- GeoJSON validates against RFC 7946.
- KML parses as OGC KML 2.2.
- CSV matches the documented schema.

### E8 and E9 — Post-launch tracking, cadence, operations

- **Post-launch tracking:** for each chosen candidate, the hexagons it would serve and their baseline speed, re-measured every quarter. Where a real cell appears (OpenCelliD), the P3 event-study method is re-applied.
- **Snapshot manifest per refresh** (`data/outputs/manifest.json`): source, release, URL, bytes, SHA-256, rows, retrieval date.
- **Data contracts in CI:**
  - (country, hexagon) is unique;
  - population ≥ 0 and speeds > 0;
  - the expected quarters are present.
- **Model card** for the P2 speed model (intended use, area of applicability, error per country).
- **Runbook** for the P6 Databricks job.

## How this differs from the earlier portfolio project (R16)

| | Earlier project (subscription churn) | This project (network planning) |
|---|---|---|
| Unit | Customer | Place (hexagon) |
| Decision | Whom to contact this month | Where to invest capital this year |
| Budget | Calls | New-tower equivalents |
| Validation | Time-based holdout | Spatial block CV, leave-one-country-out |
| Proof of value | Calibrated uplift | Measured effect of real new sites (P3) |
| Deliverable | Call list | Site list, KML/GeoJSON layers, cost–benefit curve |

**Reused, not copied:** gates written before the work, ADRs, CI, the two pages, drift checks, the cost and latency budget for LLM features.

## Amendments to ADR-002 (pre-registered; nothing has run yet)

| Phase | Added to the gate |
|---|---|
| P0 | Snapshot manifest written with SHA-256 for every input; data-contract tests pass |
| P1 | Every populated hexagon has a morphology class and a gap type. Shares are reported by morphology and gap type, and at 100 Mbps as a sensitivity |
| P1 check (reported, not a gate) | Population share in urban centres versus published Degree of Urbanisation figures, where available. A gap above 10 percentage points is investigated and explained |
| P4 | Budget in new-tower equivalents, not K sites. The optimiser must lift ≥ 10% more people than the ranking baseline at equal **cost**. Results are shown for co-location-first and greenfield-only, and across the cost ranges. Exports pass the format checks |

## Evidence (OpenAlex, retrieved 2026-10-13)

| Reference | Venue | Peer-reviewed | Year | Citations | Per year | Used for |
|---|---|---|---|---|---|---|
| Applying the Degree of Urbanisation to the globe: a new harmonised definition reveals a different picture of global urbanisation | Journal of Urban Economics | yes | 2020 (vol. 125, 2021) | 380 | 54.3 | Morphology method (E2) |

Generated by `scripts/evidence.py`. Primary documents without citation counts (standards, regulators, law):

| Document | Issuer | Year | Used for |
|---|---|---|---|
| Applying the Degree of Urbanisation: a methodological manual | Eurostat, FAO, ILO, OECD, UN-Habitat, World Bank; endorsed by the UN Statistical Commission | 2021 | Morphology thresholds (E2) |
| TR 38.901, Study on channel model for frequencies from 0.5 to 100 GHz, §7.2 | 3GPP | current release | Inter-site distances (E3) |
| FCC 17-126, Twentieth Mobile Wireless Competition Report, para. 46 | US Federal Communications Commission | 2017 | Cost ratios (E4, E5) |
| Press release: assignment of 5G spectrum (4 Sep 2019) | Bundesnetzagentur | 2019 | 100 Mbit/s for 98% of households (E6) |
| Decision (EU) 2022/2481, Digital Decade Policy Programme 2030 | European Parliament and Council | 2022 | 5G for every populated area (E6) |
| ITU-R M.2410-0, Minimum requirements for IMT-2020 radio interfaces | ITU-R | 2017 | 100 Mbit/s user-experienced rate (E6) |

## Falsification

| Result | Diagnosis | Next action |
|---|---|---|
| Almost every slow hexagon is typed as a capacity gap | OpenCelliD cells are dense near roads, so ring-1 is too generous | Report it; check with ring-0 as a sensitivity |
| Urban-centre share is far from published figures | H3 contiguity or density differs from the 1 km grid | Report the gap; cross-check with GHS-SMOD if feasible |
| Co-location-first and greenfield-only plans are almost the same | Gaps are mostly far from existing cells (coverage gaps) | Report it: co-location gives little benefit in these markets |
| Results change sharply across cost ranges | The plan is sensitive to cost assumptions | Show the range; recommend local cost data before use |

## Consequences

- **Positive:** the output answers planners' real questions (what kind of gap, which fix, what cost), and every assumption has a source and a tested range.
- **Negative:**
  - Gap typing and site counts rely on crowdsourced cell positions.
  - Costs are relative units drawn from one country.
  - Both limits are stated on the results page.

## Related Decisions

- ADR-001 (framing, unit, metrics)
- ADR-002 (validation and gates; amended above)
