# Next Site Planner

**Where would one more mobile site improve measured speeds for the most people — per unit of budget?**

Public data only, seven countries (Indonesia, Malaysia, Philippines, Germany, France, United States, United Arab Emirates):

- Measure the gap: people living where measured mobile download is below 10 or 25 Mbps (Ookla open speed tiles × Kontur population on an H3 grid)
- Compare countries fairly: at equal population density, with the unmeasured population reported
- Measure what new sites do: before/after speeds near newly seen cells (all seven countries, one rule)
- Choose sites as a set: an exact budgeted optimiser, compared with KPI-style ranking, with every nominal checked against a second population source, land cover and terrain

**Live:** [results page](https://sabrinapribadi.github.io/next-site-planner/) · [technical walkthrough](https://sabrinapribadi.github.io/next-site-planner/build.html)

Status: **phases 0–4 of 7 done**. Data foundation and experience gap passed their gates. For speed where nobody tested (P2), machine learning was only 7% more accurate than kriging, below the 10% set in advance to justify its extra inputs and upkeep, so the simpler kriging is used. The measured effect of new sites (P3) and costed site plans per country (P4) are done, with every nominal checked on the ground (the US check waits for its population file); API and AI tools (P5) are next. See [docs/PRD.md](docs/PRD.md), [docs/adr](docs/adr/README.md) and [CHANGELOG.md](CHANGELOG.md).

- 61.7M people in tested areas get under 25 Mbps on mobile; 349M people live where nobody tested.
- At equal population density the Philippines (34% below 25 Mbps) and Indonesia (22%) fall further behind.
- About 48–68M people nobody tested are likely below 25 Mbps (typical speed): the range is Kontur vs WorldPop population, with the US counted from Kontur until its WorldPop file arrives. That includes 13–23M in the Philippines and 22–30M in Indonesia.
- Population maps agree in Germany and France, but in poorly served places in Southeast Asia and the UAE they differ by 27–37%. Some original nominals sat where one map shows nobody, so every nominal is now checked.
- New sites lift slow places more than averages: a new site lifted up to about 1 in 8 slow places (below 25 Mbps) over the bar; France holds up under every check, while Germany (about 1 in 20) and the US (near 0) shrink under the strictest test. Average speed rose only in the US (+7–12%).
- Site plans: at the same budget, choosing places by expected people lifted per cost beats an equal-weight KPI ranking by +50% (Germany) to +281% (UAE) in the six countries checked so far (US pending).
  - Every nominal has people on both population maps, at least 1,000 m² of buildings (satellite land cover) and a site point on built land; terrain is flagged.
  - Before these checks the gain looked like +56% to +776%.
  - Site lists as CSV / GeoJSON / KML in `docs/data/plans/`.
- Single speed tests are mostly luck: two tests at the same place differ 3–5×. Each hexagon is blended with its neighbourhood (checked against the next quarter: 28–44% closer).

## Reproduce

```bash
brew install uv && make env           # shared environment outside OneDrive: ~/.venvs/portfolio (+ ~/.portfolio-node for browser tests)
cp .env.example .env            # set GEO_DATA_DIR (and OPENCELLID_TOKEN for `make data`)
set -a; . ./.env; set +a
make data                        # public sources into GEO_DATA_DIR (hours; resumable)
make pipeline                    # P0 → P1 → P2 → noise → P3 → P4 → nominal checks → page data (several hours on an 8 GB laptop)
make test build-test hover-test  # unit tests; browser checks of both pages
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
| Overture Maps places | CDLA-Permissive 2.0 |
| OpenCelliD | CC BY-SA 4.0 |
| OCHA COD-AB Indonesia; geoBoundaries | CC BY-IGO; CC BY 4.0 / ODbL |
| Natural Earth | Public domain |

Maps derived from Ookla data are shared under CC BY-NC-SA 4.0. Code is MIT-licensed.
