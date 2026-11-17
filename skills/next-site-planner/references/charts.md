# Table, chart or neither

The reader should get the answer in about five seconds from the headline and one visual. Pick the visual by what the reader must do with the numbers, not by what looks impressive.

## Which visual

| The reader must... | Use | Command |
|---|---|---|
| Take in one place's answer (a few numbers) | **No chart**: a bold headline and 2–4 numbered points, plus the **map**: hexagons shaded by chance of being slow (orange scale), the point in blue, places in aqua, masts in violet, buildings outlined, and a panel with the numbers | `map gap LAT LON` |
| Compare before → after for each item (KPI baseline vs plan) | **Paired horizontal bars**, baseline grey, plan blue, the multiple printed at the end | `chart countries` |
| Rank items and tell a few types apart (a shortlist by build type) | **Ranked horizontal bars**, largest first, colour = type (at most 3), value printed | `chart sites COUNTRY --k N` |
| Read exact values across several columns (cost, people, chance) | **Table** (put it after the chart, or alone for 5 or fewer rows the reader will copy) | — |
| See where places are | **Map** | `map sites COUNTRY` |
| Follow a trend over time | **Line chart** (not available here: the API serves one quarter) | — |
| See how a budget flows to build types and people | **Sankey**, only when the question is about the flow itself; otherwise ranked bars | — |
| See the parts of one whole | **Segmented or ranked bar**; a pie only for 2–3 parts read as a rough split | — |

Never: two y-axes on one chart, 3D, more than three colours for categories, or a chart that repeats a table beside it without adding something.

## Writing for five seconds

1. **Data line** (one line, small): sources, period, check date.
2. **Headline** in bold: the answer in one sentence with the key number.
3. **2–4 numbered points**: the baseline, the reason, the one caveat that changes a decision.
4. **One visual** from the table above, with its file path.
5. **To sharpen this** (one line): the inputs that would turn an estimate into a decision.

Aim for about 10 lines of text before the visual. If a point does not change what the reader would decide, cut it.
