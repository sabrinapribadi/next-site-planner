---
name: next-site-planner
description: Mobile network planning from public data for Indonesia, Malaysia, the Philippines, Germany, France, the United States and the UAE. Looks up how slow mobile is at a latitude/longitude and for how many people (coverage gap vs capacity gap), lists a country's budgeted, ground-checked site plan (new macro, small cell or co-location), explains one planned site in plain words, and compares countries. Use this skill whenever someone asks about mobile coverage or speed gaps at a place, where to build the next cell site or tower, site nominations or shortlists under a budget, people below a speed bar such as 25 Mbps, or how these seven countries compare, even if they do not name the planner. Do not use it for fixed broadband, other countries, or operator-specific network data.
---

# Next Site Planner

Answers radio-planning questions from a public, read-only API built on Ookla open speed tests, two population maps (Kontur, WorldPop), land cover and elevation, on 0.74 km² H3 hexagons. Results page: https://sabrinapribadi.github.io/next-site-planner/

## How to call it

Run the bundled client; it needs only Python 3 and the internet, and it waits through the host's cold start:

```bash
python scripts/nsp.py countries [--bar 25]          # each country: people below the bar, plan size, plan vs KPI ranking
python scripts/nsp.py gap LAT LON                   # one hexagon: speed, gap type, people, whether the plan picked it
python scripts/nsp.py sites COUNTRY [--k 10]        # the country's plan, best first (ISO3: IDN MYS PHL DEU FRA USA ARE)
python scripts/nsp.py note COUNTRY RANK             # a short note on one planned site, every number traced to the data
```

The same four tools exist over MCP at `https://next-site-planner.vercel.app/mcp` (`gap_at`, `top_sites`, `explain_site`, `compare_countries`). If an MCP connection is configured, either route is fine; the numbers are identical.

## Workflow

1. **Pick the call from the question.** A place or coordinates → `gap`. "Where should we build" or a shortlist → `sites`, then `note` for the sites the user cares about. "Which country", "how many people" → `countries`.
2. **Convert place names to coordinates yourself** before calling `gap`, and say which point you used, because a hexagon is only 0.74 km² and a nearby point can differ.
3. **Answer in the planner's terms**, with the numbers the API returned, and nothing it did not return. Read `references/fields.md` before explaining any field you are unsure of; several are easy to misread (see below).
4. **Treat `out_of_scope` as an answer.** If the API says a country or point is not covered, say so and list the seven countries; do not estimate from general knowledge.

## Reading the numbers correctly

These are the mistakes worth avoiding, because each one changes a planning decision:

- `plan_gain_vs_kpi` is a **relative gain**, not a ratio: 1.85 means the plan lifts 185% more people than ranking sites by weighted KPIs, which is **2.85×** as many. 0.50 means 1.5×. Always pair it with `plan_people_lifted`: a big multiple on a small base (the UAE: 3.8× but about 311 people) matters less than a smaller multiple on hundreds of thousands.
- `chance_below_25_mbps` is a probability for that hexagon, not a share of people. Say "an 84% chance that typical speed here is below 25 Mbps".
- `expected_people_lifted` is people × the chance of being below 25 Mbps × the measured share a site lifts (different for a new site and for co-location); it is an expectation, so round it and call it "about". Sites are ranked by it, largest first.
- `cost_new_tower_equivalents`: 1.0 = a new macro tower, 0.5 = a small cell, 0.3 = co-location on an existing tower (the API calls it `capacity`). The plan's budget is 1,000 tower-equivalents per country.
- **Coverage gap** means people are slow because there is little or no signal; **capacity gap** means signal exists but the network is congested. They need different fixes (new site vs co-location or capacity), so name the type.
- `people_kontur` and `people_worldpop` are two independent population estimates; a site's `people` is the smaller of the two (a conservative planning figure). When they differ a lot, say so.
- Speeds are crowdsourced tests for one quarter (`quarter` in `countries`); untested hexagons have estimated speeds (`tested: false`).

## What to include in an answer

- The direct answer first, in one or two sentences, in operational units (people, Mbps, sites, tower-equivalents).
- For shortlists: a small table with rank, district, intervention, cost, people and expected people lifted; mention that the plan was checked on the ground (`checked_on_ground`) when true.
- One line of caveats when they matter: estimated (untested) speeds, a large gap between the two population maps, or a single-quarter snapshot.
- The data licence when the user may reuse the numbers: speed data is Ookla Open Data under **CC BY-NC-SA 4.0 (non-commercial)**; derived data is shared under the same terms.

## Limits

Seven countries only; one quarter of speed tests; public data, not operator network data; no live traffic, interference or backhaul. Site notes are cached or templated text checked by a grader, so they never add facts beyond the API's numbers.
