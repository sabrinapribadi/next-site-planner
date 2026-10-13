"""Inference for P1 (ADR-002, with the deviations logged there on 2026-10-13).

- Gi* p-values by exact conditional randomisation: hexagon i keeps its value, its k neighbours are random draws
  from the country's values. The null distribution of their sum is the k-fold convolution of the empirical
  distribution (binned), so tail probabilities are exact down to the tiny values that FDR control over
  100,000+ tests needs; a normal approximation is wrong with 1–6 neighbours and skewed speeds, and 9,999
  simulated permutations cannot reach p < 1e-4.
- Spatial block bootstrap for people-weighted shares: blocks are H3 parents (resolution 5, ~250 km²) with
  Poisson(1) weights, so neighbouring, correlated hexagons are resampled together. Resampling speed tiles was
  pre-registered but inflates noise around the speed bar and biases the share upwards (logged in ADR-002).
"""

from __future__ import annotations

import h3
import numpy as np
from scipy.stats import norm

BINS = 2048


def ring1_neighbours(h3s: np.ndarray) -> list[np.ndarray]:
    """Indices of each hexagon's measured ring-1 neighbours (self excluded)."""
    idx = {h: i for i, h in enumerate(h3s)}
    return [np.array([idx[g] for g in h3.grid_ring(h, 1) if g in idx], dtype=np.int64) for h in h3s]


def _sum_cdfs(x: np.ndarray, kmax: int) -> tuple[float, float, list[np.ndarray]]:
    lo, hi = float(x.min()), float(x.max())
    dx = (hi - lo) / BINS if hi > lo else 1.0
    pmf = np.bincount(np.clip(((x - lo) / dx).astype(int), 0, BINS - 1), minlength=BINS) / len(x)
    cdfs, cur = [np.array([1.0])], np.array([1.0])
    for _ in range(kmax):
        cur = np.convolve(cur, pmf)
        cdfs.append(np.cumsum(cur))
    return lo, dx, cdfs


def gi_star(x: np.ndarray, nbrs: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Gi* (binary ring-1 weights, self included): z-scores, normal p-values, exact conditional p-values (two-sided)."""
    n, xbar, s = len(x), x.mean(), x.std()
    k = np.array([len(v) for v in nbrs])
    others = np.array([x[v].sum() for v in nbrs])
    w = k + 1
    z = np.full(n, np.nan)
    ok = (k >= 1) & (s > 0)
    z[ok] = (x[ok] + others[ok] - xbar * w[ok]) / (s * np.sqrt((n * w[ok] - w[ok] ** 2) / (n - 1)))
    p_norm = 2 * norm.sf(np.abs(z))
    lo, dx, cdfs = _sum_cdfs(x, int(k.max()) if len(k) else 0)
    p_exact = np.full(n, np.nan)
    for kk in range(1, len(cdfs)):
        m = ok & (k == kk)
        if not m.any():
            continue
        j = np.clip(np.floor((others[m] - kk * lo) / dx).astype(int), 0, len(cdfs[kk]) - 1)
        c = cdfs[kk]
        p_low = c[j]
        p_high = 1 - np.where(j > 0, c[np.maximum(j - 1, 0)], 0.0)
        p_exact[m] = np.minimum(1.0, 2 * np.minimum(p_low, p_high))
    return z, p_norm, p_exact


def block_bootstrap_shares(blocks: np.ndarray, pop: np.ndarray, below: dict[float, np.ndarray], reps: int,
                           rng: np.random.Generator) -> dict[float, list[float]]:
    """95% percentile intervals of people-weighted shares below each bar, resampling spatial blocks."""
    codes = np.unique(blocks, return_inverse=True)[1]
    nb = codes.max() + 1
    den = np.bincount(codes, weights=pop, minlength=nb)
    W = rng.poisson(1.0, size=(reps, nb)).astype(float)
    d = W @ den
    out = {}
    for b, mask in below.items():
        num = np.bincount(codes, weights=pop * mask, minlength=nb)
        sh = (W @ num) / np.where(d > 0, d, np.nan)
        out[b] = [float(np.nanpercentile(sh, 2.5)), float(np.nanpercentile(sh, 97.5))]
    return out
