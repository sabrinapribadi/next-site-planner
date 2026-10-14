"""Typed requests and answers for the planner tools (ADR-009). Units are in the field names."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Meter(BaseModel):
    provider: str
    model: str
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    cached: bool = False


class OutOfScope(BaseModel):
    out_of_scope: bool = True
    message: str


class GapAt(BaseModel):
    """One 0.74 km² hexagon: how slow it is and for how many people."""
    h3: str
    country: str
    district: str
    people_kontur: int
    people_worldpop: int | None = Field(None, description="None while the country's WorldPop file is pending")
    tested: bool
    tests: int
    typical_mbps: float
    chance_below_10_mbps: float
    chance_below_25_mbps: float
    area_type: str
    gap_type_25_mbps: str
    in_plan: dict | None = Field(None, description="The nominal at this hexagon, if the plan chose it")


class Site(BaseModel):
    rank: int
    h3: str
    country: str
    district: str
    intervention: str
    cost_new_tower_equivalents: float
    people: int
    people_kontur: int | None = None
    people_worldpop: int | None = None
    chance_below_25_mbps: float
    expected_people_lifted: float
    site_lat: float
    site_lon: float
    built_up_m2: int | None = None
    elevation_m: int | None = None
    slope_deg: float | None = None
    steep: bool | None = None
    high: bool | None = None
    checked_on_ground: bool


class TopSites(BaseModel):
    country: str
    budget_new_tower_equivalents: float
    checked_on_ground: bool
    sites: list[Site]


class SiteNote(BaseModel):
    site: Site
    note: str
    source: str = Field(description="'model' when the language model's note passed the grader, else 'template'")
    grader: dict
    meter: Meter


class CountryRow(BaseModel):
    country: str
    name: str
    population_millions: float
    tested_share: float
    share_below_bar_tested: float
    share_below_bar_everyone: float
    people_below_bar_everyone_millions: float
    untested_people_likely_below_bar_millions: float
    plan_people_lifted: int
    plan_gain_vs_kpi: float | None
    plan_checked_on_ground: bool


class Countries(BaseModel):
    bar_mbps: int
    quarter: str
    countries: list[CountryRow]
