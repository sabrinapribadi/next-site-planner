"""Read-only access to the serving store built by scripts/build_serving_store.py (ADR-009)."""

from __future__ import annotations

import json
import math
import os
from functools import cached_property
from pathlib import Path

import duckdb
import h3
import pandas as pd

RES = 8


def _clean(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return v.item() if hasattr(v, "item") else v


class Store:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or os.environ.get("GEO_SERVING_DIR") or Path(os.environ.get("GEO_DATA_DIR", "~/data/geo")) / "serving").expanduser()
        self.con = duckdb.connect()

    @cached_property
    def countries(self) -> dict:
        return json.loads((self.path / "countries.json").read_text())

    @cached_property
    def plans(self) -> pd.DataFrame:
        return pd.read_parquet(self.path / "plans.parquet")

    def hexagon(self, lat: float, lon: float) -> dict | None:
        cell = h3.latlng_to_cell(lat, lon, RES)
        r = self.con.execute(f"SELECT * FROM '{self.path / 'hexes.parquet'}' WHERE h3 = ?", [cell]).fetchdf()
        return None if r.empty else {k: _clean(v) for k, v in r.iloc[0].items()}

    def plan(self, country: str) -> pd.DataFrame:
        return self.plans[self.plans.iso3 == country].sort_values("rank")

    def nominal(self, country: str, rank: int) -> dict | None:
        p = self.plan(country); r = p[p["rank"] == rank]
        return None if r.empty else {k: _clean(v) for k, v in r.iloc[0].items()}

    def nominal_at(self, h3_cell: str) -> dict | None:
        r = self.plans[self.plans.h3 == h3_cell]
        return None if r.empty else {k: _clean(v) for k, v in r.iloc[0].items()}
