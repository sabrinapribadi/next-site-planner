"""P6 inputs for one country (ADR-010), exported locally and uploaded to the Unity Catalog volume.

    python scripts/databricks_prepare_inputs.py IDN
    databricks fs cp -r --overwrite build/p6/IDN dbfs:/Volumes/workspace/geo1/inputs/IDN -p portfolio

Exports to build/p6/<ISO>/ (git-ignored):
- polygon.wkt         the exact simplified country polygon the local pipeline used for tile assignment
- kontur.parquet      the country's Kontur population on H3 resolution 8
- p1_local.json       the local P1 shares (parity reference)
- plan.csv            the checked site plan (scorer parity reference)
- scorer.json         the scorer's rule: lift rates θ, population rule, built-up threshold, local people lifted
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
from acquire_public_data import COUNTRIES, DATA, _countries, _duck  # noqa: E402


def main(k: str) -> None:
    out = ROOT / "build" / "p6" / k; out.mkdir(parents=True, exist_ok=True)
    c = _duck(); _countries(c)                                  # same simplification and clip as the local tile assignment
    wkt = c.sql(f"SELECT ST_AsText(geom) FROM ctry WHERE iso3 = '{k}'").fetchone()[0]
    (out / "polygon.wkt").write_text(wkt)
    c.sql(f"COPY (SELECT h3, population FROM '{DATA}/population/kontur_7_20231101.parquet' WHERE iso3 = '{k}') TO '{out / 'kontur.parquet'}' (FORMAT parquet)")
    p1 = json.loads((ROOT / "data/outputs/p1_experience_gap.json").read_text())
    (out / "p1_local.json").write_text(json.dumps({"quarter": p1["quarter"], "country": k, **{kk: v for kk, v in p1["countries"][k].items()
                                                    if kk in ("population", "measured_share") or (kk.startswith("below_") and kk.count("_") == 1)}}, indent=1))
    shutil.copy(ROOT / "docs/data/plans" / f"{k}.csv", out / "plan.csv")
    p4 = json.loads((ROOT / "data/outputs/p4_site_plan.json").read_text())
    v = p4["countries"][k]; hb = v["budgets"][str(v["headline_budget"])]
    (out / "scorer.json").write_text(json.dumps({"country": k, "theta_new": v["theta"]["new"][0], "theta_capacity": v["theta"]["capacity"][0],
                                                 "population_rule": p4.get("population"), "built_up_minimum_m2": p4.get("built_up_minimum_m2"),
                                                 "checked_on_ground": bool(v.get("validated")), "local_people_lifted": hb["people_lifted"]}, indent=1))
    print(k, "→", out, {f.name: f.stat().st_size for f in out.iterdir()}, "| clip:", COUNTRIES[k][3])


if __name__ == "__main__":
    os.environ.setdefault("GEO_DATA_DIR", str(DATA))
    main(sys.argv[1] if len(sys.argv) > 1 else "IDN")
