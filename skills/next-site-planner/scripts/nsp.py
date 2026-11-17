#!/usr/bin/env python3
"""Client for the public next-site-planner API (standard library only).

    python nsp.py countries [--bar 25]
    python nsp.py gap LAT LON
    python nsp.py sites COUNTRY [--k 10]
    python nsp.py note COUNTRY RANK
    python nsp.py ... --base https://next-site-planner.vercel.app   # another deployment

Prints the API's JSON. The host scales to zero, so the first call can take a few seconds; the client retries once.
Exit code 0 on success (including an out-of-scope answer, which is a valid result), 1 on a network or HTTP error.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASE = "https://next-site-planner.vercel.app"
COUNTRIES = ("IDN", "MYS", "PHL", "DEU", "FRA", "USA", "ARE")


def get(base: str, path: str, params: dict | None = None, timeout: float = 60) -> dict:
    url = base.rstrip("/") + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"User-Agent": "next-site-planner-skill/1.0", "Accept": "application/json"})
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


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default=DEFAULT_BASE)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("countries"); c.add_argument("--bar", type=int, default=25, help="speed bar in Mbps (default 25)")
    g = sub.add_parser("gap"); g.add_argument("lat", type=float); g.add_argument("lon", type=float)
    s = sub.add_parser("sites"); s.add_argument("country"); s.add_argument("--k", type=int, default=10, help="1-100 sites")
    n = sub.add_parser("note"); n.add_argument("country"); n.add_argument("rank", type=int)
    a = ap.parse_args(argv)

    if a.cmd == "countries":
        out = get(a.base, "/countries", {"bar_mbps": a.bar})
    elif a.cmd == "gap":
        if not (-90 <= a.lat <= 90 and -180 <= a.lon <= 180):
            raise SystemExit("latitude must be -90..90 and longitude -180..180")
        out = get(a.base, "/gap", {"lat": a.lat, "lon": a.lon})
    elif a.cmd == "sites":
        out = get(a.base, f"/sites/{a.country.upper()}", {"k": max(1, min(100, a.k))})
    else:
        out = get(a.base, f"/sites/{a.country.upper()}/{a.rank}/note")
    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)
    print()


if __name__ == "__main__":
    main()
