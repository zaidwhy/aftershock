// "Plan a launch": the agent's steps for one title in one country appear one by one, then the Launch Brief.
// The steps and the brief are built by aftershock/launch_brief.py and ride on each launch_kit row as `brief`.
import { h, loading, errorBox, add } from "./dom.js";
import { getStorms, getStorm } from "./api.js";
import { hotspotMap } from "./charts.js";
import { rejectedList } from "./rejected.js";
import { artistName } from "./artists.js";

const STEP_MS = 450;
const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const planHref = (id, code) => `#/plan/${encodeURIComponent(id)}/${encodeURIComponent(code)}`;
const kitRows = (st) => (st.launch_kit || []).filter((r) => r.brief);

const DEFAULT_SEARCH = 8;
const MIN_CONFIRMED = 3;

/** The plan to open on. The weekly run picks it server-side (`featured_plan` in the storms list: aftershock/api.py
 *  featured_plan, rule in the README). Without it (older data, mock mode) the older rule: among the week's top storms,
 *  the first title-specific kit country where Qloo confirmed at least MIN_CONFIRMED AI picks, else the top storm's
 *  first kit country. {id, title, code, country}, or null. */
export async function defaultPlan() {
  const { storms, featured_plan: featured } = await getStorms();
  if (featured?.id && featured.code && featured.title && featured.country) return featured;
  const ranked = storms.filter((s) => s.has_kit).sort((a, b) => (b.top_forecast?.probability ?? -1) - (a.top_forecast?.probability ?? -1));
  let fallback = null;
  for (const s of ranked.slice(0, DEFAULT_SEARCH)) {
    const rows = kitRows(await getStorm(s.id));
    const pick = (row) => ({ id: s.id, title: s.title, code: row.code, country: row.brief.brief.country });
    const grounded = rows.find((r) => !r.generic && (r.plan?.confirmed?.length ?? 0) >= MIN_CONFIRMED);
    if (grounded) return pick(grounded);
    if (!fallback && rows[0]) fallback = pick(rows[0]);
  }
  return fallback;
}

const joinList = (items) => (items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items.at(-1)}`);

/** Plain-text-to-Markdown for the downloaded file, built from the brief alone. */
export function briefMarkdown(b, url) {
  const list = (items) => items.map((x) => `- ${x}`);
  const partners = b.partners.flatMap((g) => [`**${g.label}**`, ...list(g.picks.map((p) =>
    p.name + (p.source === "ai_confirmed" ? (p.also_in_qloo_kit ? " (AI pick confirmed by Qloo; also in Qloo's kit)" : " (AI pick confirmed by Qloo)") : " (Qloo's kit)"))), ""]);
  return [`# Launch brief: ${b.title} in ${b.country}`, "", b.headline, "",
    `## Summary`, b.summary, `*${b.summary_source === "template" ? "Template summary" : "Written by AI from this brief; every name and number in it checked against the brief"}.*`, "",
    ...((b.moves || []).length ? ["## This week's moves", ...(b.moves || []).map((m) => `- **${m.buyer}:** ${m.text}`), ""] : []),
    "## Where to start", ...(b.cities.length ? list(b.cities) : ["Qloo returned no named places for this country."]), "",
    ...((b.event_ideas || []).length ? ["## Event ideas", ...list(b.event_ideas.map((e) => e.text)), ""] : []),
    "## Partners to approach", ...partners,
    "## What not to claim", ...list(b.avoid), "",
    "## Evidence", ...list(b.evidence), "", url ? `Source: ${url}` : ""].join("\n");
}

function stepCard(s, n) {
  return h("li", { class: "plan-step" },
    h("p", { class: "plan-step-n mono" }, `Step ${n}`),
    h("h3", null, s.title),
    h("p", { class: "plan-found" }, s.found),
    s.note ? h("p", { class: "plan-note" }, s.note) : null,
    rejectedList(s.rejected),
    s.decision ? h("p", { class: "plan-decision" }, h("span", { class: "plan-rule mono" }, "Rule applied"), " ", s.decision) : null);
}

/** Four stat tiles for the top of the brief, in the home page's proof-tile style. */
function statTiles(b, row) {
  const plan = row.plan || {}, dropped = plan.dropped || {};
  const proposed = (plan.confirmed?.length ?? 0) + (dropped.not_placed ?? 0) + (dropped.not_in_qloo ?? 0);
  const ideas = (b.event_ideas || []).length;
  const checked = b.partner_basis === "ai_confirmed"
    ? [`${plan.confirmed.length} of ${proposed}`, "AI picks confirmed by Qloo"]
    : ["Qloo's own kit", "fewer than 3 AI picks confirmed"];
  const tiles = [
    [b.chance_label, `chance to chart in ${b.horizon_weeks} weeks`],
    [`${b.rank} of ${b.of_countries}`, "countries, ranked by chance"],
    checked,
    [String(ideas), ideas === 1 ? "event idea" : "event ideas"],
  ];
  return h("div", { class: "proof plan-tiles", role: "group", "aria-label": "Brief at a glance" },
    tiles.map(([v, n]) => h("div", { class: "proof-item" }, h("p", { class: "proof-v" }, v), h("p", { class: "proof-n" }, n))));
}

/** Hotspot cities as labelled dots on the country map (the storm page's renderer); event-idea cities get a ring.
 *  The same facts follow as text, so the map is never the only carrier. Nothing without named cities with coordinates. */
function cityMap(b, row) {
  const hs = row.hotspots || {};
  const names = (hs.places || []).slice(0, b.cities.length);
  const cells = hs.cells || [];
  if (!names.length || !cells.length || (hs.place_cells || []).length < names.length) return null;
  const ideaCities = new Map();
  (b.event_ideas || []).forEach((e) => e.cities.forEach((c) => ideaCities.set(c, [...(ideaCities.get(c) || []), e.artist])));
  const places = names.map((name, i) => ({ name, cell: hs.place_cells[i], event: ideaCities.has(name) }));
  const ringed = places.filter((p) => p.event).map((p) => `${p.name} (${ideaCities.get(p.name).join(", ")})`);
  const summary = `Map of ${b.country} with ${names.length} numbered hotspot ${names.length === 1 ? "city" : "cities"}: ${names.map((n, i) => `${i + 1} ${n}`).join(", ")}.${ringed.length ? ` Ringed, with an event idea: ${ringed.join("; ")}.` : " No city has an event idea."}`;
  const box = h("div", { class: "plan-map" });
  hotspotMap(b.code, cells, { places, width: 440, height: 360, label: summary }).then((svg) => { if (svg) { svg.classList.add("hs-map-brief"); box.prepend(svg); } }).catch(() => {});
  box.append(h("p", { class: "plan-note mono" }, "Numbered dots: ", h("strong", null, names.map((n, i) => `${i + 1} ${n}`).join(", ")), ". ",
    ringed.length ? ["Ring means an event idea: ", h("strong", null, ringed.join("; ")), "."] : "No event idea in these cities."));
  return box;
}

function briefCard(st, made, row) {
  const b = made.brief;
  const note = b.summary_source === "template" ? "Template summary, no AI wrote it." : "Written by AI from this brief; every name and number in it checked against the brief.";
  return h("article", { class: "plan-brief", "aria-labelledby": "brief-h" },
    h("p", { class: "eyebrow" }, "Deliverable"),
    h("h2", { id: "brief-h" }, `Launch brief: ${b.title} in ${b.country}`),
    statTiles(b, row),
    h("p", { class: "plan-headline" }, b.headline),
    h("section", { "aria-labelledby": "bs-sum" },
      h("h3", { id: "bs-sum" }, "Summary"), h("p", null, b.summary), h("p", { class: "plan-note mono" }, note)),
    (b.moves || []).length ? h("section", { "aria-labelledby": "bs-moves" },
      h("h3", { id: "bs-moves" }, "This week's moves"),
      h("p", { class: "plan-note mono" }, "One step per buyer, each doable within about a week, from this brief's own facts. Steps, not promised results."),
      h("dl", { class: "plan-partners" }, b.moves.map((m) => h("div", null, h("dt", null, m.buyer), h("dd", null, m.text))))) : null,
    h("section", { "aria-labelledby": "bs-cities" },
      h("h3", { id: "bs-cities" }, "Where to start"),
      b.cities.length ? h("ul", null, b.cities.map((c) => h("li", null, c))) : h("p", null, "Qloo returned no named places for this country."),
      cityMap(b, row)),
    (b.event_ideas || []).length ? h("section", { "aria-labelledby": "bs-events" },
      h("h3", { id: "bs-events" }, "Event ideas"),
      h("p", { class: "plan-note mono" }, "Cities where Qloo's map of the title's audience and of the artist's audience overlap."),
      h("ul", null, b.event_ideas.map((e) => h("li", null, artistName(e.artist), ` in ${joinList(e.cities)}: both audiences concentrate there.`)))) : null,
    h("section", { "aria-labelledby": "bs-partners" },
      h("h3", { id: "bs-partners" }, "Partners to approach"),
      h("p", { class: "plan-note mono" }, b.partner_basis === "ai_confirmed" ? "AI picks that Qloo confirmed come first." : "Qloo's own kit for this title and country."),
      h("dl", { class: "plan-partners" }, b.partners.map((g) => h("div", null,
        h("dt", null, g.label),
        h("dd", null, g.picks.flatMap((p, i) => [i ? ", " : null, g.domain === "artist" ? artistName(p.name) : p.name,
          p.source === "ai_confirmed" && p.also_in_qloo_kit ? h("span", { class: "plan-both" }, " (also in Qloo's kit)") : null])))))),
    h("section", { "aria-labelledby": "bs-avoid" },
      h("h3", { id: "bs-avoid" }, "What not to claim"), h("ul", null, b.avoid.map((a) => h("li", null, a)))),
    h("section", { "aria-labelledby": "bs-evidence" },
      h("h3", { id: "bs-evidence" }, "Evidence"), h("ul", null, b.evidence.map((a) => h("li", null, a)))),
    h("p", { class: "plan-note" }, "Forecast locked in the public ", h("a", { href: "#/ledger" }, "ledger"), " before the outcome exists. ",
      h("a", { href: `#/storm/${encodeURIComponent(st.id)}` }, "Full forecast for this title"), "."));
}

function controls(st, made) {
  const status = h("span", { class: "muted", role: "status" });
  const flash = (msg) => { status.textContent = msg; setTimeout(() => { status.textContent = ""; }, 2500); };
  const copy = h("button", { type: "button", class: "btn btn-small" }, "Copy link");
  copy.addEventListener("click", () => {
    if (!navigator.clipboard?.writeText) return flash("Copy blocked; use the address bar.");
    navigator.clipboard.writeText(location.href).then(() => flash("Link copied"), () => flash("Copy blocked; use the address bar."));
  });
  const download = h("button", { type: "button", class: "btn btn-small" }, "Download brief");
  download.addEventListener("click", () => {
    const b = made.brief;
    const url = URL.createObjectURL(new Blob([briefMarkdown(b, location.href)], { type: "text/markdown;charset=utf-8" }));
    const a = h("a", { href: url, download: `launch-brief-${st.id}-${b.code}.md`.toLowerCase(), hidden: true });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    flash("Downloaded");
  });
  const print = h("button", { type: "button", class: "btn btn-small", onclick: () => window.print() }, "Print");
  return h("div", { class: "plan-actions no-print" }, copy, download, print, status);
}

function pickers(storms, st, code) {
  const rows = st ? kitRows(st) : [];
  const title = h("select", { id: "plan-title", class: "wm-select" }, storms.map((s) =>
    h("option", { value: s.id, selected: st && s.id === st.id }, s.title + (s.season ? ` ${s.season}` : ""))));
  const country = h("select", { id: "plan-country", class: "wm-select", disabled: !rows.length }, rows.map((r) =>
    h("option", { value: r.code, selected: r.code === code }, r.brief.brief.country)));
  title.addEventListener("change", () => {
    country.disabled = true;
    getStorm(title.value).then((next) => {
      const first = kitRows(next)[0];
      if (first) location.hash = planHref(next.id, first.code);
    }).catch(() => { country.disabled = false; });
  });
  country.addEventListener("change", () => { location.hash = planHref(st.id, country.value); });
  return h("div", { class: "plan-pick no-print" },
    h("div", { class: "field" }, h("label", { for: "plan-title" }, "Title"), title),
    h("div", { class: "field" }, h("label", { for: "plan-country" }, "Country"), country));
}

export function renderPlan(root, isCurrent, id, code) {
  document.title = "Plan a launch - AFTERSHOCK";
  const body = h("div", null, loading("this week's titles"));
  add(root,
    h("div", { class: "no-print" },
      h("h1", null, "Plan a launch"),
      h("p", { class: "pitch" }, "Pick a breakout title and a country. The agent shows each step it takes, from the forecast to Qloo's taste data, and ends with a brief you can hand to a local partner.")),
    body);
  const fail = (err) => { if (isCurrent()) body.replaceChildren(errorBox("the launch planner", err)); };

  if (!id) {
    defaultPlan().then((d) => {
      if (!isCurrent()) return;
      if (d) location.replace(planHref(d.id, d.code));
      else body.replaceChildren(h("p", { class: "status" }, "No title has a Qloo launch kit this week."));
    }).catch(fail);
    return;
  }

  Promise.all([getStorms(), getStorm(id)]).then(([{ storms, week }, st]) => {
    if (!isCurrent()) return;
    const options = storms.filter((s) => s.has_kit);
    if (!options.some((s) => s.id === st.id)) options.unshift({ id: st.id, title: st.title, season: st.season });
    const row = kitRows(st).find((r) => r.code.toLowerCase() === code.toLowerCase());
    body.replaceChildren(pickers(options, st, row?.code));
    if (!row) {
      add(body, h("p", { class: "status status-error", role: "alert" },
        `No launch kit for ${code} on ${st.title}. Pick one of its kit countries above.`));
      return;
    }
    const made = row.brief;
    const region = h("div", { class: "plan-steps-region", "aria-live": "polite", "aria-label": "The agent's steps" });
    const list = h("ol", { class: "plan-steps no-print" });
    region.append(list);
    add(body, h("h2", { class: "plan-run-h no-print" }, `The agent's steps: ${st.title} in ${row.brief.brief.country}`),
      h("p", { class: "plan-note mono no-print" }, `Replay of the weekly run for the week of ${st.archived_week ?? week}. The steps were computed then and are shown one by one; nothing runs live.`),
      region);
    const finish = () => {
      if (!isCurrent()) return;
      add(body, briefCard(st, made, row), controls(st, made));
    };
    let shown = 0;
    const next = () => {
      if (!isCurrent()) return;
      list.append(stepCard(made.steps[shown], shown + 1));
      shown += 1;
      if (shown < made.steps.length) setTimeout(next, STEP_MS); else finish();
    };
    if (reduced()) {
      made.steps.forEach((s, i) => list.append(stepCard(s, i + 1)));
      finish();
    } else next();
  }).catch((err) => {
    if (!isCurrent()) return;
    if (err.status === 404) body.replaceChildren(h("p", { class: "status status-error", role: "alert" }, err.message),
      h("p", null, h("a", { href: "#/plan" }, "Plan a different launch")));
    else fail(err);
  });
}
