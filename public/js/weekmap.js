// Home: where this week's breakouts are heading. Built from the `map` block of /data/storms.json.
// "Follow one show" recolours the same map by one storm's own per-country forecast.
import { h, errorBox } from "./dom.js";
import { pct } from "./format.js";
import { ISO } from "./iso.js";
import { weekMap } from "./charts.js";
import { getStorm } from "./api.js";

const nameOf = (code, c) => c?.name ?? ISO[code]?.[1] ?? code;
const SHOW = 5;
const ACCESSIBLE = 10;
const ALL = "";
const QUICK = 4;
const WEEK_CAPTION = "Each country is shaded by the chance that at least one of this week's trending shows reaches its Top 10 in the next 4 weeks. From Netflix's public data for the week shown.";

/** "a 52% chance", with "under 1%" for tiny values. */
export function chanceText(c) {
  const t = pct(c);
  return t === "<1%" ? "a chance under 1%" : `a ${t} chance`;
}
const capital = (t) => t.charAt(0).toUpperCase() + t.slice(1);
const chanceWords = (p) => (pct(p) === "<1%" ? "under a 1% chance" : `a ${pct(p)} chance`);

/** `storms`: this week's storm list (storms.json); `followId`: a storm id to open the map already following. */
export function weekMapSection(map, week, isCurrent, storms = [], followId = null) {
  const byCode = new Map(map.countries.map((c) => [c.code, c]));
  const origins = new Set(map.origins);
  const panel = h("div", { class: "wm-panel", "aria-live": "polite" });
  const mapBox = h("div", { class: "map-box" }, h("p", { class: "status", role: "status" }, h("span", { class: "pulse", "aria-hidden": "true" }), "Loading the map..."));
  let chart = null;
  let rows = [];
  let current = map.countries[0].code;
  let followed = null; // { id, title, detail, names, forecasts: Map, origins: Set, horizon }
  let req = 0;

  const ranked = [...storms].sort((a, b) => (b.top_forecast?.probability ?? -1) - (a.top_forecast?.probability ?? -1));

  const kitLines = (f, code) => {
    const row = (f.detail.launch_kit || []).find((r) => r.code === code);
    if (!row) return [];
    const places = (row.hotspots?.places || []).slice(0, 3);
    const picks = (row.plan?.confirmed || []).map((x) => x.name).filter(Boolean).slice(0, 4);
    return [
      places.length ? h("p", { class: "plain" }, h("strong", null, "Where its audience lives: "), places.join(", ")) : null,
      picks.length ? h("p", { class: "plain" }, h("strong", null, "Partners Qloo supports: "), picks.join(", ")) : null,
    ];
  };

  const showFollowed = (code, name) => {
    const f = followed;
    const p = f.forecasts.get(code);
    const line = p != null
      ? `${f.title} in ${name}: ${chanceWords(p)} it reaches the Top 10 in the next ${f.horizon} weeks.`
      : f.origins.has(code) ? `${f.title} is popular in ${name}.`
        : `${f.title} in ${name}: no forecast. It is not expected to reach the Top 10 there in the next ${f.horizon} weeks.`;
    panel.replaceChildren(h("p", { class: "plain" }, line),
      ...(p != null ? kitLines(f, code) : []),
      h("p", { class: "plain" }, h("a", { href: `#/storm/${encodeURIComponent(f.id)}` }, "Full launch plan")));
  };

  const show = (code) => {
    if (!code) return;
    current = code;
    const c = byCode.get(code);
    const name = c?.name ?? followed?.names.get(code) ?? chart?.names.get(code) ?? nameOf(code, c);
    if (followed) showFollowed(code, name);
    else {
      const started = origins.has(code) ? `Some of this week's trending shows got popular first in ${name}. ` : "";
      panel.replaceChildren(c
        ? h("p", { class: "plain" }, h("strong", null, `${name}: `), started + `${capital(chanceText(c.chance))} that at least one of this week's breakouts reaches its Top 10. Most likely: `,
            c.top.map((t, i) => [i ? ", " : null, h("a", { href: `#/storm/${encodeURIComponent(t.id)}` }, t.title), " ", h("span", { class: "mono" }, pct(t.p))]).flat())
        : h("p", { class: "plain" }, h("strong", null, `${name}: `), started + `None of this week's trending shows is predicted to reach ${name}.`));
    }
    chart?.select(code);
    rows.forEach(([k, b]) => b.setAttribute("aria-pressed", String(k === code)));
  };

  const topOl = h("ol", { class: "wm-top" });
  const hidden = h("ol", { class: "sr-only" });
  const topHead = h("h3", { class: "wm-h3" }, "Top 5 countries");
  const caption = h("p", { class: "muted" }, WEEK_CAPTION);
  const legendText = h("span", null, "Stronger colour: higher chance");
  const originText = h("span", null, "Outlined: where this week's trending shows got popular first");

  const fillLists = () => {
    const items = followed
      ? [...followed.forecasts].sort((a, b) => b[1] - a[1]).map(([code, p]) => {
        const nm = followed.names.get(code) ?? nameOf(code);
        return { code, name: nm, p, sr: `${nm}: ${chanceWords(p)} that ${followed.title} reaches its Top 10 in the next ${followed.horizon} weeks.` };
      })
      : map.countries.map((c) => ({ code: c.code, name: c.name, p: c.chance,
        sr: `${c.name}: ${chanceText(c.chance)} that at least one of this week's breakouts reaches its Top 10. Most likely: ${c.top.map((t) => `${t.title} ${pct(t.p)}`).join(", ")}.` }));
    rows = [];
    topOl.replaceChildren(...items.slice(0, SHOW).map((c) => {
      const b = h("button", { type: "button", class: "wm-row", "aria-pressed": String(c.code === current), onclick: () => show(c.code) },
        h("span", null, c.name), h("span", { class: "muted" }, pct(c.p)));
      rows.push([c.code, b]);
      return h("li", null, b);
    }));
    hidden.replaceChildren(...items.slice(0, ACCESSIBLE).map((c) => h("li", null, c.sr)));
    topHead.textContent = followed ? `${followed.title}: top 5 countries` : "Top 5 countries";
  };

  // The control: a select plus quick chips for the top titles.
  const select = h("select", { id: "wm-follow", class: "wm-select", onchange: () => follow(select.value) },
    h("option", { value: ALL }, "All of this week's trending shows"),
    ranked.map((s) => h("option", { value: s.id }, s.label ?? s.title)));
  const chips = ranked.slice(0, QUICK).map((s) => {
    const b = h("button", { type: "button", class: "chip", "aria-pressed": "false", onclick: () => follow(followed?.id === s.id ? ALL : s.id) }, s.label ?? s.title);
    b.dataset.id = s.id;
    return b;
  });
  const syncControl = () => {
    const id = followed?.id ?? ALL;
    select.value = id;
    chips.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.id === id)));
  };

  const apply = (f) => {
    followed = f;
    if (f) {
      chart?.recolor(f.forecasts, f.origins, `the chance that ${f.title} reaches each country`);
      caption.textContent = `Each country is shaded by the chance that ${f.title} reaches its Top 10 in the next ${f.horizon} weeks. Outlined: where it is popular now.`;
      legendText.textContent = "Stronger colour: higher chance this show reaches it";
      originText.textContent = "Outlined: where this show is popular now";
    } else {
      chart?.recolor();
      caption.textContent = WEEK_CAPTION;
      legendText.textContent = "Stronger colour: higher chance";
      originText.textContent = "Outlined: where this week's trending shows got popular first";
    }
    const best = f ? [...f.forecasts].sort((a, b) => b[1] - a[1])[0]?.[0] : map.countries[0].code;
    current = best ?? current;
    syncControl();
    fillLists();
    show(current);
  };

  const follow = async (id) => {
    const mine = ++req;
    if (!id) { apply(null); return; }
    mapBox.setAttribute("aria-busy", "true");
    try {
      const detail = await getStorm(id);
      if (mine !== req || !isCurrent()) return;
      const fcs = detail.spillover?.forecasts || [];
      apply({
        id, title: ranked.find((x) => x.id === id)?.label ?? detail.title, detail,
        names: new Map(fcs.map((x) => [x.code, x.name])),
        forecasts: new Map(fcs.map((x) => [x.code, x.probability])),
        origins: new Set((detail.origin_countries || []).map((o) => o.code)),
        horizon: detail.spillover?.horizon_weeks ?? 4,
      });
    } catch (err) {
      if (mine !== req || !isCurrent()) return;
      syncControl(); // back to the previous title; the map keeps its colouring
      panel.replaceChildren(errorBox("that title's forecast", err, () => follow(id)));
    } finally {
      if (mine === req) mapBox.removeAttribute("aria-busy");
    }
  };

  fillLists();
  weekMap(map, show).then((m) => {
    if (!isCurrent()) return;
    chart = m;
    mapBox.replaceChildren(m.node);
    if (followed) apply(followed); else show(current);
  }).catch((err) => {
    if (!isCurrent()) return;
    mapBox.replaceChildren(errorBox("the map", err), h("p", { class: "muted" }, "The list below has the same data."));
    show(current);
  });
  show(current);
  if (followId && ranked.some((s) => s.id === followId)) follow(followId);

  return h("section", { class: "week-map", "aria-labelledby": "wm-h" },
    h("h2", { id: "wm-h" }, "Where this week's trending shows are heading"),
    caption,
    ranked.length ? h("div", { class: "wm-follow" },
      h("label", { for: "wm-follow" }, "Follow one show"), select,
      h("div", { class: "wm-chips", role: "group", "aria-label": "Quick picks: this week's top shows" }, chips)) : null,
    mapBox,
    h("p", { class: "legend" }, h("span", { class: "key key-ramp" }), legendText,
      h("span", { class: "key key-origin" }), originText),
    h("div", { class: "wm-grid" }, panel,
      h("div", null, topHead, topOl, hidden)));
}
