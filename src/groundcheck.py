"""Ground and terrain checks for a candidate hexagon (ADR-008 amendment 1, checks B and C).

B. ESA WorldCover 2021 v200 (10 m, CC BY 4.0): land-cover shares inside the hexagon and built-up area (class 50) in m².
   Site point = the built-up pixel nearest the centre of the hexagon's built-up area (on built land by construction).
C. Copernicus DEM GLO-30 (30 m): elevation at the site point and slope from its 3 × 3 neighbourhood (Horn 1981).

Both are cloud-optimised GeoTIFFs on public AWS buckets; only the window around each hexagon is read. A missing tile
(open ocean, checked with a HEAD request) counts as no land; any other read error is raised, never cached as a result.
"""

from __future__ import annotations

import math
import os
import threading
import urllib.error
import urllib.request
from functools import lru_cache

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "5")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")
os.environ.setdefault("VSI_CACHE", "TRUE")
os.environ.setdefault("GDAL_HTTP_TIMEOUT", "60")             # a socket frozen by sleep fails and is retried, never hangs
os.environ.setdefault("GDAL_HTTP_CONNECTTIMEOUT", "20")

import h3  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from rasterio.features import geometry_mask  # noqa: E402
from rasterio.errors import WindowError  # noqa: E402
from rasterio.windows import Window, from_bounds  # noqa: E402

WC = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{t}_Map.tif"
DEM = "https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_{t}_00_DEM/Copernicus_DSM_COG_10_{t}_00_DEM.tif"
CLASSES = {10: "tree", 20: "shrub", 30: "grass", 40: "cropland", 50: "built", 60: "bare", 70: "snow_ice",
           80: "water", 90: "wetland", 95: "mangrove", 100: "moss"}
BUILT_MIN_M2 = 1000.0          # reject below (amendment 1)
STEEP_DEG, HIGH_M = 20.0, 2500.0  # flags (amendment 1)
_local = threading.local()


@lru_cache(maxsize=None)
def tile_exists(url: str) -> bool:
    for k in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60):
                return True
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                return False
        except Exception:
            pass
    raise RuntimeError(f"cannot reach {url}")


def _open(url: str):
    cache = getattr(_local, "ds", None)
    if cache is None:
        cache = _local.ds = {}
    if url not in cache:
        ds = rasterio.open("/vsicurl/" + url)
        if ds.crs is None or ds.transform.is_identity:            # a glitched read: never let it count as "no land"
            ds.close()
            raise RuntimeError(f"no georeferencing from {url}")
        cache[url] = ds
    return cache[url]


def _wc_tiles(w: float, s: float, e: float, n: float) -> list[str]:
    out = []
    for la in range(math.floor(s / 3) * 3, math.floor(n / 3) * 3 + 1, 3):
        for lo in range(math.floor(w / 3) * 3, math.floor(e / 3) * 3 + 1, 3):
            out.append(f"{'N' if la >= 0 else 'S'}{abs(la):02d}{'E' if lo >= 0 else 'W'}{abs(lo):03d}")
    return out


def _dem_tile(lat: float, lng: float) -> str:
    la, lo = math.floor(lat), math.floor(lng)
    return f"{'N' if la >= 0 else 'S'}{abs(la):02d}_00_{'E' if lo >= 0 else 'W'}{abs(lo):03d}"


def clip_window(win: Window, width: int, height: int) -> Window | None:
    """The part of `win` inside a width × height raster, or None when they do not overlap."""
    try:
        return win.intersection(Window(0, 0, width, height))
    except WindowError:
        return None


def land_cover(cell: str) -> dict:
    """Class shares inside the hexagon, built-up m² and the site point."""
    ring = [(lng, lat) for lat, lng in h3.cell_to_boundary(cell)]
    poly = {"type": "Polygon", "coordinates": [ring + [ring[0]]]}
    xs, ys = [p[0] for p in ring], [p[1] for p in ring]
    counts, bx, by = {}, [], []
    for t in _wc_tiles(min(xs), min(ys), max(xs), max(ys)):
        url = WC.format(t=t)
        if not tile_exists(url):
            continue
        ds = _open(url)
        win = clip_window(from_bounds(min(xs), min(ys), max(xs), max(ys), ds.transform).round_offsets().round_lengths(), ds.width, ds.height)
        if win is None:                                        # bounding box only grazes this tile's edge
            continue
        a = ds.read(1, window=win)
        tr = ds.window_transform(win)
        inside = geometry_mask([poly], out_shape=a.shape, transform=tr, invert=True)
        v, n = np.unique(a[inside], return_counts=True)
        for c, k in zip(v.tolist(), n.tolist()):
            counts[c] = counts.get(c, 0) + k
        yy, xx = np.nonzero(inside & (a == 50))
        bx.extend((tr.c + (xx + 0.5) * tr.a).tolist()); by.extend((tr.f + (yy + 0.5) * tr.e).tolist())
    lat0, lng0 = h3.cell_to_latlng(cell)
    px_m2 = (111320 * math.cos(math.radians(lat0)) / 12000) * (110574 / 12000)
    total = sum(v for k, v in counts.items() if k)                 # class 0 = no data
    expected = h3.cell_area(cell, unit="m^2") / px_m2
    if counts and total < 0.97 * expected:                       # short or blank read (no-data pixels): retry, never cache
        raise RuntimeError(f"{cell}: {total} land-cover pixels read, {expected:.0f} expected")
    out = {f"share_{nm}": (counts.get(c, 0) / total if total else 0.0) for c, nm in CLASSES.items()}
    out["built_m2"] = counts.get(50, 0) * px_m2
    out["land_pixels"] = int(total)
    if bx:
        bx, by = np.array(bx), np.array(by); cx, cy = bx.mean(), by.mean()
        j = int(np.argmin(((bx - cx) * math.cos(math.radians(cy))) ** 2 + (by - cy) ** 2))
        out["site_lat"], out["site_lon"] = float(by[j]), float(bx[j])
    else:
        out["site_lat"], out["site_lon"] = lat0, lng0
    return out


def terrain(lat: float, lng: float) -> dict:
    url = DEM.format(t=_dem_tile(lat, lng))
    if not tile_exists(url):
        return {"elevation_m": float("nan"), "slope_deg": float("nan")}
    ds = _open(url)
    r, c = ds.index(lng, lat)
    a = ds.read(1, window=Window(c - 1, r - 1, 3, 3), boundless=True, fill_value=np.nan).astype("float64")
    dx = abs(ds.transform.a) * 111320 * math.cos(math.radians(lat)); dy = abs(ds.transform.e) * 110574
    return {"elevation_m": float(a[1, 1]), "slope_deg": horn_slope(a, dx, dy)}


def horn_slope(a: np.ndarray, dx: float, dy: float) -> float:
    """Slope in degrees at the centre of a 3 × 3 elevation window (Horn 1981); dx, dy = pixel size in metres."""
    (p, q, s), (d, _, f), (g, hh, i) = a
    dzdx = ((s + 2 * f + i) - (p + 2 * d + g)) / (8 * dx)
    dzdy = ((g + 2 * hh + i) - (p + 2 * q + s)) / (8 * dy)
    return float(math.degrees(math.atan(math.hypot(dzdx, dzdy))))


def check(cell: str) -> dict:
    lc = land_cover(cell)
    tr = terrain(lc["site_lat"], lc["site_lon"])
    return {"h3": cell, **lc, **tr, "built_ok": lc["built_m2"] >= BUILT_MIN_M2,
            "steep": bool(tr["slope_deg"] > STEEP_DEG), "high": bool(tr["elevation_m"] > HIGH_M)}
