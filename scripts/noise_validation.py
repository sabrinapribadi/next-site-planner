"""ADR-005 check: does shrinkage remove noise or signal? (the Efron–Morris test, across quarters)

    python scripts/noise_validation.py

Shrink 2026 Q2 hexagon speeds exactly as in noise_followup.py (tile-pair noise model, leave-one-out kriging prior,
Fay–Herriot posterior), then predict the independently measured 2026 Q3 speed of the same hexagons.
If the shrunk Q2 value predicts Q3 better than the raw Q2 value, shrinkage removed noise. Q3's own noise is
independent of Q2's, so it adds the same constant to both errors and cannot favour either.
Writes data/outputs/p2c_noise_validation.json.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import h3
import numpy as np
import pandas as pd
import yaml
from scipy.stats import norm
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.hexgrid import connect  # noqa: E402
from src.noise import fit_noise, hex_noise_var, shrink, sigma2_u, tile_pairs  # noqa: E402
from src.spatialmodel import fit_variogram, krige, xyz  # noqa: E402

CFG = yaml.safe_load((ROOT / "configs" / "default_config.yaml").read_text())
DATA = Path(os.environ.get("GEO_DATA_DIR", "~/data/geo")).expanduser()


def hex_quarter(c, y: int, q: int) -> pd.DataFrame:
    t = c.sql(f"""SELECT iso3, h3_latlng_to_cell_string(tile_y, tile_x, 8) AS h3, tests, ln(greatest(avg_d_kbps, 1) / 1000) AS y
                  FROM '{DATA}/ookla7/mobile/{y}q{q}.parquet' WHERE tests > 0""").df()
    return t


def main() -> None:
    best_k = json.loads((ROOT / "data/outputs/p2_speed_model.json").read_text())["designs"]["r6"]["kriging_best_k"]
    c = connect()
    t2, t3 = hex_quarter(c, 2026, 2), hex_quarter(c, 2026, 3)
    pop = c.sql(f"SELECT iso3, h3, population FROM '{DATA}/derived/hex_latest.parquet'").df()
    out = {}
    for k in CFG["countries"]:
        a = t2[t2.iso3 == k]
        s2t, s2m = fit_noise(tile_pairs(a, seed=1))
        g = a.assign(w=a.tests * a.y, n2=a.tests.astype(float) ** 2).groupby("h3").agg(sw=("w", "sum"), sum_n=("tests", "sum"), sum_n2=("n2", "sum"))
        g["y"] = g.sw / g.sum_n
        g["v"] = hex_noise_var(g.sum_n.to_numpy(float), g.sum_n2.to_numpy(float), s2t, s2m)
        p = xyz(*np.array([h3.cell_to_latlng(x) for x in g.index]).T)
        vario = fit_variogram(p, g.y.to_numpy(), seed=0)
        mu, _ = krige(p, g.y.to_numpy(), p, vario, k=best_k, leave_one_out=True)
        s2u = sigma2_u(g.y.to_numpy(), mu, g.v.to_numpy())
        pm, pv = shrink(g.y.to_numpy(), g.v.to_numpy(), mu, s2u)
        g = g.assign(mu=mu, post=pm, post_v=pv)
        b = t3[t3.iso3 == k]
        s2t3, s2m3 = fit_noise(tile_pairs(b, seed=1))
        q3 = b.assign(w=b.tests * b.y, n2=b.tests.astype(float) ** 2).groupby("h3").agg(sw=("w", "sum"), n3=("tests", "sum"), n23=("n2", "sum"))
        q3["y3"] = q3.sw / q3.n3
        q3["v3"] = hex_noise_var(q3.n3.to_numpy(float), q3.n23.to_numpy(float), s2t3, s2m3)
        j = g.join(q3[["y3", "n3", "v3"]], how="inner").join(pop[pop.iso3 == k].set_index("h3")["population"], how="left").fillna({"population": 0})
        e = lambda est: float(np.mean((est - j.y3) ** 2))
        slow3 = (j.y3 < np.log(25)).to_numpy()
        res = {"hexagons_in_both_quarters": int(len(j)), "mse_raw_q2": e(j.y), "mse_prior_only": e(j.mu), "mse_shrunk_q2": e(j.post)}
        res["mse_reduction_shrunk_vs_raw"] = 1 - res["mse_shrunk_q2"] / res["mse_raw_q2"]
        if 0 < slow3.mean() < 1:
            res["auc_below_25_raw"] = float(roc_auc_score(slow3, -j.y))
            res["auc_below_25_shrunk"] = float(roc_auc_score(slow3, norm.cdf((np.log(25) - j.post) / np.sqrt(j.post_v))))
        w = j.population.to_numpy()
        if w.sum() > 0:   # people-weighted share below 25 in Q3 (raw, noisy) vs what each Q2 estimate implies
            res["q3_raw_share_below_25"] = float((w * slow3).sum() / w.sum())
            res["q2_raw_share_below_25"] = float((w * (j.y < np.log(25))).sum() / w.sum())
            res["q2_shrunk_share_below_25"] = float((w * norm.cdf((np.log(25) - j.post) / np.sqrt(j.post_v))).sum() / w.sum())
            # level check: add Q3's own test noise back to the shrunk Q2 posterior; this should reproduce the noisy Q3 share
            res["q3_noisy_share_predicted_from_shrunk_q2"] = float((w * norm.cdf((np.log(25) - j.post) / np.sqrt(j.post_v + j.v3))).sum() / w.sum())
        out[k] = res
        print(k, {kk: round(vv, 3) if isinstance(vv, float) else vv for kk, vv in res.items()}, flush=True)
    (ROOT / CFG["paths"]["outputs_dir"] / "p2c_noise_validation.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
