"""P3 follow-up (ADR-007 amendment 2): imputation arm re-implemented, plus post-hoc diagnostics.

    python scripts/new_site_diagnostics.py

Imputation (Borusyak, Jaravel & Spiess 2024): hexagon + stratum×quarter effects fitted on untreated observations
(event time < -1 or never treated), counterfactual predicted for treated observations, gaps averaged by event time.
Diagnostics (post-hoc): event studies of ln(tests) and of ln(mobile) - ln(fixed). Writes data/outputs/p3b_diagnostics.json.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyfixest as pf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
import new_site_effect as ns  # noqa: E402
from src.did import event_study  # noqa: E402


def imputation(d: dict, G: np.ndarray, reps: int = 499) -> dict:
    m = ~np.isnan(G)
    nev = np.flatnonzero(m & np.isinf(G)); cap = min(20 * int((m & np.isfinite(G)).sum()), ns.MAX_NEVER_REG)
    if len(nev) > cap:
        m = m.copy(); m[np.random.default_rng(11).choice(nev, size=len(nev) - cap, replace=False)] = False
    idx = np.flatnonzero(m); U, T = np.nonzero(~np.isnan(d["Ym"][idx]))
    g = G[idx][U]; rel = np.where(np.isfinite(g), T - g, -999)
    df = pd.DataFrame({"unit": idx[U], "st": d["strat"][idx][U] * 100 + T, "y": d["Ym"][idx][U, T], "rel": rel, "block": d["block"][idx][U]})
    untreated = df[(df.rel < -1)]
    fit = pf.feols("y ~ 1 | unit + st", data=untreated)
    tr = df[(df.rel >= ns.EVENTS.start) & (df.rel < ns.EVENTS.stop) & (df.rel != -999)].copy()
    tr = tr[tr.unit.isin(untreated.unit) & tr.st.isin(untreated.st)]
    tr["gap"] = tr.y.to_numpy() - np.asarray(fit.predict(newdata=tr))
    tr = tr[np.isfinite(tr.gap)]
    out = {"event_time": {int(e): float(v) for e, v in tr.groupby("rel").gap.mean().items()}}
    post = tr[(tr.rel >= 0) & (tr.rel <= 4)]
    blocks, inv = np.unique(post.block, return_inverse=True)
    W = np.random.default_rng(5).poisson(1.0, (reps, len(blocks)))
    S = np.bincount(inv, weights=post.gap, minlength=len(blocks)); N = np.bincount(inv, minlength=len(blocks))
    rep = (W @ S) / np.maximum(W @ N, 1)
    out["post_avg_0_4"] = {"att": float(post.gap.mean()), "ci95": [float(np.percentile(rep, 2.5)), float(np.percentile(rep, 97.5))],
                           "pct_change": float(np.exp(post.gap.mean()) - 1), "note": "first stage held fixed; interval slightly narrow"}
    return out


def main() -> None:
    t0 = time.time(); c = ns.connect(); res = {}
    for k in ns.CFG["countries"]:
        d = ns.build(k, c)
        if len(d["new_site"]) < ns.MIN_EVENTS:
            res[k] = "too few new-site events"; continue
        Gn = ns.G_for(d, d["new_site"])
        r = {}
        try:
            r["imputation_new_site_ring0"] = imputation(d, Gn)
        except Exception as ex:
            r["imputation_error"] = str(ex)[:300]
        Yt = np.where(d["Nm"] > 0, np.log(np.maximum(d["Nm"], 1)), np.nan)
        r["posthoc_tests_volume"] = ns.run(d, Gn, Yt)
        r["posthoc_mobile_minus_fixed"] = ns.run(d, Gn, d["Ym"] - d["Yf"])
        res[k] = r
        ns.log(k, "imputation", (r.get("imputation_new_site_ring0") or {}).get("post_avg_0_4"), "| tests", r["posthoc_tests_volume"].get("post_avg_0_4"),
               "| mobile-fixed", r["posthoc_mobile_minus_fixed"].get("post_avg_0_4"))
        (ROOT / "data/outputs/p3b_diagnostics.json").write_text(json.dumps(res, indent=1, default=str))
    ns.log("done in", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
