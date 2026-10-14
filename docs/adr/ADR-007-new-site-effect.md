# ADR-007: Did New Sites Raise Speeds Nearby? (P3)

**Status:** Accepted — pre-registered before any outcome; amendments 1–2 logged before their runs; results below
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

## Amendment 2 (2026-10-14, after the first results; before these runs)

**1. Imputation arm, bug fix.** `pyfixest.did2s` failed in every country (an array-shape error after it drops single-observation hexagons). The arm is re-implemented directly, which is the Borusyak et al. estimator by definition:

- fit hexagon + country × area-type × quarter effects on observations not yet affected (event time < −1, or never treated);
- predict treated hexagons' counterfactual;
- average the gaps by event time.

The interval is a block bootstrap of the treated gaps, holding the first stage fixed (slightly narrow).

**2. Post-hoc diagnostics (labelled as such; not gates).** Prompted by negative mobile effects (Philippines, France) and failed fixed-broadband controls (France, US):

- **Test volume:** the same event study with ln(number of tests) as the outcome. Did more people start testing when new cells appeared?
- **Mobile minus fixed:** the same event study on ln(mobile) − ln(fixed) in hexagons with both. This removes changes that hit both networks, such as who lives there or who tests.

## Amendment 3 (2026-10-14, before these runs): is the crossing measure inflated by regression to the mean?

**Problem.** "Slow" is defined by one base quarter (g − 2). Hexagons that look slow in one noisy quarter (ADR-005) tend to bounce back anyway. Comparison places bounce back too, but by a different amount if their speeds below 25 Mbps differ. Also, the home-broadband control was never run for the crossing measure.

**Checks (all reported; P4 uses the most conservative estimate that passes):**

1. **Slow by pre-period average.** A hexagon is slow if its mean ln speed over the available quarters g − 5 … g − 2 is below ln 25. Effect = change in the share above 25 Mbps, same estimator.
2. **Within speed bands.** Base-quarter bands (< 10 and 10–25 Mbps) are estimated separately, then combined with treated-count weights. Treated and comparison places then start from similar speeds.
3. **Home-broadband control.** The same crossing measure, on fixed broadband. Expected ≈ 0.

**Pass rule for P4's input:** for a country, checks 1 and 2 have the same sign as the original and check 3's interval includes 0.

### Amendment 3: results and timing (2026-10-14)

**Timing (disclosed).** The amendment text and script were written before the run, but git was blocked by OneDrive downloads, so the push came after the results:

| File | Last written |
|---|---|
| ADR-007 (this amendment) | 08:44:41 |
| `scripts/new_site_crossing_checks.py` | 08:45:15 |
| `data/outputs/p3c_crossing_checks.json` (results) | 08:49:55 |

**Results** (percentage points of slow hexagons lifted above 25 Mbps):

| Country | As pre-set | Slow by year average | Within speed bands | Fixed-broadband control | Pass | P4 value (most cautious passing) |
|---|---|---|---|---|---|---|
| France | +12.1 (+3.0 to +21.6) | +17.9 (−0.2 to +36.0) | +12.7 (−2.7 to +28.3) | +4.5 (−1.5 to +10.4) | yes | **+12.1** |
| Germany | +12.6 (+5.6 to +19.4) | +5.2 (−17.3 to +27.6) | +16.5 (+3.1 to +27.0) | +2.8 (−6.0 to +9.9) | yes | **+5.2** |
| United States | +9.6 (+4.8 to +14.7) | +1.5 (−16.0 to +19.8) | +10.9 (+3.1 to +18.1) | +4.6 (−1.2 to +10.7) | yes | **+1.5** |
| Philippines | +5.8 | −9.4 | +8.1 | — | no (sign flips) | — |
| Indonesia | +1.4 | +2.1 | −1.8 | +7.6 | no | — |

- **Year-average intervals** are conservative (treated-count-weighted averages of per-group intervals).
- **Reading:** part of the pre-set effect was regression to the mean in Germany and the US; France holds.
- **P4:** uses this range (0 to about +12 points). Southeast Asia has no reliable estimate of its own.

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

## Results (2026-10-14; `data/outputs/p3_new_site_effect.json`, `p3b_diagnostics.json`)

**Per country (new sites):**

| Country | New sites | Pre-trends | Home-broadband control | Average speed, ring 0: Callaway–Sant'Anna / imputation / mobile − fixed | Slow places (< 25 Mbps) lifted above 25 | Verdict |
|---|---|---|---|---|---|---|
| United States | 7,001 | pass (p 0.82) | **changed** (−6%) | +6.8% / **+10.0%** / **+12.5%** | +9.6 pts (crossing pre-trend fails) | Clearest average gain. Claims restricted by the control; the mobile − fixed check is positive |
| Germany | 2,219 | pass (p 0.25) | unchanged | +7.1% / −2.5% / +2.6% (all intervals include 0) | **+12.6 pts** (+5.6 to +19.4) | Causal: lifts slow places; average ≈ 0 |
| France | 5,092 | pass (p 0.16) | **changed** (−14%) | −8.0% / −2.0% / −3.7% (all include 0) | **+12.1 pts** (+3.0 to +21.6) | Restricted (control failed) |
| Philippines | 173 | pass (p 0.44) | unchanged | −12.5% / −5.5% / −11.0% (only the first excludes 0) | +5.8 pts (−8.3 to +19.1) | Causal design; the average effect is not robust |
| Indonesia | 339 | **fail** (p 0.036) | unchanged | −3.0% / −7.0% / −5.8% | +1.4 pts (−9.3 to +11.2) | Association only: speeds fell 12% in the year *before* sites (placebo) |
| UAE | 116 | **fail** | unchanged | intervals span about −58% to +82% | — | Uninformative |
| Malaysia | 21 | — | — | — | — | Too few new sites (added capacity: −20%, its pre-trends fail) |

**Other estimands:**

- **Ring 1:** ≈ 0 everywhere; no spill-over beyond the site's own hexagon.
- **Added capacity:** ≈ 0 where pre-trends pass.
- **Test volume (post-hoc):** no change in any country (e.g. US +0.8%). The change in who tests is not "more testers".

**For P4:**

- The usable effect is the **crossing rate** for slow places: about +10 to +13 points in Germany and France, intervals +3 to +22.
- Southeast Asia's own estimates are wide and centred lower (+1 to +6 points). P4 uses a range from 0 to the Germany/France level there and reports how the plan changes across that range.

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
