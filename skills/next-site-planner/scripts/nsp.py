#!/usr/bin/env python3
"""Client for the public next-site-planner API (standard library only; `h3` optional for exact hexagon outlines).

    python nsp.py about                                  # data sources, periods and the time of this check (start every answer here)
    python nsp.py countries [--bar 25]
    python nsp.py gap LAT LON
    python nsp.py sites COUNTRY [--k 10]
    python nsp.py note COUNTRY RANK
    python nsp.py map gap LAT LON [--ring 1] [--out map.html]  # the hexagon and its neighbours, with OSM buildings, places, masts
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
    # timezone.utc, not datetime.UTC: the skill must run on Python 3.8+, and datetime.UTC is 3.11+
    return {"checked_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M"),  # noqa: UP017
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


def make_map(base: str, a: argparse.Namespace) -> Path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import maps  # sibling module, imported only when a map is asked for
    try:
        import h3  # type: ignore
    except Exception:  # noqa: BLE001 - optional: without it only the queried hexagon is drawn, as an approximate circle
        h3 = None
    ab = about(base)
    foot = (f"Data: Ookla speed tests {ab['speed_tests']['quarter']} ({ab['speed_tests']['period']}, {ab['speed_tests']['weeks']} weeks); "
            f"population Kontur 2023 / WorldPop 2020; checked {ab['checked_at_utc']} UTC. Ookla data CC BY-NC-SA 4.0 (non-commercial). "
            "Buildings, places and masts: OpenStreetMap (ODbL), volunteered and possibly incomplete. Imagery: Esri.")
    if a.what == "gap":
        g = get(base, "/gap", {"lat": a.lat, "lon": a.lon})
        if g.get("out_of_scope"):
            raise SystemExit(g["message"])
        cells = [(g, True)]
        if h3 is not None and a.ring > 0:
            for cell in h3.grid_disk(g["h3"], a.ring):
                if cell == g["h3"]:
                    continue
                la, lo = h3.cell_to_latlng(cell)
                n = get(base, "/gap", {"lat": round(la, 6), "lon": round(lo, 6)})
                if not n.get("out_of_scope"):
                    cells.append((n, False))
        hexes = [{"ring": hex_ring(a.lat, a.lon, c["h3"]) if h3 is not None else hex_ring(a.lat, a.lon, None), "approx": h3 is None,
                  "fill": maps.ramp(c["chance_below_25_mbps"]), "center": center, "popup": maps.hex_popup(c)} for c, center in cells]
        slow = [c for c, _ in cells if c["chance_below_25_mbps"] >= 0.5]
        ppl = sum(c["people_kontur"] for c, _ in cells)
        wp = f"{g['people_worldpop']:,}" if g.get("people_worldpop") is not None else "n/a"
        panel = (f"<h1>{html.escape(g['district'])}</h1><table>"
                 f"<tr><td class=k>Typical speed</td><td><b>{g['typical_mbps']} Mbps</b></td></tr>"
                 f"<tr><td class=k>Chance below 25 Mbps</td><td><b>{g['chance_below_25_mbps']:.0%}</b></td></tr>"
                 f"<tr><td class=k>Gap type</td><td>{html.escape(g['gap_type_25_mbps'])}</td></tr>"
                 f"<tr><td class=k>Speed tests</td><td>{format(g['tests'], ',') if g['tested'] else 'none (estimated)'}</td></tr>"
                 f"<tr><td class=k>People (Kontur / WorldPop)</td><td>{g['people_kontur']:,} / {wp}</td></tr>"
                 f"<tr><td class=k>Area type</td><td>{html.escape(g['area_type'].replace('_', ' '))}</td></tr>"
                 f"<tr><td class=k>In the site plan</td><td>{'#' + str(g['in_plan']['rank']) if g.get('in_plan') else 'no'}</td></tr>"
                 f"<tr><td class=k>Neighbourhood ({len(cells)} hexagons)</td><td>{len(slow)} likely slow · {ppl:,} people</td></tr></table>")
        points = [{"lat": a.lat, "lon": a.lon, "popup": f"<b>Point asked about</b><br>{a.lat}, {a.lon}<br>hexagon {g['h3']}"}]
        osm = None if a.no_osm else maps.fetch_osm(maps.bbox(hexes))
        if osm is not None:
            near = min((maps.metres((a.lat, a.lon), (t["lat"], t["lon"])) for t in osm["masts"]), default=None)
            panel += ("<table style='margin-top:6px'><tr><td class=k>OpenStreetMap in this area</td><td>"
                      f"{len(osm['buildings']):,} buildings · {len(osm['places']):,} places</td></tr>"
                      f"<tr><td class=k>Masts or towers mapped</td><td>{len(osm['masts'])}</td></tr>"
                      f"<tr><td class=k>Nearest mapped mast</td><td>{f'{round(near, -1):,.0f} m' if near is not None else 'none mapped'}</td></tr></table>")
        else:
            print("note: OpenStreetMap features unavailable (public servers busy); map has speeds only", file=sys.stderr)
        page = maps.page(f"Mobile speed around {a.lat}, {a.lon}", panel, hexes, points, "Point asked about", foot, osm=osm)
    else:
        d = get(base, f"/sites/{a.country.upper()}", {"k": max(1, min(100, a.k))})
        if d.get("out_of_scope"):
            raise SystemExit(d["message"])
        hexes, points = [], []
        for s in d["sites"]:
            popup = (f"<b>#{s['rank']} {html.escape(s['district'])}</b><br>{BUILD.get(s['intervention'], s['intervention'])} · cost {s['cost_new_tower_equivalents']}<br>"
                     f"{s['people']:,} people · {s['chance_below_25_mbps']:.0%} chance below 25 Mbps<br>about {round(s['expected_people_lifted']):,} lifted"
                     f"<br>built-up {s.get('built_up_m2') or 0:,} m² · slope {s.get('slope_deg')}°<br><i>Click to zoom in and load buildings and masts</i>")
            hexes.append({"ring": hex_ring(s["site_lat"], s["site_lon"], s["h3"] if h3 is not None else None), "approx": h3 is None,
                          "fill": maps.ramp(s["chance_below_25_mbps"]), "center": True, "popup": popup})
            points.append({"lat": s["site_lat"], "lon": s["site_lon"], "popup": popup})
        names = {c["country"]: c["name"] for c in get(base, "/countries")["countries"]}
        name = names.get(d["country"], d["country"])
        panel = (f"<h1>{html.escape(name)} plan: first {len(d['sites'])} sites</h1><table>"
                 f"<tr><td class=k>Budget</td><td>{d['budget_new_tower_equivalents']:,.1f} tower-eq.</td></tr>"
                 f"<tr><td class=k>Expected people lifted</td><td><b>about {round(sum(s['expected_people_lifted'] for s in d['sites']), -1):,.0f}</b></td></tr>"
                 f"<tr><td class=k>Cost of these sites</td><td>{sum(s['cost_new_tower_equivalents'] for s in d['sites']):.1f} tower-eq.</td></tr>"
                 f"<tr><td class=k>Ground-checked</td><td>{'yes' if d.get('checked_on_ground') else 'no'}</td></tr></table>")
        page = maps.page(f"{name} site plan", panel, hexes, points, "Planned site (click to zoom in)", foot)
    out = Path(a.out).resolve()
    out.write_text(page, encoding="utf-8")
    return out


BUILD = {"macro": "New macro tower", "small_cell": "Small cell", "capacity": "Co-location (capacity)"}


def make_chart(base: str, a: argparse.Namespace) -> Path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import charts  # sibling module, imported only when a chart is asked for
    ab = about(base)
    data_line = (f"Data: Ookla speed tests {ab['speed_tests']['quarter']} ({ab['speed_tests']['period']}); population Kontur 2023 and "
                 f"WorldPop 2020; checked {ab['checked_at_utc']} UTC. Ookla data CC BY-NC-SA 4.0 (non-commercial).")
    if a.what == "countries":
        cs = get(base, "/countries")["countries"]
        rows = [{"label": c["name"], "a": c["plan_people_lifted"] / (1 + c["plan_gain_vs_kpi"]), "b": c["plan_people_lifted"],
                 "note": f"{1 + c['plan_gain_vs_kpi']:.1f}×"} for c in cs if c.get("plan_gain_vs_kpi") is not None]
        top = max(rows, key=lambda r: r["b"] - r["a"])
        page = charts.paired_bars(rows, "Optimised plan vs KPI ranking: people lifted above 25 Mbps",
                                  f"Same budget per country. Biggest absolute win: {top['label']} (about {round(top['b'] - top['a'], -2):,.0f} more people).",
                                  data_line + " UAE budget 29.3 tower-equivalents; others 1,000. Central estimates; ranges are wide.",
                                  "KPI ranking (baseline)", "Optimised plan")
    else:
        d = get(base, f"/sites/{a.country.upper()}", {"k": max(1, min(100, a.k))})
        if d.get("out_of_scope"):
            raise SystemExit(d["message"])
        rows = [{"label": f"#{s['rank']} {s['district']}", "v": s["expected_people_lifted"], "cat": BUILD.get(s["intervention"], s["intervention"]),
                 "note": f"cost {s['cost_new_tower_equivalents']}",
                 "tip": (f"{BUILD.get(s['intervention'], s['intervention'])}, cost {s['cost_new_tower_equivalents']} tower-eq.<br>"
                         f"{s['people']:,} people, {s['chance_below_25_mbps']:.0%} chance below 25 Mbps<br>"
                         f"about {round(s['expected_people_lifted']):,} lifted")}
                for s in d["sites"]]
        sub = (f"Budget {d['budget_new_tower_equivalents']:,.0f} tower-equivalents"
               + ("; every site checked on the ground." if d.get("checked_on_ground") else "."))
        names = {c["country"]: c["name"] for c in get(base, "/countries")["countries"]}
        page = charts.ranked_bars(rows, f"{names.get(d['country'], d['country'])} plan: expected people lifted above 25 Mbps, first {len(rows)} sites",
                                  sub, data_line + " Estimates from public data.", list(BUILD.values()))
    out = Path(a.out).resolve()
    out.write_text(page, encoding="utf-8")
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
    mg.add_argument("--ring", type=int, default=1, choices=[0, 1, 2], help="neighbour rings to show (needs the h3 package)")
    mg.add_argument("--no-osm", action="store_true", help="skip OpenStreetMap buildings, places and masts (faster)")
    ms = msub.add_parser("sites"); ms.add_argument("country"); ms.add_argument("--k", type=int, default=10); ms.add_argument("--out", default="site_map.html")
    ch = sub.add_parser("chart"); csub = ch.add_subparsers(dest="what", required=True)
    cc = csub.add_parser("countries"); cc.add_argument("--out", default="chart.html")
    cst = csub.add_parser("sites"); cst.add_argument("country"); cst.add_argument("--k", type=int, default=10); cst.add_argument("--out", default="chart.html")
    a = ap.parse_args(argv)

    is_point = a.cmd == "gap" or (a.cmd == "map" and a.what == "gap")
    if is_point and not (-90 <= a.lat <= 90 and -180 <= a.lon <= 180):
        raise SystemExit("latitude must be -90..90 and longitude -180..180")
    if a.cmd == "map":
        print(f"map written: {make_map(a.base, a)}")
        return
    if a.cmd == "chart":
        print(f"chart written: {make_chart(a.base, a)}")
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
