"""P3: did new sites raise speeds nearby? Staggered difference-in-differences in Germany and the US (ADR-007).

    python scripts/new_site_effect.py

All seven countries, same rule (ADR-007 amendment 1). Events: hexagons with a reliable new LTE/5G cell (OpenCelliD first seen 2023 Q3–2024 Q4, still seen >= 180 days
later). Type: new site (no cell of any kind in ring 0–1 before) or added capacity. Comparison places: never treated
(no cell of any kind first seen since 2023 Q1 within ring 3) or not yet treated. Outcome: ln mobile download per
hexagon-quarter. Writes data/outputs/p3_new_site_effect.json.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import h3
import numpy as np
import pandas as pd
import pyfixest as pf
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.did import event_study  # noqa: E402
from src.hexgrid import connect  # noqa: E402

CFG = yaml.safe_load((ROOT / "configs" / "default_config.yaml").read_text())
DATA = Path(os.environ.get("GEO_DATA_DIR", "~/data/geo")).expanduser()
DER = DATA / "derived"
Q0 = 2023 * 4            # 2023 Q1 = quarter index 0
WIN = (2023 * 4 + 2 - Q0, 2024 * 4 + 3 - Q0)   # event window 2023 Q3 .. 2024 Q4
T = 15
EVENTS = range(-5, 9)
REPS = 499
MAX_NEVER_REG = 50_000   # memory cap for the regression arms (the US has 1.5M never-treated hexagons)
MIN_EVENTS = 100     # ADR-007 amendment 1: report an estimand only with at least 100 event hexagons
MORPH = {"rural": 0, "urban_cluster": 1, "urban_centre": 2}
log = lambda *a: print(time.strftime("%H:%M:%S"), *a, flush=True)


def build(country: str, c) -> dict:
    cells = c.sql(f"""SELECT radio, h3_latlng_to_cell_string(lat, lon, 8) AS h3,
                      year(created_ts) * 4 + quarter(created_ts) - 1 - {Q0} AS cq, date_diff('day', created_ts, updated_ts) AS days
                      FROM '{DATA}/opencellid/cells_7.parquet' WHERE iso3 = '{country}'""").df()
    first_any = cells.groupby("h3").cq.min()
    rel = cells[(cells.cq >= WIN[0]) & (cells.cq <= WIN[1]) & (cells.days >= 180) & cells.radio.isin(["LTE", "NR"])]
    ev = rel.groupby("h3").cq.min()
    prior = pd.Series({h: min((first_any.get(g, 10 ** 6) for g in h3.grid_disk(h, 1))) for h in ev.index})
    new_site = ev[prior >= ev]; capacity = ev[prior < ev]
    touched = set()
    for h in cells.loc[cells.cq >= 0, "h3"].unique():
        touched.update(h3.grid_disk(h, 3))
    ring1 = {}
    for h, g in new_site.items():
        for n in h3.grid_ring(h, 1):
            if n not in ev.index:
                ring1[n] = min(g, ring1.get(n, 10 ** 6))
    ring1 = pd.Series(ring1)

    pan = c.sql(f"""SELECT h3, type, year * 4 + quarter - 1 - {Q0} AS t, ln(down_mbps) AS y, tests
                    FROM '{DER}/hex_speed_panel.parquet' WHERE iso3 = '{country}' AND year * 4 + quarter - 1 >= {Q0}""").df()
    morph = pd.read_parquet(DER / "hex_p1.parquet", columns=["iso3", "h3", "morphology"])
    morph = morph[morph.iso3 == country].set_index("h3").morphology.map(MORPH)
    units = pd.Index(sorted(set(pan.h3)))
    uidx = {h: i for i, h in enumerate(units)}

    def mat(kind: str):
        p = pan[pan.type == kind]
        Y = np.full((len(units), T), np.nan); N = np.zeros((len(units), T))
        r = p.h3.map(uidx).to_numpy(); t = p.t.to_numpy()
        Y[r, t] = p.y.to_numpy(); N[r, t] = p.tests.to_numpy()
        return Y, N
    Ym, Nm = mat("mobile"); Yf, _ = mat("fixed")
    never = np.array([h not in touched for h in units])
    strat = units.map(lambda h: morph.get(h, 0)).to_numpy()
    block = np.array([h3.cell_to_parent(h, 5) for h in units])
    log(country, f"units {len(units):,} · new-site hexagons {len(new_site):,} · capacity {len(capacity):,} · ring-1 {len(ring1):,} · never-treated {never.sum():,}")
    return {"units": units, "Ym": Ym, "Nm": Nm, "Yf": Yf, "never": never, "strat": strat, "block": block,
            "new_site": new_site, "capacity": capacity, "ring1": ring1}


def G_for(d: dict, treated: pd.Series) -> np.ndarray:
    """First-treated quarter per unit: the estimand's treated units get g, never-treated get inf, all others NaN (dropped)."""
    G = np.full(len(d["units"]), np.nan)
    G[d["never"]] = np.inf
    g = pd.Series(d["units"]).map(treated).to_numpy()
    G[~np.isnan(g)] = g[~np.isnan(g)]
    return G


def run(d: dict, G: np.ndarray, Y: np.ndarray, keep=None, **kw) -> dict:
    m = ~np.isnan(G) if keep is None else (~np.isnan(G) & keep)
    return event_study(Y[m], G[m], d["strat"][m], d["block"][m], EVENTS, reps=REPS, seed=7, **kw)


def regression_arms(d: dict, G: np.ndarray) -> dict:
    """Imputation (two-stage, Borusyak et al. / Gardner) and two-way fixed effects, new sites in ring 0.
    Memory: one dummy per hexagon, so never-treated hexagons are sampled (seeded) up to 20× the treated count;
    every treated and not-yet-treated hexagon is kept. The Callaway–Sant'Anna estimate uses all units."""
    m = ~np.isnan(G)
    nev = np.flatnonzero(m & np.isinf(G)); cap = min(20 * int((m & np.isfinite(G)).sum()), MAX_NEVER_REG)
    if len(nev) > cap:
        drop = np.random.default_rng(11).choice(nev, size=len(nev) - cap, replace=False)
        m = m.copy(); m[drop] = False
    U, Tt = np.nonzero(~np.isnan(d["Ym"][m]))
    gi = G[m][U]
    df = pd.DataFrame({"unit": U, "t": Tt, "y": d["Ym"][m][U, Tt], "strat_t": d["strat"][m][U] * 100 + Tt, "block": pd.factorize(d["block"][m][U])[0]})
    rel = np.where(np.isfinite(gi), Tt - gi, np.nan)
    df["treat"] = (np.nan_to_num(rel, nan=-99) >= -1).astype(int)
    names = []
    for e in EVENTS:
        if e == -2:
            continue
        col = f"e{e}".replace("-", "m"); names.append((e, col))
        df[col] = (rel == e).astype(float)
    df = df[~(np.isfinite(rel) & ((rel < EVENTS.start) | (rel >= EVENTS.stop)))]   # drop treated obs outside the window
    rhs = " + ".join(c for _, c in names)
    out = {}
    try:
        fit = pf.did2s(df, yname="y", first_stage="~ 0 | unit + strat_t", second_stage=f"~ {rhs}", treatment="treat", cluster="block")
        co, se = fit.coef(), fit.se()
        out["imputation"] = {e: {"att": float(co[c]), "ci95": [float(co[c] - 1.96 * se[c]), float(co[c] + 1.96 * se[c])]} for e, c in names if c in co}
    except Exception as ex:  # reported, not hidden
        out["imputation_error"] = str(ex)[:300]
    try:
        fit = pf.feols(f"y ~ {rhs} | unit + strat_t", data=df, vcov={"CRV1": "block"})
        co, se = fit.coef(), fit.se()
        out["twfe"] = {e: {"att": float(co[c]), "ci95": [float(co[c] - 1.96 * se[c]), float(co[c] + 1.96 * se[c])]} for e, c in names if c in co}
    except Exception as ex:
        out["twfe_error"] = str(ex)[:300]
    for k in ("imputation", "twfe"):
        if k in out:
            post = [out[k][e]["att"] for e in range(0, 5) if e in out[k]]
            out[f"{k}_post_avg_0_4"] = float(np.mean(post)) if post else None
    return out


def main() -> None:
    t0 = time.time(); c = connect()
    part = ROOT / CFG["paths"]["outputs_dir"] / "p3_partial.json"
    res = json.loads(part.read_text()) if part.exists() else {}      # resume: countries already finished are kept
    for k in CFG["countries"]:          # all seven countries, same rule (ADR-007 amendment 1)
        if k in res:
            log(k, "already done (resumed)"); continue
        d = build(k, c)
        Gn, Gc, G1 = G_for(d, d["new_site"]), G_for(d, d["capacity"]), G_for(d, d["ring1"])
        r = {"counts": {"new_site_hexagons": int(len(d["new_site"])), "capacity_hexagons": int(len(d["capacity"])),
                        "ring1_hexagons": int(len(d["ring1"])), "never_treated_units": int(d["never"].sum())}}
        enough_ns, enough_cap = len(d["new_site"]) >= MIN_EVENTS, len(d["capacity"]) >= MIN_EVENTS
        r["enough_events"] = {"new_site": enough_ns, "capacity": enough_cap}
        r["capacity_ring0"] = run(d, Gc, d["Ym"]) if enough_cap else "too few events"
        if not enough_ns:
            r["new_site_ring0"] = "too few events"; r["gate"] = {"passed": None, "reason": "too few new-site events"}
            res[k] = r; log(k, "too few new-site events"); continue
        r["new_site_ring0"] = run(d, Gn, d["Ym"]); log(k, "new site ring 0", r["new_site_ring0"].get("post_avg_0_4"), r["new_site_ring0"].get("pretrend"))
        r["new_site_ring1"] = run(d, G1, d["Ym"])
        r["negative_control_fixed"] = run(d, Gn, d["Yf"])
        # placebo timing: events moved 4 quarters earlier, only data before the real anticipation quarter
        Yp = d["Ym"].copy(); Gp = Gn.copy(); tr = np.isfinite(Gn) & ~np.isnan(Gn)
        cols = np.arange(T)[None, :]
        Yp[tr] = np.where(cols >= (Gn[tr][:, None] - 1), np.nan, Yp[tr]); Gp[tr] = Gn[tr] - 4
        r["placebo_timing"] = run(d, Gp, Yp)
        Yr = np.where(d["Nm"] >= 5, d["Ym"], np.nan)
        r["robust_5_tests"] = run(d, Gn, Yr)
        r["by_area_type"] = {m: run(d, Gn, d["Ym"], keep=d["strat"] == v) for m, v in MORPH.items()}
        Yc = np.where(np.isnan(d["Ym"]), np.nan, (d["Ym"] >= np.log(25)).astype(float))
        r["crossing_25_from_below"] = run(d, Gn, Yc, base_filter=lambda yb: yb == 0)
        d["Nm"] = d["Yf"] = None                                        # free memory before the regression arms
        r["regressions_new_site_ring0"] = regression_arms(d, Gn)
        nr = r["new_site_ring0"]
        r["gate"] = {"pretrend_all_ci_include_0": nr.get("pretrend", {}).get("all_ci_include_0"),
                     "pretrend_joint_p": nr.get("pretrend", {}).get("p_value"),
                     "passed": bool(nr.get("pretrend", {}).get("all_ci_include_0") and nr.get("pretrend", {}).get("p_value", 0) > 0.05)}
        res[k] = r
        log(k, "gate", r["gate"], "| neg. control", r["negative_control_fixed"].get("post_avg_0_4"), "| placebo", r["placebo_timing"].get("post_avg_0_4"))
        (ROOT / CFG["paths"]["outputs_dir"] / "p3_partial.json").write_text(json.dumps(res, default=str))   # survive a crash
    out = {"design": "ADR-007", "events_window": "2023Q3-2024Q4", "event_times": [EVENTS.start, EVENTS.stop - 1], "bootstrap_reps": REPS,
           "countries": res, "gate_passed": {k: v["gate"].get("passed") for k, v in res.items()}, "seconds": round(time.time() - t0)}
    (ROOT / CFG["paths"]["outputs_dir"] / "p3_new_site_effect.json").write_text(json.dumps(out, indent=1, default=lambda o: int(o) if isinstance(o, np.integer) else str(o)))
    log("done in", out["seconds"], "s")


if __name__ == "__main__":
    main()
