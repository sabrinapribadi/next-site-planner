# ADR-010: Databricks Quarterly Job for Indonesia (P6)

**Status:** Accepted — written and pushed before any P6 job code (commit `acb9849`, 17:18); gate **passed** (results below)
**Date:** 2026-10-14
**Deciders:** Sabrina Pribadi

---

## Context and Problem Statement

**What P6 must show:** the local pipeline can run as a scheduled cloud job, with a model registry and monitoring (portfolio rule R15).

**Scope change, decided before any job code:**

- **ADR-002 P6 gate (as written):** the job reproduces the local P1 country shares, all seven countries.
- **Now:** Indonesia only. Uploading every country's inputs adds hours and shows nothing new, and the job takes the country as a parameter.
- **Unchanged:**
  - P5 and P7;
  - the seven-country analysis, which keeps running locally (`make pipeline`).

**Probes on Databricks Free Edition (2026-10-14, before this ADR):**

| Question | Result |
|---|---|
| Can serverless read Ookla's public S3 bucket? | Yes (Spark and pyarrow, anonymous) |
| Built-in H3 functions? | Yes; Jakarta test point gives the same cell as locally (`888c107837fffff`) |
| Spatial SQL (`ST_Contains`)? | Yes |
| Volume of one refresh | 53.7M global mobile tile rows read (15 quarters) in 28 s; 3.3M in Indonesia's bounding box |

**R15, stated honestly:**

- **By data size:** Indonesia (3.3M tile rows) does not need Spark; DuckDB on the 8 GB laptop handles it. The global read per refresh (~54M mobile rows, plus fixed broadband) is what reaches Spark scale.
- **By operations:** Databricks is used for a scheduled refresh from the source, a model registry and monitoring.

## Decision (pre-registered)

### Job `geo1_p6` (Databricks Asset Bundle, serverless, `country = IDN`)

| Task | What it does | Inputs |
|---|---|---|
| `ingest_tiles` | Reads the 15 mobile quarters straight from Ookla's S3; keeps tiles whose centre is inside the country polygon | Ookla S3; the exact simplified polygon used locally (uploaded WKT) |
| `build_hexagons` | Tile → H3 resolution-8 cell; test-weighted mean of log speed per cell and quarter; joins Kontur population | Uploaded Kontur extract for the country |
| `p1_shares` | People-weighted shares below 5, 10, 25, 50 and 100 Mbps for tested people; tested share | — |
| `parity` | Compares with the local P1 output | Uploaded `p1_experience_gap.json` |
| `register_scorer` | Registers the site-plan scorer in Unity Catalog with alias `champion` | Uploaded checked-plan inputs for the country |
| `monitor_drift` | Latest vs previous quarter: population stability index (PSI) of people-weighted log speed; change in the share below 25 Mbps | — |
| `publish_tables` | `workspace.geo1.<iso>_hex_latest`, `_p1_shares`, `_plan`, `_drift` | — |

- **Schedule:** quarterly, after Ookla's release; paused because of Free Edition quotas, so runs are on demand.

### The registered model

GEO-1's deployed speed estimate is a spatial pipeline (noise shrinkage + kriging, ADR-005), not a single trained classifier.

- **What is registered:** the step that turns those estimates into the plan, the **site-plan scorer** (MLflow pyfunc). Expected people lifted = people (smaller of two maps) × chance below 25 Mbps × lift rate θ for the intervention.
- **Version metadata:** the θ values, the population rule and the built-up threshold.
- **Not re-fitted on Databricks:** kriging and noise shrinkage. The scorer receives their outputs as inputs, and this is stated on the pages.

### Gate (ADR-002 P6, made precise here)

1. **P1 parity (the original gate, Indonesia):**
   - tested share and shares below 5, 10, 25, 50 and 100 Mbps equal the local values when rounded to 0.1 percentage point, the precision reported;
   - maximum absolute difference reported.
2. **Scorer parity:** the registered scorer reproduces the local checked plan's expected people lifted for Indonesia within 0.1%.
3. **Operations:** the job is deployed from the bundle, the model carries the `champion` alias, and the drift task writes its table.

### Drift rule (reported, not gated)

PSI > 0.2 between consecutive quarters flags a shift. 0.2 is a common convention in credit-risk monitoring, not a published standard; it is our own threshold here.

## Alternatives

| Option | Status | Why |
|---|---|---|
| All seven countries on Databricks | Rejected for P6 | Hours of uploads; the job is country-parameterised, so it adds nothing to the demonstration |
| Upload Ookla extracts instead of reading S3 | Not needed | The probe showed direct S3 reads work |
| Re-fit kriging on Databricks | Out of scope | Heavy; the pipeline's speed step stays local and versioned (ADR-005, ADR-006) |

## SOTA comparison

| Family | Method | Tested | Cited, not tested (why) |
|---|---|---|---|
| Distribution drift | Population stability index (PSI) over fixed speed bands | Yes | — |
| Distribution drift | Two-sample Kolmogorov–Smirnov test | No | With ~170,000 tested hexagons, any shift is "significant"; PSI measures size, not significance |
| Distribution drift | Jensen–Shannon divergence | No | Same information as PSI for fixed bands; less familiar to network teams |
| Orchestration | Databricks Asset Bundle job (serverless) | Yes | — |
| Orchestration | Airflow or Dagster on a server | No | Needs a running server; the Free Edition job scheduler is enough for a quarterly run |

## Evidence

No peer-reviewed source fixes PSI's 0.2 threshold; it is a monitoring convention, stated here as our own threshold. Vendor documentation: Databricks Asset Bundles, Unity Catalog model registry, H3 and spatial SQL functions; MLflow.

## Falsification

| Result | Diagnosis | Next action |
|---|---|---|
| Shares differ at the reported decimal | Assignment or aggregation differs (polygon, rounding, H3 version) | Find the first differing tile or cell; fix and log |
| Scorer differs > 0.1% | Different inputs or θ | Compare row by row |

## Results (2026-10-14; `data/outputs/p6_databricks_idn.json`; job run 690306713800731)

| Gate item | Result | Pass |
|---|---|---|
| P1 parity, Indonesia | Databricks shares equal the local ones exactly: maximum absolute difference 0.0 on the tested share and every bar (5–100 Mbps); same total population (269,734,124) | Yes |
| Scorer parity | `workspace.geo1.idn_site_scorer` v1 (`@champion`) gives 122,504 expected people lifted vs 122,506 locally (0.002%; the plan file rounds its inputs) | Yes |
| Operations | Deployed from `databricks.yml`; quarterly schedule (paused); drift table written; six tables published (`workspace.geo1.idn_tiles`, `_hex_panel`, `_hex_latest`, `_p1_shares`, `_plan`, `_drift`) | Yes |

**Volume (R15):**

- 53.7M global mobile tile rows read for 15 quarters, in 28 s.
- 2,403,501 kept inside Indonesia's polygon.

**Drift (reported):** PSI 0.223 between 2026 Q2 and Q3, above the 0.2 flag.

- People on tested hexagons above 100 Mbps: 8.5% → 25.5%.
- Below 25 Mbps: −3.5 points.
- A real shift in the data, from network upgrades or a change in Ookla's data; flagged, not explained.

**Problems found while running:**

- **MLflow experiment:** `register_scorer` failed twice ("Could not find experiment with ID None"); MLflow on Databricks needs an experiment path. The task now sets it under the running user's folder.
- **Repair run:** only the scorer and publish tasks were re-run; ingestion and parity results were kept.

## Consequences

- **Positive:** the same numbers from a scheduled cloud job reading the source, with a registry and drift checks.
- **Negative:** one country only; kriging is not recomputed in the cloud. Both are stated on the pages.

## Related Decisions

- ADR-001 (R15 justification)
- ADR-002 (P6 gate)
- ADR-005 (speed estimates)
- ADR-008 (the scorer's rule)
