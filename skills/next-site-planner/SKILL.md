---
name: next-site-planner
description: Mobile network planning from public data for Indonesia, Malaysia, the Philippines, Germany, France, the United States and the UAE. Looks up how slow mobile is at a latitude/longitude and for how many people (coverage gap vs capacity gap), lists a country's budgeted, ground-checked site plan (new macro, small cell or co-location), explains one planned site in plain words, and compares countries. Use this skill whenever someone asks about mobile coverage or speed gaps at a place, where to build the next cell site or tower, site nominations or shortlists under a budget, people below a speed bar such as 25 Mbps, or how these seven countries compare, even if they do not name the planner. Do not use it for fixed broadband, other countries, or operator-specific network data.
---

# Next Site Planner

Answers radio-planning questions from a public, read-only API built on Ookla open speed tests, two population maps (Kontur, WorldPop), land cover and elevation, on 0.74 km² H3 hexagons. Results page: https://sabrinapribadi.github.io/next-site-planner/

## How to call it

Run the bundled client; it needs only Python 3 and the internet, and it waits through the host's cold start:

```bash
python scripts/nsp.py about                         # data sources, the speed-test period and the time of this check
python scripts/nsp.py countries [--bar 25]          # each country: people below the bar, plan size, plan vs KPI ranking
python scripts/nsp.py gap LAT LON                   # one hexagon: speed, gap type, people, whether the plan picked it
python scripts/nsp.py sites COUNTRY [--k 10]        # the country's plan, best first (ISO3: IDN MYS PHL DEU FRA USA ARE)
python scripts/nsp.py note COUNTRY RANK             # a short note on one planned site, every number traced to the data
python scripts/nsp.py map gap LAT LON --out map.html          # the hexagon and its 6 neighbours by speed, plus OpenStreetMap
                                                                # buildings, places and masts; nearest mast distance (about 1 min)
python scripts/nsp.py map sites COUNTRY --k 5 --out map.html  # map of planned sites
python scripts/nsp.py chart countries --out chart.html         # KPI baseline vs plan per country (paired bars)
python scripts/nsp.py chart sites COUNTRY --k 5 --out chart.html  # shortlist: people lifted per site by build type
```

The same four tools exist over MCP at `https://next-site-planner.vercel.app/mcp` (`gap_at`, `top_sites`, `explain_site`, `compare_countries`). If an MCP connection is configured, either route is fine; the numbers are identical.

## Workflow

1. **Run `about` first** so the answer can open with the data used and when it was checked.
2. **Pick the call from the question.** A place or coordinates → `gap`. "Where should we build" or a shortlist → `sites`, then `note` for the sites the user cares about. "Which country", "how many people" → `countries`.
3. **Convert place names to coordinates yourself** before calling `gap`, and say which point you used, because a hexagon is only 0.74 km² and a nearby point can differ.
4. **Answer in the planner's terms**, with the numbers the API returned, and nothing it did not return. Read `references/fields.md` before explaining any field you are unsure of, and `references/data-sources.md` for sources, the baseline and why a hexagon is or is not in the plan.
5. **Treat `out_of_scope` as an answer.** If the API says a country or point is not covered, say so and list the seven countries; do not estimate from general knowledge.

## Reading the numbers correctly

These are the mistakes worth avoiding, because each one changes a planning decision:

- `plan_gain_vs_kpi` is a **relative gain**, not a ratio: 1.85 means the plan lifts 185% more people than the KPI ranking baseline (equal-weight speed, population and places), which is **2.85×** as many. 0.50 means 1.5×. Always pair it with `plan_people_lifted`: a big multiple on a small base (the UAE: 3.8× but about 311 people) matters less than a smaller multiple on hundreds of thousands.
- `chance_below_25_mbps` is a probability for that hexagon, not a share of people. Say "an 84% chance that typical speed here is below 25 Mbps".
- `expected_people_lifted` is people × the chance of being below 25 Mbps × the measured share a site lifts (different for a new site and for co-location); it is an expectation, so round it and call it "about". Sites are ranked by it, largest first.
- `cost_new_tower_equivalents`: 1.0 = a new macro tower, 0.5 = a small cell, 0.3 = co-location on an existing tower (the API calls it `capacity`). The plan's budget is 1,000 tower-equivalents per country, except the UAE (29.3: all 29 likely-slow candidates); read `budget_new_tower_equivalents` rather than assuming.
- **Coverage gap** means people are slow because there is little or no signal; **capacity gap** means signal exists but the network is congested. They need different fixes (new site vs co-location or capacity), so name the type.
- `people_kontur` and `people_worldpop` are two independent population estimates; a site's `people` is the smaller of the two (a conservative planning figure). When they differ a lot, say so.
- Speeds are crowdsourced tests for one quarter (`quarter` in `countries`); untested hexagons have estimated speeds (`tested: false`). With fewer than about 10 `tests`, say the evidence is thin (one test can be one bad moment).

## Answer structure

Planners and executives decide in about five seconds whether an answer is useful and trustworthy, so keep it short, numbered and visual:

1. **Data line** (one line, first): Ookla speed tests for the quarter and its dates (e.g. "2026 Q3, 1 Jul–30 Sep 2026, 13 weeks"), Kontur 2023 and WorldPop 2020 population, "checked <date> UTC" (from `about`).
2. **Headline** in bold: the answer in one sentence with its key number.
3. **2–4 numbered points**, each one line:
   - the **baseline** for any comparison: KPI ranking (equal-weight slow speed, population, number of places, filled until the budget is spent; it stands in for the weighted KPI lists planners build today), with its own number, not only the gain;
   - **why**: why a place is or is not in the plan (first reason in `references/data-sources.md` the numbers support), or the period behind a probability ("from 13 weeks of tests");
   - the one **caveat** that would change the decision (estimates with wide ranges; a large gap between population maps; the UAE's small budget).
4. **One visual**, chosen with `references/charts.md`: no chart for a single place (use the map), paired bars for baseline vs plan, ranked bars for a shortlist; a table only for exact values the reader needs. Give the file path and say what it shows. For place maps, read the panel: how many of the neighbouring hexagons are likely slow (an isolated gap or an area-wide one), the building and place counts, and the nearest mapped mast (a co-location candidate); OpenStreetMap is volunteered and may miss masts, so say "mapped".
5. **To sharpen this** (one line, for shortlists and investment questions): CAPEX and OPEX per site type, existing sites, market share, revenue per user and the commercial strategy. Add the licence (Ookla data is CC BY-NC-SA 4.0, non-commercial) when the numbers may be reused.

Aim for about ten lines of text before the visual; cut any point that would not change the reader's decision.

## Limits

Seven countries only; one quarter of speed tests; public data, not operator network data; no live traffic, interference or backhaul. Site notes are cached or templated text checked by a grader, so they never add facts beyond the API's numbers.
