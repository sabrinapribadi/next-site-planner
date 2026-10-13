# Changelog

Newest first. Each entry uses STAR (Situation, Task, Action, Result) so it can be told as a story.

## [0.1.0] — 2026-10-13 — Project design: framing, validation, gates
**Files:** README.md, LICENSE, docs/PRD.md, docs/adr/README.md, docs/adr/ADR-001-framing-and-analysis-unit.md, docs/adr/ADR-002-validation-and-gates.md, docs/references.yaml, scripts/evidence.py, scripts/acquire_public_data.py, configs/default_config.yaml, Makefile, requirements.txt, .gitignore, .env.example
- **Situation:** Site plans are often ranked on composite KPIs with agreed weights, and country comparisons quote national medians that mix cities with islands. Nobody checks whether new sites actually lifted nearby speeds.
- **Task:** Design a public-data planner for seven countries that measures the gap per person, compares countries fairly, measures what new sites do, and optimises a budgeted set of sites — with every gate fixed before analysis.
- **Action:** Framed the question around people below 10 / 25 Mbps on an H3 r8 grid (ADR-001), with density-adjusted comparison and the unmeasured population reported. Fixed validation and gates for P0–P7 (ADR-002): spatial block CV, FDR-controlled hotspots, staggered difference-in-differences with pre-trend tests, an exact covering optimiser against a ranking baseline. Added a SOTA comparison and an OpenAlex evidence table to each ADR (rule R2 as amended) and a script that regenerates the evidence. Justified Spark and Databricks from measured volumes (rule R15).
- **Result:** PRD v0.1, 2 ADRs, 8 pre-registered gates, 11 references with evidence. No analysis run yet.
- **Talking point:** "Before touching a model, I changed the question from 'which sites score highest?' to 'where would one more site lift the most people, and do sites actually lift speeds?'"
