import { h, s } from "./dom.js";
import { loading, errorBox, add } from "./dom.js";
import { getStorms, getStorm, getScorecard, getLedger, isMock } from "./api.js";
import { pct, plain2, dateLabel } from "./format.js";
import { ageLean, forecastMap, hotspotMap } from "./charts.js";
import { ISO } from "./iso.js";
import { lookupBox } from "./netflix.js";
import { weekMapSection } from "./weekmap.js";
import { launchBrief } from "./brief.js";
import { askBox } from "./ask.js";
import { agentLine } from "./agent.js";
import { defaultPlan } from "./plan.js";
import { rejectedList } from "./rejected.js";
import { artistName } from "./artists.js";
import { isCatalogTitle } from "./catalog.js";

// AUCs that differ in the third decimal must not round to the same label.
const auc4 = (n) => (n == null ? "n/a" : n.toFixed(4));

const countryName = (code) => ISO[code]?.[1] ?? code;

const setTitle = (t) => { document.title = t ? `${t} - AFTERSHOCK` : "AFTERSHOCK - An AI's launch plan sounds right. Qloo checks it."; };
const mockNote = () => (isMock() ? h("p", { class: "mock-flag" }, "Mock data (?mock=1). Numbers are placeholders, except the replay pageviews.") : null);
const whole = (n) => (n == null ? null : n.toLocaleString("en-US"));
const scrollTo = (id) => (e) => { e.preventDefault(); document.getElementById(id)?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }); };
const origins = (list) => list.map((c) => c.name).join(", ");
/** "(2017, comedy)" for a heading, or "2017 | Comedy, Drama" for a meta line; "" when Qloo had neither. */
const yearGenres = (year, genres, inline) => {
  const g = (genres || []).map((n) => (inline ? n.toLowerCase() : n));
  const parts = [year, g.length ? g.join(", ") : null].filter(Boolean);
  if (!parts.length) return "";
  return inline ? ` (${parts.join(", ")})` : parts.join(" | ");
};

/** Run a fetch into a container with loading and error states. */
function load(container, what, isCurrent, fetcher, render, notFound) {
  const run = () => {
    container.replaceChildren(loading(what));
    fetcher().then((data) => {
      if (!isCurrent()) return;
      container.replaceChildren();
      render(data, container);
    }).catch((err) => {
      if (!isCurrent()) return;
      container.replaceChildren(notFound ? notFound(err, container) ?? errorBox(what, err, run) : errorBox(what, err, run));
    });
  };
  run();
}

/* ---------------------------------------------------------------- landing */
export function renderHome(root, isCurrent, followId = null) {
  setTitle("");
  const stormBox = h("div", null);
  const heroBox = h("div", null);
  const proof = h("aside", { class: "proof", "aria-label": "Evidence at a glance" });
  const mapBox = h("div", null);
  const agentBox = h("p", { class: "agent-line", hidden: true });
  const planCta = h("a", { class: "btn btn-primary", href: "#/plan" }, "Plan a launch");
  const leadLine = h("p", { class: "lead-line", hidden: true });
  const heroFact = h("p", { class: "hero-fact", hidden: true });
  defaultPlan().then((d) => {
    if (!isCurrent() || !d) return;
    planCta.href = `#/plan/${encodeURIComponent(d.id)}/${encodeURIComponent(d.code)}`;
    planCta.textContent = `Plan a launch: ${d.title} in ${d.country}`;
  }).catch(() => {});
  const stormsP = getStorms();
  add(root,
    h("section", { class: "hero" },
      h("div", { class: "hero-top" },
        h("div", { class: "hero-copy" },
          h("p", { class: "eyebrow" }, "A Qloo taste agent for breakout shows"),
          h("h1", null, "An AI's launch plan sounds right. ", h("em", null, "Qloo checks it.")),
          heroFact,
          h("p", { class: "plan-cta" }, planCta),
          h("p", { class: "pitch" }, "Every week the agent finds titles that just broke out on Netflix in one to three countries, and Netflix history says where each is likely to chart next. For that audience Qloo's taste graph then checks what an AI suggests (artists, brands, shows, films) and maps the cities where the audience lives. Every forecast is locked publicly before the outcome exists."),
          leadLine,
          h("ul", { class: "hero-links" },
            h("li", null, h("a", { href: "#/", onclick: scrollTo("live-h") }, "This week's breakouts")))),
        h("div", { class: "hero-side" },
          h("p", { class: "buyer mono" }, "For labels, promoters, brands and local distributors: know where a breakout goes next and what to pair it with there, before the competition does."),
          heroBox)),
      askBox(isCurrent, stormsP),
      proof,
      agentBox,
      mapBox,
      lookupBox(isCurrent)),
    mockNote(),
    h("section", { "aria-labelledby": "live-h" },
      h("h2", { id: "live-h" }, "Live storms this week"),
      h("p", { class: "muted" }, "Storms: titles that just broke out in 1 to 3 countries. Netflix's Top 10 also includes older catalog titles that re-entered it; they are tagged and listed after this-or-recent releases."),
      stormBox));

  Promise.all([getScorecard(), stormsP]).then(([sc, st]) => {
    if (!isCurrent()) return;
    const bt = sc.backtest || {};
    const kits = st.storms.filter((x) => x.has_kit).length;
    const locked = (sc.spillover?.locked ?? 0) + (sc.ripple?.locked ?? 0);
    const lt = sc.lead_time;
    if (lt?.model?.lead_weeks?.median != null && lt.breakouts_that_spread_at_all) {
      // Most breakouts never travel, so lead with the buyer's question: when one does, did the top picks name where?
      const spread = lt.breakouts_that_spread_at_all;
      const whole0 = (x) => `${Math.round(x * 100)}%`;
      const times = lt.baseline.hit_rate ? (lt.model.hit_rate / lt.baseline.hit_rate).toFixed(1) : null;
      leadLine.append(`Backtest on ${whole(lt.model.breakouts)} past breakouts it never saw: counting all ${whole(lt.model.breakouts)}, `,
        `${share1(lt.model.hit_rate)} against ${share1(lt.baseline.hit_rate)}${times ? `, ${times} times the baseline` : ""}. `,
        `Of the ${whole(spread)} that spread at all, its top ${lt.top_k} named a next country `,
        `${whole0(lt.model.hit_breakouts / spread)} of the time (${whole0(lt.baseline.hit_breakouts / spread)} for the busiest-countries baseline). `,
        h("a", { href: "#/scorecard", onclick: () => { wantWarning = true; } }, "The full test, misses included"));
      leadLine.hidden = false;
    }
    const gc = sc.grounded_plan?.counts;
    if (gc) {
      const { confirmed: c, not_placed: np, not_in_qloo: nq } = gc, n = c + np + nq;
      const p = (x) => `${Math.round((x / n) * 100)}%`;
      const ke = sc.kit_experiment, sp = sc.grounded_plan?.specificity_plan;
      if (ke?.qloo != null && ke?.llm != null && sp != null) {
        const two = (x) => x.toFixed(2);
        heroFact.append(h("span", { class: "hero-cmp-h" }, "How specific to the title are the picks? (0 to 1, higher is more specific)"),
          h("span", { class: "hero-cmp", role: "list" },
            [[two(ke.qloo), "Qloo alone"], [two(ke.llm), "LLM alone"], [two(sp), "LLM checked by Qloo (exploratory)"]].map(([v, l]) =>
              h("span", { class: "hero-cmp-i", role: "listitem" }, h("strong", null, v), " ", l))));
      }
      heroFact.append(h("strong", null, `${p(np + nq)} of the names an LLM proposed are not backed by Qloo.`),
        ` Of ${whole(n)} names an AI proposed, ${p(c + np)} are names Qloo knows and ${p(c)} are ones it links to that audience there, so ${p(np + nq)} are not backed: `,
        `${p(nq)} Qloo has no data on, ${p(np)} it knows but does not place with that audience. `,
        h("a", { href: "#/scorecard" }, "How we measured it"));
      heroFact.hidden = false;
    }
    const items = [
      ["Forecasts locked", whole(locked), "forecasts locked publicly before the outcome"],
      sc.top_pick?.breakouts > 0 ? ["Top picks already charted", `${sc.top_pick.top_pick_hits} of ${sc.top_pick.breakouts}`, `expected ${sc.top_pick.expected_hits} if calibrated`]
        : bt.spillover?.history_auc != null ? ["Backtest AUC", plain2(bt.spillover.history_auc), `on ${whole(bt.spillover.test_breakouts)} breakouts`] : null,
      ["Storms with a Qloo kit", String(kits), `of ${st.storms.length} this week`],
      ["Breakouts this week", String(st.storms.length), `week of ${st.week}`],
    ].filter(Boolean);
    proof.append(...items.map(([k, v, note]) => h("div", { class: "proof-item" },
      h("p", { class: "proof-k" }, k), h("p", { class: "proof-v" }, v), h("p", { class: "proof-n" }, note))));
  }).catch(() => { proof.hidden = true; });

  agentLine(agentBox, isCurrent);

  stormsP.then((st) => {
    if (isCurrent() && st.map?.countries?.length) mapBox.append(weekMapSection(st.map, st.week, isCurrent, st.storms, followId));
  }).catch(() => {});

  stormsP.then((st) => {
    const x = st.hero;
    if (!isCurrent() || !x) return;
    const join = (a) => a.join(", ");
    const step = (label, ...kids) => h("div", { class: "ex-step" }, h("p", { class: "ex-k mono" }, label), ...kids);
    heroBox.append(h("section", { class: "example", "aria-labelledby": "ex-h" },
      h("h2", { id: "ex-h" }, `This week's clearest example: ${x.title}${yearGenres(x.year, x.genres, true)}`),
      h("div", { class: "ex-grid" },
        step("1 Breakout", h("p", null, `Broke out in ${origins(x.origin_countries)}`),
          x.just_added ? h("p", { class: "ex-why" }, `An older title: ${origins(x.origin_countries)} just added it to its Top 10 this week.`) : null),
        step("2 Where next", h("p", null, h("strong", null, x.country), " ", h("span", { class: "mono" }, pct(x.probability)), " chance to chart within 4 weeks"),
          x.why ? h("p", { class: "ex-why" }, x.why) : null),
        step("3 Pair it with", h("p", null, `Qloo: this audience in ${x.country} loves ${join(x.artists)}`, x.brands.length ? `; brands ${join(x.brands)}` : "")),
        step("4 Start in", h("p", null, `Start in ${join(x.places)}`))),
      h("p", { class: "ex-link" }, h("a", { href: `#/storm/${encodeURIComponent(x.id)}` }, "See the full forecast"))));
  }).catch(() => {});

  load(stormBox, "this week's storms", isCurrent, () => stormsP.catch(() => getStorms()), ({ week, storms }) => {
    if (!storms.length) { add(stormBox, h("p", { class: "status" }, `No title entered the Top 10 in only 1 to 3 countries in the week of ${week}.`)); return; }
    const dataYear = Number(String(week).slice(0, 4));
    const catalog = (s) => isCatalogTitle(s.meta?.year, dataYear);
    const byChance = [...storms].sort((a, b) => (b.top_forecast?.probability ?? -1) - (a.top_forecast?.probability ?? -1));
    const ranked = [...byChance.filter((s) => !catalog(s)), ...byChance.filter(catalog)];
    const maxP = Math.max(0.0001, ...ranked.map((s) => s.top_forecast?.probability ?? 0));
    add(stormBox,
      h("p", { class: "muted" }, `Week of ${week}. Titles that entered Netflix's Top 10 in 1 to 3 countries, most likely to spread first.`),
      h("p", { class: "muted" }, "Tags: \"Qloo kit\" means we have what this title's audience loves in each forecast country. \"Countrywide\" means Qloo had little title-specific signal, so the kit mostly shows the country's general taste."),
      h("ul", { class: "storm-list" }, ranked.map((s) => h("li", null,
        h("a", { href: `#/storm/${encodeURIComponent(s.id)}`, class: "storm-link" },
          h("span", { class: "storm-title" }, s.title, s.season ? h("span", { class: "muted" }, ` ${s.season}`) : null),
          h("span", { class: "storm-meta" }, s.meta && (s.meta.year || s.meta.genres?.length) ? h("span", { class: "storm-facts" }, yearGenres(s.meta.year, s.meta.genres)) : null,
            `Origin: ${origins(s.origin_countries)}`, catalog(s) ? h("span", { class: "tag tag-quiet" }, "catalog title") : null, s.has_kit ? h("span", { class: "tag tag-kit" }, s.kit_specific === false ? "Qloo kit (countrywide)" : "Qloo kit") : null),
          h("span", { class: "storm-next" }, s.top_forecast
            ? [h("span", null, "Next: ", h("strong", null, s.top_forecast.name), " ", h("span", { class: "mono" }, pct(s.top_forecast.probability))),
               h("span", { class: "pbar", role: "img", "aria-label": `${pct(s.top_forecast.probability)} chance, scaled to the top storm this week` },
                 h("span", { style: `width:${Math.max(2, (s.top_forecast.probability / maxP) * 100)}%` }))]
            : "No forecast yet"))))));
  });
}


/* ------------------------------------------------------------------ storm */
export function renderStorm(root, id, isCurrent) {
  setTitle("Storm");
  load(root, "this storm", isCurrent, () => getStorm(id), (st) => {
    setTitle(st.title);
    const fc = st.spillover?.forecasts || [];
    const mapBox = h("div", { class: "map-box" }, loading("the map"));
    add(root, 
      h("p", { class: "crumb" }, h("a", { href: "#/" }, "All storms")),
      archivedBanner(st.archived_week),
      h("h1", null, st.title, st.season ? h("span", { class: "h1-sub" }, ` ${st.season}`) : null),
      titleHead(st),
      answerLine(st, fc),
      mockNote(),
      h("section", { "aria-labelledby": "map-h" },
        h("h2", { id: "map-h" }, `Where it charts next (${st.spillover?.horizon_weeks ?? "?"} week horizon)`),
        h("p", { class: "follow-link" }, h("a", { href: `#/?follow=${encodeURIComponent(st.id)}` }, "Follow it on the world map")),
        mapBox,
        h("p", { class: "legend" }, h("span", { class: "key key-origin" }), "Origin countries (outlined)", h("span", { class: "key key-ramp" }), "Darker = higher probability"),
        fc.length ? forecastTable(fc) : h("p", { class: "status" }, "No forecast rows for this title.")),
      kitSection(st),
      h("p", { class: "locked mono" }, st.spillover?.locked_at ? `Locked at ${dateLabel(st.spillover.locked_at)} | ledger id ${st.spillover.ledger_id}` : "Not locked yet."));
    forecastMap(fc, st.origin_countries).then((svg) => {
      if (isCurrent()) mapBox.replaceChildren(svg);
    }).catch((err) => {
      if (isCurrent()) mapBox.replaceChildren(errorBox("the map", err), h("p", { class: "muted" }, "The table below has the same data."));
    });
  }, (err) => (err.status === 404 ? h("div", { class: "status status-error", role: "alert" },
    h("h2", null, "No breakout called that"),
    h("p", null, /^No breakout called/.test(err.message) ? err.message : `No breakout called ${id} in any week we have forecast.`),
    h("p", null, h("a", { href: "#/" }, "See this week's breakouts"))) : null));
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
/** Shown when the API served this storm from an earlier week's archive. */
export function archivedBanner(week) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(week || "");
  if (!m) return null;
  const when = `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[1]}`;
  return h("p", { class: "status archived-note", role: "note" },
    `From the week of ${when}. This title has since dropped out of this week's breakouts; its forecast below was locked then and is graded as Netflix publishes.`);
}

/** Poster (when Qloo has one), year, genres and a one-sentence description, then the origin line. */
function titleHead(st) {
  const m = st.meta || {};
  const facts = yearGenres(m.year, m.genres);
  const text = h("div", { class: "title-text" },
    facts ? h("p", { class: "meta title-facts" }, facts) : null,
    m.blurb ? h("p", { class: "title-blurb" }, m.blurb) : null,
    h("p", { class: "meta" }, `${st.category || "Title"} | origin week ${st.origin_week} | broke out in `, h("strong", null, origins(st.origin_countries))));
  if (!m.image) return text;
  return h("div", { class: "title-head" },
    h("img", { class: "poster", src: m.image, alt: `Poster or still for ${st.title}`, loading: "lazy", width: "84", height: "126", referrerpolicy: "no-referrer",
      onerror: (e) => e.target.remove() }), text);
}

function kitRows(st) {
  return (st.launch_kit || []).filter((r) => r.kit && Object.values(r.kit).some((v) => v?.length));
}

function answerLine(st, fc) {
  const top = fc[0], n = kitRows(st).length;
  return h("p", { class: "answer" },
    top ? h("span", null, "Most likely next: ", h("strong", null, top.name), " ", h("span", { class: "mono" }, `(${pct(top.probability)})`)) : null,
    top && n ? h("span", { class: "answer-sep", "aria-hidden": "true" }, "|") : null,
    n ? h("a", { href: "#/", onclick: scrollTo("par-h") }, `Qloo launch kit for ${n} ${n === 1 ? "country" : "countries"} below`) : null);
}

/** Hotspot map and place names for one kit country; nothing when the data is missing. */
function hotspotBlock(r) {
  const hs = r.hotspots;
  if (!hs || (!hs.cells?.length && !hs.places?.length)) return null;
  const box = h("div", { class: "hs" });
  if (hs.cells?.length) {
    hotspotMap(r.code, hs.cells).then((svg) => { if (svg) box.prepend(svg); }).catch(() => {});
  }
  if (hs.places?.length) box.append(h("p", { class: "hs-places" }, "Hotspots: ", h("strong", null, hs.places.join(", "))));
  return box;
}

/** "Quick-turn activation ideas": artists whose audience concentrates in the same cities as the title's. Nothing without any. */
function eventsBlock(r) {
  const ideas = (r.events || []).filter((e) => e.artist && e.cities?.length);
  if (!ideas.length) return null;
  return h("p", { class: "hs-places" }, "Quick-turn activation ideas: ",
    h("strong", null, ideas.flatMap((e, i) => [i ? "; " : null, artistName(e.artist), ` in ${e.cities.join(" and ")}`])),
    ". Both audiences concentrate there. Tours are booked months ahead; these are short activations where both audiences already live.");
}

const KIT_LABELS = { artist: "Artists", tv_show: "TV shows", movie: "Films", brand: "Brands" };

/** "AI plan, checked by Qloo": names an AI proposed that Qloo places with this audience, in Qloo's order, plus a
 *  plain count of the rest. Nothing when the row has no plan (the weekly run had no AI key). */
function planBlock(r) {
  const plan = r.plan;
  if (!plan) return null;
  const { not_placed: np = 0, not_in_qloo: nq = 0 } = plan.dropped || {};
  const yes = plan.confirmed || [];
  const total = yes.length + np + nq;
  if (!total) return null;
  const groups = Object.keys(KIT_LABELS).map((d) => [d, yes.filter((c) => c.domain === d)]).filter(([, list]) => list.length);
  return h("div", { class: "plan" },
    h("h4", null, "AI plan, checked by Qloo"),
    h("p", { class: "plan-sum" }, `Of ${total} names an AI suggested for this audience, Qloo confirmed ${yes.length}; ${np} it knows but does not place with these viewers here, ${nq} it has no data on.`),
    groups.length ? h("ul", { class: "plan-list" }, groups.map(([d, list]) => h("li", null,
      h("span", { class: "plan-dom" }, KIT_LABELS[d]), " ",
      list.flatMap((c, i) => [i ? ", " : null, d === "artist" ? artistName(c.name) : c.name, c.both ? h("span", { class: "plan-both" }, " (also in Qloo's kit)") : null])))) : null,
    rejectedList(plan.rejected));
}

/** "Copy launch brief": clipboard write inside the click; if it is refused, show the text selected in a box. */
function briefControl(st, rows) {
  const status = h("span", { class: "muted", role: "status" });
  const fallback = h("div", { class: "brief-fallback", hidden: true });
  const btn = h("button", { type: "button", class: "btn btn-small" }, "Copy launch brief");
  btn.addEventListener("click", () => {
    const text = launchBrief(st, location.href, rows);
    const showBox = () => {
      const area = h("textarea", { rows: "10", readonly: "", "aria-label": "Launch brief" });
      area.value = text;
      fallback.replaceChildren(h("p", { class: "muted" }, "Copying was blocked. The brief is selected below; press Ctrl+C."), area);
      status.textContent = "";
      fallback.hidden = false;
      area.focus();
      area.select();
    };
    const done = () => { status.textContent = "Copied"; setTimeout(() => { status.textContent = ""; }, 2500); };
    if (!navigator.clipboard?.writeText) return showBox();
    navigator.clipboard.writeText(text).then(() => { fallback.hidden = true; done(); }, showBox);
  });
  return h("div", { class: "brief" }, h("div", { class: "brief-row" }, btn, status), fallback);
}

function kitSection(st) {
  const rows = kitRows(st);
  if (!rows.length) {
    // Older data has only the artist partners list.
    return st.partners?.some((p) => p.artists?.length) ? h("section", { "aria-labelledby": "par-h" },
      h("h2", { id: "par-h" }, "Who this audience already loves there"),
      h("ul", { class: "partners" }, st.partners.filter((p) => p.artists?.length).map((p) => h("li", null,
        h("strong", null, countryName(p.code)), " ", h("span", null, p.artists.join(", ")))))) : null;
  }
  // A name that is also on the country's own Qloo list (no title) says nothing about this title; mute it.
  const key = (n) => n.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  const common = (r, d) => new Set((r.control?.[d] || []).map(key));
  const anyCommon = rows.some((r) => Object.keys(KIT_LABELS).some((d) => (r.kit[d] || []).some((e) => common(r, d).has(key(e.name)))));
  const names = (r, d) => r.kit[d].flatMap((e, i) => [i ? ", " : null,
    common(r, d).has(key(e.name)) ? h("span", { class: "kit-common" }, e.name) : e.name]);
  const specific = (r) => (r.specificity == null ? null : h("p", { class: "kit-spec" },
    h("strong", null, r.generic ? "Mostly countrywide taste" : "Title-specific"), `: ${Math.round(r.specificity * 100)}%`));
  return h("section", { "aria-labelledby": "par-h" },
    h("h2", { id: "par-h" }, "Launch kit: what this audience loves there"),
    h("p", { class: "muted" }, "From Qloo: what the title's audience over-indexes on in each forecast country, as a starting point for a local launch. Netflix history says where; this says what to do there. It does not change the probabilities."),
    briefControl(st, rows),
    anyCommon ? h("p", { class: "kit-cap" }, h("span", { class: "kit-common" }, "Greyed out"), ": popular across the whole country anyway, not specific to this title") : null,
    h("div", { class: "kit-cols" }, rows.map((r) => h("div", { class: "kit" },
      h("h3", null, countryName(r.code)),
      r.brief ? h("p", { class: "plan-link" }, h("a", { href: `#/plan/${encodeURIComponent(st.id)}/${encodeURIComponent(r.code)}` }, "Plan a launch here")) : null,
      specific(r),
      h("dl", { class: "kit-list" }, Object.keys(KIT_LABELS).filter((d) => r.kit[d]?.length).map((d) => h("div", { class: d === "brand" ? "kit-minor" : null },
        h("dt", null, KIT_LABELS[d]), h("dd", null, names(r, d))))),
      planBlock(r), hotspotBlock(r), eventsBlock(r)))),
    rows.some((r) => r.hotspots?.cells?.length || r.hotspots?.places?.length)
      ? h("p", { class: "hs-credit" }, "Hotspots: Qloo heatmap; place names © OpenStreetMap contributors.") : null);
}

/* ----------------------------------------------------------------- ripple */
const earlyRead = (x) => (x.early_ratio == null ? "n/a" : `${x.early_ratio.toFixed(1)}x${x.early_status === "pending" ? " pending" : ""}`);

export function renderRipple(root) {
  setTitle("Song forecasts");
  add(root, h("p", { class: "crumb" }, h("a", { href: "#/" }, "All storms")),
    h("h1", null, "No song forecasts yet"),
    h("p", null, "Song forecasts are not published right now. The storms and the scorecard are."));
}

function songTable(r, songs) {
  const heads = ["#", "Song", "Artist", "Score (age gap)", "Prior views/day (context)", "Early read", "Generation gap"];
  const numCols = [3, 4, 5];
  return h("div", { class: "table-wrap", tabindex: "0", role: "region", "aria-label": "Ranked songs table, scrolls sideways on narrow screens" },
    h("table", { class: "fc rt" },
      h("caption", null, "Score is the Qloo age gap, 0 to 1. Early read above 1x means mean daily views on days +7 to +35 after release are above the days -60 to -8 average."),
      h("thead", null, h("tr", null, heads.map((t, i) => h("th", { scope: "col", class: numCols.includes(i) ? "num" : null }, t)))),
      h("tbody", null, songs.map((x, i) => h("tr", null,
        h("td", { class: "mono" }, i + 1),
        h("th", { scope: "row" }, x.song),
        h("td", null, x.artist),
        h("td", { class: "num mono prob" }, plain2(x.score)),
        h("td", { class: "num mono" }, x.prior_daily_views == null ? "n/a" : Math.round(x.prior_daily_views).toLocaleString("en-US")),
        h("td", { class: "num mono" }, earlyRead(x)),
        h("td", null, x.leans ? ageLean(r.show_leans, x.leans, `Age bands the show audience and the audience of ${x.artist} lean to, for ${x.song}.`) : h("span", { class: "muted" }, "artist not in Qloo")))))));
}

function forecastTable(fc) {
  return h("div", { class: "table-wrap", tabindex: "0", role: "region", "aria-label": "Forecast table, scrolls sideways on narrow screens" },
    h("table", { class: "fc fc-stack" },
      h("caption", null, "Ranked forecast. Probability is the chance the title enters that country's Top 10 within the horizon."),
      h("thead", null, h("tr", null, ["#", "Country", "Probability", "Why"].map((t, i) => h("th", { scope: "col", class: i === 2 ? "num" : null }, t)))),
      h("tbody", null, fc.map((f, i) => h("tr", null,
        h("td", { class: "mono rank" }, i + 1),
        h("th", { scope: "row" }, f.name),
        h("td", { class: "num mono prob" }, pct(f.probability)),
        h("td", { class: "why" }, f.why))))));
}

export { renderTry, renderScout } from "./audience.js";

/* -------------------------------------------------------------- scorecard */
const GITHUB_README_3 = "https://github.com/zaidwhy/aftershock#3-what-we-measured-including-what-did-not-work";
const GITHUB_EXPERIMENT = "https://github.com/zaidwhy/aftershock/blob/main/docs/EXPERIMENT_KITS.md";

const share = (n) => (n == null ? "n/a" : `${Math.round(n * 100)}%`);

function kitCheckSection(sc) {
  const kc = sc.kit_check;
  if (!kc) return null;
  const example = (label, e) => (e ? h("li", null, `${label}: `, h("a", { href: `#/storm/${encodeURIComponent(e.id)}` }, `${e.title} in ${e.country}`),
    h("span", { class: "mono" }, ` (${Math.round(e.specificity * 100)}% specific)`)) : null);
  return h("section", { "aria-labelledby": "kitcheck-h" },
    h("h2", { id: "kitcheck-h" }, "What Qloo adds: is the launch kit about the title?"),
    h("p", null, h("strong", { class: "mono" }, `${kc.specific} of ${kc.kits}`), ` launch kits this week are title-specific; ${kc.generic} are mostly countrywide taste. Mean specificity is `,
      h("span", { class: "mono" }, `${Math.round(kc.mean_specificity * 100)}%`), "."),
    h("p", { class: "muted" }, "For every kit we also ask Qloo what the whole country likes, with no title. A kit counts as countrywide when most of its picks repeat that country-only list, and as title-specific when they do not."),
    h("ul", { class: "kit-examples" }, example("Title-specific", kc.example_specific), example("Countrywide", kc.example_generic)));
}

const share1 = (n) => (n == null ? "n/a" : `${(n * 100).toFixed(1)}%`);
const weeks = (n) => `${n} ${n === 1 ? "week" : "weeks"}`;
const COUNTRY = (code) => ISO[code]?.[1] || code;
const dayLabel = (iso) => `${+iso.slice(8, 10)} ${MONTHS[+iso.slice(5, 7) - 1]} ${iso.slice(0, 4)}`;
let wantWarning = false;

/** Grouped bars: for 1..horizon weeks of warning, the model's picks that charted (solid) and the baseline's (outlined). */
function leadChart(lt) {
  const hz = lt.horizon_weeks, dist = (a) => lt[a].lead_weeks.distribution;
  const max = Math.max(1, ...["model", "baseline"].flatMap((a) => Object.values(dist(a))));
  const W = 360, left = 56, top = 14, rowH = 44, H = top + hz * rowH + 4, scale = (W - left - 44) / max;
  const g = [];
  for (let w = 1; w <= hz; w++) {
    const y = top + (w - 1) * rowH;
    g.push(s("text", { x: 0, y: y + 20, class: "db-label" }, `${w} wk`));
    [["model", 0, "lw-model"], ["baseline", 17, "lw-base"]].forEach(([arm, dy, cls]) => {
      const n = dist(arm)[String(w)] ?? 0;
      g.push(s("rect", { x: left, y: y + dy, width: Math.max(n * scale, 1.5), height: 14, class: cls }),
        s("text", { x: left + Math.max(n * scale, 1.5) + 6, y: y + dy + 11, class: "db-vals" }, String(n)));
    });
  }
  const label = `Bar chart of weeks of warning for picks that charted, model against baseline. ${Array.from({ length: hz }, (_, i) => `${i + 1} week${i ? "s" : ""}: model ${dist("model")[String(i + 1)] ?? 0}, baseline ${dist("baseline")[String(i + 1)] ?? 0}`).join("; ")}.`;
  return h("div", { class: "db-box" },
    h("p", { class: "legend" }, h("span", { class: "dot dot-real" }), "Model's top 3 (solid)", h("span", { class: "dot dot-placebo" }), "Baseline: the 3 countries that chart most titles (outlined)"),
    s("svg", { viewBox: `0 0 ${W} ${H}`, class: "lw-svg", role: "img", "aria-label": label }, g));
}

function caseStudy(c) {
  const [title, season] = c.title;
  const shown = season && season !== "N/A" && !season.startsWith(title) ? `${title}: ${season}` : title;
  const picks = c.top3.map((p) => `${COUNTRY(p.country)} (${Math.round(p.probability * 100)}%${p.charted_after_weeks == null ? ", did not chart" : `, charted ${weeks(p.charted_after_weeks)} later`})`);
  const hit = c.top3.some((p) => p.charted_after_weeks != null);
  const others = c.all_countries_charted_within_horizon.length ? `Within 4 weeks it charted in ${c.all_countries_charted_within_horizon.map(COUNTRY).join(", ")}.` : "Within 4 weeks it charted nowhere else.";
  return h("li", null,
    h("strong", null, shown), ` (${c.category === "Films" ? "film" : "series"}, broke out ${dayLabel(c.breakout_week)} in ${c.origin_countries.map(COUNTRY).join(", ")}). `,
    h("span", { class: "mono" }, hit ? "Hit. " : "Miss. "), `Top 3 forecast: ${picks.join("; ")}. ${others}`);
}

/** How much warning the held-out backtest says a distributor would have had; nothing without the measurement. */
function warningSection(sc) {
  const lt = sc.lead_time;
  if (!lt) return null;
  const m = lt.model, b = lt.baseline, spread = lt.breakouts_that_spread_at_all;
  return h("section", { "aria-labelledby": "warning-h" },
    h("h2", { id: "warning-h" }, "How much warning it gives"),
    h("p", null, `In ${whole(m.breakouts)} breakouts the model had not seen, at least one of its top ${lt.top_k} countries charted the title within ${lt.horizon_weeks} weeks `,
      h("strong", { class: "mono" }, `${share1(m.hit_rate)} of the time`), ` (${m.hit_breakouts} breakouts), against ${share1(b.hit_rate)} (${b.hit_breakouts}) for the ${lt.top_k} countries that chart the most titles. `,
      `Of the ${whole(m.picks)} top-${lt.top_k} picks, ${share1(m.per_pick_precision)} charted (${share1(b.per_pick_precision)} for the baseline).`),
    spread != null ? h("p", null, `Most breakouts do not spread at all: only ${spread} of ${whole(m.breakouts)} charted in any other country within ${lt.horizon_weeks} weeks. The top ${lt.top_k} caught ${m.hit_breakouts} of those ${spread}; the baseline caught ${b.hit_breakouts}.`) : null,
    m.lead_weeks.median != null ? h("p", null, "When a pick did chart, it did so a median of ", h("strong", { class: "mono" }, weeks(m.lead_weeks.median)),
      ` after the breakout week (mean ${m.lead_weeks.mean.toFixed(1)}). That is the warning a distributor or promoter would have had.`) : null,
    m.lead_weeks.median != null ? leadChart(lt) : null,
    h("h3", null, "Three cases, chosen by a rule fixed before looking"),
    h("p", { class: "muted" }, `The rule: ${lt.case_study_rule}. Misses are included.`),
    h("ul", { class: "kit-examples" }, lt.case_studies.map(caseStudy)),
    h("p", { class: "muted" }, "A backtest on history-only forecasts (no Qloo data), March to October 2026: each forecast made from the breakout week using only earlier breakouts. It is not the live ledger."));
}

/** One explanation of the LLM-names numbers, from the counts in grounded_plan.json: of N proposed names, the share Qloo
 *  knows, the share it links to this audience in this country, and the 71% it does not back (unknown + known but not linked). */
function numbersExplained(gp) {
  const { confirmed: c, not_placed: np, not_in_qloo: nq } = gp.counts, n = c + np + nq;
  const p = (x) => `${Math.round((x / n) * 100)}%`;
  return h("div", { class: "num-explained" },
    h("p", null, `Across ${gp.pairs} title-country pairs, an LLM proposed ${whole(n)} artists, brands, films and shows for the audience. Of those ${whole(n)} names:`),
    h("ul", null,
      h("li", null, h("strong", { class: "mono" }, p(np + c)), ` are names Qloo knows (${whole(np + c)}).`),
      h("li", null, h("strong", { class: "mono" }, p(c)), ` are ones Qloo links to this audience in this country (${whole(c)}). Only these go into a launch brief.`),
      h("li", null, h("strong", { class: "mono" }, p(np + nq)), ` are not backed by Qloo (${whole(np + nq)}): `,
        `${p(nq)} (${whole(nq)}) Qloo does not know at all, plus ${p(np)} (${whole(np)}) it knows but does not link to this audience in this country.`)));
}

/** The pre-registered Qloo-versus-LLM result; an honest empty slot until the scored run exists. */
function llmSection(sc) {
  const ex = sc.kit_experiment;
  const slot = ex
    ? h("div", { class: "kit-exp" },
      h("p", null, h("strong", null, ex.verdict ?? "Result recorded"), ex.scored_pairs ? ` across ${ex.scored_pairs} title-country pairs.` : "."),
      h("p", null, `How much each list changes once the title is named, against the same source's list for the country alone (higher means more about this title): Qloo ${share(ex.qloo)}, LLM ${share(ex.llm)}.`),
      h("p", null, `Only ${share(ex.grounding_share)} of the LLM's picks are names Qloo knows as the right kind of thing (the same figure as above, before checking audience), so some are not audience taste at all.`,
        ex.grounded_pairs ? ` Counting only those, the LLM still leads (${share(ex.grounded_llm)} against Qloo's ${share(ex.grounded_qloo)} on ${ex.grounded_pairs} pairs).` : ""),
      h("p", null, "What we do about it: every kit is checked against Qloo's country-only answer and labelled countrywide when it mostly matches it, so a kit never claims to be about a title when it is not."),
      h("p", null, h("a", { href: GITHUB_EXPERIMENT, rel: "noopener" }, "How it was registered and scored")))
    : h("p", { class: "muted" }, "Registered on 27 Oct before any data was collected; results will appear here. ",
      h("a", { href: GITHUB_EXPERIMENT, rel: "noopener" }, "Read the registration"));
  const gp = sc.grounded_plan;
  if (gp?.unbacked_share == null) return h("section", { "aria-labelledby": "llm-h" }, h("h2", { id: "llm-h" }, "Qloo versus an LLM (pre-registered)"), slot);
  // Lead with the result that shapes the product; the registered test stays below it in full.
  return h("section", { "aria-labelledby": "llm-h" },
    h("h2", { id: "llm-h" }, `An LLM alone: Qloo could not back ${share(gp.unbacked_share)} of what it named`),
    ex && ex.qloo != null && ex.llm != null && gp.specificity_plan != null ? h("div", { class: "kit-cmp" },
      h("p", { class: "hero-cmp-h" }, "How specific to the title are the picks? (0 to 1, higher is more specific)"),
      h("p", { class: "hero-cmp" }, [[ex.qloo, "Qloo alone"], [ex.llm, "LLM alone"], [gp.specificity_plan, "LLM checked by Qloo (exploratory)"]].map(([v, l]) =>
        h("span", { class: "hero-cmp-i" }, h("strong", null, v.toFixed(2)), " ", l))),
      h("p", null, `${share(gp.unbacked_share)} of the LLM's names are not backed by Qloo.`)) : null,
    gp.counts ? numbersExplained(gp) : h("p", null, `Across ${gp.pairs} title-country pairs an LLM named ${whole(gp.picks_checked)} artists, brands, films and shows for the audience. Qloo placed ${share(1 - gp.unbacked_share)} of them with that audience; the rest it either does not know or does not link to these viewers. Only the confirmed names go into a launch brief.`),
    gp.specificity_plan != null ? h("p", null, `The combined plan (the LLM's names, kept only when Qloo confirms them) is `, h("strong", null, `${gp.specificity_plan.toFixed(2)} title-specific`),
      `, against ${gp.specificity_llm.toFixed(2)} for the LLM's raw picks, on ${gp.specificity_pairs} pairs.`) : null,
    h("p", { class: "muted" }, "Exploratory: designed after the registered result below, on the same pairs and cached LLM answers. It is not pre-registered."),
    h("h3", { id: "llm-reg-h" }, "The registered test: which list is more title-specific"),
    slot);
}

export function renderScorecard(root, isCurrent) {
  setTitle("Scorecard");
  const box = h("div", null);
  add(root, h("h1", null, "Scorecard"), h("p", { class: "pitch" }, "What the signals did on past events, then the live ledger: forecasts are locked first and graded later. Nothing here is edited after the fact."), mockNote(), box);
  load(box, "the scorecard", isCurrent, getScorecard, (sc) => {
    const sp = sc.spillover || {}, rp = sc.ripple || {}, bt = sc.backtest || {};
    const bs = bt.spillover || {}, br = bt.ripple || {};
    const pl = br.placebo || {};
    const row = (label, value) => h("tr", null, h("th", { scope: "row" }, label), h("td", { class: "mono" }, value));
    const so = sp.so_far;
    const closes = (() => {
      if (!sp.earliest_origin_week) return null;
      const d = new Date(`${sp.earliest_origin_week}T00:00:00Z`);
      d.setUTCDate(d.getUTCDate() + 7 * (sp.horizon_weeks ?? 4));
      return d.toISOString().slice(0, 10);
    })();
    const dl = (pairs) => h("dl", null, pairs.map(([k, v]) => h("div", null, h("dt", null, k), h("dd", { class: "mono" }, v ?? "n/a"))));
    const spillSection = h("section", { class: "score-block", "aria-label": "Spillover" },
      h("h2", null, "Spillover"),
      h("p", { class: "state" }, h("strong", { class: "mono" }, whole(sp.locked) ?? "n/a"), " forecasts locked.",
        sp.graded ? ` ${sp.graded} graded so far.` : closes ? ` First ${sp.horizon_weeks ?? 4}-week horizons close on ${closes}. Early grades appear weekly as Netflix publishes.` : " Grades appear weekly as Netflix publishes."),
      sp.graded ? dl([["Hits", sp.hits], ["Pending", sp.pending], ["AUC", plain2(sp.auc)]]) : null,
      so?.forecasts > 0 ? dl([["So far: hits, horizon still open", `${so.hits} of ${so.forecasts}`], ["So far: partial AUC (misses can still turn into hits)", plain2(so.auc)]]) : null);
    const rippleSection = h("section", { class: "score-block", "aria-label": "Ripple" },
      h("h2", null, "Ripple"),
      h("p", { class: "state" }, h("strong", { class: "mono" }, whole(rp.locked) ?? "n/a"), " releases locked.",
        rp.locked ? "" : " Song forecasts are locked only before a release's outcome window opens, with at least 4 Qloo-scorable songs; none has qualified yet."),
      rp.graded_releases ? dl([["Graded releases", rp.graded_releases], ["Pending releases", rp.pending_releases], ["Mean Spearman", plain2(rp.mean_spearman)]]) : null);
    const scored = bs.history_auc;
    const tableOf = (label, rows) => h("div", { class: "table-wrap", tabindex: "0", role: "region", "aria-label": `${label}, scrolls sideways on narrow screens` }, h("table", { class: "plain" }, h("caption", { class: "sr-only" }, label),
      h("thead", null, h("tr", null, ["Measure", "Value"].map((t) => h("th", { scope: "col" }, t)))),
      h("tbody", null, rows)));
    add(box,
      llmSection(sc),
      kitCheckSection(sc),
      warningSection(sc),
      h("section", { "aria-labelledby": "bt-h" },
        h("h2", { id: "bt-h" }, "Where a breakout goes next: the country backtest"),
        scored == null ? h("p", { class: "muted" }, "The backtest has not been generated yet.")
          : h("p", null, h("strong", null, `Ranks a country that went on to chart above one that did not ${Math.round(scored * 100)}% of the time`), ` (ROC AUC ${plain2(scored)}), on ${whole(bs.test_breakouts)} past breakouts.`),
        h("p", { class: "muted" }, "Netflix history only: how often each country followed past breakouts from the same origins. Mar-Oct 2026 breakouts the model had not seen. The country forecast uses no Qloo data."),
        tableOf("Country backtest", row(`Spillover: history-only AUC (${bs.test_breakouts ?? "n/a"} breakouts)`, auc4(bs.history_auc)))),
      h("section", { "aria-labelledby": "ledger-h" },
        h("h2", { id: "ledger-h" }, "Live ledger"),
        sc.top_pick?.breakouts > 0 ? h("div", { class: "score-block", "aria-label": "Early read" },
          h("h3", null, "Early read: last week's top picks"),
          h("p", null, `${sc.top_pick.top_pick_hits} of ${sc.top_pick.breakouts} top picks have already charted. If the forecasts were exactly calibrated we would expect ${sc.top_pick.expected_hits}. Always picking the country that charts the most titles (${sc.top_pick.baseline_country}) gets ${sc.top_pick.baseline_hits}.`),
          h("p", { class: "muted" }, "Defined before the data existed, reported every week whichever way it goes. The 4-week result is the real grade. ",
            h("a", { href: "https://github.com/zaidwhy/aftershock/blob/main/docs/EARLY_GRADE.md", rel: "noopener" }, "How it is defined"))) : null,
        h("div", { class: "grid2" }, spillSection, rippleSection),
        h("div", { class: "ledger-row" }, h("a", { class: "btn", href: "#/ledger" }, "Open the public ledger"),
          sc.ledger_intact == null ? null : h("span", { class: "muted" }, sc.ledger_intact ? "Ledger hash chain verified." : "Ledger hash chain FAILED verification."),
          sc.data_week ? h("span", { class: "muted" }, `Netflix data through the week of ${sc.data_week}.`) : null)),
      h("section", { "aria-labelledby": "dnw-h" },
        h("h2", { id: "dnw-h" }, "What did not work"),
        h("h3", null, "Qloo added nothing to the country forecast"),
        tableOf("No lift from Qloo", [
          row(`Same ${bs.subset_breakouts ?? "n/a"} breakouts, history-only`, auc4(bs.history_auc_same_subset)),
          row(`Same ${bs.subset_breakouts ?? "n/a"}, history + Qloo`, auc4(bs.qloo_auc))]),
        h("h3", null, "The song tests"),
        h("p", null, `No Qloo signal predicted which soundtrack songs spike on Wikipedia: ${br.n_artists ?? "n/a"} artists in ${br.n_shows ?? "n/a"} shows were scored, and on 2024+ releases the Qloo age gap beat a placebo spike measured before release at p = ${plain2(pl["2024_plus"]?.["p: gap real minus gap placebo"])}.`),
        h("p", { class: "muted" }, "The song tables and the placebo check are in ", h("a", { href: GITHUB_README_3, rel: "noopener" }, "README section 3"), ".")),
      h("section", { class: "caveat", "aria-labelledby": "dne-h" },
        h("h2", { id: "dne-h" }, "What this does not establish"),
        h("p", null, "Qloo describes the taste of groups, not of any individual: an audience profile says what a group tends to like, not what a given person will do. Forecasts are probabilities, so a 20% forecast that does not happen was not wrong, and one that does was not proven right. The spillover backtest shows Netflix history predicts spread well; it does not show that Qloo adds to it (no lift on the 200-breakout subset). The country forecast uses no Qloo data, and the launch kit has not been validated against outcomes. The song test collected 490 songs from 34 soundtracks; 229 artists in 24 of those shows (4 released 2024 or later) had enough Qloo audience profiles to be scored, where a placement means a song on the title's official soundtrack album, which can include songs a show barely used; its outcome (Wikipedia page spike) is a proxy for attention, and Qloo audiences are today's, which postdate those releases. No Qloo signal predicted which songs spike. Many new 2026 titles have no Qloo audience profile yet. The model would not have picked Running Up That Hill for Stranger Things 4. The live ledger, where each forecast is locked before its outcome exists, is the real test.")));
    if (wantWarning) { wantWarning = false; document.getElementById("warning-h")?.scrollIntoView(); }
  });
}

/* ----------------------------------------------------------------- ledger */
export function renderLedger(root, isCurrent) {
  setTitle("Ledger");
  const box = h("div", null);
  add(root, h("p", { class: "crumb" }, h("a", { href: "#/scorecard" }, "Scorecard")), h("h1", null, "The public forecast ledger"), mockNote(), box);
  load(box, "the ledger", isCurrent, getLedger, (lg) => {
    const when = (iso) => (iso ? dateLabel(iso) : "n/a");
    const state = { pending: "Pending", hit: "Hit", miss: "Miss" };
    add(box,
      h("p", { class: "pitch" }, "Each line is fixed when it is written: it includes a fingerprint of the line before, so changing an old forecast would break every line after it. The raw file is on GitHub."),
      h("dl", { class: "ledger-stats" },
        [["Forecasts", whole(lg.total)], ["Distinct titles", whole(lg.titles)], ["First locked", when(lg.first_locked)], ["Last locked", when(lg.last_locked)],
          ["Fingerprint chain", lg.intact ? "Verified" : "FAILED verification"]].map(([k, v]) => h("div", null, h("dt", null, k), h("dd", { class: "mono" }, v)))),
      h("p", null, "Timing: every forecast was locked before Netflix published any later week for that title."),
      h("p", { class: "ledger-raw" }, h("a", { class: "btn", href: lg.raw_url, rel: "noopener" }, "Open the raw ledger file on GitHub")),
      h("h2", null, `The ${lg.rows.length} most recent forecasts`),
      h("p", { class: "muted" }, "Newest lock first, likeliest first within one lock. Each row is the chance that the title charts in that country within 4 weeks. Status is Pending until Netflix's weekly data settles it."),
      h("div", { class: "table-wrap", tabindex: "0", role: "region", "aria-label": "Recent forecasts, scrolls sideways on narrow screens" },
        h("table", { class: "plain ledger-table" }, h("caption", { class: "sr-only" }, "Most recent locked forecasts"),
          h("thead", null, h("tr", null, ["Locked at", "Title", "Country", "Chance", "Status"].map((t, i) => h("th", { scope: "col", class: i === 3 ? "num" : null }, t)))),
          h("tbody", null, lg.rows.map((r) => h("tr", null,
            h("td", { class: "mono" }, dateLabel(r.locked_at)), h("th", { scope: "row" }, r.title), h("td", null, r.country),
            h("td", { class: "num mono" }, pct(r.probability)), h("td", null, state[r.status] ?? r.status)))))));
  });
}

/* ----------------------------------------------------------------- method */
export function renderMethod(root) {
  setTitle("Method");
  add(root, 
    h("h1", null, "Method"),
    h("p", { class: "pitch" }, "Two models, one rule: lock the forecast before the outcome."),
    h("section", null, h("h2", null, "SPILLOVER: which countries next"),
      h("p", null, "Start with a title that entered Netflix's Top 10 in 1 to 3 countries. The probability that each other country charts it within 4 weeks comes from Netflix history only: how often that country followed past breakouts from the same origin countries, smoothed toward the same-category rate for that country, which is smoothed toward the country's base rate."),
      h("p", null, "Backtest: ROC AUC 0.817 on 829 test breakouts (Mar-Oct 2026). We also tested Qloo as an extra feature on a 200-breakout subset: AUC 0.8188 with history only against 0.8182 with Qloo, so no lift. Qloo had an in-country value for only 2.8% of title-country pairs (975 of 35,344). So Qloo's role in SPILLOVER is the partners list: artists the title's audience over-indexes on in each forecast country."),
      h("p", null, "Every candidate country's probability is locked in the ledger, not just the top rows, so AUC and calibration can be graded. Grading happens once a title's 4-week horizon has passed in Netflix's weekly data.")),
    h("section", null, h("h2", null, "Launch kit and hotspots: what to do there"),
      h("p", null, "For each storm's top three forecast countries, Qloo is asked which shows, films, brands and artists the title's audience over-indexes on there, and where in the country that audience lives (a heatmap, reduced to its three strongest places and named with OpenStreetMap). Neither changes the probabilities, and neither has been validated against outcomes."),
      h("p", null, "Sync Scout is a discovery tool: it ranks the artists a show's audience likes by the age gap between the artist's audience and the show's. It ranks artists, not scenes.")),
    h("section", null, h("h2", null, "RIPPLE: the song score, tested"),
      h("p", null, "The score is the Qloo age gap, from 0 to 1: how far outside the show's generation an artist's audience sits. We tested whether it, Qloo taste fit or obscurity predicts which soundtrack songs spike on Wikipedia, using 490 songs from the official soundtracks of 34 titles in MusicBrainz (CC0). Only artists with a Qloo audience profile can be scored, and a show needs at least 4 of them: 229 artists in 24 of the 34 titles qualified."),
      h("p", null, "Result: no Qloo signal predicts the spike. Within-show Spearman for the age gap is 0.02 (p 0.40) on 24 shows and 0.18 (p 0.22) on the 4 released from 2024 on; real minus placebo p is 0.14, and taste fit is 0.04. Obscurity is 0.22 against 0.11 on a placebo spike measured before release."),
      h("p", null, "An earlier version used placement lists from Tunefind and showed a significant effect. Tunefind's terms do not permit automated collection, so that data and everything computed from it was discarded, and the effect did not replicate on MusicBrainz. The song score is an explorer, not a predictor."),
      h("p", null, "Known miss: the score would not have picked Kate Bush's Running Up That Hill for Stranger Things 4. Her page views rose from about 10k a month to 910k in June 2022 because of how the scene used the song, which neither Qloo nor Wikipedia sees.")),
    h("section", null, h("h2", null, "Data sources"),
      h("ul", { class: "plain-list" },
        h("li", null, h("strong", null, "Netflix Top 10"), ": the public weekly TSV, by country. Defines storms, supplies the SPILLOVER history and grades it."),
        h("li", null, h("strong", null, "Wikimedia pageviews API"), ": daily views per article. The song test outcome and its prior-views context."),
        h("li", null, h("strong", null, "MusicBrainz"), ": official soundtrack track lists (CC0), the song test's ground truth."),
        h("li", null, h("strong", null, "Qloo Insights"), ": entity search and demographics (age bands) for the age gap, the partners list, launch kit and heatmaps for each title's audience in each country."))),
    h("p", null, "The Qloo key stays on the server; this page only talks to AFTERSHOCK's own API."),
    h("section", null, h("h2", null, "Data and terms"),
      h("ul", { class: "plain-list" },
        h("li", null, h("strong", null, "Netflix Top 10"), ": public download from Netflix's Top 10 site."),
        h("li", null, h("strong", null, "Qloo API"), ": hackathon key. Results are shown in the app; raw responses are never published in the repo. Audiences are aggregates, not individuals."),
        h("li", null, h("strong", null, "Wikimedia Pageviews API"), "."),
        h("li", null, h("strong", null, "MusicBrainz"), " (CC0): soundtrack songs."),
        h("li", null, h("strong", null, "OpenStreetMap Nominatim"), ": place names, credited to OpenStreetMap contributors."),
        h("li", null, h("strong", null, "Gemini"), ": only for the pre-registered comparison.")),
      h("p", null, "An earlier song dataset collected from Tunefind was deleted after we read its terms; nothing derived from it is used."),
      h("p", null, "AFTERSHOCK is not affiliated with Netflix or Qloo.")));
}

export function renderNotFound(root) {
  setTitle("Not found");
  add(root, h("h1", null, "Page not found"), h("p", null, h("a", { href: "#/" }, "Back to this week's storms")));
}
