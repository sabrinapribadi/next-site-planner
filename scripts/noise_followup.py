"""ADR-005 follow-up (post-hoc, written after the P2 gate failed): measurement noise, shrinkage, noise-aware scoring,
and kriging deployment for untested hexagons.

    python scripts/noise_followup.py

Reads p2_speed_model.json (best kriging neighbourhood). Writes data/outputs/p2b_noise_followup.json,
GEO_DATA_DIR/derived/hex_noise.parquet (measured hexagons: noise variance, prior, posterior) and replaces
GEO_DATA_DIR/derived/hex_p2.parquet with kriging predictions (the pre-registered consequence of the failed gate).
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
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
import speed_model as sm  # noqa: E402
from src.hexgrid import connect  # noqa: E402
from src.noise import fit_noise, hex_noise_var, shrink, sigma2_u, tile_pairs  # noqa: E402
from src.spatialmodel import NBR_NAMES, fit_variogram, krige, neighbour_features, xyz  # noqa: E402
from src.spatialstats import block_bootstrap_shares  # noqa: E402

CFG = yaml.safe_load((ROOT / "configs" / "default_config.yaml").read_text())
DATA = Path(os.environ.get("GEO_DATA_DIR", "~/data/geo")).expanduser()
DER = DATA / "derived"
BARS = [5, 10, 25, 50, 100]
log = sm.log


def main() -> None:
    t0 = time.time()
    p2 = json.loads((ROOT / "data/outputs/p2_speed_model.json").read_text())
    best_k = p2["designs"]["r6"]["kriging_best_k"]
    y, q = CFG["experience"]["latest_quarter"]

    # 1. noise model per country, from tiles in the same hexagon
    c = connect()
    tiles = c.sql(f"""SELECT iso3, h3_latlng_to_cell_string(tile_y, tile_x, 8) AS h3, tests, ln(greatest(avg_d_kbps, 1) / 1000) AS y
                      FROM '{DATA}/ookla7/mobile/{y}q{q}.parquet' WHERE tests > 0""").df()
    noise, hexn = {}, []
    for k, t in tiles.groupby("iso3"):
        pr = tile_pairs(t, seed=1)
        s2t, s2m = fit_noise(pr)
        noise[k] = {"s2_test": s2t, "s2_micro": s2m, "tile_pairs": int(len(pr))}
        a = t.assign(n2=t.tests.astype(float) ** 2).groupby("h3").agg(sum_n=("tests", "sum"), sum_n2=("n2", "sum"))
        a["v"] = hex_noise_var(a.sum_n.to_numpy(float), a.sum_n2.to_numpy(float), s2t, s2m)
        hexn.append(a.assign(iso3=k).reset_index())
        log(k, f"s2_test {s2t:.3f} · s2_micro {s2m:.3f} · pairs {len(pr):,}")
    hexn = pd.concat(hexn)

    # 2. features (saved for reuse), measured table with noise variance
    fp = DER / "p2_features.parquet"
    F = pd.read_parquet(fp) if fp.exists() else sm.static_features()
    if not fp.exists():
        F.to_parquet(fp, index=False)
    meas = F[F.y.notna()].merge(hexn[["iso3", "h3", "sum_n", "v"]], on=["iso3", "h3"], how="left").reset_index(drop=True)
    meas["v"] = meas["v"].fillna(meas["v"].median())
    unt = F[F.y.isna() & (F.population > 0)].reset_index(drop=True)
    h3m, ym, iso, v = meas.h3.to_numpy(), meas.y.to_numpy(), meas.iso3.to_numpy(), meas.v.to_numpy()
    pts = xyz(*np.array([h3.cell_to_latlng(x) for x in h3m]).T)
    log(f"measured {len(meas):,}; mean noise variance {v.mean():.3f}")

    # 3. shrinkage: leave-one-out kriging prior, sigma_u per country, posterior
    mu, s2u, varios = np.empty(len(ym)), {}, {}
    for k in CFG["countries"]:
        m = iso == k
        varios[k] = fit_variogram(pts[m], ym[m], seed=0)
        mu[m], _ = krige(pts[m], ym[m], pts[m], varios[k], k=best_k, leave_one_out=True)
        s2u[k] = sigma2_u(ym[m], mu[m], v[m])
    s2u_row = pd.Series(iso).map(s2u).to_numpy()
    post_m, post_v = shrink(ym, v, mu, s2u_row)
    pd.DataFrame({"iso3": iso, "h3": h3m, "population": meas.population, "y": ym, "v": v, "mu": mu,
                  "post_mean": post_m, "post_var": post_v}).to_parquet(DER / "hex_noise.parquet", index=False)
    log("shrinkage", {k: round(x, 3) for k, x in s2u.items()})

    # 4. P1 noise-corrected shares (tested people), with block-bootstrap intervals
    p1 = json.loads((ROOT / "data/outputs/p1_experience_gap.json").read_text())["countries"]
    corrected, rng = {}, np.random.default_rng(2026)
    for k in CFG["countries"]:
        m = iso == k; pop = meas.population.to_numpy()[m]
        pb = {b: norm.cdf((np.log(b) - post_m[m]) / np.sqrt(post_v[m])) for b in BARS}
        blocks = np.array([h3.cell_to_parent(x, 5) for x in h3m[m]])
        ci = block_bootstrap_shares(blocks, pop, {b: pb[b] for b in (10, 25)}, CFG["experience"]["bootstrap_reps"], rng)
        corrected[k] = {f"below_{b}": float((pop * pb[b]).sum() / pop.sum()) for b in BARS}
        corrected[k].update({f"below_{b}_ci95": ci[b] for b in (10, 25)})
        corrected[k].update({f"raw_below_{b}": p1[k][f"below_{b}"] for b in BARS})
    log("P1 corrected below 25:", {k: round(x["below_25"], 3) for k, x in corrected.items()})

    # 5. P2 noise-aware scoring on the same resolution-6 folds (first rng draw with the same seed as speed_model)
    fold = sm.folds_for(h3m, "r6", np.random.default_rng(sm.SEED))
    F_test, F_train = sm.nested_neighbours(h3m, ym, fold)
    COV = ["ln_pop", "ln_pop_r2", "ln_places", "ln_places_r2", "morph", "cells_r1", "nr_r1", "ln_cells_p6", "ln_cells_p5",
           "ln_pop_p6", "ln_fixed", "ln_fixed_r1", "fixed_tests"]
    HIST = ["hist_ln", "hist_age"]; ALL = COV + HIST + NBR_NAMES + ["country"]
    w_prec = 1 / (s2u_row + v)
    pred = {m_: np.full(len(ym), np.nan) for m_ in ("kriging", "gbm", "gbm_precision_weighted")}
    for f in range(sm.K):
        te, tr = fold == f, fold != f
        Xtr = np.c_[meas.loc[tr, COV + HIST].to_numpy(), F_train[f][tr], meas.loc[tr, "country"].to_numpy()]
        Xte = np.c_[meas.loc[te, COV + HIST].to_numpy(), F_test[te], meas.loc[te, "country"].to_numpy()]
        pred["gbm"][te] = sm.gbm(Xtr, ym[tr], ALL).predict(Xte)
        b = __import__("lightgbm").train(sm.PARAMS, __import__("lightgbm").Dataset(Xtr, ym[tr], weight=w_prec[tr], feature_name=ALL), num_boost_round=sm.ROUNDS)
        pred["gbm_precision_weighted"][te] = b.predict(Xte)
        for k in CFG["countries"]:
            tk, ek = tr & (iso == k), te & (iso == k)
            if ek.sum():
                pred["kriging"][ek], _ = krige(pts[tk], ym[tk], pts[ek], fit_variogram(pts[tk], ym[tk], seed=f), k=best_k)
        log(f"  fold {f} done")
    well = meas.sum_n.fillna(0).to_numpy() >= 10
    scores = {}
    for m_, p in pred.items():
        e2 = (p - ym) ** 2
        scores[m_] = {"rmse": float(np.sqrt(e2.mean())), "rmse_noise_adjusted": float(np.sqrt(max(e2.mean() - v.mean(), 0))),
                      "rmse_well_measured_10plus_tests": float(np.sqrt(e2[well].mean())), "well_measured_hexagons": int(well.sum()),
                      "rmse_precision_weighted": float(np.sqrt(np.sum(w_prec * e2) / w_prec.sum()))}
    for key in ("rmse", "rmse_noise_adjusted", "rmse_well_measured_10plus_tests", "rmse_precision_weighted"):
        scores[f"ratio_gbm_vs_kriging_{key}"] = scores["gbm"][key] / scores["kriging"][key]
    log("scores", {m_: round(s["rmse_well_measured_10plus_tests"], 3) for m_, s in scores.items() if isinstance(s, dict)})

    # 6. kriging deployment: sigma against the true typical speed per (country, ring class) from the CV above
    ringc = sm.ring_class(F_test[:, 6]); resid2 = (pred["kriging"] - ym) ** 2
    sig = {}
    for k in CFG["countries"]:
        for j in range(len(sm.RING_CLASS)):
            mm = (iso == k) & (ringc == j)
            if mm.sum() < 30:
                mm = iso == k
            sig[(k, j)] = float(np.sqrt(max(resid2[mm].mean() - v[mm].mean(), 0.01)))
    U = np.vstack([neighbour_features(unt.h3.to_numpy()[a:a + 200000], dict(zip(h3m, ym))) for a in range(0, len(unt), 200000)])
    uringc = sm.ring_class(U[:, 6])
    pu = np.empty(len(unt))
    upts = xyz(*np.array([h3.cell_to_latlng(x) for x in unt.h3]).T)
    for k in CFG["countries"]:
        m, mu_k = unt.iso3.to_numpy() == k, iso == k
        pu[m], _ = krige(pts[mu_k], ym[mu_k], upts[m], varios[k], k=best_k)
    su = np.array([sig[(k, j)] for k, j in zip(unt.iso3, uringc)])
    out = pd.DataFrame({"iso3": unt.iso3, "h3": unt.h3, "population": unt.population, "pred_ln": pu.astype(np.float32),
                        "sigma": su.astype(np.float32), "p_below_10": norm.cdf((np.log(10) - pu) / su).astype(np.float32),
                        "p_below_25": norm.cdf((np.log(25) - pu) / su).astype(np.float32), "nearest_ring": U[:, 6].astype(np.int16),
                        "model": "kriging"})
    out.to_parquet(DER / "hex_p2.parquet", index=False)
    totals = {}
    for k in CFG["countries"]:
        o = out[out.iso3 == k]; r = p1[k]; tested = r["population"] * r["measured_share"]
        e = {b: float((o.population * norm.cdf((np.log(b) - o.pred_ln) / o.sigma)).sum()) for b in BARS}
        totals[k] = {"untested_people": float(o.population.sum()),
                     **{f"expected_untested_below_{b}": e[b] for b in BARS},
                     **{f"all_people_share_below_{b}": (corrected[k][f"below_{b}"] * tested + e[b]) / r["population"] for b in BARS},
                     **{f"all_people_share_below_{b}_raw_tested": (r[f"below_{b}"] * tested + e[b]) / r["population"] for b in BARS}}
    report = {"status": "post-hoc follow-up (ADR-005); P1 raw shares and the failed P2 gate stand as pre-registered",
              "noise_model": noise, "sigma2_u": s2u, "kriging_best_k": best_k,
              "variograms": {k: list(vv) for k, vv in varios.items()}, "p1_noise_corrected": corrected,
              "p2_noise_aware_scores": scores, "deployment": {"model": "kriging", "sigma_true_by_country_ring_class": {k: [sig[(k, j)] for j in range(len(sm.RING_CLASS))] for k in CFG["countries"]}},
              "totals": totals, "seconds": round(time.time() - t0)}
    (ROOT / CFG["paths"]["outputs_dir"] / "p2b_noise_followup.json").write_text(json.dumps(report, indent=1))
    log(f"done in {report['seconds']} s")


if __name__ == "__main__":
    main()
