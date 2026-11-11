"""Public, read-only deployment of the planner API and MCP server (ADR-011; rules R19, R20).

    GEO_SERVING_DIR=~/data/geo/serving uvicorn src.serving.public:app --port 8000

- REST: the four planner tools of src/serving/api.py.
- MCP: the same tools over Streamable HTTP at /mcp, stateless (MCP 2026-07-28), so it runs on serverless hosts.
- Notes: cached or template only. No API key is deployed, so public traffic never spends tokens (R13, R20).
- Data: derived from Speedtest by Ookla open data (CC BY-NC-SA 4.0) and the sources in the README; attribution in every root reply.
"""

from __future__ import annotations

import contextlib
import os

from fastapi import FastAPI, Query
from mcp.server.transport_security import TransportSecuritySettings

from src.serving.contracts import Countries, GapAt, OutOfScope, SiteNote, TopSites
from src.serving.mcp_server import build_server
from src.serving.notes import NoteService
from src.serving.store import Store
from src.serving.tools import CFG, Tools

ATTRIBUTION = ("Speed data: Speedtest by Ookla Global Fixed and Mobile Network Performance Maps (CC BY-NC-SA 4.0); population: "
               "Kontur and WorldPop (CC BY 4.0); land cover: ESA WorldCover (CC BY 4.0); elevation: Copernicus DEM GLO-30. "
               "Derived data shared under CC BY-NC-SA 4.0, non-commercial.")

STORE = Store()
TOOLS = Tools(STORE, NoteService(None, STORE.path / "notes_cache.json", cache_model=CFG["notes"]["model"]))


def allowed_hosts() -> list[str]:
    """DNS-rebinding protection on: localhost plus the hostnames the platform sets, plus PUBLIC_HOSTS (comma-separated)."""
    hosts = ["localhost", "localhost:*", "127.0.0.1", "127.0.0.1:*"]
    hosts += [os.environ[v] for v in ("VERCEL_URL", "VERCEL_BRANCH_URL", "VERCEL_PROJECT_PRODUCTION_URL") if os.environ.get(v)]
    return hosts + [h.strip() for h in os.environ.get("PUBLIC_HOSTS", "").split(",") if h.strip()]


_hosts = allowed_hosts()
MCP = build_server(TOOLS).streamable_http_app(
    stateless_http=True, json_response=True, streamable_http_path="/",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=_hosts,
                                                 allowed_origins=[f"{s}://{h}" for h in _hosts for s in ("http", "https")]))


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI):
    async with MCP.router.lifespan_context(MCP):
        yield


app = FastAPI(title="Next Site Planner API", version="1", lifespan=lifespan,
              description="Where one more mobile site helps the most people in seven countries: speed gaps per 0.74 km² hexagon, "
                          "checked site plans and grounded site notes. Read-only; notes are cached or templated. MCP endpoint: /mcp. "
                          + ATTRIBUTION)
app.mount("/mcp", MCP)


@app.get("/")
def root() -> dict:
    return {"name": "next-site-planner", "docs": "/docs", "mcp": "/mcp", "countries": list(STORE.countries["countries"]),
            "attribution": ATTRIBUTION, "results_page": "https://sabrinapribadi.github.io/next-site-planner/"}


@app.get("/health")
def health() -> dict:
    return {"ok": True, "countries": list(STORE.countries["countries"]), "notes": "cached or template (no LLM calls on this host)"}


@app.get("/gap", response_model=GapAt | OutOfScope)
def gap(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180)):
    return TOOLS.gap_at(lat, lon)


@app.get("/sites/{country}", response_model=TopSites | OutOfScope)
def sites(country: str, k: int = Query(10, ge=1, le=100)):
    return TOOLS.top_sites(country, k)


@app.get("/sites/{country}/{rank}/note", response_model=SiteNote | OutOfScope)
def note(country: str, rank: int):
    return TOOLS.explain_site(country, rank)


@app.get("/countries", response_model=Countries | OutOfScope)
def countries(bar_mbps: int = Query(25)):
    return TOOLS.compare_countries(bar_mbps)
