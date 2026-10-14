# ADR-008: Budgeted Site Plan — Where the Next Sites Should Go (P4)

**Status:** Accepted — written and pushed before any P4 plan; gate passed (results below)
**Date:** 2026-10-14
**Deciders:** Sabrina Pribadi

---

## Context and Problem Statement

What the earlier phases give P4:

| Input | Source | Note |
|---|---|---|
| Chance that each populated 0.74 km² hexagon's typical speed is below 25 Mbps | P2 / ADR-005 | Tested: noise-corrected; untested: kriging |
| Effect of a new site | P3 / ADR-007 | Lifts some slow places above 25 Mbps **in its own hexagon**; the ring around it ≈ 0. Cautious crossing rates θ: France 0.121, Germany 0.052, US 0.015; others have no reliable estimate |
| Effect of added capacity | P3 | Average speed ≈ 0; crossing rate not yet estimated |
| Costs, morphology, 3GPP service radii | ADR-003 | Costs in new-tower equivalents (macro 1.0, small cell 0.5, co-location 0.30) |

People whose typical speed is below 25 Mbps: Indonesia 49.1M, Philippines 33.4M, Germany 9.5M, US 7.0M, France 4.1M, Malaysia 1.3M, UAE 0.04M.

The question: **"For a given budget, which set of sites lifts the most people above 25 Mbps — and how much better is that than ranking places by a usual KPI score?"**

## Decision (pre-registered)

### Candidates and benefit

**Candidate:** one intervention per populated hexagon h.

| Situation in h | Intervention | Cost | Lift rate |
|---|---|---|---|
| No LTE/5G cell recorded within ring 1 (P3's "new site" definition) | New site: small cell in urban centres (0.5), macro elsewhere (1.0) | 0.5 or 1.0 | θ_new |
| Cells nearby | Added capacity (co-location, sector or carrier) | 0.30 | θ_cap |

**Expected people lifted** by an intervention in h:

pop_h × P(typical speed_h < 25 Mbps) × θ

- **Service area (central):** the site's own hexagon, because P3 found no effect in ring 1.
- **Sensitivity:** 3GPP service areas from ADR-003.
  - **Rural macro:** radius 866 m, so it also covers parts of neighbouring hexagons.
  - **Fractions:** computed from H3 resolution-10 children inside the radius.
  - **Overlaps:** count once (maximal covering).

### θ (lift rates)

**θ_new:**

- Germany, France and the US: their own cautious P3 value.
- The other four countries: a range from **0 to 0.121**, central = the event-weighted mean of the three, **0.058**.
- Within a country θ_new scales every new-site candidate equally, so the *choice* of new sites does not depend on it; only the totals do.

**θ_cap:** estimated now, before any plan, with the identical P3 crossing method.

- **Pass rule:** amendment 3's checks (pre-period average, within bands, fixed-broadband control).
- **If it fails or is not estimable:** central θ_cap = 0, with a sensitivity of θ_cap = θ_new.

### θ_cap result (2026-10-14, before any plan; `data/outputs/p4_capacity_crossing.json`)

Percentage points of slow hexagons lifted above 25 Mbps after added capacity, using P3 amendment 3's checks:

| Country | As pre-set | Fixed-broadband control | Checks | θ_cap used (cautious value; 0 if failed) |
|---|---|---|---|---|
| IDN | +23.1 | +28.0 (+9.8 to +44.6) | fail | 0 |
| MYS | +10.1 | — | pass | 0.038 |
| PHL | +19.8 | +25.0 (-13.3 to +47.2) | pass | 0.163 |
| DEU | +11.2 | -1.1 (-4.7 to +2.2) | pass | 0.077 |
| FRA | +14.6 | +4.5 (-0.3 to +8.5) | pass | 0.079 |
| USA | +11.8 | +8.6 (+5.4 to +11.3) | fail | 0 |
| ARE | — | — | fail | 0 |

- **Reading:** added capacity lifts slow places about as much as a new site, at 0.30 of the cost.
- **Failed in Indonesia and the US:** home broadband also rose, an area-wide change, so θ_cap = 0 there in the central plan, with θ_cap = θ_new as a sensitivity.
- **UAE:** too few events, so 0 in the central plan.

### Optimiser

**Objective:** maximise expected people lifted subject to Σ cost ≤ budget B.

- **Central (ring 0 only):** a 0/1 knapsack. Solved exactly with HiGHS (`scipy.optimize.milp`) on the top 20,000 candidates by benefit ÷ cost, and compared with greedy.
- **3GPP sensitivity:** budgeted maximal covering. Greedy has a guaranteed (1 − 1/e) ≈ 63% of the optimum (Khuller et al. 1999). An exact HiGHS solution is computed on districts small enough to solve, to measure greedy's real gap.
- **Budgets:** 100, 500, 1,000 and 5,000 new-tower equivalents per country. Headline: 1,000, or all candidates for the UAE.

### Baselines

1. **KPI ranking** (the gate's baseline, as many plans are built): equal-weight z-scores of
   - −(typical log speed),
   - log population,
   - log places,

   computed over populated hexagons. Candidates are ranked by score and picked until the budget is spent.
2. **Slowest first:** lowest typical speed first. Reported only.

### Gate (ADR-002 P4)

- **Pass:** at the headline budget, the optimiser lifts **≥ 10% more** expected people than KPI ranking. The 10% is our own practical threshold (see ADR-002); the actual gain is always reported.
  - Judged per country, at central θ and central costs.
  - The gate passes if it holds in at least 5 of the 7 countries.
- **Exports pass format checks:**
  - CSV matches its schema;
  - GeoJSON is valid RFC 7946 (closed rings, lon/lat order);
  - KML parses as XML with one Placemark per site.

### Reported (practitioner units, R9, R17)

- people lifted and cost per person lifted, with the θ range;
- the cost–benefit curve over budgets;
- intervention mix (new macro, small cell, capacity);
- top districts;
- how the plan changes across θ, cost ranges and service areas: overlap of chosen hexagons (Jaccard).

### Outputs

- `data/outputs/p4_site_plan.json`: summary, gate, sensitivities.
- `docs/data/plans/<ISO>.csv` / `.geojson` / `.kml`: the headline plan's site list.
  - Columns: rank, h3, lat, lon, district, area type, intervention, cost, cumulative cost, people, P(below 25), typical or predicted speed, expected people lifted (central, low, high).
- Exports are public under CC BY-NC-SA (derived from Ookla).

## SOTA comparison

| Family | Method | Tested | Cited, not tested (why) |
|---|---|---|---|
| Facility location | Maximal covering (Church & ReVelle 1974); its budgeted form | Yes | — |
| Exact solution | Mixed-integer programming (HiGHS) | Yes | — |
| Approximation | Greedy for budgeted maximum coverage (Khuller et al. 1999) | Yes (vs exact) | — |
| Ranking | Equal-weight KPI score | Yes (gate baseline) | Weighted scores agreed in meetings: unreproducible by design |
| Learned placement | Graph neural networks, reinforcement learning for site selection | No | Need ground-truth outcomes per plan; our objective is explicit and small enough to solve exactly |
| Radio planning | Propagation-model coverage (ray tracing) | No | Needs private antenna and clutter data (ADR-003) |

## Evidence (OpenAlex, retrieved 2026-10-14)

| Reference | Venue | Peer-reviewed | Year | Citations | Used for |
|---|---|---|---|---|---|
| The maximal covering location problem | Papers of the Regional Science Association | yes | 1974 | 2,711 | Model |
| The budgeted maximum coverage problem | Information Processing Letters | yes | 1999 | 982 | Greedy guarantee |
| Parallelizing the dual revised simplex method (HiGHS) | Mathematical Programming Computation | yes | 2017 (2018) | 427 | Exact solver |

## Falsification

| Result | Diagnosis | Next action |
|---|---|---|
| Optimiser ≈ KPI ranking | KPI scores already track people × chance of slow | Report: the simple ranking is good enough |
| Plan changes a lot across θ or costs | Choice is sensitive to unmeasured inputs | Report the stable core (hexagons chosen in every scenario) |
| Greedy far below exact | Overlaps matter | Use exact solutions where feasible |
| θ_cap clearly > 0 | Capacity lifts slow places too | Capacity enters the central plan at its cost |

## Results (2026-10-14; `data/outputs/p4_site_plan.json`, exports in `docs/data/plans/`)

**Headline budget, 1,000 new-tower equivalents** (UAE: all 29 likely-slow candidates, budget 29.3):

| Country | Plan: people lifted (range over θ) | KPI ranking | Gain | Gain if capacity = new site | Per 1,000 lifted | Mix |
|---|---|---|---|---|---|---|
| Philippines | 388,941 (0–775,156) | 127,114 | +206% | +142% | 2.6 | 2,020 capacity, 410 small cells, 189 macro |
| Indonesia | 197,111 (0–407,924) | 22,509 | +776% | +741% | 5.1 | 1,142 small cells, 429 macro |
| Germany | 110,687 (6,173–216,327) | 71,105 | +56% | +45% | 9.0 | 3,305 capacity, 12 new sites |
| France | 41,912 (1,305–107,517) | 23,407 | +79% | +89% | 23.9 | 2,805 capacity, 164 new sites |
| Malaysia | 15,942 (0–37,956) | 3,367 | +374% | +375% | 62.7 | 956 macro, 145 capacity |
| United States | 4,861 (0–63,607) | 1,715 | +183% | +90% | 205.7 | 857 macro, 286 small cells |
| UAE | 539 (0–1,115) | 0 | n/a (KPI lifts nobody) | — | 53.8 | 29 macro |

**Gate.** At least +10% in 6 of 7 countries (needed 5). All exports valid: CSV schema, GeoJSON closed rings in lon/lat, KML one Placemark per site. **Passed.**

**Solver checks:**

- Greedy reaches 99.99–100% of the exact knapsack.
- On district subproblems with 3GPP service areas, greedy covering reaches 97.9–100% of the exact covering.

**Stability** (Jaccard overlap with the central plan):

| Change | Overlap |
|---|---|
| High θ | 0.57–0.96 |
| Co-location cost 0.20 or 0.50 | 0.55–1.00 |
| 3GPP service areas | 0.55–0.99 |
| Capacity = new site | 0.07 (US) to 0.97 (Germany) |

- At low θ (= 0) every plan lifts nobody, so overlap at that end is not meaningful.

**Reading:**

- Ranking by an equal-weight KPI score favours busy commercial hexagons, which are mostly fast. Counting expected people lifted per cost wins everywhere, by +56% to +776%.
- The same budget lifts about 80× more people in the Philippines than in the US.
- The plans are most sensitive to whether added capacity really lifts slow places, in the US and the Philippines.

## Consequences

- **Positive:** a reproducible, costed site list in planners' formats, with every assumption a range.
- **Negative:**
  - Benefits rest on crowdsourced effects with wide intervals.
  - Southeast Asia borrows θ from three countries.
  - The plan says where to look (0.74 km² search areas), not where to build.
  - All three are stated on the page.

## Related Decisions

- ADR-002 (P4 gate)
- ADR-003 (costs, radii, exports)
- ADR-004 and ADR-005 (speed inputs)
- ADR-007 (lift rates)
