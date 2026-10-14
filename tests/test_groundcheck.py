"""ADR-008 amendment 1: tile naming for WorldCover / Copernicus DEM and the Horn slope (offline)."""

import math

import numpy as np

from src.groundcheck import _dem_tile, _wc_tiles, horn_slope


def test_worldcover_tiles_are_3_degree_lower_left_corners():
    assert _wc_tiles(138.5, -4.2, 138.9, -4.0) == ["S06E138"]          # Papua: -4.2 falls in the -6..-3 tile
    assert _wc_tiles(2.9, 48.0, 3.1, 48.1) == ["N48E000", "N48E003"]   # straddles a tile edge: both tiles
    assert _wc_tiles(-100.5, 35.2, -100.4, 35.3) == ["N33W102"]


def test_dem_tiles_are_1_degree_lower_left_corners():
    assert _dem_tile(-3.5, 138.7) == "S04_00_E138"
    assert _dem_tile(50.2, 7.9) == "N50_00_E007"
    assert _dem_tile(35.3, -100.4) == "N35_00_W101"


def test_horn_slope_on_known_planes():
    flat = np.full((3, 3), 120.0)
    assert horn_slope(flat, 30, 30) == 0.0
    ramp = np.array([[0, 30, 60]] * 3, dtype=float)                   # rises 30 m per 30 m pixel eastwards: 45°
    assert math.isclose(horn_slope(ramp, 30, 30), 45.0, abs_tol=1e-9)



def test_window_that_only_grazes_a_tile_is_skipped():
    """Regression: hexagon 88952e82d5fffff's box lies just above a neighbouring tile (row_off -116, height 116)."""
    from rasterio.windows import Window

    from src.groundcheck import clip_window
    assert clip_window(Window(2196, -116, 106, 116), 36000, 36000) is None
    assert clip_window(Window(2196, -50, 106, 116), 36000, 36000) == Window(2196, 0, 106, 66)
