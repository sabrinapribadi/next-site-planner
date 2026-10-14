"""The four planner tools (ADR-009): one registry shared by the REST API and the MCP server."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from src.serving.contracts import Countries, CountryRow, GapAt, OutOfScope, Site, SiteNote, TopSites
from src.serving.notes import NoteService, OpenAIWriter, facts_for
from src.serving.store import Store

ROOT = Path(__file__).resolve().parents[2]
CFG = yaml.safe_load((ROOT / "configs" / "default_config.yaml").read_text())
GAP_NAMES = {"none": "no gap", "capacity": "capacity gap", "coverage": "coverage gap", "slow_type_unknown": "slow, type unknown", "unmeasured": "not tested"}


def _num(v, cast=float):
    return None if v is None or (isinstance(v, float) and v != v) else cast(v)


class Tools:
    def __init__(self, store: Store | None = None, notes: NoteService | None = None):
        self.store = store or Store()
        if notes is None:
            c = CFG["notes"]
            writer = OpenAIWriter(model=c["model"], price_in=c["price_input_per_m"], price_cached_in=c["price_cached_input_per_m"],
                                  price_out=c["price_output_per_m"], max_output_tokens=c["max_output_tokens"],
                                  reasoning_effort=c["reasoning_effort"], timeout=c["timeout_s"]) if os.environ.get("OPENAI_API_KEY") else None
            notes = NoteService(writer, self.store.path / "notes_cache.json")
        self.notes = notes

    # ---- helpers
    def _countries(self) -> dict:
        return self.store.countries["countries"]

    def _site(self, r: dict) -> Site:
        r = {k: (None if isinstance(v, float) and v != v else v) for k, v in r.items()}
        checked = "site_lat" in r and r.get("site_lat") is not None
        return Site(rank=int(r["rank"]), h3=r["h3"], country=r["iso3"], district=r.get("district") or "", intervention=r["intervention"],
                    cost_new_tower_equivalents=float(r["cost"]), people=int(r["people"]),
                    people_kontur=_num(r.get("kontur_people"), int), people_worldpop=_num(r.get("worldpop_people"), int),
                    chance_below_25_mbps=float(r["p_below_25"]), expected_people_lifted=float(r["expected_lifted"]),
                    site_lat=float(r["site_lat"] if checked else r["lat"]), site_lon=float(r["site_lon"] if checked else r["lon"]),
                    built_up_m2=_num(r.get("built_m2"), int), elevation_m=_num(r.get("elevation_m"), int), slope_deg=_num(r.get("slope_deg")),
                    steep=None if r.get("steep") is None else bool(r["steep"]), high=None if r.get("high") is None else bool(r["high"]),
                    checked_on_ground=checked)

    # ---- tools
    def gap_at(self, lat: float, lon: float) -> GapAt | OutOfScope:
        """How slow is mobile at this point, and for how many people? Looks up the 0.74 km² hexagon containing (lat, lon)."""
        h = self.store.hexagon(lat, lon)
        if h is None:
            return OutOfScope(message="No populated hexagon with a speed estimate at this point in the seven countries covered.")
        nom = self.store.nominal_at(h["h3"])
        return GapAt(h3=h["h3"], country=h["iso3"], district=h["district"] or "", people_kontur=int(h["kontur_people"]),
                     people_worldpop=_num(h["worldpop_people"], int), tested=bool(h["tested"]), tests=int(h["tests"] or 0),
                     typical_mbps=float(h["typical_mbps"]), chance_below_10_mbps=float(h["p_below_10"]), chance_below_25_mbps=float(h["p_below_25"]),
                     area_type=h["morphology"], gap_type_25_mbps=GAP_NAMES.get(h["gap_type_25"], h["gap_type_25"] or "not typed"),
                     in_plan=None if nom is None else {"rank": int(nom["rank"]), "intervention": nom["intervention"]})

    def top_sites(self, country: str, k: int = 10) -> TopSites | OutOfScope:
        """The first k sites of a country's checked site plan (budget 1,000 new-tower equivalents), best first."""
        country = country.upper()
        if country not in self._countries():
            return OutOfScope(message=f"Countries covered: {', '.join(self._countries())}.")
        c = self._countries()[country]["plan"]; p = self.store.plan(country).head(max(1, min(int(k), 100)))
        return TopSites(country=country, budget_new_tower_equivalents=c["budget"], checked_on_ground=c["checked_on_ground"],
                        sites=[self._site(r) for r in p.to_dict("records")])

    def explain_site(self, country: str, rank: int) -> SiteNote | OutOfScope:
        """A short planner note on one nominal, grounded in its numbers (every number traced to the facts)."""
        country = country.upper()
        if country not in self._countries():
            return OutOfScope(message=f"Countries covered: {', '.join(self._countries())}.")
        r = self.store.nominal(country, int(rank))
        if r is None:
            return OutOfScope(message=f"{country}'s plan has no site ranked {rank}.")
        site = self._site(r)
        f = facts_for(r, self._countries()[country]["name"], site.checked_on_ground)
        note, source, g, meter, _ = self.notes.note(f)
        return SiteNote(site=site, note=note, source=source, grader=g, meter=meter)

    def compare_countries(self, bar_mbps: int = 25) -> Countries | OutOfScope:
        """Share and number of people below a speed bar in each country, and each country's site-plan result."""
        bars = self.store.countries["bars_mbps"]
        if int(bar_mbps) not in bars:
            return OutOfScope(message=f"Speed bars available: {', '.join(map(str, bars))} Mbps.")
        b = str(int(bar_mbps)); rows = []
        for k, c in self._countries().items():
            rows.append(CountryRow(country=k, name=c["name"], population_millions=c["population_m"], tested_share=c["tested_share"],
                                   share_below_bar_tested=c["below_tested"][b], share_below_bar_everyone=c["below_everyone"][b],
                                   people_below_bar_everyone_millions=round(c["below_everyone"][b] * c["population_m"], 2),
                                   untested_people_likely_below_bar_millions=c["untested_likely_below_m"][b],
                                   plan_people_lifted=c["plan"]["people_lifted"], plan_gain_vs_kpi=c["plan"]["gain_vs_kpi"],
                                   plan_checked_on_ground=c["plan"]["checked_on_ground"]))
        return Countries(bar_mbps=int(bar_mbps), quarter=self.store.countries["quarter"], countries=rows)


REGISTRY = ("gap_at", "top_sites", "explain_site", "compare_countries")
