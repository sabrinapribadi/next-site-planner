# Next Site Planner

**Where would one more mobile site improve measured speeds for the most people — per unit of budget?**

Public data only, seven countries (Indonesia, Malaysia, Philippines, Germany, France, United States, United Arab Emirates):

- Measure the gap: people living where measured mobile download is below 10 or 25 Mbps (Ookla open speed tiles × Kontur population on an H3 grid)
- Compare countries fairly: at equal population density, with the unmeasured population reported
- Measure what new sites do: before/after speeds near newly seen cells (all seven countries, one rule)
- Choose sites as a set: an exact budgeted optimiser vs KPI ranking; every nominal checked on the ground
- Serve answers: a planner API and MCP tools, with site notes whose numbers are all traced to the data
- Run as a cloud job: Databricks rebuilds Indonesia quarterly from Ookla's source files

**Live:** [results page](https://sabrinapribadi.github.io/next-site-planner/) · [technical walkthrough](https://sabrinapribadi.github.io/next-site-planner/build.html)

**Status: phases 0–7 done.** Details: [docs/PRD.md](docs/PRD.md), [decision records](docs/adr/README.md), [CHANGELOG.md](CHANGELOG.md).

| Phase | Gate (set before the work) | Result |
|---|---|---|
| P0 Data foundation | ≥ 99% of people and tests on the grid | Passed |
| P1 Experience gap | Intervals, clusters, gap types | Passed |
| P2 Speed where nobody tested | Machine learning ≥ 10% better than kriging | Failed (7%); kriging used |
| P3 Effect of new sites | Parallel pre-trends per country | Passed in 4 of 7 |
| P4 Site plan | ≥ 10% more people lifted than KPI ranking | Passed, after checking every nominal on the ground |
| P5 Planner API, MCP tools, site notes | Contracts, grounded notes, cost and latency budgets | Failed on live latency only; notes cached |
| P6 Databricks job (Indonesia) | Same shares as the laptop | Passed: identical |
| P7 Pages | Browser tests in three display modes | Passed |

**Results:**

- 61.7M people in tested areas get under 25 Mbps on mobile; 349M live where nobody tested.
- At equal density, the Philippines (34% below 25 Mbps) and Indonesia (22%) fall further behind.
- Area types match official EU figures within 10 points in 6 of 7 countries; the UAE gap comes from its population map.
- 47–68M untested people are likely below 25 Mbps; the range comes from two population maps.
- The two maps agree in Germany and France; in the US they differ by 17%, in Southeast Asia and the UAE by 27–37%.
- New sites lift some slow places: up to 1 in 8 crossed 25 Mbps; average speed rose only in the US.
- Checked site plans lift 1.5–3.8× as many people as KPI ranking at the same budget (+50% to +281%).
- Every nominal has people on both maps, at least 1,000 m² of buildings, and a pin on built land.
- Site lists as CSV / GeoJSON / KML in `docs/data/plans/`.
- Site notes: 100% of numbers traced to the data, $0.064 per 1,000 notes.
- Databricks reproduces Indonesia's numbers exactly, reading Ookla at the source.
- Single speed tests are mostly luck: two tests at one place differ 3–5×; neighbourhood blending fixes much of it.

## Reproduce

```bash
brew install uv && make env           # shared environment outside OneDrive: ~/.venvs/portfolio (+ ~/.portfolio-node for browser tests)
cp .env.example .env            # set GEO_DATA_DIR (and OPENCELLID_TOKEN for `make data`)
set -a; . ./.env; set +a
make data                        # public sources into GEO_DATA_DIR (hours; resumable)
make pipeline                    # P0 → P1 → P2 → noise → P3 → P4 → nominal checks → page data (several hours on an 8 GB laptop)
make test build-test hover-test  # unit tests; browser checks of both pages
python scripts/build_serving_store.py                 # P5 serving store (outside the repository)
uvicorn src.serving.api:app --port 8000              # REST API: /gap, /sites/{country}, /sites/{country}/{rank}/note, /countries
python -m src.serving.mcp_server                     # MCP server (stdio) for AI assistants
python scripts/eval_notes.py                         # live site-note evaluation (needs OPENAI_API_KEY in .env)
python scripts/databricks_prepare_inputs.py IDN      # P6 inputs, then: databricks bundle deploy && databricks bundle run geo1_p6
```

| Step | Script | Output (`data/outputs/`) | Decision record |
|---|---|---|---|
| P0 grid | `build_hex_table.py` | `p0_foundation.json`, `manifest.json` | ADR-001, ADR-003 |
| P1 gap | `experience_gap.py` | `p1_experience_gap.json` | ADR-001, ADR-002, ADR-003 |
| P2 speed model | `speed_model.py` | `p2_speed_model.json` | ADR-004 |
| Test noise, deployment | `noise_followup.py`, `noise_validation.py` | `p2b_noise_followup.json`, `p2c_noise_validation.json` | ADR-005 |
| P3 new-site effect | `new_site_effect.py`, `new_site_diagnostics.py` | `p3_new_site_effect.json`, `p3b_diagnostics.json` | ADR-007 |
| P2 version 2 freeze | `freeze_p2v2.py` | `p2v2_frozen.json` | ADR-006 |
| P4 site plan | `new_site_crossing_checks.py --estimand capacity`, `site_plan.py` | `p4_capacity_crossing.json`, `p4_site_plan.json`, `docs/data/plans/` | ADR-008 |
| P4 nominal checks | `worldpop_hex.py`, `population_crosscheck.py`, `site_plan.py --validated`, `nominal_validation_report.py` | `p1b_population_crosscheck.json`, `p4b_nominal_validation.json` | ADR-008 amendments 1–2 |
| P5 API, MCP, site notes | `build_serving_store.py`, `eval_notes.py`, `src/serving/` | `p5_notes_eval.json` | ADR-009 |
| P6 Databricks job | `databricks_prepare_inputs.py`, `databricks_p6.py`, `databricks.yml` | `p6_databricks_idn.json` | ADR-010 |
| Pages | `export_page_data.py` | `docs/data/` | — |

## Data

Raw data lives outside the repository (`GEO_DATA_DIR`). `make data` rebuilds it; `make evidence` refreshes the evidence table for cited papers.

| Source | Licence |
|---|---|
| Speedtest by Ookla Global Fixed and Mobile Network Performance Maps | CC BY-NC-SA 4.0 |
| Kontur population | CC BY 4.0 |
| WorldPop 2020 constrained, UN-adjusted (second population source) | CC BY 4.0 |
| ESA WorldCover 2021 v200 (built-up check) | CC BY 4.0 |
| Copernicus DEM GLO-30 (elevation, slope) | Free licence (Copernicus DEM licence) |
| JRC GHSL country statistics and GHS-SMOD (urban-centre check) | EU reuse policy (attribution) |
| Overture Maps places | CDLA-Permissive 2.0 |
| OpenCelliD | CC BY-SA 4.0 |
| OCHA COD-AB Indonesia; geoBoundaries | CC BY-IGO; CC BY 4.0 / ODbL |
| Natural Earth | Public domain |

Maps derived from Ookla data are shared under CC BY-NC-SA 4.0. Code is MIT-licensed.
