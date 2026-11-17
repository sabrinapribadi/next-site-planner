"""Streamlit companion app (R26): the plan on a map, a budget what-if, a place check with its neighbours, countries at your speed bar.

Only what the static results page cannot do; numbers come from the public API or the committed plan results (data/outputs).
Run: streamlit run app/streamlit_app.py   (theme in .streamlit/config.toml at the repository root)
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nsp_data as D  # sibling module; the app runs from the repo root on Streamlit Cloud

st.set_page_config(page_title="Next site planner", layout="wide", initial_sidebar_state="expanded")
dark = getattr(getattr(st.context, "theme", None), "type", "light") == "dark"
INK = "#a3a6b8" if dark else "#5d6074"
C = {"plan": "#4d94e8" if dark else "#2a78d6", "kpi": "#d95926" if dark else "#eb6834", "slow": "#199e70" if dark else "#1baf7a"}

st.html("""<style>
.eyebrow{font-size:.76rem;letter-spacing:.1em;text-transform:uppercase;font-weight:600;opacity:.65;margin:0}
.hero-title{font-family:Archivo,'IBM Plex Sans',system-ui,sans-serif;font-size:clamp(2rem,4.4vw,3.1rem);font-weight:800;line-height:1.02;margin:.2rem 0 .45rem;letter-spacing:-.01em}
.hero-sub{font-size:1.02rem;opacity:.8;max-width:70ch;margin:0 0 .4rem}
.brief-w{font-size:.68rem;letter-spacing:.08em;text-transform:uppercase;font-weight:700;color:#a99ff5;margin-bottom:.2rem}
.brief-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:8px;margin:.2rem 0 .3rem}
.bcard{border:1px solid #2b2c3c;border-radius:10px;padding:8px 12px;font-size:.86rem;line-height:1.4;background:#12131d}
.bcard a{color:#a99ff5}
.legend{display:flex;flex-wrap:wrap;gap:.35rem 1rem;font-size:.85rem;align-items:center;margin:.2rem 0 .4rem}
.legend span{display:inline-flex;align-items:center;gap:.35rem}
.sw{width:.85rem;height:.85rem;border-radius:3px;display:inline-block;border:1px solid rgba(127,127,127,.35)}
.dot{width:.75rem;height:.75rem;border-radius:50%;display:inline-block;border:1.5px solid #fff;box-shadow:0 0 0 1px rgba(0,0,0,.25)}
.note{border-left:3px solid #8f81f0;padding:.6rem .9rem;border-radius:0 .5rem .5rem 0;background:rgba(143,129,240,.12);line-height:1.5}
</style>""")


@st.cache_data(ttl=3600, show_spinner=False)
def api(path: str, **params) -> dict:
    return D.get(path, params or None)


@st.cache_data
def plan_results() -> dict:
    return D.load_plan()


def safe(path: str, **params) -> dict | None:
    try:
        return api(path, **params)
    except D.ApiError as err:
        st.warning(f"The live API did not answer ({err}). It may be waking up or paused on the free tier; try again in a minute, "
                   f"or read the [results page]({D.PAGES}), which is always on.")
        return None


def zoom_for(lats: list[float], lons: list[float]) -> float:
    span = max(max(lats) - min(lats), (max(lons) - min(lons)) * 0.8, 0.02)
    return max(3.0, min(13.0, math.log2(360 / span) - 1.2))


def legend_ramp() -> str:
    cells = "".join(f'<span><i class="sw" style="background:{c}"></i>{lo}–{min(hi, 1.0):.0%}</span>'
                    for (lo, (hi, c)) in zip(["0", "20%", "40%", "60%", "80%"], D.RAMP))
    return f'<div class="legend"><b>Chance below 25 Mbps</b>{cells}</div>'


def legend_markers(kinds: list[str]) -> str:
    return '<div class="legend"><b>Build type</b>' + "".join(
        f'<span><i class="dot" style="background:{D.MARKER[k]}"></i>{D.INTERVENTION[k]}</span>' for k in kinds) + "</div>"


# Sidebar: country and shortlist controls, shared by the map and budget tabs
with st.sidebar:
    st.subheader("Country and shortlist")
    country = st.selectbox("Country", list(D.COUNTRIES), format_func=D.COUNTRIES.get, key="country")
    k = st.slider("Top sites to show", 10, 100, 50, 10, key="k", help="The API serves the first 100 ranked sites of each plan.")
    kinds = st.multiselect("Build types", list(D.INTERVENTION), list(D.INTERVENTION), format_func=D.INTERVENTION.get, key="kinds")
    st.divider()
    st.caption("Free Streamlit Community Cloud app: it sleeps after 12 hours without visits; the first visit wakes it (up to a minute). "
               "The live API may take a few seconds on its first call.")
    st.caption("Speed data: Speedtest by Ookla open data (CC BY-NC-SA 4.0); population: Kontur and WorldPop (CC BY 4.0); "
               "land cover: ESA WorldCover; elevation: Copernicus DEM. Non-commercial use.")

# 1. Hero, KPI strip and the brief (R22, R26): the first screen is what LinkedIn's preview captures
hl = D.headline(plan_results())
st.html("""<p class="eyebrow">Ookla open speed tests · 7 countries · 6.4M populated hexagons of 0.74 km²</p>
<h1 class="hero-title">Next site planner</h1>
<p class="hero-sub">Where one more mobile site lifts the most people above 25 Mbps for the budget, checked on the ground.</p>""")
kp = st.columns(4)
kp[0].metric("People lifted above 25 Mbps", f"{hl['people_plan']:,.0f}", f"KPI ranking: {hl['people_kpi']:,.0f}", delta_color="off", delta_arrow="off", border=True)
kp[1].metric("Plan vs KPI ranking", f"{hl['times_min']:.1f}–{hl['times_max']:.1f}×", "same budget, by country", delta_color="off", delta_arrow="off", border=True)
kp[2].metric("Sites in the plans", f"{hl['sites']:,}", "each checked on the ground", delta_color="off", delta_arrow="off", border=True)
kp[3].metric("Countries", f"{hl['countries']}", "Asia, Europe, US, Gulf", delta_color="off", delta_arrow="off", border=True)
items = D.brief()
st.html('<div class="brief-grid">' + "".join(f'<div class="bcard"><div class="brief-w">{w}</div><div>{D.md_html(lines[0])}</div></div>' for w, lines in items) + "</div>")
with st.expander("Full brief"):
    for w, lines in items:
        st.markdown(f"**{w}:** " + " ".join(lines))
st.caption(f"[Results page]({D.PAGES}) · [Technical walkthrough]({D.PAGES}build.html) · [Live API]({D.API}/docs) · [Source]({D.REPO}) · "
           f"Free Streamlit app: it sleeps after 12 hours without visits; the [results page]({D.PAGES}) is always on and carries every result.")

map_tab, budget_tab, place_tab, bar_tab, agent_tab = st.tabs(["Plan on a map", "Budget what-if", "Check a place",
                                                              "Countries at your speed bar", "Ask the agent"],
                                                  key="view", on_change="rerun")   # lazy: only the open tab runs (and calls the API)

# 2. The plan's shortlist on a map
with map_tab:
    if map_tab.open:
        res = safe(f"/sites/{country}", k=k)
        if res and res.get("sites"):
            df = pd.DataFrame(res["sites"])
            df = df[df["intervention"].isin(kinds)].copy()
            if df.empty:
                st.info("No site of these build types in the shortlist; add a build type in the sidebar.")
            else:
                df["fill"] = df["chance_below_25_mbps"].map(lambda p: D.hex_rgb(D.ramp(p), 170))
                df["marker"] = df["intervention"].map(lambda t: D.hex_rgb(D.MARKER[t]))
                df["build"] = df["intervention"].map(D.INTERVENTION)
                df["chance"] = df["chance_below_25_mbps"].map(lambda p: f"{p:.0%}")
                df["lifted"] = df["expected_people_lifted"].map(lambda v: f"{v:,.0f}")
                df["ppl"] = df["people"].map(lambda v: f"{v:,}")
                st.subheader(f"{D.COUNTRIES[country]}: the first {len(df)} sites lift about {df['expected_people_lifted'].sum():,.0f} people "
                             f"above 25 Mbps for {df['cost_new_tower_equivalents'].sum():,.1f} tower-equivalents")
                m = st.columns(4)
                m[0].metric("Sites shown", f"{len(df)}", f"of the first {k} ranked", delta_color="off", delta_arrow="off", border=True)
                m[1].metric("People likely lifted", f"{df['expected_people_lifted'].sum():,.0f}", "expected, above 25 Mbps", delta_color="off", delta_arrow="off", border=True)
                m[2].metric("Budget used", f"{df['cost_new_tower_equivalents'].sum():,.1f}", "new-tower equivalents", delta_color="off", delta_arrow="off", border=True)
                m[3].metric("Checked on the ground", "all" if bool(df["checked_on_ground"].all()) else "some", "buildings, slope, elevation",
                            delta_color="off", delta_arrow="off", border=True)

                options = ["Whole shortlist"] + [f"#{r.rank} · {r.district} · {D.INTERVENTION[r.intervention]}" for r in df.itertuples()]
                focus = st.selectbox("Focus on a site (or click a marker)", options, key="focus")
                sel = None if focus in (None, "Whole shortlist") else int(focus.split(" ")[0][1:])
                if sel is not None:
                    row = df[df["rank"] == sel].iloc[0]
                    view = pdk.ViewState(latitude=row["site_lat"], longitude=row["site_lon"], zoom=13.2, pitch=0)
                else:
                    view = pdk.ViewState(latitude=df["site_lat"].mean(), longitude=df["site_lon"].mean(),
                                         zoom=zoom_for(df["site_lat"].tolist(), df["site_lon"].tolist()), pitch=0)
                hexes = pdk.Layer("H3HexagonLayer", data=df, id="hexes", get_hexagon="h3", get_fill_color="fill", get_line_color=[255, 255, 255, 200],
                                  line_width_min_pixels=1, stroked=True, filled=True, extruded=False, pickable=True)
                pts = pdk.Layer("ScatterplotLayer", data=df, id="sites", get_position=["site_lon", "site_lat"], get_fill_color="marker",
                                get_radius=120, radius_min_pixels=5, radius_max_pixels=14, stroked=True, get_line_color=[255, 255, 255],
                                line_width_min_pixels=1.5, pickable=True)
                tip = {"html": "<b>#{rank} {district}</b><br/>{build} · cost {cost_new_tower_equivalents} tower-eq.<br/>"
                               "{ppl} people · {chance} chance below 25 Mbps<br/><b>{lifted}</b> likely lifted",
                       "style": {"fontSize": "12px", "maxWidth": "280px"}}
                event = st.pydeck_chart(pdk.Deck(layers=[hexes, pts], initial_view_state=view, tooltip=tip, map_style=None), height=520,
                                        on_select="rerun", selection_mode="single-object", key="map")
                st.html(legend_ramp() + legend_markers([t for t in D.INTERVENTION if t in set(df["intervention"])]))
                picked = (getattr(event, "selection", None) or {}).get("objects", {}).get("sites") if event else None
                if picked and st.session_state.get("_picked") != picked[0]["rank"]:
                    hit = next((o for o in options if o.startswith(f"#{picked[0]['rank']} ")), None)
                    if hit:
                        st.session_state["_picked"] = picked[0]["rank"]
                        st.session_state["focus"] = hit
                        st.rerun()

                if sel is not None:
                    note = safe(f"/sites/{country}/{sel}/note")
                    if note and note.get("note"):
                        s = note["site"]
                        st.markdown(f"**Site #{sel}, {s['district']}** · {D.INTERVENTION[s['intervention']]} · "
                                    f"population used: the smaller of Kontur ({s['people_kontur']:,}) and WorldPop ({s['people_worldpop']:,})")
                        st.html(f'<div class="note">{note["note"]}</div>')
                        st.caption(f"Note written by {'the model' if note.get('source') == 'model' else 'a template'} and checked by a grader "
                                   f"({'passed' if note.get('grader', {}).get('ok') else 'failed'}); no model runs in this app.")
                with st.expander("Table view"):
                    st.dataframe(df[["rank", "district", "build", "cost_new_tower_equivalents", "people", "chance_below_25_mbps", "expected_people_lifted",
                                     "built_up_m2", "slope_deg", "elevation_m"]].rename(columns={
                        "rank": "Rank", "district": "District", "build": "Build type", "cost_new_tower_equivalents": "Cost (tower-eq.)", "people": "People",
                        "chance_below_25_mbps": "Chance below 25 Mbps", "expected_people_lifted": "People likely lifted", "built_up_m2": "Built-up (m²)",
                        "slope_deg": "Slope (°)", "elevation_m": "Elevation (m)"}), hide_index=True, width="stretch",
                        column_config={"Chance below 25 Mbps": st.column_config.NumberColumn(format="percent"),
                                       "People likely lifted": st.column_config.NumberColumn(format="localized")})

# 3. Budget what-if from the committed plan results (P4)
with budget_tab:
    if budget_tab.open:
        plan = plan_results()
        rows = pd.DataFrame(D.budget_rows(plan, country))
        budgets = sorted(rows["budget"].unique())
        pick = st.segmented_control("Budget (new-tower equivalents)", budgets, default=1000.0 if 1000.0 in budgets else budgets[0],
                                    format_func=lambda b: f"{b:,.0f}" if b == int(b) else f"{b:,.1f}", key="budget")
        pick = pick if pick is not None else budgets[0]
        at = rows[rows["budget"] == pick].set_index("method")
        p_plan, p_kpi = at.loc[D.METHODS["people_lifted"], "people"], at.loc[D.METHODS["kpi_ranking"], "people"]
        times = p_plan / p_kpi if p_kpi else float("nan")
        st.subheader(f"At {pick:,.0f} tower-equivalents in {D.place_name(country)}, the plan lifts about {p_plan:,.0f} people: "
                     f"{times:.1f}× as many as KPI ranking ({p_kpi:,.0f})")
        m = st.columns(4)
        m[0].metric("People lifted, plan", f"{p_plan:,.0f}", f"range {at.loc[D.METHODS['people_lifted'], 'low']:,.0f}–{at.loc[D.METHODS['people_lifted'], 'high']:,.0f}",
                    delta_color="off", delta_arrow="off", border=True)
        m[1].metric("People lifted, KPI ranking", f"{p_kpi:,.0f}", "today's practice", delta_color="off", delta_arrow="off", border=True)
        m[2].metric("Plan vs KPI ranking", f"{times:.1f}×", "same budget", delta_color="off", delta_arrow="off", border=True)
        m[3].metric("Sites in the plan", f"{int(at['sites'].iloc[0]):,}", "at this budget", delta_color="off", delta_arrow="off", border=True)
        if p_plan < 1000:
            st.warning(f"Few people are left on slow mobile in {D.place_name(country)}, so the multiple rests on a small number; read the people count, not the ×.")

        order = list(D.METHODS.values())
        x = alt.X("budget:Q", title="Budget (new-tower equivalents, log scale)", scale=alt.Scale(type="log", domain=[min(budgets), max(budgets)], nice=False),
                  axis=alt.Axis(format="~s", values=budgets))
        band = alt.Chart(rows.dropna(subset=["low"])).mark_area(opacity=0.16, color=C["plan"]).encode(x=x, y="low:Q", y2="high:Q")
        lines = alt.Chart(rows).mark_line(strokeWidth=2.5, point=alt.OverlayMarkDef(size=70, filled=True)).encode(
            x=x, y=alt.Y("people:Q", title="People lifted above 25 Mbps", axis=alt.Axis(format="~s")),
            color=alt.Color("method:N", sort=order, scale=alt.Scale(domain=order, range=[C["plan"], C["kpi"], C["slow"]]),
                            legend=alt.Legend(title=None, orient="top", labelLimit=260)),
            tooltip=[alt.Tooltip("method:N", title=""), alt.Tooltip("budget:Q", title="Budget", format=",.1f"),
                     alt.Tooltip("people:Q", title="People lifted", format=",.0f")])
        rule = alt.Chart(pd.DataFrame([{"budget": pick}])).mark_rule(color=INK, strokeDash=[4, 4]).encode(x="budget:Q")
        st.altair_chart((band + lines + rule).properties(height=340), width="stretch", theme="streamlit")
        st.caption("From the committed plan results (P4): an exact optimiser over cost classes; the shaded band is the plan's low–high range "
                   "from the new-site effect's confidence interval. KPI ranking = equal-weight z-scores of slow speed, population and places.")
        with st.expander("Table view"):
            st.dataframe(rows.pivot_table(index="budget", columns="method", values="people").reset_index().rename(columns={"budget": "Budget"}),
                         hide_index=True, width="stretch")

# 4. Check a place and its neighbours (live API)
with place_tab:
    if place_tab.open:
        a, b, c = st.columns([2, 1, 1])
        preset = a.selectbox("Place", list(D.PRESETS) + ["Custom point"], key="preset")
        lat0, lon0 = D.PRESETS.get(preset, (7.21421, 124.22888))
        lat = b.number_input("Latitude", -90.0, 90.0, float(lat0), 0.001, format="%.5f", key="lat", disabled=preset != "Custom point")
        lon = c.number_input("Longitude", -180.0, 180.0, float(lon0), 0.001, format="%.5f", key="lon", disabled=preset != "Custom point")
        if preset != "Custom point":
            lat, lon = lat0, lon0
        g = safe("/gap", lat=round(lat, 5), lon=round(lon, 5))
        if g and g.get("out_of_scope"):
            st.info(g.get("message", "Outside the seven countries covered."))
        elif g and g.get("h3"):
            cells = [g] + [x for x in (safe("/gap", lat=round(la, 5), lon=round(lo, 5)) for la, lo in map(D.centre, D.neighbours(g["h3"]))) if x]
            people = min(g["people_kontur"], g["people_worldpop"])
            st.subheader(f"{g['district']}: {g['gap_type_25_mbps']}, typical {g['typical_mbps'] or 0:.0f} Mbps, "
                         f"{g['chance_below_25_mbps']:.0%} chance of being below 25 Mbps")
            m = st.columns(4)
            m[0].metric("Typical speed", f"{g['typical_mbps']:.0f} Mbps" if g["typical_mbps"] is not None else "not measured",
                        "measured" if g["tested"] else "estimated (kriging)", delta_color="off", delta_arrow="off", border=True)
            m[1].metric("Speed tests", f"{g['tests']:,}", "in the quarter", delta_color="off", delta_arrow="off", border=True)
            m[2].metric("People", f"{people:,}", "smaller of two maps", delta_color="off", delta_arrow="off", border=True)
            m[3].metric("In the plan", f"#{g['in_plan']['rank']}" if g.get("in_plan") else "no", D.INTERVENTION[g["in_plan"]["intervention"]] if g.get("in_plan") else
                        "not among the chosen sites", delta_color="off", delta_arrow="off", border=True)
            if g["tests"] < 10:
                st.warning(f"Thin evidence: only {g['tests']} speed tests here, so the chance rests mostly on neighbours and the model.")
            cdf = pd.DataFrame([{"h3": x["h3"], "p": x.get("chance_below_25_mbps"), "mbps": x.get("typical_mbps"), "tests": x.get("tests", 0),
                                 "role": "this point" if x is g else "neighbour", "people": min(x.get("people_kontur", 0), x.get("people_worldpop", 0))}
                                for x in cells if x.get("h3")])
            cdf["fill"] = cdf["p"].map(lambda p: D.hex_rgb(D.ramp(p), 190))
            cdf["chance"] = cdf["p"].map(lambda p: "n/a" if p is None or pd.isna(p) else f"{p:.0%}")
            cdf["speed"] = cdf["mbps"].map(lambda v: "n/a" if v is None or pd.isna(v) else f"{v:.0f} Mbps")
            # constant line settings only: per-feature line accessors blank the whole deck in Streamlit's pydeck build
            ring = pdk.Layer("H3HexagonLayer", data=cdf[cdf["role"] == "neighbour"], id="ring", get_hexagon="h3", get_fill_color="fill",
                             get_line_color=[255, 255, 255, 220], line_width_min_pixels=1, stroked=True, filled=True, extruded=False, pickable=True)
            here = pdk.Layer("H3HexagonLayer", data=cdf[cdf["role"] == "this point"], id="here", get_hexagon="h3", get_fill_color="fill",
                             get_line_color=[25, 26, 36, 255], line_width_min_pixels=3, stroked=True, filled=True, extruded=False, pickable=True)
            st.pydeck_chart(pdk.Deck(layers=[ring, here], initial_view_state=pdk.ViewState(latitude=lat, longitude=lon, zoom=13.4),
                                     tooltip={"html": "<b>{role}</b><br/>{speed} typical · {tests} tests<br/>{chance} chance below 25 Mbps<br/>{people} people"},
                                     map_style=None), height=430)
            st.html(legend_ramp() + '<div class="legend"><span><i class="sw" style="background:transparent;border:3px solid currentColor"></i>'
                    'this point (dark outline); the six around it are its neighbours</span></div>')
            slow = int((cdf["p"].fillna(0) >= 0.5).sum())
            st.caption(f"{slow} of {len(cdf)} hexagons here are more likely than not below 25 Mbps. Quarter: speed tests from the latest Ookla release the API serves.")

# 5. Countries at your speed bar (live API)
with bar_tab:
    if bar_tab.open:
        bar = st.segmented_control("Speed bar", D.BARS, default=25, format_func=lambda b: f"{b} Mbps", key="bar") or 25
        cs = safe("/countries", bar_mbps=bar)
        if cs and cs.get("countries"):
            cdf = pd.DataFrame(cs["countries"])
            worst = cdf.sort_values("share_below_bar_everyone", ascending=False).iloc[0]
            wname = D.place_name(worst["country"])
            st.subheader(f"Below {bar} Mbps: {wname[0].upper() + wname[1:]} has the largest share, {worst['share_below_bar_everyone']:.0%} of people "
                         f"({worst['people_below_bar_everyone_millions']:,.1f}M), counting areas nobody tested")
            long = cdf.melt(id_vars=["name"], value_vars=["share_below_bar_tested", "share_below_bar_everyone"], var_name="who", value_name="share")
            long["who"] = long["who"].map({"share_below_bar_tested": "Among tested areas only", "share_below_bar_everyone": "Everyone (untested areas estimated)"})
            order = cdf.sort_values("share_below_bar_everyone", ascending=False)["name"].tolist()
            whos = ["Among tested areas only", "Everyone (untested areas estimated)"]
            chart = alt.Chart(long).mark_bar(cornerRadiusEnd=3, height=11).encode(
                y=alt.Y("name:N", sort=order, title=None, axis=alt.Axis(labelLimit=200)), yOffset=alt.YOffset("who:N", sort=whos),
                x=alt.X("share:Q", title=f"Share of people below {bar} Mbps", axis=alt.Axis(format="%")),
                color=alt.Color("who:N", sort=whos, scale=alt.Scale(domain=whos, range=[C["kpi"], C["plan"]]), legend=alt.Legend(title=None, orient="top", labelLimit=300)),
                tooltip=[alt.Tooltip("name:N", title="Country"), alt.Tooltip("who:N", title=""), alt.Tooltip("share:Q", title="Share", format=".1%")])
            st.altair_chart(chart.properties(height=alt.Step(30)), width="stretch", theme="streamlit")
            st.caption(f"Speed tests: Ookla open data, {cs.get('quarter', '')}. 'Everyone' adds untested populated hexagons, estimated by kriging from "
                       "their tested neighbours; the gap between the two bars is the people a test-only view misses.")
            for col in ["tested_share", "share_below_bar_tested", "share_below_bar_everyone"]:
                cdf[col] = cdf[col] * 100
            st.dataframe(cdf[["name", "population_millions", "tested_share", "share_below_bar_tested", "share_below_bar_everyone",
                              "people_below_bar_everyone_millions", "untested_people_likely_below_bar_millions"]].rename(columns={
                "name": "Country", "population_millions": "Population (M)", "tested_share": "Tested share", "share_below_bar_tested": "Below bar, tested",
                "share_below_bar_everyone": "Below bar, everyone", "people_below_bar_everyone_millions": "People below (M)",
                "untested_people_likely_below_bar_millions": "Untested, likely below (M)"}), hide_index=True, width="stretch",
                column_config={c: st.column_config.NumberColumn(format="%.1f%%") for c in ["Tested share", "Below bar, tested", "Below bar, everyone"]})

# 6. The planner agent: recorded answers by default, live only with the viewer's own key
with agent_tab:
    if agent_tab.open:
        import agent_tools as AT
        import chat
        st.markdown("Ask the planning agent in plain words. It picks the tools (a place's speed, a country's plan, one site's note, "
                    "countries at a speed bar), reads their results and answers; every number must come from a tool.")
        chat.render(st, Path(__file__).resolve().parent / "replays.json", AT)
