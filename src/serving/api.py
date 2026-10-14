"""REST API over the planner tools (ADR-009).

    uvicorn src.serving.api:app --port 8000
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI, Query

from src.serving.contracts import Countries, GapAt, OutOfScope, SiteNote, TopSites
from src.serving.tools import Tools

app = FastAPI(title="Next Site Planner API", version="1", description="Where one more mobile site helps the most people: speed gaps, checked site plans and grounded site notes.")


@lru_cache(maxsize=1)
def tools() -> Tools:
    return Tools()


@app.get("/health")
def health() -> dict:
    return {"ok": True, "countries": list(tools().store.countries["countries"])}


@app.get("/gap", response_model=GapAt | OutOfScope)
def gap(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180)):
    return tools().gap_at(lat, lon)


@app.get("/sites/{country}", response_model=TopSites | OutOfScope)
def sites(country: str, k: int = Query(10, ge=1, le=100)):
    return tools().top_sites(country, k)


@app.get("/sites/{country}/{rank}/note", response_model=SiteNote | OutOfScope)
def note(country: str, rank: int):
    return tools().explain_site(country, rank)


@app.get("/countries", response_model=Countries | OutOfScope)
def countries(bar_mbps: int = Query(25)):
    return tools().compare_countries(bar_mbps)
