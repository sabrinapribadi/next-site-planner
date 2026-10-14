"""Markdown tables for ADR-001 and ADR-008 (amendments 1-2), rendered from the outputs so documents cannot drift.

    python scripts/validation_tables.py

Reads data/outputs/p1b_population_crosscheck.json, p4_site_plan.json and p4b_nominal_validation.json (with --partial:
pending countries are marked) and prints the tables to paste into the ADRs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
import site_plan as sp  # noqa: E402

NAMES = {"IDN": "Indonesia", "MYS": "Malaysia", "PHL": "Philippines", "DEU": "Germany", "FRA": "France", "USA": "United States", "ARE": "UAE"}
M = lambda v: f"{v / 1e6:,.1f}M" if v >= 1e5 else f"{v / 1e3:,.0f}k"
P = lambda v: "n/a" if v is None else f"{v:+.0%}"


def main() -> None:
    out = ROOT / "data/outputs"
    p4 = json.loads((out / "p4_site_plan.json").read_text())["countries"]
    p4b_all = json.loads((out / "p4b_nominal_validation.json").read_text()); p4b = p4b_all["countries"]
    pending = p4b_all.get("pending_countries", [])
    orig = json.loads((out / "p4_site_plan_original.json").read_text())["countries"]
    p1b_f = out / "p1b_population_crosscheck.json"
    p1b = json.loads(p1b_f.read_text())["countries"] if p1b_f.exists() else {}
    ks = [k for k in sp.CFG["countries"] if k in p4b]

    if p1b:
        print("### ADR-001: Kontur vs WorldPop\n")
        print("| Country | Total: Kontur / WorldPop | People in poorly served hexagons: difference | People where the maps differ > 3× | Expected below 25 Mbps: Kontur / WorldPop / smaller | Untested, likely below 25 Mbps: Kontur / WorldPop | Row 3 (> 10%) |")
        print("|---|---|---|---|---|---|---|")
        for k in [k for k in sp.CFG["countries"] if k in p1b]:
            r = p1b[k]; e, u = r["expected_below_25_all"], r["expected_below_25_untested"]
            print(f"| {NAMES[k]} | {M(r['total']['kontur'])} / {M(r['total']['worldpop'])} | {r['adr001_poorly_served_difference']:+.1%} | {r['kontur_share_in_disagreeing_hexagons']:.1%} "
                  f"| {M(e['kontur'])} / {M(e['worldpop'])} / {M(e['smaller'])} | {M(u['kontur'])} / {M(u['worldpop'])} | {'triggered' if r['adr001_row3_triggered'] else 'no'} |")
        print()

    print("### ADR-008 amendment 1: the original nominals\n")
    print("| Country | Original nominals | Population maps differ > 3× | WorldPop 0 | No built-up land (< 1,000 m²) | Mostly water or wetland | Steep | High | People lifted: original → re-scored → checked plan |")
    print("|---|---|---|---|---|---|---|---|---|")
    for k in ks:
        r = p4b[k]
        print(f"| {NAMES[k]} | {r['original_nominals']:,} | {r['share_population_disagrees_3x']:.0%} | {r['share_worldpop_zero']:.0%} | {r['share_fail_built_up']:.1%} "
              f"| {r['share_mostly_water_or_wetland']:.1%} | {r['share_steep']:.1%} | {r['share_high']:.1%} "
              f"| {r['original_people_lifted']:,.0f} → {r['original_rescored_people_lifted']:,.0f} → {r['validated_people_lifted']:,.0f} |")

    print("\n### ADR-008 amendment 1: checked plan vs KPI ranking\n")
    print("| Country | Checked plan: people lifted (range over θ) | KPI ranking | Gain | Gain before the checks | Overlap with the original plan | Solve rounds (plan, KPI) | Excluded: no built-up |")
    print("|---|---|---|---|---|---|---|---|")
    for k in ks:
        r, v = p4b[k], p4[k]
        hb = v["budgets"][str(v["headline_budget"])]
        print(f"| {NAMES[k]} | {r['validated_people_lifted']:,.0f} ({r['validated_range'][0]:,.0f}–{r['validated_range'][1]:,.0f}) | {r['validated_kpi']:,.0f} | {P(r['validated_gain_vs_kpi'])} "
              f"| {P(r['original_gain_vs_kpi'])} | {r['jaccard_original_vs_validated']:.2f} | {v['validation']['solve_rounds']['plan']}, {v['validation']['solve_rounds']['kpi']} | {v['validation']['excluded_no_built_up']} |")

    print("\n### ADR-008 amendment 2: crowding sensitivity\n")
    print("| Country | Headline top-10 flagged (< 10 m² built-up per person) | Headline benefit from flagged nominals | Headline people lifted → under the cap | Capped plan | Overlap with headline |")
    print("|---|---|---|---|---|---|")
    for k in ks:
        c = p4b[k]["crowding_cap_sensitivity"]
        print(f"| {NAMES[k]} | {c['headline_top10_crowded']} | {c['headline_crowded_benefit_share']:.1%} | {c['headline_people_lifted']:,.0f} → {c['headline_plan_under_cap']:,.0f} "
              f"| {c['capped_plan_people_lifted']:,.0f} | {c['jaccard']:.2f} |")
    for k in pending:
        print(f"| {NAMES[k]} | pending: WorldPop file still downloading |")
    print(f"\nChecked-plan gate: {sum(p4b[k]['validated_gate_10pct'] for k in ks)} of {len(ks)} countries ≥ +10%.")
    print(f"Original gates for comparison: {sum(bool(orig[k]['gate_gain_10pct']) for k in ks)} of {len(ks)}.")


if __name__ == "__main__":
    main()
