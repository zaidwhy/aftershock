// Plain-language "Try it" and "Sync Scout" pages. Written for a reader who has never seen Qloo or an age gap.
import { h, loading, errorBox, add } from "./dom.js";
import { scoreSongs, scoutShow, isMock } from "./api.js";
import { BANDS } from "./format.js";

/** Age-gap cut points for the verdict chip. The gap is 0 (same age groups) to 1 (opposite); these are
 *  presentation words only. The gap did not predict which songs spike (README section 3). */
export const VERDICTS = [
  { max: 0.45, label: "Same crowd", cls: "v-same" },
  { max: 0.6, label: "Partly new crowd", cls: "v-part" },
  { max: Infinity, label: "New crowd", cls: "v-new" },
];
export const verdict = (gap) => VERDICTS.find((v) => gap <= v.max);

const SHORT = { "24_and_younger": "under 25", "25_to_29": "25-29", "30_to_34": "30-34", "35_to_44": "35-44", "45_to_54": "45-54", "55_and_older": "55+" };
const bandText = (leans) => {
  const l = (leans || []).map((k) => SHORT[k]).filter(Boolean);
  return l.length < 2 ? l[0] ?? "no clear age group" : `${l.slice(0, -1).join(", ")} and ${l[l.length - 1]}`;
};
const HONEST = "This compares audiences. It does not predict whether a song will take off: we tested that and it did not hold (see Scorecard).";

/** Possessive that does not double the s: Things' not Things's. */
const poss = (n) => (/s$/i.test(n) ? `${n}'` : `${n}'s`);

const setTitle = (t) => { document.title = `${t} - AFTERSHOCK`; };
const mockNote = () => (isMock() ? h("p", { class: "mock-flag" }, "Mock data (?mock=1). Numbers are placeholders.") : null);

/** "song | artist" (first "|"), else "song by artist" split on the last " by ". Mirrors the API. */
function parseSongLine(line) {
  const pipeAt = line.indexOf("|");
  if (pipeAt >= 0) return { song: line.slice(0, pipeAt).trim(), artist: line.slice(pipeAt + 1).trim(), sep: "|" };
  const byAt = line.toLowerCase().lastIndexOf(" by ");
  if (byAt < 0) return { song: line.trim(), artist: "" };
  return { song: line.slice(0, byAt).trim(), artist: line.slice(byAt + 4).trim(), sep: "by" };
}
const joinLine = (p) => (p.sep === "|" ? `${p.song} | ${p.artist}` : `${p.song} by ${p.artist}`);

const steps = (items) => h("ol", { class: "steps" }, items.map((t, i) => h("li", null, h("span", { class: "step-n mono", "aria-hidden": "true" }, i + 1), h("span", null, t))));

const chip = (gap) => { const v = verdict(gap); return h("span", { class: `verdict ${v.cls}` }, v.label); };

/** Two labelled rows of six band cells; a filled cell means that audience leans to that age group. */
function bandStrip(showLeans, artistLeans, who) {
  const rows = [["Show's viewers", showLeans, "on-show"], ["Artist's listeners", artistLeans, "on-artist"]];
  const cells = [h("span", { class: "bs-corner" }), ...BANDS.map(([k]) => h("span", { class: "bs-head mono" }, SHORT[k]))];
  for (const [label, leans, cls] of rows) {
    cells.push(h("span", { class: "bs-label" }, label));
    for (const [k] of BANDS) cells.push(h("span", { class: `bs-cell ${(leans || []).includes(k) ? cls : ""}`, "aria-hidden": "true" }));
  }
  return h("div", { class: "band-strip", role: "img", "aria-label": `Show's viewers lean ${bandText(showLeans)}. ${poss(who)} listeners lean ${bandText(artistLeans)}.` }, cells);
}

const details = (...lines) => h("details", { class: "row-details" }, h("summary", null, "Details"), lines.map((l) => h("p", null, l)));

const REACH = {
  "v-same": "So this song mostly reaches people who already watch shows like this.",
  "v-part": "So this song reaches some people outside the show's usual audience.",
  "v-new": "So this song could reach people outside the show's usual audience.",
};

const suggestBtn = (name, onclick) => h("button", { type: "button", class: "btn btn-small", onclick }, `Use ${name} and try again`);

function songRow(x, showName, showLeans, fix) {
  if (x.resolved === false) {
    return h("li", { class: "song song-bad" },
      h("div", { class: "song-head" }, h("div", null, h("strong", null, x.song), ` by ${x.artist}`)),
      h("p", { class: "not-found" }, `We couldn't find "${x.artist}" in Qloo. `,
        x.suggestion ? [`Did you mean ${x.suggestion}? `, suggestBtn(x.suggestion, () => fix(x, x.suggestion))] : "Check the spelling or try another artist."));
  }
  const matched = x.matched_artist || x.artist;
  const differs = matched.trim().toLowerCase() !== x.artist.trim().toLowerCase();
  const head = h("div", { class: "song-head" },
    h("div", null, h("strong", null, x.song), ` by ${matched}`, differs ? h("span", { class: "mono matched" }, ` matched in Qloo (you typed: ${x.artist})`) : null),
    x.age_gap != null ? chip(x.age_gap) : null);
  if (x.age_gap == null) {
    return h("li", { class: "song song-bad" }, head,
      h("p", { class: "not-found" }, `Qloo knows ${matched} but has no audience data for them yet, so we can't compare.`));
  }
  const v = verdict(x.age_gap);
  return h("li", { class: "song" }, head,
    h("p", { class: "plain" }, `${poss(showName)} viewers lean ${bandText(showLeans)}. ${poss(matched)} listeners lean ${bandText(x.leans)}. `, REACH[v.cls]),
    bandStrip(showLeans, x.leans, matched),
    details(`Age gap ${x.age_gap.toFixed(2)}: how far apart the two audiences' age groups sit, from 0 (same) to 1 (opposite).`,
      x.prior_daily_views != null
        ? `Prior Wikipedia views ${Math.round(x.prior_daily_views).toLocaleString("en-US")}/day: average daily page views of the song or artist before the date scored, a rough sense of how known it already is.`
        : "No Wikipedia page was found for this song or artist, so there is no prior-views figure."));
}

function failBox(err, what) {
  if (err.status !== 429) return errorBox(what, err);
  const msg = /daily/i.test(err.detail || "")
    ? "The shared daily limit for live lookups has been used up. Try again tomorrow or use an example below."
    : "You have used the live lookups for this hour (10 per hour per visitor). Try again later or use an example below.";
  return h("div", { class: "status status-error", role: "alert" }, h("p", null, msg));
}

/** Show did not resolve: a suggestion button when Qloo has a near name, a profile notice otherwise. */
function unresolvedShow(r, typed, retryWith) {
  if (r.no_profile) return `Qloo knows ${r.show} but has no audience data for it yet, so we can't compare. Try another show.`;
  return [`We couldn't find "${typed}" in Qloo. `,
    r.suggestion ? [`Did you mean ${r.suggestion}? `, suggestBtn(r.suggestion, () => retryWith(r.suggestion))] : "Check the spelling or try another show."];
}

const examples = (list) => h("div", { class: "examples" }, h("span", { class: "mono eg-label" }, "Try an example"),
  list.map(([label, fn]) => h("button", { type: "button", class: "btn btn-small", onclick: fn }, label)));

/* ---------------------------------------------------------------- try it */
const TRY_EXAMPLES = [
  ["Stranger Things + 3 songs", "Stranger Things", "Running Up That Hill by Kate Bush\nMaster of Puppets by Metallica\nPsycho Killer by Talking Heads"],
  ["A Bollywood classic + 2 songs", "Dilwale Dulhania Le Jayenge", "Tujhe Dekha To by Kumar Sanu\nMere Khwabon Mein by Lata Mangeshkar"],
];

export function renderTry(root, isCurrent) {
  setTitle("Try it");
  const out = h("div", { class: "try-out", "aria-live": "polite" });
  const show = h("input", { id: "show", name: "show", type: "text", required: true, autocomplete: "off", placeholder: "Stranger Things", maxlength: "120" });
  const songs = h("textarea", { id: "songs", name: "songs", rows: "5", required: true, "aria-describedby": "songs-help", placeholder: "Running Up That Hill by Kate Bush\nMaster of Puppets by Metallica" });
  const asOf = h("input", { id: "asof", name: "asof", type: "date", min: "2015-08-01", "aria-describedby": "asof-help" });
  const btn = h("button", { type: "submit", class: "btn btn-primary" }, "Compare these songs");
  const fail = (msg) => { out.replaceChildren(h("div", { class: "status status-error", role: "alert" }, h("p", null, msg))); };

  const submit = () => {
    const showName = show.value.trim();
    const parsed = songs.value.split("\n").map((l) => l.trim()).filter(Boolean).map(parseSongLine);
    const bad = parsed.findIndex((p) => !p.song || !p.artist);
    if (!showName) { fail("Enter a show or film name."); show.focus(); return; }
    if (!parsed.length) { fail("Enter at least one song, one per line, like: Song by Artist."); songs.focus(); return; }
    if (parsed.length > 8) { fail(`Up to 8 songs are allowed, you entered ${parsed.length}.`); songs.focus(); return; }
    if (bad >= 0) { fail(`Line ${bad + 1} needs both a song and an artist, written "Song by Artist".`); songs.focus(); return; }
    btn.disabled = true;
    out.replaceChildren(loading(`Asking Qloo about ${showName} and each artist... this can take 10 to 20 seconds the first time.`, true));
    scoreSongs(showName, parsed, asOf.value || null).then((r) => {
      if (!isCurrent()) return;
      out.replaceChildren();
      if (r.resolved === false) {
        add(out, h("div", { class: "status status-error", role: "alert" }, h("p", null, unresolvedShow(r, showName, (name) => { show.value = name; submit(); }))));
        return;
      }
      const fix = (x, name) => {
        songs.value = songs.value.split("\n").map((l) => {
          const p = parseSongLine(l.trim());
          return p.song === x.song && p.artist === x.artist ? joinLine({ ...p, artist: name }) : l;
        }).join("\n");
        submit();
      };
      add(out, h("h2", null, `How these songs compare with ${r.show}`),
        h("ol", { class: "songs" }, r.songs.map((x) => songRow(x, r.show, r.show_leans, fix))),
        h("p", { class: "honest" }, HONEST));
    }).catch((err) => { if (isCurrent()) out.replaceChildren(failBox(err, "the comparison")); })
      .finally(() => { btn.disabled = false; });
  };

  const form = h("form", { class: "try-form", novalidate: true, onsubmit: (e) => { e.preventDefault(); submit(); } },
    h("div", { class: "field" }, h("label", { for: "show" }, "Show or film"), show),
    h("div", { class: "field" }, h("label", { for: "songs" }, "Songs, one per line"), songs,
      h("p", { id: "songs-help", class: "help" }, "Write each as \"Song by Artist\". Up to 8 lines. Limited to 10 live lookups per hour per visitor.")),
    h("details", { class: "advanced" }, h("summary", null, "Advanced"),
      h("div", { class: "field" }, h("label", { for: "asof" }, "Score as of (optional)"), asOf,
        h("p", { id: "asof-help", class: "help" }, "The release date, to replay a past show. It changes only the Wikipedia context (prior views are read before this date); the Qloo audiences, and so the score, are today's, so a past replay carries Qloo's later knowledge. Try Stranger Things as of 2022-05-27 with Running Up That Hill by Kate Bush, Master of Puppets by Metallica, Psycho Killer by Talking Heads."))),
    btn);
  const fill = ([, s, l]) => () => { show.value = s; songs.value = l; submit(); };
  add(root, h("h1", null, "Will this song reach a new crowd?"),
    steps(["You type a show and some songs (songs already in it, or ones you are thinking of placing).",
      "We look up who watches the show and who listens to each artist, using Qloo's audience data.",
      "You see whether each song's listeners are the same crowd as the show's, or a different age group the show could reach."]),
    mockNote(), examples(TRY_EXAMPLES.map((e) => [e[0], fill(e)])), form, out);
}

/* ----------------------------------------------------------- sync scout */
const SCOUT_EXAMPLES = ["Stranger Things", "Wednesday", "Squid Game"];

function scoutRow(a, showName, showLeans, of) {
  return h("li", { class: "song" },
    h("div", { class: "song-head" }, h("strong", null, a.name), chip(a.gap)),
    h("p", { class: "plain" }, `Fans of ${showName} like this artist. The artist's own listeners lean ${bandText(a.leans)}; the show's viewers lean ${bandText(showLeans)}.`),
    bandStrip(showLeans, a.leans, a.name),
    h("p", { class: "rank mono" }, `#${a.taste_rank} of ${of} on Qloo's list of what this show's fans like`),
    details(`Age gap ${a.gap.toFixed(2)}: how far apart the two audiences' age groups sit, from 0 (same) to 1 (opposite).`,
      `Rank #${a.taste_rank}: where Qloo places this artist among the ${of} artists it says ${poss(showName)} fans like most (1 is the closest match). It is context only and does not change the order here.`));
}

export function renderScout(root, isCurrent) {
  setTitle("Sync Scout");
  const out = h("div", { class: "try-out", "aria-live": "polite" });
  const show = h("input", { id: "scout-show", name: "show", type: "text", required: true, autocomplete: "off", placeholder: "Wednesday", maxlength: "120" });
  const btn = h("button", { type: "submit", class: "btn btn-primary" }, "Find artists");
  const submit = () => {
    const name = show.value.trim();
    if (!name) { out.replaceChildren(h("div", { class: "status status-error", role: "alert" }, h("p", null, "Enter a show or film name."))); show.focus(); return; }
    btn.disabled = true;
    out.replaceChildren(loading(`Asking Qloo about ${name}... this takes about 15 seconds the first time.`, true));
    scoutShow(name).then((r) => {
      if (!isCurrent()) return;
      out.replaceChildren();
      if (r.resolved === false) {
        add(out, h("div", { class: "status status-error", role: "alert" }, h("p", null, unresolvedShow(r, name, (n) => { show.value = n; submit(); }))));
        return;
      }
      if (!r.artists?.length) { add(out, h("p", { class: "status" }, `Qloo returned no artists with audience data for ${r.show}.`)); return; }
      add(out, h("h2", null, `Artists who could bring ${r.show} a new audience`),
        h("p", { class: "muted" }, `The ${r.artists.length} best candidates, from the ${r.candidates} artists Qloo says ${poss(r.show)} fans like. Artists whose own fans are a different age group come first.${r.truncated ? " The lookup limit ran out, so the list is partial." : ""}`),
        h("ol", { class: "songs scout-list" }, r.artists.map((a) => scoutRow(a, r.show, r.show_leans, r.candidates))),
        h("p", { class: "honest" }, HONEST));
    }).catch((err) => { if (isCurrent()) out.replaceChildren(failBox(err, "the artist list")); })
      .finally(() => { btn.disabled = false; });
  };
  const form = h("form", { class: "try-form", novalidate: true, onsubmit: (e) => { e.preventDefault(); submit(); } },
    h("div", { class: "field" }, h("label", { for: "scout-show" }, "Show or film"), show,
      h("p", { class: "help" }, "Each lookup counts toward 10 live lookups per hour per visitor, shared with Try it.")),
    btn);
  add(root, h("h1", null, "Find artists who could bring a show a new audience"),
    steps(["You type a show.", "Qloo lists the artists that show's fans love.",
      "We sort them so artists whose own fans are a different age group come first: candidates that could bring the show new listeners."]),
    mockNote(), examples(SCOUT_EXAMPLES.map((n) => [n, () => { show.value = n; submit(); }])), form, out);
}
