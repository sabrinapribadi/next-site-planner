"""ADR-003 rules on synthetic hexagons: Degree of Urbanisation classes, gap types, data contracts, manifest."""

import h3
import numpy as np
import pandas as pd

from src.contracts import check_hex_latest, check_panel_quarters, manifest
from src.morphology import RURAL, URBAN_CENTRE, URBAN_CLUSTER, cells_within_ring, degree_of_urbanisation, gap_type

CFG = {"urban_centre": {"min_density_km2": 1500, "min_population": 50000},
       "urban_cluster": {"min_density_km2": 300, "min_population": 5000}}
JKT = h3.latlng_to_cell(-6.2, 106.8, 8)
AREA = h3.cell_area(JKT, unit="km^2")


def _disk(centre, k):
    return pd.Series(sorted(h3.grid_disk(centre, k)))


def test_dense_large_cluster_is_urban_centre_and_its_fringe_an_urban_cluster():
    core = set(h3.grid_disk(JKT, 4))                       # 61 hexagons
    fringe = set(h3.grid_disk(JKT, 6)) - core
    hs = pd.Series(sorted(core | fringe))
    pop = hs.map(lambda h: 3000 * AREA if h in core else 500 * AREA)  # people per hexagon from density
    m = degree_of_urbanisation(hs, pop, CFG)
    assert (m[hs.isin(core)] == URBAN_CENTRE).all()        # 61 × 3000 × 0.74 ≈ 135k people >= 50k
    assert (m[hs.isin(fringe)] == URBAN_CLUSTER).all()


def test_dense_but_small_cluster_is_not_an_urban_centre():
    hs = _disk(JKT, 1)                                     # 7 hexagons × 3000/km² × 0.74 km² ≈ 15k people
    m = degree_of_urbanisation(hs, pd.Series(3000 * AREA, index=hs.index), CFG)
    assert (m == URBAN_CLUSTER).all()


def test_sparse_hexagons_are_rural_and_clusters_need_contiguity():
    far = h3.latlng_to_cell(-7.5, 110.0, 8)
    hs = pd.Series([JKT, far])
    m = degree_of_urbanisation(hs, pd.Series([4000 * AREA, 4000 * AREA]), CFG)
    assert (m == RURAL).all()                              # each alone is under 5,000 people


def test_gap_types():
    hs = pd.Series([JKT, h3.latlng_to_cell(-7.5, 110.0, 8), h3.latlng_to_cell(-8.0, 112.0, 8), h3.latlng_to_cell(-3.0, 120.0, 8)])
    nb = list(h3.grid_ring(hs[0], 1))[0]                   # a cell next to the first hexagon only
    near = cells_within_ring(hs, pd.Series([nb]), pd.Series([2]), k=1)
    assert near.tolist() == [2, 0, 0, 0]
    g = gap_type(pd.Series([5.0, 5.0, np.nan, 40.0]), near, bar=10)
    assert g.tolist() == ["capacity", "coverage", "unmeasured", "none"]


def test_contracts_catch_duplicates_and_bad_values():
    ok = pd.DataFrame({"iso3": ["IDN", "DEU"], "h3": [JKT, h3.latlng_to_cell(52.5, 13.4, 8)], "population": [10.0, 5.0],
                       "places": [1, 0], "cells": [0, 3], "mobile_down_mbps": [12.0, np.nan], "mobile_tests": [4, 0]})
    assert check_hex_latest(ok, ["IDN", "DEU"]) == []
    bad = pd.concat([ok, ok.iloc[[0]]]).assign(population=[10.0, -1.0, 10.0])
    broken = check_hex_latest(bad, ["IDN", "DEU", "USA"])
    assert any("not unique" in b for b in broken) and any("negative" in b for b in broken) and any("without rows" in b for b in broken)


def test_panel_quarters_and_manifest(tmp_path):
    assert check_panel_quarters({(2026, 2), (2026, 3)}, (2026, 1), (2026, 3)) == ["missing quarters: [(2026, 1)]"]
    f = tmp_path / "a.parquet"; f.write_bytes(b"abc")
    m = manifest(tmp_path, [f], {"a.parquet": 3})
    assert m["inputs"][0]["sha256"] == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad" and m["inputs"][0]["rows"] == 3
