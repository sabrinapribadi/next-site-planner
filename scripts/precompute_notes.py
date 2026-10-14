"""Write and cache a grounded note for every nominal (ADR-009's pre-set cost lever), so planners get cached notes.

    python scripts/precompute_notes.py [--workers 8]

Uses the same NoteService as the API (model → grader → template), so every cached note is grounded.
Writes a summary to data/outputs/p5_notes_precompute.json (counts, sources, cost, latency).
"""

from __future__ import annotations

import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.serving.notes import facts_for  # noqa: E402
from src.serving.tools import Tools  # noqa: E402

log = lambda *a: print(time.strftime("%H:%M:%S"), *a, flush=True)


def main(workers: int = 8) -> None:
    t = Tools(); lock = threading.Lock(); recs = []
    rows = t.store.plans.to_dict("records")
    names = {k: v["name"] for k, v in t.store.countries["countries"].items()}

    def one(r):
        site = t._site(r)
        f = facts_for({kk: (None if isinstance(v, float) and v != v else v) for kk, v in r.items()}, names[r["iso3"]], site.checked_on_ground)
        note, source, g, meter, _ = t.notes.note(f)
        return {"source": source, "served_ok": g["served_ok"], "cached": meter.cached, "cost": meter.cost_usd, "ms": meter.latency_ms, "provider": meter.provider}

    t0 = time.time()
    with ThreadPoolExecutor(workers) as ex:
        futs = [ex.submit(one, r) for r in rows]
        for i, fu in enumerate(as_completed(futs), 1):
            with lock:
                recs.append(fu.result())
            if i % 1000 == 0 or i == len(rows):
                log(f"{i:,}/{len(rows):,} notes · ${sum(x['cost'] for x in recs):.3f}")
    t.notes.save()                                            # flush the cache
    live = [x for x in recs if x["provider"] == "openai"]
    res = {"design": "ADR-009 cost lever", "nominals": len(recs), "served_grounded": int(sum(x["served_ok"] for x in recs)),
           "from_model": int(sum(x["source"] == "model" for x in recs)), "from_template": int(sum(x["source"] == "template" for x in recs)),
           "already_cached": int(sum(x["cached"] for x in recs)), "live_calls": len(live), "cost_usd": round(sum(x["cost"] for x in recs), 4),
           "live_latency_ms": {"p50": float(np.percentile([x["ms"] for x in live], 50)), "p95": float(np.percentile([x["ms"] for x in live], 95))} if live else None,
           "seconds": round(time.time() - t0)}
    (ROOT / "data/outputs/p5_notes_precompute.json").write_text(json.dumps(res, indent=1))
    log(res)


if __name__ == "__main__":
    main(int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 8)
