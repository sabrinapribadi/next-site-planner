"""Morphology and gap type per hexagon (ADR-003, E1 and E2).

Morphology follows the Degree of Urbanisation (Eurostat et al. 2021) on H3 r8 instead of 1 km² squares:
  urban centre  — contiguous hexagons each >= 1,500 people/km², >= 50,000 people in the cluster
  urban cluster — contiguous hexagons each >= 300 people/km², >= 5,000 people, minus urban-centre hexagons
  rural         — everything else
Contiguity is H3 ring-1 (six neighbours), so the manual's 4- and 8-point rules collapse into one; no gap-filling.

Gap type, for populated hexagons only:
  coverage   — measured speed below the bar and no LTE/5G cell within ring-1
  capacity   — measured speed below the bar and at least one LTE/5G cell within ring-1
  unmeasured — no speed measurement
  none       — measured speed at or above the bar
"""

from __future__ import annotations

import h3
import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

URBAN_CENTRE, URBAN_CLUSTER, RURAL = "urban_centre", "urban_cluster", "rural"


def density_km2(h3s: pd.Series, population: pd.Series) -> np.ndarray:
    area = np.array([h3.cell_area(h, unit="km^2") for h in h3s])
    return population.to_numpy(dtype=float) / area


def _clusters(h3s: np.ndarray, pop: np.ndarray, keep: np.ndarray, min_pop: float) -> np.ndarray:
    """Mask of hexagons in ring-1-contiguous clusters of `keep` hexagons whose total population >= min_pop."""
    idx = np.flatnonzero(keep)
    if len(idx) == 0:
        return np.zeros(len(h3s), dtype=bool)
    pos = {h: i for i, h in enumerate(h3s[idx])}
    rows, cols = [], []
    for i, h in enumerate(h3s[idx]):
        for g in h3.grid_ring(h, 1):
            j = pos.get(g)
            if j is not None:
                rows.append(i); cols.append(j)
    n = len(idx)
    graph = coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(n, n))
    _, lab = connected_components(graph, directed=False)
    total = np.bincount(lab, weights=pop[idx])
    out = np.zeros(len(h3s), dtype=bool)
    out[idx] = total[lab] >= min_pop
    return out


def degree_of_urbanisation(h3s: pd.Series, population: pd.Series, cfg: dict) -> pd.Series:
    """Morphology class per hexagon (one country at a time, so clusters do not cross borders)."""
    hs, pop = h3s.to_numpy(), population.to_numpy(dtype=float)
    d = density_km2(h3s, population)
    uc, ucl = cfg["urban_centre"], cfg["urban_cluster"]
    centre = _clusters(hs, pop, d >= uc["min_density_km2"], uc["min_population"])
    cluster = _clusters(hs, pop, d >= ucl["min_density_km2"], ucl["min_population"]) & ~centre
    return pd.Series(np.where(centre, URBAN_CENTRE, np.where(cluster, URBAN_CLUSTER, RURAL)), index=h3s.index)


def cells_within_ring(h3s: pd.Series, cell_h3: pd.Series, cell_n: pd.Series, k: int = 1) -> np.ndarray:
    """Number of cells in each hexagon's ring-k disk (self included)."""
    have = dict(zip(cell_h3.to_numpy(), cell_n.to_numpy()))
    return np.array([sum(have.get(g, 0) for g in h3.grid_disk(h, k)) for h in h3s], dtype=float)


def gap_type(speed_mbps: pd.Series, cells_nearby: np.ndarray, bar: float) -> pd.Series:
    s = speed_mbps.to_numpy(dtype=float)
    measured = ~np.isnan(s)
    below = measured & (s < bar)
    out = np.where(~measured, "unmeasured", np.where(~below, "none", np.where(cells_nearby > 0, "capacity", "coverage")))
    return pd.Series(out, index=speed_mbps.index)
