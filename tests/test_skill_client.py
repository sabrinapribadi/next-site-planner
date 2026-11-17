"""Agent skill client (R24): argument handling and request building, with the network stubbed out."""
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("nsp", Path(__file__).resolve().parents[1] / "skills/next-site-planner/scripts/nsp.py")
nsp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(nsp)


@pytest.fixture
def calls(monkeypatch):
    seen = []
    monkeypatch.setattr(nsp, "get", lambda base, path, params=None, timeout=60: seen.append((path, params)) or {"ok": True})
    return seen


def test_routes(calls, capsys):
    nsp.main(["countries", "--bar", "10"]); nsp.main(["gap", "-6.2", "106.8"])
    nsp.main(["sites", "phl", "--k", "500"]); nsp.main(["note", "idn", "3"])
    assert calls == [("/countries", {"bar_mbps": 10}), ("/gap", {"lat": -6.2, "lon": 106.8}),
                     ("/sites/PHL", {"k": 100}), ("/sites/IDN/3/note", None)]
    out = capsys.readouterr().out
    assert out.count('"ok": true') == 4          # each call prints the API's JSON


def test_bad_coordinates(calls):
    with pytest.raises(SystemExit):
        nsp.main(["gap", "95", "10"])
    assert calls == []


def test_skill_files():
    root = Path(__file__).resolve().parents[1] / "skills/next-site-planner"
    head = (root / "SKILL.md").read_text().split("---")[1]
    assert "name: next-site-planner" in head and "description:" in head
    cases = [p for p in (root / "evals").iterdir() if p.is_dir()]
    assert len(cases) >= 4 and all((c / "prompt.md").exists() and (c / "case.yaml").exists() and any((c / "graders").glob("*.md")) for c in cases)
    trig = json.loads((root / "trigger-evals.json").read_text())
    assert sum(t["should_trigger"] for t in trig) >= 8 and sum(not t["should_trigger"] for t in trig) >= 8


def test_quarter_dates():
    assert nsp.quarter_dates("2026Q3") == ("2026-07-01", "2026-09-30")
    assert nsp.quarter_dates("2026Q4") == ("2026-10-01", "2026-12-31")


def test_map_offline(monkeypatch, tmp_path):
    gap = {"h3": "888c106a49fffff", "district": "Kota Jakarta Utara", "typical_mbps": 89.3, "gap_type_25_mbps": "no gap",
           "chance_below_25_mbps": 0.0, "people_kontur": 12968}
    monkeypatch.setattr(nsp, "get", lambda base, path, params=None, timeout=60: gap)
    out = tmp_path / "m.html"
    nsp.main(["map", "gap", "-6.2", "106.8", "--out", str(out)])
    page = out.read_text()
    assert "leaflet@1.9.4" in page and "888c106a49fffff" in page and "Kota Jakarta Utara" in page
