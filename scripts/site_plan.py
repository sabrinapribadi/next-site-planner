"""P4: budgeted site plan per country (ADR-008).

    python scripts/site_plan.py

Benefit of an intervention in hexagon h = people_h × P(typical speed_h < 25 Mbps) × θ, where θ is the measured lift
rate (P3 / ADR-008): new site where no LTE/5G cell is recorded within ring 1 (macro 1.0, small cell 0.5 in urban
centres), added capacity otherwise (0.30). Exact knapsack (HiGHS) vs greedy vs KPI ranking vs slowest first, at budgets
of 100, 500, 1,000 and 5,000 new-tower equivalents; sensitivities for θ, costs and 3GPP service areas.
Writes data/outputs/p4_site_plan.json and docs/data/plans/<ISO>.csv / .geojson / .kml (headline plan).
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import h3
import numpy as np
import pandas as pd
import yaml
from scipy.sparse import csr_matrix
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.plan import cover_value, exact_cover, exact_knapsack, greedy_cover, greedy_knapsack, kpi_ranking, zscore  # noqa: E402

CFG = yaml.safe_load((ROOT / "configs" / "default_config.yaml").read_text())
DATA = Path(os.environ.get("GEO_DATA_DIR", "~/data/geo")).expanduser()
DER = DATA / "derived"
OUT = ROOT / "docs" / "data" / "plans"
BUDGETS = [100, 500, 1000, 5000]
HEADLINE = 1000
COST = {"macro": 1.0, "small_cell": 0.5, "capacity": 0.30}
log = lambda *a: print(time.strftime("%H:%M:%S"), *a, flush=True)


def thetas() -> dict:
    """Central, low and high lift rates per country and intervention type (ADR-008)."""
    p3 = json.loads((ROOT / "data/outputs/p3c_crossing_checks.json").read_text())
    cap = json.loads((ROOT / "data/outputs/p4_capacity_crossing.json").read_text())
    p3m = json.loads((ROOT / "data/outputs/p3_new_site_effect.json").read_text())["countries"]
    own = {k: v["p4_value"] for k, v in p3.items() if isinstance(v, dict) and v.get("p4_value")}
    ev = {k: p3m[k]["counts"]["new_site_hexagons"] for k in own}
    pooled = sum(own[k]["att"] * ev[k] for k in own) / sum(ev.values())
    hi_all = max(v["att"] for v in own.values())
    t = {}
    for k in CFG["countries"]:
        if k in own:
            new = (own[k]["att"], max(0.0, own[k]["ci95"][0]), max(own[k]["att"], own[k]["ci95"][1]))
        else:
            new = (pooled, 0.0, hi_all)
        cv = cap.get(k)
        if isinstance(cv, dict) and cv.get("pass_for_p4") and cv.get("p4_value"):
            pv = cv["p4_value"]; capt = (pv["att"], max(0.0, pv["ci95"][0]), max(pv["att"], pv["ci95"][1]))
        else:
            capt = (0.0, 0.0, new[0])
        t[k] = {"new": new, "capacity": capt, "own_new_estimate": k in own}
    return t


def load() -> pd.DataFrame:
    p1 = pd.read_parquet(DER / "hex_p1.parquet", columns=["iso3", "h3", "population", "morphology", "cells_ring"])
    noise = pd.read_parquet(DER / "hex_noise.parquet", columns=["iso3", "h3", "post_mean", "post_var"])
    p2 = pd.read_parquet(DER / "hex_p2.parquet", columns=["iso3", "h3", "pred_ln", "sigma"])
    places = pd.read_parquet(DER / "hex_latest.parquet", columns=["iso3", "h3", "places"])
    d = p1[p1.population > 0].merge(noise, on=["iso3", "h3"], how="left").merge(p2, on=["iso3", "h3"], how="left").merge(places, on=["iso3", "h3"], how="left")
    d["tested"] = d.post_mean.notna()
    d["typical_ln"] = np.where(d.tested, d.post_mean, d.pred_ln)
    d["sd"] = np.where(d.tested, np.sqrt(d.post_var), d.sigma)
    d = d[d.typical_ln.notna()].copy()
    d["p25"] = norm.cdf((np.log(25) - d.typical_ln) / d.sd)
    d["intervention"] = np.where(d.cells_ring > 0, "capacity", np.where(d.morphology == "urban_centre", "small_cell", "macro"))
    d["cost"] = d.intervention.map(COST)
    return d.reset_index(drop=True)


def district_names() -> dict:
    js = (ROOT / "docs/data/page_data.js").read_text()
    G = json.loads(js[js.index("window.GEO1 = ") + len("window.GEO1 = "):].rstrip().rstrip(";"))
    out = {}
    for k, c in G["countries"].items():
        m = c["map"]
        out[k] = {h + "fffffff": m["names"][n] for h, n in zip(m["h"], m["n"])}
    return out


def benefit(d: pd.DataFrame, th: dict, which: int = 0, cap_equals_new: bool = False) -> np.ndarray:
    tn = th["new"][which]; tc = th["new"][which] if cap_equals_new else th["capacity"][which]
    return (d.population * d.p25 * np.where(d.intervention == "capacity", tc, tn)).to_numpy()


def jaccard(a: np.ndarray, b: np.ndarray) -> float:
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 1.0


def cover_matrix(d: pd.DataFrame, cand: np.ndarray, radius_km: float = 0.866) -> tuple[csr_matrix, np.ndarray]:
    """3GPP sensitivity: a rural macro also lifts the share of each ring-1 neighbour within its radius (RMa ISD/2)."""
    idx = {h: i for i, h in enumerate(d.h3)}
    rows, cols, vals = [], [], []
    for r, j in enumerate(cand):
        rows.append(r); cols.append(j); vals.append(1.0)
        if d.intervention.iat[j] != "macro" or d.morphology.iat[j] != "rural":
            continue
        lat0, lng0 = h3.cell_to_latlng(d.h3.iat[j])
        for nb in h3.grid_ring(d.h3.iat[j], 1):
            i = idx.get(nb)
            if i is None:
                continue
            kids = h3.cell_to_children(nb, 10)
            inside = sum(h3.great_circle_distance((lat0, lng0), h3.cell_to_latlng(k), unit="km") <= radius_km for k in kids)
            if inside:
                rows.append(r); cols.append(i); vals.append(inside / len(kids))
    return csr_matrix((vals, (rows, cols)), shape=(len(cand), len(d))), np.array(cand)


def export(k: str, d: pd.DataFrame, chosen: np.ndarray, b: dict, names: dict) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    s = d[chosen].assign(b=b["central"][chosen], b_low=b["low"][chosen], b_high=b["high"][chosen])
    s = s.sort_values("b", ascending=False).reset_index(drop=True)
    s["rank"] = np.arange(1, len(s) + 1); s["cumulative_cost"] = s.cost.cumsum()
    rows = []
    for r in s.itertuples():
        lat, lng = h3.cell_to_latlng(r.h3)
        rows.append({"rank": r.rank, "h3": r.h3, "lat": round(lat, 5), "lon": round(lng, 5),
                     "district": names.get(k, {}).get(h3.cell_to_parent(r.h3, 5), ""), "area_type": r.morphology,
                     "intervention": r.intervention, "cost": r.cost, "cumulative_cost": round(r.cumulative_cost, 2),
                     "people": int(round(r.population)), "p_below_25": round(float(r.p25), 3),
                     "typical_mbps": round(float(np.exp(r.typical_ln)), 1), "tested": bool(r.tested),
                     "expected_lifted": round(float(r.b), 1), "expected_lifted_low": round(float(r.b_low), 1), "expected_lifted_high": round(float(r.b_high), 1)})
    cols = list(rows[0].keys()) if rows else []
    with open(OUT / f"{k}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
    feats = []
    for r in rows:
        ring = [[round(lng, 6), round(lat, 6)] for lat, lng in h3.cell_to_boundary(r["h3"])]
        ring.append(ring[0])
        feats.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]}, "properties": r})
    (OUT / f"{k}.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":")))
    kml = ['<?xml version="1.0" encoding="UTF-8"?>', '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>', f"<name>{k} site plan (search areas)</name>"]
    for r in rows:
        desc = f"{r['intervention']} · {r['people']} people · P(below 25 Mbps) {r['p_below_25']} · expected lifted {r['expected_lifted']}"
        kml.append(f"<Placemark><name>{r['rank']}. {r['h3']}</name><description>{desc}</description><Point><coordinates>{r['lon']},{r['lat']}</coordinates></Point></Placemark>")
    kml.append("</Document></kml>")
    (OUT / f"{k}.kml").write_text("\n".join(kml))
    # format checks (ADR-008)
    gj = json.loads((OUT / f"{k}.geojson").read_text())
    gj_ok = all(f["geometry"]["coordinates"][0][0] == f["geometry"]["coordinates"][0][-1] and all(-180 <= x <= 180 and -90 <= y <= 90 for x, y in f["geometry"]["coordinates"][0]) for f in gj["features"])
    kml_n = len(ET.parse(OUT / f"{k}.kml").getroot().findall(".//{http://www.opengis.net/kml/2.2}Placemark"))
    with open(OUT / f"{k}.csv") as f:
        csv_ok = next(csv.reader(f)) == cols
    return {"sites": len(rows), "geojson_valid": bool(gj_ok), "kml_placemarks": kml_n, "kml_ok": kml_n == len(rows), "csv_schema_ok": bool(csv_ok)}


def main() -> None:
    t0 = time.time(); TH = thetas(); D = load(); names = district_names(); res = {}
    for k in CFG["countries"]:
        d = D[D.iso3 == k].reset_index(drop=True); th = TH[k]
        b = {"central": benefit(d, th, 0), "low": benefit(d, th, 1), "high": benefit(d, th, 2)}
        c = d.cost.to_numpy()
        score = zscore(-d.typical_ln.to_numpy()) + zscore(np.log1p(d.population.to_numpy())) + zscore(np.log1p(d.places.fillna(0).to_numpy()))
        slow = -d.typical_ln.to_numpy()
        likely = d.p25 >= 0.5
        head = HEADLINE if k != "ARE" else float(d.cost[likely].sum())     # UAE: all likely-slow candidates (ADR-008)
        r = {"theta": th, "candidates": int(len(d)), "likely_slow_hexagons": int(likely.sum()), "headline_budget": head, "budgets": {}}
        for B in sorted(set(BUDGETS + [head])):
            ex, info = exact_knapsack(b["central"], c, B)
            gr = greedy_knapsack(b["central"], c, B); kp = kpi_ranking(score, c, B); sf = kpi_ranking(slow, c, B)
            v = lambda m: float(b["central"][m].sum())
            r["budgets"][str(B)] = {"people_lifted": v(ex), "people_lifted_low": float(b["low"][ex].sum()), "people_lifted_high": float(b["high"][ex].sum()),
                                    "greedy": v(gr), "kpi_ranking": v(kp), "slowest_first": v(sf),
                                    "gain_vs_kpi": v(ex) / v(kp) - 1 if v(kp) > 0 else None, "cost_used": float(c[ex].sum()),
                                    "sites": int(ex.sum()), "mix": d.intervention[ex].value_counts().to_dict(), "solver": info}
            if B == head:
                chosen = ex
        # sensitivities at the headline budget
        sens = {}
        alt = benefit(d, th, 0, cap_equals_new=True); m2, _ = exact_knapsack(alt, c, head)
        sens["capacity_equals_new"] = {"jaccard": jaccard(chosen, m2), "mix": d.intervention[m2].value_counts().to_dict()}
        for nm, cc in (("colocation_0.20", {"capacity": 0.20}), ("colocation_0.50", {"capacity": 0.50}), ("small_cell_0.25", {"small_cell": 0.25})):
            cost2 = d.intervention.map({**COST, **cc}).to_numpy(); m3, _ = exact_knapsack(b["central"], cost2, head)
            sens[nm] = {"jaccard": jaccard(chosen, m3), "people_lifted": float(b["central"][m3].sum())}
        for nm, w in (("theta_low", 1), ("theta_high", 2)):
            m4, _ = exact_knapsack(benefit(d, th, w), c, head); sens[nm] = {"jaccard": jaccard(chosen, m4)}
        # 3GPP service areas: rural macros also lift part of their neighbours (greedy covering on the top candidates)
        top = np.argsort(-(b["central"] / c))[:20000]
        cov, cand = cover_matrix(d, top)
        wn = (d.population * d.p25 * th["new"][0]).to_numpy()
        w_cov = np.where(d.intervention.to_numpy() == "capacity", b["central"], wn)
        gc = greedy_cover(w_cov, cov, c[cand], head)
        ch_cov = np.zeros(len(d), bool); ch_cov[cand[gc]] = True
        sens["3gpp_service_areas"] = {"jaccard": jaccard(chosen, ch_cov), "people_lifted": cover_value(w_cov, cov, gc)}
        # exact vs greedy covering on the largest district subproblem that is small enough
        dist = pd.Series([names.get(k, {}).get(h3.cell_to_parent(x, 5), "") for x in d.h3.iloc[cand]])
        best = dist.value_counts(); sub = None
        for nm_d, n in best.items():
            if 30 <= n <= 300:
                sub = np.flatnonzero(dist.to_numpy() == nm_d); break
        if sub is not None:
            cs = cov[sub]; cols = np.unique(cs.indices); cs = cs[:, cols]; ws = w_cov[cols]; Bs = float(c[cand][sub].sum()) * 0.2
            g_s = greedy_cover(ws, cs, c[cand][sub], Bs); e_s, val = exact_cover(ws, cs, c[cand][sub], Bs)
            sens["covering_exact_vs_greedy"] = {"district": nm_d, "candidates": int(len(sub)), "greedy": cover_value(ws, cs, g_s), "exact": val}
        r["sensitivity"] = sens
        r["exports"] = export(k, d, chosen, b, names)
        hb = r["budgets"][str(head)]
        r["gate_gain_10pct"] = bool(hb["gain_vs_kpi"] is not None and hb["gain_vs_kpi"] >= 0.10)
        res[k] = r
        log(k, f"budget {head:g}: lifted {hb['people_lifted']:,.0f} ({hb['people_lifted_low']:,.0f}–{hb['people_lifted_high']:,.0f}) vs KPI {hb['kpi_ranking']:,.0f} → gain {hb['gain_vs_kpi']:+.1%} | mix {hb['mix']} | exports {r['exports']}")
    passed = sum(v["gate_gain_10pct"] for v in res.values())
    out = {"design": "ADR-008", "headline_budget": HEADLINE, "countries": res, "gate_countries_passed": int(passed),
           "gate_passed": bool(passed >= 5 and all(v["exports"]["geojson_valid"] and v["exports"]["kml_ok"] and v["exports"]["csv_schema_ok"] for v in res.values())),
           "seconds": round(time.time() - t0)}
    (ROOT / CFG["paths"]["outputs_dir"] / "p4_site_plan.json").write_text(json.dumps(out, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    log(f"gate: {passed} of 7 countries ≥ +10% · passed {out['gate_passed']} · {out['seconds']} s")


if __name__ == "__main__":
    main()
