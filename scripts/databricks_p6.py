"""P6 Databricks job tasks for one country (ADR-010). Run by the bundle (databricks.yml), one task per call:

    databricks_p6.py --task ingest_tiles|build_hexagons|p1_shares|register_scorer|monitor_drift|publish --country IDN

Mirrors the local pipeline: tiles assigned by tile centre inside the exact local polygon (acquire_public_data.ookla),
test-weighted mean of log speed per H3 r8 cell (hexgrid.speed_by_hex), people-weighted shares (experience_gap.shares).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

QUARTERS = [(y, q) for y in range(2023, 2027) for q in range(1, 5) if (y, q) <= (2026, 3)]
BARS = [5, 10, 25, 50, 100]
CAT, SCHEMA = "workspace", "geo1"


def paths(k: str) -> tuple[Path, Path]:
    i, o = Path(f"/Volumes/{CAT}/{SCHEMA}/inputs/{k}"), Path(f"/Volumes/{CAT}/{SCHEMA}/outputs/{k}")
    o.mkdir(parents=True, exist_ok=True)
    return i, o


def t(k: str, name: str) -> str:
    return f"{CAT}.{SCHEMA}.{k.lower()}_{name}"


def ingest_tiles(spark, k):
    i, _ = paths(k)
    wkt = (i / "polygon.wkt").read_text()
    spark.createDataFrame([(wkt,)], "wkt string").createOrReplaceTempView("poly_src")
    spark.sql("""CREATE OR REPLACE TEMP VIEW poly AS SELECT ST_GeomFromText(wkt) AS g, ST_XMin(ST_GeomFromText(wkt)) AS x0, ST_XMax(ST_GeomFromText(wkt)) AS x1,
                 ST_YMin(ST_GeomFromText(wkt)) AS y0, ST_YMax(ST_GeomFromText(wkt)) AS y1 FROM poly_src""")
    srcs = [f"s3://ookla-open-data/parquet/performance/type=mobile/year={y}/quarter={q}/" for y, q in QUARTERS]
    tiles = None
    for (y, q), s in zip(QUARTERS, srcs):
        d = spark.read.parquet(s).select("tile_x", "tile_y", "avg_d_kbps", "tests").withColumn("year", F.lit(y)).withColumn("quarter", F.lit(q))
        tiles = d if tiles is None else tiles.unionByName(d)
    tiles.createOrReplaceTempView("tiles")
    out = spark.sql("""SELECT t.* FROM tiles t CROSS JOIN poly p
                       WHERE t.tile_x BETWEEN p.x0 AND p.x1 AND t.tile_y BETWEEN p.y0 AND p.y1 AND ST_Contains(p.g, ST_Point(t.tile_x, t.tile_y))""")
    out.write.mode("overwrite").saveAsTable(t(k, "tiles"))
    print("tiles kept:", spark.table(t(k, "tiles")).count())


def build_hexagons(spark, k):
    i, _ = paths(k)
    hx = (spark.table(t(k, "tiles")).where("tests > 0")
          .withColumn("h3", F.expr("h3_longlatash3string(tile_x, tile_y, 8)"))
          .groupBy("h3", "year", "quarter")
          .agg(F.sum("tests").alias("tests"),
               (F.exp(F.sum(F.col("tests") * F.log(F.greatest(F.col("avg_d_kbps"), F.lit(1.0)))) / F.sum("tests")) / 1000.0).alias("down_mbps")))
    hx.write.mode("overwrite").saveAsTable(t(k, "hex_panel"))
    spark.read.parquet(str(i / "kontur.parquet")).write.mode("overwrite").saveAsTable(t(k, "population"))
    print("hexagon-quarters:", spark.table(t(k, "hex_panel")).count())


def latest(spark, k, y=2026, q=3):
    mob = spark.table(t(k, "hex_panel")).where(f"year = {y} AND quarter = {q}").select("h3", "down_mbps", "tests")
    return spark.table(t(k, "population")).join(mob, "h3", "full_outer").withColumn("population", F.coalesce("population", F.lit(0.0)))


def p1_shares(spark, k):
    i, o = paths(k)
    h = latest(spark, k); h.write.mode("overwrite").saveAsTable(t(k, "hex_latest"))
    m = F.col("down_mbps").isNotNull()
    aggs = [F.sum("population").alias("pop"), F.sum(F.when(m, F.col("population")).otherwise(0.0)).alias("pm")]
    aggs += [F.sum(F.when(m & (F.col("down_mbps") < b), F.col("population")).otherwise(0.0)).alias(f"b{b}") for b in BARS]
    r = spark.table(t(k, "hex_latest")).agg(*aggs).collect()[0]
    got = {"population": r["pop"], "measured_share": r["pm"] / r["pop"], **{f"below_{b}": r[f"b{b}"] / r["pm"] for b in BARS}}
    ref = json.loads((i / "p1_local.json").read_text())
    keys = ["measured_share"] + [f"below_{b}" for b in BARS]
    diff = {kk: abs(got[kk] - ref[kk]) for kk in keys}
    same = {kk: round(100 * got[kk], 1) == round(100 * ref[kk], 1) for kk in keys}
    res = {"country": k, "quarter": ref["quarter"], "databricks": got, "local": {kk: ref[kk] for kk in ["population"] + keys},
           "max_abs_difference": max(diff.values()), "population_difference": got["population"] - ref["population"],
           "equal_at_reported_decimal": same, "gate_p1_parity": all(same.values())}
    (o / "p1_parity.json").write_text(json.dumps(res, indent=1))
    spark.createDataFrame([{**{kk: float(v) for kk, v in got.items()}, "country": k}]).write.mode("overwrite").saveAsTable(t(k, "p1_shares"))
    print(json.dumps(res, indent=1))


def register_scorer(spark, k):
    import mlflow
    import pandas as pd
    from mlflow.models import infer_signature
    i, o = paths(k)
    cfg = json.loads((i / "scorer.json").read_text())

    class SiteScorer(mlflow.pyfunc.PythonModel):
        """Expected people lifted above 25 Mbps = people (smaller of two maps) × chance below 25 Mbps × lift rate θ (ADR-008)."""

        def __init__(self, theta_new: float, theta_capacity: float):
            self.theta_new, self.theta_capacity = theta_new, theta_capacity

        def predict(self, context, model_input, params=None):
            th = model_input["intervention"].map(lambda x: self.theta_capacity if x == "capacity" else self.theta_new)
            return model_input["people"].astype(float) * model_input["p_below_25"].astype(float) * th.astype(float)

    plan = pd.read_csv(i / "plan.csv")
    x = plan[["people", "p_below_25", "intervention"]]
    model = SiteScorer(cfg["theta_new"], cfg["theta_capacity"])
    name = f"{CAT}.{SCHEMA}.{k.lower()}_site_scorer"
    mlflow.set_tracking_uri("databricks"); mlflow.set_registry_uri("databricks-uc")
    user = spark.sql("SELECT current_user() AS u").collect()[0]["u"]
    mlflow.set_experiment(f"/Users/{user}/geo1-p6")             # experiment under the running user's workspace folder
    with mlflow.start_run(run_name=f"{k} site scorer") as run:
        mlflow.log_params({kk: v for kk, v in cfg.items() if kk != "local_people_lifted"})
        info = mlflow.pyfunc.log_model(name="scorer", python_model=model, input_example=x.head(3),
                                       signature=infer_signature(x, model.predict(None, x)), registered_model_name=name)
    client = mlflow.MlflowClient()
    version = info.registered_model_version
    client.set_registered_model_alias(name, "champion", version)
    loaded = mlflow.pyfunc.load_model(f"models:/{name}@champion")
    total = float(loaded.predict(x).sum())
    rel = abs(total - cfg["local_people_lifted"]) / cfg["local_people_lifted"]
    res = {"model": name, "version": int(version), "alias": "champion", "people_lifted": total, "local_people_lifted": cfg["local_people_lifted"],
           "relative_difference": rel, "gate_scorer_parity": rel <= 0.001, "run_id": run.info.run_id}
    (o / "scorer_parity.json").write_text(json.dumps(res, indent=1))
    spark.createDataFrame(plan.assign(scored_people_lifted=loaded.predict(x).astype(float))).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(t(k, "plan"))
    print(json.dumps(res, indent=1))


def monitor_drift(spark, k):
    _, o = paths(k)
    edges = [0, 5, 10, 25, 50, 100, 1e9]

    def dist(y, q):
        h = latest(spark, k, y, q).where("down_mbps IS NOT NULL")
        rows = h.select("population", "down_mbps").collect()
        w = [0.0] * (len(edges) - 1)
        for r in rows:
            for j in range(len(edges) - 1):
                if edges[j] <= r["down_mbps"] < edges[j + 1]:
                    w[j] += r["population"]; break
        s = sum(w)
        return [max(v / s, 1e-6) for v in w], s
    cur, _ = dist(2026, 3); prev, _ = dist(2026, 2)
    psi = sum((a - b) * math.log(a / b) for a, b in zip(cur, prev))
    res = {"country": k, "compare": "2026Q3 vs 2026Q2", "bins_mbps": edges[1:-1], "share_by_bin_current": cur, "share_by_bin_previous": prev,
           "psi": psi, "drift_flag_psi_gt_0_2": psi > 0.2,
           "share_below_25_change_pts": 100 * (sum(cur[:3]) - sum(prev[:3]))}
    (o / "drift.json").write_text(json.dumps(res, indent=1))
    spark.createDataFrame([{"country": k, "psi": float(psi), "flag": bool(psi > 0.2), "share_below_25_change_pts": float(res["share_below_25_change_pts"])}]).write.mode("overwrite").saveAsTable(t(k, "drift"))
    print(json.dumps(res, indent=1))


def publish(spark, k):
    _, o = paths(k)
    out = {}
    for f in ("p1_parity", "scorer_parity", "drift"):
        p = o / f"{f}.json"
        out[f] = json.loads(p.read_text()) if p.exists() else None
    out["tables"] = [t(k, n) for n in ("tiles", "hex_panel", "hex_latest", "p1_shares", "plan", "drift")]
    out["gate_passed"] = bool(out["p1_parity"] and out["p1_parity"]["gate_p1_parity"] and out["scorer_parity"] and out["scorer_parity"]["gate_scorer_parity"] and out["drift"])
    (o / "p6_result.json").write_text(json.dumps(out, indent=1))
    print("P6 gate passed:", out["gate_passed"])


if __name__ == "__main__":
    a = argparse.ArgumentParser(); a.add_argument("--task", required=True); a.add_argument("--country", default="IDN")
    args = a.parse_args()
    spark = SparkSession.builder.getOrCreate()
    globals()[args.task](spark, args.country.upper())
