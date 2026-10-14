# ADR-005: Measurement Noise — Small-Area Shrinkage and Noise-Aware Scoring

**Status:** Accepted (post-hoc follow-up; results in §7 and below). Written after the P2 gate failed and pushed before any of these analyses ran. Nothing here changes a pre-registered result: the P1 shares and the failed P2 gate stand as reported.
**Date:** 2026-10-13
**Deciders:** Sabrina Pribadi

---

## Context and Problem Statement

**What P2 showed.** On resolution-6 block CV, LightGBM had an RMSE of 1.241 (ln download) and the best kriging 1.335. The ratio of 0.929 failed the gate (≤ 0.90). Both errors are large: a factor of about 3.5 on speed.

**Diagnosis, from the 2026 Q3 mobile tiles:**

| Fact | Value |
|---|---|
| Tiles with 1–2 tests | 64% |
| Tiles per measured hexagon (median) | 1 |
| SD of ln speed between two tiles **in the same 0.74 km² hexagon** | 1.15 |
| SD of ln speed across hexagons | 1.49 |

**What follows:**

- A hexagon's "measured" speed is a very small sample of its typical experience (device, plan, operator, time of day, indoor or outdoor). No model scored against such targets can reach an RMSE much below ~1.15.
- **For P2,** the gate compared models mostly on noise.
- **For P1,** noise spreads hexagon speeds out. Many more hexagons sit just above a speed bar than just below it, so noise pushes more of them below than above, and the shares below 10 and 25 Mbps are probably **overstated**. This is the same mechanism that biased the tile bootstrap (ADR-002 deviation).

The question: **"What is each hexagon's typical speed once test noise is separated from real differences, and how do the P1 shares and P2 model comparisons change?"**

## Decision

### 1. Noise model (per country, from tiles in the same hexagon)

For two tiles i and j in the same hexagon, with n_i and n_j tests:

E[(y_i − y_j)²] = 2·σ²_micro + σ²_test·(1/n_i + 1/n_j)

- **σ²_test:** variance between single tests.
- **σ²_micro:** real variation between tile locations inside a hexagon.
- **Fit:** least squares on all within-hexagon tile pairs.

A hexagon's value is the test-weighted mean of its tiles. Its noise variance is therefore:

v_h = (σ²_test·Σn_i + σ²_micro·Σn_i²) / (Σn_i)²

### 2. Empirical-Bayes shrinkage (Fay & Herriot 1979)

For each measured hexagon:

- **Prior mean μ_h:** leave-one-out local ordinary kriging, using the same variogram and neighbourhood rules as the P2 baseline. The hexagon's own value is excluded.
- **Prior variance σ²_u (per country):** method of moments, mean[(y_h − μ_h)² − v_h], with a floor of 0.01.
- **Posterior:** θ_h ~ Normal(γ_h·y_h + (1 − γ_h)·μ_h, γ_h·v_h), with γ_h = σ²_u / (σ²_u + v_h).
  - A 1-test hexagon moves a lot toward its neighbourhood.
  - A 200-test hexagon barely moves.

### 3. P1, noise-corrected (published next to the raw shares)

- **Share below bar b:** Σ population·P(θ_h < ln b) / Σ population, over measured hexagons.
- **Intervals:** the same spatial block bootstrap as P1 (resolution-5 blocks).
- **Labelling:** the raw P1 shares stay the pre-registered headline until this follow-up is reviewed. The page shows both and says which is which.

### 4. P2, noise-aware scoring (diagnostic; the gate stays failed)

Re-run resolution-6 block CV for the best kriging and LightGBM. Then report:

- **RMSE on well-measured hexagons** (≥ 10 tests), where the target's noise is small;
- **noise-adjusted RMSE,** √(MSE − mean v_h): an estimate of error against the true typical speed;
- **precision-weighted RMSE** (weights 1 / (σ²_u + v_h));
- **a LightGBM variant trained with those weights.**

### 5. Deployment

- **Model:** kriging, because the P2 gate failed (pre-registered consequence). It predicts every untested populated hexagon.
- **Uncertainty:** taken against the true typical speed. σ per (country, ring-distance class) = √(max(CV MSE − mean v_h, 0.01)), from kriging's resolution-6 CV.
- **Outputs:** P(typical speed below 10 / 25 Mbps).

### 6. Check added before it ran (2026-10-13, 22:45): does shrinkage remove noise or signal?

Shrink 2026 Q2 hexagon speeds the same way, then predict the independently measured 2026 Q3 speed of the same hexagons (the Efron–Morris test).

- **Pass:** the shrunk Q2 value has lower error than the raw Q2 value against Q3.
- **Fail:** shrinkage removed signal, and the noise-corrected P1 shares are not published as an estimate.

Q3's own noise is independent of Q2's, so it adds the same amount to both errors and cannot favour either. Script: `scripts/noise_validation.py`.

### 7. Results of the check (2026-10-13)

**Pass (pre-written criterion).** Against the independent Q3 measurement, shrunk Q2 speeds have 28–44% lower squared error than raw Q2 speeds, in all seven countries. They also beat the neighbourhood-only prior. The AUC for spotting Q3's slow hexagons rises from 0.70–0.80 to 0.74–0.83.

**Level diagnostic (added after the pass/fail result).** Add Q3's own noise back to the shrunk Q2 posterior and predict the noisy Q3 share below 25 Mbps:

| Country | Observed | Predicted | Verdict |
|---|---|---|---|
| Malaysia | 4.0% | 4.6% | level credible |
| France | 6.0% | 6.8% | level credible |
| United States | 6.5% | 5.7% | level credible |
| UAE | 2.5% | 1.9% | level credible |
| Germany | 12.1% | 16.2% | overshoots: level provisional |
| Philippines | 12.5% | 18.7% | overshoots: level provisional |
| Indonesia | 10.4% | 19.6% | overshoots: level provisional |

**Use:**

- Shrunk speeds are used per hexagon (maps, district view, P4 inputs).
- Noise-corrected country shares are published beside the raw shares, marked credible or provisional per country.
- The raw P1 shares remain the headline.
- **Likely cause of the overshoot:** the noise model overstates noise where typical speeds sit near 25 Mbps, plus a real speed-up between quarters in Indonesia (raw share 13.8% → 10.4%). The next refinement is a heavier-tailed noise distribution, checked again across quarters.

### 8. P2 noise-aware scores and deployment (`data/outputs/p2b_noise_followup.json`)

**Noise-aware scores (resolution-6 blocks):**

| Score | Kriging | LightGBM | LightGBM, precision-weighted |
|---|---|---|---|
| RMSE, all | 1.335 | 1.241 | 1.241 |
| RMSE on ≥ 10-test hexagons | 0.807 | 0.659 | 0.648 |
| Noise-adjusted RMSE | 0.689 | 0.481 | 0.482 |

**Deployed predictions (kriging):**

- 5.76M untested populated hexagons.
- ≈ 68M people expected below 25 Mbps (typical speed): Philippines 23.4M, Indonesia 30.3M, Germany 5.5M, United States 4.7M, France 3.4M, Malaysia 0.8M, UAE 0.03M. These use Kontur population; with WorldPop the total is 47M (ADR-001, 2026-10-14), so the headline is shown as 47–68M.

## SOTA comparison

| Family | Method | Tested | Cited, not tested (why) |
|---|---|---|---|
| Area-level small-area estimation | Fay–Herriot empirical Bayes with a spatial (kriging) prior | Yes (chosen) | — |
| Spatial hierarchical Bayes | Besag–York–Mollié conditional autoregressive model | No | Needs a full Bayesian fit over 647k areas (INLA/MCMC); the kriging prior plays the spatial role at far lower cost |
| Noise-aware learning | Precision-weighted training | Yes (LightGBM variant) | — |
| More data per hexagon | Pool four quarters | No | Mixes in older speeds while networks upgrade, which adds bias |

## Evidence (OpenAlex, retrieved 2026-10-13)

| Reference | Venue | Peer-reviewed | Year | Citations | Used for |
|---|---|---|---|---|---|
| Estimates of Income for Small Places: An Application of James-Stein Procedures to Census Data | Journal of the American Statistical Association | yes | 1979 | 1,260 | Fay–Herriot shrinkage |
| Small Area Estimation: An Appraisal | Statistical Science | yes | 1994 | 733 | Small-area estimation practice |
| Bayesian image restoration, with two applications in spatial statistics | Annals of the Institute of Statistical Mathematics | yes | 1991 | 4,205 | Cited alternative (BYM) |

## Falsification

| Result | Diagnosis | Next action |
|---|---|---|
| Fitted σ²_test ≈ 0 | Tile differences are real location effects, not noise | Report: shares are not overstated; no correction |
| Corrected shares ≈ raw shares | Noise is symmetric around the bar | Report: raw P1 holds |
| LightGBM's advantage vanishes on well-measured hexagons | The 7% gain came from fitting noise patterns | Report; kriging stays |
| σ²_u at the floor in a country | Neighbourhood explains almost everything | Report; shrinkage is near-total there |

## Consequences

- **Positive:** shares and maps describe typical experience, not lucky or unlucky single tests. Model comparisons separate skill from noise.
- **Negative:**
  - Two sets of P1 numbers exist (raw, pre-registered; noise-corrected, post-hoc). The page must label them clearly.
  - Shrinkage borrows from neighbours, so it smooths very local slow spots.

## Related Decisions

- ADR-001 (headline metric)
- ADR-002 (P1 and P2 gates; deviations)
- ADR-004 (P2 design; the failed gate)
