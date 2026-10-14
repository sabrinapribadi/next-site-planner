"""Kontur vs WorldPop for the earlier headline counts (ADR-001 falsification row 3; ADR-008 amendment 1, check A).

    python scripts/population_crosscheck.py

Per country, under Kontur 2023, WorldPop 2020 and the smaller of the two per hexagon:
- total people;
- people in tested hexagons whose typical speed is below 25 Mbps (P1's single-quarter measure);
- expected people below 25 Mbps, tested (noise-corrected) and untested (kriging), as used in P4;
- share of people in hexagons where the two sources disagree by more than 3× ((larger + 100) ÷ (smaller + 100)).
Writes data/outputs/p1b_population_crosscheck.json.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
import site_plan as sp  # noqa: E402

RATIO = 3.0


def main() -> None:
    t0 = time.time()
    isos = [k for k in sp.CFG["countries"] if (sp.DER / f"hex_worldpop_{k}.parquet").exists()]
    if len(isos) < len(sp.CFG["countries"]):
        sp.log("WorldPop missing for", sorted(set(sp.CFG["countries"]) - set(isos)), "- interim run; listed as pending")
    wp = pd.concat([pd.read_parquet(sp.DER / f"hex_worldpop_{k}.parquet") for k in isos])
    p1 = pd.read_parquet(sp.DER / "hex_p1.parquet", columns=["iso3", "h3", "population", "mobile_down_mbps"])
    d = sp.load()                                            # Kontur-populated hexagons with typical speed and P(< 25)
    out = {}
    for k in isos:
        w = wp[wp.iso3 == k]
        a = p1[p1.iso3 == k].merge(w[["h3", "wp_population"]], on="h3", how="outer").fillna({"population": 0, "wp_population": 0})
        a["low"] = np.minimum(a.population, a.wp_population)
        ratio = (np.maximum(a.population, a.wp_population) + 100) / (np.minimum(a.population, a.wp_population) + 100)
        slow_tested = a.mobile_down_mbps < 25
        x = d[d.iso3 == k].merge(w[["h3", "wp_population"]], on="h3", how="left").fillna({"wp_population": 0})
        x["low"] = np.minimum(x.population, x.wp_population)
        x_ratio = (np.maximum(x.population, x.wp_population) + 100) / (np.minimum(x.population, x.wp_population) + 100)
        poor = x.p25 >= 0.5
        e = lambda col, m: float((x[col] * x.p25)[m].sum())
        r = {
            "total": {"kontur": float(a.population.sum()), "worldpop": float(a.wp_population.sum()), "smaller": float(a.low.sum())},
            "tested_below_25_p1": {"kontur": float(a.population[slow_tested].sum()), "worldpop": float(a.wp_population[slow_tested].sum()),
                                   "smaller": float(a.low[slow_tested].sum())},
            "expected_below_25_all": {c: e(c, slice(None)) for c in ("population", "wp_population", "low")},
            "expected_below_25_untested": {c: e(c, ~x.tested) for c in ("population", "wp_population", "low")},
            "people_in_poorly_served_hexagons": {"kontur": float(x.population[poor].sum()), "worldpop": float(x.wp_population[poor].sum())},
            "kontur_share_in_disagreeing_hexagons": float(a.population[ratio > RATIO].sum() / a.population.sum()),
            "kontur_share_in_disagreeing_poorly_served": float(x.population[poor & (x_ratio > RATIO)].sum() / max(x.population[poor].sum(), 1)),
            "worldpop_people_outside_kontur_hexagons": float(a.wp_population[a.population == 0].sum()),
        }
        for blk in ("expected_below_25_all", "expected_below_25_untested"):
            r[blk] = {"kontur": r[blk].pop("population"), "worldpop": r[blk].pop("wp_population"), "smaller": r[blk].pop("low")}
        pp = r["people_in_poorly_served_hexagons"]
        r["adr001_poorly_served_difference"] = pp["worldpop"] / pp["kontur"] - 1 if pp["kontur"] else None
        r["adr001_row3_triggered"] = bool(r["adr001_poorly_served_difference"] is not None and abs(r["adr001_poorly_served_difference"]) > 0.10)
        out[k] = r
        m = lambda v: f"{v / 1e6:,.2f}M"
        sp.log(k, f"total K {m(r['total']['kontur'])} WP {m(r['total']['worldpop'])} | expected < 25 K {m(r['expected_below_25_all']['kontur'])} "
                  f"WP {m(r['expected_below_25_all']['worldpop'])} min {m(r['expected_below_25_all']['smaller'])} | untested K {m(r['expected_below_25_untested']['kontur'])} "
                  f"WP {m(r['expected_below_25_untested']['worldpop'])} | poorly served diff {r['adr001_poorly_served_difference']:+.1%} | "
                  f"disagree > 3×: {r['kontur_share_in_disagreeing_hexagons']:.1%} of people, {r['kontur_share_in_disagreeing_poorly_served']:.1%} in poorly served")
    tot = lambda blk, c: sum(v[blk][c] for v in out.values())
    summary = {blk: {c: tot(blk, c) for c in ("kontur", "worldpop", "smaller")} for blk in ("total", "tested_below_25_p1", "expected_below_25_all", "expected_below_25_untested")}
    res = {"design": "ADR-001 falsification row 3; ADR-008 amendment 1 check A", "worldpop": "2020 constrained UN-adjusted 100 m",
           "kontur": "2023-11-01 H3 r8", "disagreement_ratio": RATIO, "countries": out, "all_countries": summary, "seconds": round(time.time() - t0)}
    res["pending_countries"] = [k for k in sp.CFG["countries"] if k not in isos]   # WorldPop still downloading
    (ROOT / sp.CFG["paths"]["outputs_dir"] / "p1b_population_crosscheck.json").write_text(json.dumps(res, indent=1))
    sp.log(f"all {len(isos)} countries", {b: {c: round(v / 1e6, 2) for c, v in s.items()} for b, s in summary.items()})


if __name__ == "__main__":
    main()
