# Changelog

Newest first. Each entry uses STAR (Situation, Task, Action, Result) so it can be told as a story.

## [0.2.0] — 2026-10-13 — Industry alignment before analysis (ADR-003); data acquisition for seven countries
**Files:** docs/adr/ADR-003-industry-alignment.md, docs/adr/ADR-002-validation-and-gates.md, docs/adr/README.md, docs/PRD.md, docs/references.yaml, configs/default_config.yaml, scripts/acquire_public_data.py, docs/build.html, tests/browser/build_test.js, Makefile, .gitignore
- **Situation:** The design answered an analyst's question but not a planner's. It had no coverage-vs-capacity split, no urban/rural morphology, "K sites" with equal costs, no co-location option and no planner-ready output. Separately, the 11 GB Overture places release was too slow to scan for every country on an 8 GB machine.
- **Task:** Align the plan with how network planning works, using primary public sources, and fix it before P1 runs. Finish acquiring the seven-country data.
- **Action:**
  - Wrote ADR-003:
    - gap types (coverage / capacity / unmeasured) from cells within ring-1;
    - morphology using the Degree of Urbanisation on H3;
    - service radii from 3GPP TR 38.901 inter-site distances;
    - co-location-first interventions with cost ratios from FCC 17-126 (in new-tower equivalents, with ranges);
    - regulatory benchmarks (BNetzA 2019, EU Digital Decade, ITU-R M.2410) and a 100 Mbps sensitivity bar;
    - CSV / GeoJSON / KML exports, post-launch tracking, snapshot manifest, data contracts.
  - Amended gates P0, P1 and P4 in ADR-002, then the PRD (v0.2) and config.
  - Acquisition: per-country Overture extracts, plus the official Overture command-line tool for the US and UAE, with retries; atomic writes everywhere.
  - Technical walkthrough page (`docs/build.html`) started, with browser tests.
- **Result:** 3 ADRs; gates still pre-registered (nothing analysed yet). Overture places: 29.8M across seven countries. Kontur population on H3 r8; OpenCelliD 1.6M cells.
- **Talking point:** "Before running any numbers, I checked the plan against how planners actually work — gap type, morphology, co-location first, cost — and sourced every assumption from a standard or a regulator."

## [0.1.0] — 2026-10-13 — Project design: framing, validation, gates
**Files:** README.md, LICENSE, docs/PRD.md, docs/adr/README.md, docs/adr/ADR-001-framing-and-analysis-unit.md, docs/adr/ADR-002-validation-and-gates.md, docs/references.yaml, scripts/evidence.py, scripts/acquire_public_data.py, configs/default_config.yaml, Makefile, requirements.txt, .gitignore, .env.example
- **Situation:** Site plans are often ranked on composite KPIs with agreed weights, and country comparisons quote national medians that mix cities with islands. Nobody checks whether new sites actually lifted nearby speeds.
- **Task:** Design a public-data planner for seven countries that measures the gap per person, compares countries fairly, measures what new sites do, and optimises a budgeted set of sites — with every gate fixed before analysis.
- **Action:** Framed the question around people below 10 / 25 Mbps on an H3 r8 grid (ADR-001), with density-adjusted comparison and the unmeasured population reported. Fixed validation and gates for P0–P7 (ADR-002): spatial block CV, FDR-controlled hotspots, staggered difference-in-differences with pre-trend tests, an exact covering optimiser against a ranking baseline. Added a SOTA comparison and an OpenAlex evidence table to each ADR (rule R2 as amended) and a script that regenerates the evidence. Justified Spark and Databricks from measured volumes (rule R15).
- **Result:** PRD v0.1, 2 ADRs, 8 pre-registered gates, 11 references with evidence. No analysis run yet.
- **Talking point:** "Before touching a model, I changed the question from 'which sites score highest?' to 'where would one more site lift the most people, and do sites actually lift speeds?'"
