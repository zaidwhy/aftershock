// "Plan a launch": the agent's steps for one title in one country appear one by one, then the Launch Brief.
// The steps and the brief are built by aftershock/launch_brief.py and ride on each launch_kit row as `brief`.
import { h, loading, errorBox, add } from "./dom.js";
import { getStorms, getStorm } from "./api.js";
import { hotspotMap } from "./charts.js";
import { rejectedList } from "./rejected.js";
import { artistName } from "./artists.js";
import { checkBox } from "./check.js";
import { rankLabel } from "./format.js";

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

/** Artists and brands are who to approach; TV shows and films say what the audience watches. Groups without a
 *  `group` field (older data) count as partners for artists and brands only. */
export function splitPartners(groups) {
  const isPartner = (g) => (g.group ? g.group === "partner" : ["artist", "brand"].includes(g.domain));
  return { partners: groups.filter(isPartner), watches: groups.filter((g) => !isPartner(g)) };
}

const joinList =(items) => (items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items.at(-1)}`);

/** Plain-text-to-Markdown for the downloaded file, built from the brief alone. */
export function briefMarkdown(b, url) {
  const list = (items) => items.map((x) => `- ${x}`);
  const kitFirst = b.partner_basis === "qloo_kit_first";
  const mark = (p) => (p.source === "ai_confirmed"
    ? (kitFirst ? " (also confirmed by Qloo from the AI's suggestions)" : p.also_in_qloo_kit ? " (AI pick confirmed by Qloo; also in Qloo's kit)" : " (AI pick confirmed by Qloo)")
    : " (Qloo's kit)");
  const group = (gs) => gs.flatMap((g) => [`**${g.label}**`, ...list(g.picks.map((p) => p.name + mark(p))), ""]);
  const { partners, watches } = splitPartners(b.partners);
  return [`# Launch brief: ${b.title} in ${b.country}`, "", ...(b.window ? [`*${b.window}.*`, ""] : []), b.headline, "", ...(b.scale ? [b.scale, ""] : []),
    `## Summary`, b.summary, `*${b.summary_source === "template" ? "Template summary" : "Written by AI from this brief; every name and number in it checked against the brief"}.*`, "",
    ...((b.moves || []).length ? ["## This week's moves", ...(b.moves || []).map((m) => `- **${m.buyer}:** ${m.text}`), ""] : []),
    "## Where to start", ...(b.cities.length ? list(b.cities) : ["Qloo returned no named places for this country."]), "",
    ...((b.event_ideas || []).length ? ["## Quick-turn activation ideas", "Tours are booked months ahead; these are short activations where both audiences already live.", "", ...list(b.event_ideas.map((e) => e.text)), ""] : []),
    "## Partners to approach", ...(b.kit_lead ? [b.kit_lead, ""] : []), ...group(partners),
    ...(watches.length ? ["## This audience also watches (for creative and ad targeting)", ...group(watches)] : []),
    "## What not to claim", ...list(b.avoid), "",
    "## Evidence", ...list(b.evidence), "", url ? `Source: ${url}` : ""].join("\n");
}

function stepCard(s, n) {
  // Steps that call Qloo are lit, so a reader sees at a glance which decisions are Qloo's.
  const qloo = /qloo/i.test(`${s.title} ${s.found}`);
  return h("li", { class: qloo ? "plan-step plan-step-qloo" : "plan-step" },
    h("p", { class: "plan-step-n mono" }, `Step ${n}`, qloo ? h("span", { class: "qloo-mark plan-step-tag" }, "Qloo") : null),
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
  const checked = b.partner_basis !== "qloo_kit"
    ? [`${plan.confirmed.length} of ${proposed}`, "AI picks confirmed by Qloo"]
    : ["Qloo's own kit", "fewer than 3 AI picks confirmed"];
  const tiles = [
    [`${b.rank} of ${b.of_countries}`, rankLabel(b.rank, b.of_countries).toLowerCase()],
    [b.chance_label, `chance to chart in ${b.horizon_weeks} weeks`],
    checked,
    [String(ideas), ideas === 1 ? "quick activation idea" : "quick activation ideas"],
  ];
  return h("div", { class: "proof plan-tiles", role: "group", "aria-label": "Brief at a glance" },
    tiles.map(([v, n]) => h("div", { class: "proof-item" }, h("p", { class: "proof-v" }, v), h("p", { class: "proof-n" }, n))));
}

/** Hotspot cities as labelled dots on the country map (the storm page's renderer); activation-idea cities get a ring.
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
  const summary = `Map of ${b.country} with ${names.length} numbered hotspot ${names.length === 1 ? "city" : "cities"}: ${names.map((n, i) => `${i + 1} ${n}`).join(", ")}.${ringed.length ? ` Ringed, with an activation idea: ${ringed.join("; ")}.` : " No city has an activation idea."}`;
  const box = h("div", { class: "plan-map" });
  hotspotMap(b.code, cells, { places, width: 440, height: 360, label: summary }).then((svg) => { if (svg) { svg.classList.add("hs-map-brief"); box.prepend(svg); } }).catch(() => {});
  box.append(h("p", { class: "plan-note mono" }, "Numbered dots: ", h("strong", null, names.map((n, i) => `${i + 1} ${n}`).join(", ")), ". ",
    ringed.length ? ["Ring means a quick activation idea: ", h("strong", null, ringed.join("; ")), "."] : "No activation idea in these cities."));
  return box;
}

function partnerList(groups, kitFirst) {
  const name = (g, p) => (g.domain === "artist" ? artistName(p.name) : p.name);
  return h("dl", { class: "plan-partners" }, groups.map((g) => {
    const lead = kitFirst ? g.picks.filter((p) => p.source === "qloo_kit") : g.picks;
    const extra = kitFirst ? g.picks.filter((p) => p.source === "ai_confirmed") : [];
    return h("div", null,
      h("dt", null, g.label),
      h("dd", null, lead.flatMap((p, i) => [i ? ", " : null, name(g, p),
        !kitFirst && p.source === "ai_confirmed" && p.also_in_qloo_kit ? h("span", { class: "plan-both" }, " (also in Qloo's kit)") : null]),
        extra.length ? h("span", { class: "plan-ai-extra" }, h("span", { class: "plan-both" }, "Also confirmed by Qloo from the AI's suggestions: "),
          extra.flatMap((p, i) => [i ? ", " : null, name(g, p)])) : null));
  }));
}

/** "Partners to approach" (artists and brands) and, apart, what the audience also watches (shows and films). */
function partnerSection(b) {
  const { partners, watches } = splitPartners(b.partners);
  const kitFirst = b.partner_basis === "qloo_kit_first";
  return h("div", null,
    h("section", { "aria-labelledby": "bs-partners" },
      h("h3", { id: "bs-partners" }, "Partners to approach"),
      b.kit_lead ? h("p", { class: "plan-kit-lead" }, b.kit_lead) : null,
      h("p", { class: "plan-note mono" }, b.partner_basis === "qloo_kit_first" ? "Qloo's own kit for this title and country leads; AI picks that Qloo also confirmed follow."
        : b.partner_basis === "ai_confirmed" ? "AI picks that Qloo confirmed come first." : "Qloo's own kit for this title and country."),
      partnerList(partners, kitFirst)),
    watches.length ? h("section", { "aria-labelledby": "bs-watches" },
      h("h3", { id: "bs-watches" }, "This audience also watches (for creative and ad targeting)"),
      partnerList(watches, kitFirst)) : null);
}

// Frozen backtest numbers (data/results/lead_time.json, 829 held-out breakouts): how often the top 3 countries
// included one that charted next, against always naming the three busiest countries.
const BACKTEST = { model: "9.8%", baseline: "4.1%", times: "2.4", spread: "113", modelSpread: "72%", baseSpread: "30%" };
const pctOf = (p) => (p == null ? "n/a" : `${Math.round(p * 100)}%`);

/** What decision the brief supports, and for each claim the signal behind it and what is still unproven. */
function evidenceTable(st, b, row) {
  const fc = (st.spillover?.forecasts || []).find((r) => r.code === b.code);
  const confirmed = row?.plan?.confirmed?.length ?? 0;
  const dropped = row?.plan?.dropped || {};
  const proposed = confirmed + (dropped.not_placed || 0) + (dropped.not_in_qloo || 0);
  const spec = row?.specificity;
  const rows = [
    [`${b.country} is the ${rankLabel(b.rank, b.of_countries).toLowerCase()}`,
      `${pctOf(fc?.probability)} chance to chart within 4 weeks${fc?.why ? `; ${fc.why}` : ""}. In the backtest the top 3 countries caught a next market ${BACKTEST.model} of the time against ${BACKTEST.baseline} for the busiest-countries baseline (${BACKTEST.times} times).`,
      "This title's forecast is not graded yet; most breakouts never spread at all."],
    ["These partners fit this audience",
      `Qloo confirmed ${confirmed} of the ${proposed} names an AI proposed for these viewers in ${b.country}${spec != null ? `; Qloo's own kit is ${Math.round(spec * 100)}% different from the country's general taste, so it is about this title` : ""}.`,
      "No data yet that these partners move streams, tickets or sales."],
    [`Start in ${(b.cities || []).slice(0, 3).join(", ") || "the mapped cities"}`,
      "Qloo's heatmap of this title's audience in the country peaks there.",
      "The heatmap shows where the audience lives, not where it will buy."],
  ];
  if ((b.event_ideas || []).length) rows.push(["Quick-turn activations",
    "An artist's five strongest heatmap cells sit within 30 km of a title hotspot.",
    "Audience overlap is not ticket demand; venue dates are unknown."]);
  return h("section", { class: "plan-evidence", "aria-labelledby": "bs-ev" },
    h("h3", { id: "bs-ev" }, "Evidence behind each claim"),
    h("div", { class: "table-wrap" }, h("table", { class: "plain ev-table" },
      h("thead", null, h("tr", null, h("th", null, "Claim"), h("th", null, "What supports it"), h("th", null, "What is still missing"))),
      h("tbody", null, rows.map(([c, e, m]) => h("tr", null, h("td", null, h("strong", null, c)), h("td", null, e), h("td", { class: "ev-gap" }, m)))))));
}

function decisionLine(b) {
  return h("div", { class: "plan-decision-box" }, h("p", { class: "gp-label mono" }, "The decision this supports"),
    h("p", null, `Is ${b.country} worth a week of ${b.title} promotion, and where should it start? Read this as a shortlist for further research, a predicted opportunity, not a confirmed business one.`));
}

function briefCard(st, made, row) {
  const b = made.brief;
  const note = b.summary_source === "template" ? "Template summary, no AI wrote it." : "Written by AI from this brief; every name and number in it checked against the brief.";
  return h("article", { class: "plan-brief", "aria-labelledby": "brief-h" },
    h("p", { class: "eyebrow" }, "Deliverable"),
    h("h2", { id: "brief-h" }, `Launch brief: ${b.title} in ${b.country}`),
    decisionLine(b),
    b.window ? h("p", { class: "plan-window" }, b.window) : null,
    statTiles(b, row),
    h("p", { class: "plan-headline" }, b.headline),
    b.scale ? h("p", { class: "plan-note" }, b.scale) : null,
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
      h("h3", { id: "bs-events" }, "Quick-turn activation ideas"),
      h("p", { class: "plan-note mono" }, "Things doable within about a week, such as a club night, a screening party, a DJ set, a sponsor activation or a playlist push, in cities where Qloo's map of the title's audience and of the artist's audience overlap. Tours are booked months ahead; these are short activations where both audiences already live."),
      h("ul", null, b.event_ideas.map((e) => h("li", null, artistName(e.artist), ` in ${joinList(e.cities)}: both audiences concentrate there.`)))) : null,
    partnerSection(b),
    evidenceTable(st, b, row),
    h("section", { "aria-labelledby": "bs-avoid" },
      h("h3", { id: "bs-avoid" }, "What not to claim"), h("ul", null, b.avoid.map((a) => h("li", null, a)))),
    h("section", { "aria-labelledby": "bs-evidence" },
      h("h3", { id: "bs-evidence" }, "Evidence"), h("ul", null, b.evidence.map((a) => h("li", null, a)))),
    h("p", { class: "plan-note" }, "Forecast locked in the public ", h("a", { href: "#/ledger" }, "ledger"), " before Netflix published the outcome. ",
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
      h("p", { class: "plan-note mono no-print" }, `These steps ran in this week's automatic run (week of ${st.archived_week ?? week}) and are replayed one by one here; the check box below asks Qloo live.`),
      region);
    const finish = () => {
      if (!isCurrent()) return;
      add(body, briefCard(st, made, row), controls(st, made));
    };
    let shown = 0;
    const next = () => {
      if (!isCurrent()) return;
      const step = made.steps[shown];
      list.append(stepCard(step, shown + 1));
      if (step.key === "qloo_check") list.append(checkBox(st.id, row.code, st.title, made.brief.country));
      shown += 1;
      if (shown < made.steps.length) setTimeout(next, STEP_MS); else finish();
    };
    if (reduced()) {
      made.steps.forEach((step, i) => {
        list.append(stepCard(step, i + 1));
        if (step.key === "qloo_check") list.append(checkBox(st.id, row.code, st.title, made.brief.country));
      });
      finish();
    } else next();
  }).catch((err) => {
    if (!isCurrent()) return;
    if (err.status === 404) body.replaceChildren(h("p", { class: "status status-error", role: "alert" }, err.message),
      h("p", null, h("a", { href: "#/plan" }, "Plan a different launch")));
    else fail(err);
  });
}
