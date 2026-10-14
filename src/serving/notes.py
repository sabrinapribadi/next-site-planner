"""Grounded site notes (ADR-009, rule R13): facts → language model → deterministic grader → template fallback.

Every number in a served note must come from the facts (rounding allowed). A note that fails the grader, a timeout or a
missing key falls back to a template built only from the facts, so every served note is grounded. Each call is metered
(tokens, latency, cost) and notes are cached by a hash of their facts.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from src.serving.contracts import Meter

PROMPT_VERSION = "v2"   # v1 → v2 (ADR-009 pre-set remedies after run 1): required-fact checklist, shorter note, fewer facts
MAX_WORDS = 70
SYSTEM = """You write a note of at most 45 words for a mobile network planner about one candidate site (a "nominal").
Use only the facts. Every number you write must appear in the facts; you may round it, never compute a new one.
Always include, in this order:
1. the intervention (new macro site, new small cell, or extra capacity);
2. the number of people in the search area;
3. the chance they are below 25 Mbps, written as a percentage;
4. the number who could be lifted above 25 Mbps;
5. the ground check: buildings in m², elevation and slope, and any steep or high flag; if checked_on_ground is false, write "not yet checked on the ground".
One plain paragraph. No promises. No operator or equipment-vendor names."""
NAMES = ("telkomsel", "smartfren", "xl axiata", "globe", "smart communications", "dito", "maxis", "celcom",
         "digi", "u mobile", "deutsche telekom", "vodafone", "telefonica", "o2", "orange", "sfr", "bouygues", "free mobile", "verizon",
         "at&t", "t-mobile", "etisalat", "du", "ericsson", "nokia", "huawei", "zte", "samsung")
NAME_RE = re.compile(r"(?<![\w&-])(" + "|".join(re.escape(n) for n in NAMES) + r")(?![\w&-])", re.I)
PROMISE = re.compile(r"\b(will|guarantee[ds]?|certainly|definitely)\b", re.I)
NUM = re.compile(r"(?<![\w.#])([-−])?#?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?\s*(%|[kK]\b|M\b)?")   # a minus only after a space: "5-10" is a range
INTERVENTION = {"macro": "a new macro site", "small_cell": "a new small cell", "capacity": "extra capacity on an existing site"}


# ------------------------------------------------------------------ facts and template
def facts_for(site: dict, country_name: str, checked: bool) -> dict:
    f = {"rank": int(site["rank"]), "country": country_name, "district": site.get("district") or "", "intervention": site["intervention"],
         "people": int(site["people"]), "chance_below_25_mbps": site["p_below_25"], "expected_people_lifted": round(site["expected_lifted"]),
         "bar_mbps": 25, "checked_on_ground": checked}
    if checked:
        i = lambda v: None if v is None else int(round(v))
        f.update({"people_kontur": i(site.get("kontur_people")), "people_worldpop": i(site.get("worldpop_people")), "built_up_m2": i(site.get("built_m2")),
                  "elevation_m": i(site.get("elevation_m")), "slope_deg": site.get("slope_deg"), "steep": bool(site.get("steep")), "high": bool(site.get("high"))})
    return f


def _pct(x: float) -> str:
    v = 100 * x
    return f"{v:.1f}" if 0 < v < 9.95 else f"{round(v)}"             # two significant figures for small shares


def template_note(f: dict) -> str:
    s = (f"#{f['rank']} in the {f['country']} plan ({f['district']}): {INTERVENTION.get(f['intervention'], f['intervention'])}. "
         f"{f['people']:,} people live in this search area; {_pct(f['chance_below_25_mbps'])}% are likely below 25 Mbps, "
         f"so about {f['expected_people_lifted']:,} could be lifted above it.")
    if not f["checked_on_ground"]:
        return s + " Not yet checked on the ground."
    g = f" Ground check: {f['built_up_m2']:,} m² of buildings"
    if f.get("elevation_m") is not None:
        g += f" at {f['elevation_m']:,} m, slope {f['slope_deg']}°"
    flags = [w for w, on in (("steep", f.get("steep")), ("high", f.get("high"))) if on]
    return s + g + (f"; {' and '.join(flags)}, so check access." if flags else ".")


# ------------------------------------------------------------------ grader
def _numbers(x, out: list[float]) -> None:
    if isinstance(x, bool) or x is None:
        return
    if isinstance(x, (int, float)):
        if not (isinstance(x, float) and math.isnan(x)):
            out.append(float(x))
    elif isinstance(x, dict):
        for v in x.values():
            _numbers(v, out)
    elif isinstance(x, str):
        for m in NUM.finditer(x):
            out.append(_val(m))


def _val(m: re.Match) -> float:
    v = float(m.group(2).replace(",", "") + (f".{m.group(3)}" if m.group(3) else ""))
    v = -v if m.group(1) else v                                  # e.g. elevation -1 m (below sea level)
    return v * 1e3 if (m.group(4) or "").lower() == "k" else v * 1e6 if m.group(4) == "M" else v


def _matches(n: float, facts: list[float]) -> bool:
    for f in facts:
        for cand in (f, 100 * f) if 0 <= f <= 1 else (f,):
            if abs(cand - n) <= 1e-9 * max(1.0, abs(n)):
                return True
            if cand == 0:
                continue
            lo = 1 - math.floor(math.log10(abs(cand)))       # rounding must keep at least two significant figures
            for p in range(lo, 4):                           # e.g. 2,161 → 2,200 (not 2,000); 0.523 → 0.52; 66 stays 66
                if abs(round(cand, p) - n) <= 1e-9 * max(1.0, abs(n)):
                    return True
    return False


def grade(note: str, facts: dict) -> dict:
    known: list[float] = []; _numbers(facts, known)
    found = [(m.group(0), _val(m)) for m in NUM.finditer(note)]
    unknown = [s for s, v in found if not _matches(v, known)]
    given = " ".join(str(v) for v in facts.values() if isinstance(v, str)).lower()     # e.g. district "Orange, Vermont"
    names = sorted({m.group(1).lower() for m in NAME_RE.finditer(note)} - {m.group(1).lower() for m in NAME_RE.finditer(given)})
    words = len(note.split())
    ok = not unknown and not names and not PROMISE.search(note) and 0 < words <= MAX_WORDS
    return {"ok": ok, "unknown_numbers": unknown, "names": names, "promise": bool(PROMISE.search(note)), "words": words}


def coverage(note: str, f: dict) -> dict:
    """Required facts mentioned (ADR-009): intervention, people, chance below 25 Mbps, ground check."""
    low = note.lower(); nums = [_val(m) for m in NUM.finditer(note)]
    has = lambda x: any(_matches(n, [x]) for n in nums)
    word = {"macro": "macro", "small_cell": "small cell", "capacity": "capacity"}[f["intervention"]]
    low = low.replace("small-cell", "small cell")
    ground = ("not yet checked" in low or "not checked" in low) if not f["checked_on_ground"] else ("building" in low or "m²" in note or "m2" in low)
    c = {"intervention": word in low, "people": has(f["people"]), "chance_below": has(f["chance_below_25_mbps"]), "ground_check": ground}
    return {**c, "all": all(c.values())}


# ------------------------------------------------------------------ providers
@dataclass
class OpenAIWriter:
    model: str
    price_in: float
    price_cached_in: float
    price_out: float
    max_output_tokens: int = 200
    reasoning_effort: str | None = "none"
    timeout: float = 10.0
    _client: object | None = field(default=None, repr=False)

    def write(self, facts: dict) -> tuple[str, Meter]:
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(timeout=self.timeout)
        extra = {"reasoning": {"effort": self.reasoning_effort}} if self.reasoning_effort else {}
        t0 = time.perf_counter()
        r = self._client.responses.create(model=self.model, instructions=SYSTEM, input="Facts (JSON):\n" + json.dumps(facts, ensure_ascii=False),
                                          max_output_tokens=self.max_output_tokens, **extra)
        ms = (time.perf_counter() - t0) * 1000
        u = getattr(r, "usage", None); it = int(getattr(u, "input_tokens", 0) or 0); ot = int(getattr(u, "output_tokens", 0) or 0)
        ct = int(getattr(getattr(u, "input_tokens_details", None), "cached_tokens", 0) or 0)
        cost = ((it - ct) * self.price_in + ct * self.price_cached_in + ot * self.price_out) / 1e6
        return (getattr(r, "output_text", "") or "").strip(), Meter(provider="openai", model=self.model, input_tokens=it, cached_input_tokens=ct,
                                                                     output_tokens=ot, latency_ms=round(ms, 1), cost_usd=round(cost, 8))


class NoteService:
    """Cache → model → grader → template. `writer=None` (no key) serves templates only."""

    def __init__(self, writer: OpenAIWriter | None, cache_path: Path | None = None, save_every: int = 50):
        import threading
        self.writer, self.cache_path, self.save_every = writer, cache_path, save_every
        self.cache = json.loads(cache_path.read_text()) if cache_path and cache_path.exists() else {}
        self._lock, self._unsaved = threading.Lock(), 0

    def save(self) -> None:
        """Atomic, thread-safe write of the cache (temporary file, then rename)."""
        if not self.cache_path:
            return
        with self._lock:
            snapshot = json.dumps(self.cache)
            self._unsaved = 0
        tmp = self.cache_path.with_suffix(".tmp")
        tmp.write_text(snapshot); os.replace(tmp, self.cache_path)

    def key(self, facts: dict) -> str:
        model = self.writer.model if self.writer else "template"
        return hashlib.sha256(json.dumps([PROMPT_VERSION, model, facts], sort_keys=True, default=str).encode()).hexdigest()[:24]

    def note(self, facts: dict, use_cache: bool = True) -> tuple[str, str, dict, Meter, str | None]:
        """Returns (served note, source, grader result, meter, raw model text)."""
        k = self.key(facts); t0 = time.perf_counter()
        if use_cache and k in self.cache:
            c = self.cache[k]
            g = c["grader"] if "served_ok" in c["grader"] else {**c["grader"], "served_ok": grade(c["note"], facts)["ok"]}   # older entries
            return c["note"], c["source"], g, Meter(provider="cache", model=c["model"], latency_ms=round((time.perf_counter() - t0) * 1000, 3), cached=True), c.get("raw")
        raw, meter = None, Meter(provider="template", model="template-v1")
        if self.writer is not None and os.environ.get("OPENAI_API_KEY"):
            try:
                raw, meter = self.writer.write(facts)
            except Exception as e:                           # noqa: BLE001 — timeout or API error: template
                meter = Meter(provider="openai-error", model=self.writer.model, latency_ms=round((time.perf_counter() - t0) * 1000, 1))
                raw = None
        g = grade(raw, facts) if raw else {"ok": False, "unknown_numbers": [], "names": [], "promise": False, "words": 0}
        note, source = (raw, "model") if raw and g["ok"] else (template_note(facts), "template")
        served = grade(note, facts)
        with self._lock:
            self.cache[k] = {"note": note, "source": source, "grader": {**g, "served_ok": served["ok"]}, "model": meter.model, "raw": raw,
                             "cost_usd": meter.cost_usd, "latency_ms": meter.latency_ms}
            self._unsaved += 1
            due = self._unsaved >= self.save_every
        if due:
            self.save()
        return note, source, {**g, "served_ok": served["ok"]}, meter, raw
