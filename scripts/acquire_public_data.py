"""Acquire the public data for seven countries (portfolio plan §9, GEO-1).

    python scripts/acquire_public_data.py ookla opencellid population overture boundaries

Every step is resumable: existing outputs are skipped. Raw data lives in GEO_DATA_DIR
(default ~/data/geo), outside the repository and outside cloud sync.

Sources and licences
- Ookla open performance tiles (CC BY-NC-SA 4.0), s3://ookla-open-data, quarterly
- OpenCelliD full database (CC BY-SA 4.0), token in .env as OPENCELLID_TOKEN
- Kontur population 2023-11-01 on H3 resolution 8 (CC BY 4.0); WorldPop 2020 Indonesia as a cross-check
- Overture Maps places (CDLA-Permissive 2.0)
- geoBoundaries gbOpen (CC BY 4.0 / ODbL by country); Indonesia kecamatan from OCHA COD-AB (CC BY-IGO)
- Natural Earth admin-0 countries (public domain), used to assign Ookla tiles to countries
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

DATA = Path(os.environ.get("GEO_DATA_DIR", "~/data/geo")).expanduser()

COUNTRIES = {  # iso3: name, iso2, mobile country codes, optional clip to the main territory
    "IDN": ("Indonesia", "ID", [510], None),
    "MYS": ("Malaysia", "MY", [502], None),
    "PHL": ("Philippines", "PH", [515], None),
    "DEU": ("Germany", "DE", [262], None),
    "FRA": ("France", "FR", [208], "POLYGON((-5.5 41,10 41,10 51.5,-5.5 51.5,-5.5 41))"),          # metropolitan France
    "USA": ("United States", "US", [310, 311, 312, 313, 314, 315, 316], "POLYGON((-125 24,-66 24,-66 50,-125 50,-125 24))"),  # lower 48
    "ARE": ("United Arab Emirates", "AE", [424, 430, 431], None),
}
QUARTERS = [(y, q) for y in range(2023, 2027) for q in range(1, 5) if (y, q) <= (2026, 3)]


def _duck():
    import duckdb
    c = duckdb.connect()
    c.sql("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; SET s3_region='us-west-2';")
    # 8 GB machine: cap memory and spill to disk, or macOS kills the process without an error (seen 2026-10-13)
    tmp = DATA / "tmp_duckdb"; tmp.mkdir(parents=True, exist_ok=True)
    c.sql(f"SET threads=3; SET memory_limit='2.5GB'; SET preserve_insertion_order=false; SET temp_directory='{tmp}';")
    return c


def _countries(c) -> None:
    ne = DATA / "countries" / "ne_10m_admin_0_countries.geojson"
    if not ne.exists():
        ne.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_0_countries.geojson", ne)
    iso = ",".join(repr(k) for k in COUNTRIES)
    c.sql(f"CREATE OR REPLACE TABLE ctry AS SELECT ADM0_A3 AS iso3, ST_SimplifyPreserveTopology(geom, 0.01) AS geom FROM ST_Read('{ne}') WHERE ADM0_A3 IN ({iso})")
    for k, (_, _, _, clip) in COUNTRIES.items():
        if clip:
            c.sql(f"UPDATE ctry SET geom = ST_Intersection(geom, ST_GeomFromText('{clip}')) WHERE iso3 = '{k}'")
    c.sql("CREATE OR REPLACE TABLE cb AS SELECT *, ST_XMin(geom) x0, ST_XMax(geom) x1, ST_YMin(geom) y0, ST_YMax(geom) y1 FROM ctry")


def ookla() -> None:
    """One read per global quarter file; tiles assigned to a country by point-in-polygon on the tile centre."""
    c = _duck(); _countries(c)
    for typ in ("mobile", "fixed"):
        out_dir = DATA / "ookla7" / typ; out_dir.mkdir(parents=True, exist_ok=True)
        for y, q in QUARTERS:
            out = out_dir / f"{y}q{q}.parquet"
            if out.exists():
                continue
            t0 = time.time(); m = (q - 1) * 3 + 1
            tmp = out.with_suffix(f".tmp{os.getpid()}.parquet")
            src = f"s3://ookla-open-data/parquet/performance/type={typ}/year={y}/quarter={q}/{y}-{m:02d}-01_performance_{typ}_tiles.parquet"
            c.sql(f"""COPY (SELECT cb.iso3, t.quadkey, t.tile_x, t.tile_y, t.avg_d_kbps, t.avg_u_kbps, t.avg_lat_ms, t.tests, t.devices,
                               {y} AS year, {q} AS quarter, '{typ}' AS type
                        FROM read_parquet('{src}') t JOIN cb ON t.tile_x BETWEEN cb.x0 AND cb.x1 AND t.tile_y BETWEEN cb.y0 AND cb.y1
                        WHERE ST_Contains(cb.geom, ST_Point(t.tile_x, t.tile_y))) TO '{tmp}' (FORMAT parquet)""")
            os.replace(tmp, out)  # atomic: a parallel run never sees a half-written file
            n = c.sql(f"SELECT count(*) FROM '{out}'").fetchone()[0]
            print(f"ookla {typ} {y}Q{q}: {n:,} tiles in {time.time() - t0:.0f}s", flush=True)


def opencellid() -> None:
    src = DATA / "opencellid" / "cell_towers.csv.gz"
    if not src.exists():
        token = os.environ.get("OPENCELLID_TOKEN")
        if not token:
            raise SystemExit("OPENCELLID_TOKEN missing: put it in .env")
        src.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(f"https://opencellid.org/ocid/downloads?token={token}&type=full&file=cell_towers.csv.gz", src)
    out = DATA / "opencellid" / "cells_7.parquet"
    c = _duck()
    rows = ",".join(f"('{k}', {m})" for k, v in COUNTRIES.items() for m in v[2])
    c.sql(f"CREATE TABLE cmap AS SELECT * FROM (VALUES {rows}) t(iso3, mcc)")
    c.sql(f"""COPY (SELECT cmap.iso3, cells.*, to_timestamp(created) AS created_ts, to_timestamp(updated) AS updated_ts
                FROM read_csv('{src}', header=true) cells JOIN cmap USING (mcc)) TO '{out}' (FORMAT parquet)""")
    print("opencellid:", c.sql(f"SELECT iso3, count(*) FROM '{out}' GROUP BY 1 ORDER BY 2 DESC").fetchall())


def population(release: str = "20231101") -> None:
    """Kontur population on H3 resolution 8 (~400 m hexagons), one global file; seven countries extracted.
    WorldPop's per-country server was too slow for the US (494 MB); WorldPop Indonesia is kept as a cross-check."""
    d = DATA / "population"; d.mkdir(parents=True, exist_ok=True)
    gz, gpkg, out = d / f"kontur_population_{release}.gpkg.gz", d / f"kontur_population_{release}.gpkg", d / f"kontur_7_{release}.parquet"
    if out.exists():
        return
    if not gpkg.exists():
        url = f"https://geodata-eu-central-1-kontur-public.s3.eu-central-1.amazonaws.com/kontur_datasets/kontur_population_{release}.gpkg.gz"
        t0 = time.time()
        subprocess.run(["curl", "-sL", "-C", "-", "--retry", "5", "-o", str(gz), url], check=True)
        subprocess.run(["gunzip", "-f", str(gz)], check=True)
        print(f"kontur downloaded and unpacked in {time.time() - t0:.0f}s", flush=True)
    c = _duck(); _countries(c)
    c.sql("INSTALL h3 FROM community; LOAD h3;")  # hexagon centres from the H3 id itself: no projection to get wrong
    c.sql(f"CREATE TABLE k AS SELECT h3, population, ST_Point(h3_cell_to_lng(h3), h3_cell_to_lat(h3)) AS pt FROM (SELECT h3, population FROM ST_Read('{gpkg}'))")
    c.sql(f"""COPY (SELECT cb.iso3, k.h3, k.population, ST_X(k.pt) AS lon, ST_Y(k.pt) AS lat FROM k JOIN cb
                ON ST_X(k.pt) BETWEEN cb.x0 AND cb.x1 AND ST_Y(k.pt) BETWEEN cb.y0 AND cb.y1
                WHERE ST_Contains(cb.geom, k.pt)) TO '{out}.tmp' (FORMAT parquet)""")
    os.replace(f"{out}.tmp", out)
    print("population:", c.sql(f"SELECT iso3, count(*) hexes, round(sum(population)/1e6, 1) AS million FROM '{out}' GROUP BY 1 ORDER BY 3 DESC").fetchall())


PLACE_COLS = """id, names."primary" AS name, basic_category, taxonomy."primary" AS category, confidence, operating_status,
               addresses[1].region AS region, addresses[1].locality AS locality, ST_X(geometry) AS lon, ST_Y(geometry) AS lat"""


def overture(release: str = "2026-09-23.1", only: list[str] | None = None) -> None:
    """Places per country, one country per pass with a single bounding box (lets DuckDB skip row groups).
    The US is fetched with Overture's own CLI instead (step `overture_us`): one box, catalog-filtered files."""
    d = DATA / "overture"; d.mkdir(parents=True, exist_ok=True)
    c = _duck(); _countries(c)
    for k, (_, iso2, _, _) in COUNTRIES.items():
        out = d / f"{k.lower()}_places_{release}.parquet"
        if out.exists() or k == "USA" or (only and k not in only):
            continue
        x0, x1, y0, y1 = c.sql(f"SELECT x0, x1, y0, y1 FROM cb WHERE iso3 = '{k}'").fetchone()
        tmp = out.with_suffix(f".tmp{os.getpid()}.parquet"); t0 = time.time()
        c.sql(f"""COPY (SELECT {PLACE_COLS}
                  FROM read_parquet('s3://overturemaps-us-west-2/release/{release}/theme=places/type=place/*.parquet', hive_partitioning=1)
                  WHERE bbox.xmin >= {x0} AND bbox.xmax <= {x1} AND bbox.ymin >= {y0} AND bbox.ymax <= {y1}
                    AND addresses[1].country = '{iso2}') TO '{tmp}' (FORMAT parquet)""")
        os.replace(tmp, out)
        print(f"overture {k}: {c.sql(f'SELECT count(*) FROM {chr(39)}{out}{chr(39)}').fetchone()[0]:,} places in {time.time() - t0:.0f}s", flush=True)


def overture_cli(only: list[str] | None = None, release: str = "2026-09-23.1") -> None:
    """Places with Overture's official CLI (overturemaps download): one bounding box per country, catalog-filtered
    files, then the same columns as `overture`. Much faster than scanning the release (US: 17.8M places in ~10 min)."""
    d = DATA / "overture"; d.mkdir(parents=True, exist_ok=True)
    c = _duck(); _countries(c)
    for k in only or ["USA"]:
        iso2 = COUNTRIES[k][1]
        out = d / f"{k.lower()}_places_{release}.parquet"
        if out.exists():
            continue
        x0, x1, y0, y1 = c.sql(f"SELECT x0, x1, y0, y1 FROM cb WHERE iso3 = '{k}'").fetchone()
        raw = d / f"_{k.lower()}_raw_{release}.parquet"; t0 = time.time()
        for attempt in range(1, 4):  # the CLI's default connect timeout is 3 s; long downloads hit it
            r = subprocess.run(["overturemaps", "download", f"--bbox={x0},{y0},{x1},{y1}", "-f", "geoparquet", "--type=place",
                                f"--release={release}", "--connect_timeout=30", "--request_timeout=120", "-o", str(raw.with_suffix(".part"))])
            if r.returncode == 0:
                break
            print(f"overture {k} (CLI): attempt {attempt} failed, retrying", flush=True)
        else:
            raise SystemExit(f"overture {k} download failed 3 times")
        os.replace(raw.with_suffix(".part"), raw)
        for f in d.glob(f"_{k.lower()}_raw_*.state"):
            f.unlink()
        tmp = out.with_suffix(".tmp.parquet")
        c.sql(f"COPY (SELECT {PLACE_COLS} FROM read_parquet('{raw}') WHERE addresses[1].country = '{iso2}') TO '{tmp}' (FORMAT parquet)")
        os.replace(tmp, out); raw.unlink()
        print(f"overture {k} (CLI): {c.sql(f'SELECT count(*) FROM {chr(39)}{out}{chr(39)}').fetchone()[0]:,} places in {time.time() - t0:.0f}s", flush=True)


def overture_us() -> None:
    overture_cli(["USA"])


def overture_are() -> None:
    overture_cli(["ARE"])


def boundaries() -> None:
    d = DATA / "boundaries" / "gb"; d.mkdir(parents=True, exist_ok=True)
    for k in COUNTRIES:
        meta = json.load(urllib.request.urlopen(f"https://www.geoboundaries.org/api/current/gbOpen/{k}/ALL/"))
        for m in meta:
            f = d / f"{k}_{m['boundaryType']}.geojson"
            if m["boundaryType"] in ("ADM0", "ADM1", "ADM2", "ADM3") and not f.exists():
                urllib.request.urlretrieve(m["gjDownloadURL"], f)
                print(f"boundaries {k} {m['boundaryType']}: {m['admUnitCount']} units, licence {m['boundaryLicense']}", flush=True)


STEPS = {"ookla": ookla, "opencellid": opencellid, "population": population, "overture": overture, "overture_us": overture_us, "overture_are": overture_are, "boundaries": boundaries}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("steps", nargs="+", choices=list(STEPS)); a = ap.parse_args()
    for s in a.steps:
        STEPS[s]()
