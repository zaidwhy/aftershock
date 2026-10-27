import { h, s } from "./dom.js";
import { BANDS, monthLabel, views, pct } from "./format.js";
import { ISO, NUMERIC_TO_CODE, MICRO_LONLAT } from "./iso.js";

const WORLD_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-110m.json";

// Deterministic noise so the trace looks the same on every load.
function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Seismograph trace of monthly pageviews. Amplitude follows the views, jitter is cosmetic. */
export function seismograph(replay) {
  const data = replay.monthly_views;
  const W = 960, H = 260, mid = 118, pad = 20;
  const max = Math.max(...data.map((d) => d[1]));
  const peakIdx = data.findIndex((d) => d[1] === max);
  const N = 520;
  const rand = rng(7 + data.length);
  const ampAt = (x) => {
    const f = (x / (N - 1)) * (data.length - 1);
    const i = Math.min(Math.floor(f), data.length - 2);
    const t = f - i;
    const v = data[i][1] * (1 - t) + data[i + 1][1] * t;
    // Linear, so a 90x spike reads as 90x; the jitter is cosmetic, the envelope is the data.
    return 2 + 100 * (v / max);
  };
  let d = "";
  for (let x = 0; x < N; x++) {
    const px = pad + (x / (N - 1)) * (W - 2 * pad);
    const py = mid + (rand() * 2 - 1) * ampAt(x) * (x % 2 ? 1 : 0.8);
    d += `${x ? "L" : "M"}${px.toFixed(1)} ${py.toFixed(1)}`;
  }
  const peakX = pad + (peakIdx / (data.length - 1)) * (W - 2 * pad);
  const ticks = data.map((m, i) => {
    const x = pad + (i / (data.length - 1)) * (W - 2 * pad);
    return s("g", null,
      s("line", { x1: x, x2: x, y1: mid + 112, y2: mid + 118, class: "sg-tick" }),
      s("text", { x, y: H - 2, class: "sg-label", "text-anchor": i === 0 ? "start" : i === data.length - 1 ? "end" : "middle" }, monthLabel(m[0]).replace(" 20", " '")));
  });
  const calloutAnchor = peakX > W * 0.7 ? "end" : "start";
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, class: "seismo", role: "img",
    "aria-label": `Seismograph of English Wikipedia monthly views for ${replay.song} by ${replay.artist}. ${data.map((m) => `${monthLabel(m[0])}: ${views(m[1])}`).join(", ")}.` },
    s("line", { x1: pad, x2: W - pad, y1: mid, y2: mid, class: "sg-axis" }),
    s("path", { d, class: "sg-trace", pathLength: 1 }),
    s("line", { x1: peakX, x2: peakX, y1: 4, y2: mid + 112, class: "sg-peak" }),
    s("text", { x: peakX + (calloutAnchor === "end" ? -8 : 8), y: 16, class: "sg-call", "text-anchor": calloutAnchor }, `${views(max)} views, ${monthLabel(data[peakIdx][0])}`),
    ticks);
  return svg;
}

/** Diverging bar pairs: show audience vs artist audience over six age bands. */
export function generationGap(showAge, artistAge, label) {
  const W = 300, H = 112, zero = 50, scale = 42, bw = 14;
  const colW = (W - 10) / BANDS.length;
  const g = [];
  BANDS.forEach(([key, short], i) => {
    const x0 = 5 + i * colW + (colW - 2 * bw - 2) / 2;
    const bars = [[showAge?.[key], "bar-show", "Show"], [artistAge?.[key], "bar-artist", "Artist"]];
    bars.forEach(([v, cls, who], j) => {
      if (v == null) return;
      const hgt = Math.abs(v) * scale;
      g.push(s("rect", { x: x0 + j * (bw + 2), y: v >= 0 ? zero - hgt : zero, width: bw, height: Math.max(hgt, 0.5), class: cls }, s("title", null, `${who}, ${short}: ${v >= 0 ? "+" : "-"}${Math.abs(v).toFixed(2)}`)));
    });
    g.push(s("text", { x: 5 + i * colW + colW / 2, y: H - 2, class: "ax-label", "text-anchor": "middle" }, short));
  });
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, class: "gap-chart", role: "img", "aria-label": label },
    s("line", { x1: 0, x2: W, y1: zero, y2: zero, class: "sg-axis" }), g);
  const rows = BANDS.map(([key, , long]) => h("tr", null, h("th", { scope: "row" }, long), h("td", null, showAge?.[key]?.toFixed(2) ?? "n/a"), h("td", null, artistAge?.[key]?.toFixed(2) ?? "n/a")));
  const table = h("table", { class: "sr-only" }, h("caption", null, label),
    h("thead", null, h("tr", null, h("th", { scope: "col" }, "Age band"), h("th", { scope: "col" }, "Show audience"), h("th", { scope: "col" }, "Artist audience"))), h("tbody", null, rows));
  return h("div", { class: "gap-wrap" }, svg, table);
}

/** Ripple panel: one row per song. Unresolved songs are reported plainly. */
export function ripplePanel(ripple) {
  const resolved = ripple.songs.filter((x) => x.resolved !== false);
  const maxScore = Math.max(0.01, ...resolved.map((x) => x.score ?? 0));
  const items = ripple.songs.map((x) => {
    if (x.resolved !== false && x.score == null) {
      return h("li", { class: "song song-bad" },
        h("div", { class: "song-head" }, h("strong", null, x.song), x.artist ? h("span", { class: "muted" }, ` - ${x.artist}`) : null),
        h("p", { class: "not-found" }, "Qloo has no audience profile for this artist, so there is no age gap and no score.",
          x.prior_daily_views != null ? ` Prior Wikipedia views ${Math.round(x.prior_daily_views)}/day (context).` : ""));
    }
    if (x.resolved === false) {
      return h("li", { class: "song song-bad" },
        h("div", { class: "song-head" }, h("strong", null, x.song), x.artist ? h("span", { class: "muted" }, ` - ${x.artist}`) : null),
        h("p", { class: "not-found" }, "Not found in Qloo. This song or artist could not be matched, so it has no score."));
    }
    const graded = x.status === "graded";
    return h("li", { class: "song" },
      h("div", { class: "song-head" },
        h("div", null, h("strong", null, x.song), h("span", { class: "muted" }, ` - ${x.artist}`)),
        x.status ? h("span", { class: `tag ${graded ? "tag-graded" : "tag-pending"}` }, graded ? "graded" : "pending") : null),
      h("div", { class: "score-row" },
        h("span", { class: "mono score-num", "aria-label": `ripple score ${x.score.toFixed(2)}` }, x.score.toFixed(2)),
        h("div", { class: "bar", role: "img", "aria-label": `Score ${x.score.toFixed(2)} out of a panel maximum of ${maxScore.toFixed(2)}` },
          h("span", { style: `width:${Math.max(2, (x.score / maxScore) * 100)}%` }))),
      h("p", { class: "song-math mono" }, [
          x.age_gap != null ? `age gap ${x.age_gap.toFixed(2)} (score)` : "age gap n/a",
          x.prior_daily_views != null ? `prior Wikipedia views ${Math.round(x.prior_daily_views)}/day (context)` : "no Wikipedia page (context)",
          x.fit != null ? `taste fit ${x.fit.toFixed(2)} (context)` : null].filter(Boolean).join(" | "),
        graded && x.observed_ratio != null ? ` | observed views ratio ${x.observed_ratio.toFixed(1)}x` : ""),
      generationGap(ripple.show_age, x.artist_age, `Generation gap for ${x.song} by ${x.artist}: show audience versus artist audience by age band, over-index from -1 to +1.`));
  });
  return h("div", { class: "ripple" },
    h("p", { class: "legend" }, h("span", { class: "key key-show" }), "Show audience", h("span", { class: "key key-artist" }), "Artist audience", h("span", { class: "muted" }, " (over-index by age band)")),
    h("ol", { class: "songs" }, items));
}

/** Choropleth of forecast probabilities. Resolves with the svg or throws if libs/atlas fail to load. */
export async function forecastMap(forecasts, origins) {
  if (!window.d3 || !window.topojson) throw new Error("d3 or topojson-client did not load from cdn.jsdelivr.net.");
  const res = await fetch(WORLD_URL);
  if (!res.ok) throw new Error(`world-atlas returned HTTP ${res.status} from cdn.jsdelivr.net.`);
  const world = await res.json();
  const { d3, topojson } = window;
  const feats = topojson.feature(world, world.objects.countries).features;
  const W = 960, H = 500;
  const proj = d3.geoNaturalEarth1().fitExtent([[6, 6], [W - 6, H - 6]], { type: "Sphere" });
  const path = d3.geoPath(proj);
  const byCode = new Map(forecasts.map((f) => [f.code, f]));
  const originSet = new Set(origins.map((o) => o.code));
  const maxP = Math.max(0.01, ...forecasts.map((f) => f.probability));
  const svg = d3.create("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("class", "world").attr("role", "img")
    .attr("aria-label", `World map shaded by forecast probability. Top: ${forecasts.slice(0, 3).map((f) => `${f.name} ${pct(f.probability)}`).join(", ")}. A full table follows.`);
  svg.append("path").attr("d", path({ type: "Sphere" })).attr("class", "map-sphere");
  svg.append("g").selectAll("path").data(feats).join("path").attr("d", path).attr("class", (d) => {
    const code = NUMERIC_TO_CODE[+d.id];
    return "country" + (originSet.has(code) ? " is-origin" : "") + (byCode.has(code) ? " has-fc" : "");
  }).attr("style", (d) => {
    const f = byCode.get(NUMERIC_TO_CODE[+d.id]);
    if (!f) return null;
    const t = Math.round(12 + (f.probability / maxP) * 88);
    return `fill:color-mix(in srgb, var(--accent) ${t}%, var(--map-base))`;
  }).append("title").text((d) => {
    const code = NUMERIC_TO_CODE[+d.id];
    const f = byCode.get(code);
    const name = ISO[code]?.[1] || d.properties?.name || "Unlisted";
    return originSet.has(code) ? `${name}: origin country` : f ? `${name}: ${pct(f.probability)}` : `${name}: no forecast`;
  });
  // Outlines that project to a few pixels (or have no 110m outline at all) get a dot at their centroid.
  const SMALL_AREA = 150;
  const dots = [];
  const seen = new Set();
  feats.forEach((d) => {
    const code = NUMERIC_TO_CODE[+d.id];
    if (!byCode.has(code) || originSet.has(code) || path.area(d) >= SMALL_AREA) return;
    seen.add(code);
    dots.push([code, proj(d3.geoCentroid(d))]);
  });
  forecasts.forEach((f) => {
    if (!seen.has(f.code) && MICRO_LONLAT[f.code] && !originSet.has(f.code)) dots.push([f.code, proj(MICRO_LONLAT[f.code])]);
  });
  svg.append("g").attr("class", "fc-dots").selectAll("circle").data(dots.filter(([, xy]) => xy)).join("circle")
    .attr("cx", ([, xy]) => xy[0]).attr("cy", ([, xy]) => xy[1])
    .attr("r", ([c]) => 3.5 + (byCode.get(c).probability / maxP) * 4.5)
    .attr("class", "fc-dot")
    .attr("style", ([c]) => `fill:color-mix(in srgb, var(--accent) ${Math.round(12 + (byCode.get(c).probability / maxP) * 88)}%, var(--map-base))`)
    .append("title").text(([c]) => `${ISO[c]?.[1] || c}: ${pct(byCode.get(c).probability)}`);
  return svg.node();
}

/** Dumbbell chart: per row, a real-spike marker and a placebo-spike marker on one shared axis with a zero line.
 *  Drawn at the container's pixel width (viewBox equals the width), so text keeps its CSS size; redrawn on resize. */
export function dumbbell(rows, label) {
  const f2 = (v) => (v >= 0 ? v.toFixed(2) : "-" + Math.abs(v).toFixed(2));
  const vals = rows.flatMap((r) => [r.real, r.placebo]);
  const lo = Math.min(-0.2, Math.floor(Math.min(...vals) * 10) / 10);
  const hi = Math.max(0.4, Math.ceil(Math.max(...vals) * 10) / 10);
  const ticks = [];
  for (let v = lo; v <= hi + 1e-9; v += 0.1) ticks.push(Math.round(v * 10) / 10);
  const draw = (W) => {
    const wide = W >= 560;
    const labelW = wide ? 200 : 0, valsW = wide ? 190 : 0, pad = 18;
    const x0 = labelW + pad, x1 = W - valsW - pad;
    const x = (v) => x0 + ((v - lo) / (hi - lo)) * (x1 - x0);
    const rowH = wide ? 46 : 74, top = 6, axisH = 26;
    const H = top + rows.length * rowH + axisH;
    const g = [];
    // Wide: grid lines run the full height. Narrow: labels sit above each plot, so lines only span each plot band.
    const bands = wide ? [[top, H - axisH]] : rows.map((_, i) => [top + i * rowH + 44, top + i * rowH + 68]);
    ticks.forEach((v) => {
      bands.forEach(([y1, y2]) => g.push(s("line", { x1: x(v), x2: x(v), y1, y2, class: v === 0 ? "db-zero" : "db-grid" })));
      g.push(s("text", { x: x(v), y: H - 8, class: "ax-label db-tick", "text-anchor": "middle" }, f2(v)));
    });
    rows.forEach((r, i) => {
      const t = top + i * rowH;
      const y = wide ? t + rowH / 2 : t + 56;
      const vals = `${f2(r.real)} real, ${f2(r.placebo)} placebo`;
      g.push(wide
        ? s("text", { x: 0, y: y + 4, class: "db-label" }, r.label)
        : s("text", { x: 0, y: t + 16, class: "db-label" }, r.label),
        wide ? s("text", { x: W, y: y + 4, class: "db-vals", "text-anchor": "end" }, vals)
          : s("text", { x: 0, y: t + 34, class: "db-vals" }, vals),
        s("line", { x1: x(r.real), x2: x(r.placebo), y1: y, y2: y, class: "db-link" }),
        s("circle", { cx: x(r.placebo), cy: y, r: 6, class: "db-placebo" }, s("title", null, `${r.label}, placebo spike: ${f2(r.placebo)}`)),
        s("circle", { cx: x(r.real), cy: y, r: 6.5, class: "db-real" }, s("title", null, `${r.label}, real spike: ${f2(r.real)}`)));
    });
    return s("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, class: "dumbbell", role: "img", "aria-label": label }, g);
  };
  const table = h("table", { class: "sr-only" }, h("caption", null, label),
    h("thead", null, h("tr", null, ["Signal", "Real spike", "Placebo spike"].map((t) => h("th", { scope: "col" }, t)))),
    h("tbody", null, rows.map((r) => h("tr", null, h("th", { scope: "row" }, r.label), h("td", null, f2(r.real)), h("td", null, f2(r.placebo))))));
  const wrap = h("div", { class: "db-wrap" });
  const holder = h("div", { class: "db-svg" });
  wrap.append(holder, table);
  let last = 0;
  const render = () => {
    const w = Math.round(holder.clientWidth);
    if (!w || w === last) return;
    last = w;
    holder.replaceChildren(draw(w));
  };
  if (window.ResizeObserver) new ResizeObserver(render).observe(holder);
  else window.addEventListener("resize", render);
  requestAnimationFrame(render);
  return wrap;
}

/** Small per-country map of where the title's audience concentrates: outline fitted to the box,
 *  one dot per heatmap cell (opacity by weight). Territories with no 110m outline fit the cells' bounds. */
export async function hotspotMap(code, cells) {
  if (!window.d3 || !window.topojson || !cells?.length) return null;
  const { d3, topojson } = window;
  if (!hotspotMap.world) hotspotMap.world = fetch(WORLD_URL).then((r) => { if (!r.ok) throw new Error("atlas"); return r.json(); });
  const world = await hotspotMap.world;
  const W = 260, H = 180, pad = 8;
  const numeric = ISO[code]?.[0];
  const feat = topojson.feature(world, world.objects.countries).features.find((f) => +f.id === numeric);
  const points = { type: "MultiPoint", coordinates: cells.map((c) => [c[1], c[0]]) };
  const proj = d3.geoMercator();
  const path = d3.geoPath(proj);
  const svg = d3.create("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("class", "hs-map").attr("role", "img")
    .attr("aria-label", `Map of the ${cells.length} strongest audience cells in ${ISO[code]?.[1] || code}.`);
  if (feat) {
    // Keep only the polygons that hold cells, so far-flung parts (Alaska, French Guiana) do not shrink the outline.
    const g = feat.geometry;
    const polys = g.type === "MultiPolygon" ? g.coordinates : [g.coordinates];
    const used = polys.filter((p) => cells.some((c) => d3.geoContains({ type: "Polygon", coordinates: p }, [c[1], c[0]])));
    const shape = { type: "MultiPolygon", coordinates: used.length ? used : polys };
    proj.fitExtent([[pad, pad], [W - pad, H - pad]], shape);
    svg.append("path").attr("d", path(shape)).attr("class", "hs-outline");
  } else {
    proj.fitExtent([[pad + 10, pad + 10], [W - pad - 10, H - pad - 10]], points);
    svg.append("rect").attr("x", 0.5).attr("y", 0.5).attr("width", W - 1).attr("height", H - 1).attr("class", "hs-frame");
  }
  // A single cell (or cells at one point) has no extent to fit: centre on it at a fixed zoom.
  const first = proj([cells[0][1], cells[0][0]]);
  if (!first || !first.every(Number.isFinite)) proj.center([cells[0][1], cells[0][0]]).scale(3000).translate([W / 2, H / 2]);
  svg.append("g").selectAll("circle").data(cells.filter((c) => proj([c[1], c[0]]))).join("circle")
    .attr("cx", (c) => proj([c[1], c[0]])[0]).attr("cy", (c) => proj([c[1], c[0]])[1])
    .attr("r", 2.6).attr("class", "hs-dot").attr("fill-opacity", (c) => (0.15 + 0.8 * c[2]).toFixed(2));
  return svg.node();
}
