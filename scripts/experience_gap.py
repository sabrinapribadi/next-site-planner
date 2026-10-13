"""P1: the experience gap per person, a fair cross-country benchmark, and slow-speed hotspots (ADR-001, ADR-002).

    python scripts/experience_gap.py

Inputs (GEO_DATA_DIR/derived, from P0): hex_latest.parquet, plus the latest quarter's mobile tiles for the bootstrap.
Outputs: data/outputs/p1_experience_gap.json (country results) and GEO_DATA_DIR/derived/hex_p1.parquet (map layer).

- Gap: share of people in measured hexagons whose mobile download is below each bar (5, 10, 25, 50 Mbps);
  the share of people in unmeasured hexagons is reported separately, never dropped silently.
- Density-adjusted: shares within people-weighted density deciles (pooled over the seven countries),
  re-weighted to the pooled decile distribution (direct standardisation).
- 95% intervals: Poisson bootstrap over speed tiles (each tile's weight ~ Poisson(1)), hexagon speeds recomputed.
- Hotspots: Getis–Ord Gi* on log speed with H3 ring-1 neighbours (self included); Benjamini–Hochberg FDR 5%
  within each country. Check: false hotspots on spatially shuffled speeds, with vs without FDR.
- Industry view (ADR-003): morphology (Degree of Urbanisation on H3), gap type at each headline bar (coverage /
  capacity / unmeasured / none, from LTE/5G cells within ring-1), shares by morphology, and the share of people
  with a 5G (NR) cell within ring-1 (a lower bound: OpenCelliD under-records cells).
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
sys.path.insert(0, str(ROOT))
from src.hexgrid import connect  # noqa: E402
from src.morphology import cells_within_ring, degree_of_urbanisation, gap_type  # noqa: E402

CFG = yaml.safe_load((ROOT / "configs" / "default_config.yaml").read_text())
DATA = Path(os.environ.get("GEO_DATA_DIR", "~/data/geo")).expanduser()
DER = DATA / "derived"
RNG = np.random.default_rng(2026)


def shares(df: pd.DataFrame, bars: list[float], speed: str = "mobile_down_mbps") -> dict:
    m = df[speed].notna()
    pop, pm = df["population"].sum(), df.loc[m, "population"].sum()
    out = {"population": float(pop), "measured_share": float(pm / pop) if pop else 0.0}
    for b in bars:
        out[f"below_{b:g}"] = float(df.loc[m & (df[speed] < b), "population"].sum() / pm) if pm else float("nan")
    return out


def density_adjusted(df: pd.DataFrame, edges: np.ndarray, weights: np.ndarray, bar: float) -> float:
    m = df["mobile_down_mbps"].notna() & (df["population"] > 0)
    d = df.loc[m]
    dec = np.clip(np.searchsorted(edges, d["population"].to_numpy(), side="right") - 1, 0, len(weights) - 1)
    num = np.bincount(dec, weights=d["population"].to_numpy() * (d["mobile_down_mbps"].to_numpy() < bar), minlength=len(weights))
    den = np.bincount(dec, weights=d["population"].to_numpy(), minlength=len(weights))
    have = den > 0
    w = weights * have
    return float(np.sum(w[have] * num[have] / den[have]) / w.sum())


def gi_star(h3s: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Getis–Ord Gi* z-scores with binary ring-1 weights (self included)."""
    idx = {h: i for i, h in enumerate(h3s)}
    n, xbar, s = len(x), x.mean(), x.std()
    z = np.full(n, np.nan)
    for i, h in enumerate(h3s):
        nb = [idx[g] for g in h3.grid_disk(h, 1) if g in idx]
        w = len(nb)
        if w < 2 or s == 0:
            continue
        num = x[nb].sum() - xbar * w
        den = s * np.sqrt((n * w - w * w) / (n - 1))
        z[i] = num / den
    return z


def bh(p: np.ndarray, q: float = 0.05) -> np.ndarray:
    """Benjamini–Hochberg: boolean mask of discoveries."""
    ok = ~np.isnan(p)
    out = np.zeros_like(p, dtype=bool)
    pv = p[ok]; order = np.argsort(pv); m = len(pv)
    thr = q * np.arange(1, m + 1) / m
    passed = pv[order] <= thr
    k = np.max(np.where(passed)[0]) + 1 if passed.any() else 0
    sel = np.zeros(m, dtype=bool); sel[order[:k]] = True
    out[np.where(ok)[0]] = sel
    return out


def main() -> None:
    t0 = time.time()
    E = CFG["experience"]; bars = sorted(E["thresholds_mbps"] + E["sensitivity_mbps"])
    hexes = pd.read_parquet(DER / "hex_latest.parquet")
    hexes = hexes[hexes["population"].notna()]
    cellhex = hexes.groupby("h3", as_index=False)[["cells_lte", "cells_nr"]].sum()
    cellhex["lte_nr"] = cellhex["cells_lte"] + cellhex["cells_nr"]
    ring = CFG["gap_typing"]["cell_search_ring"]
    iso = list(CFG["countries"])

    # pooled, people-weighted density deciles (hexagons are near equal-area, so population = density)
    pos = hexes[hexes["population"] > 0]
    order = np.argsort(pos["population"].to_numpy()); cw = np.cumsum(pos["population"].to_numpy()[order]) / pos["population"].sum()
    edges = np.concatenate([[0], [pos["population"].to_numpy()[order][np.searchsorted(cw, k / 10)] for k in range(1, 10)], [np.inf]])
    weights = np.full(10, 0.1)

    # bootstrap: Poisson weights on the latest quarter's mobile tiles
    y, q = E["latest_quarter"]
    c = connect()
    tiles = c.sql(f"""SELECT iso3, h3_latlng_to_cell_string(tile_y, tile_x, 8) AS h3, tests, ln(greatest(avg_d_kbps, 1)) AS lg
                      FROM '{DATA}/ookla7/mobile/{y}q{q}.parquet' WHERE tests > 0""").df()

    results, hexlayer = {}, []
    for k in iso:
        h = hexes[hexes["iso3"] == k].copy()
        r = shares(h, bars)

        # industry view (ADR-003): morphology, gap type, 5G presence — populated hexagons only
        hp = h[h["population"] > 0].copy()
        hp["morphology"] = degree_of_urbanisation(hp["h3"], hp["population"], CFG["morphology"])
        cells = cellhex[cellhex["lte_nr"] > 0]
        hp["cells_ring"] = cells_within_ring(hp["h3"], cells["h3"], cells["lte_nr"], k=ring)
        nr = cellhex[cellhex["cells_nr"] > 0]
        hp["nr_ring"] = cells_within_ring(hp["h3"], nr["h3"], nr["cells_nr"], k=ring)
        for b in E["thresholds_mbps"]:
            hp[f"gap_{b:g}"] = gap_type(hp["mobile_down_mbps"], hp["cells_ring"].to_numpy(), b)
        P = hp["population"].sum()
        r["morphology"] = {m: {"population_share": float(g["population"].sum() / P), **shares(g, E["thresholds_mbps"])}
                           for m, g in hp.groupby("morphology")}
        r["gap_types"] = {f"{b:g}": {t: float(v / P) for t, v in hp.groupby(f"gap_{b:g}")["population"].sum().items()}
                          for b in E["thresholds_mbps"]}
        r["population_with_5g_cell_within_ring"] = float(hp.loc[hp["nr_ring"] > 0, "population"].sum() / P)
        r["populated_hexagons_untyped"] = int(hp["morphology"].isna().sum() + hp[[f"gap_{b:g}" for b in E["thresholds_mbps"]]].isna().any(axis=1).sum())
        for b in E["thresholds_mbps"]:
            r[f"below_{b:g}_density_adjusted"] = density_adjusted(h, edges, weights, b)
        # Poisson bootstrap over tiles
        t = tiles[tiles["iso3"] == k]
        codes, uniq = pd.factorize(t["h3"])
        popmap = h.set_index("h3")["population"].reindex(uniq).fillna(0).to_numpy()
        boots = {b: [] for b in E["thresholds_mbps"]}
        for _ in range(E["bootstrap_reps"]):
            w = RNG.poisson(1.0, len(t)) * t["tests"].to_numpy()
            sw = np.bincount(codes, weights=w, minlength=len(uniq))
            lg = np.bincount(codes, weights=w * t["lg"].to_numpy(), minlength=len(uniq))
            have = sw > 0
            mbps = np.exp(lg[have] / sw[have]) / 1000
            pp = popmap[have]
            for b in E["thresholds_mbps"]:
                boots[b].append(pp[mbps < b].sum() / pp.sum() if pp.sum() else np.nan)
        for b in E["thresholds_mbps"]:
            r[f"below_{b:g}_ci95"] = [float(np.nanpercentile(boots[b], 2.5)), float(np.nanpercentile(boots[b], 97.5))]

        # Gi* on log speed, measured hexagons only; FDR within country
        mh = h[h["mobile_down_mbps"].notna()].reset_index(drop=True)
        z = gi_star(mh["h3"].to_numpy(), np.log(mh["mobile_down_mbps"].to_numpy()))
        p = 2 * norm.sf(np.abs(z))
        slow_fdr = bh(p) & (z < 0)
        slow_raw = (p < 0.05) & (z < 0)
        zs = gi_star(mh["h3"].to_numpy(), RNG.permutation(np.log(mh["mobile_down_mbps"].to_numpy())))
        ps = 2 * norm.sf(np.abs(zs))
        r["hotspots"] = {"measured_hexagons": int(len(mh)), "slow_hotspot_hexagons_fdr": int(slow_fdr.sum()),
                         "people_in_slow_hotspots_fdr": float(mh.loc[slow_fdr, "population"].sum()),
                         "slow_hotspot_hexagons_unadjusted": int(slow_raw.sum()),
                         "false_hotspots_on_shuffled_unadjusted": int(((ps < 0.05) & (zs < 0)).sum()),
                         "false_hotspots_on_shuffled_fdr": int((bh(ps) & (zs < 0)).sum())}
        mh["gi_z"] = z; mh["slow_hotspot"] = slow_fdr
        lay = hp[["iso3", "h3", "population", "mobile_down_mbps", "mobile_tests", "morphology", "cells_ring", "nr_ring"]
                 + [f"gap_{b:g}" for b in E["thresholds_mbps"]]].merge(mh[["h3", "gi_z", "slow_hotspot"]], on="h3", how="left")
        hexlayer.append(lay)
        results[k] = r
        print(k, {kk: (round(v, 4) if isinstance(v, float) else v) for kk, v in r.items() if kk not in ("hotspots", "morphology", "gap_types")},
              r["hotspots"], r["gap_types"], flush=True)

    pd.concat(hexlayer).to_parquet(DER / "hex_p1.parquet", index=False)
    report = {"quarter": f"{y}Q{q}", "bars_mbps": bars, "density_deciles_edges_people_per_hex": [float(e) for e in edges[1:-1]],
              "countries": results, "seconds": round(time.time() - t0),
              "gate_passed": all("below_10_ci95" in r and r["hotspots"]["slow_hotspot_hexagons_fdr"] >= 0
                                 and r["populated_hexagons_untyped"] == 0 for r in results.values())}
    (ROOT / CFG["paths"]["outputs_dir"] / "p1_experience_gap.json").write_text(json.dumps(report, indent=2))
    print("done in", report["seconds"], "s")


if __name__ == "__main__":
    main()
