"""Staggered difference-in-differences (Callaway & Sant'Anna 2021), unconditional within strata, with a spatial block
bootstrap (ADR-007).

Inputs are a unit × quarter matrix Y (NaN where a hexagon was not tested), each unit's first-treated quarter G
(np.inf = never treated), its stratum (country × area type) and its bootstrap block (H3 resolution 5).
For group g and quarter t, with base quarter b = g - base_offset:
    ATT(g, t) = mean over treated units of (Y_t - Y_b)  -  mean over comparison units of (Y_t - Y_b)
Comparison units are never treated or not yet treated: G > max(t, b) + anticipation. Only units tested in both
quarters count. Cells are computed within strata and combined with weights equal to the number of treated units;
event-time estimates (e = t - g) combine cells the same way.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import chi2


def event_study(Y: np.ndarray, G: np.ndarray, stratum: np.ndarray, block: np.ndarray, events: range,
                anticipation: int = 1, base_offset: int = 2, reps: int = 499, seed: int = 0,
                base_filter=None, min_cell: int = 5) -> dict:
    """Event-time ATTs with 95% bootstrap intervals, the average over post periods 0..4, and a joint pre-trend test.
    base_filter(y_base) -> bool mask keeps only units whose base-period value passes (e.g. below a speed bar)."""
    U, T = Y.shape
    rng = np.random.default_rng(seed)
    blocks, binv = np.unique(block, return_inverse=True)
    W = rng.poisson(1.0, size=(reps, len(blocks))).astype(float)
    groups = sorted(int(g) for g in np.unique(G[np.isfinite(G)]))
    strata = np.unique(stratum)
    acc = {e: [0.0, np.zeros(reps), 0.0, np.zeros(reps)] for e in events}   # point num, rep num, point den, rep den
    ncells = {e: 0 for e in events}
    ntreated = {e: 0 for e in events}
    for g in groups:
        b = g - base_offset
        if b < 0:
            continue
        for e in events:
            t = g + e
            if t < 0 or t >= T or t == b:
                continue
            d = Y[:, t] - Y[:, b]
            ok = ~np.isnan(d)
            if base_filter is not None:
                ok &= base_filter(Y[:, b])
            tr_all = ok & (G == g)
            co_all = ok & (G > max(t, b) + anticipation)
            for s in strata:
                tr, co = tr_all & (stratum == s), co_all & (stratum == s)
                ntr, nco = int(tr.sum()), int(co.sum())
                if ntr < min_cell or nco < min_cell:
                    continue
                att = d[tr].mean() - d[co].mean()
                Str = np.bincount(binv[tr], weights=d[tr], minlength=len(blocks)); Ntr = np.bincount(binv[tr], minlength=len(blocks)).astype(float)
                Sco = np.bincount(binv[co], weights=d[co], minlength=len(blocks)); Nco = np.bincount(binv[co], minlength=len(blocks)).astype(float)
                wtr, wco = W @ Ntr, W @ Nco
                with np.errstate(invalid="ignore", divide="ignore"):
                    att_r = (W @ Str) / wtr - (W @ Sco) / wco
                att_r = np.where(np.isfinite(att_r), att_r, att)
                acc[e][0] += ntr * att; acc[e][1] += wtr * att_r; acc[e][2] += ntr; acc[e][3] += wtr
                ncells[e] += 1; ntreated[e] += ntr
    out = {"event_time": {}}
    reps_by_e = {}
    for e in events:
        if acc[e][2] == 0:
            continue
        est = acc[e][0] / acc[e][2]
        r = acc[e][1] / np.where(acc[e][3] > 0, acc[e][3], np.nan)
        reps_by_e[e] = r
        out["event_time"][e] = {"att": float(est), "ci95": [float(np.nanpercentile(r, 2.5)), float(np.nanpercentile(r, 97.5))],
                                "se": float(np.nanstd(r)), "cells": ncells[e], "treated_obs": ntreated[e]}
    post = [e for e in range(0, 5) if e in out["event_time"]]
    if post:
        pe = np.mean([out["event_time"][e]["att"] for e in post]); pr = np.nanmean(np.vstack([reps_by_e[e] for e in post]), axis=0)
        out["post_avg_0_4"] = {"att": float(pe), "ci95": [float(np.nanpercentile(pr, 2.5)), float(np.nanpercentile(pr, 97.5))],
                               "pct_change": float(np.exp(pe) - 1), "pct_ci95": [float(np.exp(np.nanpercentile(pr, 2.5)) - 1), float(np.exp(np.nanpercentile(pr, 97.5)) - 1)]}
    pre = [e for e in (-5, -4, -3) if e in out["event_time"]]
    if pre:
        beta = np.array([out["event_time"][e]["att"] for e in pre])
        R = np.vstack([reps_by_e[e] for e in pre]).T
        R = R[np.isfinite(R).all(axis=1)]
        cov = np.cov(R, rowvar=False).reshape(len(pre), len(pre))
        stat = float(beta @ np.linalg.pinv(cov) @ beta)
        out["pretrend"] = {"events": pre, "wald": stat, "p_value": float(chi2.sf(stat, len(pre))),
                           "all_ci_include_0": bool(all(out["event_time"][e]["ci95"][0] <= 0 <= out["event_time"][e]["ci95"][1] for e in pre))}
    return out
