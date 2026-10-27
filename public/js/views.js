import { h } from "./dom.js";
import { loading, errorBox, add } from "./dom.js";
import { getStorms, getStorm, getScorecard, getReplays, getRipples, getRipple, scoreSongs, scoutShow, isMock } from "./api.js";
import { pct, plain2, dateLabel, monthLabel, views } from "./format.js";
import { seismograph, ripplePanel, generationGap, forecastMap } from "./charts.js";
import { ISO } from "./iso.js";

// AUCs that differ in the third decimal must not round to the same label.
const auc4 = (n) => (n == null ? "n/a" : n.toFixed(4));

const countryName = (code) => ISO[code]?.[1] ?? code;

const setTitle = (t) => { document.title = t ? `${t} - AFTERSHOCK` : "AFTERSHOCK - forecast where a breakout show spreads"; };
const mockNote = () => (isMock() ? h("p", { class: "mock-flag" }, "Mock data (?mock=1). Numbers are placeholders, except the replay pageviews.") : null);
/** "song | artist" (first "|"), else "song by artist" split on the last " by ". Mirrors the API. */
function parseSongLine(line) {
  const pipeAt = line.indexOf("|");
  if (pipeAt >= 0) return { song: line.slice(0, pipeAt).trim(), artist: line.slice(pipeAt + 1).trim() };
  const byAt = line.toLowerCase().lastIndexOf(" by ");
  if (byAt < 0) return { song: line.trim(), artist: "" };
  return { song: line.slice(0, byAt).trim(), artist: line.slice(byAt + 4).trim() };
}
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
  const watchBox = h("div", null);
  add(root, 
    h("section", { class: "hero" },
      h("p", { class: "eyebrow" }, "Breakout forecasting"),
      h("h1", null, "A show breaks out in one country. ", h("em", null, "Where does it land next?")),
      h("p", { class: "pitch" }, "SPILLOVER: for a title that broke out in 1 to 3 countries, the probability each other country charts it within 4 weeks, from Netflix history. RIPPLE: for songs placed in a show, a ranking by the age gap between the artist's audience and the show's, from Qloo. Every forecast is locked in a public ledger before the outcome is known."),
      chartBox),
    mockNote(),
    h("section", { "aria-labelledby": "watch-h" },
      h("h2", { id: "watch-h" }, "Songs to watch"),
      watchBox),
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

  load(watchBox, "new releases", isCurrent, getRipples, ({ ripples }) => {
    if (!ripples?.length) { add(watchBox, h("p", { class: "status" }, "No new releases with known song placements yet.")); return; }
    add(watchBox,
      h("p", { class: "muted" }, "New releases with known song placements. Songs are locked only if that happens before the outcome window opens; older releases are an early read only."),
      h("ul", { class: "storm-list" }, ripples.map((r) => h("li", null,
        h("a", { href: `#/ripple/${encodeURIComponent(r.id)}`, class: "storm-link" },
          h("span", { class: "storm-title" }, r.show),
          h("span", { class: "storm-meta" }, `${r.platform} | released ${r.release_date} | ${r.songs} ${r.songs === 1 ? "song" : "songs"}`, r.lockable === false ? h("span", { class: "tag tag-pending" }, "early read only") : null),
          h("span", { class: "storm-next" }, r.top_song ? h("span", null, "Top: ", h("strong", null, r.top_song.song), ` by ${r.top_song.artist} `, h("span", { class: "mono" }, plain2(r.top_song.score))) : "No ranked song"))))));
  });

  load(stormBox, "this week's storms", isCurrent, getStorms, ({ week, storms }) => {
    if (!storms.length) { add(stormBox, h("p", { class: "status" }, `No title entered the Top 10 in only 1 to 3 countries in the week of ${week}.`)); return; }
    add(stormBox, 
      h("p", { class: "muted" }, `Week of ${week}. Titles that entered Netflix's Top 10 in 1 to 3 countries.`),
      h("ul", { class: "storm-list" }, storms.map((s) => h("li", null,
        h("a", { href: `#/storm/${encodeURIComponent(s.id)}`, class: "storm-link" },
          h("span", { class: "storm-title" }, s.title, s.season ? h("span", { class: "muted" }, ` ${s.season}`) : null),
          h("span", { class: "storm-meta" }, `Origin: ${origins(s.origin_countries)}`),
          h("span", { class: "storm-next" }, s.top_forecast ? h("span", null, "Next: ", h("strong", null, s.top_forecast.name), " ", h("span", { class: "mono" }, pct(s.top_forecast.probability))) : "No forecast yet"))))));
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
      kitSection(st),
      h("p", { class: "locked mono" }, st.spillover?.locked_at ? `Locked at ${dateLabel(st.spillover.locked_at)} | ledger id ${st.spillover.ledger_id}` : "Not locked yet."));
    forecastMap(fc, st.origin_countries).then((svg) => {
      if (isCurrent()) mapBox.replaceChildren(svg);
    }).catch((err) => {
      if (isCurrent()) mapBox.replaceChildren(errorBox("the map", err), h("p", { class: "muted" }, "The table below has the same data."));
    });
  });
}

const KIT_LABELS = { artist: "Artists", tv_show: "TV shows", movie: "Films", brand: "Brands" };

function kitSection(st) {
  const rows = (st.launch_kit || []).filter((r) => r.kit && Object.values(r.kit).some((v) => v?.length));
  if (!rows.length) {
    // Older data has only the artist partners list.
    return st.partners?.some((p) => p.artists?.length) ? h("section", { "aria-labelledby": "par-h" },
      h("h2", { id: "par-h" }, "Who this audience already loves there"),
      h("ul", { class: "partners" }, st.partners.filter((p) => p.artists?.length).map((p) => h("li", null,
        h("strong", null, countryName(p.code)), " ", h("span", null, p.artists.join(", ")))))) : null;
  }
  return h("section", { "aria-labelledby": "par-h" },
    h("h2", { id: "par-h" }, "Launch kit: what this audience loves there"),
    h("p", { class: "muted" }, "From Qloo: what the title's audience over-indexes on in each forecast country, as a starting point for a local launch. Netflix history says where; this says what to do there. It does not change the probabilities."),
    rows.map((r) => h("div", { class: "kit" },
      h("h3", null, countryName(r.code)),
      h("dl", { class: "kit-list" }, Object.keys(KIT_LABELS).filter((d) => r.kit[d]?.length).map((d) => h("div", null,
        h("dt", null, KIT_LABELS[d]), h("dd", null, r.kit[d].map((e) => e.name).join(", "))))))));
}

/* ----------------------------------------------------------------- ripple */
const earlyRead = (x) => (x.early_ratio == null ? "n/a" : `${x.early_ratio.toFixed(1)}x${x.early_status === "pending" ? " pending" : ""}`);

export function renderRipple(root, id, isCurrent) {
  setTitle("Release");
  load(root, "this release", isCurrent, () => getRipple(id), (r) => {
    setTitle(r.show);
    const songs = [...(r.songs || [])].filter((x) => x.score != null).sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
    add(root,
      h("p", { class: "crumb" }, h("a", { href: "#/" }, "Songs to watch")),
      h("h1", null, r.show),
      h("p", { class: "meta" }, `${r.platform} | released ${r.release_date} | scored as of release day`),
      mockNote(),
      h("p", null, "The score is the Qloo age gap, from 0 to 1: how far the artist's audience sits from the show's audience by age band. Prior Wikipedia views are shown as context only: songs with few views tend to spike more, but they also tend to rise on their own, so this is mostly regression to the mean and is not scored. The early read is the mean daily Wikipedia views on days +7 to +35 after release over days -60 to -8; it is still accumulating while pending."),
      songs.length ? h("section", { "aria-labelledby": "rs-h" },
        h("h2", { id: "rs-h" }, "Ranked songs"),
        h("p", { class: "legend" }, h("span", { class: "key key-show" }), "Show audience", h("span", { class: "key key-artist" }), "Artist audience", h("span", { class: "muted" }, " (over-index by age band)")),
        songTable(r, songs)) : h("p", { class: "status" }, "No songs were scored for this release."),
      h("p", { class: "locked mono" }, r.locked_at ? `Locked at ${dateLabel(r.locked_at)} | ledger id ${r.ledger_id}` : (r.not_locked_reason ? `Not locked: ${r.not_locked_reason}` : "Not locked yet.")));
  });
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
        h("td", null, x.artist_age ? generationGap(r.show_age, x.artist_age, `Generation gap for ${x.song} by ${x.artist}: show audience versus artist audience by age band, over-index from -1 to +1.`) : h("span", { class: "muted" }, "artist not in Qloo")))))));
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
  const songs = h("textarea", { id: "songs", name: "songs", rows: "6", required: true, "aria-describedby": "songs-help", placeholder: "Running Up That Hill by Kate Bush\nMaster of Puppets by Metallica" });
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
      h("p", { id: "asof-help", class: "help" }, "The release date, to replay a past show. It changes only the Wikipedia context (prior views are read before this date); the Qloo audiences, and so the score, are today's, so a past replay carries Qloo's later knowledge. Try Wednesday as of 2022-11-23 with Space Song by Beach House, Physical by Dua Lipa, Dream Weaver by Gary Wright, Dancing In the Dark by Bruce Springsteen.")),
    btn);
  add(root, h("h1", null, "Try it on any show"),
    h("p", { class: "pitch" }, "Name a show and the songs placed in it. AFTERSHOCK resolves each artist in Qloo and scores it by the age gap: how far the artist's audience sits from the show's, from 0 to 1. Prior Wikipedia views and Qloo taste fit are shown as context and are not scored."),
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
    h("p", { class: "caveat-line" }, "Ranks artists, not scenes. The age gap tracked real song spikes but not a placebo in our backtest (README section 3); it is modest, in-sample evidence, not a hit predictor."),
    mockNote(), form, out);
}

/* -------------------------------------------------------------- scorecard */
export function renderScorecard(root, isCurrent) {
  setTitle("Scorecard");
  const box = h("div", null);
  add(root, h("h1", null, "Scorecard"), h("p", { class: "pitch" }, "Forecasts are locked first and graded later. Nothing here is edited after the fact."), mockNote(), box);
  load(box, "the scorecard", isCurrent, getScorecard, (sc) => {
    const sp = sc.spillover || {}, rp = sc.ripple || {}, bt = sc.backtest || {};
    const bs = bt.spillover || {}, br = bt.ripple || {};
    const pl = br.placebo || {};
    const row = (label, value) => h("tr", null, h("th", { scope: "row" }, label), h("td", { class: "mono" }, value));
    const gapCell = br.gap_2024_plus == null ? "n/a" : `${plain2(br.gap_2024_plus)}${br.gap_2024_plus_p == null ? "" : ` (permutation p = ${br.gap_2024_plus_p.toFixed(2)})`}`;
    const placeboRow = (label, key, a, b) => h("tr", null, h("th", { scope: "row" }, label),
      [pl["2024_plus"]?.[a], pl["2024_plus"]?.[b], pl.all?.[a], pl.all?.[b]].map((v) => h("td", { class: "num mono" }, plain2(v))));
    add(box,
      h("div", { class: "grid2" },
        scoreBlock("Spillover", "graded weekly by Netflix Top 10, once a title's 4-week horizon has passed", sp.locked, sp.graded,
          [["Hits", sp.hits], ["Pending", sp.pending], ["AUC", plain2(sp.auc)],
           ["So far: hits, horizon still open", sp.so_far ? `${sp.so_far.hits} of ${sp.so_far.forecasts}` : "n/a"],
           ["So far: partial AUC (misses can still turn into hits)", plain2(sp.so_far?.auc)]]),
        scoreBlock("Ripple", "graded by Wikipedia pageviews, per release", rp.locked, undefined,
          [["Graded releases", rp.graded_releases], ["Pending releases", rp.pending_releases], ["Mean Spearman", plain2(rp.mean_spearman)]])),
      h("h2", null, "Backtests on past events"),
      h("table", { class: "plain" }, h("caption", { class: "sr-only" }, "Backtest results"),
        h("thead", null, h("tr", null, ["Measure", "Value"].map((t) => h("th", { scope: "col" }, t)))),
        h("tbody", null,
          row(`Spillover: history-only AUC (${bs.test_breakouts ?? "n/a"} breakouts)`, auc4(bs.history_auc)),
          row(`Spillover: same ${bs.subset_breakouts ?? "n/a"} breakouts, history-only`, auc4(bs.history_auc_same_subset)),
          row(`Spillover: same ${bs.subset_breakouts ?? "n/a"}, history + Qloo`, auc4(bs.qloo_auc)),
          row("Ripple: Qloo age gap, 2024+ releases (Spearman)", gapCell),
          row("Ripple: Qloo taste fit, 2024+", plain2(br.fit_2024_plus)),
          row("Ripple: obscurity, 2024+ (mostly regression to the mean, see placebo)", plain2(br.obscurity_2024_plus)))),
      h("p", { class: "muted" }, `Ripple backtest: ${br.n_artists ?? "n/a"} artists placed in ${br.n_shows ?? "n/a"} shows (${br.n_shows_2024_plus ?? "n/a"} released 2024 or later). Outcome is the artist's Wikipedia page spike, days +7 to +35 over days -60 to -8.`),
      h("h2", null, "Placebo check"),
      h("p", { class: "muted" }, "Mean within-show Spearman against the real spike and against a placebo spike measured entirely before release. A score that predicts the placebo is picking up regression to the mean, not the show."),
      h("table", { class: "plain" }, h("caption", { class: "sr-only" }, "Real versus placebo Spearman"),
        h("thead", null, h("tr", null, ["Score", `Real, 2024+ (${pl["2024_plus"]?.n_shows ?? "n/a"} shows)`, "Placebo, 2024+", `Real, all (${pl.all?.n_shows ?? "n/a"} shows)`, "Placebo, all"].map((t, i) => h("th", { scope: "col", class: i ? "num" : null }, t)))),
        h("tbody", null,
          placeboRow("Obscurity", "obscurity", "real: obscurity", "placebo: obscurity (its own pre-window)"),
          placeboRow("Age gap", "gap", "real: gap", "placebo: gap"))),
      h("p", { class: "muted" }, `Real minus placebo for the age gap: permutation p = ${plain2(pl["2024_plus"]?.["p: gap real minus gap placebo"])} on 2024+ releases, ${plain2(pl.all?.["p: gap real minus gap placebo"])} on all.`),
      h("p", null, sc.ledger_url ? h("a", { class: "btn", href: sc.ledger_url, rel: "noopener" }, "Open the public ledger") : null,
        sc.ledger_intact == null ? null : h("span", { class: "muted" }, sc.ledger_intact ? " Ledger hash chain verified." : " Ledger hash chain FAILED verification."),
        sc.data_week ? h("span", { class: "muted" }, ` Netflix data through the week of ${sc.data_week}.`) : null),
      h("section", { class: "caveat", "aria-labelledby": "dne-h" },
        h("h2", { id: "dne-h" }, "What this does not establish"),
        h("p", null, "Qloo describes the taste of groups, not of any individual: an audience profile says what a group tends to like, not what a given person will do. Forecasts are probabilities, so a 20% forecast that does not happen was not wrong, and one that does was not proven right. The spillover backtest shows Netflix history predicts spread well; it does not show that Qloo adds to it (no lift on the 200-breakout subset). The ripple backtest is 9 shows from 2024 on and 195 artists, with an outcome (Wikipedia page spike) that is a proxy for attention, and Qloo audiences are today's, which postdate those releases. Many new 2026 titles have no Qloo audience profile yet. The model would not have picked Running Up That Hill for Stranger Things 4. The live ledger, where each forecast is locked before its outcome exists, is the real test.")));
  });
}

function scoreBlock(name, graded_by, locked, graded, extra) {
  return h("section", { class: "score-block", "aria-label": name },
    h("h2", null, name), h("p", { class: "muted" }, graded_by),
    h("dl", null,
      h("div", null, h("dt", null, "Locked"), h("dd", { class: "mono" }, locked ?? "n/a")),
      graded === undefined ? null : h("div", null, h("dt", null, "Graded"), h("dd", { class: "mono" }, graded ?? "n/a")),
      extra.map(([k, v]) => h("div", null, h("dt", null, k), h("dd", { class: "mono" }, v ?? "n/a")))));
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
    h("section", null, h("h2", null, "RIPPLE: which songs"),
      h("p", null, "The score is the Qloo age gap, from 0 to 1: how far the artist's audience sits from the show's audience by age band, using Qloo demographics for both (the artist's over-index weighted by the age bands the show over-indexes on)."),
      h("p", null, "Evidence: 195 artists placed in 24 shows, with the outcome being the artist's Wikipedia page spike (days +7 to +35 over days -60 to -8). On releases from 2024 on (9 shows) the age gap's mean within-show Spearman is 0.28 (permutation p 0.02). It does not predict a placebo spike measured entirely before release (-0.11), and real minus placebo is significant (p 0.03; 0.04 on all 24 shows)."),
      h("p", null, "Qloo taste fit predicted nothing (about 0.00) and is shown as context only. Obscurity (low Wikipedia views before release) correlates with the spike (0.29) but predicts the placebo spike almost as well (0.28): it is mostly regression to the mean, so it is shown as context with that warning, not scored."),
      h("p", null, "Live: a release's songs are locked only if the lock happens before its outcome window opens (release + 7 days) and at least 4 songs are scorable. Older releases are shown as an early read only, with a reason. Many new 2026 titles have no Qloo audience profile yet, which is a coverage limit."),
      h("p", null, "Known miss: the model would not have picked Kate Bush's Running Up That Hill for Stranger Things 4. The show's audience skews young and her Qloo audience does not, yet taste fit was very high, and her page views rose from about 10k a month to 909k in June 2022 because of how the scene used the song, which neither Qloo nor Wikipedia sees.")),
    h("section", null, h("h2", null, "Data sources"),
      h("ul", { class: "plain-list" },
        h("li", null, h("strong", null, "Netflix Top 10"), ": the public weekly TSV, by country. Defines storms, supplies the SPILLOVER history and grades it."),
        h("li", null, h("strong", null, "Wikimedia pageviews API"), ": daily views per article. The RIPPLE outcome and its prior-views context."),
        h("li", null, h("strong", null, "Qloo Insights"), ": entity search and demographics (age bands) for the RIPPLE age gap, and the partners list of artists a title's audience over-indexes on in each country."))),
    h("p", null, "The Qloo key stays on the server; this page only talks to AFTERSHOCK's own API."));
}

export function renderNotFound(root) {
  setTitle("Not found");
  add(root, h("h1", null, "Page not found"), h("p", null, h("a", { href: "#/" }, "Back to this week's storms")));
}
