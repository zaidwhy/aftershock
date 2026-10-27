// Home: where this week's breakouts are heading. Built from the `map` block of /data/storms.json.
import { h, errorBox } from "./dom.js";
import { pct } from "./format.js";
import { ISO } from "./iso.js";
import { weekMap } from "./charts.js";

const nameOf = (code, c) => c?.name ?? ISO[code]?.[1] ?? code;
const SHOW = 5;
const ACCESSIBLE = 10;

/** "a 52% chance", with "under 1%" for tiny values. */
export function chanceText(c) {
  const t = pct(c);
  return t === "<1%" ? "a chance under 1%" : `a ${t} chance`;
}
const capital = (t) => t.charAt(0).toUpperCase() + t.slice(1);

export function weekMapSection(map, week, isCurrent) {
  const byCode = new Map(map.countries.map((c) => [c.code, c]));
  const origins = new Set(map.origins);
  const panel = h("div", { class: "wm-panel", "aria-live": "polite" });
  const mapBox = h("div", { class: "map-box" }, h("p", { class: "status", role: "status" }, h("span", { class: "pulse", "aria-hidden": "true" }), "Loading the map..."));
  let chart = null;
  const rows = [];

  const show = (code) => {
    if (!code) return;
    const c = byCode.get(code);
    const name = c?.name ?? chart?.names.get(code) ?? nameOf(code, c);
    const started = origins.has(code) ? `Some of this week's breakouts started in ${name}. ` : "";
    panel.replaceChildren(c
      ? h("p", { class: "plain" }, h("strong", null, `${name}: `), started + `${capital(chanceText(c.chance))} that at least one of this week's breakouts reaches its Top 10. Most likely: `,
          c.top.map((t, i) => [i ? ", " : null, h("a", { href: `#/storm/${encodeURIComponent(t.id)}` }, t.title), " ", h("span", { class: "mono" }, pct(t.p))]).flat())
      : h("p", { class: "plain" }, h("strong", null, `${name}: `), started + `No breakout from this week is forecast to reach ${name}.`));
    chart?.select(code);
    rows.forEach(([k, b]) => b.setAttribute("aria-pressed", String(k === code)));
  };

  const topList = h("ol", { class: "wm-top" }, map.countries.slice(0, SHOW).map((c) => {
    const b = h("button", { type: "button", class: "wm-row", "aria-pressed": "false", onclick: () => show(c.code) },
      h("span", null, c.name), h("span", { class: "muted" }, pct(c.chance)));
    rows.push([c.code, b]);
    return h("li", null, b);
  }));
  const hidden = h("ol", { class: "sr-only" }, map.countries.slice(0, ACCESSIBLE).map((c) => h("li", null,
    `${c.name}: ${chanceText(c.chance)} that at least one of this week's breakouts reaches its Top 10. Most likely: ${c.top.map((t) => `${t.title} ${pct(t.p)}`).join(", ")}.`)));

  weekMap(map, show).then((m) => {
    if (!isCurrent()) return;
    chart = m;
    mapBox.replaceChildren(m.node);
    show(map.countries[0].code);
  }).catch((err) => {
    if (!isCurrent()) return;
    mapBox.replaceChildren(errorBox("the map", err), h("p", { class: "muted" }, "The list below has the same data."));
    show(map.countries[0].code);
  });

  return h("section", { class: "week-map", "aria-labelledby": "wm-h" },
    h("h2", { id: "wm-h" }, "Where this week's breakouts are heading"),
    h("p", { class: "muted" }, "Each country is shaded by the chance that at least one of this week's breakouts reaches its Top 10 in the next 4 weeks. Updated every week from Netflix's public data."),
    mapBox,
    h("p", { class: "legend" }, h("span", { class: "key key-ramp" }), "Stronger colour: higher chance",
      h("span", { class: "key key-origin" }), "Outlined: where this week's breakouts started"),
    h("div", { class: "wm-grid" }, panel,
      h("div", null, h("h3", { class: "wm-h3" }, "Top 5 countries"), topList, hidden)));
}
