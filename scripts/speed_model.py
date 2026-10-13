"""P2: predict mobile download speed in untested populated hexagons (ADR-004; gate in ADR-002).

    python scripts/speed_model.py

Target: ln(mobile download, Mbps) per measured H3 r8 hexagon, latest quarter. Validation: 5-fold spatial block CV.
Folds are H3 resolution-6 blocks (gate), resolution 7 / 5 and random hexagons (sensitivity). Neighbour features are
nested out-of-fold: test rows see training folds only; a training row in fold g sees folds other than g and the
test fold. Models: ordinary kriging (gate baseline), ring-1 neighbour mean (naive), LightGBM on covariates only
(ablation), LightGBM with spatial features (chosen).

Writes data/outputs/p2_speed_model.json and GEO_DATA_DIR/derived/hex_p2.parquet (untested populated hexagons:
prediction, sigma, P(below 10 / 25 Mbps), area-of-applicability flag).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import h3
import lightgbm as lgb
import numpy as np
import pandas as pd
import yaml
from scipy.stats import norm
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.neighbors import KDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.hexgrid import connect  # noqa: E402
from src.spatialmodel import NBR_NAMES, fit_variogram, krige, neighbour_features, xyz  # noqa: E402

CFG = yaml.safe_load((ROOT / "configs" / "default_config.yaml").read_text())
DATA = Path(os.environ.get("GEO_DATA_DIR", "~/data/geo")).expanduser()
DER = DATA / "derived"
SEED, K = 2026, 5
DESIGNS = ["r6", "r7", "r5", "random"]
MORPH = {"rural": 0, "urban_cluster": 1, "urban_centre": 2}
RING_CLASS = [(1, 1), (2, 2), (3, 3), (4, 6), (7, 99)]
PARAMS = dict(objective="regression", learning_rate=0.05, num_leaves=63, min_data_in_leaf=40, feature_fraction=0.8,
              bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, seed=SEED, deterministic=True, num_threads=4, verbose=-1)
ROUNDS = 600
KNN = [16, 32, 64]   # kriging search neighbourhoods tried on the gate design; the best is the baseline
log = lambda *a: print(time.strftime("%H:%M:%S"), *a, flush=True)


def ring_class(r: np.ndarray) -> np.ndarray:
    out = np.full(len(r), len(RING_CLASS) - 1)
    for j, (a, b) in enumerate(RING_CLASS):
        out[(r >= a) & (r <= b)] = j
    return out


def static_features() -> pd.DataFrame:
    """Covariates for every hexagon (measured or not), none derived from the mobile target."""
    c = connect()
    y, q = CFG["experience"]["latest_quarter"]
    c.sql(f"""CREATE TABLE base AS SELECT l.iso3, l.h3, l.population, l.places, l.cells_lte + l.cells_nr AS lte_nr, l.cells_nr,
              l.mobile_down_mbps, l.mobile_up_mbps, l.mobile_latency_ms, l.fixed_down_mbps, coalesce(l.fixed_tests, 0) AS fixed_tests,
              coalesce(p.morphology, 'rural') AS morphology
              FROM '{DER}/hex_latest.parquet' l LEFT JOIN (SELECT iso3, h3, morphology FROM '{DER}/hex_p1.parquet') p USING (iso3, h3)""")
    log("base", c.sql("SELECT count(*) FROM base").fetchone()[0])
    c.sql("""CREATE TABLE r2 AS SELECT a.h3, sum(b.population) AS pop_r2, sum(b.places) AS places_r2
             FROM (SELECT h3, unnest(h3_grid_disk(h3, 2)) AS nb FROM base) a JOIN base b ON b.h3 = a.nb GROUP BY a.h3""")
    c.sql("""CREATE TABLE r1 AS SELECT a.h3, sum(b.lte_nr) AS cells_r1, sum(b.cells_nr) AS nr_r1, avg(ln(b.fixed_down_mbps)) AS ln_fixed_r1
             FROM (SELECT h3, unnest(h3_grid_disk(h3, 1)) AS nb FROM base) a JOIN base b ON b.h3 = a.nb GROUP BY a.h3""")
    c.sql("""CREATE TABLE par AS SELECT h3, sum(lte_nr) OVER (PARTITION BY h3_cell_to_parent(h3, 6)) AS cells_p6,
             sum(lte_nr) OVER (PARTITION BY h3_cell_to_parent(h3, 5)) AS cells_p5,
             sum(population) OVER (PARTITION BY h3_cell_to_parent(h3, 6)) AS pop_p6 FROM base""")
    c.sql(f"""CREATE TABLE hist AS SELECT h3, arg_max(ln(down_mbps), year * 4 + quarter) AS hist_ln, max(year * 4 + quarter) AS hist_q
              FROM '{DER}/hex_speed_panel.parquet' WHERE type = 'mobile' AND year * 4 + quarter < {y * 4 + q} GROUP BY h3""")
    df = c.sql(f"""SELECT b.*, r2.pop_r2, r2.places_r2, r1.cells_r1, r1.nr_r1, r1.ln_fixed_r1, par.cells_p6, par.cells_p5, par.pop_p6,
                   hist.hist_ln, {y * 4 + q} - hist.hist_q AS hist_age
                   FROM base b LEFT JOIN r2 USING (h3) LEFT JOIN r1 USING (h3) LEFT JOIN par USING (h3) LEFT JOIN hist USING (h3)""").df()
    df = df.drop_duplicates(["iso3", "h3"]).reset_index(drop=True)
    f = pd.DataFrame({"iso3": df.iso3, "h3": df.h3, "population": df.population.astype(float),
                      "y": np.log(df.mobile_down_mbps), "ln_up_down": np.log(df.mobile_up_mbps / df.mobile_down_mbps),
                      "latency": df.mobile_latency_ms})
    feats = {"ln_pop": np.log1p(df.population), "ln_pop_r2": np.log1p(df.pop_r2), "ln_places": np.log1p(df.places),
             "ln_places_r2": np.log1p(df.places_r2), "morph": df.morphology.map(MORPH).astype(float),
             "cells_r1": df.cells_r1, "nr_r1": df.nr_r1, "ln_cells_p6": np.log1p(df.cells_p6), "ln_cells_p5": np.log1p(df.cells_p5),
             "ln_pop_p6": np.log1p(df.pop_p6), "ln_fixed": np.log(df.fixed_down_mbps), "ln_fixed_r1": df.ln_fixed_r1,
             "fixed_tests": df.fixed_tests, "hist_ln": df.hist_ln, "hist_age": df.hist_age,
             "country": df.iso3.map({k: i for i, k in enumerate(CFG["countries"])}).astype(float)}
    for k, v in feats.items():
        f[k] = np.asarray(v, dtype=np.float32)
    return f


def folds_for(h3s: np.ndarray, design: str, rng: np.random.Generator) -> np.ndarray:
    if design == "random":
        return rng.integers(0, K, len(h3s))
    blk = np.array([h3.cell_to_parent(x, int(design[1:])) for x in h3s])
    _, inv = np.unique(blk, return_inverse=True)
    return rng.integers(0, K, inv.max() + 1)[inv]


def nested_neighbours(h3s: np.ndarray, y: np.ndarray, fold: np.ndarray) -> tuple[np.ndarray, dict[int, np.ndarray]]:
    """F_test[i]: features from folds != fold[i]. F_train[f][i] (i not in f): from folds not in {fold[i], f}."""
    F_test = np.full((len(h3s), 8), np.nan)
    for g in range(K):
        m = fold == g
        F_test[m] = neighbour_features(h3s[m], dict(zip(h3s[~m], y[~m])))
    F_train = {}
    for f in range(K):
        F = np.full((len(h3s), 8), np.nan)
        for g in range(K):
            if g == f:
                continue
            m = fold == g; src = (fold != g) & (fold != f)
            F[m] = neighbour_features(h3s[m], dict(zip(h3s[src], y[src])))
        F_train[f] = F
    return F_test, F_train


def gbm(X: np.ndarray, y: np.ndarray, names: list[str]) -> lgb.Booster:
    return lgb.train(PARAMS, lgb.Dataset(X, y, feature_name=names, free_raw_data=True), num_boost_round=ROUNDS)


def metrics(y, p, pop, ringc=None, dep_w=None, iso=None) -> dict:
    e = p - y
    out = {"rmse": float(np.sqrt(np.mean(e ** 2))), "mae": float(np.mean(np.abs(e))),
           "rmse_people_weighted": float(np.sqrt(np.sum(pop * e ** 2) / pop.sum())) if pop.sum() > 0 else None, "n": int(len(y))}
    if ringc is not None and dep_w is not None:
        num = den = 0.0
        for k, w in dep_w.items():      # per country: re-weight ring classes to the deployment distribution
            m = iso == k
            for j, wj in enumerate(w["class_share"]):
                mj = m & (ringc == j)
                if mj.sum() >= 20 and wj > 0:
                    num += w["people"] * wj * np.mean(e[mj] ** 2); den += w["people"] * wj
        out["rmse_distance_matched"] = float(np.sqrt(num / den)) if den else None
    return out


def main() -> None:
    t0 = time.time(); rng = np.random.default_rng(SEED)
    log("static features")
    F = static_features()
    COV = ["ln_pop", "ln_pop_r2", "ln_places", "ln_places_r2", "morph", "cells_r1", "nr_r1", "ln_cells_p6", "ln_cells_p5",
           "ln_pop_p6", "ln_fixed", "ln_fixed_r1", "fixed_tests"]
    HIST = ["hist_ln", "hist_age"]
    ALL = COV + HIST + NBR_NAMES + ["country"]
    meas = F[F.y.notna()].reset_index(drop=True)
    unt = F[F.y.isna() & (F.population > 0)].reset_index(drop=True)
    h3m, ym, iso = meas.h3.to_numpy(), meas.y.to_numpy(), meas.iso3.to_numpy()
    pts = xyz(*np.array([h3.cell_to_latlng(x) for x in h3m]).T)
    log(f"measured {len(meas):,} · untested populated {len(unt):,}")

    # deployment geometry: untested people's ring distance to the nearest measured hexagon (for distance matching)
    log("deployment neighbour features")
    allm = dict(zip(h3m, ym))
    U = np.vstack([neighbour_features(unt.h3.to_numpy()[a:a + 200000], allm) for a in range(0, len(unt), 200000)])
    unt_ringc = ring_class(U[:, 6])
    dep_w = {}
    for k in CFG["countries"]:
        m = unt.iso3.to_numpy() == k; w = unt.population.to_numpy()[m]
        dep_w[k] = {"people": float(w.sum()), "class_share": [float(w[unt_ringc[m] == j].sum() / w.sum()) for j in range(len(RING_CLASS))]}

    results, cv_store, best_k = {}, {}, 32
    for design in DESIGNS:
        log("design", design)
        fold = folds_for(h3m, design, rng)
        F_test, F_train = nested_neighbours(h3m, ym, fold)
        pred = {m: np.full(len(ym), np.nan) for m in ["naive", "gbm", "gbm_covariates_only"] + [f"kriging_k{nk}" for nk in KNN]}
        varios = {}
        for f in range(K):
            te, tr = fold == f, fold != f
            Xtr = np.c_[meas.loc[tr, COV + HIST].to_numpy(), F_train[f][tr], meas.loc[tr, "country"].to_numpy()]
            Xte = np.c_[meas.loc[te, COV + HIST].to_numpy(), F_test[te], meas.loc[te, "country"].to_numpy()]
            pred["gbm"][te] = gbm(Xtr, ym[tr], ALL).predict(Xte)
            if design == "r6":
                cols = COV + ["country"]
                pred["gbm_covariates_only"][te] = gbm(meas.loc[tr, cols].to_numpy(), ym[tr], cols).predict(meas.loc[te, cols].to_numpy())
            nv = F_test[te, 0].copy(); nv[np.isnan(nv)] = F_test[te, 7][np.isnan(nv)]
            cm = pd.Series(ym[tr]).groupby(iso[tr]).mean(); fill = pd.Series(iso[te]).map(cm).to_numpy()
            nv[np.isnan(nv)] = fill[np.isnan(nv)]; pred["naive"][te] = nv
            for k in CFG["countries"]:
                tk, ek = tr & (iso == k), te & (iso == k)
                if ek.sum() == 0:
                    continue
                v = fit_variogram(pts[tk], ym[tk], seed=f); varios.setdefault(k, []).append(v)
                for nk in (KNN if design == "r6" else [best_k]):
                    pk, _ = krige(pts[tk], ym[tk], pts[ek], v, k=nk)
                    pred[f"kriging_k{nk}"][ek] = pk
            log(f"  fold {f} done")
        if design == "r6":   # the gate uses the best kriging neighbourhood (most favourable to the baseline)
            best_k = min(KNN, key=lambda nk: np.sqrt(np.mean((pred[f"kriging_k{nk}"] - ym) ** 2)))
        pred["kriging"] = pred[f"kriging_k{best_k}"]
        ringc = ring_class(F_test[:, 6])
        res = {m: metrics(ym, p, meas.population.to_numpy(), ringc, dep_w, iso) for m, p in pred.items() if not np.isnan(p).all()}
        res["per_country"] = {k: {m: metrics(ym[iso == k], p[iso == k], meas.population.to_numpy()[iso == k])["rmse"]
                                  for m, p in pred.items() if not np.isnan(p).all()} for k in CFG["countries"]}
        res["test_share_ring1"] = float(np.mean(F_test[:, 6] == 1))
        res["ratio_gbm_vs_kriging"] = res["gbm"]["rmse"] / res["kriging"]["rmse"]
        if design == "r6":
            res["variograms_by_fold"] = {k: [list(v) for v in vs] for k, vs in varios.items()}
            res["kriging_best_k"] = int(best_k)
            cv_store = {"fold": fold, "F_test": F_test, "pred": pred["gbm"], "ringc": ringc}
        results[design] = res
        log(f"  {design}: gbm {res['gbm']['rmse']:.4f} · kriging {res['kriging']['rmse']:.4f} · ratio {res['ratio_gbm_vs_kriging']:.3f}")

    # uncertainty from r6 CV residuals: sigma per (country, ring class); cross-fitted coverage of the 80% interval
    fold, Ft, pg, rc = cv_store["fold"], cv_store["F_test"], cv_store["pred"], cv_store["ringc"]
    resid = ym - pg
    def sig_table(mask):
        t = {}
        for k in CFG["countries"]:
            for j in range(len(RING_CLASS)):
                m = mask & (iso == k) & (rc == j)
                t[(k, j)] = float(np.std(resid[m])) if m.sum() >= 30 else float(np.std(resid[mask & (iso == k)]))
        return t
    cover, sig_cv = np.zeros(len(ym), bool), np.zeros(len(ym))
    for f in range(K):
        t = sig_table(fold != f); te = fold == f
        s = np.array([t[(k, j)] for k, j in zip(iso[te], rc[te])]); sig_cv[te] = s
        cover[te] = np.abs(resid[te]) <= norm.ppf(0.9) * s
    sig_all = sig_table(np.ones(len(ym), bool))
    below25 = ym < np.log(25); p25 = norm.cdf((np.log(25) - pg) / sig_cv)
    unc = {"coverage_80": float(cover.mean()),
           "coverage_80_by_ring_class": [float(cover[rc == j].mean()) for j in range(len(RING_CLASS))],
           "auc_below_25": float(roc_auc_score(below25, p25)), "brier_below_25": float(np.mean((p25 - below25) ** 2)),
           "sigma_by_country_ring_class": {k: [sig_all[(k, j)] for j in range(len(RING_CLASS))] for k in CFG["countries"]}}
    log(f"uncertainty: coverage80 {unc['coverage_80']:.3f} · AUC<25 {unc['auc_below_25']:.3f}")

    # leave-one-country-out: no country feature; held-out country's own neighbours (r6 out-of-fold) only
    loco = {}
    noc = COV + HIST + NBR_NAMES
    Xall = np.c_[meas[COV + HIST].to_numpy(), Ft]
    for k in CFG["countries"]:
        m = iso == k
        b = gbm(Xall[~m], ym[~m], noc)
        loco[k] = {"rmse": float(np.sqrt(np.mean((b.predict(Xall[m]) - ym[m]) ** 2))), "within_country_cv_rmse": results["r6"]["per_country"][k]["gbm"]}
    log("loco", {k: round(v["rmse"], 3) for k, v in loco.items()})

    # final model on all measured (r6 out-of-fold neighbour features), predictions for untested populated hexagons
    final = gbm(np.c_[Xall, meas["country"].to_numpy()], ym, ALL)
    imp = dict(zip(ALL, final.feature_importance("gain").tolist()))
    Xu = np.c_[unt[COV + HIST].to_numpy(), U, unt["country"].to_numpy()]
    pu = final.predict(Xu)
    su = np.array([sig_all[(k, j)] for k, j in zip(unt.iso3, unt_ringc)])

    # area of applicability (Meyer & Pebesma 2021) on the 8 most important features, importance-weighted
    top = sorted(imp, key=imp.get, reverse=True)
    top = [c for c in top if c != "country"][:8]
    wts = np.array([imp[c] for c in top]); wts = wts / wts.sum()
    Mtr = pd.DataFrame(Xall, columns=noc)[top]; mu, sd = Mtr.mean(), Mtr.std().replace(0, 1)
    Z = ((Mtr - mu) / sd).fillna(0).to_numpy() * wts
    Zu = ((pd.DataFrame(Xu[:, :-1], columns=noc)[top] - mu) / sd).fillna(0).to_numpy() * wts
    sub = np.random.default_rng(SEED).choice(len(Z), size=min(150000, len(Z)), replace=False)
    dbar = np.mean(KDTree(Z[sub]).query(Z[sub], k=2)[0][:, 1])
    di_cv = np.zeros(len(Z))
    for f in range(K):
        tr = np.where(fold != f)[0]; s2 = np.random.default_rng(f).choice(tr, size=min(150000, len(tr)), replace=False)
        te = np.where(fold == f)[0]
        di_cv[te] = KDTree(Z[s2]).query(Z[te], k=1)[0][:, 0] / dbar
    q1, q3 = np.percentile(di_cv, [25, 75]); thr = q3 + 1.5 * (q3 - q1)
    di_u = KDTree(Z[sub]).query(Zu, k=1)[0][:, 0] / dbar
    in_aoa = di_u <= thr

    out = pd.DataFrame({"iso3": unt.iso3, "h3": unt.h3, "population": unt.population, "pred_ln": pu.astype(np.float32),
                        "sigma": su.astype(np.float32), "p_below_10": norm.cdf((np.log(10) - pu) / su).astype(np.float32),
                        "p_below_25": norm.cdf((np.log(25) - pu) / su).astype(np.float32), "nearest_ring": U[:, 6].astype(np.int16),
                        "in_aoa": in_aoa})
    out.to_parquet(DER / "hex_p2.parquet", index=False)
    p1 = json.loads((ROOT / "data/outputs/p1_experience_gap.json").read_text())["countries"]
    totals = {}
    for k in CFG["countries"]:
        o = out[out.iso3 == k]; r = p1[k]; tested = r["population"] * r["measured_share"]
        e10, e25 = float((o.population * o.p_below_10).sum()), float((o.population * o.p_below_25).sum())
        totals[k] = {"untested_people": float(o.population.sum()), "expected_untested_below_10": e10, "expected_untested_below_25": e25,
                     "untested_share_below_25": e25 / float(o.population.sum()), "untested_people_in_aoa_share": float((o.population * o.in_aoa).sum() / o.population.sum()),
                     "tested_below_25": r["below_25"] * tested, "all_people_share_below_25": (r["below_25"] * tested + e25) / r["population"],
                     "tested_share_below_25": r["below_25"]}

    # ADR-003 follow-up: do upload/download ratio and latency separate coverage from capacity gaps where typed?
    p1h = pd.read_parquet(DER / "hex_p1.parquet", columns=["iso3", "h3", "gap_25"])
    g = meas.merge(p1h, on=["iso3", "h3"])
    g = g[g.gap_25.isin(["coverage", "capacity"]) & g.ln_up_down.notna() & g.latency.notna()]
    gf = folds_for(g.h3.to_numpy(), "r6", np.random.default_rng(SEED)); yv = (g.gap_25 == "coverage").to_numpy()
    sc = np.zeros(len(g))
    for f in range(K):
        tr, te = gf != f, gf == f
        Xg = g[["ln_up_down", "latency"]].to_numpy()
        sc[te] = LogisticRegression(max_iter=1000).fit(Xg[tr], yv[tr]).predict_proba(Xg[te])[:, 1]
    gap_follow = {"hexagons": int(len(g)), "coverage_share": float(yv.mean()), "block_cv_auc": float(roc_auc_score(yv, sc)) if 0 < yv.mean() < 1 else None}

    gate = results["r6"]["ratio_gbm_vs_kriging"] <= CFG["gates"]["p2_max_rmse_ratio_vs_kriging"]
    report = {"quarter": f"{CFG['experience']['latest_quarter'][0]}Q{CFG['experience']['latest_quarter'][1]}",
              "measured_hexagons": int(len(meas)), "untested_populated_hexagons": int(len(unt)), "designs": results,
              "uncertainty": unc, "leave_one_country_out": loco, "feature_importance_gain": imp,
              "area_of_applicability": {"features": top, "threshold": float(thr), "untested_people_inside": float((out.population * out.in_aoa).sum() / out.population.sum())},
              "deployment_ring_class_share": dep_w, "ring_classes": RING_CLASS, "untested_totals": totals,
              "gap_type_followup": gap_follow, "gate_ratio_max": CFG["gates"]["p2_max_rmse_ratio_vs_kriging"],
              "gate_passed": bool(gate), "params": {**PARAMS, "rounds": ROUNDS}, "seconds": round(time.time() - t0)}
    (ROOT / CFG["paths"]["outputs_dir"] / "p2_speed_model.json").write_text(json.dumps(report, indent=1))
    log(f"gate {'passed' if gate else 'FAILED'}: ratio {results['r6']['ratio_gbm_vs_kriging']:.3f} · done in {report['seconds']} s")


if __name__ == "__main__":
    main()
