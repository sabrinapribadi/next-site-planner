"""WorldPop 2020 constrained (100 m) summed into H3 resolution-8 hexagons (ADR-008 amendment 1, check A).

    python scripts/worldpop_hex.py [ISO3 ...]

Each populated pixel is assigned to the hexagon containing its centre. Hexagons outside the project's territory clip
(metropolitan France, the US lower 48; same boxes as acquire_public_data.py) are dropped. Writes derived/hex_worldpop_<ISO3>.parquet
(iso3, h3, wp_population, wp_pixels) per country, so countries can be added as their downloads finish.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import h3
import numpy as np
import pandas as pd
import rasterio
import yaml
from rasterio.windows import Window

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
from acquire_public_data import COUNTRIES  # noqa: E402
from src.hexgrid import RES, connect  # noqa: E402

CFG = yaml.safe_load((ROOT / "configs" / "default_config.yaml").read_text())
DATA = Path(os.environ.get("GEO_DATA_DIR", "~/data/geo")).expanduser()
POP = DATA / "population"
DER = DATA / "derived"
ROWS = 512
log = lambda *a: print(time.strftime("%H:%M:%S"), *a, flush=True)


def aggregate(iso3: str) -> pd.DataFrame:
    c = connect(); parts = []
    with rasterio.open(POP / f"{iso3.lower()}_ppp_2020_UNadj_constrained.tif") as r:
        t = r.transform
        for y0 in range(0, r.height, ROWS):
            a = r.read(1, window=Window(0, y0, r.width, min(ROWS, r.height - y0)))
            yy, xx = np.nonzero(a > 0)
            if not len(yy):
                continue
            px = pd.DataFrame({"lat": t.f + (y0 + yy + 0.5) * t.e, "lng": t.c + (xx + 0.5) * t.a, "v": a[yy, xx].astype("float64")})
            parts.append(c.sql(f"SELECT h3_latlng_to_cell_string(lat, lng, {RES}) AS h3, sum(v) AS wp_population, count(*) AS wp_pixels FROM px GROUP BY 1").df())
    d = pd.concat(parts).groupby("h3", as_index=False).sum()
    clip = COUNTRIES[iso3][3]
    if clip:                                                   # same territory as Kontur and the speed tiles (ADR-001)
        xs = [float(v.split()[0]) for v in clip[clip.index("((") + 2:clip.index("))")].split(",")]
        ys = [float(v.split()[1]) for v in clip[clip.index("((") + 2:clip.index("))")].split(",")]
        ll = np.array([h3.cell_to_latlng(x) for x in d.h3])
        d = d[(ll[:, 1] >= min(xs)) & (ll[:, 1] <= max(xs)) & (ll[:, 0] >= min(ys)) & (ll[:, 0] <= max(ys))]
    d.insert(0, "iso3", iso3)
    return d.reset_index(drop=True)


def main(isos: list[str]) -> None:
    for k in isos:
        t0 = time.time(); d = aggregate(k)
        d.to_parquet(DER / f"hex_worldpop_{k}.parquet", index=False)
        log(k, f"{len(d):,} hexagons, {d.wp_population.sum() / 1e6:,.2f}M people, {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main(sys.argv[1:] or CFG["countries"])
