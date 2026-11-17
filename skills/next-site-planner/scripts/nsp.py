#!/usr/bin/env python3
"""Client for the public next-site-planner API (standard library only; `h3` optional for exact hexagon outlines).

    python nsp.py about                                  # data sources, periods and the time of this check (start every answer here)
    python nsp.py countries [--bar 25]
    python nsp.py gap LAT LON
    python nsp.py sites COUNTRY [--k 10]
    python nsp.py note COUNTRY RANK
    python nsp.py map gap LAT LON [--out map.html]       # map of the hexagon at a point
    python nsp.py map sites COUNTRY [--k 10] [--out ...] # map of the plan's first k sites
    python nsp.py ... --base https://next-site-planner.vercel.app   # another deployment

Prints the API's JSON (the map commands print the file written). The host scales to zero, so the first call can take a few
seconds; the client retries once. Exit code 0 on success (an out-of-scope answer is a valid result), 1 on a network or HTTP error.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_BASE = "https://next-site-planner.vercel.app"
COUNTRIES = ("IDN", "MYS", "PHL", "DEU", "FRA", "USA", "ARE")
HEX_AREA_KM2 = 0.737                     # H3 resolution 8 average cell area


def get(base: str, path: str, params: dict | None = None, timeout: float = 60) -> dict:
    url = base.rstrip("/") + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"User-Agent": "next-site-planner-skill/1.1", "Accept": "application/json"})
    last = None
    for attempt in range(2):                      # one retry covers a cold start or a transient error
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code < 500:
                raise SystemExit(f"HTTP {e.code} for {url}: {e.read().decode(errors='replace')[:300]}")
            last = e
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
        time.sleep(3 * (attempt + 1))
    print(f"error: could not reach {url}: {last}", file=sys.stderr)
    sys.exit(1)


def quarter_dates(q: str) -> tuple[str, str]:
    """'2026Q3' -> ('2026-07-01', '2026-09-30')."""
    y, n = int(q[:4]), int(q[-1])
    start = dt.date(y, 3 * n - 2, 1)
    end = (dt.date(y + (n == 4), (3 * n) % 12 + 1, 1) - dt.timedelta(days=1))
    return start.isoformat(), end.isoformat()


def about(base: str) -> dict:
    root, cs = get(base, "/"), get(base, "/countries")
    q = cs["quarter"]
    s, e = quarter_dates(q)
    weeks = round(((dt.date.fromisoformat(e) - dt.date.fromisoformat(s)).days + 1) / 7)
    return {"checked_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "speed_tests": {"source": "Speedtest by Ookla open data (mobile), crowdsourced", "quarter": q,
                            "period": f"{s} to {e}", "weeks": weeks},
            "population": ["Kontur 2023 (H3 resolution 8)", "WorldPop 2020 constrained 100 m"],
            "ground_check": ["ESA WorldCover 2021 v200 (built-up land, 10 m)", "Copernicus DEM GLO-30 (elevation, slope)"],
            "places": "Overture Maps places (used only by the KPI baseline)",
            "countries": root.get("countries"), "attribution": root.get("attribution"), "results_page": root.get("results_page")}


def hex_ring(lat: float, lon: float, h3_id: str | None) -> list[list[float]]:
    """Exact hexagon outline with the optional `h3` package; otherwise an equal-area circle (marked approximate)."""
    try:
        import h3  # type: ignore
        return [[a, b] for a, b in h3.cell_to_boundary(h3_id)] if h3_id else []
    except Exception:  # noqa: BLE001 - h3 missing or an old API: fall back to a circle
        r_km = math.sqrt(HEX_AREA_KM2 / math.pi)
        return [[lat + r_km / 111.32 * math.sin(t), lon + r_km / (111.32 * math.cos(math.radians(lat))) * math.cos(t)]
                for t in [2 * math.pi * k / 36 for k in range(36)]]


def map_html(features: list[dict], title: str) -> str:
    """A self-contained Leaflet page: street map and satellite imagery (buildings visible when zoomed in)."""
    data = json.dumps(features)
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>html,body,#m{{height:100%;margin:0}} .note{{position:absolute;z-index:999;bottom:8px;left:8px;background:#fff;padding:6px 8px;
font:12px system-ui;border-radius:6px;max-width:420px}}</style></head><body><div id="m"></div>
<div class="note">{html.escape(title)}. Outline = the 0.74 km² analysis hexagon (dashed = approximate). Satellite view by default: zoom in to see the buildings; switch to Street for names.
Speed: Ookla open data (CC BY-NC-SA 4.0). Imagery: Esri. Map: © OpenStreetMap contributors.</div>
<script>
const F = {data};
const street = L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{maxZoom: 19, attribution: '© OpenStreetMap contributors'}});
const sat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{maxZoom: 19, attribution: 'Imagery © Esri'}});
const m = L.map('m', {{layers: [sat]}}); L.control.layers({{'Satellite': sat, 'Street': street}}).addTo(m);
const g = L.featureGroup().addTo(m);
for (const f of F) {{
  if (f.ring.length) L.polygon(f.ring, {{color: f.color, weight: 2, fillOpacity: 0.15, dashArray: f.approx ? '6 4' : null}}).bindPopup(f.popup).addTo(g);
  L.circleMarker([f.lat, f.lon], {{radius: 6, color: f.color, fillOpacity: 0.9}}).bindPopup(f.popup).addTo(g);
}}
m.fitBounds(g.getBounds().pad(0.4));
</script></body></html>"""


def make_map(base: str, a: argparse.Namespace) -> Path:
    feats = []
    have_h3 = True
    try:
        import h3  # type: ignore  # noqa: F401
    except Exception:  # noqa: BLE001
        have_h3 = False
    if a.what == "gap":
        g = get(base, "/gap", {"lat": a.lat, "lon": a.lon})
        if g.get("out_of_scope"):
            raise SystemExit(g["message"])
        popup = (f"<b>{html.escape(g['district'])}</b><br>typical {g['typical_mbps']} Mbps · {g['gap_type_25_mbps']}<br>"
                 f"chance below 25 Mbps {g['chance_below_25_mbps']:.0%}<br>people {g['people_kontur']:,} (Kontur)")
        feats.append({"lat": a.lat, "lon": a.lon, "ring": hex_ring(a.lat, a.lon, g["h3"]), "approx": not have_h3,
                      "color": "#c0392b" if g["chance_below_25_mbps"] >= 0.5 else "#1e7d4f", "popup": popup})
        title = f"Hexagon {g['h3']} at {a.lat}, {a.lon}"
    else:
        d = get(base, f"/sites/{a.country.upper()}", {"k": max(1, min(100, a.k))})
        if d.get("out_of_scope"):
            raise SystemExit(d["message"])
        for s in d["sites"]:
            popup = (f"<b>#{s['rank']} {html.escape(s['district'])}</b><br>{s['intervention']} · cost {s['cost_new_tower_equivalents']}<br>"
                     f"about {round(s['expected_people_lifted']):,} people lifted<br>built-up {s.get('built_up_m2') or 0:,} m²")
            feats.append({"lat": s["site_lat"], "lon": s["site_lon"], "ring": hex_ring(s["site_lat"], s["site_lon"], s["h3"]),
                          "approx": not have_h3, "color": "#2c5fa8", "popup": popup})
        title = f"{d['country']} plan: first {len(d['sites'])} sites"
    out = Path(a.out).resolve()
    out.write_text(map_html(feats, title), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default=DEFAULT_BASE)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("about")
    c = sub.add_parser("countries"); c.add_argument("--bar", type=int, default=25, help="speed bar in Mbps (default 25)")
    g = sub.add_parser("gap"); g.add_argument("lat", type=float); g.add_argument("lon", type=float)
    s = sub.add_parser("sites"); s.add_argument("country"); s.add_argument("--k", type=int, default=10, help="1-100 sites")
    n = sub.add_parser("note"); n.add_argument("country"); n.add_argument("rank", type=int)
    m = sub.add_parser("map"); msub = m.add_subparsers(dest="what", required=True)
    mg = msub.add_parser("gap"); mg.add_argument("lat", type=float); mg.add_argument("lon", type=float); mg.add_argument("--out", default="site_map.html")
    ms = msub.add_parser("sites"); ms.add_argument("country"); ms.add_argument("--k", type=int, default=10); ms.add_argument("--out", default="site_map.html")
    a = ap.parse_args(argv)

    if a.cmd in ("gap",) or (a.cmd == "map" and a.what == "gap"):
        if not (-90 <= a.lat <= 90 and -180 <= a.lon <= 180):
            raise SystemExit("latitude must be -90..90 and longitude -180..180")
    if a.cmd == "map":
        print(f"map written: {make_map(a.base, a)}")
        return
    if a.cmd == "about":
        out = about(a.base)
    elif a.cmd == "countries":
        out = get(a.base, "/countries", {"bar_mbps": a.bar})
    elif a.cmd == "gap":
        out = get(a.base, "/gap", {"lat": a.lat, "lon": a.lon})
    elif a.cmd == "sites":
        out = get(a.base, f"/sites/{a.country.upper()}", {"k": max(1, min(100, a.k))})
    else:
        out = get(a.base, f"/sites/{a.country.upper()}/{a.rank}/note")
    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)
    print()


if __name__ == "__main__":
    main()
