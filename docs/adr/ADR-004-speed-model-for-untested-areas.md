# ADR-004: Speed Model for Untested Areas (P2)

**Status:** Accepted — written and pushed before any P2 model was trained; **gate failed, kriging deployed** (results below)
**Date:** 2026-10-13
**Deciders:** Sabrina Pribadi

---

## Context and Problem Statement

P1 found that **349M people (39%)** live in populated hexagons with no mobile speed test in 2026 Q3. Most of them are rural, where measured slow shares are highest.

Without a prediction for these hexagons:

- the experience gap is understated;
- P4 cannot choose sites where nobody has tested.

**How far untested people are from a test.** Measured before any model on up to 20,000 untested hexagons per country, people-weighted, by ring distance (rings of H3 resolution-8 hexagons, ~0.9 km each):

| Country | Next ring (~0.9 km) | Within 3 rings | 90th percentile |
|---|---|---|---|
| Indonesia | 63% | 86% | ring 5 |
| Philippines | 46% | 76% | ring 7 |
| Malaysia | 67% | 86% | ring 5 |
| Germany | 69% | 94% | ring 3 |
| France | 52% | 83% | ring 4 |
| United States | 67% | 87% | ring 4 |
| UAE | 52% | 79% | ring 6 |

The task is mostly short-range interpolation, with a tail of remote areas.

The question: **"What is the mobile download speed, with uncertainty, in every populated hexagon nobody tested — and where can that prediction be trusted?"**

## Decision Drivers

- **Error that matches use.** Cross-validation must create the same test-to-training distances as real prediction. Random splits flatter spatial models (Ploton et al. 2020); very large blocks punish them (Wadoux et al. 2021).
- **A simple, strong baseline.** Kriging is the standard spatial interpolator. A machine-learning model must beat it clearly or not be used (gate in ADR-002).
- **Uncertainty per hexagon.** P4 needs the probability that a hexagon is below 10 or 25 Mbps, not only a point estimate.
- **No leakage.** No feature may use the target of a held-out hexagon.
- **R15.** About 647k measured hexagons and 6.4M populated hexagons. This fits the 8 GB machine with LightGBM; Spark is not needed for P2. The quarterly Databricks job (P6) re-runs it.

## Considered Options

### Validation design (chosen before training, from geometry only)

Five folds. The test-to-training ring distance was compared with the deployment distance (above), using the 1-D Wasserstein distance in rings, averaged over the seven countries (the kNNDM principle; Linnenbrink et al. 2024).

| Design | Distance to deployment | Test hexagons next to training data | Status |
|---|---|---|---|
| Random hexagons | 1.24 | 92–98% | Head-to-head only (shows the optimism) |
| H3 resolution-8 blocks | 1.23 | 92–98% | Rejected (same as random) |
| H3 resolution-7 blocks (~5 km²) | 0.95 | 68–77% | Sensitivity |
| **H3 resolution-6 blocks (~36 km²)** | **0.82** | 32–39% | **Chosen for the gate** |
| H3 resolution-5 blocks (~250 km²) | 2.17 | 13–25% | Sensitivity (pessimistic) |

**Distance-matched error.** Cross-validation errors are also re-weighted by ring distance (1, 2, 3, 4–6, 7+) to the deployment distribution. It is reported next to the plain block-CV error.

### Model

| Option | Status | Why |
|---|---|---|
| Ordinary kriging, local (moving search neighbourhood of 16, 32 or 64 nearest training hexagons, as gstat's `nmax`; Pebesma 2004), per-country variogram (exponential or spherical, whichever fits better by Cressie's 1985 weighted least squares) | **Baseline (gate)** | Standard geostatistical interpolator (Cressie 1993). The gate uses the **best** of the three neighbourhoods, the setting most favourable to the baseline |
| Mean of ring-1 training neighbours | Naive baseline | Shows what a "look next door" rule gets |
| LightGBM on covariates only (population, places, cells, fixed broadband, area type) | Ablation | Shows what context alone explains |
| **LightGBM with spatial features** (covariates + neighbours' measured speeds by ring + nearest observation + the hexagon's own earlier quarters) | **Chosen** | The random-forest spatial approach (Hengl et al. 2018; Sekulić et al. 2020), with gradient boosting (Ke et al. 2017) |
| Graph neural networks or learned location encoders | Cited, not tested | Candidates only if LightGBM fails the gate (recorded in ADR-002) |

### Features (each available for an untested hexagon at prediction time)

| Group | Features | Leakage guard |
|---|---|---|
| People and places | ln population; ln population within ring 2; ln places in the hexagon and ring 2; area type (Degree of Urbanisation) | Not target-derived |
| Cells | LTE/5G records within ring 1; 5G records within ring 1; ring distance to the nearest recorded cell (capped at 10) | Not target-derived |
| Fixed broadband | ln fixed download in the hexagon and ring 1; fixed tests | A different measurement (home Wi-Fi), same quarter |
| Neighbours' mobile speed | mean ln speed of **training** hexagons in ring 1, 2 and 3; their counts; ring distance and value of the nearest training hexagon | Computed per fold from training hexagons only |
| History | the hexagon's last measured ln speed in 2023 Q1 – 2026 Q2, and quarters since | Past quarters only |
| Country | categorical | Dropped in leave-one-country-out |

### Uncertainty

- **Predictive distribution:** Normal on log speed. σ comes from the cross-validation residuals in the same ring-distance class and country.
- **P(below 10 / 25 Mbps):** read from that distribution.
- **Calibration check:** the share of held-out hexagons inside the 80% interval, per ring-distance class.

### Area of applicability

- **Method:** dissimilarity index on standardised, importance-weighted covariates (Meyer & Pebesma 2021). The threshold comes from cross-validation.
- **Reported:** the share of untested people inside the area. Predictions outside it are flagged on the map.

## Decision Outcome (pre-registered)

**Gate (ADR-002):**

- **Pass:** LightGBM with spatial features has RMSE of ln download ≤ **0.90 ×** the best ordinary-kriging RMSE (16, 32 or 64 neighbours), on the same resolution-6 block folds, pooled over the seven countries. LightGBM hyperparameters are fixed in advance (no tuning on the test folds).
- **Fail:** keep kriging and report the negative result.

**Reported, not gated:**

- RMSE per country;
- people-weighted RMSE;
- distance-matched RMSE;
- RMSE under resolution-7 and resolution-5 blocks and random splits;
- leave-one-country-out RMSE;
- AUC and Brier score for "below 25 Mbps";
- 80% interval coverage;
- share of untested people inside the area of applicability;
- the ablation table.

**Also reported:** an ADR-003 follow-up. In the city areas where gaps were typed, test whether the upload/download ratio and latency, which come from Ookla alone, separate coverage gaps from capacity gaps (block-CV AUC).

**Then:**

- predict every untested populated hexagon, with its probability of being below 10 and 25 Mbps;
- update the experience-gap totals ("measured + predicted") with intervals;
- feed P4.

## SOTA comparison

| Family | Method | Tested head-to-head | Cited, not tested (why) |
|---|---|---|---|
| Geostatistics | Ordinary kriging | Yes (gate baseline) | Regression-kriging: LightGBM with neighbour features plays the same role |
| Tree ensembles with spatial features | LightGBM with neighbour and nearest-observation features | Yes (chosen) | Random forest versions (RFsp, RFSI): same idea; gradient boosting is faster on 647k rows |
| Covariates only | LightGBM without spatial features | Yes (ablation) | — |
| Deep spatial models | GNNs, positional encoders (e.g. PE-GNN, 2021 preprint) | No | Heavier, no clear evidence of gains at this scale; only if the gate fails |
| Validation | Spatial block CV, sized by distance matching (kNNDM) | Yes (vs random, smaller and larger blocks) | Full kNNDM fold search: block size chosen by the same criterion instead |

## Evidence (OpenAlex, retrieved 2026-10-13)

| Reference | Venue | Peer-reviewed | Year | Citations | Used for |
|---|---|---|---|---|---|
| Random forest as a generic framework for predictive modeling of spatial and spatio-temporal variables | PeerJ | yes | 2018 | 1,094 | Spatial features in tree models |
| Random Forest Spatial Interpolation | Remote Sensing | yes | 2020 | 366 | Nearest-observation features |
| LightGBM: A Highly Efficient Gradient Boosting Decision Tree | NeurIPS | yes | 2017 | 9,120 | Model |
| kNNDM CV: k-fold nearest-neighbour distance matching cross-validation | Geoscientific Model Development | yes | 2024 | 49 | Block size by distance matching |
| Nearest neighbour distance matching Leave-One-Out Cross-Validation for map validation | Methods in Ecology and Evolution | yes | 2022 | 111 | Distance-matched error |
| Positional Encoder Graph Neural Networks for Geographic Data | arXiv 2111.10144 | no (preprint) | 2021 | 6 | Cited alternative |

| Multivariable geostatistics in S: the gstat package | Computers & Geosciences | yes | 2004 | 3,001 | Local kriging neighbourhood |
| Fitting variogram models by weighted least squares | Mathematical Geology | yes | 1985 | 1,058 | Variogram fitting |

Plus the P2 references already in ADR-002: Roberts et al. 2017, Ploton et al. 2020, Wadoux et al. 2021, Meyer & Pebesma 2021. Book without a count: Cressie (1993), *Statistics for Spatial Data*.

## Falsification

| Result | Diagnosis | Next action |
|---|---|---|
| LightGBM within 10% of kriging | Neighbours' speeds carry almost all the signal | Keep kriging (gate); report |
| Random-split RMSE far below block RMSE | Spatial leakage in random splits | Report both; only blocks count |
| Leave-one-country-out error much higher | Countries differ (operators, spectrum) | Use within-country models; restrict claims |
| 80% intervals cover far less than 80% | σ underestimated far from tests | Widen by ring-distance class; flag outside the area of applicability |
| Predicted untested areas mostly fast | Untested ≠ slow | Report: the gap is smaller than feared |

## Results (2026-10-13; `data/outputs/p2_speed_model.json`)

**Gate design (resolution-6 blocks), RMSE of ln download:**

| Model | RMSE | Typical miss |
|---|---|---|
| Ring-1 neighbour mean | 1.687 | 5.4× |
| Kriging (best: 64 neighbours) | 1.335 | 3.8× |
| LightGBM, covariates only | 1.306 | 3.7× |
| LightGBM with spatial features | 1.241 | 3.5× |

- **Ratio 0.929 > 0.90: the gate fails** and kriging is the deployed model.
- **Other designs:** resolution 7 = 0.933, resolution 5 = 0.922, random hexagons = 0.935.
- **Distance-matched RMSE:** kriging 1.240, LightGBM 1.157. **People-weighted RMSE:** 1.018 and 0.940.
- **Uncertainty:**
  - 80% intervals cover 84%;
  - AUC for "below 25 Mbps" = 0.76;
  - 95% of untested people are inside the area of applicability.
- **Leave-one-country-out:** error rises 3–13% against within-country CV (UAE most).
- **ADR-003 follow-up:** upload/download ratio and latency do not separate coverage from capacity gaps (AUC 0.51).

**Why the margin is small, and what happened next (ADR-005, post-hoc):**

- Two tiles in the same hexagon differ by SD 1.15 on the log scale, so test noise dominates the error.
- **On well-tested hexagons (≥ 10 tests):** kriging 0.807, LightGBM 0.659, ratio 0.82.
- **Against the noise-free typical speed:** 0.689 and 0.481.
- This is a diagnostic only. The pre-registered gate stays failed.
- **LightGBM version 2:** a gate scored on well-tested hexagons must be pre-registered and tested on a fresh quarter (2026 Q4) before LightGBM can replace kriging.

**Note on outputs:**

- `p2_speed_model.json` → `untested_totals` comes from the LightGBM deployment path that ran before the gate decision. It is **not used**.
- Deployed predictions (kriging) and their totals are in `data/outputs/p2b_noise_followup.json` and `derived/hex_p2.parquet`.

## Consequences

- **Positive:** every populated hexagon gets a speed estimate with an honest uncertainty, and the gap totals stop ignoring 39% of people.
- **Negative:** predictions inherit the test-taker bias of the training data. They describe tested-like conditions, which is stated on the page.

## Related Decisions

- ADR-001 (unit and metric)
- ADR-002 (P2 gate; validation principles)
- ADR-003 (gap types; the upload/download follow-up)
