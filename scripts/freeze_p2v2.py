"""ADR-006: freeze kriging and LightGBM predictions for every untested populated hexagon (2026 Q3), before 2026 Q4 exists.

    python scripts/freeze_p2v2.py

LightGBM is trained exactly as in scripts/speed_model.py (ADR-004): same features, hyperparameters, seed, and
resolution-6 out-of-fold neighbour features for training rows; untested hexagons get neighbour features from all
measured hexagons. Kriging predictions are the deployed ones (derived/hex_p2.parquet, ADR-005).
sigma is against the true typical speed for both models: kriging's from ADR-005; LightGBM's from its resolution-6
CV residuals per (country, ring class) minus the country's mean measurement-noise variance (floor 0.01).
Writes GEO_DATA_DIR/derived/p2v2_frozen_predictions.parquet and data/outputs/p2v2_frozen.json (SHA-256, rows, commit).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
import speed_model as sm  # noqa: E402
from src.contracts import sha256  # noqa: E402
from src.spatialmodel import NBR_NAMES, neighbour_features  # noqa: E402

DATA = Path(os.environ.get("GEO_DATA_DIR", "~/data/geo")).expanduser()
DER = DATA / "derived"
COV = ["ln_pop", "ln_pop_r2", "ln_places", "ln_places_r2", "morph", "cells_r1", "nr_r1", "ln_cells_p6", "ln_cells_p5",
       "ln_pop_p6", "ln_fixed", "ln_fixed_r1", "fixed_tests"]
HIST = ["hist_ln", "hist_age"]
ALL = COV + HIST + NBR_NAMES + ["country"]


def main() -> None:
    t0 = time.time()
    F = pd.read_parquet(DER / "p2_features.parquet")
    meas = F[F.y.notna()].reset_index(drop=True)
    unt = F[F.y.isna() & (F.population > 0)].reset_index(drop=True)
    h3m, ym, iso = meas.h3.to_numpy(), meas.y.to_numpy(), meas.iso3.to_numpy()

    # training rows: resolution-6 out-of-fold neighbour features (same folds and seed as speed_model.py)
    fold = sm.folds_for(h3m, "r6", np.random.default_rng(sm.SEED))
    Ft = np.full((len(h3m), 8), np.nan)
    for g in range(sm.K):
        m = fold == g
        Ft[m] = neighbour_features(h3m[m], dict(zip(h3m[~m], ym[~m])))
        sm.log(f"oof neighbours fold {g}")
    final = sm.gbm(np.c_[meas[COV + HIST].to_numpy(), Ft, meas["country"].to_numpy()], ym, ALL)

    # untested rows: neighbour features from all measured hexagons
    allm = dict(zip(h3m, ym))
    U = np.vstack([neighbour_features(unt.h3.to_numpy()[a:a + 200000], allm) for a in range(0, len(unt), 200000)])
    sm.log("deployment neighbours done")
    pg = final.predict(np.c_[unt[COV + HIST].to_numpy(), U, unt["country"].to_numpy()])

    # sigma against the true typical speed for LightGBM (CV residual variance minus mean noise variance)
    p2 = json.loads((ROOT / "data/outputs/p2_speed_model.json").read_text())
    sig_gbm = p2["uncertainty"]["sigma_by_country_ring_class"]
    noise = pd.read_parquet(DER / "hex_noise.parquet", columns=["iso3", "v"]).groupby("iso3").v.mean().to_dict()
    ringc = sm.ring_class(U[:, 6])
    sg = np.array([np.sqrt(max(sig_gbm[k][j] ** 2 - noise[k], 0.01)) for k, j in zip(unt.iso3, ringc)])

    kr = pd.read_parquet(DER / "hex_p2.parquet", columns=["iso3", "h3", "pred_ln", "sigma", "model"])
    assert (kr.model == "kriging").all(), "hex_p2.parquet must hold the deployed kriging predictions"
    out = unt[["iso3", "h3", "population"]].assign(pred_gbm_ln=pg.astype(np.float32), sigma_gbm=sg.astype(np.float32),
                                                   nearest_ring=U[:, 6].astype(np.int16))
    out = out.merge(kr.rename(columns={"pred_ln": "pred_kriging_ln", "sigma": "sigma_kriging"}).drop(columns="model"),
                    on=["iso3", "h3"], how="left")
    assert out.pred_kriging_ln.notna().all() and len(out) == len(kr)
    out = out.sort_values(["iso3", "h3"]).reset_index(drop=True)
    f = DER / "p2v2_frozen_predictions.parquet"
    out.to_parquet(f, index=False)

    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    rec = {"adr": "ADR-006", "frozen_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "trained_on_quarter": "2026Q3", "test_quarter": "2026Q4 (not yet published when frozen)",
           "file": str(f.relative_to(DATA)), "sha256": sha256(f), "rows": int(len(out)), "code_commit": commit,
           "rows_by_country": out.groupby("iso3").size().to_dict(),
           "median_pred_mbps": {m: {k: round(float(np.exp(g[c].median())), 1) for k, g in out.groupby("iso3")}
                                for m, c in (("kriging", "pred_kriging_ln"), ("lightgbm", "pred_gbm_ln"))},
           "seconds": round(time.time() - t0)}
    (ROOT / "data/outputs/p2v2_frozen.json").write_text(json.dumps(rec, indent=1))
    sm.log(f"frozen {rec['rows']:,} rows · sha256 {rec['sha256'][:16]}… · {rec['seconds']} s")


if __name__ == "__main__":
    main()
