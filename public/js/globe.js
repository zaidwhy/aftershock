// The home globe: this week's breakouts as epicentres (pulsing rings), each title's next countries as arcs, and,
// for a chosen title and country, Qloo's city heatmap rising out of the surface. globe.gl (three.js) is vendored
// and loaded only on the home page, after the copy has painted.
import { h } from "./dom.js";
import { getStorm } from "./api.js";
import { pct, rankLabel } from "./format.js";
import { ISO } from "./iso.js";
import { CENTROID } from "./centroids.js";

const GLOBE_SRC = "vendor/globe.gl-2.46.2.min.js";
const WORLD_SRC = "vendor/countries-110m.json";
const ARCS_PER_TITLE = 5;
const WEEK_ARCS = 24;
const SHOCK = "#ff5a36";
const QLOO = "#3ee6b0";

const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const byNumeric = new Map(Object.entries(ISO).map(([code, [num]]) => [num, code]));
const name = (code) => ISO[code]?.[1] ?? code;
// globe.gl renders tooltips as HTML; titles come from Netflix's lists, so escape them.
const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const at = (code) => CENTROID[code] && { lat: CENTROID[code][0], lng: CENTROID[code][1] };

let globeLib = null;
function loadGlobe() {
  globeLib ||= new Promise((resolve, reject) => {
    if (window.Globe) { resolve(window.Globe); return; }
    const tag = document.createElement("script");
    tag.src = GLOBE_SRC;
    tag.onload = () => resolve(window.Globe);
    tag.onerror = () => { globeLib = null; reject(new Error("The 3D globe library did not load.")); };
    document.head.append(tag);
  });
  return globeLib;
}

async function countries() {
  const res = await fetch(WORLD_SRC);
  if (!res.ok) throw new Error(`Country outlines returned HTTP ${res.status}.`);
  const world = await res.json();
  for (let i = 0; i < 50 && !window.topojson; i++) await new Promise((r) => setTimeout(r, 100));
  if (!window.topojson) throw new Error("topojson-client did not load.");
  return window.topojson.feature(world, world.objects.countries).features
    .map((f) => ({ ...f, code: byNumeric.get(Number(f.id)) || null }));
}

// Chance tints run from the sea colour to the shock colour; a country with no forecast stays plain land.
const tint = (chance) => {
  if (chance == null) return document.documentElement.dataset.theme === "light" ? "rgba(118,100,78,0.20)" : "rgba(120,132,150,0.16)";
  const a = 0.22 + Math.min(1, chance / 0.5) * 0.68;
  return `rgba(255,90,54,${a.toFixed(2)})`;
};

/**
 * Mount the globe into `host`. `week` is the static storms payload (map, storms). `onPick({code, storm})` fires when a
 * country is clicked; the caller renders the side panel. Returns {focus(stormId), select(code), destroy()}.
 */
export async function mountGlobe(host, week, onPick) {
  const [Globe, feats] = await Promise.all([loadGlobe(), countries()]);
  const chanceBy = new Map((week.map?.countries || []).map((c) => [c.code, c.chance]));
  const originSet = new Set(week.map?.origins || []);
  const drawn = new Set(feats.map((f) => f.code).filter(Boolean));
  // Countries too small for the 110m outline (Malta, Singapore, Bahrain...) get a marker instead of a shape.
  const markers = Object.keys(ISO).filter((c) => !drawn.has(c) && CENTROID[c]).map((code) => ({ code, ...at(code) }));

  let focusId = null;
  let picked = null;
  let detail = null;
  let hover = null;

  const light = () => document.documentElement.dataset.theme === "light";
  const g = Globe({ animateIn: !reduced() })(host)
    .backgroundColor("rgba(0,0,0,0)")
    .showAtmosphere(true).atmosphereColor(SHOCK).atmosphereAltitude(0.16)
    .polygonsData(feats)
    .polygonCapColor((f) => (f.code && f.code === picked ? SHOCK : originSet.has(f.code) && !focusId ? "rgba(255,196,120,0.95)" : tint(focusChance(f.code))))
    .polygonSideColor(() => "rgba(255,90,54,0.12)")
    .polygonStrokeColor(() => "rgba(255,255,255,0.10)")
    .polygonAltitude((f) => (f === hover || (f.code && f.code === picked) ? 0.035 : f.code && (originSet.has(f.code) || chanceBy.has(f.code)) ? 0.012 : 0.006))
    .polygonsTransitionDuration(300)
    .polygonLabel((f) => label(f.code))
    .onPolygonHover((f) => { hover = f; host.style.cursor = f?.code ? "pointer" : "grab"; g.polygonAltitude(g.polygonAltitude()); })
    .onPolygonClick((f) => f.code && select(f.code))
    .pointsData(markers)
    .pointLat("lat").pointLng("lng")
    .pointColor((m) => (m.code === picked ? SHOCK : originSet.has(m.code) ? "#ffc478" : chanceBy.has(m.code) ? "#ff8a6a" : light() ? "rgba(118,100,78,0.45)" : "rgba(200,210,225,0.5)"))
    .pointAltitude(0.02).pointRadius(0.45)
    .pointLabel((m) => label(m.code))
    .onPointClick((m) => select(m.code))
    .arcColor((a) => [`rgba(255,196,120,${0.35 + a.p})`, `rgba(255,90,54,${0.5 + a.p})`])
    .arcStroke((a) => 0.25 + Math.min(1.2, a.p * 5))
    .arcDashLength(0.45).arcDashGap(0.25)
    .arcDashAnimateTime(reduced() ? 0 : 2200)
    .arcAltitudeAutoScale(0.45)
    .arcLabel((a) => esc(`${a.title}: ${name(a.from)} to ${name(a.to)}, ${pct(a.p)}`))
    .ringColor(() => (t) => `rgba(255,90,54,${(1 - t).toFixed(2)})`)
    .ringMaxRadius(5).ringPropagationSpeed(2.2).ringRepeatPeriod(reduced() ? 0 : 1400)
    .hexBinPointLat((c) => c[0]).hexBinPointLng((c) => c[1]).hexBinPointWeight((c) => c[2])
    .hexBinResolution(4).hexMargin(0.25)
    .hexAltitude((d) => Math.min(0.25, d.sumWeight * 0.05))
    .hexTopColor(() => QLOO).hexSideColor(() => "rgba(62,230,176,0.45)")
    .hexLabel((d) => `Qloo heatmap: affinity ${d.sumWeight.toFixed(2)} in this cell`)
    .labelLat("lat").labelLng("lng").labelText("text").labelSize(0.9).labelDotRadius(0.35)
    .labelColor(() => "rgba(255,240,230,0.92)").labelResolution(2);

  const paintSea = () => {
    g.globeMaterial().color.set(getComputedStyle(document.documentElement).getPropertyValue("--globe-sea").trim() || "#0d1320");
    // Light paper gets a warm off-white sea with a soft rim, so the globe reads as part of the page, not a lamp on it.
    g.globeMaterial().emissive?.set(light() ? "#9c927f" : "#05070c");
    g.polygonStrokeColor(() => (light() ? "rgba(80,64,44,0.22)" : "rgba(255,255,255,0.10)"));
    g.atmosphereColor(light() ? "#e9a184" : SHOCK).atmosphereAltitude(light() ? 0.11 : 0.16);
    g.labelColor(() => (light() ? "rgba(30,24,18,0.9)" : "rgba(255,240,230,0.92)"));
  };
  paintSea();
  // three.js draws a transparent double-sided material in two passes and marks it for a program check between
  // them, every frame. With ~570 country meshes that alone kept the main thread near 100%. The caps face outward,
  // so one pass looks the same. Layers make new materials as data changes; each is caught on the frame it first draws.
  const singlePass = (m) => { if (m.transparent && m.side === 2 && !m.forceSinglePass) m.forceSinglePass = true; }; // 2 is DoubleSide
  g.scene().onBeforeRender = () => g.scene().traverse((o) => {
    if (Array.isArray(o.material)) o.material.forEach(singlePass);
    else if (o.material) singlePass(o.material);
  });
  const onTheme = () => { paintSea(); g.polygonCapColor(g.polygonCapColor()).pointColor(g.pointColor()); };
  window.addEventListener("aftershock:theme", onTheme);
  g.renderer().setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
  const controls = g.controls();
  controls.autoRotate = !reduced();
  controls.autoRotateSpeed = 0.45;
  controls.enableZoom = true;
  controls.minDistance = 160;
  controls.maxDistance = 520;
  host.addEventListener("pointerdown", () => { controls.autoRotate = false; }, { once: true });

  const size = () => g.width(host.clientWidth).height(host.clientHeight);
  size();
  const resize = new ResizeObserver(size);
  resize.observe(host);
  // A WebGL loop costs battery and scroll smoothness while nobody can see it.
  const seen = new IntersectionObserver(([e]) => (e.isIntersecting ? g.resumeAnimation() : g.pauseAnimation()));
  seen.observe(host);

  function focusChance(code) {
    if (!focusId) return chanceBy.get(code);
    const row = detail?.spillover?.forecasts?.find((r) => r.code === code);
    return row ? row.probability * 2.5 : undefined;
  }

  function label(code) {
    if (!code) return "";
    const bits = [`<b>${esc(name(code))}</b>`];
    if (focusId && detail) {
      const row = detail.spillover?.forecasts?.find((r) => r.code === code);
      if (detail.origin_countries?.some((o) => o.code === code)) bits.push("Broke out here");
      else if (row) bits.push(`${rankLabel(detail.spillover.forecasts.indexOf(row) + 1, detail.spillover.forecasts.length)}: ${pct(row.probability)}`);
    } else {
      if (originSet.has(code)) bits.push("A breakout started here this week");
      if (chanceBy.has(code)) bits.push(`${pct(chanceBy.get(code))} chance at least one breakout arrives`);
    }
    return `<div class="globe-tip">${bits.join("<br>")}</div>`;
  }

  function weekLayers() {
    const ranked = [...week.storms].filter((s) => s.top_forecast).sort((a, b) => b.top_forecast.probability - a.top_forecast.probability);
    const arcs = [];
    for (const s of ranked.slice(0, WEEK_ARCS)) {
      const o = s.origin_countries?.[0]?.code, to = s.top_forecast.code;
      const a = at(o), b = at(to);
      if (a && b) arcs.push({ startLat: a.lat, startLng: a.lng, endLat: b.lat, endLng: b.lng, p: s.top_forecast.probability, title: s.title, from: o, to });
    }
    g.arcsData(arcs)
      .ringsData([...originSet].map(at).filter(Boolean))
      .hexBinPointsData([])
      .labelsData([]);
  }

  function titleLayers() {
    const origin = detail.origin_countries || [];
    const rows = (detail.spillover?.forecasts || []).slice(0, ARCS_PER_TITLE);
    const arcs = [];
    for (const o of origin) for (const r of rows) {
      const a = at(o.code), b = at(r.code);
      if (a && b) arcs.push({ startLat: a.lat, startLng: a.lng, endLat: b.lat, endLng: b.lng, p: r.probability, title: detail.title, from: o.code, to: r.code });
    }
    const kit = picked && (detail.launch_kit || []).find((k) => k.code === picked);
    g.arcsData(arcs)
      .ringsData(origin.map((o) => at(o.code)).filter(Boolean))
      .hexBinPointsData(kit?.hotspots?.cells || [])
      .labelsData(rows.map((r) => ({ ...at(r.code), text: `${name(r.code)} ${pct(r.probability)}` })).filter((l) => l.lat != null));
  }

  function repaint() {
    (focusId && detail ? titleLayers : weekLayers)();
    g.polygonCapColor(g.polygonCapColor()).pointColor(g.pointColor());
  }

  function fly(code, altitude, besidePanel = false) {
    const p = at(code);
    if (!p) return;
    // The panel covers the right third of the globe on wide screens; turning the camera east of the target slides
    // the target left, clear of it. The turn scales with altitude, since a closer camera sweeps fewer degrees.
    const shift = besidePanel && innerWidth >= 980 ? altitude * 24 : 0;
    g.pointOfView({ lat: p.lat, lng: p.lng + shift, altitude }, reduced() ? 0 : 1100);
  }

  async function focus(stormId) {
    focusId = stormId;
    picked = null;
    if (!stormId) { detail = null; repaint(); g.pointOfView({ altitude: 2.3 }, reduced() ? 0 : 900); return null; }
    detail = await getStorm(stormId);
    if (focusId !== stormId) return null;
    controls.autoRotate = false;
    repaint();
    // When a forecast follows, the caller selects that country next; one flight there reads better than two.
    if (!detail.spillover?.forecasts?.length) fly(detail.origin_countries?.[0]?.code, 1.6);
    return detail;
  }

  function select(code) {
    picked = code;
    controls.autoRotate = false;
    repaint();
    const hasCells = focusId && detail && (detail.launch_kit || []).some((k) => k.code === code && k.hotspots?.cells?.length);
    // Close enough to read Qloo's city cells, far enough to keep the origin and the arc into this country in view.
    fly(code, hasCells ? 0.85 : 1.4, true);
    onPick?.({ code, storm: focusId ? detail : null });
  }

  repaint();
  g.pointOfView({ lat: 25, lng: 30, altitude: 2.3 });
  return {
    focus, select,
    destroy() { window.removeEventListener("aftershock:theme", onTheme); resize.disconnect(); seen.disconnect(); g.pauseAnimation(); g._destructor?.(); host.replaceChildren(); },
  };
}

/** The panel beside the globe for one country: week view lists the titles involved; title view gives the forecast,
 *  the reason, Qloo's cities and the AI names Qloo confirmed there. */
export function countryPanel(code, storm, week) {
  const head = h("p", { class: "gp-kicker mono" }, storm ? storm.title : "This week");
  if (storm) {
    const rows = storm.spillover?.forecasts || [];
    const row = rows.find((r) => r.code === code);
    const rank = rows.indexOf(row) + 1;
    const isOrigin = storm.origin_countries?.some((o) => o.code === code);
    const kit = (storm.launch_kit || []).find((k) => k.code === code);
    const confirmed = kit?.plan?.confirmed || [];
    return h("div", { class: "gp-body" }, head,
      h("h3", { class: "gp-title" }, name(code)),
      isOrigin ? h("p", { class: "gp-big" }, "Broke out here") : row ? [h("p", { class: "gp-rank mono" }, rankLabel(rank, rows.length)), h("p", { class: "gp-big" }, h("span", { class: "gp-num" }, pct(row.probability)), " chance to chart within 4 weeks")] : h("p", { class: "gp-big" }, "Not in this title's forecast"),
      row?.why ? h("p", { class: "gp-why" }, h("span", { class: "gp-label mono" }, "Why"), `${row.why}.`) : null,
      kit?.hotspots?.places?.length ? h("p", { class: "gp-cities" }, h("span", { class: "gp-label mono qloo-mark" }, "Qloo heatmap"), `Audience lives around ${kit.hotspots.places.join(", ")}`) : null,
      confirmed.length ? h("p", { class: "gp-cities" }, h("span", { class: "gp-label mono qloo-mark" }, "Qloo confirmed"), confirmed.slice(0, 5).map((c) => c.name).join(", ")) : null,
      kit?.brief ? h("a", { class: "btn btn-primary gp-cta", href: `#/plan/${encodeURIComponent(storm.id)}/${encodeURIComponent(code)}` }, `Plan the launch in ${name(code)}`)
        : h("a", { class: "btn gp-cta", href: `#/storm/${encodeURIComponent(storm.id)}` }, "Open the full forecast"));
  }
  const c = (week.map?.countries || []).find((x) => x.code === code);
  const started = week.storms.filter((s) => s.origin_countries?.some((o) => o.code === code));
  return h("div", { class: "gp-body" }, head,
    h("h3", { class: "gp-title" }, name(code)),
    c ? h("p", { class: "gp-big" }, h("span", { class: "gp-num" }, pct(c.chance)), " chance at least one of this week's breakouts charts here") : h("p", { class: "gp-big" }, "No breakout is forecast to arrive here this week"),
    c?.top?.length ? h("ul", { class: "gp-list" }, c.top.map((t) => h("li", null, h("a", { href: `#/storm/${encodeURIComponent(t.id)}` }, t.title), h("span", { class: "mono" }, pct(t.p))))) : null,
    started.length ? h("p", { class: "gp-cities" }, h("span", { class: "gp-label mono" }, "Broke out here"), started.slice(0, 4).map((s) => s.title).join(", ")) : null,
    h("p", { class: "gp-hint" }, "Pick a title above to see where it goes next and Qloo's city heatmap."));
}
