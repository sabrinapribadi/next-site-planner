"""P1 inference on synthetic hexagons: exact Gi* p-values hold their size on shuffled data; block bootstrap is centred."""

import h3
import numpy as np

from src.spatialstats import block_bootstrap_shares, gi_star, ring1_neighbours

CENTRE = h3.latlng_to_cell(-6.2, 106.8, 8)


def _grid(k=25):
    return np.array(sorted(h3.grid_disk(CENTRE, k)))         # 1,951 hexagons


def test_exact_p_values_keep_their_size_where_the_normal_approximation_does_not():
    rng = np.random.default_rng(0)
    hs = _grid(); nb = ring1_neighbours(hs)
    x = np.log(rng.lognormal(3, 1.2, len(hs)) + rng.exponential(200, len(hs)) * (rng.random(len(hs)) < 0.05))  # skewed, no spatial pattern
    _, p_norm, p_exact = gi_star(x, nb)
    assert abs(np.mean(p_exact < 0.05) - 0.05) < 0.02
    assert np.mean(p_exact < 0.01) < 0.02


def test_planted_slow_cluster_is_found():
    rng = np.random.default_rng(1)
    hs = _grid(); nb = ring1_neighbours(hs)
    x = rng.normal(3.5, 0.6, len(hs))
    slow = np.isin(hs, list(h3.grid_disk(hs[300], 2)))
    x[slow] -= 2.5
    z, _, p = gi_star(x, nb)
    assert np.mean((p[slow] < 0.001) & (z[slow] < 0)) > 0.5


def test_block_bootstrap_interval_contains_the_estimate():
    rng = np.random.default_rng(2)
    hs = _grid(40)
    pop = rng.gamma(2, 500, len(hs)); speed = rng.lognormal(3, 1, len(hs))
    blocks = np.array([h3.cell_to_parent(h, 6) for h in hs])
    below = {10.0: speed < 10}
    est = (pop * below[10.0]).sum() / pop.sum()
    lo, hi = block_bootstrap_shares(blocks, pop, below, 500, rng)[10.0]
    assert lo < est < hi and hi - lo < 0.2
