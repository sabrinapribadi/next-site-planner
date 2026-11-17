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
python scripts/nsp.py map gap LAT LON --out map.html          # interactive map of the hexagon over satellite imagery
python scripts/nsp.py map sites COUNTRY --k 5 --out map.html  # map of planned sites
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
- Speeds are crowdsourced tests for one quarter (`quarter` in `countries`); untested hexagons have estimated speeds (`tested: false`).

## Answer structure

Planners and executives decide whether to trust a number before they read it, so the order matters:

1. **Data used** (two or three lines, first): speed tests from Ookla open data for the quarter and its dates (e.g. "2026 Q3, 1 July–30 September 2026, 13 weeks"), population from Kontur 2023 and WorldPop 2020, and "checked on <date> UTC" from `about`.
2. **Baseline** (for any comparison or "how much better"): what the plan is compared with and why. The usual baseline is KPI ranking: equal-weight scores of slow speed, population and number of places, filled until the budget is spent; it stands in for the weighted KPI lists planners build today. Give the baseline's own number (people it lifts), not only the gain.
3. **The answer**, in operational units: people, Mbps, sites, tower-equivalents. For shortlists, a table with rank, district, intervention, cost, people and expected people lifted.
4. **Why**: for a place, why it is or is not in the plan (the first reason in `references/data-sources.md` that the numbers support); for a probability, what period it comes from ("from 13 weeks of tests").
5. **Map** when the question is about a place or specific sites: run `map` and give the file path; say what the satellite view shows (built-up land, open land) and quote `built_up_m2` for planned sites.
6. **Caveats and what would sharpen it**: these are estimates from public data (ranges in `references/data-sources.md`); for a shortlist or investment question, ask for CAPEX and OPEX per site type, existing sites, market share, revenue per user and the commercial strategy. Mention the licence (Ookla data is CC BY-NC-SA 4.0, non-commercial) when the numbers may be reused.

Keep each part short; the data and baseline lines exist so the reader can judge the answer, not to pad it.

## Limits

Seven countries only; one quarter of speed tests; public data, not operator network data; no live traffic, interference or backhaul. Site notes are cached or templated text checked by a grader, so they never add facts beyond the API's numbers.
