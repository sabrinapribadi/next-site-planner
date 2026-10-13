"""H3 resolution-8 grid: speed tiles, population, places and cells on one hexagon per row (ADR-001).

A hexagon's download speed is the test-weighted mean of log speed over the Ookla tiles whose centre
falls in it (speeds are right-skewed, so log); reported back in Mbps as exp(mean log). Population is
Kontur's (already H3 r8). Places and cells are counts per hexagon.
"""

from __future__ import annotations

import duckdb

RES = 8


def connect() -> duckdb.DuckDBPyConnection:
    c = duckdb.connect()
    c.sql("INSTALL h3 FROM community; LOAD h3; INSTALL spatial; LOAD spatial;")
    return c


def speed_by_hex(c: duckdb.DuckDBPyConnection, tiles: str, res: int = RES) -> str:
    """SQL for one row per (iso3, h3, year, quarter, type): tests, devices, tiles and test-weighted log speeds."""
    return f"""
    SELECT iso3, h3_latlng_to_cell_string(tile_y, tile_x, {res}) AS h3, year, quarter, type,
           sum(tests) AS tests, sum(devices) AS devices, count(*) AS tiles,
           exp(sum(tests * ln(greatest(avg_d_kbps, 1))) / sum(tests)) / 1000.0 AS down_mbps,
           exp(sum(tests * ln(greatest(avg_u_kbps, 1))) / sum(tests)) / 1000.0 AS up_mbps,
           sum(tests * avg_lat_ms) / sum(tests) AS latency_ms
    FROM {tiles} WHERE tests > 0
    GROUP BY ALL"""


def counts_by_hex(table: str, lat: str = "lat", lon: str = "lon", res: int = RES, extra: str = "") -> str:
    """SQL for counts of points (places, cells) per hexagon, with optional extra aggregates."""
    return f"""SELECT iso3, h3_latlng_to_cell_string({lat}, {lon}, {res}) AS h3, count(*) AS n{extra}
               FROM {table} GROUP BY ALL"""
