# Next Site Planner

**Where would one more mobile site improve measured speeds for the most people — per unit of budget?**

Public data only, seven countries (Indonesia, Malaysia, Philippines, Germany, France, United States, United Arab Emirates):

- Measure the gap: people living where measured mobile download is below 10 or 25 Mbps (Ookla open speed tiles × Kontur population on an H3 grid)
- Compare countries fairly: at equal population density, with the unmeasured population reported
- Measure what new sites do: before/after speeds near newly seen cells (Germany, US)
- Choose sites as a set: a budgeted covering optimiser, compared with KPI-style ranking

**Live:** [results page](https://sabrinapribadi.github.io/next-site-planner/) · [technical walkthrough](https://sabrinapribadi.github.io/next-site-planner/build.html)

Status: **phases 0–2 of 7 done**. Data foundation and experience gap passed their gates. For speed where nobody tested (P2), machine learning failed its gate against kriging (7% better; 10% needed), so kriging is used. New-site effect (P3) and site optimiser (P4) are next. See [docs/PRD.md](docs/PRD.md), [docs/adr](docs/adr/README.md) and [CHANGELOG.md](CHANGELOG.md).

- 61.7M people in tested areas get under 25 Mbps on mobile; 349M people live where nobody tested.
- At equal population density the Philippines (34% below 25 Mbps) and Indonesia (22%) fall further behind.
- About 68M people nobody tested are likely below 25 Mbps (typical speed), including 23M in the Philippines and 30M in Indonesia.
- Single speed tests are mostly luck: two tests at the same place differ 3–5×. Each hexagon is blended with its neighbourhood (checked against the next quarter: 28–44% closer).

## Data

Raw data lives outside the repository (`GEO_DATA_DIR`). `make data` rebuilds it; `make evidence` refreshes the evidence table for cited papers.

| Source | Licence |
|---|---|
| Speedtest by Ookla Global Fixed and Mobile Network Performance Maps | CC BY-NC-SA 4.0 |
| Kontur population | CC BY 4.0 |
| Overture Maps places | CDLA-Permissive 2.0 |
| OpenCelliD | CC BY-SA 4.0 |
| OCHA COD-AB Indonesia; geoBoundaries | CC BY-IGO; CC BY 4.0 / ODbL |
| Natural Earth | Public domain |

Maps derived from Ookla data are shared under CC BY-NC-SA 4.0. Code is MIT-licensed.
