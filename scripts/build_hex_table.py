"""P0: seven-country data foundation on H3 resolution 8 (ADR-001, gate in ADR-002).

    python scripts/build_hex_table.py

Writes to GEO_DATA_DIR/derived:
  hex_speed_panel.parquet   one row per (country, hexagon, quarter, mobile|fixed)
  hex_latest.parquet        one row per (country, hexagon): population, places, cells, latest mobile/fixed speed
and data/outputs/p0_foundation.json with the gate checks.

Gate (ADR-002, amended by ADR-003): >= 99% of each country's population and speed tests assigned to the grid in
the right country; data contracts pass; snapshot manifest written (data/outputs/manifest.json, SHA-256 per input).
Assignment uses simplified borders (fast); the check recounts against full-detail borders. Country totals
are also compared with the World Bank's 2023 population (a sanity check, not a gate).
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.contracts import check_hex_latest, check_panel_quarters, manifest  # noqa: E402
from src.hexgrid import connect, counts_by_hex, speed_by_hex  # noqa: E402

CFG = yaml.safe_load((ROOT / "configs" / "default_config.yaml").read_text())
DATA = Path(os.environ.get("GEO_DATA_DIR", "~/data/geo")).expanduser()
OUT = DATA / "derived"
CLIP = {"USA": "POLYGON((-125 24,-66 24,-66 50,-125 50,-125 24))", "FRA": "POLYGON((-5.5 41,10 41,10 51.5,-5.5 51.5,-5.5 41))"}


def world_bank_population(iso3: str) -> float | None:
    try:
        d = json.load(urllib.request.urlopen(f"https://api.worldbank.org/v2/country/{iso3}/indicator/SP.POP.TOTL?date=2023&format=json", timeout=30))
        return float(d[1][0]["value"])
    except Exception:
        return None


def main() -> None:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    c = connect()
    iso = list(CFG["countries"])
    ne = DATA / "countries" / "ne_10m_admin_0_countries.geojson"
    c.sql(f"CREATE TABLE full AS SELECT ADM0_A3 AS iso3, geom FROM ST_Read('{ne}') WHERE ADM0_A3 IN ({','.join(repr(i) for i in iso)})")
    for k, w in CLIP.items():
        c.sql(f"UPDATE full SET geom = ST_Intersection(geom, ST_GeomFromText('{w}')) WHERE iso3 = '{k}'")
    c.sql("CREATE TABLE fb AS SELECT *, ST_XMin(geom) x0, ST_XMax(geom) x1, ST_YMin(geom) y0, ST_YMax(geom) y1 FROM full")

    # speed panel: every quarter, mobile and fixed
    c.sql(f"CREATE VIEW tiles AS SELECT * FROM read_parquet('{DATA}/ookla7/*/*.parquet')")
    c.sql(f"COPY ({speed_by_hex(c, 'tiles')}) TO '{OUT}/hex_speed_panel.parquet' (FORMAT parquet)")
    y, q = CFG["experience"]["latest_quarter"]

    # population, places, cells on the same grid
    c.sql(f"CREATE VIEW pop AS SELECT iso3, h3, population FROM '{DATA}/population/kontur_7_20231101.parquet'")
    places = " UNION ALL ".join(f"SELECT '{k}' AS iso3, lat, lon FROM '{DATA}/overture/{k.lower()}_places_2026-09-23.1.parquet'" for k in iso)
    c.sql(f"CREATE VIEW places AS {places}")
    c.sql(f"CREATE VIEW cells AS SELECT iso3, lat, lon, radio FROM '{DATA}/opencellid/cells_7.parquet'")
    c.sql(f"""COPY (
      WITH sp AS (SELECT * FROM '{OUT}/hex_speed_panel.parquet' WHERE year = {y} AND quarter = {q}),
           mob AS (SELECT iso3, h3, down_mbps AS mobile_down_mbps, up_mbps AS mobile_up_mbps, latency_ms AS mobile_latency_ms,
                          tests AS mobile_tests, devices AS mobile_devices FROM sp WHERE type = 'mobile'),
           fix AS (SELECT iso3, h3, down_mbps AS fixed_down_mbps, tests AS fixed_tests FROM sp WHERE type = 'fixed'),
           pl AS ({counts_by_hex('places')}),
           ce AS ({counts_by_hex('cells', extra=", count_if(radio = 'NR') AS cells_nr, count_if(radio = 'LTE') AS cells_lte")})
      SELECT coalesce(pop.iso3, mob.iso3, fix.iso3, pl.iso3, ce.iso3) AS iso3, coalesce(pop.h3, mob.h3, fix.h3, pl.h3, ce.h3) AS h3,
             coalesce(pop.population, 0) AS population, coalesce(pl.n, 0) AS places, coalesce(ce.n, 0) AS cells,
             coalesce(ce.cells_nr, 0) AS cells_nr, coalesce(ce.cells_lte, 0) AS cells_lte,
             mob.* EXCLUDE (iso3, h3), fix.* EXCLUDE (iso3, h3)
      FROM pop FULL JOIN mob USING (iso3, h3) FULL JOIN fix USING (iso3, h3) FULL JOIN pl USING (iso3, h3) FULL JOIN ce USING (iso3, h3)
    ) TO '{OUT}/hex_latest.parquet' (FORMAT parquet)""")

    # gate: recount against full-detail borders
    src = f"{DATA}/ookla7/mobile/{y}q{q}.parquet"
    c.sql(f"CREATE TABLE raw AS SELECT tile_x, tile_y, tests FROM read_parquet('{src}')")
    full_tests = dict(c.sql("""SELECT fb.iso3, sum(tests) FROM raw JOIN fb ON tile_x BETWEEN x0 AND x1 AND tile_y BETWEEN y0 AND y1
                               WHERE ST_Contains(fb.geom, ST_Point(tile_x, tile_y)) GROUP BY 1""").fetchall())
    kept_tests = dict(c.sql(f"SELECT iso3, sum(mobile_tests) FROM '{OUT}/hex_latest.parquet' GROUP BY 1").fetchall())
    pop_kept = dict(c.sql(f"SELECT iso3, sum(population) FROM '{OUT}/hex_latest.parquet' GROUP BY 1").fetchall())
    c.sql(f"CREATE TABLE kp AS SELECT h3, population, ST_Point(h3_cell_to_lng(h3), h3_cell_to_lat(h3)) AS pt FROM '{DATA}/population/kontur_7_20231101.parquet'")
    pop_full = dict(c.sql("""SELECT fb.iso3, sum(population) FROM kp JOIN fb ON ST_X(pt) BETWEEN x0 AND x1 AND ST_Y(pt) BETWEEN y0 AND y1
                             WHERE ST_Contains(fb.geom, pt) GROUP BY 1""").fetchall())
    rows = {}
    for k in iso:
        wb = world_bank_population(k)
        rows[k] = {"population_assigned": round(pop_kept.get(k, 0) / max(pop_full.get(k, 1), 1), 4),
                   "tests_assigned": round((kept_tests.get(k) or 0) / max(full_tests.get(k, 1), 1), 4),
                   "population_kontur": round(pop_kept.get(k, 0)), "population_world_bank_2023": wb,
                   "kontur_vs_world_bank": round(pop_kept.get(k, 0) / wb, 3) if wb else None,
                   "hexagons": c.sql(f"SELECT count(*) FROM '{OUT}/hex_latest.parquet' WHERE iso3 = '{k}'").fetchone()[0]}
    # data contracts (ADR-003, E9)
    hl = c.sql(f"SELECT iso3, h3, population, places, cells, mobile_down_mbps, mobile_tests FROM '{OUT}/hex_latest.parquet'").df()
    E = CFG["experience"]
    panel_q = {tuple(r) for r in c.sql(f"SELECT DISTINCT year, quarter FROM '{OUT}/hex_speed_panel.parquet' WHERE type = 'mobile'").fetchall()}
    broken = check_hex_latest(hl, iso) + check_panel_quarters(panel_q, tuple(E["first_quarter"]), tuple(E["latest_quarter"]))
    del hl

    # snapshot manifest: every input file, with SHA-256 and rows
    inputs = (sorted((DATA / "ookla7").glob("*/*.parquet")) + [DATA / "population" / "kontur_7_20231101.parquet",
              DATA / "opencellid" / "cells_7.parquet", ne] + [DATA / "overture" / f"{k.lower()}_places_2026-09-23.1.parquet" for k in iso])
    nrows = {str(f.relative_to(DATA)): c.sql(f"SELECT count(*) FROM '{f}'").fetchone()[0] for f in inputs if f.suffix == ".parquet"}
    out_dir = ROOT / CFG["paths"]["outputs_dir"]; out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text(json.dumps(manifest(DATA, inputs, nrows), indent=1))

    g = CFG["gates"]
    gate = not broken and all(r["population_assigned"] >= g["p0_min_population_assigned"] and r["tests_assigned"] >= g["p0_min_tests_assigned"] for r in rows.values())
    report = {"quarter": f"{y}Q{q}", "countries": rows, "contracts_broken": broken, "inputs_in_manifest": len(inputs),
              "gate_passed": gate, "seconds": round(time.time() - t0),
              "panel_rows": c.sql(f"SELECT count(*) FROM '{OUT}/hex_speed_panel.parquet'").fetchone()[0]}
    (ROOT / CFG["paths"]["outputs_dir"] / "p0_foundation.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
