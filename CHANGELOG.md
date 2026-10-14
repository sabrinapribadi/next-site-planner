# Changelog

Newest first. Each entry uses STAR (Situation, Task, Action, Result) so it can be told as a story.

## [0.8.0] — 2026-10-14 — Nominals checked on the ground; full document audit (interim: US pending its WorldPop file)
**Files:** docs/adr/ADR-001, ADR-002, ADR-007, ADR-008 (amendments 1–2), docs/adr/README.md, docs/PRD.md, README.md, Makefile, src/groundcheck.py, tests/test_groundcheck.py, scripts/worldpop_hex.py, scripts/population_crosscheck.py, scripts/nominal_validation_report.py, scripts/validation_tables.py, scripts/site_plan.py, scripts/acquire_public_data.py, scripts/export_page_data.py, data/outputs/p1b_population_crosscheck.json, p4b_nominal_validation.json, p4_site_plan.json, p4_site_plan_original.json, p4_original_plans/*, docs/data/plans/*, docs/data/cells/*, docs/index.html, docs/build.html, tests/browser/hover_test.js
- **Situation:**
  - The new terrain map of nominals showed Indonesia's top sites in the Papua highlands.
  - One had 28,665 people in Kontur and 0 in WorldPop.
  - ADR-001's promised WorldPop cross-check had never run.
- **Task:** Make sure no nominal sits in a lake, a forest or on an empty mountain, and audit every document against the outputs.
- **Action:**
  - **Pre-registered first:** ADR-008 amendment 1 (pushed 10:54, before any check) set the same rules for all seven countries:
    - two population maps, counting the smaller;
    - at least 1,000 m² of buildings (ESA WorldCover 10 m);
    - a site point on built land;
    - terrain flags (Copernicus DEM).
  - **Re-planning:** the plan and the KPI baseline were re-solved until every pick had passed.
  - **WorldPop for seven countries:** summed into hexagons. The server ignores resume requests, so the US file (494 MB) is still downloading.
  - **Crowding:** both maps over-crowd some remote towns. Handled as a sensitivity, not a rule change: amendment 2, pushed before computing.
  - **Existing cells on the map:** recorded LTE/5G cells (OpenCelliD) are shown, so nominals' gaps are visible. The page and ADR-008 now say that "new site" means "no tower on record", which in Southeast Asia is not "no tower".
  - **Readability (hiring readers):**
    - every chart has a question as its title and a one-line answer computed from the data;
    - tooltips cut to 2–4 short lines (they now cover 5–8% of a chart, down from 15–51%);
    - the nominal map has its own country switcher;
    - zooming in shows every recorded cell hexagon (loaded on first zoom).
  - **Audit fixes:**
    - an unverifiable reference removed;
    - P3 scope (all seven countries) corrected in README, PRD and ADR-007;
    - the optimiser described as an exact knapsack, not "covering";
    - capacity lift +3.8 to +16.3 points (was +7.7 to +16), with its intervals;
    - the P2 range 0.92–0.93 (was 0.92–0.94);
    - Overture places described as model input and baseline, not "daytime demand";
    - stale "phases 2–4 next" text removed;
    - the decision log put in order;
    - WorldPop added to `make data`, and the checks to `make pipeline`.
- **Result:**
  - **Population:**
    - The maps agree in Germany and France (−7%, −9% in poorly served places).
    - They disagree by 27–37% in Indonesia, Malaysia, the Philippines and the UAE, so those counts are now ranges. For example, 22–30M untested Indonesians are likely below 25 Mbps.
  - **Original nominals:**
    - Indonesia: 23% had nobody in WorldPop and 8% had no buildings.
    - UAE: 31% had no buildings, so its original plan is stated as a failure.
  - **Checked plans:** +50% (Germany) to +281% (UAE) more people than KPI ranking in 6 of 6 checked countries; before the checks this was +56% to +776%. Indonesia's original plan, re-scored, lifts 90k people, not 197k.
  - **Crowding:** the cap changes the chosen sites little (overlap 0.95–1.00).
  - **Tests:** 30 unit tests; browser checks 11 of 11 in three modes.
- **Talking point:** "A plan that looked 9× better than ranking was partly chasing people only one map could see. Checking every nominal against a second population map and satellite land cover cut the gain to a believable 1.5–3.8× and put every pin on built land, not in a forest."

## [0.7.0] — 2026-10-14 — P4: costed site plans for seven countries
**Files:** docs/adr/ADR-008-budgeted-site-plan.md, docs/adr/ADR-002-validation-and-gates.md, docs/adr/README.md, docs/references.yaml, docs/PRD.md, src/plan.py, tests/test_plan.py, scripts/site_plan.py, scripts/new_site_crossing_checks.py, data/outputs/p4_capacity_crossing.json, data/outputs/p4_site_plan.json, docs/data/plans/*, scripts/export_page_data.py, docs/index.html, docs/build.html, README.md, Makefile
- **Situation:** Planners rank places by agreed KPI scores; P3 showed new sites and added capacity lift some slow places above 25 Mbps.
- **Task:** For a fixed budget, choose the set of interventions that lifts the most people, and beat KPI ranking by the pre-set 10% or say so.
- **Action:**
  - **Design first:** ADR-008 pushed before any plan.
  - **Capacity lift rate:** estimated with P3's crossing checks before planning. It passes in Germany, France, the Philippines and Malaysia (+3.8 to +16.3 pts).
  - **The 10% margins:** labelled as our own pre-set thresholds, with the practice cited (Lakens).
  - **Solver:** exact knapsack by enumerating the three cost classes, tested against brute force.
  - **Baselines:** KPI ranking and slowest-first.
  - **Sensitivities:** θ, costs, capacity = new site, 3GPP service areas with greedy vs exact covering.
  - **Exports:** CSV / GeoJSON / KML per country, format-checked.
  - **Pages:** a plan chart, plan points on the map, download links, a details table, the walkthrough's P4 phase.
- **Result:**
  - **Gate passed:** +56% to +776% more people lifted than KPI ranking in 6 of 7 countries; the UAE's KPI plan lifts nobody.
  - **Robust:** still +45% to +741% if capacity worked like a new site. Greedy reaches 98–100% of exact.
  - **Cost per 1,000 people lifted:** 2.6 (Philippines) to 206 (US) new-tower equivalents.
  - **Tests:** 26 unit tests; browser checks 9 of 9 in three modes.
- **Talking point:** "Counting the people a site would lift, instead of scoring places, lifted 1.6 to 9 times more people for the same money."

## [0.6.1] — 2026-10-14 — P3 crossing measure checked for regression to the mean; environments outside OneDrive
**Files:** docs/adr/ADR-007-new-site-effect.md, docs/adr/ADR-002-validation-and-gates.md, src/did.py, tests/test_did.py, scripts/new_site_crossing_checks.py, data/outputs/p3c_crossing_checks.json, scripts/export_page_data.py, docs/index.html, docs/build.html, docs/data/page_data.js, README.md, Makefile
- **Situation:**
  - P4 was about to rely on "slow places lifted above 25 Mbps", but "slow" came from one noisy quarter, which invites regression to the mean.
  - The home-broadband control had not been run for that measure.
  - Separately, an 856 MB `.venv` inside OneDrive blocked git.
- **Task:** Test the crossing measure before P4 uses it, and stop environments living in synced folders.
- **Action:**
  - **Amendment 3:**
    - "slow" defined over a year;
    - estimates within speed bands;
    - a fixed-broadband control.
    - Written at 08:44, run at 08:49, pushed later because git was blocked; disclosed in the ADR with file times.
  - **Estimator:** `filter_Y` option, unit-tested.
  - **Pages:** the chart shows the pre-set and the cautious estimate; wording changed from "about 1 in 8" to "up to about 1 in 8".
  - **Environments:** shared `~/.venvs/portfolio` (uv) and `~/.portfolio-node`; the in-repo copies deleted.
- **Result:**
  - **France** holds: +12.1 pts.
  - **Germany** shrinks to +5.2 and the **US** to +1.5 under the strictest definition. The fixed control ≈ 0 everywhere.
  - **Philippines and Indonesia** fail the checks.
  - **P4:** gets an honest range of 0 to about +12 pts.
  - **Tests:** 22 unit tests, 318 of 318 walkthrough checks, 8 of 8 hover checks in three modes.
- **Talking point:** "Before using my own headline number, I tested it for regression to the mean — one country held, two shrank, and the plan now uses the range."

## [0.6.0] — 2026-10-14 — P3: what new sites did, in all seven countries
**Files:** docs/adr/ADR-007-new-site-effect.md, docs/adr/ADR-002-validation-and-gates.md, docs/adr/README.md, docs/PRD.md, src/did.py, tests/test_did.py, scripts/new_site_effect.py, scripts/new_site_diagnostics.py, data/outputs/p3_new_site_effect.json, data/outputs/p3b_diagnostics.json, scripts/export_page_data.py, docs/index.html, docs/build.html, README.md, Makefile, docs/references.yaml
- **Situation:** P4 needs the measured effect of a new site, but sites are built where demand already is and crowdsourced data dates them only roughly.
- **Task:** Estimate what new sites did to nearby speeds with a design fixed in advance, and treat every country the same.
- **Action:**
  - **Design first:** ADR-007 pushed before any outcome.
  - **Amendment 1:** all seven countries under one rule, at least 100 events per estimate. Pushed before running the new countries; Germany's already-seen result disclosed.
  - **Estimator:** Callaway–Sant'Anna written and unit-tested, with a spatial block bootstrap.
  - **Checks:** home-broadband control, placebo timing, ≥ 5-test robustness, area types, crossing 25 Mbps.
  - **Memory:** the regression arms sample never-treated hexagons (≤ 50k); results saved per country with resume.
  - **Amendment 2:** pushed before running. A direct imputation estimator, plus post-hoc test-volume and mobile-minus-fixed diagnostics.
  - **Pages:** a P3 chart, a details table, method rows, "How to read this" notes, the walkthrough's P3 phase.
- **Result:**
  - **Pre-trends:** pass in Germany, France, the US and the Philippines; fail in Indonesia (sites followed falling speeds: −12% the year before) and the UAE. Malaysia has too few sites.
  - **Slow places lifted above 25 Mbps:** +12.6 pts in Germany (+5.6 to +19.4) and +12.1 in France (+3.0 to +21.6).
  - **Average speed:** ≈ 0 except in the US (+7 to +12% across three methods).
  - **Test volumes:** unchanged everywhere.
  - **Tests:** 21 unit tests; browser checks 8 of 8 in three modes; walkthrough 318 of 318.
- **Talking point:** "New sites lift slow places over the bar more than they raise averages — and where a check failed, I said so country by country."

## [0.5.2] — 2026-10-14 — ADR-006 pre-registered and frozen; explanations collapsible
**Files:** docs/adr/ADR-006-p2-version-2-fresh-quarter-test.md, docs/adr/README.md, scripts/freeze_p2v2.py, data/outputs/p2v2_frozen.json, docs/index.html, docs/build.html, README.md
- **Situation:**
  - LightGBM failed P2's gate (7% better; 10% needed), yet was 18% better on well-tested hexagons, a diagnostic chosen after the fact.
  - Readers were confused by "beat kriging by 7%, so kriging is used".
  - The always-open notes lengthened the page.
- **Task:** Settle the model choice on data that does not exist yet; explain the decision plainly; keep the page short.
- **Action:**
  - **ADR-006:** pushed before 2026 Q4 exists.
    - Both models' predictions for all 5,762,813 untested hexagons are frozen and fingerprinted (SHA-256 ec23f069…).
    - They are scored on hexagons first tested in Q4 with ≥ 10 tests, against the same 0.90 gate.
  - **Clearer wording:** "only 7% more accurate, below the 10% set in advance to justify its extra inputs".
  - **Collapsible notes:** "? How to read this" items next to each number.
  - **New caveat:** the models disagree on untested places.
- **Result:**
  - **At freeze,** LightGBM predicts untested places 30–45% slower than kriging (e.g. Philippines median 12.9 vs 22.3 Mbps). The deployed ≈ 68M untested people below 25 Mbps may be too low; the Q4 test will decide.
  - **Tests:** browser checks pass 7 of 7 in three modes.
- **Talking point:** "When my diagnostic disagreed with my pre-set gate, I didn't switch models — I froze both predictions with a fingerprint and let next quarter's data decide."

## [0.5.1] — 2026-10-14 — Audit: every document aligned; results page de-duplicated for the hiring team
**Files:** docs/PRD.md, docs/adr/ADR-001…005, docs/adr/README.md, docs/index.html, docs/build.html, README.md, Makefile, scripts/evidence.py, scripts/speed_model.py, data/outputs/references_evidence.json
- **Situation:** After P2 the documents had drifted:
  - the PRD still said "P0 next";
  - all ADRs said "Proposed";
  - the walkthrough quoted 15.3M hexagon-quarters and 29 inputs (now 30.9M and 40);
  - two promised checks were not marked as open;
  - the results page repeated the same numbers in up to six places.
- **Task:** Align every document with the result files, and make the results page readable in two minutes (R12) without repeating itself.
- **Action:**
  - **PRD v0.3:** gate results recorded.
  - **ADRs:** marked Accepted, with results and open items.
    - The WorldPop cross-check and the published urban-centre comparison are open.
    - ADR-004 notes that `p2_speed_model.json` untested totals come from the LightGBM path and are not used.
  - **ADR-002:** gate results table.
  - **Walkthrough:** P0 numbers corrected.
  - **Results page:**
    - one headline ("1 in 9 people … 2 in 3 never tested");
    - tiles that each say something different;
    - one combined country chart (measured with interval, equal density, everyone);
    - the area-type chart moved to details;
    - non-overlapping caveats and FAQ;
    - one map note;
    - the duplicate decision table removed.
  - **Results page, R17 and R6:** "How to read this" notes for every remaining number; all P2 and noise sources listed.
  - **Reproducibility:** README "Reproduce" section; `make pipeline`.
  - **Evidence:** a 30 s timeout for OpenAlex calls; evidence regenerated (23 references).
- **Result:**
  - The collapsed page is 5.5 screens on desktop (limit about 7). Only the data card and data table shared numbers (places, cells); fixed.
  - Tests: 18 unit tests, 297 of 297 walkthrough checks, 7 of 7 hover checks in three modes.
- **Talking point:** "An audit after every phase keeps the PRD, decision records, pages and result files telling the same story."

## [0.5.0] — 2026-10-14 — P2: speed where nobody tested (gate failed → kriging); test noise; every number explained
**Files:** docs/adr/ADR-004-speed-model-for-untested-areas.md, docs/adr/ADR-005-measurement-noise.md, src/spatialmodel.py, src/noise.py, scripts/speed_model.py, scripts/noise_followup.py, scripts/noise_validation.py, tests/test_spatialmodel.py, tests/test_noise.py, data/outputs/p2_speed_model.json, data/outputs/p2b_noise_followup.json, data/outputs/p2c_noise_validation.json, scripts/export_page_data.py, docs/index.html, docs/build.html, docs/data/*
- **Situation:** 349M people (39%) live where nobody tested, so P1 could not count them. Most tested hexagons rest on 1–2 tests.
- **Task:** Predict typical speed where nobody tested, beat standard kriging by the pre-set 10% or fall back, and make every number readable (R17).
- **Action:**
  - **Design first:** ADR-004 pushed before training.
    - Test blocks sized by distance matching (~36 km²).
    - The strongest fair kriging: Cressie's weighted fit, exponential or spherical variogram, 16/32/64 neighbours, the best one used.
    - Leak-proof nested out-of-fold features; four test designs.
  - **Gate:** failed (0.929), so kriging is deployed.
  - **Follow-up (ADR-005, written before it ran):**
    - a noise model from tile pairs;
    - Fay–Herriot blending with a leave-one-out kriging prior;
    - a cross-quarter check.
  - **Pages:**
    - the district view coloured by the chance of a typical speed below the bar;
    - an "everyone" chart including untested people;
    - "How to read this" notes, a glossary, P2 and noise tables;
    - the walkthrough's P2 phase.
- **Result:**
  - **Model comparison:** LightGBM was 6–8% better than kriging on every design, 18% better on well-tested hexagons (a diagnostic, after the fact). Kriging stays.
  - **Noise:** two tests at one place differ 3–5×.
  - **Blending check:** blended speeds were 28–44% closer to the next quarter's tests in all seven countries. Share levels are credible in 4 of 7.
  - **Untested people:** ≈ 68M are likely below 25 Mbps (23M in the Philippines, 30M in Indonesia).
  - **Tests:** 18 unit tests pass; browser checks 8 of 8 in three modes and 297 of 297 on the walkthrough.
- **Talking point:** "My machine-learning model failed my own gate, so I shipped kriging — then showed the real limit was test noise, and that about 68 million people nobody tested are likely on slow mobile."

## [0.4.1] — 2026-10-13 — District zoom at analysis resolution (0.74 km²)
**Files:** docs/index.html, scripts/export_page_data.py, docs/data/d/*.js, tests/browser/hover_test.js
- **Situation:** The map showed ~250 km² display cells, which read as if sites were planned at that size; a planner needs the 0.74 km² analysis hexagons.
- **Task:** Let a reader zoom from the country view into one district's analysis hexagons without making the page heavy.
- **Action:**
  - One small file per district in any top-10 list (113 files, 12 MB, the largest 0.5 MB), loaded on demand.
  - **District view:** each hexagon is coloured tested-below / tested-above / not tested. Hover shows people, area type, measured speed, gap type and cluster membership. A back button returns to the country.
  - Map heading and note now say "display cells ≈ 250 km²; analysis on 0.74 km²".
  - **Fixed a tooltip that could stick:** opening a section redrew a chart under the pointer, so it never received "mouse left".
- **Result:** Hover tests pass 7 of 7 in light, dark and phone modes, twice in a row. Example: Bogor has 2,458 hexagons and 4.42M people.
- **Talking point:** "The overview stays light, but every district can be opened at the resolution the analysis — and later the site search — actually uses."

## [0.4.0] — 2026-10-13 — Results page live: hexagon map, district list, fair country comparison
**Files:** docs/index.html, docs/data/page_data.js, scripts/export_page_data.py, tests/browser/hover_test.js, Makefile
- **Situation:** P0 and P1 passed, but the results only existed as JSON and a technical walkthrough; a planner or hiring manager could not see them.
- **Task:** Build the hiring-team results page (R12) with practitioner numbers (R9) and hover on every chart (R10), without a basemap or a build step.
- **Action:**
  - The export script rolls 6.6M hexagons up to 46k areas of ~250 km², each with a district name (geoBoundaries).
  - **Map:** a canvas hexagon map drawn with h3-js, with hover by inverse projection.
  - **Controls:** what-if buttons for the speed bar (5–100 Mbps) and the country.
  - **District list:** districts ranked by the people below the bar.
  - **Charts:** country comparison (raw with block-bootstrap intervals, and at equal density), area types, tested vs untested, gap types.
  - The FAQ and caveats state the limits.
- **Result:**
  - The page loads 1.75 MB of data.
  - Hover tests pass: 6 of 6 in desktop light, desktop dark and phone at 400 px; no sideways scroll; no JS errors.
  - Headline: 61.7M people in tested areas are below 25 Mbps, and 349M live where nobody tested.
- **Talking point:** "The map answers a planner's first question — which districts have the most people on slow mobile — before any model exists, and says plainly what it cannot see."

## [0.3.0] — 2026-10-13 — P0 and P1 run: gates passed; three methods corrected after checks
**Files:** scripts/build_hex_table.py, scripts/experience_gap.py, src/spatialstats.py, src/hexgrid.py, tests/test_spatialstats.py, configs/default_config.yaml, docs/adr/ADR-002-validation-and-gates.md, docs/adr/ADR-003-industry-alignment.md, data/outputs/p0_foundation.json, data/outputs/p1_experience_gap.json, data/outputs/manifest.json, docs/build.html
- **Situation:** The first P1 run passed its gate on paper, but three checks showed problems:
  - Germany, France and the US had bootstrap intervals that missed their own estimates.
  - The shuffled-data test still found up to 318 "hotspots" after FDR.
  - OpenCelliD finds a cell near only 2% of fast rural Indonesian hexagons.
- **Task:** Fix the methods without moving the goalposts, and record every change.
- **Action:**
  - **P0:** border check moved from DuckDB (stuck after 13 min) to GeoPandas (about 3 s per million points). The input file list is read once at the start, skipping files still downloading.
  - **P1 intervals:** spatial block bootstrap (H3 resolution 5; resolution 4 as a check) replaced the biased tile bootstrap. Both are published.
  - **P1 hotspots:** exact conditional-randomisation p-values for Gi* (convolution of the empirical distribution) replaced the normal approximation.
  - **P1 gap types:** typed only where OpenCelliD finds ≥ 80% of fast hexagons' cells; elsewhere `slow_type_unknown`.
  - **5G measure:** relabelled as a completeness figure, not coverage.
  - All three changes are logged as deviations in ADR-002 and ADR-003.
- **Result:**
  - **P0 gate passed:** ≥ 99% of people and tests assigned in all 7 countries; contracts clean; 29 inputs in the manifest.
  - **P1 gate passed:** every interval contains its estimate.
  - **Hotspots:** false hotspots on shuffled data fell from 21–318 per country to 0 everywhere. Real slow hotspots remain only in Indonesia (24 hexagons) and the Philippines (14).
- **Talking point:** "The checks I wrote in advance caught three of my own methods failing — biased intervals, a test that found hotspots in noise, and a cell database too sparse to type gaps — and each fix is published next to the original."

## [0.2.1] — 2026-10-13 — ADR-003 in code: morphology, gap types, data contracts, manifest, CI
**Files:** src/morphology.py, src/contracts.py, tests/test_morphology_contracts.py, scripts/build_hex_table.py, scripts/experience_gap.py, configs/default_config.yaml, requirements.txt, .github/workflows/ci.yml
- **Situation:** ADR-003 fixed the industry view on paper, but P0 and P1 could not yet produce it, and the repo had no CI.
- **Task:** Implement the ADR-003 rules exactly as written, with tests, before any result exists.
- **Action:**
  - Degree of Urbanisation on H3: density per km², ring-1 contiguity, connected components, 50k / 5k cluster minimums.
  - Gap types at 10 and 25 Mbps from LTE/5G cells within ring-1.
  - Share of people with a 5G cell nearby.
  - Data contracts (unique keys, value ranges, all countries, all quarters) and a SHA-256 snapshot manifest in P0.
  - P1 gate now also requires every populated hexagon to be typed.
  - GitHub Actions runs the tests.
- **Result:** 9 unit tests pass locally and in CI (3 grid, 6 new; CI first failed because plain `pytest` does not put the repo root on the import path, so it now runs `python -m pytest`). No analysis run yet.
- **Talking point:** "The industry rules went into tested code before any result existed, so they could not be tuned to the answer."

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
