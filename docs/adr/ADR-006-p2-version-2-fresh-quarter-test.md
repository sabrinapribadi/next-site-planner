# ADR-006: P2 Version 2 — Test LightGBM Against Kriging on a Fresh Quarter

**Status:** Proposed — **pre-registered on 2026-10-14**, before Ookla's 2026 Q4 data exists. Predictions are frozen and fingerprinted (below) before any Q4 data is read.
**Date:** 2026-10-14
**Deciders:** Sabrina Pribadi

---

## Context and Problem Statement

**What has been tested so far:**

- **P2's pre-registered gate failed.** LightGBM's RMSE was 0.929 × kriging's (7% better; 10% needed), so kriging is deployed (ADR-004).
- **The diagnostic disagrees.** Scored only on well-tested hexagons (≥ 10 tests), the ratio was 0.82, so LightGBM looks clearly better once noisy targets are left out (ADR-005).

**Why the diagnostic cannot decide.** It was chosen after seeing the result, on the same data. Switching models on that basis would be moving the goalposts.

**The fair test.** Fix the rule now and judge it on data that does not exist yet.

The question: **"Predicting places nobody had tested, does LightGBM beat kriging by at least 10% where the new measurements are reliable?"**

## Decision (pre-registered)

### Freeze (2026-10-14, before 2026 Q4 is published)

1. **Kriging predictions:** for every untested populated hexagon (2026 Q3). Already deployed in `derived/hex_p2.parquet`.
2. **LightGBM predictions:** for the same hexagons, using the model trained exactly as in ADR-004 (same features, hyperparameters and seed). No retraining after this date.
3. **Fingerprint:**
   - Both predictions, with their σ, go into `derived/p2v2_frozen_predictions.parquet`.
   - The file's SHA-256, row count and the code commit are pushed in `data/outputs/p2v2_frozen.json`.
   - **Any later change to the file voids the test.**

#### Frozen record

- **File:** `derived/p2v2_frozen_predictions.parquet`, 5,762,813 rows.
- **SHA-256:** `ec23f069982459f7165994048219fac4cac5a4ded55d8c1705f57e63bbcadf8d`
- **Frozen:** 2026-10-13T23:18:53+00:00, from code commit `252a6b7`.
- The file stays in the data folder as a dated snapshot. It must hash to this value when the test runs.

**Observed at freeze (before any Q4 data).** The two models disagree systematically on untested hexagons. Median predicted download:

| Country | Kriging | LightGBM |
|---|---|---|
| Philippines | 22.3 Mbps | 12.9 Mbps |
| Indonesia | 28.1 Mbps | 15.9 Mbps |
| Malaysia | 47.1 Mbps | 25.0 Mbps |
| Germany | 39.1 Mbps | 27.1 Mbps |
| France | 50.3 Mbps | 32.6 Mbps |
| United States | 99.3 Mbps | 69.6 Mbps |
| UAE | 182.9 Mbps | 130.2 Mbps |

- **Why they differ:** kriging borrows from nearby *tested* places. LightGBM also uses what the place is (population, places, cells, history), and untested places are sparser.
- **Stakes:** if LightGBM is right, the deployed estimate of untested people below 25 Mbps (≈ 68M, from kriging) is too low. The fresh-quarter test therefore also settles the size of the hidden gap.
- **Also reported at test time:** the people-weighted share below 25 Mbps in newly tested hexagons, measured vs each model's prediction.

### Test set (defined now)

- Populated hexagons with **no** mobile test in 2026 Q3 and **at least one** in 2026 Q4: "newly tested hexagons".
- **Primary set:** newly tested hexagons with **≥ 10 tests** in 2026 Q4 (reliable targets).
- **Minimum size:** ≥ 2,000 primary hexagons pooled over the seven countries. If fewer, add 2027 Q1 under the same rules; the predictions stay frozen.

### Gate (version 2)

- **Pass:** RMSE of ln(2026 Q4 download) on the primary set, LightGBM ≤ **0.90 ×** kriging, pooled over the seven countries.
- **On pass:** LightGBM replaces kriging for deployment from the next refresh, and the pages say so.
- **On fail:** kriging stays and LightGBM is retired for P2. The result is published either way.

### Reported, not gated

- RMSE on all newly tested hexagons;
- precision-weighted RMSE (ADR-005 weights);
- per-country RMSE;
- AUC for "below 25 Mbps";
- 80% interval coverage, with 2026 Q4 test noise added to each model's σ;
- the share of newly tested people below 25 Mbps: predicted vs measured.

## Why this design

| Choice | Alternative | Why this |
|---|---|---|
| Newly tested hexagons | All 2026 Q4 hexagons | Matches the real use: predicting places nobody had tested |
| ≥ 10 tests | All tests | Removes most target noise (ADR-005), so skill rather than luck decides |
| Frozen, fingerprinted predictions | Retrain when Q4 arrives | No room to tune after seeing the answer |
| Same 0.90 margin | A lower margin | The cost argument (16 extra inputs, upkeep) is unchanged |

## Falsification

| Result | Diagnosis | Next action |
|---|---|---|
| Fewer than 2,000 primary hexagons | Few places become tested in one quarter | Add 2027 Q1 (same rules) |
| LightGBM passes on the primary set but not on all newly tested | Its advantage shows only where targets are reliable | Deploy LightGBM; keep the noise caveat |
| Both models much worse than in CV | Newly tested places differ from tested ones (selection) | Report; widen σ for untested areas |

## Consequences

- **Positive:** the model choice is settled by data that did not exist when the rule was written.
- **Negative:** the decision waits for Ookla's next release. Until then kriging stays deployed.

## Related Decisions

- ADR-002 (gates)
- ADR-004 (P2 design; failed gate)
- ADR-005 (noise; the diagnostic that motivated this test)
