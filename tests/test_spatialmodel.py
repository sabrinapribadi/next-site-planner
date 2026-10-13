"""ADR-004 building blocks: neighbour features never read the query's own value; kriging honours data and the trend."""

import h3
import numpy as np

from src.spatialmodel import fit_variogram, krige, neighbour_features, xyz

C = h3.latlng_to_cell(52.5, 13.4, 8)


def test_neighbour_features_use_rings_only_never_self():
    r1 = list(h3.grid_ring(C, 1)); r2 = list(h3.grid_ring(C, 2))
    train = {C: 100.0, r1[0]: 1.0, r1[1]: 3.0, r2[0]: 10.0}
    f = neighbour_features(np.array([C]), train)[0]
    assert f[0] == 2.0 and f[1] == 2 and f[2] == 10.0 and f[3] == 1      # ring-1 mean 2 (self's 100 ignored), ring 2
    assert np.isnan(f[4]) and f[5] == 0 and f[6] == 1 and f[7] == 2.0      # nothing in ring 3; nearest ring = 1


def test_nearest_ring_beyond_three_and_cap():
    far = list(h3.grid_ring(C, 5))[0]
    f = neighbour_features(np.array([C]), {far: 4.0}, cap=10)[0]
    assert f[6] == 5 and f[7] == 4.0 and f[1] == f[3] == f[5] == 0
    g = neighbour_features(np.array([C]), {far: 4.0}, cap=3)[0]
    assert g[6] == 4 and np.isnan(g[7])                                    # beyond the cap


def test_kriging_reproduces_a_smooth_field_and_is_exact_at_data():
    rng = np.random.default_rng(0)
    lat = 52 + rng.random(3000) * 0.6; lng = 13 + rng.random(3000) * 0.9
    p = xyz(lat, lng); y = np.sin(lat * 8) + np.cos(lng * 6) + rng.normal(0, 0.02, 3000)
    v = fit_variogram(p, y, max_km=30)
    assert v[0] in ("exponential", "spherical") and v[3] > 1                # a range of more than 1 km for a smooth field
    ql, qg = 52.1 + rng.random(300) * 0.4, 13.1 + rng.random(300) * 0.6
    pred, var = krige(p, y, xyz(ql, qg), v, k=24)
    truth = np.sin(ql * 8) + np.cos(qg * 6)
    assert np.sqrt(np.mean((pred - truth) ** 2)) < 0.08 and (var >= -1e-9).all()
    at, _ = krige(p, y, p[:50], (v[0], 0.0, v[2], v[3]), k=24)            # no nugget: exact interpolator
    assert np.allclose(at, y[:50], atol=1e-6)
