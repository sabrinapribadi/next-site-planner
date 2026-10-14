// Real-browser tooltip check (rule R10) in three modes: desktop light, desktop dark, phone 400 px.
// Opens every collapsed section, then for every chart: tooltip appears on hover, stays inside its chart
// (or as a panel under it on phones), disappears on leave; none on load; no sideways scroll; no JS errors.
// Run: make hover-test   (needs Node + Google Chrome)
const puppeteer = require("puppeteer-core");
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const [file, outDir] = process.argv.slice(2);
  const b = await puppeteer.launch({ executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: "new" });
  const modes = [["desktop-light", 1280, 900, "light"], ["desktop-dark", 1280, 900, "dark"], ["phone-400", 400, 860, "light"]];
  const summary = [];
  for (const [mode, W, H, scheme] of modes) {
    const page = await b.newPage(); await page.setViewport({ width: W, height: H, deviceScaleFactor: 1 });
    await page.emulateMediaFeatures([{ name: "prefers-color-scheme", value: scheme }]);
    const errs = []; page.on("pageerror", (e) => errs.push(e.message));
    await page.goto("file://" + file, { waitUntil: "networkidle0" });
    const onLoad = await page.$$eval(".tip", (ts) => ts.filter((t) => getComputedStyle(t).display !== "none").length);
    const closedOnLoad = await page.$$eval("details.more", (ds) => ds.filter((d) => !d.open).length);
    await page.$$eval("details", (ds) => ds.forEach((d) => (d.open = true)));
    const hScroll = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    const ids = await page.$$eval("svg.plot", (ss) => ss.map((s) => s.id));
    const rows = [];
    for (const id of ids) {
      const el = await page.$("#" + id); await el.scrollIntoView(); await wait(300);
      const box = await el.boundingBox();
      const probes = [[0.5, 0.45], [0.3, 0.5], [0.7, 0.4], [0.2, 0.3], [0.8, 0.6], [0.6, 0.7]];
      const circ = await page.$$eval("#" + id + " circle:not(.hover-mark)", (cs) => cs.slice(0, 1).map((c) => { const r = c.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }));
      let res = null, shotDone = false;
      for (const pt of probes.map(([fx, fy]) => [box.x + box.width * fx, box.y + box.height * fy]).concat(circ)) {
        await page.mouse.move(pt[0], pt[1]); await wait(70);
        res = await page.evaluate((id) => { const t = document.getElementById(id).parentElement.querySelector(":scope > .tip"); if (!t || getComputedStyle(t).display === "none") return null;
          const r = t.getBoundingClientRect(), w = t.parentElement.getBoundingClientRect(), cs = getComputedStyle(t);
          const clipped = [...t.querySelectorAll("*")].some((e) => e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflow !== "visible");
          return { inside: r.left >= w.left - 1 && r.right <= w.right + 1 && r.top >= w.top - 1 && r.bottom <= w.bottom + 1, w: Math.round(r.width), h: Math.round(r.height), coverPct: Math.round(100 * r.width * r.height / (w.width * w.height)), bg: cs.backgroundColor, fg: cs.color, clipped, text: t.textContent.replace(/\s+/g, " ").trim().slice(0, 70) }; }, id);
        if (res) { if (mode !== "phone-400" || true) { const wrap = await page.evaluateHandle((id) => document.getElementById(id).parentElement, id); await wrap.asElement().screenshot({ path: `${outDir}/${mode}_${id}.png` }); shotDone = true; } break; }
      }
      await page.mouse.move(2, 2); await wait(80);
      const gone = await page.evaluate((id) => { const t = document.getElementById(id).parentElement.querySelector(":scope > .tip"); return !t || getComputedStyle(t).display === "none"; }, id);
      const ok = !!res && res.inside && gone;
      rows.push({ id, ok, ...(res || {}), gone });
    }
    // map: hover the centre of the top area (canvas), then a top-list row (keyboard focus); tip inside the map box, hides on leave
    const mapTip = () => page.evaluate(() => { const w = document.getElementById("mapwrap"), t = w.querySelector(":scope > .tip"); if (getComputedStyle(t).display === "none") return null;
      const r = t.getBoundingClientRect(), b = w.getBoundingClientRect(); return { inside: r.left >= b.left - 1 && r.right <= b.right + 1 && r.top >= b.top - 1 && r.bottom <= b.bottom + 1, w: Math.round(r.width), h: Math.round(r.height), text: t.textContent.replace(/\s+/g, " ").trim().slice(0, 70) }; });
    const mw = await page.$("#mapwrap"); await mw.scrollIntoView(); await wait(300);
    const pt = await page.evaluate(() => { const i = +document.querySelector("#toplist li").dataset.i; const [x, y] = cellCentre(i); const r = document.getElementById("map").getBoundingClientRect(); return [r.left + x, r.top + y]; });
    await page.mouse.move(pt[0], pt[1]); await wait(100);
    const mt = await mapTip();
    if (mt) { await mw.screenshot({ path: `${outDir}/${mode}_map.png` }); }
    await page.mouse.move(2, 2); await wait(80);
    const mGone = (await mapTip()) === null;
    rows.push({ id: "map", ok: !!mt && mt.inside && mGone && /people/.test(mt.text), ...(mt || {}), gone: mGone });
    await page.focus("#toplist li:nth-child(2)"); await wait(100);
    const lt = await mapTip(); await page.evaluate(() => document.activeElement.blur()); await wait(80);
    const lGone = (await mapTip()) === null;
    rows.push({ id: "toplist", ok: !!lt && lt.inside && lGone, ...(lt || {}), gone: lGone });
    // district zoom: click the first district, hover one of its 0.74 km² hexagons, then go back
    await page.evaluate(() => document.querySelector("#toplist li").click()); await page.waitForFunction(() => state.detail !== null, { timeout: 10000 }); await wait(200);
    await page.evaluate(() => document.getElementById("mapwrap").scrollIntoView({ block: "center" })); await wait(200);
    const dp = await page.evaluate(() => { const [x, y] = cellCentre(0); const r = document.getElementById("map").getBoundingClientRect(); return [r.left + x, r.top + y]; });
    await page.mouse.move(dp[0], dp[1]); await wait(100);
    const dt = await mapTip();
    if (dt) { await mw.screenshot({ path: `${outDir}/${mode}_district.png` }); }
    await page.mouse.move(2, 2); await wait(80);
    const head = await page.$eval("#maphead", (e) => e.textContent.replace(/\s+/g, " ").trim().slice(0, 80));
    await page.evaluate(() => document.getElementById("map-back").click()); await wait(150);
    const back = await page.evaluate(() => state.detail === null);
    // nominal map: markers, a popup with satellite link, terrain tiles loaded (network)
    const nm = await page.$("#nmap"); await nm.scrollIntoView(); await wait(2500);
    const nmr = await page.evaluate(() => { const ls = nlayer ? nlayer.getLayers() : []; if (ls.length) ls[0].openPopup();
      const pop = document.querySelector("#nmap .leaflet-popup-content"); return { markers: ls.length, popup: pop ? pop.textContent.replace(/\s+/g, " ").slice(0, 70) : "",
        sat: !!(pop && pop.querySelector('a[href*="google.com/maps"]')), tiles: document.querySelectorAll("#nmap img.leaflet-tile-loaded").length,
        checks: !!(pop && /WorldPop/.test(pop.textContent) && /Buildings/.test(pop.textContent)), cells: ncells ? ncells.getLayers().length : 0 }; });
    if (nmr.markers) await nm.screenshot({ path: `${outDir}/${mode}_nominals.png` });
    rows.push({ id: "nominals", ok: nmr.markers > 0 && /people/.test(nmr.popup) && nmr.sat && nmr.tiles > 0, w: nmr.markers, h: nmr.tiles, inside: true, gone: true, text: nmr.popup });
    rows.push({ id: "nom-checks", ok: nmr.checks && nmr.cells > 0, w: nmr.cells, h: 0, inside: true, gone: true, text: `popup shows population sources and built-up land: ${nmr.checks} · existing-cell shapes drawn: ${nmr.cells}` });
    // zoomed in over Jakarta: every recorded cell hexagon loads and draws; the map has its own country switcher
    await page.evaluate(() => { nmap.closePopup(); nmap.setView([-6.2, 106.82], 12); }); await wait(3000);
    const zh = await page.evaluate(() => ({ hex: ncells.getLayers().length, isoButtons: document.querySelectorAll("#nmap-iso button").length }));
    rows.push({ id: "cell-hexes", ok: zh.hex > 0 && zh.isoButtons === 7, w: zh.hex, h: zh.isoButtons, inside: true, gone: true, text: `cell hexagons drawn at zoom 12: ${zh.hex} · country buttons on the map: ${zh.isoButtons}` });
    const subs = await page.evaluate(() => [...document.querySelectorAll(".chart-sub")].map((e) => e.textContent.trim()));
    rows.push({ id: "subtitles", ok: subs.length === 6 && subs.every((t) => t.length > 20 && !/undefined|NaN/.test(t)), w: subs.length, h: 0, inside: true, gone: true, text: subs.map((t) => t.slice(0, 40)).join(" | ") });
    rows.push({ id: "district", ok: !!dt && dt.inside && /Typical speed|Not tested/.test(dt.text) && back, ...(dt || {}), gone: back, text: (dt ? dt.text : "") + " | " + head });
    summary.push({ mode, onLoad, closedOnLoad, hScroll, errs: errs.length, pass: rows.filter((r) => r.ok).length, total: rows.length });
    console.log(`\n== ${mode}: tooltips visible on load=${onLoad} · page scrolls sideways=${hScroll} · JS errors=${errs.length}`);
    for (const r of rows) console.log(`  ${r.ok ? "OK  " : "FAIL"} ${r.id.padEnd(8)} ${r.w ? `${r.w}×${r.h}px covers ${r.coverPct ?? "-"}% inside=${r.inside}${r.clipped ? " CLIPPED" : ""}` : "not shown"} hides=${r.gone} | ${r.text || ""}`);
    if (mode === "desktop-dark") console.log(`  tooltip colours (dark): bg ${rows[0].bg} · text ${rows[0].fg}`);
    await page.close();
  }
  console.log("\nSUMMARY", JSON.stringify(summary));
  await b.close();
})();
