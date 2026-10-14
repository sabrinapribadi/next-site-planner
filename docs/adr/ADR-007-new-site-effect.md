# ADR-007: Did New Sites Raise Speeds Nearby? (P3)

**Status:** Proposed — written and pushed before any P3 outcome was computed; Amendment 1 extends it to all seven countries
**Date:** 2026-10-14
**Deciders:** Sabrina Pribadi

---

## Context and Problem Statement

- **What P4 needs:** what a new site actually does to the speeds people get. "Sites near high speeds" proves nothing, because sites are built where demand already is.
- **Public data:** two sources make a before/after comparison possible.
  - **OpenCelliD** records when each cell was first seen.
  - **Ookla** gives 15 quarters of speed (2023 Q1 – 2026 Q3).
- **Counted before any outcome** (locations and dates only). LTE/5G cells first seen 2023 Q3 – 2024 Q4 and still seen ≥ 180 days later:

| | Germany | United States |
|---|---|---|
| Hexagons with such a cell | 18,028 | 31,238 |
| **New site:** no cell of any kind within ring-1 (~1.3 km) before | 2,219 | 7,001 |
| **Added capacity:** cells already nearby | 15,809 | 24,237 |

The question: **"When a new site or new capacity appears, how much does mobile download speed change in that hexagon and the ring around it, compared with similar places that have not yet received one?"**

In plain words: compare speeds before and after a new site, and subtract the change that happened anyway in comparable places. That is difference-in-differences.

## Amendment 1 (2026-10-14, before running any country other than Germany and the US)

**Principle (user decision):** treat all countries the same, with one method and no country-specific data sources.

- The analysis covers **all seven countries** with the identical event rule.
- Counts under that rule, from locations and dates only:

| Country | New-site hexagons | Added-capacity hexagons |
|---|---|---|
| France | 5,092 | 19,282 |
| United States | 7,001 | 24,237 |
| Germany | 2,219 | 15,809 |
| Indonesia | 339 | 217 |
| Philippines | 173 | 699 |
| UAE | 116 | 547 |
| Malaysia | 21 | 892 |

- **Minimum:** an estimate is reported where an estimand has at least 100 event hexagons; otherwise it says "too few events" (Malaysia's new sites).
- **Gate:** applied per country.
- **Transfer:** where a country's own estimate exists, P4 uses it instead of transferring another country's effect.
- **Disclosure:** Germany's new-site, ring-0 result had already been seen (+7%, interval −7% to +22%; pre-trends pass) when this amendment was written. The design is unchanged for every country, so seeing it cannot bias the others.

## Decision Drivers

- **Staggered timing:**
  - Sites arrive in different quarters.
  - Classic two-way fixed-effects regressions are biased then: early sites are compared with late ones, already changed (Goodman-Bacon 2021).
  - Modern estimators avoid this.
- **Dating is noisy:**
  - "First seen" lags the real launch by weeks or months.
  - Allow one quarter of anticipation, and measure from two quarters before first sighting.
- **Selection:**
  - Sites go where speeds are worsening or demand is rising.
  - A pre-trend test must show treated and comparison places moved in parallel before.
- **Noisy outcomes:** ADR-005. Noise widens intervals but does not bias a difference-in-differences. Raw hexagon speeds are used, because shrinkage would borrow from treated neighbours.
- **R15:** a few million hexagon-quarters, two countries. This runs locally; Spark is not needed.

## Decision (pre-registered)

### Data

| Element | Definition |
|---|---|
| Unit | H3 r8 hexagon × quarter, 2023 Q1 – 2026 Q3 (unbalanced: a hexagon counts in quarters it was tested) |
| Outcome | ln(mobile download, Mbps) of the hexagon |
| Event | Hexagon containing a reliable new LTE/5G cell, as counted above. The first such quarter is its event quarter g |
| Type | New site, or added capacity (definitions above) |
| Rings | Effect in the event hexagon (ring 0) and, separately, its ring-1 neighbours |
| Comparison places | Same country and same area type (Degree of Urbanisation). Either not yet treated (event later in the window) or never treated (no new cell of any kind within ring 3 through 2026 Q3) |
| Base period | g − 2 (one quarter of anticipation allowed) |

### Estimators

| Role | Estimator | Notes |
|---|---|---|
| **Chosen** | Callaway & Sant'Anna (2021): group-time effects, each a 2×2 difference-in-differences against comparison places, aggregated to event time with group-size weights | Unconditional within country × area type strata, weighted by treated counts |
| Head-to-head | Borusyak, Jaravel & Spiess (2024) imputation (two-stage form; `pyfixest.did2s`) | Hexagon and country × area-type × quarter fixed effects. Never-treated hexagons are sampled (seeded) up to 20× the treated count, at most 50,000, to fit in memory; the chosen estimator uses all units |
| Shown only to illustrate bias | Two-way fixed-effects event study | Expected to differ when effects vary over time |

**Inference:** cluster bootstrap over H3 resolution-5 blocks (~250 km²; nearby hexagons are correlated), 499 replicates, 95% percentile intervals.

### Gate (ADR-002 P3, made precise here)

Germany and the US are judged separately, for new sites, ring 0.

1. **Parallel pre-trends:** every pre-period estimate (event time −5 to −3) has a 95% interval that includes 0, **and** a joint test of all three gives p > 0.05.
2. **Effect reported:** average effect over event time 0 to +4, with its 95% interval. It is also shown as a percentage change, (e^β − 1).

- **Pass:** the effect is reported as causal for that country.
- **Fail:** it is reported as an association only, and P4 uses a range that includes zero.

### Falsification checks (reported, not gated)

| Check | Expected if the design is sound |
|---|---|
| Negative-control outcome: fixed (home) broadband speed in the same hexagons | Effect ≈ 0 (interval includes 0) |
| Placebo timing: pretend each event happened 4 quarters earlier, using pre-event data only | Effect ≈ 0 |
| Only hexagons with ≥ 5 tests in both periods | Same sign; similar size |
| Ring 1 vs ring 0 | Smaller effect further away |
| Imputation vs Callaway–Sant'Anna | Similar estimates |

### Reported for practitioners (R9, R17)

- Effect in % download speed for a new site and for added capacity, by area type. Example of the plain reading: "+18% means a 20 Mbps place typically reaches about 23.6 Mbps".
- **Share of event hexagons that crossed 25 Mbps** after a new site vs comparison places: the input P4 needs.
- **Transfer to Indonesia:** an assumption, stated. P4 uses the range across Germany, the US and the area types.

## SOTA comparison

| Family | Method | Tested | Cited, not tested (why) |
|---|---|---|---|
| Staggered DiD | Callaway & Sant'Anna (2021) | Yes (chosen) | — |
| Imputation | Borusyak, Jaravel & Spiess (2024) | Yes (head-to-head) | — |
| Interaction-weighted event study | Sun & Abraham (2021) | No | Same target as Callaway–Sant'Anna with not-yet-treated controls; one of the two is enough |
| Heterogeneity-robust DiD | de Chaisemartin & D'Haultfœuille (2020) | No | Designed for on/off treatments; ours is absorbing |
| Synthetic DiD | Arkhangelsky et al. (2021) | No | Needs a balanced panel; Ookla hexagons come and go |
| Two-way fixed effects | Event-study regression | Shown | Biased with staggered timing (Goodman-Bacon 2021); shown to make the point |

## Evidence (OpenAlex, retrieved 2026-10-14)

| Reference | Venue | Peer-reviewed | Year | Citations | Used for |
|---|---|---|---|---|---|
| Difference-in-Differences with multiple time periods | Journal of Econometrics | yes | 2020 (vol. 225, 2021) | 8,823 | Chosen estimator |
| Revisiting Event-Study Designs: Robust and Efficient Estimation | Review of Economic Studies | yes | 2024 | 2,124 | Imputation arm |
| Difference-in-differences with variation in treatment timing | Journal of Econometrics | yes | 2021 | 7,832 | Why two-way fixed effects is biased |
| Estimating dynamic treatment effects in event studies with heterogeneous treatment effects | Journal of Econometrics | yes | 2020 (vol. 225, 2021) | 5,457 | Cited alternative |
| Two-Way Fixed Effects Estimators with Heterogeneous Treatment Effects | American Economic Review | yes | 2020 | 4,948 | Cited alternative |
| Synthetic Difference-in-Differences | American Economic Review | yes | 2021 | 1,482 | Cited alternative |

## Falsification

| Result | Diagnosis | Next action |
|---|---|---|
| Pre-trends fail | Sites follow worsening or improving speeds | No causal claim; report association; P4 range includes 0 |
| Fixed broadband also "improves" | Area-wide change (e.g. fibre roll-out), not the site | Report; restrict claims |
| Effect ≈ 0 | Sites added where capacity was not binding, or dating too noisy | Report; P4 uses small effects |
| Germany and the US differ a lot | Market differences (spectrum, density) | Report separately; Indonesia's range spans both |

## Consequences

- **Positive:** P4's "people lifted" comes from measured effects of real sites, with an honest range.
- **Negative:**
  - OpenCelliD positions and dates are crowdsourced.
  - "New site" means "first cell seen nearby", not a confirmed tower build.
  - Both are stated on the page.

## Related Decisions

- ADR-002 (P3 gate)
- ADR-003 (interventions: new site vs co-location/capacity)
- ADR-005 (noise)
