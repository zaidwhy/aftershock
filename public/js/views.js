import { h } from "./dom.js";
import { loading, errorBox, add } from "./dom.js";
import { getStorms, getStorm, getScorecard, getReplays, getRipple, isMock } from "./api.js";
import { pct, plain2, dateLabel, monthLabel, views } from "./format.js";
import { seismograph, ripplePanel, forecastMap } from "./charts.js";
import { ISO } from "./iso.js";

const countryName = (code) => ISO[code]?.[1] ?? code;

const setTitle = (t) => { document.title = t ? `${t} - AFTERSHOCK` : "AFTERSHOCK - forecast where a breakout show spreads"; };
const mockNote = () => (isMock() ? h("p", { class: "mock-flag" }, "Mock data (?mock=1). Numbers are placeholders, except the replay pageviews.") : null);
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
  add(root, 
    h("section", { class: "hero" },
      h("p", { class: "eyebrow" }, "Breakout forecasting"),
      h("h1", null, "A show breaks out in one country. ", h("em", null, "Where does it land next?")),
      h("p", { class: "pitch" }, "AFTERSHOCK uses Qloo's taste graph to forecast which countries a breakout show charts in next, and which songs placed in it will spike. Every forecast is locked in a public ledger before the outcome is known."),
      chartBox),
    mockNote(),
    h("section", { "aria-labelledby": "live-h" },
      h("h2", { id: "live-h" }, "Live storms this week"),
      stormBox));

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

  load(stormBox, "this week's storms", isCurrent, getStorms, ({ week, storms }) => {
    if (!storms.length) { add(stormBox, h("p", { class: "status" }, `No title entered the Top 10 in only 1 to 3 countries in the week of ${week}.`)); return; }
    add(stormBox, 
      h("p", { class: "muted" }, `Week of ${week}. Titles that entered Netflix's Top 10 in 1 to 3 countries.`),
      h("ul", { class: "storm-list" }, storms.map((s) => h("li", null,
        h("a", { href: `#/storm/${encodeURIComponent(s.id)}`, class: "storm-link" },
          h("span", { class: "storm-title" }, s.title, s.season ? h("span", { class: "muted" }, ` ${s.season}`) : null),
          h("span", { class: "storm-meta" }, `Origin: ${origins(s.origin_countries)}`),
          h("span", { class: "storm-next" }, s.top_forecast ? h("span", null, "Next: ", h("strong", null, s.top_forecast.name), " ", h("span", { class: "mono" }, pct(s.top_forecast.probability))) : "No forecast yet",
            s.has_ripple ? h("span", { class: "tag tag-pending" }, "songs") : null))))));
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
      mockNote(),
      h("section", { "aria-labelledby": "map-h" },
        h("h2", { id: "map-h" }, `Where it charts next (${st.spillover?.horizon_weeks ?? "?"} week horizon)`),
        mapBox,
        h("p", { class: "legend" }, h("span", { class: "key key-origin" }), "Origin countries (outlined)", h("span", { class: "key key-ramp" }), "Darker = higher probability"),
        fc.length ? forecastTable(fc) : h("p", { class: "status" }, "No forecast rows for this title.")),
      st.partners?.some((p) => p.artists?.length) ? h("section", { "aria-labelledby": "par-h" },
        h("h2", { id: "par-h" }, "Who this audience already loves there"),
        h("p", { class: "muted" }, "From Qloo: artists the title's audience over-indexes on in each forecast country, as partners for a local launch."),
        h("ul", { class: "partners" }, st.partners.filter((p) => p.artists?.length).map((p) => h("li", null,
          h("strong", null, countryName(p.code)), " ", h("span", null, p.artists.join(", ")))))) : null,
      st.ripple ? h("section", { "aria-labelledby": "rip-h" }, h("h2", { id: "rip-h" }, "Song ripple"),
        h("p", { class: "muted" }, "Songs placed in the show whose Wikipedia pageviews may spike. Score = within-show rank of how unknown the song was before release, averaged with the rank of the age gap between the show's audience and the artist's (Qloo)."), ripplePanel(st.ripple)) : null,
      h("p", { class: "locked mono" }, st.spillover?.locked_at ? `Locked at ${dateLabel(st.spillover.locked_at)} | ledger id ${st.spillover.ledger_id}` : "Not locked yet."));
    forecastMap(fc, st.origin_countries).then((svg) => {
      if (isCurrent()) mapBox.replaceChildren(svg);
    }).catch((err) => {
      if (isCurrent()) mapBox.replaceChildren(errorBox("the map", err), h("p", { class: "muted" }, "The table below has the same data."));
    });
  });
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
  const songs = h("textarea", { id: "songs", name: "songs", rows: "6", required: true, "aria-describedby": "songs-help", placeholder: "Running Up That Hill | Kate Bush\nMaster of Puppets | Metallica" });
  const btn = h("button", { type: "submit", class: "btn btn-primary" }, "Score these songs");
  const form = h("form", { class: "try-form", novalidate: true,
    onsubmit: (e) => {
      e.preventDefault();
      const showName = show.value.trim();
      const lines = songs.value.split("\n").map((l) => l.trim()).filter(Boolean);
      const parsed = lines.map((l) => { const [song, ...rest] = l.split("|"); return { song: song.trim(), artist: rest.join("|").trim() }; });
      const bad = parsed.findIndex((p) => !p.song || !p.artist);
      if (!showName) { out.replaceChildren(errorBox("your input", new Error("Enter a show name."))); show.focus(); return; }
      if (!parsed.length) { out.replaceChildren(errorBox("your input", new Error("Enter at least one line as: song | artist."))); songs.focus(); return; }
      if (parsed.length > 8) { out.replaceChildren(errorBox("your input", new Error(`Up to 8 songs are allowed, you entered ${parsed.length}.`))); songs.focus(); return; }
      if (bad >= 0) { out.replaceChildren(errorBox("your input", new Error(`Line ${bad + 1} needs both a song and an artist, written "song | artist".`))); songs.focus(); return; }
      btn.disabled = true;
      out.replaceChildren(loading("scores from Qloo"));
      getRipple(showName, parsed).then((r) => {
        if (!isCurrent()) return;
        out.replaceChildren();
        if (r.resolved === false || r.show_resolved === false) add(out, h("div", { class: "status status-error", role: "alert" }, h("p", null, `"${showName}" was not found in Qloo, so no audience profile exists to score against.`)));
        else add(out, h("h2", null, `Ripple scores for ${showName}`), ripplePanel(r));
      }).catch((err) => { if (isCurrent()) out.replaceChildren(errorBox("the scores", err)); })
        .finally(() => { btn.disabled = false; });
    } },
    h("div", { class: "field" }, h("label", { for: "show" }, "Show or film"), show),
    h("div", { class: "field" }, h("label", { for: "songs" }, "Songs, one per line"), songs,
      h("p", { id: "songs-help", class: "help" }, "Format: song | artist. Up to 8 lines. Limited to 10 live scorings per hour.")),
    btn);
  add(root, h("h1", null, "Try it on any show"),
    h("p", { class: "pitch" }, "Name a show and the songs placed in it. AFTERSHOCK resolves each one in Qloo and Wikipedia and ranks them by how unknown each song is and how far its audience sits from the show's."),
    mockNote(), form, out);
}

/* -------------------------------------------------------------- scorecard */
export function renderScorecard(root, isCurrent) {
  setTitle("Scorecard");
  const box = h("div", null);
  add(root, h("h1", null, "Scorecard"), h("p", { class: "pitch" }, "Forecasts are locked first and graded later. Nothing here is edited after the fact."), mockNote(), box);
  load(box, "the scorecard", isCurrent, getScorecard, (sc) => {
    const sp = sc.spillover || {}, rp = sc.ripple || {}, bt = sc.backtest || {};
    add(box, 
      h("div", { class: "grid2" },
        scoreBlock("Spillover", "graded weekly by Netflix Top 10", sp.locked, sp.graded,
          [["Hits (locked top 10 per title)", sp.hits], ["Pending", sp.pending], ["AUC", plain2(sp.auc)]]),
        scoreBlock("Ripple", "graded daily by Wikipedia pageviews", rp.locked, rp.graded,
          [["Spearman", plain2(rp.spearman)], ["Baseline Spearman", plain2(rp.baseline_spearman)]])),
      h("h2", null, "Backtests on past events"),
      h("table", { class: "plain" }, h("caption", { class: "sr-only" }, "Backtest results"),
        h("thead", null, h("tr", null, ["Model", "Measure", "Value"].map((t) => h("th", { scope: "col" }, t)))),
        h("tbody", null,
          h("tr", null, h("th", { scope: "row" }, "Spillover"), h("td", null, "History-only AUC"), h("td", { class: "mono" }, plain2(bt.spillover?.history_auc))),
          h("tr", null, h("th", { scope: "row" }, "Spillover"), h("td", null, "With Qloo AUC"), h("td", { class: "mono" }, plain2(bt.spillover?.qloo_auc))),
          h("tr", null, h("th", { scope: "row" }, "Ripple"), h("td", null, `Spearman (n = ${bt.ripple?.n ?? 0})`), h("td", { class: "mono" }, plain2(bt.ripple?.spearman))))),
      h("p", null, h("a", { class: "btn", href: sc.ledger_url, rel: "noopener" }, "Open the public ledger")),
      h("section", { class: "caveat", "aria-labelledby": "dne-h" },
        h("h2", { id: "dne-h" }, "What this does not establish"),
        h("p", null, "Qloo describes the taste of groups, not of any individual: a high score says an audience tends to like something, not that a given person will. Forecasts are probabilities, so a 20% forecast that does not happen was not wrong, and one that does was not proven right. Backtests on past events are biased in both directions, because today's Qloo data postdates those events: a song that already spiked now has a younger audience, so its age gap looks smaller than it was before release. The live ledger, where each forecast is locked before its outcome exists, is the real test.")));
  });
}

function scoreBlock(name, graded_by, locked, graded, extra) {
  return h("section", { class: "score-block", "aria-label": name },
    h("h2", null, name), h("p", { class: "muted" }, graded_by),
    h("dl", null,
      h("div", null, h("dt", null, "Locked"), h("dd", { class: "mono" }, locked ?? "n/a")),
      h("div", null, h("dt", null, "Graded"), h("dd", { class: "mono" }, graded ?? "n/a")),
      extra.map(([k, v]) => h("div", null, h("dt", null, k), h("dd", { class: "mono" }, v ?? "n/a")))));
}

/* ----------------------------------------------------------------- method */
export function renderMethod(root) {
  setTitle("Method");
  add(root, 
    h("h1", null, "Method"),
    h("p", { class: "pitch" }, "Two models, one rule: lock the forecast before the outcome."),
    h("section", null, h("h2", null, "SPILLOVER: which countries next"),
      h("p", null, "Start with a title that entered Netflix's Top 10 in 1 to 3 countries. From past breakouts that began in the same countries, count how often each other country followed; that is the history probability. Then adjust it with Qloo: how strongly the title's audience taste matches each country, relative to the title's average country. The output is a probability per country over a four-week horizon, graded against the next weekly Top 10."),
      h("p", null, "The history column in the forecast table is the baseline. The Qloo column is how far the taste signal moved the forecast away from it.")),
    h("section", null, h("h2", null, "RIPPLE: which songs spike"),
      h("p", null, "For each song placed in a show, compare two audiences from Qloo, the show's and the artist's, by age band: the age gap is how far the artist's audience sits from the bands the show's audience over-indexes on. Add obscurity: the song's mean daily Wikipedia views in the 60 days before release (its artist's page when the song has none). Score = the average of the two within-show percentiles. We also tested Qloo taste fit (how much the show's audience likes the artist); it did not predict spikes, so it is shown as context only."),
      h("p", null, "Stranger Things 4 is the case: its audience over-indexes on 24-and-younger (+0.71) while Kate Bush's is flat there (+0.03) and peaks at 45-54 (+0.34), yet fit is very high (0.925). Her English Wikipedia views went from about 10k a month to 909k in June 2022. Graded daily against Wikimedia pageviews.")),
    h("section", null, h("h2", null, "Data sources"),
      h("ul", { class: "plain-list" },
        h("li", null, h("strong", null, "Netflix Top 10"), ": the public weekly TSV, by country. Defines storms and grades SPILLOVER."),
        h("li", null, h("strong", null, "Wikimedia pageviews API"), ": daily views per article. Grades RIPPLE."),
        h("li", null, h("strong", null, "Qloo Insights"), ": entity search, demographics (age bands), cross-domain affinity (show to artist), and location-conditioned affinity (taste by country)."))),
    h("p", null, "The Qloo key stays on the server; this page only talks to AFTERSHOCK's own API."));
}

export function renderNotFound(root) {
  setTitle("Not found");
  add(root, h("h1", null, "Page not found"), h("p", null, h("a", { href: "#/" }, "Back to this week's storms")));
}
