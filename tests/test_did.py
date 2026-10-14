"""ADR-007: the staggered DiD recovers a known, growing effect with flat pre-trends, and keeps units tested in both quarters only."""

import numpy as np

from src.did import event_study


def _panel(seed=0, U=6000, T=15, effect=0.2, growth=0.05):
    rng = np.random.default_rng(seed)
    G = np.full(U, np.inf)
    treated = rng.random(U) < 0.4
    G[treated] = rng.integers(6, 12, treated.sum())               # staggered first-treated quarters
    stratum = rng.integers(0, 2, U)
    unit_fe = rng.normal(3, 1, U)[:, None]
    time_fe = np.linspace(0, 0.6, T)[None, :] + 0.2 * stratum[:, None] * np.linspace(0, 1, T)[None, :]
    e = np.arange(T)[None, :] - G[:, None]
    tau = np.where(e >= 0, effect + growth * np.clip(e, 0, None), 0.0)     # effect grows over time
    Y = unit_fe + time_fe + tau + rng.normal(0, 0.3, (U, T))
    Y[rng.random((U, T)) < 0.3] = np.nan                                  # unbalanced: 30% of quarters untested
    block = np.arange(U) // 20
    return Y, G, stratum, block


def test_recovers_effect_and_flat_pretrends():
    Y, G, s, b = _panel()
    r = event_study(Y, G, s, b, range(-5, 5), reps=199, seed=1)
    truth = np.mean([0.2 + 0.05 * e for e in range(5)])
    assert abs(r["post_avg_0_4"]["att"] - truth) < 0.03
    lo, hi = r["post_avg_0_4"]["ci95"]
    assert lo < truth < hi
    assert r["pretrend"]["p_value"] > 0.01 and abs(r["event_time"][-3]["att"]) < 0.05


def test_no_effect_gives_interval_around_zero():
    Y, G, s, b = _panel(seed=2, effect=0.0, growth=0.0)
    r = event_study(Y, G, s, b, range(-5, 5), reps=199, seed=3)
    lo, hi = r["post_avg_0_4"]["ci95"]
    assert lo < 0 < hi


def test_base_filter_restricts_units():
    Y, G, s, b = _panel(seed=4)
    r = event_study(Y, G, s, b, range(0, 2), reps=49, base_filter=lambda yb: yb < -100)   # nothing passes
    assert r["event_time"] == {}


def test_filter_on_another_matrix():
    Y, G, s, b = _panel(seed=5)
    ind = np.where(np.isnan(Y), np.nan, (Y > 3).astype(float))
    r_all = event_study(ind, G, s, b, range(0, 2), reps=49)
    r_low = event_study(ind, G, s, b, range(0, 2), reps=49, filter_Y=Y, base_filter=lambda yb: yb < 3)
    assert r_low["event_time"][0]["treated_obs"] < r_all["event_time"][0]["treated_obs"]
