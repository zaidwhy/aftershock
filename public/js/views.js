import { h, s } from "./dom.js";
import { loading, errorBox, add } from "./dom.js";
import { getStorms, getStorm, getScorecard, getLedger, isMock } from "./api.js";
import { pct, plain2, dateLabel, plainWhy } from "./format.js";
import { ageLean, forecastMap, hotspotMap } from "./charts.js";
import { ISO } from "./iso.js";
import { weekMapSection } from "./weekmap.js";
import { mountGlobe, countryPanel } from "./globe.js";
import { launchBrief } from "./brief.js";
import { agentLine } from "./agent.js";
import { defaultPlan } from "./plan.js";
import { rejectedList } from "./rejected.js";
import { artistName } from "./artists.js";
import { isCatalogTitle } from "./catalog.js";
import { roadmap } from "./roadmap.js";

// AUCs that differ in the third decimal must not round to the same label.
const auc4 = (n) => (n == null ? "n/a" : n.toFixed(4));

const countryName = (code) => ISO[code]?.[1] ?? code;

const setTitle = (t) => { document.title = t ? `${t} - AFTERSHOCK` : "AFTERSHOCK - Shows travel. See where next."; };
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
// The rail favours this-or-recent releases, then the likeliest to spread, so the first chip is a title worth following.
const RAIL = 10;

// Left alone, the globe walks once through the week's top breakouts and then rests on the whole week. Any touch,
// key or scroll stops the walk for good; the tour and an open chat keep it from starting.
const IDLE_TITLES = 4;
const IDLE_START_MS = 10000;
const IDLE_STEP_MS = 6500;

function idleWalk(ids, pick, host, isCurrent) {
  if (!ids.length || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  let timer = null, done = false;
  const busy = () => document.querySelector(".tour-card, .tour-veil") || !document.querySelector(".chat")?.hidden;
  const inView = () => { const r = host.getBoundingClientRect(); return r.bottom > 80 && r.top < innerHeight * 0.6; };
  const quit = () => {
    clearTimeout(timer);
    done = true;
    ["pointerdown", "keydown", "wheel", "touchstart"].forEach((t) => removeEventListener(t, quit, true));
  };
  const walk = (k) => {
    // The tour or the chat taking over mid-walk ends it, or the walk would fight the tour for the globe.
    if (done || !isCurrent() || busy()) return quit();
    if (k >= ids.length) { pick(null); return quit(); }
    pick(ids[k]);
    timer = setTimeout(() => walk(k + 1), IDLE_STEP_MS);
  };
  const wait = () => {
    if (done || !isCurrent()) return quit();
    if (busy() || !inView()) { timer = setTimeout(wait, IDLE_START_MS); return; }
    walk(0);
  };
  ["pointerdown", "keydown", "wheel", "touchstart"].forEach((t) => addEventListener(t, quit, { capture: true, passive: true }));
  timer = setTimeout(wait, IDLE_START_MS);
}

// How it works, in three steps a newcomer can hold in their head; the third is the one only Qloo can do.
const STEPS3 = [
  ["Spot it", "A Netflix show or film enters the weekly Top 10 in just one to three countries. That is the first sign it could travel."],
  ["Predict the next country", "Netflix's own history shows where similar shows went next, and we show the reason for every country."],
  ["Plan the launch with Qloo", "An AI suggests local artists, brands and shows. Qloo checks each one against what that audience really likes, keeps the ones it supports, and maps the cities where those fans live."],
];
const USES = [
  ["A brand's marketing team", "Which show to build this week's moment marketing on (a meme, a scene, a line) before it trends in their country, and where to run local ads", "The shows predicted to arrive next, and the brands Qloo links to that audience", "That the post or ad converts"],
  ["A music label", "Where to push a song this week, when a show linked to it is heading to a new country", "The next likely country, the artists Qloo links to that audience there, and the cities", "That the push lifts streams"],
  ["An artist's team", "Where to post, play a DJ set or announce a show next", "Shows whose viewers love the artist, and where both audiences live", "That fans will buy tickets"],
  ["A promoter", "Which cities to look at for a tour or a one-off show", "Plan my release: countries, cities and the right kind of venues", "Ticket demand or open dates"],
];
// One small drawing per step, in the site's line style: a tremor, an arc between two places, a check.
const STEP_ICONS = [
  ["M2 13h4l2.2-6 3.2 12 3-9 1.8 3H22"],
  ["M6.6 16.4C7.5 9 11 6.3 16.6 6.5", "M14.2 4.2l2.6 2.3-2.4 2.5"],
  ["M7.5 12.4l3.1 3.1 6-6.4"],
];
const stepIcon = (k) => s("svg", { class: "flow-ico", viewBox: "0 0 24 24", "aria-hidden": "true" },
  k === 1 ? [s("circle", { cx: 5, cy: 18, r: 2.4 }), s("circle", { cx: 19, cy: 6, r: 2.4 })] : null,
  k === 2 ? s("circle", { cx: 12, cy: 12, r: 9 }) : null,
  STEP_ICONS[k].map((d) => s("path", { d })));
// Said by a first-time user, a marketer, after seeing the trending list; quoted as he asked to be named.
const USER_VOICE = { quote: "Seeing in one glance what's trending.", who: "Head of Marketing, Nobero" };
// Recent releases before catalog titles, then titles whose Qloo kit was made for that title's own audience before
// countrywide ones (Qloo's picks for the whole country, which say less about the title), then forecast chance.
const kitRank = (s) => (s.has_kit ? (s.kit_specific === false ? 1 : 0) : 2);
const breakoutOrder = (dataYear) => (a, b) =>
  isCatalogTitle(a.meta?.year, dataYear) - isCatalogTitle(b.meta?.year, dataYear) || kitRank(a) - kitRank(b)
  || (b.top_forecast?.probability ?? -1) - (a.top_forecast?.probability ?? -1);
// The week's list opens on the likeliest movers; the long tail folds away.
const STORMS_SHOWN = 8;

/** One real prediction from this week, end to end, so a first-time visitor sees the whole product in one card. */
function fillExample(box, week, isCurrent) {
  const id = week.featured_plan?.id;
  if (!id) return;
  getStorm(id).then((st) => {
    if (!isCurrent()) return;
    const all = st.spillover?.forecasts || [];
    const next = all[0];
    const row = next && (st.launch_kit || []).find((r) => r.code === next.code);
    if (!next || !row) return;
    const confirmed = row.plan?.confirmed || [];
    const dropped = row.plan?.dropped || {};
    const asked = confirmed.length + (dropped.not_placed || 0) + (dropped.not_in_qloo || 0);
    const kind = /tv/i.test(st.category || "") ? "series" : "film";
    const genre = st.meta?.genres?.[0]?.toLowerCase();
    const origin = (st.origin_countries || []).map((o) => o.name).join(", ");
    const fact = (label, value) => h("div", { class: "ex-row" }, h("dt", null, label), h("dd", null, value));
    box.replaceChildren(
      h("div", { class: "ex-head" },
        st.meta?.image ? h("img", { class: "ex-poster", src: st.meta.image, alt: "", width: 84, height: 120, loading: "lazy" }) : null,
        h("div", null,
          h("p", { class: "ex-tag mono" }, "A real prediction from this week"),
          h("h3", null, st.title),
          h("p", { class: "ex-sub" }, `A ${genre ? `${genre} ` : ""}${kind}, popular in ${origin} this week. Where does it go next?`)),
        h("div", { class: "ex-route" },
          h("span", { class: "ex-pct" }, pct(next.probability)),
          h("span", { class: "ex-path" }, h("span", null, (st.origin_countries || [])[0]?.name || origin), h("span", { class: "ex-arrow", "aria-hidden": "true" }), h("strong", null, next.name)),
          h("span", { class: "ex-when" }, `chance within ${st.spillover.horizon_weeks} weeks`))),
      h("dl", { class: "ex-facts" },
        fact("Predicted next country", h("span", null, h("strong", null, next.name), `, a ${pct(next.probability)} chance within ${st.spillover.horizon_weeks} weeks: the most likely of ${all.length}`)),
        next.why ? fact("Why", plainWhy(next.why)) : null,
        row.hotspots?.places?.length ? fact("Where its fans live", row.hotspots.places.join(", ")) : null,
        confirmed.length ? fact("Partners Qloo supports", confirmed.slice(0, 6).map((c) => c.name).join(", ")) : null,
        asked ? fact("AI ideas Qloo filtered out", `${asked - confirmed.length} of ${asked}`) : null),
      h("a", { class: "btn btn-primary", href: `#/plan/${encodeURIComponent(st.id)}/${encodeURIComponent(next.code)}` }, `Open the full launch plan for ${next.name}`));
    box.hidden = false;
  }).catch(() => {});
}

export function renderHome(root, isCurrent, followId = null) {
  setTitle("");
  const stormBox = h("div", null);
  const stats = h("div", { class: "stage-stats", hidden: true });
  const proofBar = h("div", { class: "qproof", hidden: true });
  const testBox = h("div", { class: "fc-test", hidden: true });
  const agentBox = h("p", { class: "agent-line", hidden: true });
  const testDetail = h("details", { hidden: true });
  const qlooDetail = h("details", { hidden: true });
  const exampleBox = h("div", { class: "example-card", hidden: true });
  const hook = h("button", { type: "button", class: "hook", hidden: true });
  const planCta = h("a", { class: "btn", href: "#/plan", "data-tour": "plan" }, "Explore a launch plan");
  const globeHost = h("div", { class: "globe-host", role: "img", "aria-label": "Globe of the Netflix shows trending this week and where each is predicted to go next" });
  const panel = h("aside", { class: "globe-panel", "aria-live": "polite", hidden: true });
  const rail = h("div", { class: "title-rail", role: "toolbar", "aria-label": "Follow one show on the globe", "data-tour": "rail" });
  const legend = h("p", { class: "globe-legend mono" },
    h("span", { class: "lg lg-origin" }, "popular now"), h("span", { class: "lg lg-chance" }, "chance it arrives next"),
    h("span", { class: "lg lg-qloo" }, "where fans live (Qloo)"));
  const toList = () => document.getElementById("live-h")?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  defaultPlan().then((d) => {
    if (!isCurrent() || !d) return;
    planCta.href = `#/plan/${encodeURIComponent(d.id)}/${encodeURIComponent(d.code)}`;
  }).catch(() => {});
  const stormsP = getStorms();

  add(root,
    h("section", { class: "stage" },
      h("div", { class: "stage-copy" },
        h("p", { class: "eyebrow mono" }, "Netflix trend predictor, powered by Qloo"),
        h("h1", null, "Shows travel. ", h("em", null, "See where next.")),
        hook,
        h("p", { class: "lede" }, "When a Netflix show gets popular in one country, AFTERSHOCK predicts the next country, and ",
          h("strong", { class: "qloo-word" }, "Qloo"), "'s taste data plans the launch there: the cities, artists and brands."),
        h("div", { class: "cta-row" },
          h("button", { type: "button", class: "btn btn-primary", onclick: toList }, "See this week's predictions"),
          planCta,
          h("button", { type: "button", class: "tour-link", "data-tour": "replay-inline", onclick: () => window.dispatchEvent(new CustomEvent("aftershock:tour")) },
            h("span", { class: "tour-link-dot", "aria-hidden": "true" }), "How it works, in 60 s")),
        h("p", { class: "stats-q" }, "AI can suggest anything. Does the audience actually want it?"),
        stats),
      h("div", { class: "stage-globe", "data-tour": "globe" }, globeHost, panel, legend),
      rail),
    mockNote(),
    h("section", { class: "how", "aria-labelledby": "how-h", "data-tour": "how" },
      h("h2", { id: "how-h" }, "From popular in one country to a launch plan"),
      h("ol", { class: "flow flow-3" }, STEPS3.map(([name, line], k) =>
        h("li", { class: k === 2 ? "flow-qloo" : null },
          h("span", { class: "flow-top" }, stepIcon(k), h("span", { class: "flow-n mono" }, String(k + 1).padStart(2, "0"))),
          h("strong", null, name), h("span", null, line))))),
    h("section", { class: "example-band", "aria-labelledby": "ex-h" },
      h("h2", { id: "ex-h" }, "See it in action"),
      exampleBox,
      h("figure", { class: "voice" },
        h("blockquote", null, h("p", null, `\u201c${USER_VOICE.quote}\u201d`)),
        h("figcaption", null, USER_VOICE.who, h("span", { class: "muted" }, ", on the trending list below")))),
    h("section", { "aria-labelledby": "live-h", "data-tour": "storms" },
      h("h2", { id: "live-h" }, "Trending this week"),
      agentBox,
      stormBox),
    h("section", { class: "qloo-band", "aria-labelledby": "qp-h", "data-tour": "qloo" },
      h("h2", { id: "qp-h" }, "AI can suggest anything. Qloo checks it."),
      proofBar),
    h("section", { class: "fc-band", "aria-labelledby": "fc-h" },
      h("h2", { id: "fc-h" }, "How good are the predictions?"),
      testBox),
    h("section", { class: "next-band", "aria-labelledby": "next-h" },
      h("h2", { id: "next-h" }, "What's next"),
      roadmap()),
    h("section", { class: "more", "aria-labelledby": "more-h" },
      h("h2", { id: "more-h" }, "More detail"),
      h("details", null, h("summary", null, "Who it is for, and the decision it helps with"),
        h("div", { class: "table-wrap" }, h("table", { class: "plain use-table" },
          h("thead", null, h("tr", null, h("th", null, "Who"), h("th", null, "The decision"), h("th", null, "What AFTERSHOCK gives them"), h("th", null, "What it does not prove"))),
          h("tbody", null, USES.map((r) => h("tr", null, r.map((c, i) => h("td", { class: i === 3 ? "ev-gap" : null }, i === 0 ? h("strong", null, c) : c)))))))),
      testDetail,
      qlooDetail,
      h("details", null, h("summary", null, "What we do not claim"),
        h("ul", { class: "more-list" },
          h("li", null, "Every plan is a shortlist to research further: a likely opportunity, not a guaranteed one."),
          h("li", null, "No customers, pilots or prices yet."),
          h("li", null, "Predictions are chances, not promises. Checking them against what really happened is paused until Netflix permits reading its newer files."),
          h("li", null, "No permission from Netflix is claimed; this is a hackathon prototype.")))));

  getScorecard().then((sc) => {
    if (!isCurrent()) return;
    const gc = sc.grounded_plan?.counts;
    const lift = sc.lead_time?.baseline?.hit_rate ? sc.lead_time.model.hit_rate / sc.lead_time.baseline.hit_rate : null;
    const locked = (sc.spillover?.locked ?? 0) + (sc.ripple?.locked ?? 0);
    const n = gc ? gc.confirmed + gc.not_placed + gc.not_in_qloo : 0;
    const p = (x) => `${Math.round((x / n) * 100)}%`;
    const tiles = [
      gc ? [p(gc.not_placed + gc.not_in_qloo), "of an AI's partner ideas had no backing in Qloo's audience data"] : null,
      lift ? [`${lift.toFixed(1)}x`, `better than the obvious guess at naming the next country (${whole(sc.lead_time.model.breakouts)} past cases)`] : null,
      locked ? [whole(locked), "predictions recorded before Netflix published the results"] : null,
    ].filter(Boolean);
    stats.replaceChildren(...tiles.map(([v, k]) => h("div", { class: "stat" }, h("span", { class: "stat-v" }, v), h("span", { class: "stat-k" }, k))),
      h("a", { class: "stats-how", href: "#/scorecard" }, "See how we tested it"));
    stats.hidden = !tiles.length;
    const lt = sc.lead_time;
    if (lt?.model?.breakouts && lt.breakouts_that_spread_at_all) {
      const share = (x) => `${(x * 100).toFixed(1)}%`;
      const spread = lt.breakouts_that_spread_at_all;
      const rateRow = (label, rate, max, cls) => h("div", { class: `fc-row ${cls}` }, h("span", { class: "fc-l" }, label),
        h("span", { class: "fc-track" }, h("span", { class: "fc-fill", style: `width:${(rate / max) * 100}%` })), h("span", { class: "fc-v mono" }, share(rate)));
      const ours = lt.model.hit_rate, guess = lt.baseline.hit_rate;
      const oursSpread = lt.model.hit_breakouts / spread, guessSpread = lt.baseline.hit_breakouts / spread;
      testBox.replaceChildren(
        h("p", { class: "qp-lede" }, `We tested it on ${whole(lt.model.breakouts)} past cases it had never seen, against the obvious guess: the ${lt.top_k} countries where the most shows reach the Top 10.`),
        h("div", { class: "fc-grid" },
          h("div", { class: "fc-card" }, h("p", { class: "gp-label mono" }, `All ${whole(lt.model.breakouts)} cases`),
            rateRow("AFTERSHOCK", ours, Math.max(ours, guess), "fc-us"), rateRow("Obvious guess", guess, Math.max(ours, guess), "fc-base"),
            h("p", { class: "fc-say" }, `${(ours / guess).toFixed(1)}x better than the obvious guess.`)),
          h("div", { class: "fc-card" }, h("p", { class: "gp-label mono" }, `The ${whole(spread)} that spread to another country`),
            rateRow("AFTERSHOCK", oursSpread, Math.max(oursSpread, guessSpread), "fc-us"), rateRow("Obvious guess", guessSpread, Math.max(oursSpread, guessSpread), "fc-base"),
            h("p", { class: "fc-say" }, `When a show did spread, our top ${lt.top_k} usually named where.`))),
        h("p", { class: "qp-foot" }, h("a", { href: "#/scorecard" }, "Every test, including what did not work")));
      testDetail.replaceChildren(h("summary", null, "How we tested the predictions"),
        h("ul", { class: "more-list" },
          h("li", null, `${whole(lt.model.breakouts)} past cases were hidden from the model; for each it named the ${lt.top_k} countries it expected next.`),
          h("li", null, `The fair comparison is the obvious guess: the ${lt.top_k} countries where the most shows reach the Top 10.`),
          h("li", null, "Over all cases the rate is low, because most shows never spread anywhere."),
          h("li", null, "So it points at the right next country far more often than the obvious guess. It is a shortlist, not a promise that a show will chart.")));
      testDetail.hidden = false;
      testBox.hidden = false;
    }
    if (gc) {
      const seg = (cls, x, label) => h("span", { class: `qp-seg ${cls}`, style: `flex:${x}` }, h("span", { class: "qp-v mono" }, p(x)), h("span", { class: "qp-l" }, label));
      proofBar.replaceChildren(
        h("p", { class: "qp-lede" }, `We asked an AI alone for launch partners: ${whole(n)} suggestions. Here is how many Qloo's audience data supported.`),
        h("div", { class: "qp-bar", role: "img", "aria-label": `${p(gc.confirmed)} supported by Qloo, ${p(gc.not_placed)} known to Qloo but not for that audience, ${p(gc.not_in_qloo)} not in Qloo's data yet` },
          seg("qp-ok", gc.confirmed, "supported by Qloo for that audience"), seg("qp-np", gc.not_placed, "Qloo knows them, but not for these viewers"), seg("qp-nq", gc.not_in_qloo, "not in Qloo's data yet")),
        h("p", { class: "qp-foot" }, "So in AFTERSHOCK the AI only suggests, and Qloo decides what goes in the plan. Unsupported does not always mean wrong: some names are simply missing from Qloo's data. ",
          h("a", { href: "#/scorecard" }, "See how we tested it")));
      qlooDetail.replaceChildren(h("summary", null, "How the Qloo check works"),
        h("ul", { class: "more-list" },
          h("li", null, `An AI alone was asked for launch partners (artists, brands, shows, films) for 81 show-and-country audiences: ${whole(n)} names.`),
          h("li", null, "Each name was looked up in Qloo and checked against the people who watch that show in that country."),
          h("li", null, "In a plan only the names Qloo supports stay; Qloo adds its own picks for that audience and maps the cities where it lives.")));
      qlooDetail.hidden = false;
      proofBar.hidden = false;
    }
  }).catch(() => {});

  agentLine(agentBox, isCurrent);
  stormsP.then((week) => fillExample(exampleBox, week, isCurrent)).catch(() => {});

  let globe = null;
  const showPanel = ({ code, storm }, week) => {
    panel.replaceChildren(h("button", { type: "button", class: "gp-close", "aria-label": "Close", onclick: () => { panel.hidden = true; } }, "×"), countryPanel(code, storm, week));
    panel.hidden = false;
  };
  stormsP.then((week) => {
    if (!isCurrent()) return;
    const dataYear = Number(String(week.week).slice(0, 4));
    const ranked = [...week.storms].filter((s) => s.top_forecast).sort(breakoutOrder(dataYear)).slice(0, RAIL);
    const chips = [];
    const pick = async (id) => {
      chips.forEach((c) => c.setAttribute("aria-pressed", String(c.dataset.id === (id || ""))));
      panel.hidden = true;
      if (!globe) return;
      const st = await globe.focus(id || null);
      if (!isCurrent() || !st) return;
      const next = st.spillover?.forecasts?.[0];
      if (next) globe.select(next.code);
    };
    chips.push(h("button", { type: "button", class: "rail-chip", "data-id": "", "aria-pressed": String(!followId), onclick: () => pick(null) }, "All shows"));
    for (const s of ranked) chips.push(h("button", { type: "button", class: "rail-chip", "data-id": s.id, "aria-pressed": "false", onclick: () => pick(s.id) },
      s.meta?.image ? h("img", { src: s.meta.image, alt: "", loading: "lazy", width: 28, height: 40 }) : null,
      h("span", null, h("span", { class: "rc-t" }, s.title), h("span", { class: "rc-n" }, `Next: ${s.top_forecast.name} ${pct(s.top_forecast.probability)}`))));
    rail.replaceChildren(h("span", { class: "rail-h mono" }, "Follow one show"), ...chips);
    const live = ranked.slice(0, 5);
    let turn = 0;
    const paintHook = () => {
      const x = live[turn % live.length];
      const from = x.origin_countries?.[0]?.name || "one country";
      hook.replaceChildren(h("span", { class: "hook-live mono" }, h("span", { class: "hook-dot", "aria-hidden": "true" }), "Live this week"),
        h("span", { class: "hook-text" }, h("strong", { class: "hook-title" }, x.title), h("span", { class: "hook-from" }, ` in ${from}`),
          h("span", { class: "hook-arrow", "aria-hidden": "true" }), h("span", { class: "hook-next" }, `${x.top_forecast.name} ${pct(x.top_forecast.probability)}`)));
      hook.setAttribute("aria-label", `${x.title} is popular in ${from}; predicted next: ${x.top_forecast.name}, ${pct(x.top_forecast.probability)}. Show it on the globe.`);
      hook.onclick = () => pick(x.id);
    };
    if (live.length) {
      paintHook();
      hook.hidden = false;
      if (!matchMedia("(prefers-reduced-motion: reduce)").matches) {
        const cycle = setInterval(() => {
          if (!isCurrent()) { clearInterval(cycle); return; }
          if (hook.matches(":hover, :focus-visible")) return;
          turn += 1;
          paintHook();
        }, 3600);
      }
    }
    // Paint first, then pull in the 2 MB WebGL library.
    requestAnimationFrame(() => mountGlobe(globeHost, week, (sel) => showPanel(sel, week)).then((g) => {
      if (!isCurrent()) { g.destroy(); return; }
      globe = g;
      // The tour follows a breakout to show the globe at work; when it ends, the globe goes back to the whole week.
      const reset = () => { if (isCurrent()) pick(null); };
      window.addEventListener("aftershock:globe-reset", reset);
      const stop = () => { if (!isCurrent()) { g.destroy(); window.removeEventListener("hashchange", stop); window.removeEventListener("aftershock:globe-reset", reset); } };
      window.addEventListener("hashchange", stop);
      if (followId) pick(followId);
      else idleWalk(ranked.slice(0, IDLE_TITLES).map((x) => x.id), pick, globeHost, isCurrent);
    }).catch(() => {
      // No WebGL (old phone, locked-down browser): the flat map still answers the same question.
      if (!isCurrent()) return;
      globeHost.classList.add("globe-fallback");
      globeHost.replaceChildren(weekMapSection(week.map, week.week, isCurrent, week.storms, followId));
    }));
  }).catch(() => {});

  load(stormBox, "this week's breakouts", isCurrent, () => stormsP.catch(() => getStorms()), ({ week, storms }) => {
    if (!storms.length) { add(stormBox, h("p", { class: "status" }, `No title entered the Top 10 in only 1 to 3 countries in the week of ${week}.`)); return; }
    const dataYear = Number(String(week).slice(0, 4));
    const catalog = (s) => isCatalogTitle(s.meta?.year, dataYear);
    const ranked = [...storms].sort(breakoutOrder(dataYear));
    const maxP = Math.max(0.0001, ...ranked.map((s) => s.top_forecast?.probability ?? 0));
    const stormRow = (s) => h("li", null,
        h("a", { href: `#/storm/${encodeURIComponent(s.id)}`, class: "storm-link" },
          s.meta?.image ? h("img", { class: "storm-poster", src: s.meta.image, alt: "", loading: "lazy", width: 42, height: 60 }) : h("span", { class: "storm-poster" }),
          h("span", { class: "storm-main" },
            h("span", { class: "storm-title" }, s.title, s.season ? h("span", { class: "muted" }, ` ${s.season}`) : null),
            h("span", { class: "storm-meta" }, s.meta && (s.meta.year || s.meta.genres?.length) ? h("span", { class: "storm-facts" }, yearGenres(s.meta.year, s.meta.genres)) : null,
              `Popular in ${origins(s.origin_countries)}`, catalog(s) ? h("span", { class: "tag tag-quiet" }, "older show") : null, s.has_kit ? h("span", { class: "tag tag-kit" }, s.kit_specific === false ? "Plan ready (general picks)" : "Plan ready") : null)),
          h("span", { class: "storm-next" }, s.top_forecast
            ? [h("span", null, "Next: ", h("strong", null, s.top_forecast.name), " ", h("span", { class: "mono" }, pct(s.top_forecast.probability))),
               h("span", { class: "pbar", role: "img", "aria-label": `${pct(s.top_forecast.probability)} chance, scaled to the top storm this week` },
                 h("span", { style: `width:${Math.max(2, (s.top_forecast.probability / maxP) * 100)}%` }))]
            : "No forecast yet")));
    add(stormBox,
      h("p", { class: "muted" }, `Week of ${dayLabel(week)}: ${storms.length} Netflix shows and films became popular in just 1 to 3 countries. For each, the country we predict is next.`),
      h("ul", { class: "storm-list" }, ranked.slice(0, STORMS_SHOWN).map(stormRow)),
      ranked.length > STORMS_SHOWN ? h("details", { class: "storm-more" }, h("summary", null, `Show the other ${ranked.length - STORMS_SHOWN}`),
        h("ul", { class: "storm-list" }, ranked.slice(STORMS_SHOWN).map(stormRow))) : null);
  });
}


/* ------------------------------------------------------------------ storm */
export function renderStorm(root, id, isCurrent) {
  setTitle("Breakout");
  load(root, "this breakout", isCurrent, () => getStorm(id), (st) => {
    setTitle(st.title);
    const fc = st.spillover?.forecasts || [];
    const mapBox = h("div", { class: "map-box" }, loading("the map"));
    add(root, 
      h("p", { class: "crumb" }, h("a", { href: "#/" }, "All trending shows")),
      archivedBanner(st.archived_week),
      h("h1", null, st.title, st.season ? h("span", { class: "h1-sub" }, ` ${st.season}`) : null),
      titleHead(st),
      answerLine(st, fc),
      mockNote(),
      h("section", { "aria-labelledby": "map-h" },
        h("h2", { id: "map-h" }, `Where it goes next (within ${st.spillover?.horizon_weeks ?? "?"} weeks)`),
        h("p", { class: "follow-link" }, h("a", { href: `#/?follow=${encodeURIComponent(st.id)}` }, "Follow it on the globe")),
        mapBox,
        h("p", { class: "legend" }, h("span", { class: "key key-origin" }), "Popular here now (outlined)", h("span", { class: "key key-ramp" }), "Darker = higher chance it arrives"),
        fc.length ? forecastTable(fc) : h("p", { class: "status" }, "No forecast rows for this title.")),
      kitSection(st),
      h("p", { class: "locked mono" }, st.spillover?.locked_at ? `Recorded in advance on ${dateLabel(st.spillover.locked_at)} | prediction id ${st.spillover.ledger_id}` : "Not recorded yet."));
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
    h("p", { class: "meta" }, `${/tv/i.test(st.category || "") ? "Series" : st.category ? "Film" : "Show"} | week of ${st.origin_week} | popular in `, h("strong", null, origins(st.origin_countries))));
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
    top ? h("span", null, "Most likely next country: ", h("strong", null, top.name), " ", h("span", { class: "mono" }, `(${pct(top.probability)})`)) : null,
    top && n ? h("span", { class: "answer-sep", "aria-hidden": "true" }, "|") : null,
    n ? h("a", { href: "#/", onclick: scrollTo("par-h") }, `Qloo's launch picks for ${n} ${n === 1 ? "country" : "countries"} below`) : null);
}

/** Hotspot map and place names for one kit country; nothing when the data is missing. */
function hotspotBlock(r) {
  const hs = r.hotspots;
  if (!hs || (!hs.cells?.length && !hs.places?.length)) return null;
  const box = h("div", { class: "hs" });
  if (hs.cells?.length) {
    hotspotMap(r.code, hs.cells).then((svg) => { if (svg) box.prepend(svg); }).catch(() => {});
  }
  if (hs.places?.length) box.append(h("p", { class: "hs-places" }, "Where fans live: ", h("strong", null, hs.places.join(", "))));
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

/** "AI ideas, checked by Qloo": names an AI proposed that Qloo places with this audience, in Qloo's order, plus a
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
    h("h4", null, "AI ideas, checked by Qloo"),
    h("p", { class: "plan-sum" }, `Of ${total} names an AI suggested for this audience, Qloo confirmed ${yes.length}; ${np} it knows but does not place with these viewers here, ${nq} it has no data on.`),
    groups.length ? h("ul", { class: "plan-list" }, groups.map(([d, list]) => h("li", null,
      h("span", { class: "plan-dom" }, KIT_LABELS[d]), " ",
      list.flatMap((c, i) => [i ? ", " : null, d === "artist" ? artistName(c.name) : c.name, c.both ? h("span", { class: "plan-both" }, " (also in Qloo's picks)") : null])))) : null,
    rejectedList(plan.rejected));
}

/** "Copy launch plan": clipboard write inside the click; if it is refused, show the text selected in a box. */
function briefControl(st, rows) {
  const status = h("span", { class: "muted", role: "status" });
  const fallback = h("div", { class: "brief-fallback", hidden: true });
  const btn = h("button", { type: "button", class: "btn btn-small" }, "Copy launch plan");
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
    h("strong", null, r.generic ? "Mostly the whole country's taste" : "Specific to this show"), `: ${Math.round(r.specificity * 100)}%`));
  return h("section", { "aria-labelledby": "par-h" },
    h("h2", { id: "par-h" }, "Qloo's picks: what this audience loves there"),
    h("p", { class: "muted" }, "From Qloo: what this show's viewers like far more than average in each predicted country, as a starting point for a local launch. Netflix history says where; Qloo says what to do there. It does not change the chances."),
    briefControl(st, rows),
    anyCommon ? h("p", { class: "kit-cap" }, h("span", { class: "kit-common" }, "Greyed out"), ": popular across the whole country anyway, not specific to this show") : null,
    h("div", { class: "kit-cols" }, rows.map((r) => h("div", { class: "kit" },
      h("h3", null, countryName(r.code)),
      r.brief ? h("p", { class: "plan-link" }, h("a", { href: `#/plan/${encodeURIComponent(st.id)}/${encodeURIComponent(r.code)}` }, "See the launch plan here")) : null,
      specific(r),
      h("dl", { class: "kit-list" }, Object.keys(KIT_LABELS).filter((d) => r.kit[d]?.length).map((d) => h("div", { class: d === "brand" ? "kit-minor" : null },
        h("dt", null, KIT_LABELS[d]), h("dd", null, names(r, d))))),
      planBlock(r), hotspotBlock(r), eventsBlock(r)))),
    rows.some((r) => r.hotspots?.cells?.length || r.hotspots?.places?.length)
      ? h("p", { class: "hs-credit" }, "Where fans live: from Qloo's audience map; place names © OpenStreetMap contributors.") : null);
}

/* ----------------------------------------------------------------- ripple */
const earlyRead = (x) => (x.early_ratio == null ? "n/a" : `${x.early_ratio.toFixed(1)}x${x.early_status === "pending" ? " pending" : ""}`);

export function renderRipple(root) {
  setTitle("Song forecasts");
  add(root, h("p", { class: "crumb" }, h("a", { href: "#/" }, "All trending shows")),
    h("h1", null, "No song forecasts yet"),
    h("p", null, "Song forecasts are not published right now. The breakouts and the scorecard are."));
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
      h("caption", null, "Countries ranked by chance: the chance the show enters that country's Top 10 within the time shown."),
      h("thead", null, h("tr", null, ["#", "Country", "Chance", "Why"].map((t, i) => h("th", { scope: "col", class: i === 2 ? "num" : null }, t)))),
      h("tbody", null, fc.map((f, i) => h("tr", null,
        h("td", { class: "mono rank" }, i + 1),
        h("th", { scope: "row" }, f.name),
        h("td", { class: "num mono prob" }, pct(f.probability)),
        h("td", { class: "why" }, plainWhy(f.why)))))));
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
    h("span", { class: "mono" }, ` (${Math.round(e.specificity * 100)}% specific to the show)`)) : null);
  return h("section", { "aria-labelledby": "kitcheck-h" },
    h("h2", { id: "kitcheck-h" }, "What Qloo adds: are its picks about the show?"),
    h("p", null, h("strong", { class: "mono" }, `${kc.specific} of ${kc.kits}`), ` sets of Qloo picks this week are specific to their show; ${kc.generic} mostly match the whole country's taste. On average they are `,
      h("span", { class: "mono" }, `${Math.round(kc.mean_specificity * 100)}%`), " specific to their show."),
    h("p", { class: "muted" }, "For every set of picks we also ask Qloo what the whole country likes, with no show named. A set counts as whole-country taste when most of its picks repeat that list, and as specific to the show when they do not."),
    h("ul", { class: "kit-examples" }, example("Specific to the show", kc.example_specific), example("Whole-country taste", kc.example_generic)));
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
    h("p", { class: "legend" }, h("span", { class: "dot dot-real" }), "Our top 3 (solid)", h("span", { class: "dot dot-placebo" }), "The obvious guess: the 3 countries where the most shows reach the Top 10 (outlined)"),
    s("svg", { viewBox: `0 0 ${W} ${H}`, class: "lw-svg", role: "img", "aria-label": label }, g));
}

function caseStudy(c) {
  const [title, season] = c.title;
  const shown = season && season !== "N/A" && !season.startsWith(title) ? `${title}: ${season}` : title;
  const picks = c.top3.map((p) => `${COUNTRY(p.country)} (${Math.round(p.probability * 100)}%${p.charted_after_weeks == null ? ", did not reach the Top 10" : `, reached the Top 10 ${weeks(p.charted_after_weeks)} later`})`);
  const hit = c.top3.some((p) => p.charted_after_weeks != null);
  const others = c.all_countries_charted_within_horizon.length ? `Within 4 weeks it reached the Top 10 in ${c.all_countries_charted_within_horizon.map(COUNTRY).join(", ")}.` : "Within 4 weeks it reached no other Top 10.";
  return h("li", null,
    h("strong", null, shown), ` (${c.category === "Films" ? "film" : "series"}, popular from ${dayLabel(c.breakout_week)} in ${c.origin_countries.map(COUNTRY).join(", ")}). `,
    h("span", { class: "mono" }, hit ? "Hit. " : "Miss. "), `Our top 3: ${picks.join("; ")}. ${others}`);
}

/** How much warning the held-out backtest says a distributor would have had; nothing without the measurement. */
function warningSection(sc) {
  const lt = sc.lead_time;
  if (!lt) return null;
  const m = lt.model, b = lt.baseline, spread = lt.breakouts_that_spread_at_all;
  return h("section", { "aria-labelledby": "warning-h" },
    h("h2", { id: "warning-h" }, "How much warning it gives"),
    h("p", null, `In ${whole(m.breakouts)} past cases the model had not seen, at least one of its top ${lt.top_k} countries had the show in its Top 10 within ${lt.horizon_weeks} weeks `,
      h("strong", { class: "mono" }, `${share1(m.hit_rate)} of the time`), ` (${m.hit_breakouts} cases), against ${share1(b.hit_rate)} (${b.hit_breakouts}) for the obvious guess, the ${lt.top_k} countries where the most shows reach the Top 10. `,
      `Of the ${whole(m.picks)} top-${lt.top_k} picks, ${share1(m.per_pick_precision)} charted (${share1(b.per_pick_precision)} for the baseline).`),
    spread != null ? h("p", null, `Most shows do not spread at all: only ${spread} of ${whole(m.breakouts)} reached any other country's Top 10 within ${lt.horizon_weeks} weeks. Our top ${lt.top_k} caught ${m.hit_breakouts} of those ${spread}; the obvious guess caught ${b.hit_breakouts}.`) : null,
    m.lead_weeks.median != null ? h("p", null, "When a predicted country did pick the show up, it did so a median of ", h("strong", { class: "mono" }, weeks(m.lead_weeks.median)),
      ` after the show got popular (mean ${m.lead_weeks.mean.toFixed(1)}). That is the warning a brand, a distributor or a promoter would have had.`) : null,
    m.lead_weeks.median != null ? leadChart(lt) : null,
    h("h3", null, "Three cases, chosen by a rule fixed before looking"),
    h("p", { class: "muted" }, `The rule: ${lt.case_study_rule.replace("held-out breakouts", "past cases the model never saw").replace("top-1 forecast probability", "chance for their most likely country").replace("then title", "then name")}. Misses are included.`),
    h("ul", { class: "kit-examples" }, lt.case_studies.map(caseStudy)),
    h("p", { class: "muted" }, "Tested on past data with Netflix history only (no Qloo data), March to October 2026: each prediction made from the week the show got popular, using only earlier shows. It is not the prediction history."));
}

/** One explanation of the LLM-names numbers, from the counts in grounded_plan.json: of N proposed names, the share Qloo
 *  knows, the share it links to this audience in this country, and the 71% it does not back (unknown + known but not linked). */
function numbersExplained(gp) {
  const { confirmed: c, not_placed: np, not_in_qloo: nq } = gp.counts, n = c + np + nq;
  const p = (x) => `${Math.round((x / n) * 100)}%`;
  return h("div", { class: "num-explained" },
    h("p", null, `Across ${gp.pairs} show-and-country pairs, an AI (a large language model) suggested ${whole(n)} artists, brands, films and shows for the audience. Of those ${whole(n)} names:`),
    h("ul", null,
      h("li", null, h("strong", { class: "mono" }, p(np + c)), ` are names Qloo knows (${whole(np + c)}).`),
      h("li", null, h("strong", { class: "mono" }, p(c)), ` are ones Qloo links to this audience in this country (${whole(c)}). Only these go into a launch plan.`),
      h("li", null, h("strong", { class: "mono" }, p(np + nq)), ` are not supported by Qloo (${whole(np + nq)}): `,
        `${p(nq)} (${whole(nq)}) Qloo does not know at all, plus ${p(np)} (${whole(np)}) it knows but does not link to this audience in this country.`)));
}

/** The pre-registered Qloo-versus-LLM result; an honest empty slot until the scored run exists. */
function llmSection(sc) {
  const ex = sc.kit_experiment;
  const slot = ex
    ? h("div", { class: "kit-exp" },
      h("p", null, h("strong", null, ex.verdict ? ex.verdict.replace(/^LLM /, "The AI's list was ").replace("title-specific", "specific to the show") : "Result recorded"), ex.scored_pairs ? ` across ${ex.scored_pairs} show-and-country pairs.` : "."),
      h("p", null, `How much each list changes once the show is named, against the same source's list for the country alone (higher means more about this show): Qloo ${share(ex.qloo)}, AI ${share(ex.llm)}.`),
      h("p", null, `Only ${share(ex.grounding_share)} of the AI's picks are names Qloo knows as the right kind of thing (the same figure as above, before checking audience), so some are not audience taste at all.`,
        ex.grounded_pairs ? ` Counting only those, the AI still leads (${share(ex.grounded_llm)} against Qloo's ${share(ex.grounded_qloo)} on ${ex.grounded_pairs} pairs).` : ""),
      h("p", null, "What we do about it: every set of Qloo picks is checked against Qloo's answer for the whole country and labelled when it mostly matches it, so a plan never claims to be about a show when it is not."),
      h("p", null, h("a", { href: GITHUB_EXPERIMENT, rel: "noopener" }, "How it was registered and scored")))
    : h("p", { class: "muted" }, "Registered on 27 Oct before any data was collected; results will appear here. ",
      h("a", { href: GITHUB_EXPERIMENT, rel: "noopener" }, "Read the registration"));
  const gp = sc.grounded_plan;
  if (gp?.unbacked_share == null) return h("section", { "aria-labelledby": "llm-h" }, h("h2", { id: "llm-h" }, "Qloo versus an AI (pre-registered)"), slot);
  // Lead with the result that shapes the product; the registered test stays below it in full.
  return h("section", { "aria-labelledby": "llm-h" },
    h("h2", { id: "llm-h" }, `An AI alone: Qloo's data did not support ${share(gp.unbacked_share)} of what it suggested`),
    ex && ex.qloo != null && ex.llm != null && gp.specificity_plan != null ? h("div", { class: "kit-cmp" },
      h("p", { class: "hero-cmp-h" }, "How specific to the show are the picks? (0 to 1, higher is more specific)"),
      h("p", { class: "hero-cmp" }, [[ex.qloo, "Qloo alone"], [ex.llm, "AI alone"], [gp.specificity_plan, "AI checked by Qloo (exploratory)"]].map(([v, l]) =>
        h("span", { class: "hero-cmp-i" }, h("strong", null, v.toFixed(2)), " ", l))),
      h("p", null, `${share(gp.unbacked_share)} of the AI's names are not supported by Qloo's data.`)) : null,
    gp.counts ? numbersExplained(gp) : h("p", null, `Across ${gp.pairs} title-country pairs an LLM named ${whole(gp.picks_checked)} artists, brands, films and shows for the audience. Qloo placed ${share(1 - gp.unbacked_share)} of them with that audience; the rest it either does not know or does not link to these viewers. Only the confirmed names go into a launch brief.`),
    gp.specificity_plan != null ? h("p", null, `The combined plan (the AI's names, kept only when Qloo supports them) is `, h("strong", null, `${gp.specificity_plan.toFixed(2)} specific to the show`),
      `, against ${gp.specificity_llm.toFixed(2)} for the AI's raw picks, on ${gp.specificity_pairs} pairs.`) : null,
    h("p", { class: "muted" }, "Exploratory: designed after the registered result below, on the same pairs and cached AI answers. It is not pre-registered."),
    h("h3", { id: "llm-reg-h" }, "The registered test: which list is more specific to the show"),
    slot);
}

// Plain meanings for the measured words the results page keeps, so it stays exact and still readable.
const GLOSSARY = [
  ["Breakout", "A show or film that entered Netflix's weekly Top 10 in only 1 to 3 countries: the first sign it could travel."],
  ["Chart", "To enter a country's Netflix Top 10."],
  ["The obvious guess (baseline)", "Always naming the 3 countries where the most shows reach the Top 10. A useful prediction has to beat it."],
  ["Backtest", "Testing on past cases the model had never seen, using only what was known at the time."],
  ["ROC AUC", "How often the model ranks a country that later charted above one that did not: 1.0 is perfect, 0.5 is a coin flip."],
  ["Spillover", "Our name for a show spreading from one country to the next."],
  ["Qloo's picks (kit)", "What Qloo says a show's viewers in a country like far more than average: artists, shows, films, brands."],
  ["Prediction history (ledger)", "Every prediction, recorded before Netflix published the result and chained so none can be edited later."],
  ["AI (LLM)", "A large language model, here Gemini, asked for launch partners on its own."],
];

export function renderScorecard(root, isCurrent) {
  setTitle("Prediction results");
  const box = h("div", null);
  add(root, h("h1", null, "Prediction results"),
    h("p", { class: "pitch" }, "How well AFTERSHOCK's predictions and Qloo's checks did on past data, including what did not work. Nothing here is edited after the fact."),
    h("details", { class: "fold glossary" }, h("summary", null, "Words used on this page"),
      h("dl", { class: "glossary-list" }, GLOSSARY.map(([k, v]) => h("div", null, h("dt", null, k), h("dd", null, v))))),
    mockNote(), box);
  load(box, "the prediction results", isCurrent, getScorecard, (sc) => {
    const sp = sc.spillover || {}, rp = sc.ripple || {}, bt = sc.backtest || {};
    const bs = bt.spillover || {}, br = bt.ripple || {};
    const pl = br.placebo || {};
    const row = (label, value) => h("tr", null, h("th", { scope: "row" }, label), h("td", { class: "mono" }, value));
    const so = sp.so_far;
    const dl = (pairs) => h("dl", null, pairs.map(([k, v]) => h("div", null, h("dt", null, k), h("dd", { class: "mono" }, v ?? "n/a"))));
    const spillSection = h("section", { class: "score-block", "aria-label": "Next-country predictions" },
      h("h2", null, "Next-country predictions (spillover)"),
      h("p", { class: "state" }, h("strong", { class: "mono" }, whole(sp.locked) ?? "n/a"), " predictions recorded in advance.",
        sp.graded ? ` ${sp.graded} graded so far.` : " Checking them against what really happened is paused until Netflix permits reading its newer files."),
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
        h("h2", { id: "bt-h" }, "Where a show goes next: tested on past cases"),
        scored == null ? h("p", { class: "muted" }, "The backtest has not been generated yet.")
          : h("p", null, h("strong", null, `Ranks a country that went on to chart above one that did not ${Math.round(scored * 100)}% of the time`), ` (ROC AUC ${plain2(scored)}), on ${whole(bs.test_breakouts)} past breakouts.`),
        h("p", { class: "muted" }, "Netflix history only: how often each country followed earlier shows from the same countries. March to October 2026 cases the model had not seen. The next-country prediction uses no Qloo data."),
        tableOf("Next-country test", row(`Next country: ROC AUC with Netflix history only (${bs.test_breakouts ?? "n/a"} past cases)`, auc4(bs.history_auc)))),
      h("section", { "aria-labelledby": "ledger-h" },
        h("h2", { id: "ledger-h" }, "Prediction history"),
        sc.top_pick?.breakouts > 0 ? h("div", { class: "score-block", "aria-label": "Early read" },
          h("h3", null, "Early read: last week's top picks"),
          h("p", null, `${sc.top_pick.top_pick_hits} of ${sc.top_pick.breakouts} top picks have already charted. If the forecasts were exactly calibrated we would expect ${sc.top_pick.expected_hits}. Always picking the country that charts the most titles (${sc.top_pick.baseline_country}) gets ${sc.top_pick.baseline_hits}.`),
          h("p", { class: "muted" }, "Defined before the data existed and reported whichever way it goes. The 4-week result is the real grade. ",
            h("a", { href: "https://github.com/zaidwhy/aftershock/blob/main/docs/EARLY_GRADE.md", rel: "noopener" }, "How it is defined"))) : null,
        h("div", { class: "grid2" }, spillSection, rp.locked ? rippleSection : null),
        h("div", { class: "ledger-row" }, h("a", { class: "btn", href: "#/ledger" }, "Open the prediction history"),
          sc.ledger_intact == null ? null : h("span", { class: "muted" }, sc.ledger_intact ? "Ledger hash chain verified." : "Ledger hash chain FAILED verification."),
          sc.data_week ? h("span", { class: "muted" }, `Netflix data through the week of ${sc.data_week}.`) : null)),
      h("section", { "aria-labelledby": "dnw-h" },
        h("h2", { id: "dnw-h" }, "What did not work"),
        h("h3", null, "Qloo added nothing to the next-country prediction"),
        tableOf("No lift from Qloo", [
          row(`Same ${bs.subset_breakouts ?? "n/a"} cases, Netflix history only`, auc4(bs.history_auc_same_subset)),
          row(`Same ${bs.subset_breakouts ?? "n/a"}, history plus Qloo`, auc4(bs.qloo_auc))]),
        h("details", { class: "fold" }, h("summary", null, "The song tests"),
        h("p", null, `No Qloo signal predicted which soundtrack songs spike on Wikipedia: ${br.n_artists ?? "n/a"} artists in ${br.n_shows ?? "n/a"} shows were scored, and on 2024+ releases the Qloo age gap beat a placebo spike measured before release at p = ${plain2(pl["2024_plus"]?.["p: gap real minus gap placebo"])}.`),
        h("p", { class: "muted" }, "The song tables and the placebo check are in ", h("a", { href: GITHUB_README_3, rel: "noopener" }, "README section 3"), "."))),
      h("section", { class: "caveat", "aria-labelledby": "dne-h" },
        h("h2", { id: "dne-h" }, "What this does not establish"),
        h("ul", { class: "more-list caveat-list" },
          h("li", null, "Qloo describes the taste of groups, not of any individual: an audience profile says what a group tends to like, not what a given person will do."),
          h("li", null, "Predictions are chances, so a 20% prediction that does not happen was not wrong, and one that does was not proven right."),
          h("li", null, "The next-country test shows Netflix history predicts spread well; it does not show that Qloo adds to it (no lift on the 200-case subset)."),
          h("li", null, "The next-country prediction uses no Qloo data, and Qloo's picks have not been tested against real results."),
          h("li", null, "The song test collected 490 songs from 34 soundtracks; 229 artists in 24 of those shows (4 released 2024 or later) had enough Qloo audience profiles to be scored, where a placement means a song on the title's official soundtrack album, which can include songs a show barely used; its outcome (Wikipedia page spike) is a proxy for attention, and Qloo audiences are today's, which postdate those releases."),
          h("li", null, "No Qloo signal predicted which songs spike."),
          h("li", null, "Many new 2026 shows have no Qloo audience profile yet."),
          h("li", null, "The model would not have picked Running Up That Hill for Stranger Things 4."),
          h("li", null, "The prediction history, where each prediction is recorded before Netflix publishes the result, is the real test."))));
    if (wantWarning) { wantWarning = false; document.getElementById("warning-h")?.scrollIntoView(); }
  });
}

/* ----------------------------------------------------------------- ledger */
export function renderLedger(root, isCurrent) {
  setTitle("Ledger");
  const box = h("div", null);
  add(root, h("p", { class: "crumb" }, h("a", { href: "#/scorecard" }, "Prediction results")), h("h1", null, "Prediction history"), mockNote(), box);
  load(box, "the ledger", isCurrent, getLedger, (lg) => {
    const when = (iso) => (iso ? dateLabel(iso) : "n/a");
    const state = { pending: "Pending", hit: "Hit", miss: "Miss" };
    add(box,
      h("p", { class: "pitch" }, "Every prediction AFTERSHOCK made, recorded before Netflix published the result. Each line carries a fingerprint of the line before, so changing an old prediction would break every line after it. The raw file is on GitHub."),
      h("dl", { class: "ledger-stats" },
        [["Predictions", whole(lg.total)], ["Different shows", whole(lg.titles)], ["First recorded", when(lg.first_locked)], ["Last recorded", when(lg.last_locked)],
          ["Fingerprint chain", lg.intact ? "Verified" : "FAILED verification"]].map(([k, v]) => h("div", null, h("dt", null, k), h("dd", { class: "mono" }, v)))),
      h("p", null, "Timing: every prediction was recorded before Netflix published any later week for that show."),
      h("p", { class: "ledger-raw" }, h("a", { class: "btn", href: lg.raw_url, rel: "noopener" }, "Open the raw file on GitHub")),
      h("h2", null, `The ${lg.rows.length} most recent predictions`),
      h("p", { class: "muted" }, "Newest first, most likely first within one batch. Each row is the chance that the show reaches that country's Top 10 within 4 weeks. Status stays Pending until it is checked against Netflix's data, which is paused until Netflix permits it."),
      h("div", { class: "table-wrap", tabindex: "0", role: "region", "aria-label": "Recent predictions, scrolls sideways on narrow screens" },
        h("table", { class: "plain ledger-table" }, h("caption", { class: "sr-only" }, "Most recent predictions"),
          h("thead", null, h("tr", null, ["Recorded", "Show", "Country", "Chance", "Status"].map((t, i) => h("th", { scope: "col", class: i === 3 ? "num" : null }, t)))),
          h("tbody", null, lg.rows.map((r) => h("tr", null,
            h("td", { class: "mono" }, dateLabel(r.locked_at)), h("th", { scope: "row" }, r.title), h("td", null, r.country),
            h("td", { class: "num mono" }, pct(r.probability)), h("td", null, state[r.status] ?? r.status)))))));
  });
}

/* ----------------------------------------------------------------- method */
export function renderMethod(root) {
  setTitle("How it is built");
  add(root, 
    h("h1", null, "How it is built"),
    h("p", { class: "pitch" }, "The technical detail, for anyone who wants to check it. In short: Netflix's own history predicts the next country, Qloo plans what to do there, and every prediction is recorded before the result is known."),
    h("section", null, h("h2", null, "Spillover: which country is next"),
      h("p", null, "Start with a title that entered Netflix's Top 10 in 1 to 3 countries. The probability that each other country charts it within 4 weeks comes from Netflix history only: how often that country followed past breakouts from the same origin countries, smoothed toward the same-category rate for that country, which is smoothed toward the country's base rate."),
      h("p", null, "Backtest: ROC AUC 0.817 on 829 test breakouts (Mar-Oct 2026). We also tested Qloo as an extra feature on a 200-breakout subset: AUC 0.8188 with history only against 0.8182 with Qloo, so no lift. Qloo had an in-country value for only 2.8% of title-country pairs (975 of 35,344). So Qloo's role in SPILLOVER is the partners list: artists the title's audience over-indexes on in each forecast country."),
      h("p", null, "Every candidate country's probability is locked in the ledger, not just the top rows, so AUC and calibration can be graded. Grading happens once a title's 4-week horizon has passed in Netflix's weekly data.")),
    h("section", null, h("h2", null, "Qloo's picks and where fans live: what to do there"),
      h("p", null, "For each show's top three predicted countries, Qloo is asked which shows, films, brands and artists the show's viewers there like far more than average, and where in the country that audience lives (a heatmap, reduced to its three strongest places and named with OpenStreetMap). Neither changes the probabilities, and neither has been validated against outcomes."),
      h("p", null, "Sync Scout is a discovery tool: it ranks the artists a show's audience likes by the age gap between the artist's audience and the show's. It ranks artists, not scenes.")),
    h("section", null, h("h2", null, "Ripple: the song score, tested"),
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
        h("li", null, h("strong", null, "Netflix Top 10"), ": the per-country file Netflix links from its Top 10 site, credited. We have no permission from Netflix and claim none; its Terms of Use restrict automated access and reuse, so this is a prototype, and any use beyond it would need Netflix's permission."),
        h("li", null, h("strong", null, "Qloo API"), ": hackathon key. Results are shown in the app; raw responses are never published in the repo. Audiences are aggregates, not individuals."),
        h("li", null, h("strong", null, "Wikimedia Pageviews API"), "."),
        h("li", null, h("strong", null, "MusicBrainz"), " (CC0): soundtrack songs."),
        h("li", null, h("strong", null, "OpenStreetMap Nominatim"), ": place names, credited to OpenStreetMap contributors."),
        h("li", null, h("strong", null, "Gemini"), ": only for the pre-registered comparison.")),
      h("p", null, "An earlier song dataset collected from Tunefind was removed from the product and the current repo after we read its terms (older commits still hold it); nothing derived from it is used.")));
}

export function renderNotFound(root) {
  setTitle("Not found");
  add(root, h("h1", null, "Page not found"), h("p", null, h("a", { href: "#/" }, "Back to this week's trending shows")));
}
