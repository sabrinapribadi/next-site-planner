"""Streamlit companion app (R26): data helpers and AppTest smoke tests of every tab, offline (API answers recorded in fixtures)."""
import io
import json
import sys
import types
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
pytest.importorskip("streamlit")
pytest.importorskip("h3")
import nsp_data as D
from streamlit.testing.v1 import AppTest

APP = str(ROOT / "app" / "streamlit_app.py")
FIX = json.loads((ROOT / "tests" / "fixtures" / "app_api.json").read_text())


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def offline(monkeypatch):
    """Serve recorded API answers; anything not recorded fails like a network error."""
    def fake(req, timeout=None):
        key = req.full_url.split(D.API.rstrip("/"), 1)[1]
        if key not in FIX:
            raise urllib.error.URLError(f"not recorded: {key}")
        return _Resp(json.dumps(FIX[key]).encode())
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    monkeypatch.setattr(D, "time", types.SimpleNamespace(sleep=lambda s: None))   # only the helper's retry pause


def run(view=None, **state):
    at = AppTest.from_file(APP, default_timeout=60)
    if view:
        at.session_state["view"] = view
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    assert not at.exception, at.exception
    return at


def test_budget_rows_match_committed_plan():
    plan = D.load_plan()
    rows = D.budget_rows(plan, "PHL")
    at1000 = {r["method"]: r["people"] for r in rows if r["budget"] == 1000.0}
    b = plan["countries"]["PHL"]["budgets"]["1000"]
    assert at1000[D.METHODS["people_lifted"]] == b["people_lifted"] and at1000[D.METHODS["kpi_ranking"]] == b["kpi_ranking"]
    assert {r["budget"] for r in D.budget_rows(plan, "ARE")} >= {29.3, 1000.0}


def test_helpers():
    assert D.place_name("PHL") == "the Philippines" and D.place_name("IDN") == "Indonesia"
    assert D.ramp(0.93) == "#a8461a" and D.ramp(None) == "#c9ccd3" and D.hex_rgb("#2a78d6", 10) == [42, 120, 214, 10]
    assert len(D.neighbours("8868513063fffff")) == 6
    assert "](https://" in " ".join(dict(D.brief())["Where"])


def test_map_tab_opens_with_brief_and_shortlist(offline):
    at = run()
    text = " ".join(m.value for m in at.markdown)
    caps = " ".join(c.value for c in at.caption)
    assert "A planner that picks" in text and "Results page" in caps and "12 hours" in caps
    hl = D.headline(D.load_plan())
    assert [m.value for m in at.metric][:2] == [f"{hl['people_plan']:,.0f}", "1.5–3.8×"]       # first screen: committed results
    assert at.subheader[0].value.startswith("Philippines: the first 50 sites lift about")
    assert [m.label for m in at.metric][4:] == ["Sites shown", "People likely lifted", "Budget used", "Checked on the ground"]


def test_site_note(offline):
    at = run()
    opts = at.selectbox(key="focus").options
    at.selectbox(key="focus").set_value(opts[1]).run()
    assert not at.exception and any("Site #1, Cotabato City" in m.value for m in at.markdown)


def test_budget_tab_uses_committed_numbers(offline):
    at = run("Budget what-if")
    b = D.load_plan()["countries"]["PHL"]["budgets"]["1000"]
    assert at.subheader[0].value.startswith(f"At 1,000 tower-equivalents in the Philippines, the plan lifts about {b['people_lifted']:,.0f} people")


def test_place_tab_and_thin_evidence(offline):
    at = run("Check a place")
    assert at.subheader[0].value.startswith("Cotabato City") and "93% chance" in at.subheader[0].value
    assert [m.value for m in at.metric][4:6] == ["15 Mbps", "25"]


def test_speed_bar_tab_and_api_failure(offline):
    at = run("Countries at your speed bar")
    assert at.subheader[0].value.startswith("Below 25 Mbps: The Philippines has the largest share")
    at = run("Countries at your speed bar", bar=100)                    # not recorded: the app must warn, not crash
    assert any("did not answer" in w.value for w in at.warning)
