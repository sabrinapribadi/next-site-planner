"""ADR-003 P1 check: population share by Degree of Urbanisation class vs the published GHSL figures.

    python scripts/degurba_check.py

Published: JRC GHSL country statistics (GHS-COUNTRY-STATS_MT_GLOBE_R2024A, sheet POP_L1): national population per
grid class (urban centre, urban cluster, rural), from GHS-SMOD and GHS-POP. Ours: P1 morphology on H3 resolution 8 with
Kontur 2023 population (ADR-003 E2). Pre-set rule (ADR-003): a gap above 10 percentage points is investigated.
Compared at the published epoch nearest to 2023 (both nearest epochs reported when 2023 lies between two).

Decomposition of the gap (ADR-003's pre-set follow-up: cross-check with GHS-SMOD): urban-centre share under
  rule × population = {ours, GHS-SMOD 2025 class at the hexagon centre} × {Kontur 2023, WorldPop 2020}.
If "SMOD × Kontur" is close to the published figure, our rule causes the gap; if close to ours, the population map does.
Writes data/outputs/p1c_degurba_check.json.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import h3
import numpy as np
import pandas as pd
import rasterio
import yaml
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.morphology import degree_of_urbanisation  # noqa: E402
CFG = yaml.safe_load((ROOT / "configs" / "default_config.yaml").read_text())
DATA = Path(os.environ.get("GEO_DATA_DIR", "~/data/geo")).expanduser()
XLSX = DATA / "ghsl/country_stats/GHS-COUNTRY-STATS_MT_GLOBE_R2024_V1_0.xlsx"
OURS = {"urban_centre": "UC", "urban_cluster": "UCL", "rural": "RUR"}
GAP_PTS = 10.0
SMOD = DATA / "ghsl/smod2025/GHS_SMOD_E2025_GLOBE_R2023A_4326_30ss_V2_0.tif"
SMOD_L1 = {30: "urban_centre", 23: "urban_cluster", 22: "urban_cluster", 21: "urban_cluster", 13: "rural", 12: "rural", 11: "rural", 10: "rural"}


def smod_class(h3s: pd.Series) -> np.ndarray:
    """GHS-SMOD 2025 class at each hexagon centre (one windowed read per country)."""
    ll = np.array([h3.cell_to_latlng(x) for x in h3s])
    with rasterio.open(SMOD) as r:
        w = from_bounds(ll[:, 1].min() - 0.05, ll[:, 0].min() - 0.05, ll[:, 1].max() + 0.05, ll[:, 0].max() + 0.05, r.transform).round_offsets().round_lengths()
        a = r.read(1, window=w); t = r.window_transform(w)
    rows = np.clip(((ll[:, 0] - t.f) / t.e).astype(int), 0, a.shape[0] - 1); cols = np.clip(((ll[:, 1] - t.c) / t.a).astype(int), 0, a.shape[1] - 1)
    return np.array([SMOD_L1.get(int(v), "rural") for v in a[rows, cols]])


def shares(cls: np.ndarray, pop: np.ndarray) -> dict:
    tot = pop.sum()
    return {c: float(pop[cls == c].sum() / tot) for c in OURS}


def main() -> None:
    pop = pd.read_excel(XLSX, sheet_name="POP_L1")
    years = sorted(int(c) for c in pop.columns if str(c).replace(".0", "").isdigit())
    near = sorted(years, key=lambda y: abs(y - 2023))[:2]
    p1 = json.loads((ROOT / "data/outputs/p1_experience_gap.json").read_text())["countries"]
    out = {}
    for k in CFG["countries"]:
        g = pop[pop.GADM_ISO == k]
        if g.empty:
            out[k] = None; continue
        pub = {}
        for y in near:
            col = next(c for c in g.columns if str(c).replace(".0", "") == str(y))
            tot = float(g[col].sum())
            pub[str(y)] = {cls: float(g.loc[g.DEGURBA_L1 == code, col].sum() / tot) for cls, code in OURS.items()}
            pub[str(y)]["population"] = tot
        ours = {cls: float(p1[k]["morphology"][cls]["population_share"]) for cls in OURS}
        hp = pd.read_parquet(DATA / "derived/hex_p1.parquet", columns=["iso3", "h3", "population", "morphology"]).query("iso3 == @k and population > 0")
        wp = pd.read_parquet(DATA / f"derived/hex_worldpop_{k}.parquet")
        wp = wp[wp.wp_population > 0].reset_index(drop=True)
        wp_rule = degree_of_urbanisation(wp.h3, wp.wp_population, CFG["morphology"]).to_numpy()
        decomp = {"ours_rule_kontur": ours,
                  "smod_kontur": shares(smod_class(hp.h3), hp.population.to_numpy()),
                  "ours_rule_worldpop": shares(wp_rule, wp.wp_population.to_numpy()),
                  "smod_worldpop": shares(smod_class(wp.h3), wp.wp_population.to_numpy())}
        y0 = str(near[0])
        gaps = {cls: 100 * (ours[cls] - pub[y0][cls]) for cls in OURS}
        out[k] = {"ours_kontur_2023": ours, "published": pub, "compared_epoch": int(y0), "gap_pts": gaps, "decomposition_urban_centre": {kk: v["urban_centre"] for kk, v in decomp.items()},
                  "decomposition": decomp,
                  "urban_centre_gap_over_10_pts": abs(gaps["urban_centre"]) > GAP_PTS,
                  "any_class_gap_over_10_pts": any(abs(v) > GAP_PTS for v in gaps.values())}
        print(k, f"urban centre ours {100 * ours['urban_centre']:.1f}% vs GHSL {y0} {100 * pub[y0]['urban_centre']:.1f}% "
                 f"(gap {gaps['urban_centre']:+.1f} pts) | cluster {gaps['urban_cluster']:+.1f} | rural {gaps['rural']:+.1f} || urban centre: "
                 + " · ".join(f"{kk} {100 * v['urban_centre']:.1f}%" for kk, v in decomp.items()), flush=True)
    res = {"design": "ADR-003 P1 check (reported, not gated)", "source": "JRC GHSL GHS-COUNTRY-STATS_MT_GLOBE_R2024A, sheet POP_L1 (grid classes)",
           "epochs_available": years, "compared_epoch_rule": "published epoch nearest to 2023", "gap_rule_pts": GAP_PTS,
           "scope_note": "GHSL totals are whole countries (France with overseas departments, the US with Alaska, Hawaii and territories); ours are metropolitan France and the lower 48",
           "countries": out}
    (ROOT / "data/outputs/p1c_degurba_check.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
