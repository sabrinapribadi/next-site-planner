"""ADR-009 gate in CI without a key: replay the recorded live notes through the same grader and coverage check."""

import json
from pathlib import Path

from src.serving.notes import coverage, grade, template_note

ROOT = Path(__file__).resolve().parents[1]
REC = json.loads((ROOT / "tests/fixtures/notes_recorded.json").read_text())
EVAL = json.loads((ROOT / "data/outputs/p5_notes_eval.json").read_text())


def test_recorded_live_notes_still_pass_the_grader():
    ok = [grade(r["raw"], r["facts"])["ok"] for r in REC if r["raw"]]
    assert len(ok) == len(REC) and sum(ok) / len(ok) >= 0.90


def test_every_served_note_is_grounded():
    for r in REC:
        served = r["raw"] if r["raw"] and grade(r["raw"], r["facts"])["ok"] else template_note(r["facts"])
        assert grade(served, r["facts"])["ok"], (r["country"], r["rank"], served)


def test_required_fact_coverage():
    cov = [coverage(r["raw"] if grade(r["raw"], r["facts"])["ok"] else template_note(r["facts"]), r["facts"])["all"] for r in REC]
    assert sum(cov) / len(cov) >= 0.90


def test_template_always_grounded_and_covering():
    for r in REC:
        t = template_note(r["facts"])
        assert grade(t, r["facts"])["ok"] and coverage(t, r["facts"])["all"], t


def test_reported_gate_matches_the_recorded_metrics():
    g = EVAL["gate"]
    assert g["live_grounded_ge_90"] == (EVAL["live_grounded_pass_rate"] >= 0.90)
    assert g["cost_within_budget"] == (EVAL["cost_per_1000_usd"] <= EVAL["budgets"]["cost_per_1000_usd"])
    assert g["p95_live_within_budget"] == (EVAL["latency_ms_live"]["p95"] <= EVAL["budgets"]["p95_ms_live"])
    assert EVAL["gate_passed"] == all(g.values())
