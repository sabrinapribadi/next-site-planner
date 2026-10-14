# ADR-008: Budgeted Site Plan — Where the Next Sites Should Go (P4)

**Status:** Proposed — written and pushed before any P4 plan is computed
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

- **Pass:** at the headline budget, the optimiser lifts **≥ 10% more** expected people than KPI ranking.
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
