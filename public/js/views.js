import { h } from "./dom.js";
import { loading, errorBox, add } from "./dom.js";
import { getStorms, getStorm, getScorecard, getReplays, scoreSongs, scoutShow, isMock } from "./api.js";
import { pct, plain2, dateLabel, monthLabel, views } from "./format.js";
import { seismograph, ripplePanel, ageLean, forecastMap, dumbbell, hotspotMap } from "./charts.js";
import { ISO } from "./iso.js";

// AUCs that differ in the third decimal must not round to the same label.
const auc4 = (n) => (n == null ? "n/a" : n.toFixed(4));

const countryName = (code) => ISO[code]?.[1] ?? code;

const setTitle = (t) => { document.title = t ? `${t} - AFTERSHOCK` : "AFTERSHOCK - a Qloo taste agent for breakout shows"; };
const mockNote = () => (isMock() ? h("p", { class: "mock-flag" }, "Mock data (?mock=1). Numbers are placeholders, except the replay pageviews.") : null);
/** "song | artist" (first "|"), else "song by artist" split on the last " by ". Mirrors the API. */
function parseSongLine(line) {
  const pipeAt = line.indexOf("|");
  if (pipeAt >= 0) return { song: line.slice(0, pipeAt).trim(), artist: line.slice(pipeAt + 1).trim() };
  const byAt = line.toLowerCase().lastIndexOf(" by ");
  if (byAt < 0) return { song: line.trim(), artist: "" };
  return { song: line.slice(0, byAt).trim(), artist: line.slice(byAt + 4).trim() };
}
const whole = (n) => (n == null ? null : n.toLocaleString("en-US"));
const scrollTo = (id) => (e) => { e.preventDefault(); document.getElementById(id)?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }); };
const origins = (list) => list.map((c) => c.name).join(", ");

/** Run a fetch into a container with loading and error states. */
function load(container, what, isCurrent, fetcher, render) {
  const run = () => {
    container.replaceChildren(loading(what));
    fetcher().then((data) => {
      if (!isCurrent()) return;
      container.replaceChildren();
      render(data, container);
    }).catch((err) => {
      if (!isCurrent()) return;
      container.replaceChildren(errorBox(what, err, run));
    });
  };
  run();
}

/* ---------------------------------------------------------------- landing */
export function renderHome(root, isCurrent) {
  setTitle("");
  const chartBox = h("div", { class: "hero-chart" });
  const stormBox = h("div", null);
  const heroBox = h("div", null);
  const proof = h("aside", { class: "proof", "aria-label": "Evidence at a glance" });
  const stormsP = getStorms();
  add(root,
    h("section", { class: "hero" },
      h("div", { class: "hero-top" },
        h("div", { class: "hero-copy" },
          h("p", { class: "eyebrow" }, "A Qloo taste agent for breakout shows"),
          h("h1", null, "A show breaks out in one country. ", h("em", null, "Where does it land next, and what travels with it?")),
          h("p", { class: "pitch" }, "Every week the agent finds titles that just broke out on Netflix in one to three countries. Netflix history says where each is likely to chart next. Qloo's taste graph says what to pair it with there: the artists and brands that title's audience loves in each country, and the cities where that audience lives. Every forecast is locked publicly before the outcome exists."),
          h("ul", { class: "hero-links" },
            h("li", null, h("a", { href: "#/", onclick: scrollTo("live-h") }, "This week's breakouts")),
            h("li", null, h("a", { href: "#/scout" }, "Sync Scout - find artists from outside a show's generation")),
            h("li", null, h("a", { href: "#/try" }, "Try it - explore songs placed in any show")))),
        proof),
      h("p", { class: "buyer mono" }, "For local distributors, music publishers and promoters: know where a breakout goes next and what to pair it with there, before the competition does."),
      heroBox,
      chartBox),
    mockNote(),
    h("section", { "aria-labelledby": "live-h" },
      h("h2", { id: "live-h" }, "Live storms this week"),
      h("p", { class: "muted" }, "Storms: titles that just broke out in 1 to 3 countries."),
      stormBox));

  Promise.all([getScorecard(), stormsP]).then(([sc, st]) => {
    if (!isCurrent()) return;
    const bt = sc.backtest || {};
    const kits = st.storms.filter((x) => x.has_kit).length;
    const locked = (sc.spillover?.locked ?? 0) + (sc.ripple?.locked ?? 0);
    const items = [
      ["Forecasts locked", whole(locked), "forecasts locked publicly before the outcome"],
      bt.spillover?.history_auc != null ? ["Backtest AUC", plain2(bt.spillover.history_auc), `on ${whole(bt.spillover.test_breakouts)} breakouts`] : null,
      ["Storms with a Qloo kit", String(kits), `of ${st.storms.length} this week`],
      ["Breakouts this week", String(st.storms.length), `week of ${st.week}`],
    ].filter(Boolean);
    proof.append(...items.map(([k, v, note]) => h("div", { class: "proof-item" },
      h("p", { class: "proof-k" }, k), h("p", { class: "proof-v" }, v), h("p", { class: "proof-n" }, note))));
  }).catch(() => { proof.hidden = true; });

  stormsP.then((st) => {
    const x = st.hero;
    if (!isCurrent() || !x) return;
    const join = (a) => a.join(", ");
    const step = (label, ...kids) => h("div", { class: "ex-step" }, h("p", { class: "ex-k mono" }, label), ...kids);
    heroBox.append(h("section", { class: "example", "aria-labelledby": "ex-h" },
      h("h2", { id: "ex-h" }, `This week's clearest example: ${x.title}`),
      h("div", { class: "ex-grid" },
        step("1 Breakout", h("p", null, `Broke out in ${origins(x.origin_countries)}`)),
        step("2 Likely next", h("p", null, `Likely next: `, h("strong", null, x.country), " ", h("span", { class: "mono" }, pct(x.probability))),
          x.why ? h("p", { class: "ex-why" }, x.why) : null),
        step("3 Pair it with", h("p", null, `Qloo: this audience in ${x.country} loves ${join(x.artists)}`, x.brands.length ? `; brands ${join(x.brands)}` : "")),
        step("4 Start in", h("p", null, `Start in ${join(x.places)}`))),
      h("p", { class: "ex-link" }, h("a", { href: `#/storm/${encodeURIComponent(x.id)}` }, "See the full forecast"))));
  }).catch(() => {});

  load(chartBox, "the replay", isCurrent, getReplays, ({ replays }) => {
    if (!replays?.length) { chartBox.append(h("p", { class: "status" }, "No replays are published yet.")); return; }
    const caption = h("p", { class: "hero-cap" });
    const stage = h("div", { class: "stage" });
    const picks = h("div", { class: "picks", role: "group", "aria-label": "Choose a replay" });
    const show = (i) => {
      const r = replays[i];
      stage.replaceChildren(seismograph(r));
      const peak = r.monthly_views.reduce((a, b) => (b[1] > a[1] ? b : a));
      const base = r.monthly_views[0][1];
      caption.replaceChildren(h("strong", null, r.song), ` by ${r.artist}, placed in ${r.show} (released ${r.release}). English Wikipedia views went from about ${views(base)} in ${monthLabel(r.monthly_views[0][0])} to ${views(peak[1])} in ${monthLabel(peak[0])}.`);
      picks.querySelectorAll("button").forEach((b, j) => b.setAttribute("aria-pressed", String(j === i)));
    };
    replays.forEach((r, i) => picks.append(h("button", { type: "button", class: "chip", onclick: () => show(i) }, r.song)));
    chartBox.append(stage, caption, picks);
    show(0);
  });

  load(stormBox, "this week's storms", isCurrent, () => stormsP.catch(() => getStorms()), ({ week, storms }) => {
    if (!storms.length) { add(stormBox, h("p", { class: "status" }, `No title entered the Top 10 in only 1 to 3 countries in the week of ${week}.`)); return; }
    const grp = (s) => (s.kit_specific ? 0 : s.has_kit ? 1 : 2);
    const ranked = [...storms].sort((a, b) => grp(a) - grp(b) || (b.top_forecast?.probability ?? -1) - (a.top_forecast?.probability ?? -1));
    const maxP = Math.max(0.0001, ...ranked.map((s) => s.top_forecast?.probability ?? 0));
    add(stormBox,
      h("p", { class: "muted" }, `Week of ${week}. Titles that entered Netflix's Top 10 in 1 to 3 countries, most likely to spread first.`),
      h("p", { class: "muted" }, "Qloo kit: what this title's audience loves in each forecast country. Countrywide: Qloo had little title-specific signal, so the kit mostly shows the country's general taste."),
      h("ul", { class: "storm-list" }, ranked.map((s) => h("li", null,
        h("a", { href: `#/storm/${encodeURIComponent(s.id)}`, class: "storm-link" },
          h("span", { class: "storm-title" }, s.title, s.season ? h("span", { class: "muted" }, ` ${s.season}`) : null),
          h("span", { class: "storm-meta" }, `Origin: ${origins(s.origin_countries)}`, s.has_kit ? h("span", { class: "tag tag-kit" }, s.kit_specific === false ? "Qloo kit (countrywide)" : "Qloo kit") : null),
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
      h("h1", null, st.title, st.season ? h("span", { class: "h1-sub" }, ` ${st.season}`) : null),
      h("p", { class: "meta" }, `${st.category || "Title"} | origin week ${st.origin_week} | broke out in `, h("strong", null, origins(st.origin_countries))),
      answerLine(st, fc),
      mockNote(),
      h("section", { "aria-labelledby": "map-h" },
        h("h2", { id: "map-h" }, `Where it charts next (${st.spillover?.horizon_weeks ?? "?"} week horizon)`),
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
  });
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

const KIT_LABELS = { artist: "Artists", tv_show: "TV shows", movie: "Films", brand: "Brands" };

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
    h("strong", null, r.generic ? "Mostly countrywide taste" : "Title-specific"), ` ${Math.round(r.specificity * 100)}% specific to this title`));
  return h("section", { "aria-labelledby": "par-h" },
    h("h2", { id: "par-h" }, "Launch kit: what this audience loves there"),
    h("p", { class: "muted" }, "From Qloo: what the title's audience over-indexes on in each forecast country, as a starting point for a local launch. Netflix history says where; this says what to do there. It does not change the probabilities."),
    anyCommon ? h("p", { class: "kit-cap" }, h("span", { class: "kit-common" }, "muted"), ": what the whole country likes anyway (Qloo, no title)") : null,
    h("div", { class: "kit-cols" }, rows.map((r) => h("div", { class: "kit" },
      h("h3", null, countryName(r.code)), specific(r),
      h("dl", { class: "kit-list" }, Object.keys(KIT_LABELS).filter((d) => r.kit[d]?.length).map((d) => h("div", null,
        h("dt", null, KIT_LABELS[d]), h("dd", null, names(r, d))))),
      hotspotBlock(r)))),
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
    h("table", { class: "fc" },
      h("caption", null, "Ranked forecast. Probability is the chance the title enters that country's Top 10 within the horizon."),
      h("thead", null, h("tr", null, ["#", "Country", "Probability", "Why"].map((t, i) => h("th", { scope: "col", class: i === 2 ? "num" : null }, t)))),
      h("tbody", null, fc.map((f, i) => h("tr", null,
        h("td", { class: "mono" }, i + 1),
        h("th", { scope: "row" }, f.name),
        h("td", { class: "num mono prob" }, pct(f.probability)),
        h("td", { class: "why" }, f.why))))));
}

/* -------------------------------------------------------------------- try */
export function renderTry(root, isCurrent) {
  setTitle("Try it");
  const out = h("div", { class: "try-out", "aria-live": "polite" });
  const show = h("input", { id: "show", name: "show", type: "text", required: true, autocomplete: "off", placeholder: "Stranger Things", maxlength: "120" });
  const songs = h("textarea", { id: "songs", name: "songs", rows: "6", required: true, "aria-describedby": "songs-help", placeholder: "Running Up That Hill by Kate Bush\nMaster of Puppets by Metallica\nPsycho Killer by Talking Heads" });
  const asOf = h("input", { id: "asof", name: "asof", type: "date", min: "2015-08-01", "aria-describedby": "asof-help" });
  const btn = h("button", { type: "submit", class: "btn btn-primary" }, "Score these songs");
  const form = h("form", { class: "try-form", novalidate: true,
    onsubmit: (e) => {
      e.preventDefault();
      const showName = show.value.trim();
      const lines = songs.value.split("\n").map((l) => l.trim()).filter(Boolean);
      const parsed = lines.map(parseSongLine);
      const bad = parsed.findIndex((p) => !p.song || !p.artist);
      if (!showName) { out.replaceChildren(errorBox("your input", new Error("Enter a show name."))); show.focus(); return; }
      if (!parsed.length) { out.replaceChildren(errorBox("your input", new Error("Enter at least one line as: song by artist."))); songs.focus(); return; }
      if (parsed.length > 8) { out.replaceChildren(errorBox("your input", new Error(`Up to 8 songs are allowed, you entered ${parsed.length}.`))); songs.focus(); return; }
      if (bad >= 0) { out.replaceChildren(errorBox("your input", new Error(`Line ${bad + 1} needs both a song and an artist, written "song by artist" or "song | artist".`))); songs.focus(); return; }
      btn.disabled = true;
      out.replaceChildren(loading("scores from Qloo"));
      scoreSongs(showName, parsed, asOf.value || null).then((r) => {
        if (!isCurrent()) return;
        out.replaceChildren();
        if (r.resolved === false || r.show_resolved === false) add(out, h("div", { class: "status status-error", role: "alert" }, h("p", null, `"${showName}" was not found in Qloo, so no audience profile exists to score against.`)));
        else add(out, h("h2", null, `Ripple scores for ${showName}`), ripplePanel(r));
      }).catch((err) => { if (isCurrent()) out.replaceChildren(errorBox("the scores", err)); })
        .finally(() => { btn.disabled = false; });
    } },
    h("div", { class: "field" }, h("label", { for: "show" }, "Show or film"), show),
    h("div", { class: "field" }, h("label", { for: "songs" }, "Songs, one per line"), songs,
      h("p", { id: "songs-help", class: "help" }, "Format: \"song by artist\" or \"song | artist\". Up to 8 lines. Limited to 10 live scorings per hour per visitor.")),
    h("div", { class: "field" }, h("label", { for: "asof" }, "Score as of (optional)"), asOf,
      h("p", { id: "asof-help", class: "help" }, "The release date, to replay a past show. It changes only the Wikipedia context (prior views are read before this date); the Qloo audiences, and so the score, are today's, so a past replay carries Qloo's later knowledge. Try Stranger Things as of 2022-05-27 with Running Up That Hill by Kate Bush, Master of Puppets by Metallica, Psycho Killer by Talking Heads.")),
    btn);
  add(root, h("h1", null, "Try it on any show"),
    h("p", { class: "pitch" }, "Name a show and the songs placed in it. AFTERSHOCK resolves each artist in Qloo and scores it as the Qloo age gap between each artist's audience and the show's: how far outside the show's generation a song reaches, from 0 to 1. It is an explorer, not a hit predictor. Prior Wikipedia views are shown as context and are not scored."),
    mockNote(), form, out);
}

/* ------------------------------------------------------------ sync scout */
export function renderScout(root, isCurrent) {
  setTitle("Sync Scout");
  const out = h("div", { class: "try-out", "aria-live": "polite" });
  const show = h("input", { id: "scout-show", name: "show", type: "text", required: true, autocomplete: "off", placeholder: "Wednesday", maxlength: "120" });
  const btn = h("button", { type: "submit", class: "btn btn-primary" }, "Scout artists");
  const form = h("form", { class: "try-form", novalidate: true,
    onsubmit: (e) => {
      e.preventDefault();
      const name = show.value.trim();
      if (!name) { out.replaceChildren(errorBox("your input", new Error("Enter a show or film name."))); show.focus(); return; }
      btn.disabled = true;
      out.replaceChildren(loading("candidates from Qloo (about 15 seconds the first time, faster when cached)"));
      scoutShow(name).then((r) => {
        if (!isCurrent()) return;
        out.replaceChildren();
        if (r.resolved === false) {
          add(out, h("div", { class: "status status-error", role: "alert" }, h("p", null, `Could not scout "${name}": ${r.reason || "Qloo has no data for it."}`)));
          return;
        }
        if (!r.artists?.length) { add(out, h("p", { class: "status" }, `Qloo returned no artists with an audience profile for ${r.show}.`)); return; }
        add(out, h("h2", null, `Artists for ${r.show}`),
          h("p", { class: "muted" }, `Top ${r.artists.length} of ${r.profiled} profiled artists from ${r.candidates} candidates, ranked by age gap.${r.truncated ? " The Qloo call budget ran out, so the list is partial." : ""}`),
          h("ol", { class: "songs scout-list" }, r.artists.map((a) => h("li", { class: "song" },
            h("div", { class: "song-head" }, h("strong", null, a.name), h("span", { class: "muted mono" }, `taste rank ${a.taste_rank}`)),
            h("div", { class: "score-row" }, h("span", { class: "score-num mono" }, a.gap.toFixed(2)),
              h("div", { class: "bar", role: "img", "aria-label": `Age gap ${a.gap.toFixed(2)} of 1` }, h("span", { style: `width:${Math.round(a.gap * 100)}%` }))),
            h("p", { class: "song-math" }, a.why)))));
      }).catch((err) => { if (isCurrent()) out.replaceChildren(errorBox("the scout", err)); })
        .finally(() => { btn.disabled = false; });
    } },
    h("div", { class: "field" }, h("label", { for: "scout-show" }, "Show or film"), show,
      h("p", { class: "help" }, "Uses up to 60 live Qloo calls and takes about 15 seconds when not cached. Shares the limit of 10 live requests per hour per visitor with Try it.")),
    btn);
  add(root, h("h1", null, "Sync Scout"),
    h("p", { class: "pitch" }, "For a music supervisor: which artists does this show's taste neighbourhood like, whose audience sits outside the show's own generation? Candidates come from Qloo; the ranking is the age gap, from 0 to 1."),
    h("p", { class: "caveat-line" }, "Ranks artists, not scenes. A discovery tool: these are on-taste artists whose own audience sits outside the show's age groups. In our test, the age gap did not predict which soundtrack songs spike (see Scorecard), so treat this as a shortlist, not a forecast."),
    mockNote(), form, out);
}

/* -------------------------------------------------------------- scorecard */
export function renderScorecard(root, isCurrent) {
  setTitle("Scorecard");
  const box = h("div", null);
  add(root, h("h1", null, "Scorecard"), h("p", { class: "pitch" }, "What the signals did on past events, then the live ledger: forecasts are locked first and graded later. Nothing here is edited after the fact."), mockNote(), box);
  load(box, "the scorecard", isCurrent, getScorecard, (sc) => {
    const sp = sc.spillover || {}, rp = sc.ripple || {}, bt = sc.backtest || {};
    const bs = bt.spillover || {}, br = bt.ripple || {};
    const pl = br.placebo || {};
    const row = (label, value) => h("tr", null, h("th", { scope: "row" }, label), h("td", { class: "mono" }, value));
    const gapCell = br.gap_2024_plus == null ? "n/a" : `${plain2(br.gap_2024_plus)}${br.gap_2024_plus_p == null ? "" : ` (permutation p = ${br.gap_2024_plus_p.toFixed(2)})`}`;
    const placeboRow = (label, a, b) => h("tr", null, h("th", { scope: "row" }, label),
      [pl["2024_plus"]?.[a], pl["2024_plus"]?.[b], pl.all?.[a], pl.all?.[b]].map((v) => h("td", { class: "num mono" }, plain2(v))));
    const recent = pl["2024_plus"] || {};
    const rows = [
      ["Qloo age gap", recent["real: gap"], recent["placebo: gap"]],
      ["Obscurity", recent["real: obscurity"], recent["placebo: obscurity (its own pre-window)"]],
    ].filter((r) => r && r[1] != null && r[2] != null).map(([label, real, placebo]) => ({ label, real, placebo }));
    const evidence = rows.length ? h("section", { "aria-labelledby": "why-h" },
      h("h2", { id: "why-h" }, "What we tested"),
      h("div", { class: "db-box" },
        h("p", { class: "legend" }, h("span", { class: "dot dot-real" }), "Real spike", h("span", { class: "dot dot-placebo" }), "Placebo spike, measured before release"),
        dumbbell(rows, `Within-show Spearman with the artist's Wikipedia spike on 2024+ releases, real spike versus placebo spike. ${rows.map((r) => `${r.label}: real ${plain2(r.real)}, placebo ${plain2(r.placebo)}`).join("; ")}.`)),
      h("p", { class: "muted" }, "Mean within-show Spearman with the artist's Wikipedia spike, real versus a placebo measured before release, on licensed MusicBrainz soundtrack data. No Qloo signal is significant here; see the README for the full test and why an earlier result was discarded.")) : null;
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
    add(box,
      evidence,
      h("h2", null, "Placebo check"),
      h("p", { class: "muted" }, "Mean within-show Spearman against the real spike and against a placebo spike measured entirely before release. A score that predicts the placebo is picking up regression to the mean, not the show."),
      h("div", { class: "table-wrap", tabindex: "0", role: "region", "aria-label": "Placebo check, scrolls sideways on narrow screens" }, h("table", { class: "plain" }, h("caption", { class: "sr-only" }, "Real versus placebo Spearman"),
        h("thead", null, h("tr", null, ["Score", `Real, 2024+ (${pl["2024_plus"]?.n_shows ?? "n/a"} shows)`, "Placebo, 2024+", `Real, all (${pl.all?.n_shows ?? "n/a"} shows)`, "Placebo, all"].map((t, i) => h("th", { scope: "col", class: i ? "num" : null }, t)))),
        h("tbody", null,
          placeboRow("Obscurity", "real: obscurity", "placebo: obscurity (its own pre-window)"),
          placeboRow("Qloo age gap", "real: gap", "placebo: gap")))),
      h("p", { class: "muted" }, `Real minus placebo for the Qloo age gap: permutation p = ${plain2(pl["2024_plus"]?.["p: gap real minus gap placebo"])} on 2024+ releases, ${plain2(pl.all?.["p: gap real minus gap placebo"])} on all.`),
      h("h2", null, "Backtests on past events"),
      h("div", { class: "table-wrap", tabindex: "0", role: "region", "aria-label": "Backtest results, scrolls sideways on narrow screens" }, h("table", { class: "plain" }, h("caption", { class: "sr-only" }, "Backtest results"),
        h("thead", null, h("tr", null, ["Measure", "Value"].map((t) => h("th", { scope: "col" }, t)))),
        h("tbody", null,
          row(`Spillover: history-only AUC (${bs.test_breakouts ?? "n/a"} breakouts)`, auc4(bs.history_auc)),
          row(`Spillover: same ${bs.subset_breakouts ?? "n/a"} breakouts, history-only`, auc4(bs.history_auc_same_subset)),
          row(`Spillover: same ${bs.subset_breakouts ?? "n/a"}, history + Qloo`, auc4(bs.qloo_auc)),
          row("Ripple: Qloo age gap, 2024+ releases (Spearman)", gapCell),
          row("Ripple: Qloo taste fit, 2024+", plain2(br.fit_2024_plus)),
          row("Ripple: obscurity, 2024+ (see placebo)", plain2(br.obscurity_2024_plus))))),
      h("p", { class: "muted" }, `Ripple backtest: ${br.n_artists ?? "n/a"} artists placed in ${br.n_shows ?? "n/a"} shows (${br.n_shows_2024_plus ?? "n/a"} released 2024 or later). Outcome is the artist's Wikipedia page spike, days +7 to +35 over days -60 to -8.`),
      h("h2", null, "Live ledger"),
      h("div", { class: "grid2" }, spillSection, rippleSection),
      h("div", { class: "ledger-row" }, sc.ledger_url ? h("a", { class: "btn", href: sc.ledger_url, rel: "noopener" }, "Open the public ledger") : null,
        sc.ledger_intact == null ? null : h("span", { class: "muted" }, sc.ledger_intact ? "Ledger hash chain verified." : "Ledger hash chain FAILED verification."),
        sc.data_week ? h("span", { class: "muted" }, `Netflix data through the week of ${sc.data_week}.`) : null),
      h("section", { class: "caveat", "aria-labelledby": "dne-h" },
        h("h2", { id: "dne-h" }, "What this does not establish"),
        h("p", null, "Qloo describes the taste of groups, not of any individual: an audience profile says what a group tends to like, not what a given person will do. Forecasts are probabilities, so a 20% forecast that does not happen was not wrong, and one that does was not proven right. The spillover backtest shows Netflix history predicts spread well; it does not show that Qloo adds to it (no lift on the 200-breakout subset). The country forecast uses no Qloo data, and the launch kit has not been validated against outcomes. The song test covers 229 artists in 24 shows (4 released 2024 or later), where a placement means a song on the title's official soundtrack album, which can include songs a show barely used; its outcome (Wikipedia page spike) is a proxy for attention, and Qloo audiences are today's, which postdate those releases. No Qloo signal predicted which songs spike. Many new 2026 titles have no Qloo audience profile yet. The model would not have picked Running Up That Hill for Stranger Things 4. The live ledger, where each forecast is locked before its outcome exists, is the real test.")));
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
      h("p", null, "Backtest: ROC AUC 0.817 on 829 test breakouts (Mar-Oct 2026). We also tested Qloo as an extra feature on a 200-breakout subset: AUC 0.8188 with history only against 0.8182 with Qloo, so no lift. Qloo had an in-country value for only 1.8% of title-country pairs. So Qloo's role in SPILLOVER is the partners list: artists the title's audience over-indexes on in each forecast country."),
      h("p", null, "Every candidate country's probability is locked in the ledger, not just the top rows, so AUC and calibration can be graded. Grading happens once a title's 4-week horizon has passed in Netflix's weekly data.")),
    h("section", null, h("h2", null, "Launch kit and hotspots: what to do there"),
      h("p", null, "For each storm's top three forecast countries, Qloo is asked which shows, films, brands and artists the title's audience over-indexes on there, and where in the country that audience lives (a heatmap, reduced to its three strongest places and named with OpenStreetMap). Neither changes the probabilities, and neither has been validated against outcomes."),
      h("p", null, "Sync Scout is a discovery tool: it ranks the artists a show's audience likes by the age gap between the artist's audience and the show's. It ranks artists, not scenes.")),
    h("section", null, h("h2", null, "RIPPLE: the song score, tested"),
      h("p", null, "The score is the Qloo age gap, from 0 to 1: how far outside the show's generation an artist's audience sits. We tested whether it, Qloo taste fit or obscurity predicts which soundtrack songs spike on Wikipedia, using 490 songs from the official soundtracks of 34 titles in MusicBrainz (CC0)."),
      h("p", null, "Result: no Qloo signal predicts the spike. Within-show Spearman for the age gap is 0.02 (p 0.40) on 24 shows and 0.18 (p 0.22) on the 4 released from 2024 on; real minus placebo p is 0.14, and taste fit is 0.04. Obscurity is 0.22 against 0.11 on a placebo spike measured before release."),
      h("p", null, "An earlier version used placement lists from Tunefind and showed a significant effect. Tunefind's terms do not permit automated collection, so that data and everything computed from it was discarded, and the effect did not replicate on MusicBrainz. The song score is an explorer, not a predictor."),
      h("p", null, "Known miss: the score would not have picked Kate Bush's Running Up That Hill for Stranger Things 4. Her page views rose from about 10k a month to 909k in June 2022 because of how the scene used the song, which neither Qloo nor Wikipedia sees.")),
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
