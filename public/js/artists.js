// "For music artists": this week's trending shows read from the artist's side. Data from aftershock/artist_view.py, exported to
// public/data/artists.json and public/data/artists/<slug>.json. Audience overlap from Qloo, not a forecast of streams.
import { h, loading, errorBox, add } from "./dom.js";
import { getArtists, getArtist } from "./api.js";

const planHref = (id, code) => `#/plan/${encodeURIComponent(id)}/${encodeURIComponent(code)}`;
const artistHref = (slug) => `#/artist/${encodeURIComponent(slug)}`;
const join = (items) => (items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items.at(-1)}`);
// Same comparison as aftershock/launch_kit.name_key: accents and punctuation stripped, lower case.
const key = (n) => n.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim() || n.toLowerCase().trim();

let slugs = null;
const slugMap = () => (slugs ??= getArtists().then((d) => new Map(d.artists.map((a) => [key(a.name), a.slug]))).catch(() => { slugs = null; return new Map(); }));

/** An artist's name as plain text that becomes a link to their page once the week's artist list has loaded,
 *  when the artist has a page. */
export function artistName(name) {
  const span = h("span", null, name);
  slugMap().then((m) => {
    const slug = m.get(key(name));
    if (slug && span.isConnected !== false) span.replaceChildren(h("a", { href: artistHref(slug) }, name));
  });
  return span;
}

/** Names in a comma list, each linked when the artist has a page. */
export const artistNames = (names) => names.flatMap((n, i) => [i ? ", " : null, artistName(n)]);

const HOW = [
  ["A show travels", "A Netflix show gets popular in one country and heads to the next."],
  ["Its viewers love your music", "Qloo's taste data shows which artists those viewers like far more than average."],
  ["That is your week", "Post, play or push a playlist in the cities where both audiences live."],
];

export function renderArtists(root, isCurrent) {
  document.title = "For music artists - AFTERSHOCK";
  const body = h("div", null, loading("this week's artists"));
  const feature = h("div", { class: "ma-feature", hidden: true });
  add(root,
    h("p", { class: "eyebrow mono" }, "For music artists"),
    h("h1", null, "Are you a musician? ", h("em", null, "Find your next fans.")),
    h("p", { class: "lede" }, "When a Netflix show spreads to a new country, its viewers there already love certain artists. If you are one of them, that is your week: here is where, and what to do."),
    h("ol", { class: "ma-how" }, HOW.map(([t, d]) => h("li", null, h("strong", null, t), h("span", null, d)))),
    feature,
    body);
  getArtists().then((data) => {
    if (!isCurrent()) return;
    const grid = h("ul", { class: "ma-grid" });
    const status = h("p", { class: "plan-note mono", role: "status" });
    const input = h("input", { type: "text", id: "artist-q", autocomplete: "off", spellcheck: "false", placeholder: "Type an artist's name" });
    const render = () => {
      const q = key(input.value);
      const hits = data.artists.filter((a) => !q || key(a.name).includes(q));
      grid.replaceChildren(...hits.map((a) => h("li", null, h("a", { class: "ma-card", href: artistHref(a.slug) },
        h("span", { class: "ma-avatar", "aria-hidden": "true" }, a.name.trim().charAt(0).toUpperCase()),
        h("span", { class: "ma-name" }, a.name),
        h("span", { class: "ma-meta" }, h("b", null, `${a.breakouts} ${a.breakouts === 1 ? "show" : "shows"}`), ` · ${a.countries.join(", ")}`)))));
      status.textContent = q ? `${hits.length} of ${data.artists.length} artists match` : `${data.artists.length} artists this week, most shows first`;
    };
    input.addEventListener("input", render);
    render();
    body.replaceChildren(
      h("div", { class: "ma-search" }, h("label", { for: "artist-q" }, "Find your name"), input),
      status, grid,
      h("p", { class: "plan-note" }, `Based on Qloo audience data for the week of ${data.week}; this shows where audiences overlap, not a prediction of streams or ticket sales.`));
    // This week's leading artist, told as one sentence, so the idea is clear before anyone searches.
    const top = data.artists[0];
    if (top) getArtist(top.slug).then((a) => {
      const b = a.breakouts?.[0];
      if (!isCurrent() || !b) return;
      feature.replaceChildren(h("p", { class: "ma-feature-tag mono" }, "This week's example"),
        h("h2", null, `${a.name}: ${b.country}, this week`),
        h("p", null, `Viewers of ${b.title}, heading to ${b.country}, like ${a.name}'s music far more than average.${b.cities.length ? ` Both audiences live around ${join(b.cities)}.` : ""}`),
        h("a", { class: "btn btn-primary", href: artistHref(a.slug) }, `See ${a.name}'s week`));
      feature.hidden = false;
    }).catch(() => {});
  }).catch((err) => { if (isCurrent()) body.replaceChildren(errorBox("the artist list", err)); });
}

function card(name, b) {
  const kit = [b.qloo_confirmed ? "Qloo confirmed the AI's suggestion for this audience." : "Not an AI suggestion: this artist came from Qloo's own list.",
    b.in_qloo_kit ? "Qloo's own list also named you." : null].filter(Boolean).join(" ");
  return h("li", { class: "plan-step ma-week" },
    h("div", { class: "ma-week-head" }, h("span", { class: "ma-week-pct" }, b.chance_label),
      h("span", null, h("strong", null, b.country), h("span", { class: "muted" }, ` via ${b.title}, popular in ${b.origin}`))),
    b.countrywide ? h("p", { class: "plan-note" }, h("span", { class: "tag tag-quiet" }, "country-wide taste"),
      " Qloo's picks for this title here mostly repeat what the whole country likes, so the link to this title is weak.") : null,
    h("p", null, `Viewers of ${b.title} (popular in ${b.origin}, with a ${b.chance_label} chance to reach the Top 10 in ${b.country} within ${b.horizon_weeks} weeks) like this artist's music far more than average, according to Qloo.`),
    b.cities.length ? h("p", null, `Both audiences concentrate in ${join(b.cities)}.`) : null,
    b.cities.length ? h("p", { class: "plan-decision" }, h("span", { class: "plan-rule mono" }, "This week's move"), " ",
      `A post, a DJ set or a playlist push aimed at ${join(b.cities)}, doable within about a week while the show is in the Top 10 there. Tours are booked months ahead; this is a quick idea where both audiences already live.`) : null,
    h("p", { class: "plan-note" }, kit),
    h("p", { class: "plan-link" }, h("a", { href: planHref(b.storm_id, b.code) }, `See the plan for ${b.title} in ${b.country}`)));
}

export function renderArtist(root, slug, isCurrent) {
  document.title = "Artist - AFTERSHOCK";
  const body = h("div", null, loading("this artist's breakouts"));
  add(root, h("p", { class: "crumb" }, h("a", { href: "#/artists" }, "All artists")), body);
  getArtist(slug).then((a) => {
    if (!isCurrent()) return;
    document.title = `${a.name} - AFTERSHOCK`;
    body.replaceChildren(
      h("p", { class: "eyebrow mono" }, "For music artists"),
      h("h1", null, `${a.name}: `, h("em", null, "where new fans are this week")),
      h("p", { class: "lede" }, `${a.breakouts.length} ${a.breakouts.length === 1 ? "show" : "shows"} heading to a new country this week ${a.breakouts.length === 1 ? "has" : "have"} viewers who love this music. Each card says where, and one thing to do there.`),
      h("ul", { class: "plan-steps" }, a.breakouts.map((b) => card(a.name, b))),
      h("p", { class: "plan-note" }, `Based on Qloo audience data for the week of ${a.week}; this shows where audiences overlap, not a prediction of streams or ticket sales.`));
    const h1 = root.querySelector("h1");
    if (h1) { h1.tabIndex = -1; h1.focus({ preventScroll: true }); }
  }).catch((err) => {
    if (!isCurrent()) return;
    if (err.status === 404) body.replaceChildren(h("h1", null, "Artist not found"), h("p", { class: "status status-error", role: "alert" }, err.message),
      h("p", null, h("a", { href: "#/artists" }, "Search all artists")));
    else body.replaceChildren(errorBox("this artist", err));
  });
}
