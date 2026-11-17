"""Site planner's agent for the app chat: one tool-using agent over the four planner tools, calling the public API.

Tool names, parameters and descriptions mirror src/serving/tools.py (REGISTRY); tests/test_streamlit_app.py fails if they drift.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

API = os.environ.get("NSP_API_BASE", "https://next-site-planner.vercel.app")
MODEL = "gpt-6-luna"
PRICES = {"input": 0.10, "cached_input": 0.01, "output": 0.50}            # USD per 1M tokens, as the notes' config (read 2026-10-12)
SYSTEM = """You are a mobile network planning assistant for Indonesia, Malaysia, the Philippines, Germany, France, the United States and the UAE.
Answer questions about how slow mobile is at a place and for how many people, each country's checked site plan, a note on one planned site, and how countries compare below a speed bar.
Always use the tools for facts; never guess a number. Every number in your answer must come from the question or a tool result: quote tool numbers (rounding is fine) and do not calculate new ones.
Chances and shares are fractions in the tools (0.93 = 93%). chance_below_25_mbps is the model's estimated chance that typical speed at the place is below 25 Mbps; it is not a share of speed tests, so never describe it as tests below a speed. People counts are the smaller of two population maps. plan_gain_vs_kpi is a relative gain: 1.85 means 185% more people lifted than KPI ranking at the same budget; say it that way and pair it with plan_people_lifted.
Countries are ISO codes in the tools (PHL, IDN, MYS, DEU, FRA, USA, ARE). If a place is outside the seven countries, say so. Say when a place has fewer than 10 speed tests.
If a question is outside these topics, say what you can help with instead, without calling tools. Answer in at most 120 words, plain English, no tables."""

SCHEMAS = [
    {"type": "function", "name": "gap_at",
     "description": "How slow is mobile at this point, and for how many people? Looks up the 0.74 km² hexagon containing (lat, lon).",
     "parameters": {"type": "object", "required": ["lat", "lon"], "properties": {
         "lat": {"type": "number", "minimum": -90, "maximum": 90, "description": "Latitude"},
         "lon": {"type": "number", "minimum": -180, "maximum": 180, "description": "Longitude"}}}},
    {"type": "function", "name": "top_sites",
     "description": "The first k sites of a country's checked site plan (budget 1,000 new-tower equivalents), best first.",
     "parameters": {"type": "object", "required": ["country"], "properties": {
         "country": {"type": "string", "description": "ISO3 code: IDN, MYS, PHL, DEU, FRA, USA or ARE"},
         "k": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10, "description": "How many sites"}}}},
    {"type": "function", "name": "explain_site",
     "description": "A short planner note on one nominal, grounded in its numbers (every number traced to the facts).",
     "parameters": {"type": "object", "required": ["country", "rank"], "properties": {
         "country": {"type": "string", "description": "ISO3 code"}, "rank": {"type": "integer", "minimum": 1, "description": "Rank in the plan"}}}},
    {"type": "function", "name": "compare_countries",
     "description": "Share and number of people below a speed bar in each country, and each country's site-plan result.",
     "parameters": {"type": "object", "properties": {
         "bar_mbps": {"type": "integer", "enum": [5, 10, 25, 50, 100], "default": 25, "description": "Speed bar in Mbps"}}}},
]


def _get(path: str, params: dict | None = None) -> dict:
    url = API.rstrip("/") + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"User-Agent": "next-site-planner-streamlit-agent/1.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code in (404, 422):
            return {"error": f"not found or invalid input (HTTP {e.code})"}
        raise


def _c(country: str) -> str:
    return urllib.parse.quote(str(country).upper(), safe="")


FNS = {
    "gap_at": lambda lat, lon: _get("/gap", {"lat": lat, "lon": lon}),
    "top_sites": lambda country, k=10: _get(f"/sites/{_c(country)}", {"k": k}),
    "explain_site": lambda country, rank: _get(f"/sites/{_c(country)}/{int(rank)}/note"),
    "compare_countries": lambda bar_mbps=25: _get("/countries", {"bar_mbps": bar_mbps}),
}
TOOLS = {s["name"]: {"schema": s, "fn": FNS[s["name"]]} for s in SCHEMAS}

QUESTIONS = [                                                             # recorded for replay by scripts/record_agent_replays.py
    "Is mobile slow near -6.2, 106.8 in Jakarta, and for how many people?",
    "Is there a coverage gap at 7.21421, 124.22888 in Cotabato City?",
    "Which are the top 5 sites in the Philippines' plan?",
    "Explain the Philippines' number 1 site.",
    "Which country has the largest share of people below 10 Mbps?",
    "How does Indonesia's plan compare with KPI ranking?",
    "What are Germany's top 3 sites and what kind of build are they?",
    "How slow is mobile in Tokyo, at 35.68, 139.76?",
    "Can you write me a poem about towers?",
]
