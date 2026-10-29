// Plan a release: for a film, series, album or comedy special that has not launched yet (or a tour), Qloo ranks
// countries by audience affinity, maps the cities, suggests venues and names the local taste to pair with. Worked
// examples load from static files; a typed title runs live (GET /api/release) and shows every Qloo call it made.
import { h, s, add, loading } from "./dom.js";
import { getReleaseExamples, getReleaseExample, planRelease } from "./api.js";
import { hotspotMap } from "./charts.js";
import { failBox } from "./audience.js";
import { ISO } from "./iso.js";
import { downloadWord, printPdf } from "./export.js";

const WORLD_SRC = "vendor/countries-110m.json";
const KINDS = [["film", "Film"], ["series", "Series"], ["music", "Music"], ["comedy", "Comedy"]];
const GOALS = [["tour", "Tour or live shows"], ["premiere", "Premiere or screenings"], ["digital", "Streaming or digital only"]];
const REGIONS = [["any", "Anywhere (24 big markets)"], ["asia", "Asia"], ["europe", "Europe"], ["americas", "The Americas"], ["middle-east-africa", "Middle East and Africa"], ["oceania", "Oceania"]];
const TASTE = [["tv_show", "Shows"], ["movie", "Films"], ["artist", "Artists"]];
const VENUE_WORD = { comedy: "Comedy clubs", music: "Live music venues", film: "Cinemas", series: "Cinemas for premieres" };
// Tiers are relative to the best country checked: Qloo affinity is a relative score, so the map says how close each
// country comes to the leader, not an absolute demand level.
const TIERS = [[0.97, "Top", "t1"], [0.9, "Strong", "t2"], [0.8, "Good", "t3"], [0, "Lower", "t4"]];
const two = (x) => (x == null ? "n/a" : x.toFixed(2));
const defaultGoal = (kind) => (kind === "music" || kind === "comedy" ? "tour" : "premiere");
const tierOf = (score, top) => TIERS.find(([cut]) => score / top >= cut);

/** Every checked country's score: the API's `scores` when present, else the ranked top countries. */
const allScores = (plan) => (plan.scores?.length ? plan.scores : plan.countries.map((c) => ({ code: c.code, name: c.name, score: c.score })));

let world = null;
const loadWorld = () => (world ||= fetch(WORLD_SRC).then((r) => { if (!r.ok) throw new Error("atlas"); return r.json(); }));

/** The world coloured by tier, with the ranked list beside it (the shape a content analyst expects). */
function worldHeat(plan) {
  const scores = allScores(plan);
  const top = Math.max(0.01, ...scores.map((x) => x.score));
  const byNum = new Map(scores.map((x) => [ISO[x.code]?.[0], x]));
  const mapBox = h("div", { class: "wh-map" });
  const list = h("ol", { class: "wh-list" }, scores.slice(0, 12).map((x, i) => {
    const [, label, cls] = tierOf(x.score, top);
    return h("li", null, h("span", { class: "wh-n mono" }, i + 1), h("span", { class: "wh-code mono" }, x.code),
      h("span", { class: "wh-name" }, x.name), h("span", { class: "wh-v mono" }, two(x.score)), h("span", { class: `wh-tier ${cls}` }, label));
  }));
  const legend = h("div", { class: "wh-legend" }, TIERS.map(([cut, label, cls]) => h("span", { class: `wh-key ${cls}` }, label, h("small", null, cut ? ` ${Math.round(cut * 100)}%+ of the leader` : ""))),
    h("span", { class: "wh-key t0" }, "Not checked"));
  loadWorld().then((w) => {
    if (!window.d3 || !window.topojson) return;
    const { d3, topojson } = window;
    const feats = topojson.feature(w, w.objects.countries).features.filter((f) => f.id !== "010");
    const W = 720, H = 360;
    const proj = d3.geoNaturalEarth1().fitSize([W, H], { type: "FeatureCollection", features: feats });
    const path = d3.geoPath(proj);
    const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, class: "wh-svg", role: "img", "aria-label": `World map: ${scores.length} countries checked, coloured by Qloo affinity relative to ${scores[0]?.name}.` },
      feats.map((f) => {
        const x = byNum.get(Number(f.id));
        const cls = x ? tierOf(x.score, top)[2] : "t0";
        return s("path", { d: path(f), class: `wh-c ${cls}` }, x ? s("title", null, `${x.name}: Qloo match score ${two(x.score)}`) : null);
      }));
    mapBox.append(svg);
  }).catch(() => mapBox.append(h("p", { class: "muted" }, "The world map did not load; the ranking beside it is complete.")));
  return h("div", { class: "wh card" },
    h("div", { class: "wh-head" }, h("h3", null, "How well each country matches"), h("span", { class: "gp-label mono qloo-mark" }, `Qloo match score, ${scores.length} countries checked`)),
    h("div", { class: "wh-body" }, list, mapBox), legend);
}

function cityMaps(plan) {
  const withCells = plan.countries.filter((c) => c.hotspots?.cells?.length).slice(0, 3);
  if (!withCells.length) return null;
  const grid = h("div", { class: "rel-maps" });
  for (const c of withCells) {
    const cities = c.cities || [];
    const fig = h("figure", { class: "card rel-map" }, h("figcaption", null, h("span", { class: "gp-label mono qloo-mark" }, "Where fans live (Qloo)"), h("strong", null, c.name)));
    grid.append(fig);
    const pc = c.hotspots.place_cells || [];
    const places = (c.hotspots.places || []).slice(0, pc.length).map((name, i) => ({ name, cell: pc[i] }));
    hotspotMap(c.code, c.hotspots.cells, { places, width: 320, height: 220, label: `Where the audience lives in ${c.name}` })
      .then((svg) => { if (svg) fig.insertBefore(svg, fig.children[1] || null); }).catch(() => {});
    if (cities.length) fig.append(h("ol", { class: "rel-city-proof" }, cities.map((x) => h("li", null, h("strong", null, x.name),
      h("span", { class: "mono muted" }, x.density != null ? ` fan density ${x.density.toFixed(1)}` : "", x.affinity != null ? `, match ${two(x.affinity)}` : "")))));
  }
  return grid;
}

function venues(plan) {
  if (plan.goal === "digital") return h("p", { class: "muted" }, "A streaming or digital launch needs no venues, so the plan skipped those calls.");
  const groups = (plan.venues || []).filter((g) => g.venues?.length);
  if (!groups.length) return h("p", { class: "muted" }, "Qloo returned no tagged venues near the top cities for this kind of release.");
  return h("div", { class: "cards cards-3" }, groups.map((g) => h("div", { class: "card" },
    h("h3", null, `${g.city}, ${g.country}`),
    h("ul", { class: "rel-venues" }, g.venues.slice(0, 5).map((v) => h("li", null, h("strong", null, v.name),
      v.tags?.length ? h("span", { class: "muted" }, ` ${v.tags[0]}`) : null))))));
}

function taste(plan) {
  return h("div", { class: "cards" }, (plan.local_taste || []).map((t) => h("div", { class: "card card-qloo" },
    h("h3", null, `This audience in ${t.country} also loves`),
    h("dl", { class: "rel-taste" }, TASTE.filter(([k]) => t[k]?.length).flatMap(([k, label]) => [h("dt", { class: "mono" }, label), h("dd", null, t[k].join(", "))])))));
}

/** How each number was made, in the order the agent made it, so a reader can check the ranking instead of trusting it. */
function proof(plan) {
  const scores = allScores(plan);
  const [a, b] = scores;
  const sig = plan.signal?.entities || [];
  const lead = plan.countries[0];
  const items = [
    h("li", null, h("strong", null, "Who the audience is. "), plan.signal?.used === "comparables"
      ? `Qloo has no entry for "${plan.name}" yet, so the audience is the people who love ${sig.map((e) => e.name).join(" and ")}.`
      : `Qloo's entry for ${sig[0]?.name} is the audience: everyone whose taste Qloo links to it.`),
    h("li", null, h("strong", null, "Which countries. "), `One Qloo call per country (${scores.length} in all) scores how closely that country's places match this audience. `,
      a && b ? `${a.name} leads at ${two(a.score)}, ${b.name} follows at ${two(b.score)}; the full list is on the map above.` : ""),
    lead?.cities?.length ? h("li", null, h("strong", null, "Which cities. "), "Inside each top country, Qloo's map shows where this audience lives. ",
      `In ${lead.name}, ${lead.cities[0].name} holds the densest part of it (fan density ${lead.cities[0].density?.toFixed(1) ?? "n/a"}${lead.cities[1] ? `, against ${lead.cities[1].density?.toFixed(1) ?? "n/a"} for ${lead.cities[1].name}` : ""}).`) : null,
    h("li", null, h("strong", null, "What to pair it with. "), "The shows, films and artists are Qloo's own picks for this audience in that country, not an AI's guesses."),
    h("li", null, h("strong", null, "What it cost. "), `${plan.calls} Qloo calls, every one listed below with its parameters, so anyone with a Qloo key can rerun them.`),
  ];
  return h("section", { class: "rel-sec rel-proof card card-qloo" }, h("h2", null, "Why this ranking"), h("ol", null, items));
}

function callTrail(plan) {
  return h("details", { class: "rel-trail" },
    h("summary", null, `Every Qloo call this plan made (${plan.calls})`),
    h("ol", { class: "steps" }, (plan.steps || []).map((st, i) => h("li", { class: st.ok ? null : "step-no" },
      h("span", { class: "step-n mono" }, String(i + 1)),
      h("span", null, h("span", { class: "mono ask-tool" }, `GET ${st.endpoint}`), ` x${st.calls} `, st.note,
        h("code", { class: "rel-params" }, Object.entries(st.params || {}).map(([k, v]) => `${k}=${v}`).join("&")),
        st.varies ? h("span", { class: "muted rel-varies" }, ` varies: ${Object.entries(st.varies).map(([k, v]) => `${k} over ${Array.isArray(v) ? v.length : 1}`).join(", ")}`) : null)))));
}

const WEEK = 7 * 864e5;
// Standard lead times for each kind of launch; they come from how releases are usually run, not from Qloo.
const SCHEDULES = {
  tour: [[-12, "Hold venues in the top cities", "venues"], [-8, "Announce in the top three countries with a local partner from the taste list", "taste"], [-4, "Push a clip or single to listeners in the top cities", "cities"], [-1, "Local press and creator posts in each top city", "cities"], [0, "Opening night", null], [1, "Check which city sold best; add a date there", null]],
  premiere: [[-8, "Book premiere screenings in the top cities", "venues"], [-6, "Trailer aimed at the top three countries", "countries"], [-3, "Co-promotion with a show or artist from the taste list", "taste"], [-1, "Creator screenings and press in the top cities", "cities"], [0, "Release", null], [2, "Watch the next countries on the globe for a breakout", null]],
  digital: [[-6, "Reach out to partners from the taste list in the top countries", "taste"], [-3, "Trailer and paid social aimed at the top cities", "cities"], [-1, "Localised artwork and subtitles for the top three countries", "countries"], [0, "Release", null], [1, "Watch the next countries on the globe for a breakout", null]],
};
function schedule(plan, dateStr) {
  const d = dateStr ? new Date(`${dateStr}-01T00:00:00`) : null;
  if (!d || Number.isNaN(d.getTime())) return null;
  const goal = plan.goal || defaultGoal(plan.kind);
  const fmt = (t) => new Date(t).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  const where = { venues: (plan.venues || []).map((v) => v.city).slice(0, 3).join(", "), cities: plan.countries.flatMap((c) => (c.cities || []).slice(0, 1).map((x) => x.name)).slice(0, 3).join(", "),
    countries: plan.countries.slice(0, 3).map((c) => c.name).join(", "), taste: (plan.local_taste?.[0]?.artist || plan.local_taste?.[0]?.tv_show || []).slice(0, 2).join(", ") };
  return h("section", { class: "rel-sec" }, h("h2", null, "A schedule for your date"),
    h("p", { class: "muted" }, "Built from your release month and standard lead times. The places come from the plan above; the timing is a template, not Qloo data."),
    h("ol", { class: "rel-sched" }, SCHEDULES[goal].map(([w, what, key]) => h("li", { class: w === 0 ? "now" : null },
      h("span", { class: "mono rel-when" }, w === 0 ? fmt(d) : `${w > 0 ? "+" : ""}${w} wk, ${fmt(d.getTime() + w * WEEK)}`),
      h("span", null, what, key && where[key] ? h("span", { class: "muted" }, `: ${where[key]}`) : null)))));
}

function refusal(plan, focusLike) {
  return h("div", { class: "status rel-refuse" }, h("p", null, h("strong", null, plan.reason || plan.message || "Qloo did not recognise that title or any comparable.")),
    plan.try?.length ? h("ul", null, plan.try.map((t) => h("li", null, t))) : null,
    h("button", { type: "button", class: "btn", onclick: focusLike }, "Add similar titles"));
}

/** The plan as a report for the Word and PDF files, in the page's order. */
function releaseReport(plan, dateStr) {
  const scores = allScores(plan);
  const sig = plan.signal?.entities || [];
  const top = Math.max(0.01, ...scores.map((x) => x.score));
  const goal = plan.goal || defaultGoal(plan.kind);
  const sched = SCHEDULES[goal] && dateStr ? (() => {
    const d = new Date(`${dateStr}-01T00:00:00`);
    const fmt = (t) => new Date(t).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
    return SCHEDULES[goal].map(([w, what]) => [w === 0 ? fmt(d) : `${w > 0 ? "+" : ""}${w} wk, ${fmt(d.getTime() + w * WEEK)}`, what]);
  })() : null;
  return {
    title: `Release plan: ${plan.name}`,
    lead: plan.countries[0]?.summary || "",
    source: location.href,
    blocks: [
      { heading: "The decision this supports", decision: "Which countries and cities to research first for this release, which venues to approach, and what local taste to pair it with. A shortlist for further research, not a forecast of tickets or streams." },
      { heading: "Who the audience is", text: plan.signal?.used === "comparables" ? `Qloo does not know "${plan.name}" yet, so the audience is the people who love ${sig.map((e) => e.name).join(" and ")}.` : `Qloo's entry for ${sig[0]?.name} is the audience.` },
      { heading: "Where the audience is", table: { head: ["#", "Country", "Qloo affinity", "Tier", "Cities"], rows: scores.map((x, i) => {
        const c = plan.countries.find((k) => k.code === x.code);
        return [String(i + 1), x.name, two(x.score), tierOf(x.score, top)[1], (c?.cities || []).map((k) => k.name).join(", ")];
      }) }, note: "The Qloo match score (0 to 1) says how closely a country's taste fits this audience; the tiers compare each country with the best one." },
      goal === "digital" ? { heading: VENUE_WORD[plan.kind] || "Venues", text: "A streaming or digital launch needs no venues." }
        : { heading: VENUE_WORD[plan.kind] || "Venues", table: { head: ["City", "Venues"], rows: (plan.venues || []).filter((g) => g.venues?.length).map((g) => [`${g.city}, ${g.country}`, g.venues.slice(0, 5).map((v) => v.name).join(", ")]) } },
      { heading: "Local taste to pair it with", table: { head: ["Country", "Shows", "Films", "Artists"], rows: (plan.local_taste || []).map((t) => [t.country, (t.tv_show || []).join(", "), (t.movie || []).join(", "), (t.artist || []).join(", ")]) } },
      sched ? { heading: "A schedule for your date", table: { head: ["When", "What"], rows: sched }, note: "Standard lead times, not Qloo data." } : null,
      { heading: "How it was made", text: `${plan.calls} Qloo calls, each listed with its parameters on the page.` },
      plan.caveats?.length ? { heading: "What this can't tell you", list: plan.caveats } : null,
    ],
  };
}

function exportBar(plan, opts) {
  return h("div", { class: "plan-actions rel-export" },
    h("button", { type: "button", class: "btn btn-small btn-primary", onclick: () => printPdf(releaseReport(plan, opts.date)) }, "Download PDF"),
    h("button", { type: "button", class: "btn btn-small", onclick: () => downloadWord(releaseReport(plan, opts.date)) }, "Download Word"));
}

function result(plan, opts) {
  if (!plan.resolved) return refusal(plan, opts.focusLike);
  const sig = plan.signal?.entities || [];
  const used = plan.signal?.used === "comparables"
    ? `Qloo does not know "${plan.name}" yet, so we use the people who love similar titles: ${sig.map((e) => e.name).join(", ")}.`
    : `Qloo knows ${sig[0]?.name}, so we use the people who love it.`;
  const scope = [plan.region && plan.region !== "any" ? REGIONS.find(([v]) => v === plan.region)?.[1] : null, plan.home ? `${ISO[plan.home]?.[1] || plan.home} left out as the home market` : null].filter(Boolean);
  return h("div", { class: "rel-result" },
    plan.example ? h("p", { class: "tag tag-quiet rel-example" }, plan.example_note) : null,
    exportBar(plan, opts),
    h("p", { class: "rel-signal" }, h("span", { class: "gp-label mono qloo-mark" }, "Whose audience"), used, scope.length ? h("span", { class: "muted" }, ` Scope: ${scope.join("; ")}.`) : null),
    plan.countries[0] ? h("p", { class: "rel-lead" }, h("span", { class: "gp-num" }, plan.countries[0].name), plan.countries[0].summary ? h("span", { class: "muted" }, ` ${plan.countries[0].summary}`) : null) : null,
    h("section", { class: "rel-sec" }, h("h2", null, "Where the audience is"), worldHeat(plan), cityMaps(plan)),
    h("section", { class: "rel-sec" }, h("h2", null, VENUE_WORD[plan.kind] || "Venues"), venues(plan)),
    h("section", { class: "rel-sec" }, h("h2", null, "Local taste to pair it with"),
      h("p", { class: "muted" }, "Qloo's picks for this audience in each top country: collaborators, co-promotions and playlist or watch-party tie-ins."), taste(plan)),
    schedule(plan, opts.date),
    proof(plan),
    callTrail(plan),
    plan.caveats?.length ? h("section", { class: "rel-sec" }, h("h3", null, "What this can't tell you"), h("ul", { class: "muted" }, plan.caveats.map((c) => h("li", null, c)))) : null);
}

/** A row of toggle buttons that behaves like a radio group. */
function segmented(label, options, value, onChange) {
  const btns = options.map(([v, l]) => h("button", { type: "button", class: "seg-b", "aria-pressed": String(v === value), "data-v": v,
    onclick: () => { btns.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.v === v))); onChange(v); } }, l));
  return h("div", { class: "seg", role: "group", "aria-label": label }, btns);
}

export function renderRelease(root, isCurrent, preset = {}) {
  document.title = "Plan a release - AFTERSHOCK";
  const state = { kind: KINDS.some(([k]) => k === preset.kind) ? preset.kind : "film", goal: GOALS.some(([g]) => g === preset.goal) ? preset.goal : null };
  const out = h("div", { "aria-live": "polite" });
  const name = h("input", { id: "rel-name", type: "text", maxlength: "120", required: true, value: preset.name || "", placeholder: "e.g. Squid Game, BTS, Zakir Khan, or your own title" });
  const like = h("input", { id: "rel-like", type: "text", maxlength: "600", value: preset.like || "", placeholder: "e.g. Squid Game, Alice in Borderland" });
  const region = h("select", { id: "rel-region", "aria-label": "Region" }, REGIONS.map(([v, l]) => h("option", { value: v }, l)));
  const home = h("select", { id: "rel-home", "aria-label": "Home market to leave out" }, h("option", { value: "" }, "Home market: none, include every market"),
    Object.entries(ISO).sort((a, b) => a[1][1].localeCompare(b[1][1])).map(([code, [, n]]) => h("option", { value: code }, `Leave out ${n}`)));
  const date = h("input", { id: "rel-date", type: "month", "aria-label": "Release month" });
  const go = h("button", { type: "submit", class: "btn btn-primary" }, "Plan it with Qloo");
  const examples = h("div", { class: "rel-examples" });
  const goalBox = h("div", null);
  const drawGoal = () => goalBox.replaceChildren(segmented("Goal", GOALS, state.goal || defaultGoal(state.kind), (v) => { state.goal = v; }));
  drawGoal();
  const focusLike = () => { like.focus(); like.scrollIntoView({ block: "center", behavior: "smooth" }); };

  const show = (plan) => { out.replaceChildren(result(plan, { date: date.value, focusLike })); out.scrollIntoView({ block: "start", behavior: "smooth" }); };
  const runLive = () => {
    const n = name.value.trim();
    if (!n) { name.focus(); return; }
    go.disabled = true;
    const scope = region.value === "any" ? "24 countries" : `every country we check in ${REGIONS.find(([v]) => v === region.value)[1]}`;
    const opts = { region: region.value, home: home.value, goal: state.goal || defaultGoal(state.kind) };
    // The plan lives in the address, so a refresh or a shared link reruns the same plan (replaceState fires no hashchange).
    const q = new URLSearchParams({ name: n, kind: state.kind, ...(like.value.trim() ? { like: like.value.trim() } : {}), ...opts, run: "1" });
    if (!opts.home) q.delete("home");
    history.replaceState(null, "", `#/release?${q}`);
    const stages = ["Finding it in Qloo", `Scoring ${scope} for this audience`, "Reading Qloo's heatmap for the cities", opts.goal === "digital" ? "Skipping venues (digital launch)" : "Looking up venues", "Asking what this audience also loves"];
    const list = h("ol", { class: "rel-stages" }, stages.map((st) => h("li", null, st)));
    out.replaceChildren(h("div", { class: "status rel-running", role: "status" }, h("p", null, h("span", { class: "pulse", "aria-hidden": "true" }), "Asking Qloo. 10 to 30 seconds; the stages run in this order:"), list));
    // The server answers once at the end, so this only paces the visible list; the order is the planner's real order.
    let at = 0;
    const tick = setInterval(() => { list.children[at]?.classList.add("done"); at += 1; if (at < stages.length) list.children[at].classList.add("now"); else clearInterval(tick); }, 3000);
    list.children[0].classList.add("now");
    planRelease(n, state.kind, like.value, opts)
      .then((plan) => { if (isCurrent()) show(plan); })
      .catch((err) => { if (isCurrent()) out.replaceChildren(failBox(err, "the release planner")); })
      .finally(() => { clearInterval(tick); go.disabled = false; });
  };
  const field = (n, label, hint, ...control) => h("div", { class: "rel-field" }, h("span", { class: "rel-step mono" }, n),
    h("div", { class: "rel-field-body" }, h("p", { class: "rel-label" }, label), hint ? h("p", { class: "rel-hint" }, hint) : null, ...control));

  add(root,
    h("section", { class: "rel-hero" },
      h("p", { class: "eyebrow mono" }, "Plan my release"),
      h("h1", null, "Releasing something new? ", h("em", null, "Find its audience first.")),
      h("p", { class: "lede" }, "A film, series, album, special or tour. Qloo finds the countries, cities and venues where its audience lives, and what to pair it with."),
      h("form", { class: "rel-form card", onsubmit: (e) => { e.preventDefault(); runLive(); } },
        field("01", "What are you releasing?", "A film, a series, an album, an artist or a comedian, spelled the way Netflix, Spotify or Wikipedia spells it.", name),
        field("02", "What kind?", null, segmented("Kind", KINDS, state.kind, (v) => { state.kind = v; if (!state.goal) drawGoal(); })),
        field("03", "Similar shows, films or artists", "Only if it is not out yet: two or three that share its audience.", like),
        // Everything below has a sensible default, so it waits behind one click instead of lengthening the form.
        h("details", { class: "rel-more", open: !!(preset.goal || preset.region || preset.home) }, h("summary", null, "More options: goal, region, release month"),
          field("04", "What's the goal?", "Tours and premieres get venues; a digital launch skips them.", goalBox),
          field("05", "Where?", "Pick a region to look deeper there, and leave out your home market to see where to expand.", h("div", { class: "rel-two" }, region, home)),
          field("06", "When?", "Your release month turns the plan into a schedule.", date)),
        go),
      h("p", { class: "rail-h mono" }, "Or open a worked example"), examples),
    out);

  if (preset.region && REGIONS.some(([v]) => v === preset.region)) region.value = preset.region;
  if (preset.home && ISO[preset.home]) home.value = preset.home;
  if (preset.name && preset.run === "1") setTimeout(runLive, 0);

  getReleaseExamples().then((idx) => {
    if (!isCurrent()) return;
    examples.replaceChildren(...idx.examples.map((x) => h("button", { type: "button", class: "rail-chip", onclick: () => {
      out.replaceChildren(loading("this example"));
      getReleaseExample(x.slug).then((plan) => { if (isCurrent()) show(plan); }).catch((err) => out.replaceChildren(failBox(err, "the example")));
    } }, h("span", null, h("span", { class: "rc-t" }, x.name), h("span", { class: "rc-n mono" }, `${x.headline}: ${x.top_countries.map((c) => c.name).join(", ")}`)))));
    if (!preset.name && idx.examples[0]) getReleaseExample(idx.examples[0].slug).then((plan) => { if (isCurrent()) out.replaceChildren(result(plan, { date: "", focusLike })); }).catch(() => {});
  }).catch(() => { examples.replaceChildren(h("p", { class: "muted" }, "Worked examples are not available right now; type a title above.")); });
}
