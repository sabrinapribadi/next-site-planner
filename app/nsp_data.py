"""Data access for the Streamlit companion app (R26): the public API and the committed plan results only; no keys, no store.

Every number shown in the app comes from here, so the app says exactly what the API and the results page say.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import h3
import yaml

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "data" / "outputs" / "p4_site_plan.json"
BRIEF = ROOT / "docs" / "brief.yaml"
REPO = "https://github.com/sabrinapribadi/next-site-planner"
PAGES = "https://sabrinapribadi.github.io/next-site-planner/"
API = os.environ.get("NSP_API_BASE", "https://next-site-planner.vercel.app")

COUNTRIES = {"PHL": "Philippines", "IDN": "Indonesia", "MYS": "Malaysia", "DEU": "Germany", "FRA": "France",
             "USA": "United States", "ARE": "United Arab Emirates"}
BARS = [5, 10, 25, 50, 100]                                   # speed bars the API serves
INTERVENTION = {"macro": "New macro site", "small_cell": "Small cell", "capacity": "Co-location (capacity)"}
METHODS = {"people_lifted": "This plan (exact optimiser)", "kpi_ranking": "KPI ranking (today's practice)", "slowest_first": "Slowest first"}
PRESETS = {
    "Cotabato City, Philippines (plan's top site)": (7.21421, 124.22888),
    "North Jakarta, Indonesia": (-6.2, 106.8),
    "Kota Kinabalu, Malaysia": (5.9804, 116.0735),
    "Berlin Mitte, Germany": (52.52, 13.405),
    "Rural Auvergne, France": (45.2, 3.0),
}
RAMP = [(0.2, "#fde3d4"), (0.4, "#f7b48f"), (0.6, "#ef8a55"), (0.8, "#d9622a"), (1.01, "#a8461a")]   # chance below 25 Mbps (as the skill's maps)
MARKER = {"macro": "#2a78d6", "small_cell": "#1baf7a", "capacity": "#6250d6"}


class ApiError(RuntimeError):
    pass


def get(path: str, params: dict | None = None, timeout: float = 45) -> dict:
    """GET the public API; a 404 comes back as data ({"not_found": True}); two failures raise ApiError."""
    url = API.rstrip("/") + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"User-Agent": "next-site-planner-streamlit/1.0", "Accept": "application/json"})
    last: Exception | None = None
    for attempt in range(2):                                  # one retry covers a cold start
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {"not_found": True}
            last = e
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            last = e
        time.sleep(1.5 * (attempt + 1))
    raise ApiError(f"{type(last).__name__}: {last}")


def place_name(code: str) -> str:
    """Country name as it reads in a sentence ("the Philippines")."""
    n = COUNTRIES[code]
    return f"the {n}" if code in {"PHL", "USA", "ARE"} else n


def hex_rgb(h: str, alpha: int = 255) -> list[int]:
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)] + [alpha]


def ramp(p: float | None) -> str:
    if p is None:
        return "#c9ccd3"
    return next(c for t, c in RAMP if p < t)


def neighbours(cell: str) -> list[str]:
    """Ring 1 around a hexagon (6 cells), in a stable order."""
    return sorted(set(h3.grid_disk(cell, 1)) - {cell})


def centre(cell: str) -> tuple[float, float]:
    return h3.cell_to_latlng(cell)


def budget_rows(plan: dict, country: str) -> list[dict]:
    """People lifted at each budget for the three methods, with the plan's low-high range (P4, committed)."""
    out = []
    for b, v in sorted(plan["countries"][country]["budgets"].items(), key=lambda kv: float(kv[0])):
        for k, name in METHODS.items():
            out.append({"budget": float(b), "method": name, "people": v[k],
                        "low": v["people_lifted_low"] if k == "people_lifted" else None,
                        "high": v["people_lifted_high"] if k == "people_lifted" else None,
                        "sites": v["sites"], "gain_vs_kpi": v["gain_vs_kpi"]})
    return out


def load_plan(path: Path = PLAN) -> dict:
    return json.loads(Path(path).read_text())


def brief(path: Path = BRIEF) -> list[tuple[str, list[str]]]:
    """R22 brief items; links to repo files become absolute GitHub links."""
    b = yaml.safe_load(Path(path).read_text())

    def fix(t: str) -> str:
        return re.sub(r"\]\((?!https?://)([^)]+)\)", lambda m: f"]({REPO}/blob/main/{m.group(1)})", t)

    return [(item["w"], [fix(str(x)) for x in item["lines"]]) for item in b["brief"]]


def headline(plan: dict) -> dict:
    """KPI strip for the first screen: the seven plans at their headline budgets (committed P4 results)."""
    rows = []
    for c, v in plan["countries"].items():
        b = next(x for k, x in v["budgets"].items() if float(k) == float(v["headline_budget"]))
        rows.append((c, b["people_lifted"], b["kpi_ranking"], b["sites"], 1 + b["gain_vs_kpi"]))
    return {"people_plan": sum(r[1] for r in rows), "people_kpi": sum(r[2] for r in rows), "sites": sum(r[3] for r in rows),
            "times_min": min(r[4] for r in rows), "times_max": max(r[4] for r in rows), "countries": len(rows)}


def md_html(text: str) -> str:
    """Markdown links and bold to HTML for the compact brief cards (brief text is our own, from docs/brief.yaml)."""
    import html as _h
    t = _h.escape(text, quote=False)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2" target="_blank">\1</a>', t)
    return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
