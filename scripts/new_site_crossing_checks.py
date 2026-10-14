"""ADR-007 amendment 3: regression-to-the-mean checks for the 'slow places lifted above 25 Mbps' measure.

    python scripts/new_site_crossing_checks.py

Outcome: share of hexagons whose mobile download is at or above 25 Mbps. Checks:
1. Slow by pre-period average: per first-treated group g, keep that group and its comparison places whose mean ln
   speed over quarters g-5..g-2 is below ln 25; combine groups with treated-count weights.
2. Within base-speed bands (< 10 and 10-25 Mbps at the base quarter), combined with treated-count weights.
3. Home-broadband control: the same measure on fixed broadband (should be about 0).
Combined intervals are treated-count-weighted averages of the parts' intervals (conservative).
Writes data/outputs/p3c_crossing_checks.json.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
import new_site_effect as ns  # noqa: E402
from src.did import event_study  # noqa: E402

L25, L10 = np.log(25), np.log(10)
above = lambda Y: np.where(np.isnan(Y), np.nan, (Y >= L25).astype(float))


def combine(parts: list[tuple[int, dict]]) -> dict:
    parts = [(n, p) for n, p in parts if p and n > 0]
    if not parts:
        return {}
    w = np.array([n for n, _ in parts], float)
    f = lambda key, i=None: float(np.sum(w * np.array([p[key] if i is None else p[key][i] for _, p in parts])) / w.sum())
    return {"att": f("att"), "ci95": [f("ci95", 0), f("ci95", 1)], "parts": len(parts)}


def post_n(r: dict) -> int:
    return sum(r["event_time"][e]["treated_obs"] for e in range(0, 5) if e in r.get("event_time", {}))


def main() -> None:
    t0 = time.time(); c = ns.connect(); out = {}
    for k in ns.CFG["countries"]:
        d = ns.build(k, c)
        if len(d["new_site"]) < ns.MIN_EVENTS:
            out[k] = "too few new-site events"; continue
        G = ns.G_for(d, d["new_site"]); m = ~np.isnan(G)
        Ym, Ya = d["Ym"], above(d["Ym"])
        r = {"original": ns.run(d, G, Ya, base_filter=lambda yb: yb == 0).get("post_avg_0_4")}
        # 1. slow by pre-period average, one group at a time
        parts = []
        for g in sorted(int(x) for x in np.unique(G[m & np.isfinite(G)])):
            lo, hi = max(g - 5, 0), g - 1
            if hi - lo < 1:
                continue
            with np.errstate(all="ignore"):
                pre = np.nanmean(Ym[:, lo:hi], axis=1)
            keep = m & ((G == g) | (G > g + 1)) & (pre < L25)
            Gg = np.where(G == g, g, np.inf)[keep]
            ev = event_study(Ya[keep], Gg, d["strat"][keep], d["block"][keep], range(0, 5), reps=ns.REPS, seed=9)
            parts.append((post_n(ev), ev.get("post_avg_0_4")))
        r["slow_by_preperiod_average"] = combine(parts)
        # 2. base-speed bands
        bands = {}
        for name, lo, hi in (("below_10", -np.inf, L10), ("10_to_25", L10, L25)):
            ev = event_study(Ya[m], G[m], d["strat"][m], d["block"][m], range(-5, 5), reps=ns.REPS, seed=9,
                             filter_Y=Ym[m], base_filter=lambda yb, lo=lo, hi=hi: (yb >= lo) & (yb < hi))
            bands[name] = (post_n(ev), ev.get("post_avg_0_4"), ev.get("pretrend"))
        r["bands"] = {b: {"post": v[1], "pretrend": v[2], "treated_obs": v[0]} for b, v in bands.items()}
        r["within_bands_combined"] = combine([(n, p) for n, p, _ in bands.values()])
        # 3. home broadband: same measure on fixed
        Yf = d["Yf"]
        r["fixed_control_crossing"] = event_study(above(Yf)[m], G[m], d["strat"][m], d["block"][m], range(-5, 5), reps=ns.REPS, seed=9,
                                                  filter_Y=Yf[m], base_filter=lambda yb: yb < L25).get("post_avg_0_4")
        o, a1, a2, fc = r["original"], r["slow_by_preperiod_average"], r["within_bands_combined"], r["fixed_control_crossing"]
        same = lambda x: bool(x) and o is not None and np.sign(x["att"]) == np.sign(o["att"])
        r["pass_for_p4"] = bool(same(a1) and same(a2) and (fc is None or fc["ci95"][0] <= 0 <= fc["ci95"][1]))
        r["p4_value"] = min([x for x in (o, a1, a2) if x], key=lambda x: x["att"]) if r["pass_for_p4"] else None
        out[k] = r
        ns.log(k, "orig", o and round(o["att"], 3), "| pre-avg", a1 and round(a1["att"], 3), "| bands", a2 and round(a2["att"], 3),
               "| fixed", fc and round(fc["att"], 3), fc and [round(x, 3) for x in fc["ci95"]], "| pass", r["pass_for_p4"])
        (ROOT / "data/outputs/p3c_crossing_checks.json").write_text(json.dumps(out, indent=1, default=str))
    ns.log("done in", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
