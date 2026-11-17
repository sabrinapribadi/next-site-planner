# Field reference

Every field the four calls return, with what it means and how to say it. Units are in the field names.

## `countries` (one row per country)

| Field | Meaning | Say it like |
|---|---|---|
| `bar_mbps` | The speed bar used for this table (default 25) | "below 25 Mbps" |
| `quarter` | The Ookla quarter the speeds come from | "speed tests from 2026 Q3" |
| `population_millions` | Population covered by populated hexagons (Kontur) | "about 270 million people" |
| `tested_share` | Share of people living in hexagons with at least one speed test | "65% of people live where speeds were measured" |
| `share_below_bar_tested` | Of people in tested hexagons, share whose typical speed is below the bar | |
| `share_below_bar_everyone` | Same, including untested hexagons with estimated speeds | "about 18% of everyone" |
| `people_below_bar_everyone_millions` | People below the bar, tested and estimated | "about 49 million people" |
| `untested_people_likely_below_bar_millions` | People in untested hexagons likely below the bar | the hidden part of the problem |
| `plan_people_lifted` | Expected people lifted above the bar by the country's plan | "about 122,500 people" |
| `plan_gain_vs_kpi` | **Relative** gain over ranking sites by weighted KPIs at the same budget | 1.85 → "185% more people, 2.85× as many" |
| `plan_checked_on_ground` | The plan's nominals were checked against land cover and slope | |

## `gap` (one 0.74 km² hexagon)

| Field | Meaning |
|---|---|
| `h3` | H3 cell id (resolution 8) |
| `district` | Administrative area name |
| `people_kontur`, `people_worldpop` | Two independent population estimates; `people_worldpop` can be null |
| `tested`, `tests` | Whether speeds were measured here, and how many tests |
| `typical_mbps` | Typical (median) download speed; estimated if `tested` is false |
| `chance_below_10_mbps`, `chance_below_25_mbps` | Probability that typical speed is below the bar |
| `area_type` | Morphology: `urban_centre`, `urban_cluster` or `rural` |
| `gap_type_25_mbps` | `no gap`, `coverage gap` (little or no signal), `capacity gap` (signal but congested), `slow, type unknown`, `not tested` |
| `in_plan` | The planned site at this hexagon, if the plan chose it; null otherwise |

## `sites` (a country's plan, best first)

| Field | Meaning |
|---|---|
| `budget_new_tower_equivalents` | The plan's budget: 1,000 tower-equivalents |
| `rank` | Order by expected people lifted, largest first. The budgeted optimiser chose the set of sites (most people lifted within the budget); rank only orders them |
| `intervention` | `macro` (new tower), `small_cell`, `capacity` (co-location on an existing tower) |
| `cost_new_tower_equivalents` | 1.0 macro, 0.5 small cell, 0.3 co-location (FCC 17-126 cost ratios) |
| `people` | People in the site's area used for planning: the smaller of the two estimates (Kontur, WorldPop), sometimes capped further by built-up area, so it is conservative |
| `chance_below_25_mbps` | Probability the area is below 25 Mbps |
| `expected_people_lifted` | people × chance below 25 Mbps × the measured share a site lifts (different for a new site and for co-location); round it ("about 2,100") |
| `site_lat`, `site_lon` | Nominal location |
| `built_up_m2`, `elevation_m`, `slope_deg`, `steep`, `high` | Ground check: hexagons with under 1,000 m² of built-up land are rejected; `steep` (slope above 20°) and `high` (above 2,500 m) are flags that raise access and build cost, not rejections |
| `checked_on_ground` | The nominal passed the ground check |

## `note` (one planned site)

| Field | Meaning |
|---|---|
| `note` | A short plain-language note; every number in it is traced to `site` |
| `source` | `model` if a language model wrote it and it passed the grader, else `template` |
| `grader` | The checks the note passed (no unknown numbers, no names, no promises) |
| `meter` | Tokens, latency and cost of producing the note; `cached: true` costs nothing |

## Licence

Speed data: Speedtest by Ookla Global Fixed and Mobile Network Performance Maps, **CC BY-NC-SA 4.0 (non-commercial)**. Population: Kontur and WorldPop (CC BY 4.0). Land cover: ESA WorldCover (CC BY 4.0). Elevation: Copernicus DEM GLO-30. Derived data: CC BY-NC-SA 4.0.
