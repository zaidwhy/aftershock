// "Ask the agent": one input that sends a plain question to /api/ask and shows the answer plus the steps the agent took.
// The router is fixed rules (aftershock/ask.py), so every sentence here comes from a tool result.
import { h, loading, add } from "./dom.js";
import { askAgent } from "./api.js";
import { pct } from "./format.js";
import { titlePanel } from "./netflix.js";
import { songRow, scoutRow, unresolvedShow, failBox } from "./audience.js";
import { hotspotMap } from "./charts.js";
import { bandText } from "./crowd.js";

const FALLBACK_KIT = "What should Fukrey Returns pair with in Bangladesh?";
/** The example questions. The launch-kit one names this week's hero title and country so it always resolves. */
export function examples(hero) {
  return [
    "Where will Squid Game go next?",
    hero?.title && hero?.country ? `What should ${hero.title} pair with in ${hero.country}?` : FALLBACK_KIT,
    "Find songs for Stranger Things",
    "Running Up That Hill by Kate Bush for Stranger Things",
  ];
}
const KIT_LABELS = { artist: "Artists", tv_show: "TV shows", movie: "Films", brand: "Brands" };
const poss = (n) => (/s$/i.test(n) ? `${n}'` : `${n}'s`);
const list = (items) => (items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`);
const yearGenres = (year, genres) => {
  const g = (genres || []).map((n) => n.toLowerCase());
  const parts = [year, g.length ? g.join(", ") : null].filter(Boolean);
  return parts.length ? ` (${parts.join(", ")})` : "";
};

function forecastList(rows) {
  return h("ul", { class: "timeline ask-next" }, rows.map((f) => h("li", null, h("span", null, f.name), h("span", { class: "mono" }, pct(f.probability)))));
}

function stormCard(a) {
  const f = a.focus;
  return h("div", { class: "ask-card" },
    h("h3", null, `${a.title}${a.season ? ` ${a.season}` : ""}${yearGenres(a.year, a.genres)}`),
    a.note ? h("p", { class: "plain" }, a.note) : null,
    h("p", { class: "plain" }, `It is one of this week's breakouts: it started in ${a.origin}.`),
    f ? h("p", { class: "plain" }, f.probability == null ? `${f.name} is not in its forecast list.`
      : `${f.name} is #${f.rank} in its forecast: a ${pct(f.probability)} chance of charting there within ${a.horizon_weeks} weeks.`) : null,
    h("p", { class: "plain" }, "Likeliest next:"),
    forecastList(a.forecast),
    a.forecast[0]?.why ? h("p", { class: "ask-why" }, `${a.forecast[0].name}: ${a.forecast[0].why}.`) : null,
    a.kit_countries.length ? h("p", { class: "plain" }, `Qloo launch kits are ready for ${list(a.kit_countries)}.`) : null);
}

function kitCard(a) {
  const hot = h("div", { class: "hs" });
  if (a.cells?.length) hotspotMap(a.code, a.cells).then((svg) => { if (svg) hot.prepend(svg); }).catch(() => {});
  const rows = Object.keys(KIT_LABELS).filter((d) => a.picks[d]?.length || a.common[d]?.length);
  return h("div", { class: "ask-card" },
    h("h3", null, `${a.title}${a.season ? ` ${a.season}` : ""}${yearGenres(a.year, [])}: what to pair it with in ${a.country}`),
    h("p", { class: "plain" }, a.probability == null ? `${a.country} is not in its forecast.`
      : `${a.title} started in ${a.origin}. ${a.country} is #${a.rank} in its forecast: a ${pct(a.probability)} chance of charting there within ${a.horizon_weeks} weeks.`),
    a.why ? h("p", { class: "ask-why" }, `${a.why}.`) : null,
    a.specificity == null ? null : h("p", { class: "kit-spec" },
      h("strong", null, a.generic ? "Mostly countrywide taste" : "Title-specific"), `: ${Math.round(a.specificity * 100)}%`,
      a.generic ? ". Qloo had little signal for this title here, so these picks mostly show the country's general taste." : ". These picks are specific to this title's audience, not just the country's usual favourites."),
    h("p", { class: "plain" }, `What this audience in ${a.country} loves, from Qloo:`),
    h("dl", { class: "kit-list" }, rows.map((d) => h("div", { class: d === "brand" ? "kit-minor" : null },
      h("dt", null, KIT_LABELS[d]),
      h("dd", null, a.picks[d].join(", "), a.common[d].length ? h("span", { class: "kit-common" }, `${a.picks[d].length ? "; " : ""}${a.common[d].join(", ")} (popular everywhere there)`) : null)))),
    a.places.length ? h("p", { class: "hs-places" }, "Start in: ", h("strong", null, a.places.join(", "))) : null, hot);
}

function countryCard(a) {
  if (a.chance == null) {
    return h("div", { class: "ask-card" }, h("h3", null, a.name),
      h("p", { class: "plain" }, `No breakout this week lists ${a.name} among its likeliest next countries${a.origin ? ", though some started there" : ""}.`));
  }
  return h("div", { class: "ask-card" }, h("h3", null, `Heading to ${a.name}`),
    h("p", { class: "plain" }, `This week there is a ${pct(a.chance)} chance at least one new breakout arrives in ${a.name}${a.week ? ` (week of ${a.week})` : ""}.`),
    h("p", { class: "plain" }, "Most likely titles:"),
    h("ul", { class: "timeline ask-next" }, a.top.map((t) => h("li", null,
      h("a", { href: `#/storm/${encodeURIComponent(t.id)}` }, t.title), h("span", { class: "mono" }, pct(t.p))))));
}

function rippleCard(a, run) {
  const r = a.ripple, p = a.parsed;
  const again = (songs, show) => run(`${songs.map((s) => `${s.song} by ${s.artist}`).join(", ")} for ${show}`);
  if (r.resolved === false) {
    return h("div", { class: "status status-error", role: "alert" },
      h("p", null, unresolvedShow(r, p.show, (name) => again(p.songs, name))));
  }
  const fix = (x, name) => again(p.songs.map((s) => (s.song === x.song && s.artist === x.artist ? { ...s, artist: name } : s)), p.show);
  return h("div", { class: "ask-card" }, h("h3", null, `How these songs compare with ${r.show}`),
    h("ol", { class: "songs" }, r.songs.map((x) => songRow(x, r.show, r.show_leans, fix))));
}

function scoutCard(a, run) {
  const r = a.scout;
  if (r.resolved === false) {
    return h("div", { class: "status status-error", role: "alert" }, h("p", null, unresolvedShow(r, a.show, (name) => run(`Find songs for ${name}`))));
  }
  if (!r.artists?.length) return h("p", { class: "status" }, `Qloo returned no artists with audience data for ${r.show}.`);
  return h("div", { class: "ask-card" }, h("h3", null, `Artists who could bring ${r.show} a new audience`),
    h("p", { class: "plain" }, `From the ${r.candidates} artists Qloo says ${poss(r.show)} fans like, the ${r.artists.length} whose own fans are the most different age group come first. ${poss(r.show)} viewers lean ${bandText(r.show_leans)}.`),
    h("ol", { class: "songs scout-list" }, r.artists.map((x) => scoutRow(x, r.show_leans, r.candidates, r.show))));
}

function answerCard(res, run) {
  const a = res.answer;
  switch (a.kind) {
    case "storm": return stormCard(a);
    case "kit": return kitCard(a);
    case "country": return countryCard(a);
    case "ripple": return rippleCard(a, run);
    case "scout": return scoutCard(a, run);
    case "title": return h("div", { class: "ask-card" }, a.note ? h("p", { class: "plain" }, a.note) : null,
      a.focus ? h("p", { class: "plain" }, a.focus) : null, titlePanel(a.history));
    default: return h("div", { class: "status", role: "status" }, h("p", null, a.message));
  }
}

function stepsList(steps) {
  return h("section", { class: "ask-steps", "aria-label": "How the agent answered" },
    h("h3", null, "How the agent answered"),
    h("ol", { class: "steps" }, steps.map((s) => h("li", { class: s.ok ? null : "step-no" },
      h("span", { class: "step-n mono", "aria-hidden": "true" }, s.n),
      h("span", null, h("span", { class: "mono ask-tool" }, s.tool.replaceAll("_", " ")), " ", s.note)))));
}

/** The home-page input. `isCurrent` stops the rotating placeholder once the visitor leaves the page. */
export function askBox(isCurrent, stormsP) {
  let EXAMPLES = examples(null);
  const out = h("div", { class: "ask-out", "aria-live": "polite" });
  const input = h("input", { id: "ask-q", type: "text", autocomplete: "off", maxlength: "200", placeholder: EXAMPLES[0], required: true });
  const btn = h("button", { type: "submit", class: "btn btn-primary" }, "Ask");
  const chips = h("div", { class: "examples" }, h("span", { class: "mono eg-label" }, "Try"));
  const drawChips = () => chips.replaceChildren(h("span", { class: "mono eg-label" }, "Try"),
    ...EXAMPLES.map((q) => h("button", { type: "button", class: "chip", onclick: () => run(q) }, q)));
  const run = (text) => {
    const q = (text ?? input.value).trim();
    if (!q) { out.replaceChildren(h("p", { class: "status" }, "Type a question, or tap an example.")); input.focus(); return; }
    input.value = q;
    btn.disabled = true;
    out.replaceChildren(loading("The agent is choosing a tool... questions about songs and artists ask Qloo live and can take 10 to 20 seconds.", true));
    askAgent(q).then((res) => {
      if (!isCurrent()) return;
      out.replaceChildren();
      add(out, answerCard(res, run), stepsList(res.steps),
        res.links?.length ? h("p", { class: "ask-links" }, res.links.map((l) => h("a", { href: l.href }, l.label))) : null);
    }).catch((err) => { if (isCurrent()) out.replaceChildren(failBox(err, "the agent")); })
      .finally(() => { btn.disabled = false; });
  };
  drawChips();
  if (stormsP) stormsP.then((st) => {
    if (!isCurrent()) return;
    EXAMPLES = examples(st?.hero);
    if (!input.value && document.activeElement !== input) input.placeholder = EXAMPLES[0];
    drawChips();
  }).catch(() => {});
  if (!matchMedia("(prefers-reduced-motion: reduce)").matches) {
    let i = 0;
    const timer = setInterval(() => {
      if (!isCurrent()) { clearInterval(timer); return; }
      if (document.activeElement === input || input.value) return;
      i = (i + 1) % EXAMPLES.length;
      input.placeholder = EXAMPLES[i];
    }, 3500);
  }
  return h("section", { class: "ask", "aria-labelledby": "ask-h" },
    h("h2", { id: "ask-h" }, "Ask the agent"),
    h("p", { class: "muted" }, "Ask in plain words. The agent picks the right tool and shows every step. It answers from this week's run and shows every tool it used."),
    h("form", { class: "lookup-form ask-form", novalidate: true, onsubmit: (e) => { e.preventDefault(); run(); } },
      h("label", { for: "ask-q", class: "sr-only" }, "Ask the agent a question"), input, btn),
    chips,
    out);
}
