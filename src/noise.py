"""Measurement noise in crowdsourced speed tiles and empirical-Bayes shrinkage (ADR-005).

Noise model, from pairs of tiles i, j in the same hexagon with n_i, n_j tests:
    E[(y_i - y_j)^2] = 2 * s2_micro + s2_test * (1/n_i + 1/n_j)
A hexagon's value is the test-weighted mean of its tiles, so its noise variance is
    v_h = (s2_test * sum(n) + s2_micro * sum(n^2)) / sum(n)^2
Shrinkage (Fay & Herriot 1979): theta_h ~ N(g*y + (1-g)*mu, g*v), g = s2_u / (s2_u + v).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import nnls


def tile_pairs(tiles: pd.DataFrame, max_tiles: int = 12, seed: int = 0) -> pd.DataFrame:
    """All pairs of tiles in the same hexagon (at most max_tiles tiles per hexagon): columns d2, inv_n."""
    rng = np.random.default_rng(seed)
    out = []
    for _, g in tiles.groupby("h3", sort=False):
        if len(g) < 2:
            continue
        if len(g) > max_tiles:
            g = g.iloc[rng.choice(len(g), max_tiles, replace=False)]
        y, n = g["y"].to_numpy(), g["tests"].to_numpy(float)
        i, j = np.triu_indices(len(g), 1)
        out.append(np.c_[(y[i] - y[j]) ** 2, 1 / n[i] + 1 / n[j]])
    a = np.vstack(out) if out else np.empty((0, 2))
    return pd.DataFrame(a, columns=["d2", "inv_n"])


def fit_noise(pairs: pd.DataFrame) -> tuple[float, float]:
    """(s2_test, s2_micro) by non-negative least squares of d2 on [1/n_i + 1/n_j, 2]."""
    A = np.c_[pairs["inv_n"].to_numpy(), np.full(len(pairs), 2.0)]
    (s2_test, s2_micro), _ = nnls(A, pairs["d2"].to_numpy())
    return float(s2_test), float(s2_micro)


def hex_noise_var(sum_n: np.ndarray, sum_n2: np.ndarray, s2_test: float, s2_micro: float) -> np.ndarray:
    return (s2_test * sum_n + s2_micro * sum_n2) / sum_n ** 2


def sigma2_u(y: np.ndarray, mu: np.ndarray, v: np.ndarray, floor: float = 0.01) -> float:
    """Method-of-moments variance of the true value around the prior mean."""
    return float(max(np.mean((y - mu) ** 2 - v), floor))


def shrink(y: np.ndarray, v: np.ndarray, mu: np.ndarray, s2u: float) -> tuple[np.ndarray, np.ndarray]:
    g = s2u / (s2u + v)
    return g * y + (1 - g) * mu, g * v
