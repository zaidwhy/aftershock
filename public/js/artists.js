// "For artists": the week's breakouts read from the artist's side. Data from aftershock/artist_view.py, exported to
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

export function renderArtists(root, isCurrent) {
  document.title = "For artists - AFTERSHOCK";
  const body = h("div", null, loading("this week's artists"));
  add(root, h("h1", null, "For artists"),
    h("p", { class: "pitch" }, "Where new fans may be this week. Qloo links each artist below to the audience of a title that is breaking out in a new country. Find your name, or browse by how many breakouts mention you."),
    body);
  getArtists().then((data) => {
    if (!isCurrent()) return;
    const list = h("ul", { class: "artist-list" });
    const status = h("p", { class: "plan-note mono", role: "status" });
    const input = h("input", { type: "text", id: "artist-q", autocomplete: "off", spellcheck: "false" });
    const render = () => {
      const q = key(input.value);
      const hits = data.artists.filter((a) => !q || key(a.name).includes(q));
      list.replaceChildren(...hits.map((a) => h("li", null,
        h("a", { href: artistHref(a.slug) }, a.name), " ",
        h("span", { class: "muted" }, `${a.breakouts} ${a.breakouts === 1 ? "breakout" : "breakouts"}: ${a.countries.join(", ")}`),
        a.countrywide_only ? [" ", h("span", { class: "tag tag-quiet" }, "country-wide taste")] : null)));
      status.textContent = `${hits.length} of ${data.artists.length} artists`;
    };
    input.addEventListener("input", render);
    render();
    body.replaceChildren(
      h("div", { class: "field" }, h("label", { for: "artist-q" }, "Search by name"), input),
      status, list,
      h("p", { class: "plan-note" }, `Based on Qloo audience data for the week of ${data.week}; this is where audiences overlap, not a forecast of streams or ticket sales.`));
  }).catch((err) => { if (isCurrent()) body.replaceChildren(errorBox("the artist list", err)); });
}

function card(name, b) {
  const kit = [b.qloo_confirmed ? "Qloo confirmed the AI's suggestion for this audience." : "Not an AI suggestion: this artist came from Qloo's own list.",
    b.in_qloo_kit ? "Qloo's own list also named you." : null].filter(Boolean).join(" ");
  return h("li", { class: "plan-step" },
    b.countrywide ? h("p", { class: "plan-note" }, h("span", { class: "tag tag-quiet" }, "country-wide taste"),
      " This title's kit in this country mostly repeats what the whole country likes, so the link to this title is weak.") : null,
    h("p", null, `Viewers of ${b.title} (breaking out from ${b.origin} into ${b.country}, ${b.chance_label} chance to chart there within ${b.horizon_weeks} weeks) over-index on this artist's music, according to Qloo.`),
    b.cities.length ? h("p", null, `Both audiences concentrate in ${join(b.cities)}.`) : null,
    b.cities.length ? h("p", { class: "plan-decision" }, h("span", { class: "plan-rule mono" }, "This week's move"), " ",
      `A post, a DJ set or a playlist push aimed at ${join(b.cities)}, doable within about a week while the title is charting. Tours are booked months ahead; this is a short activation where both audiences already live.`) : null,
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
      h("h1", null, `${a.name}: where new fans are this week`),
      h("ul", { class: "plan-steps" }, a.breakouts.map((b) => card(a.name, b))),
      h("p", { class: "plan-note" }, `Based on Qloo audience data for the week of ${a.week}; this is where audiences overlap, not a forecast of streams or ticket sales.`));
    const h1 = root.querySelector("h1");
    if (h1) { h1.tabIndex = -1; h1.focus({ preventScroll: true }); }
  }).catch((err) => {
    if (!isCurrent()) return;
    if (err.status === 404) body.replaceChildren(h("h1", null, "Artist not found"), h("p", { class: "status status-error", role: "alert" }, err.message),
      h("p", null, h("a", { href: "#/artists" }, "Search all artists")));
    else body.replaceChildren(errorBox("this artist", err));
  });
}
