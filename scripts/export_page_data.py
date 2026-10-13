"""Data for the results page (docs/index.html): writes docs/data/page_data.js (window.GEO1 = {...}).

    python scripts/export_page_data.py

Every number on the page comes from data/outputs/p0_foundation.json, p1_experience_gap.json and the P1 hexagon layer.
Map: populated H3 r8 hexagons rolled up to resolution 5 (~250 km²) per country, as compact columns:
  h  — resolution-5 cell id without its constant 'fffffff' tail
  p  — people (thousands, 1 decimal)
  m  — share of people living in measured hexagons (%)
  b  — for each bar (5, 10, 25, 50, 100 Mbps): share of measured people below it (%), -1 if nothing measured
  n  — index into the country's place-name list: "district, province/state" (geoBoundaries ADM2 + ADM1; the
       nearest district when a cell's centre falls just offshore)
District detail (analysis resolution): every district in a country's top-10 list at any bar gets docs/data/d/<ISO>_<n>.js,
loaded on demand, with its H3 r8 hexagons (~0.74 km²): people, measured Mbps (-1 untested), gap type at 25 Mbps,
area type, slow-cluster flag, and — once P2 has run — predicted Mbps and sigma (log scale) for untested hexagons.
Derived maps follow the Ookla licence (CC BY-NC-SA 4.0); the page says so.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import geopandas as gpd
os.environ.setdefault("OGR_GEOJSON_MAX_OBJ_SIZE", "0")  # Philippine provinces are single very large GeoJSON features
import h3
import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CFG = yaml.safe_load((ROOT / "configs" / "default_config.yaml").read_text())
DATA = Path(os.environ.get("GEO_DATA_DIR", "~/data/geo")).expanduser()
OUT = ROOT / "docs" / "data" / "page_data.js"
BARS = [5, 10, 25, 50, 100]
NAMES = CFG["countries"]
TAIL = "fffffff"


def place_names(iso3: str, cells: list[str]) -> tuple[list[str], list[int]]:
    """'District, Province' for each resolution-5 cell centre, from geoBoundaries ADM2 and ADM1."""
    pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy([h3.cell_to_latlng(c)[1] for c in cells], [h3.cell_to_latlng(c)[0] for c in cells]), crs=4326)
    parts = []
    for lvl in ("ADM2", "ADM1"):
        f = DATA / "boundaries" / "gb" / f"{iso3}_{lvl}.geojson"
        if not f.exists():
            parts.append([None] * len(cells)); continue
        b = gpd.read_file(f, columns=["shapeName"], engine="pyogrio").to_crs(4326)
        j = gpd.sjoin(pts, b, predicate="within", how="left")
        j = j[~j.index.duplicated()]
        miss = j["shapeName"].isna()
        if miss.any():
            nn = gpd.sjoin_nearest(pts[miss.to_numpy()].to_crs(3857), b.to_crs(3857), how="left")
            nn = nn[~nn.index.duplicated()]
            j.loc[nn.index, "shapeName"] = nn["shapeName"]
        parts.append(j["shapeName"].tolist())
        del b
    labels = [a if not b or a == b else (b if not a else f"{a}, {b}") for a, b in zip(*parts)]
    names = sorted(set(labels))
    pos = {n: i for i, n in enumerate(names)}
    return names, [pos[x] for x in labels]


def map_layer(h: pd.DataFrame, iso3: str) -> dict:
    h = h.assign(r5=[h3.cell_to_parent(x, 5) for x in h["h3"]])
    meas = h["mobile_down_mbps"].notna()
    g = h.assign(pm=h["population"] * meas, **{f"pb{b}": h["population"] * meas * (h["mobile_down_mbps"] < b) for b in BARS})
    a = g.groupby("r5")[["population", "pm"] + [f"pb{b}" for b in BARS]].sum()
    a = a[a["population"] > 0]
    assert all(x.endswith(TAIL) for x in a.index)
    with np.errstate(invalid="ignore", divide="ignore"):
        b = [[int(round(100 * v)) if pm > 0 else -1 for v, pm in zip(a[f"pb{bar}"] / a["pm"], a["pm"])] for bar in BARS]
    names, idx = place_names(iso3, list(a.index))
    return {"h": [x[: -len(TAIL)] for x in a.index], "p": [round(v / 1000, 1) for v in a["population"]],
            "m": [int(round(100 * v)) for v in a["pm"] / a["population"]], "b": b, "names": names, "n": idx}


GAP = {"none": 0, "capacity": 1, "coverage": 2, "slow_type_unknown": 3, "unmeasured": 4}
MOR = {"rural": 0, "urban_cluster": 1, "urban_centre": 2}
DDIR = ROOT / "docs" / "data" / "d"
NOISE = None   # set in main() from derived/hex_noise.parquet when the ADR-005 follow-up has run


def district_details(iso3: str, hk: pd.DataFrame, m: dict, p2: pd.DataFrame | None) -> list[int]:
    """Write one on-demand file per district in the top-10 list at any bar; return their name indices."""
    keep = set()
    for bi, _ in enumerate(BARS):
        v = pd.Series([0 if b < 0 else p * 1000 * mm / 100 * b / 100 for p, mm, b in zip(m["p"], m["m"], m["b"][bi])])
        keep |= set(v.groupby(pd.Series(m["n"])).sum().sort_values(ascending=False).head(10).index)
    r5 = pd.Series([h3.cell_to_parent(x, 5)[: -len(TAIL)] for x in hk["h3"]], index=hk.index)
    name_of_r5 = dict(zip(m["h"], m["n"]))
    hk = hk.assign(nidx=r5.map(name_of_r5))
    if p2 is not None:
        hk = hk.merge(p2[p2["iso3"] == iso3][["h3", "pred_ln", "sigma"]], on="h3", how="left")
    if NOISE is not None:
        hk = hk.merge(NOISE[NOISE["iso3"] == iso3][["h3", "post_mean", "post_var"]], on="h3", how="left")
    for n in sorted(keep):
        d = hk[hk["nidx"] == n]
        assert all(x.endswith("fffff") for x in d["h3"])
        out = {"h": [x[:-5] for x in d["h3"]], "p": [int(round(v)) for v in d["population"]],
               "s": [round(v, 1) if v == v else -1 for v in d["mobile_down_mbps"]],
               "g": [GAP.get(v, 4) for v in d["gap_25"]], "a": [MOR.get(v, 0) for v in d["morphology"]],
               "x": [1 if v is True else 0 for v in d["slow_hotspot"]]}
        if p2 is not None:
            out["pm"] = [round(float(np.exp(v)), 1) if v == v else -1 for v in d["pred_ln"]]
            out["sg"] = [round(float(v), 3) if v == v else -1 for v in d["sigma"]]
        if NOISE is not None:   # typical (noise-corrected) speed of tested hexagons
            out["tm"] = [round(float(np.exp(v)), 1) if v == v else -1 for v in d["post_mean"]]
            out["ts"] = [round(float(np.sqrt(v)), 3) if v == v else -1 for v in d["post_var"]]
        (DDIR / f"{iso3}_{n}.js").write_text(f'(window.GEO1_D = window.GEO1_D || {{}})["{iso3}_{n}"] = ' + json.dumps(out, separators=(",", ":")) + ";\n")
    return sorted(int(n) for n in keep)


def main() -> None:
    p0 = json.loads((ROOT / "data/outputs/p0_foundation.json").read_text())
    p1 = json.loads((ROOT / "data/outputs/p1_experience_gap.json").read_text())
    hex8 = pd.read_parquet(DATA / "derived" / "hex_p1.parquet")
    p2f = DATA / "derived" / "hex_p2.parquet"
    p2 = pd.read_parquet(p2f, columns=["iso3", "h3", "pred_ln", "sigma"]) if p2f.exists() else None
    global NOISE
    nf = DATA / "derived" / "hex_noise.parquet"
    NOISE = pd.read_parquet(nf, columns=["iso3", "h3", "post_mean", "post_var"]) if nf.exists() else None
    p2j = json.loads((ROOT / "data/outputs/p2_speed_model.json").read_text()) if (ROOT / "data/outputs/p2_speed_model.json").exists() else None
    p2b = json.loads((ROOT / "data/outputs/p2b_noise_followup.json").read_text()) if (ROOT / "data/outputs/p2b_noise_followup.json").exists() else None
    p2c = json.loads((ROOT / "data/outputs/p2c_noise_validation.json").read_text()) if (ROOT / "data/outputs/p2c_noise_validation.json").exists() else None
    DDIR.mkdir(parents=True, exist_ok=True)
    for f in DDIR.glob("*.js"):
        f.unlink()
    countries = {}
    for k, r in p1["countries"].items():
        pop, ms = r["population"], r["measured_share"]
        c = {"name": NAMES[k], "population_m": round(pop / 1e6, 2), "measured_share": round(ms, 4),
             "unmeasured_people_m": round(pop * (1 - ms) / 1e6, 2),
             "below": {str(b): round(r[f"below_{b}"], 4) for b in BARS},
             "people_below_m": {str(b): round(r[f"below_{b}"] * ms * pop / 1e6, 2) for b in BARS},
             "ci95": {str(b): [round(x, 4) for x in r[f"below_{b}_ci95"]] for b in CFG["experience"]["thresholds_mbps"]},
             "ci95_tile_bootstrap": {str(b): [round(x, 4) for x in r[f"below_{b}_ci95_tile_bootstrap_preregistered"]] for b in CFG["experience"]["thresholds_mbps"]},
             "density_adjusted": {str(b): round(r[f"below_{b}_density_adjusted"], 4) for b in CFG["experience"]["thresholds_mbps"]},
             "morphology": {m: {"share": round(v["population_share"], 4), "measured": round(v["measured_share"], 4),
                                "below_10": round(v["below_10"], 4), "below_25": round(v["below_25"], 4)} for m, v in r["morphology"].items()},
             "gap_types_25": {t: round(v, 4) for t, v in r["gap_types"]["25"].items()},
             "opencellid_detection": {m: round(v, 3) for m, v in r["opencellid_detection_in_fast_hexagons"].items()},
             "near_5g_record": round(r["people_near_opencellid_5g_record"], 4),
             "hotspots": r["hotspots"],
             "p0": {kk: p0["countries"][k][kk] for kk in ("population_assigned", "tests_assigned", "kontur_vs_world_bank", "hexagons")}}
        hk = hex8[hex8["iso3"] == k]
        hs = hk[hk["slow_hotspot"] == True]  # noqa: E712
        c["hotspot_cells"] = [[x, round(p), round(s, 1)] for x, p, s in zip(hs["h3"], hs["population"], hs["mobile_down_mbps"])]
        c["map"] = map_layer(hk, k)
        c["detail"] = district_details(k, hk, c["map"], p2)
        if p2j:
            d6 = p2j["designs"]["r6"]
            c["p2"] = {"rmse_kriging": round(d6["per_country"][k]["kriging"], 3), "rmse_gbm": round(d6["per_country"][k]["gbm"], 3),
                       "loco_rmse": round(p2j["leave_one_country_out"][k]["rmse"], 3)}
        if p2b and p2c:
            corr, tot, val = p2b["p1_noise_corrected"][k], p2b["totals"][k], p2c[k]
            credible = abs(val["q3_noisy_share_predicted_from_shrunk_q2"] - val["q3_raw_share_below_25"]) <= 0.015
            c["noise"] = {"corrected_below": {str(b): round(corr[f"below_{b}"], 4) for b in BARS},
                          "corrected_ci95": {str(b): [round(x, 4) for x in corr[f"below_{b}_ci95"]] for b in (10, 25)},
                          "level_credible": bool(credible),
                          "validation": {kk: round(vv, 4) if isinstance(vv, float) else vv for kk, vv in val.items()},
                          "s2_test": round(p2b["noise_model"][k]["s2_test"], 3), "s2_micro": round(p2b["noise_model"][k]["s2_micro"], 3)}
            c["untested"] = {"people_m": round(tot["untested_people"] / 1e6, 2),
                             "expected_below_m": {str(b): round(tot[f"expected_untested_below_{b}"] / 1e6, 2) for b in BARS},
                             "all_people_share_below": {str(b): round(tot[f"all_people_share_below_{b}"], 4) for b in BARS}}
        countries[k] = c
        print(k, len(c["map"]["h"]), "map cells,", len(c["hotspot_cells"]), "hotspot hexagons,", len(c["detail"]), "district files", flush=True)
    page = {"quarter": p1["quarter"], "bars": BARS, "countries": countries, "has_p2": p2 is not None,
            "p2": None if not p2j else {k_: {"rmse": round(v["kriging"]["rmse"], 3), "gbm": round(v["gbm"]["rmse"], 3), "ratio": round(v["ratio_gbm_vs_kriging"], 3)} for k_, v in p2j["designs"].items()}
                  | {"gate_passed": p2j["gate_passed"], "coverage_80": round(p2j["uncertainty"]["coverage_80"], 3), "auc_below_25": round(p2j["uncertainty"]["auc_below_25"], 3),
                     "aoa_people_inside": round(p2j["area_of_applicability"]["untested_people_inside"], 3), "gap_followup_auc": round(p2j["gap_type_followup"]["block_cv_auc"], 3),
                     "naive": round(p2j["designs"]["r6"]["naive"]["rmse"], 3), "covariates_only": round(p2j["designs"]["r6"]["gbm_covariates_only"]["rmse"], 3),
                     "distance_matched": {m: round(p2j["designs"]["r6"][m]["rmse_distance_matched"], 3) for m in ("kriging", "gbm")},
                     "people_weighted": {m: round(p2j["designs"]["r6"][m]["rmse_people_weighted"], 3) for m in ("kriging", "gbm")}},
            "noise_scores": None if not p2b else {m: {kk: round(vv, 3) for kk, vv in v.items()} for m, v in p2b["p2_noise_aware_scores"].items() if isinstance(v, dict)},
            "p0": {"gate_passed": p0["gate_passed"], "panel_rows": p0["panel_rows"], "inputs": p0["inputs_in_manifest"]},
            "p1": {"gate_passed": p1["gate_passed"], "density_deciles_edges": p1["density_deciles_edges_people_per_hex"]}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("// Generated by scripts/export_page_data.py from data/outputs/*.json — do not edit by hand.\nwindow.GEO1 = "
                   + json.dumps(page, separators=(",", ":")) + ";\n")
    print(f"{OUT.relative_to(ROOT)}: {OUT.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
