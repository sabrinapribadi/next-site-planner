"""ADR-001 aggregation rules on synthetic tiles: H3 assignment, test-weighted log mean, no zero-test tiles."""

import math

import h3
import pandas as pd
import pytest

from src.hexgrid import connect, counts_by_hex, speed_by_hex


@pytest.fixture(scope="module")
def c():
    return connect()


def test_tiles_land_in_their_h3_cell_and_speeds_are_test_weighted_log_means(c):
    lat, lon = -6.2, 106.8  # Jakarta
    t = pd.DataFrame({"iso3": ["IDN"] * 3, "tile_x": [lon, lon + 1e-4, lon + 0.5], "tile_y": [lat, lat + 1e-4, lat],
                      "avg_d_kbps": [10_000, 40_000, 5_000], "avg_u_kbps": [2_000, 8_000, 1_000], "avg_lat_ms": [30, 20, 50],
                      "tests": [1, 3, 2], "devices": [1, 2, 1], "year": 2026, "quarter": 3, "type": "mobile"})
    c.register("t", t)
    r = c.sql(speed_by_hex(c, "t")).df().set_index("h3")
    cell = h3.latlng_to_cell(lat, lon, 8)
    assert cell in r.index and len(r) == 2
    want = math.exp((1 * math.log(10_000) + 3 * math.log(40_000)) / 4) / 1000
    assert r.loc[cell, "down_mbps"] == pytest.approx(want) and r.loc[cell, "tests"] == 4 and r.loc[cell, "tiles"] == 2
    assert r.loc[cell, "latency_ms"] == pytest.approx((30 + 60) / 4)


def test_tiles_without_tests_are_ignored(c):
    t = pd.DataFrame({"iso3": ["DEU"], "tile_x": [13.4], "tile_y": [52.5], "avg_d_kbps": [50_000], "avg_u_kbps": [10_000],
                      "avg_lat_ms": [20], "tests": [0], "devices": [0], "year": 2026, "quarter": 3, "type": "mobile"})
    c.register("t0", t)
    assert len(c.sql(speed_by_hex(c, "t0")).df()) == 0


def test_point_counts_per_hexagon(c):
    p = pd.DataFrame({"iso3": ["USA"] * 3, "lat": [40.7128, 40.71281, 34.05], "lon": [-74.006, -74.00601, -118.24]})
    c.register("p", p)
    r = c.sql(counts_by_hex("p")).df()
    assert sorted(r["n"]) == [1, 2]
