"""P2 building blocks (ADR-004): neighbour features from training hexagons only, and local ordinary kriging.

Neighbour features for a query hexagon come from a dict {h3: value} of *training* hexagons. The query's own
entry is never read (rings start at 1), so passing a dict that contains the query cannot leak its target.

Kriging: local ordinary kriging with the k nearest training hexagons (a moving search neighbourhood, as in gstat's
nmax; Pebesma 2004), solved in batches. Variogram: exponential or spherical, fitted to the binned empirical
semivariogram by Cressie's (1985) weighted least squares (weights N_j / gamma_j^2), the better-fitting model kept.
Distances are chord distances on a 6,371 km sphere (equal to great-circle distance at these scales).
"""

from __future__ import annotations

import h3
import numpy as np
from scipy.optimize import curve_fit
from scipy.spatial import cKDTree

R_EARTH = 6371.0
NBR_NAMES = ["nb1_mean", "nb1_n", "nb2_mean", "nb2_n", "nb3_mean", "nb3_n", "nearest_ring", "nearest_mean"]


def neighbour_features(query: np.ndarray, train: dict[str, float], cap: int = 10) -> np.ndarray:
    """Per query hexagon: mean and count of training values in rings 1, 2, 3; ring distance (≤ cap, else cap + 1)
    and mean value of the nearest ring that has any training hexagon (NaN if none within cap)."""
    out = np.full((len(query), 8), np.nan)
    for i, x in enumerate(query):
        found = False
        for k in range(1, cap + 1):
            vals = [train[y] for y in h3.grid_ring(x, k) if y in train]
            if k <= 3:
                out[i, 2 * (k - 1)] = np.mean(vals) if vals else np.nan
                out[i, 2 * (k - 1) + 1] = len(vals)
            if vals and not found:
                out[i, 6], out[i, 7], found = k, np.mean(vals), True
            if found and k >= 3:
                break
        if not found:
            out[i, 6] = cap + 1
    return out


def xyz(lat: np.ndarray, lng: np.ndarray) -> np.ndarray:
    la, lo = np.radians(lat), np.radians(lng)
    return R_EARTH * np.c_[np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)]


def expo(h, nugget, psill, rng):
    return nugget + psill * (1.0 - np.exp(-h / rng))


def sph(h, nugget, psill, rng):
    r = np.minimum(h / rng, 1.0)
    return nugget + psill * (1.5 * r - 0.5 * r ** 3)


MODELS = {"exponential": expo, "spherical": sph}


def fit_variogram(p: np.ndarray, y: np.ndarray, max_km: float = 30.0, n_sample: int = 20000, bins: int = 15,
                  seed: int = 0) -> tuple[str, float, float, float]:
    """(model, nugget, partial sill, range km): exponential and spherical fitted by Cressie's weighted least squares
    to the binned empirical semivariogram; the model with the lower weighted residual is kept."""
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(y), size=min(n_sample, len(y)), replace=False)
    ps, ys = p[idx], y[idx]
    pairs = cKDTree(ps).query_pairs(max_km, output_type="ndarray")
    if len(pairs) > 2_000_000:
        pairs = pairs[rng.choice(len(pairs), 2_000_000, replace=False)]
    d = np.linalg.norm(ps[pairs[:, 0]] - ps[pairs[:, 1]], axis=1)
    g = 0.5 * (ys[pairs[:, 0]] - ys[pairs[:, 1]]) ** 2
    edges = np.linspace(0, max_km, bins + 1)
    b = np.clip(np.digitize(d, edges) - 1, 0, bins - 1)
    nj = np.bincount(b, minlength=bins)
    ok = nj > 30
    hm = np.bincount(b, weights=d, minlength=bins)[ok] / nj[ok]
    gm = np.bincount(b, weights=g, minlength=bins)[ok] / nj[ok]
    var = float(np.var(ys))
    best = ("exponential", 0.5 * var, 0.5 * var, max_km / 3, np.inf)
    for name, fn in MODELS.items():
        try:   # Cressie (1985): minimise sum N_j (gamma_hat_j - gamma(h_j))^2 / gamma(h_j)^2, with gamma(h_j) ~ gamma_hat_j
            (n, s_, r), _ = curve_fit(fn, hm, gm, p0=[0.3 * var, 0.7 * var, max_km / 3], sigma=gm / np.sqrt(nj[ok]),
                                      bounds=([0, 1e-6, 0.05], [2 * var, 3 * var, 10 * max_km]), maxfev=20000)
        except (RuntimeError, ValueError):
            continue
        obj = float(np.sum(nj[ok] * (gm - fn(hm, n, s_, r)) ** 2 / fn(hm, n, s_, r) ** 2))
        if obj < best[4]:
            best = (name, float(n), float(s_), float(r), obj)
    return best[:4]


def krige(p_train: np.ndarray, y_train: np.ndarray, p_query: np.ndarray, vario: tuple[str, float, float, float],
          k: int = 32, batch: int | None = None, leave_one_out: bool = False) -> tuple[np.ndarray, np.ndarray]:
    """Local ordinary kriging: prediction and kriging variance for each query point.
    leave_one_out: the query points are the training points; each is predicted from its k nearest *other* points."""
    name, n, s, r = vario
    fn = MODELS[name]
    gam = lambda h: np.where(h > 0, fn(h, n, s, r), 0.0)  # γ(0) = 0
    k = min(k, len(y_train) - (1 if leave_one_out else 0))
    batch = batch or max(500, int(2e8 / (k * k * 3 * 8)))   # keep the (batch, k, k, 3) distance array near 200 MB
    tree = cKDTree(p_train)
    pred, var = np.empty(len(p_query)), np.empty(len(p_query))
    for a in range(0, len(p_query), batch):
        q = p_query[a:a + batch]
        if leave_one_out:
            dq, iq = tree.query(q, k=k + 1)
            dq, iq = dq[:, 1:], iq[:, 1:]          # drop the point itself (distance 0)
        else:
            dq, iq = tree.query(q, k=k)
        if k == 1 and dq.ndim == 1:
            dq, iq = dq[:, None], iq[:, None]
        pts = p_train[iq]                                                   # (B, k, 3)
        dd = np.linalg.norm(pts[:, :, None, :] - pts[:, None, :, :], axis=-1)
        A = np.ones((len(q), k + 1, k + 1)); A[:, :k, :k] = gam(dd); A[:, k, k] = 0.0
        bvec = np.ones((len(q), k + 1)); bvec[:, :k] = gam(dq)
        w = np.linalg.solve(A, bvec[..., None])[..., 0]
        pred[a:a + batch] = np.einsum("bk,bk->b", w[:, :k], y_train[iq])
        var[a:a + batch] = np.einsum("bk,bk->b", w, bvec)
    return pred, var
