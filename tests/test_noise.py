"""ADR-005: the tile-pair noise fit recovers known variances; shrinkage moves noisy hexagons most."""

import numpy as np
import pandas as pd

from src.noise import fit_noise, hex_noise_var, shrink, sigma2_u, tile_pairs
from src.spatialmodel import krige, xyz


def test_noise_fit_recovers_test_and_micro_variance():
    rng = np.random.default_rng(0); rows = []
    for h in range(6000):
        true = rng.normal(3, 1)
        for t in range(rng.integers(2, 5)):
            n = rng.integers(1, 20)
            rows.append((f"h{h}", n, true + rng.normal(0, np.sqrt(0.3)) + rng.normal(0, np.sqrt(1.0 / n))))
    tiles = pd.DataFrame(rows, columns=["h3", "tests", "y"])
    s2_test, s2_micro = fit_noise(tile_pairs(tiles))
    assert abs(s2_test - 1.0) < 0.12 and abs(s2_micro - 0.3) < 0.05


def test_hex_noise_and_shrinkage():
    v = hex_noise_var(np.array([1.0, 100.0]), np.array([1.0, 100.0]), 1.0, 0.3)   # one tile: 1 test vs 100 tests
    assert v[0] > 10 * v[1]
    m, pv = shrink(np.array([0.0, 0.0]), v, np.array([1.0, 1.0]), 0.2)
    assert m[0] > m[1] and pv[0] < v[0]                                             # the 1-test hexagon moves most
    assert sigma2_u(np.zeros(3), np.zeros(3), np.ones(3)) == 0.01                   # floor


def test_leave_one_out_kriging_never_uses_the_point_itself():
    rng = np.random.default_rng(1)
    lat, lng = 50 + rng.random(500) * 0.2, 8 + rng.random(500) * 0.2
    p = xyz(lat, lng); y = rng.normal(0, 1, 500); y[0] = 100.0
    loo, _ = krige(p, y, p, ("exponential", 0.0, 1.0, 2.0), k=8, leave_one_out=True)
    assert abs(loo[0]) < 5                                                          # its own 100 is not used
