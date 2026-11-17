"""Interactive Leaflet maps for the skill (one HTML file, no build step).

Design (references/charts.md, iteration 4 review):
- Hexagons are filled on one orange scale by the chance that typical speed is below 25 Mbps (light = fast, dark = likely slow);
  the queried hexagon has a thick outline. Markers use other hues so they never blend with the hexagons:
  blue = the point asked about or a planned site, aqua = places (shops, schools, offices, stations), violet = telecom masts and towers,
  white outlines = buildings.
- Buildings, places and masts come live from OpenStreetMap (Overpass API) for the area in view once zoomed in to street level,
  so they work for any place; they are volunteered data and may be incomplete, which the panel says.
- A panel shows the numbers a planner needs, the colour legend, the layer counts and the data line.
"""
from __future__ import annotations

import html
import json
import math
import urllib.parse
import urllib.request

RAMP = [(0.2, "#fde3d4"), (0.4, "#f7b48f"), (0.6, "#ef8a55"), (0.8, "#d9622a"), (1.01, "#a8461a")]   # chance below 25 Mbps
BLUE, AQUA, VIOLET = "#2a78d6", "#1baf7a", "#6250d6"
OVERPASS = ("https://maps.mail.ru/osm/tools/overpass/api/interpreter", "https://overpass-api.de/api/interpreter")   # fastest first (measured 2026-11-17)


def fetch_osm(box: list[float], timeout: float = 90) -> dict | None:
    """Buildings, places and masts from OpenStreetMap for a small box [s, w, n, e]; None if every mirror fails.
    Public Overpass servers queue requests (20-60 s measured), so this runs once when the map is built, not in the browser."""
    bb = "(" + ",".join(f"{x:.5f}" for x in box) + ")"
    q = (f'[out:json][timeout:60];(way["building"]{bb};node["amenity"]{bb};node["shop"]{bb};node["office"]{bb};node["tourism"]{bb};'
         f'node["railway"="station"]{bb};node["public_transport"="station"]{bb};node["man_made"~"mast|tower|communications_tower"]{bb};'
         f'way["man_made"~"mast|tower|communications_tower"]{bb};node["telecom"]{bb};node["communication:mobile_phone"]{bb};);out geom 4000;')
    for url in OVERPASS:
        try:
            req = urllib.request.Request(url, data=("data=" + urllib.parse.quote(q)).encode(), headers={"User-Agent": "next-site-planner-skill/1.1"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                els = json.load(r)["elements"]
            break
        except Exception:  # noqa: BLE001 - try the next mirror
            els = None
    if els is None:
        return None
    out = {"buildings": [], "places": [], "masts": []}
    for e in els:
        t = e.get("tags", {})
        is_mast = bool(any(k in (t.get("man_made") or "") for k in ("mast", "tower")) or t.get("telecom") or t.get("communication:mobile_phone"))
        if e["type"] == "way" and t.get("building") and not is_mast and e.get("geometry"):
            out["buildings"].append({"ring": [[round(g["lat"], 6), round(g["lon"], 6)] for g in e["geometry"]],
                                     "name": t.get("name") or t["building"], "levels": t.get("building:levels")})
        elif is_mast:
            ll = (e["lat"], e["lon"]) if e["type"] == "node" else (e["geometry"][0]["lat"], e["geometry"][0]["lon"])
            out["masts"].append({"lat": ll[0], "lon": ll[1], "name": t.get("name") or "Mast / tower",
                                 "kind": " ".join(x for x in (t.get("man_made"), t.get("tower:type")) if x), "operator": t.get("operator") or ""})
        elif e["type"] == "node":
            kind = t.get("amenity") or t.get("shop") or t.get("office") or t.get("tourism") or t.get("railway") or t.get("public_transport")
            out["places"].append({"lat": e["lat"], "lon": e["lon"], "name": t.get("name") or kind, "kind": kind})
    return out


def metres(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def ramp(p: float) -> str:
    return next(c for t, c in RAMP if p < t)


TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
html,body,#m{height:100%;margin:0}body{font:13px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif;color:#0b0b0b}
.panel{position:absolute;z-index:1000;top:10px;right:10px;width:290px;max-height:calc(100% - 40px);overflow:auto;background:#fcfcfb;
border:1px solid rgba(11,11,11,.12);border-radius:8px;padding:10px 12px;box-shadow:0 2px 10px rgba(0,0,0,.15)}
.panel h1{font-size:14px;margin:0 0 6px}.panel .k{color:#52514e}.panel table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
.panel td{padding:2px 0;vertical-align:top}.panel td:last-child{text-align:right}.sw{display:inline-block;width:12px;height:12px;border-radius:2px;vertical-align:-2px;margin-right:6px}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;vertical-align:-1px;margin-right:6px;border:2px solid #fff;box-shadow:0 0 0 1px rgba(0,0,0,.25)}
.ramp{display:flex;gap:2px;margin:4px 0 2px}.ramp span{flex:1;height:10px;border-radius:2px}.small{font-size:11.5px;color:#52514e}
.status{font-size:11.5px;color:#52514e;margin-top:4px}
@media (max-width:520px){.panel{width:auto;left:10px;top:auto;bottom:24px;max-height:45%}}
</style></head><body><div id="m"></div>
<div class="panel">__PANEL__
<div style="margin-top:8px"><b>Hexagons:</b> chance typical speed is below 25 Mbps</div>
<div class="ramp">__RAMP__</div><div class="small" style="display:flex;justify-content:space-between"><span>0% (fast)</span><span>100% (slow)</span></div>
<div style="margin-top:8px"><span class="dot" style="background:__BLUE__"></span>__MAINDOT__<br>
<span class="dot" style="background:__AQUA__"></span>Places: shops, schools, offices, stations<br>
<span class="dot" style="background:__VIOLET__"></span>Telecom masts and towers (co-location options)<br>
<span class="sw" style="border:2px solid #fff;background:transparent;box-shadow:0 0 0 1px rgba(0,0,0,.3)"></span>Buildings</div>
<div class="status" id="status">Loading OpenStreetMap features…</div>
<div class="small" style="margin-top:6px">__FOOT__</div></div>
<script>
const HEX = __HEX__, PTS = __PTS__, OSM = __OSM__;   // OSM: features fetched when the map was built (null = load live when zoomed in)
const street = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19, attribution: '© OpenStreetMap contributors (ODbL)'});
const sat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {maxZoom: 19, attribution: 'Imagery © Esri'});
const m = L.map('m', {layers: [sat], zoomSnap: 0.5}); L.control.scale({imperial: false}).addTo(m);
m.createPane('top'); m.getPane('top').style.zIndex = 650;   // the asked-about point or planned sites stay above every other marker
const hexL = L.featureGroup().addTo(m), ptL = L.featureGroup().addTo(m);
const bldL = L.layerGroup().addTo(m), poiL = L.layerGroup().addTo(m), mastL = L.layerGroup().addTo(m);
L.control.layers({'Satellite': sat, 'Street': street},
  {'Hexagons (speed)': hexL, 'Point / planned sites': ptL, 'Buildings (OSM)': bldL, 'Places (OSM)': poiL, 'Masts and towers (OSM)': mastL},
  {position: 'topleft'}).addTo(m);
for (const h of HEX) {
  if (!h.ring.length) continue;
  L.polygon(h.ring, {color: h.center ? '#0b0b0b' : '#ffffff', weight: h.center ? 3.5 : 1.2, opacity: .95, fillColor: h.fill, fillOpacity: .3,
    dashArray: h.approx ? '6 4' : null}).bindPopup(h.popup).addTo(hexL);
}
for (const p of PTS) {
  L.circleMarker([p.lat, p.lon], {pane: 'top', radius: 10, color: '#ffffff', weight: 3, fillColor: '__BLUE__', fillOpacity: 1}).bindPopup(p.popup).addTo(ptL)
   .on('click', () => { if (m.getZoom() < 15) m.setView([p.lat, p.lon], 16); });
}
m.fitBounds((hexL.getLayers().length ? hexL : ptL).getBounds().pad(0.25));
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function draw(o) {
  bldL.clearLayers(); poiL.clearLayers(); mastL.clearLayers();
  for (const b of o.buildings) L.polygon(b.ring, {color: '#ffffff', weight: 1, fill: false, opacity: .9})
    .bindPopup(`<b>Building</b><br>${esc(b.name)}${b.levels ? '<br>' + esc(b.levels) + ' levels' : ''}`).addTo(bldL);
  for (const p of o.places) L.circleMarker([p.lat, p.lon], {radius: 4.5, color: '#ffffff', weight: 1.5, fillColor: '__AQUA__', fillOpacity: 1})
    .bindPopup(`<b>${esc(p.name)}</b><br>${esc(p.kind)}`).addTo(poiL);
  for (const t of o.masts) L.circleMarker([t.lat, t.lon], {radius: 7, color: '#ffffff', weight: 2, fillColor: '__VIOLET__', fillOpacity: 1})
    .bindPopup(`<b>${esc(t.name)}</b><br>${esc(t.kind)}<br>${esc(t.operator)}`).addTo(mastL);
  return [o.buildings.length, o.places.length, o.masts.length];
}
let busy = false, lastKey = '';
async function loadOSM() {
  const st = document.getElementById('status');
  if (m.getZoom() < 15) { st.textContent = 'Zoom in to street level to load buildings, places and masts (live; public servers can take a minute).'; return; }
  const b = m.getBounds(), box = [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()], key = box.map(x => x.toFixed(4)).join(',');
  if (busy || key === lastKey) return; busy = true; lastKey = key; st.textContent = 'Loading OpenStreetMap features…';
  const bb = `(${key})`;
  const q = `[out:json][timeout:25];(way["building"]${bb};node["amenity"]${bb};node["shop"]${bb};node["office"]${bb};node["tourism"]${bb};`
    + `node["railway"="station"]${bb};node["public_transport"="station"]${bb};node["man_made"~"mast|tower|communications_tower"]${bb};`
    + `way["man_made"~"mast|tower|communications_tower"]${bb};node["telecom"]${bb};node["communication:mobile_phone"]${bb};);out geom 3000;`;
  try {
    const r = await fetch('https://overpass-api.de/api/interpreter', {method: 'POST', body: 'data=' + encodeURIComponent(q)});
    const d = await r.json(); bldL.clearLayers(); poiL.clearLayers(); mastL.clearLayers(); let nb = 0, np = 0, nm = 0;
    for (const e of d.elements) {
      const t = e.tags || {}, mast = /mast|tower/.test(t.man_made || '') || t.telecom || t['communication:mobile_phone'];
      if (e.type === 'way' && t.building && !mast && e.geometry) {
        nb++; L.polygon(e.geometry.map(g => [g.lat, g.lon]), {color: '#ffffff', weight: 1, fill: false, opacity: .9})
          .bindPopup(`<b>Building</b><br>${esc(t.name || t.building)}${t['building:levels'] ? '<br>' + esc(t['building:levels']) + ' levels' : ''}`).addTo(bldL);
      } else if (mast) {
        nm++; const ll = e.type === 'node' ? [e.lat, e.lon] : [e.geometry[0].lat, e.geometry[0].lon];
        L.circleMarker(ll, {radius: 7, color: '#ffffff', weight: 2, fillColor: '__VIOLET__', fillOpacity: 1})
          .bindPopup(`<b>${esc(t.name || 'Mast / tower')}</b><br>${esc(t.man_made || '')} ${esc(t['tower:type'] || '')}<br>${esc(t.operator || '')}`).addTo(mastL);
      } else if (e.type === 'node') {
        np++; const kind = t.amenity || t.shop || t.office || t.tourism || t.railway || t.public_transport;
        L.circleMarker([e.lat, e.lon], {radius: 4.5, color: '#ffffff', weight: 1.5, fillColor: '__AQUA__', fillOpacity: 1})
          .bindPopup(`<b>${esc(t.name || kind)}</b><br>${esc(kind)}`).addTo(poiL);
      }
    }
    st.textContent = `In view (OpenStreetMap, may be incomplete): ${nb.toLocaleString()} buildings · ${np.toLocaleString()} places · ${nm} masts or towers.`;
  } catch (err) { st.textContent = 'OpenStreetMap features could not be loaded (Overpass busy); the map still works.'; lastKey = ''; }
  busy = false;
}
if (OSM) { const [nb, np, nm] = draw(OSM); document.getElementById('status').textContent =
  `In this area (OpenStreetMap, may be incomplete): ${nb.toLocaleString()} buildings · ${np.toLocaleString()} places · ${nm} masts or towers.`; }
else { document.getElementById('status').textContent = 'Zoom in to street level (or click a site) to load buildings, places and masts.'; m.on('moveend', loadOSM); }
</script></body></html>"""


def page(title: str, panel_html: str, hexes: list[dict], points: list[dict], main_dot: str, foot: str, osm: dict | None = None) -> str:
    ramp_html = "".join(f'<span style="background:{c}"></span>' for _, c in RAMP)
    out = TEMPLATE
    for k, v in {"__TITLE__": html.escape(title), "__PANEL__": panel_html, "__RAMP__": ramp_html, "__MAINDOT__": html.escape(main_dot),
                 "__FOOT__": html.escape(foot), "__HEX__": json.dumps(hexes), "__PTS__": json.dumps(points),
                 "__BLUE__": BLUE, "__AQUA__": AQUA, "__VIOLET__": VIOLET, "__OSM__": json.dumps(osm)}.items():
        out = out.replace(k, v)
    return out


def bbox(hexes: list[dict]) -> list[float]:
    pts = [pt for h in hexes for pt in h["ring"]]
    return [min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)]


def hex_popup(g: dict) -> str:
    plan = f"in the plan: #{g['in_plan']['rank']} ({g['in_plan']['intervention']})" if g.get("in_plan") else "not in the plan"
    wp = f"{g['people_worldpop']:,}" if g.get("people_worldpop") is not None else "n/a"
    return (f"<b>{html.escape(g['district'])}</b><br>typical {g['typical_mbps']} Mbps · {html.escape(g['gap_type_25_mbps'])}<br>"
            f"chance below 25 Mbps {g['chance_below_25_mbps']:.0%} · below 10 Mbps {g['chance_below_10_mbps']:.0%}<br>"
            f"{'measured: ' + format(g['tests'], ',') + ' tests' if g['tested'] else 'estimated from neighbours (untested)'}<br>"
            f"people {g['people_kontur']:,} (Kontur) / {wp} (WorldPop) · {html.escape(g['area_type'].replace('_', ' '))}<br>{plan}")
