"""P5 evaluation of grounded site notes (ADR-009): live run, metered, recorded for CI replay.

    python scripts/eval_notes.py

Evaluation set (fixed rule): 10 nominals per country at evenly spaced ranks of its plan, plus 10 hard cases
(3 crowding-flagged, 2 steep or high, 2 where the population maps differ most, 3 unchecked or lowest-people).
Each is written live (no cache), graded, scored for required facts, and metered. Then each is requested again through
the cache to measure cached latency. Writes data/outputs/p5_notes_eval.json and tests/fixtures/notes_recorded.json.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.serving.notes import coverage, facts_for, grade, template_note  # noqa: E402
from src.serving.tools import CFG, Tools  # noqa: E402

log = lambda *a: print(time.strftime("%H:%M:%S"), *a, flush=True)


def eval_set(t: Tools) -> list[tuple[str, dict, str]]:
    cases, seen = [], set()
    for k in t.store.countries["countries"]:
        p = t.store.plan(k).reset_index(drop=True)
        for i in np.unique(np.linspace(0, len(p) - 1, 10).round().astype(int)):
            r = p.iloc[i].to_dict(); cases.append((k, r, "stratified")); seen.add(r["h3"])
    allp = t.store.plans
    hard = []
    if "built_m2_per_person" in allp:
        hard += [("crowded", allp[(allp.built_m2_per_person < 10) & ~allp.h3.isin(seen)].sort_values("built_m2_per_person").head(3))]
        hard += [("steep_or_high", allp[(allp.steep.fillna(False) | allp.high.fillna(False)) & ~allp.h3.isin(seen)].head(2))]
        ratio = (np.maximum(allp.kontur_people, allp.worldpop_people) + 100) / (np.minimum(allp.kontur_people, allp.worldpop_people) + 100)
        hard += [("maps_disagree", allp.assign(_r=ratio)[~allp.h3.isin(seen)].sort_values("_r", ascending=False).head(2))]
    unchecked = allp[allp.site_lat.isna() & ~allp.h3.isin(seen)] if "site_lat" in allp else allp.iloc[0:0]
    hard += [("unchecked_or_few_people", (unchecked if len(unchecked) else allp[~allp.h3.isin(seen)]).sort_values("people").head(3))]
    for tag, df in hard:
        for r in df.to_dict("records"):
            cases.append((r["iso3"], r, tag))
    return cases


def main() -> None:
    t = Tools(); c = CFG["notes"]
    assert t.notes.writer is not None, "set OPENAI_API_KEY for the live evaluation"
    cases = eval_set(t); recs = []
    log(f"{len(cases)} cases")
    for i, (k, r, tag) in enumerate(cases, 1):
        site = t._site({**r, "iso3": k})
        f = facts_for(r, t.store.countries["countries"][k]["name"], site.checked_on_ground)
        note, source, g, meter, raw = t.notes.note(f, use_cache=False)
        cov = coverage(note, f)
        recs.append({"country": k, "rank": int(r["rank"]), "tag": tag, "facts": f, "raw": raw, "source": source, "grader": g,
                     "coverage": cov, "meter": meter.model_dump()})
        if i % 10 == 0:
            log(f"{i}/{len(cases)} written")
    cached_ms = []
    for k, r, _ in cases:                                    # same facts again: served from the cache
        t0 = time.perf_counter(); t.explain_site(k, int(r["rank"])); cached_ms.append((time.perf_counter() - t0) * 1000)
    live = [x for x in recs if x["meter"]["provider"] == "openai"]
    lat = np.array([x["meter"]["latency_ms"] for x in live]); cost = np.array([x["meter"]["cost_usd"] for x in live])
    res = {
        "design": "ADR-009", "model": c["model"], "prompt": "src/serving/notes.py SYSTEM (v1)", "cases": len(recs), "live_calls": len(live),
        "live_grounded_pass_rate": float(np.mean([x["grader"]["ok"] for x in recs])),
        "served_grounded_rate": float(np.mean([x["grader"]["served_ok"] for x in recs])),
        "required_fact_coverage": float(np.mean([x["coverage"]["all"] for x in recs])),
        "coverage_by_fact": {kk: float(np.mean([x["coverage"][kk] for x in recs])) for kk in ("intervention", "people", "chance_below", "ground_check")},
        "served_by_template": int(sum(x["source"] == "template" for x in recs)),
        "failures": [{"country": x["country"], "rank": x["rank"], "tag": x["tag"], "grader": x["grader"], "raw": x["raw"]} for x in recs if not x["grader"]["ok"]],
        "cost_per_1000_usd": float(1000 * cost.mean()) if len(cost) else None,
        "latency_ms_live": {"p50": float(np.percentile(lat, 50)), "p95": float(np.percentile(lat, 95))} if len(lat) else None,
        "latency_ms_cached": {"p50": float(np.percentile(cached_ms, 50)), "p95": float(np.percentile(cached_ms, 95))},
        "tokens_mean": {"input": float(np.mean([x["meter"]["input_tokens"] for x in live])), "output": float(np.mean([x["meter"]["output_tokens"] for x in live]))},
        "budgets": {"cost_per_1000_usd": c["budget_cost_per_1000"], "p95_ms_live": c["budget_p95_ms_live"], "p95_ms_cached": c["budget_p95_ms_cached"]},
        "prices_per_m_usd": {"input": c["price_input_per_m"], "cached_input": c["price_cached_input_per_m"], "output": c["price_output_per_m"],
                             "source": "developers.openai.com/api/docs/pricing, retrieved 2026-10-14"},
    }
    res["gate"] = {"live_grounded_ge_90": res["live_grounded_pass_rate"] >= 0.90, "served_grounded_100": res["served_grounded_rate"] == 1.0,
                   "coverage_ge_90": res["required_fact_coverage"] >= 0.90,
                   "cost_within_budget": res["cost_per_1000_usd"] is not None and res["cost_per_1000_usd"] <= c["budget_cost_per_1000"],
                   "p95_live_within_budget": res["latency_ms_live"] is not None and res["latency_ms_live"]["p95"] <= c["budget_p95_ms_live"],
                   "p95_cached_within_budget": res["latency_ms_cached"]["p95"] <= c["budget_p95_ms_cached"]}
    res["gate_passed"] = all(res["gate"].values())
    (ROOT / "data/outputs/p5_notes_eval.json").write_text(json.dumps(res, indent=1))
    fx = ROOT / "tests/fixtures"; fx.mkdir(parents=True, exist_ok=True)
    (fx / "notes_recorded.json").write_text(json.dumps([{k: x[k] for k in ("country", "rank", "tag", "facts", "raw")} for x in recs], indent=1, ensure_ascii=False))
    log({k: res[k] for k in ("live_grounded_pass_rate", "served_grounded_rate", "required_fact_coverage", "cost_per_1000_usd", "latency_ms_live", "latency_ms_cached", "served_by_template")})
    log("gate", res["gate"], "passed" if res["gate_passed"] else "FAILED")


if __name__ == "__main__":
    main()
