"""ADR-009 contract tests: the four planner tools through Python, the REST API and the MCP server (fixture store, no key)."""

import asyncio
import json
import os
from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures" / "serving"
os.environ["GEO_SERVING_DIR"] = str(FIX)
os.environ.pop("OPENAI_API_KEY", None)                       # CI has no key: notes come from the template

from src.serving.contracts import Countries, GapAt, OutOfScope, SiteNote, TopSites  # noqa: E402
from src.serving.notes import NoteService, grade  # noqa: E402
from src.serving.store import Store  # noqa: E402
from src.serving.tools import REGISTRY, Tools  # noqa: E402

PTS = json.loads((FIX / "points.json").read_text())


@pytest.fixture(scope="module")
def tools():
    return Tools(Store(FIX), NoteService(None))


def test_gap_at_known_point_and_out_of_scope(tools):
    g = tools.gap_at(*PTS["jakarta"])
    assert isinstance(g, GapAt) and g.country == "IDN" and g.people_kontur > 0
    assert 0 <= g.chance_below_25_mbps <= 1 and g.chance_below_10_mbps <= g.chance_below_25_mbps + 1e-9
    assert isinstance(tools.gap_at(0.0, -150.0), OutOfScope)          # Pacific Ocean


def test_top_sites_ranked_and_typed(tools):
    for k in tools.store.countries["countries"]:
        t = tools.top_sites(k.lower(), 3)
        assert isinstance(t, TopSites) and [s.rank for s in t.sites] == [1, 2, 3]
        assert all(s.checked_on_ground == t.checked_on_ground for s in t.sites)
    assert isinstance(tools.top_sites("XX"), OutOfScope)


def test_explain_site_is_grounded_without_a_key(tools):
    n = tools.explain_site("IDN", 1)
    assert isinstance(n, SiteNote) and n.source == "template" and n.grader["served_ok"]
    assert isinstance(tools.explain_site("IDN", 99999), OutOfScope)


def test_compare_countries(tools):
    c = tools.compare_countries(25)
    assert isinstance(c, Countries) and len(c.countries) == 7
    assert all(0 <= r.share_below_bar_everyone <= 1 for r in c.countries)
    assert isinstance(tools.compare_countries(33), OutOfScope)


def test_rest_api_contract(tools, monkeypatch):
    from fastapi.testclient import TestClient

    import src.serving.api as api
    monkeypatch.setattr(api, "tools", lambda: tools)
    c = TestClient(api.app)
    assert c.get("/health").json()["ok"]
    lat, lon = PTS["berlin"]
    assert c.get("/gap", params={"lat": lat, "lon": lon}).json()["country"] == "DEU"
    assert c.get("/gap", params={"lat": 95, "lon": 0}).status_code == 422             # invalid latitude
    assert len(c.get("/sites/PHL", params={"k": 2}).json()["sites"]) == 2
    assert c.get("/sites/FRA/1/note").json()["grader"]["served_ok"]
    assert c.get("/countries", params={"bar_mbps": 10}).json()["bar_mbps"] == 10


def test_mcp_server_lists_and_calls_the_same_tools(tools):
    from src.serving.mcp_server import build_server
    srv = build_server(tools)
    names = {t.name for t in asyncio.run(srv.list_tools())}
    assert names == set(REGISTRY)
    out = asyncio.run(srv.call_tool("top_sites", {"country": "DEU", "k": 2}))
    text = json.dumps(out, default=str)
    assert "DEU" in text and "rank" in text


def test_grader_rejects_invented_numbers_names_and_promises():
    f = {"people": 2161, "chance_below_25_mbps": 0.523, "expected_people_lifted": 66, "bar_mbps": 25, "rank": 3}
    assert grade("2,161 people; 52% likely below 25 Mbps; about 66 could be lifted.", f)["ok"]
    assert grade("About 2,200 people, 52.3% below 25 Mbps.", f)["ok"]                  # rounding allowed
    assert not grade("2,161 people; 70 could be lifted.", f)["ok"]                    # 70 is not a fact
    assert not grade("2,161 people near the Digi tower.", f)["ok"]                    # operator name
    assert not grade("This site will lift 66 people.", f)["ok"]                       # promise
    assert grade("2,161 people in Orange, Vermont.", {**f, "district": "Orange, Vermont"})["ok"]   # a place name from the facts is not an operator
    assert grade("Buildings at -1 m elevation.", {**f, "elevation_m": -1})["ok"]          # below sea level (Jefferson, Louisiana)
    assert not grade("Buildings at -1 m elevation.", {**f, "elevation_m": 1})["ok"]       # the sign matters
    assert grade("Between 5-10 people.", {**f, "a": 5, "b": 10})["ok"]                    # a hyphen between numbers is a range


def test_cached_note_keeps_grounding_flag(tmp_path, tools):
    from src.serving.notes import NoteService
    svc = NoteService(None, tmp_path / "cache.json", save_every=1)
    t2 = Tools(tools.store, svc)
    first, again = t2.explain_site("DEU", 1), t2.explain_site("DEU", 1)
    assert first.grader["served_ok"] and again.grader["served_ok"] and again.meter.cached
