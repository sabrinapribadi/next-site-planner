"""Serving store for the planner API and MCP tools (ADR-009): small, read-only, rebuilt from the outputs.

    python scripts/build_serving_store.py

Writes GEO_DATA_DIR/serving/ (never the repository):
- hexes.parquet      one row per populated 0.74 km² hexagon: people on both maps, typical speed, chance below
                     10 / 25 Mbps, tested or predicted, area type, gap type, district; sorted by h3 for fast lookups
- plans.parquet      the checked site plans (docs/data/plans/*.csv), with the country
- countries.json     per-country summary (P1 shares, untested people, P3 lift, P4 plan) and the population range
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import h3
import numpy as np
import pandas as pd
import yaml
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
CFG = yaml.safe_load((ROOT / "configs" / "default_config.yaml").read_text())
DATA = Path(os.environ.get("GEO_DATA_DIR", "~/data/geo")).expanduser()
DER, OUT = DATA / "derived", DATA / "serving"
log = lambda *a: print(time.strftime("%H:%M:%S"), *a, flush=True)


def district_names() -> dict:
    js = (ROOT / "docs/data/page_data.js").read_text()
    G = json.loads(js[js.index("window.GEO1 = ") + len("window.GEO1 = "):].rstrip().rstrip(";"))
    return {h + "fffffff": m["names"][n] for c in G["countries"].values() for m in [c["map"]] for h, n in zip(m["h"], m["n"])}, G


def main() -> None:
    t0 = time.time(); OUT.mkdir(parents=True, exist_ok=True)
    names, G = district_names()
    p1 = pd.read_parquet(DER / "hex_p1.parquet", columns=["iso3", "h3", "population", "mobile_down_mbps", "mobile_tests", "morphology", "gap_25"])
    noise = pd.read_parquet(DER / "hex_noise.parquet", columns=["iso3", "h3", "post_mean", "post_var"])
    p2 = pd.read_parquet(DER / "hex_p2.parquet", columns=["iso3", "h3", "pred_ln", "sigma"])
    wp = pd.concat([pd.read_parquet(f) for f in sorted(DER.glob("hex_worldpop_*.parquet"))])[["iso3", "h3", "wp_population"]]
    d = p1[p1.population > 0].merge(noise, on=["iso3", "h3"], how="left").merge(p2, on=["iso3", "h3"], how="left").merge(wp, on=["iso3", "h3"], how="left")
    have_wp = set(wp.iso3)
    d["tested"] = d.post_mean.notna()
    ln = np.where(d.tested, d.post_mean, d.pred_ln); sd = np.where(d.tested, np.sqrt(d.post_var), d.sigma)
    d = d.assign(typical_mbps=np.round(np.exp(ln), 1), p_below_10=np.round(norm.cdf((np.log(10) - ln) / sd), 3),
                 p_below_25=np.round(norm.cdf((np.log(25) - ln) / sd), 3))
    d["worldpop_people"] = np.where(d.iso3.isin(have_wp), d.wp_population.fillna(0).round(), np.nan)
    d["district"] = d.h3.map(lambda x: names.get(h3.cell_to_parent(x, 5), ""))
    hexes = d.rename(columns={"population": "kontur_people", "mobile_down_mbps": "measured_mbps", "mobile_tests": "tests", "gap_25": "gap_type_25"})[
        ["h3", "iso3", "district", "kontur_people", "worldpop_people", "tested", "tests", "measured_mbps", "typical_mbps", "p_below_10", "p_below_25", "morphology", "gap_type_25"]]
    hexes = hexes[hexes.typical_mbps.notna()].sort_values("h3").reset_index(drop=True)
    hexes.to_parquet(OUT / "hexes.parquet", index=False, row_group_size=50_000)
    plans = pd.concat([pd.read_csv(f).assign(iso3=f.stem) for f in sorted((ROOT / "docs/data/plans").glob("*.csv"))], ignore_index=True)
    plans.to_parquet(OUT / "plans.parquet", index=False)
    p4 = json.loads((ROOT / "data/outputs/p4_site_plan.json").read_text())["countries"]
    countries = {}
    for k, c in G["countries"].items():
        v = p4[k]; hb = v["budgets"][str(v["headline_budget"])]
        countries[k] = {"name": c["name"], "population_m": c["population_m"], "tested_share": c["measured_share"],
                        "below_tested": c["below"], "below_everyone": c["untested"]["all_people_share_below"],
                        "untested_people_m": c["untested"]["people_m"], "untested_likely_below_m": c["untested"]["expected_below_m"],
                        "population_check": c.get("population_check"),
                        "new_site_lift_pts": (round(100 * c["p3"]["crossing_cautious"]["att"], 1) if c.get("p3", {}).get("crossing_cautious") else None),
                        "plan": {"budget": v["headline_budget"], "people_lifted": round(hb["people_lifted"]), "kpi_ranking": round(hb["kpi_ranking"]),
                                 "gain_vs_kpi": None if hb["gain_vs_kpi"] is None else round(hb["gain_vs_kpi"], 3), "sites": hb["sites"], "mix": hb["mix"],
                                 "checked_on_ground": bool(v.get("validated", False)),
                                 "theta_new": round(v["theta"]["new"][0], 3), "theta_capacity": round(v["theta"]["capacity"][0], 3)}}
    (OUT / "countries.json").write_text(json.dumps({"bars_mbps": G["bars"], "quarter": G["quarter"], "countries": countries}, indent=1))
    log(f"serving store: {len(hexes):,} hexagons, {len(plans):,} nominals, {len(countries)} countries → {OUT} ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
