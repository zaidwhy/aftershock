// "On Netflix" panel and the title lookup box. Plain words first; the chance figures sit under Details.
import { h, errorBox, add } from "./dom.js";
import { lookupTitle } from "./api.js";
import { pct } from "./format.js";
import { ISO } from "./iso.js";

const name = (code) => ISO[code]?.[1] ?? code;
const day = (iso) => new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const list = (items) => (items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`);
const SHOWN = 12;
const NEXT = 5;
const norm = (t) => t.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();

/** One title's Netflix history. `typed` is what the visitor typed, to say so when the match is only close;
 *  `pick(title)` makes the "did you mean" buttons; both optional. */
export function titlePanel(rec, typed, pick) {
  const first = rec.countries.filter(([, w]) => w === rec.first_week).map(([c]) => name(c));
  const later = rec.countries.filter(([, w]) => w !== rec.first_week);
  const close = typed && !norm(rec.show).startsWith(norm(typed).replace(/ season \d+$/, ""));
  const fc = rec.forecast;
  const next = fc?.next?.slice(0, NEXT) ?? [];
  const reasons = next.filter((n) => n.why);
  return h("section", { class: "on-netflix", "aria-label": `${rec.title} on Netflix` },
    h("h3", null, "On Netflix ", h("span", { class: "tag" }, rec.kind === "film" ? "Film" : "TV")),
    close ? h("p", { class: "muted" }, `Closest match to "${typed}":`) : null,
    h("p", { class: "plain" }, h("strong", null, rec.title), ` first entered a Netflix Top 10 on ${day(rec.first_week)}`,
      first.length > 6 ? ` and entered the Top 10 in ${first.length} countries in its first week.` : ` in ${list(first)}.`),
    later.length
      ? [h("p", { class: "plain" }, `${first.length > 6 ? "Countries it added afterwards" : "It has since charted in"} (${later.length}):`),
         h("ul", { class: "timeline" }, later.slice(0, SHOWN).map(([c, w]) => h("li", null, h("span", null, name(c)), h("span", { class: "muted mono" }, day(w))))),
         later.length > SHOWN ? h("p", { class: "muted" }, `and ${later.length - SHOWN} more`) : null]
      : h("p", { class: "plain" }, first.length > 6 ? "No later additions." : "It has not charted anywhere else yet."),
    rec.storm_id ? h("p", { class: "plain" }, "It is one of this week's breakouts. ", h("a", { href: `#/storm/${encodeURIComponent(rec.storm_id)}` }, "See its storm page and forecast")) : null,
    next.length ? [
      h("p", { class: "plain" }, "Likely next:"),
      h("ul", { class: "timeline" }, next.map((n) => h("li", null, h("span", null, n.name), h("span", { class: "mono" }, pct(n.probability))))),
      h("details", { class: "row-details" }, h("summary", null, "Details"),
        h("p", null, `Each percentage is the chance the title charts in that country within ${fc.horizon_weeks} weeks of its debut, from Netflix's own history of past breakouts. It is a forecast, not a promise.`),
        reasons.map((n) => h("p", null, `${n.name}: ${n.why}.`)))] : null,
    rec.storm_id || !rec.still_spreading || next.length ? null
      : h("p", { class: "plain" }, rec.forecast_note ? "Likely next: not forecast, it is already charting in many countries." : "Likely next: not enough history to forecast."),
    pick && rec.others?.length ? h("p", { class: "muted" }, "Also matching: ",
      rec.others.map((o) => h("button", { type: "button", class: "btn btn-small", onclick: () => pick(o.title) }, o.title))) : null);
}

/** Run a lookup in parallel with another request; render the panel into `box` only when the title is found. */
export function attachTitlePanel(box, typed, isCurrent) {
  box.replaceChildren();
  lookupTitle(typed).then((rec) => { if (rec && isCurrent()) box.replaceChildren(titlePanel(rec, typed)); }).catch(() => {});
}

/** The home page lookup: any title, results inline, a polite message when there is no match. */
export function lookupBox(isCurrent) {
  const out = h("div", { "aria-live": "polite" });
  const input = h("input", { id: "nf-title", type: "text", autocomplete: "off", maxlength: "80", placeholder: "Stranger Things", required: true });
  const btn = h("button", { type: "submit", class: "btn btn-primary" }, "Look up");
  const run = (text) => {
    const typed = (text ?? input.value).trim();
    if (!typed) { out.replaceChildren(h("p", { class: "status" }, "Type a show or film name.")); input.focus(); return; }
    input.value = typed;
    btn.disabled = true;
    out.replaceChildren(h("p", { class: "status", role: "status" }, h("span", { class: "pulse", "aria-hidden": "true" }), "Looking..."));
    lookupTitle(typed).then((rec) => {
      if (!isCurrent()) return;
      out.replaceChildren();
      add(out, rec ? titlePanel(rec, typed, run)
        : h("p", { class: "status" }, "No close match in Netflix's Top 10 since 2024. Check the spelling, or try the title as Netflix lists it."));
    }).catch((err) => { if (isCurrent()) out.replaceChildren(errorBox("the title lookup", err)); })
      .finally(() => { btn.disabled = false; });
  };
  return h("section", { class: "lookup", "aria-labelledby": "nf-h" },
    h("h2", { id: "nf-h" }, "Look up any title"),
    h("p", { class: "muted" }, "See when a show or film first reached Netflix's Top 10, where it has charted since, and where it may go next."),
    h("form", { class: "lookup-form", novalidate: true, onsubmit: (e) => { e.preventDefault(); run(); } },
      h("label", { for: "nf-title", class: "sr-only" }, "Show or film"), input, btn),
    out);
}
