"""ADR-008 amendment 1: how the original nominals fare on each check, and original vs validated plan.

    python scripts/nominal_validation_report.py

Countries the validated run marks as pending (WorldPop still downloading) are listed, not reported.

Reads the archived original plans (data/outputs/p4_original_plans/, p4_site_plan_original.json), the validated run
(p4_site_plan.json, docs/data/plans/), WorldPop per hexagon and the ground-check cache.
Writes data/outputs/p4b_nominal_validation.json.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
import site_plan as sp  # noqa: E402

RATIO = 3.0
CROWDED_M2 = sp.CROWD_M2   # amendment 2 (post-hoc): fewer m² of built-up land per person than this is implausible


def main() -> None:
    t0 = time.time()
    orig_j = json.loads((ROOT / "data/outputs/p4_site_plan_original.json").read_text())["countries"]
    val_j = json.loads((ROOT / "data/outputs/p4_site_plan.json").read_text())
    pending = val_j.get("pending_countries", [])
    assert "amendment 1" in val_j["design"], "p4_site_plan.json is not the validated run"
    val_j = val_j["countries"]
    ck = sp.run_checks([])
    out = {}
    for k in [k for k in sp.CFG["countries"] if k not in pending]:
        wp = pd.read_parquet(sp.DER / f"hex_worldpop_{k}.parquet")[["h3", "wp_population"]]
        o = pd.read_csv(ROOT / "data/outputs/p4_original_plans" / f"{k}.csv").merge(wp, on="h3", how="left").fillna({"wp_population": 0})
        o = o.merge(ck[["built_ok", "built_m2", "share_water", "share_wetland", "share_mangrove", "share_tree", "steep", "high", "elevation_m"]],
                    left_on="h3", right_index=True, how="left")
        assert o.built_ok.notna().all(), f"{k}: original nominals not all checked"
        ratio = (np.maximum(o.people, o.wp_population) + 100) / (np.minimum(o.people, o.wp_population) + 100)
        wet = o.share_water + o.share_wetland + o.share_mangrove
        # original plan re-scored: people both sources agree on, nothing where there is no built-up land
        rescored = (o.expected_lifted * np.minimum(o.people, o.wp_population) / o.people.clip(lower=1) * o.built_ok.astype(float)).sum()
        v = pd.read_csv(ROOT / "docs/data/plans" / f"{k}.csv")
        so, sv = set(o.h3), set(v.h3)
        ob, vb = orig_j[k]["budgets"][str(orig_j[k]["headline_budget"])], val_j[k]["budgets"][str(val_j[k]["headline_budget"])]
        r = {
            "original_nominals": int(len(o)),
            "share_population_disagrees_3x": float((ratio > RATIO).mean()),
            "share_worldpop_zero": float((o.wp_population < 1).mean()),
            "share_fail_built_up": float((~o.built_ok.astype(bool)).mean()),
            "share_mostly_water_or_wetland": float((wet > 0.5).mean()),
            "share_mostly_tree_cover": float((o.share_tree > 0.5).mean()),
            "share_steep": float(o.steep.astype(bool).mean()), "share_high": float(o.high.astype(bool).mean()),
            "original_people_lifted": ob["people_lifted"], "original_rescored_people_lifted": float(rescored),
            "original_gain_vs_kpi": ob["gain_vs_kpi"],
            "validated_people_lifted": vb["people_lifted"], "validated_range": [vb["people_lifted_low"], vb["people_lifted_high"]],
            "validated_kpi": vb["kpi_ranking"], "validated_gain_vs_kpi": vb["gain_vs_kpi"], "validated_gate_10pct": val_j[k]["gate_gain_10pct"],
            "validated_sites": int(len(v)), "validated_share_steep": float(v.steep.mean()), "validated_share_high": float(v.high.mean()),
            "validated_median_built_m2": float(v.built_m2.median()), "validated_median_places": float(v.places.median()),
            "validated_share_zero_places": float((v.places == 0).mean()),
            "posthoc_crowded_share": float((v.built_m2_per_person < CROWDED_M2).mean()),
            "posthoc_crowded_benefit_share": float(v.expected_lifted[v.built_m2_per_person < CROWDED_M2].sum() / max(v.expected_lifted.sum(), 1e-9)),
            "validated_median_built_m2_per_person": float(v.built_m2_per_person.median()),
            "jaccard_original_vs_validated": len(so & sv) / len(so | sv) if so | sv else 1.0,
            "validation": val_j[k].get("validation"),
            "crowding_cap_sensitivity": val_j[k]["sensitivity"].get("crowding_cap"),
        }
        r["original_fails_built_over_20pct"] = r["share_fail_built_up"] > 0.20
        out[k] = r
        g = lambda x: "n/a" if x is None else f"{x:+.0%}"
        sp.log(k, f"orig {len(o):,}: pop disagrees {r['share_population_disagrees_3x']:.0%} (WorldPop 0: {r['share_worldpop_zero']:.0%}), no built-up {r['share_fail_built_up']:.1%}, "
                  f"water {r['share_mostly_water_or_wetland']:.1%}, crowded {r['posthoc_crowded_share']:.1%} ({r['posthoc_crowded_benefit_share']:.0%} of benefit), steep {r['share_steep']:.1%}, high {r['share_high']:.1%} | lifted orig {r['original_people_lifted']:,.0f} → "
                  f"rescored {rescored:,.0f} → validated {r['validated_people_lifted']:,.0f} | gain orig {g(r['original_gain_vs_kpi'])} → validated {g(r['validated_gain_vs_kpi'])} | J {r['jaccard_original_vs_validated']:.2f}")
    passed = sum(v["validated_gate_10pct"] for v in out.values())
    res = {"design": "ADR-008 amendment 1", "population_disagreement_ratio": RATIO, "built_up_minimum_m2": sp.BUILT_MIN_M2,
           "posthoc_crowded_m2_per_person": CROWDED_M2, "posthoc_note": "crowding diagnostic added after the checks ran; report-only, never removes a nominal",
           "countries": out, "validated_gate_countries_passed": int(passed), "validated_gate_passed": bool(passed >= 5), "seconds": round(time.time() - t0)}
    res["pending_countries"] = pending
    res["validated_gate_passed"] = None if pending else res["validated_gate_passed"]
    (ROOT / sp.CFG["paths"]["outputs_dir"] / "p4b_nominal_validation.json").write_text(json.dumps(res, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    sp.log(f"validated gate: {passed} of {len(out)} ≥ +10%")


if __name__ == "__main__":
    main()
