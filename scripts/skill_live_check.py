"""Live check for the agent skill (R24): the client reaches the deployed API and the facts the eval graders rely on still hold.

    python scripts/skill_live_check.py [--base URL]
If the data is refreshed and a fact changes, this fails so the graders in skills/next-site-planner/evals are updated, not left stale.
"""
import json
import subprocess
import sys
from pathlib import Path

CLIENT = Path(__file__).resolve().parents[1] / "skills/next-site-planner/scripts/nsp.py"
base = sys.argv[sys.argv.index("--base") + 1] if "--base" in sys.argv else "https://next-site-planner.vercel.app"


def call(*args):
    r = subprocess.run([sys.executable, str(CLIENT), "--base", base, *args], capture_output=True, text=True, timeout=180, check=False)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


gap = call("gap", "-6.2", "106.8")
assert gap["gap_type_25_mbps"] == "no gap" and gap["tests"] == 1027 and gap["typical_mbps"] == 89.3, gap
sites = call("sites", "PHL", "--k", "5")["sites"]
assert [s["rank"] for s in sites] == [1, 2, 3, 4, 5] and sites[0]["district"].startswith("Cotabato City") and round(sites[0]["expected_people_lifted"]) == 2155, sites[0]
note = call("note", "PHL", "1")
assert note["grader"]["ok"] and "2,155" in note["note"], note
cs = {c["country"]: c for c in call("countries")["countries"]}
assert max(cs, key=lambda k: cs[k]["plan_gain_vs_kpi"]) == "ARE" and round(cs["ARE"]["plan_gain_vs_kpi"], 2) == 2.81, cs["ARE"]
assert call("gap", "35.681", "139.767").get("out_of_scope") is True
print(f"skill live check passed against {base}")
