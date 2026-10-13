"""Data contracts and the snapshot manifest (ADR-003, E9; gate P0 in ADR-002).

Contracts fail loudly: each check returns a list of broken rules, and P0 refuses to pass its gate if any break.
The manifest records what every refresh was built from, so a number on the page can be traced to its inputs.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path

import pandas as pd


def check_hex_latest(df: pd.DataFrame, countries: list[str]) -> list[str]:
    broken = []
    need = {"iso3", "h3", "population", "places", "cells", "mobile_down_mbps", "mobile_tests"}
    if missing := need - set(df.columns):
        return [f"missing columns: {sorted(missing)}"]
    if df.duplicated(["iso3", "h3"]).any():
        broken.append(f"(iso3, h3) not unique: {int(df.duplicated(['iso3', 'h3']).sum())} duplicates")
    if (df["population"] < 0).any():
        broken.append("negative population")
    sp = df["mobile_down_mbps"].dropna()
    if (sp <= 0).any():
        broken.append("non-positive mobile speed")
    if df["h3"].str.len().ne(15).any():
        broken.append("h3 is not a 15-character cell id")
    if extra := set(df["iso3"]) - set(countries):
        broken.append(f"unexpected countries: {sorted(extra)}")
    if absent := set(countries) - set(df["iso3"]):
        broken.append(f"countries without rows: {sorted(absent)}")
    return broken


def check_panel_quarters(quarters: set[tuple[int, int]], first: tuple[int, int], last: tuple[int, int]) -> list[str]:
    want = {(y, q) for y in range(first[0], last[0] + 1) for q in range(1, 5) if first <= (y, q) <= last}
    return [f"missing quarters: {sorted(want - quarters)}"] if want - quarters else []


def sha256(path: Path, chunk: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def manifest(root: Path, files: list[Path], rows: dict[str, int] | None = None) -> dict:
    rows = rows or {}
    return {"built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "inputs": [{"path": str(p.relative_to(root)), "bytes": p.stat().st_size, "sha256": sha256(p),
                        "rows": rows.get(str(p.relative_to(root))),
                        "modified": dt.datetime.fromtimestamp(p.stat().st_mtime, dt.timezone.utc).date().isoformat()}
                       for p in sorted(files)]}
