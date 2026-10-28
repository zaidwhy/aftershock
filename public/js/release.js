// Plan a release: for a film, series, album or comedy special that has not launched yet (or a tour), Qloo ranks
// countries by audience affinity, maps the cities, suggests venues and names the local taste to pair with. Worked
// examples load from static files; a typed title runs live (GET /api/release) and shows every Qloo call it made.
import { h, add, loading } from "./dom.js";
import { getReleaseExamples, getReleaseExample, planRelease } from "./api.js";
import { hotspotMap } from "./charts.js";
import { failBox } from "./audience.js";

const KINDS = [["film", "Film"], ["series", "Series"], ["music", "Album, song or music tour"], ["comedy", "Comedy special or tour"]];
const TASTE = [["tv_show", "Shows"], ["movie", "Films"], ["artist", "Artists"]];
const VENUE_WORD = { comedy: "Comedy clubs", music: "Live music venues", film: "Cinemas", series: "Cinemas for premieres" };
const two = (x) => (x == null ? "n/a" : x.toFixed(2));

function countryRows(plan) {
  const top = Math.max(0.01, ...plan.countries.map((c) => c.score));
  return h("ol", { class: "rel-countries" }, plan.countries.map((c, i) => h("li", { class: i < 3 ? "rel-top" : null },
    h("span", { class: "rel-rank mono" }, String(i + 1).padStart(2, "0")),
    h("span", { class: "rel-c" }, h("strong", null, c.name),
      h("span", { class: "rel-cities" }, (c.hotspots?.places?.length ? c.hotspots.places : (c.cities || []).map((x) => x.name)).slice(0, 3).join(", "))),
    h("span", { class: "rel-score" }, h("span", { class: "mono" }, two(c.score)),
      h("span", { class: "pbar", role: "img", "aria-label": `Qloo affinity ${two(c.score)}` }, h("span", { style: `width:${(c.score / top) * 100}%` }))))));
}

function cityMaps(plan) {
  const withCells = plan.countries.filter((c) => c.hotspots?.cells?.length).slice(0, 3);
  if (!withCells.length) return null;
  const grid = h("div", { class: "rel-maps" });
  for (const c of withCells) {
    const fig = h("figure", { class: "card rel-map" }, h("figcaption", null, h("span", { class: "gp-label mono qloo-mark" }, "Qloo heatmap"), h("strong", null, c.name),
      c.hotspots.places?.length ? h("span", { class: "muted" }, ` - ${c.hotspots.places.join(", ")}`) : null));
    grid.append(fig);
    const pc = c.hotspots.place_cells || [];
    const places = (c.hotspots.places || []).slice(0, pc.length).map((name, i) => ({ name, cell: pc[i] }));
    hotspotMap(c.code, c.hotspots.cells, { places, width: 320, height: 220, label: `Where the audience lives in ${c.name}` })
      .then((svg) => { if (svg) fig.append(svg); }).catch(() => {});
  }
  return grid;
}

function venues(plan) {
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

function callTrail(plan) {
  return h("details", { class: "rel-trail" },
    h("summary", null, `Every Qloo call this plan made (${plan.calls})`),
    h("ol", { class: "steps" }, (plan.steps || []).map((st, i) => h("li", { class: st.ok ? null : "step-no" },
      h("span", { class: "step-n mono" }, String(i + 1)),
      h("span", null, h("span", { class: "mono ask-tool" }, `GET ${st.endpoint}`), ` x${st.calls} `, st.note,
        h("code", { class: "rel-params" }, Object.entries(st.params || {}).map(([k, v]) => `${k}=${v}`).join("&")),
        st.varies ? h("span", { class: "muted rel-varies" }, ` varies: ${Object.entries(st.varies).map(([k, v]) => `${k} over ${Array.isArray(v) ? v.length : 1}`).join(", ")}`) : null)))));
}

function result(plan) {
  if (!plan.resolved) return h("div", { class: "status" }, h("p", null, plan.message || "Qloo did not recognise that title or any comparable."));
  const used = plan.signal?.used === "comparables"
    ? `Qloo does not know "${plan.name}" yet, so the audience comes from its comparables: ${plan.signal.entities.map((e) => e.name).join(", ")}.`
    : `Qloo knows ${plan.signal.entities[0]?.name}, so its own audience is the signal.`;
  const lead = plan.countries[0];
  return h("div", { class: "rel-result" },
    plan.example ? h("p", { class: "tag tag-quiet rel-example" }, plan.example_note) : null,
    h("p", { class: "rel-signal" }, h("span", { class: "gp-label mono qloo-mark" }, "Qloo signal"), used),
    lead ? h("p", { class: "rel-lead" }, h("span", { class: "gp-num" }, lead.name), lead.summary ? h("span", { class: "muted" }, ` ${lead.summary}`) : null) : null,
    h("section", { class: "rel-sec" }, h("h2", null, "Where the audience is"),
      h("p", { class: "muted" }, `Qloo ranked ${plan.countries_checked} countries by how closely their places match this audience (Qloo affinity, 0 to 1, relative, not a forecast).`),
      countryRows(plan), cityMaps(plan)),
    h("section", { class: "rel-sec" }, h("h2", null, VENUE_WORD[plan.kind] || "Venues"), venues(plan)),
    h("section", { class: "rel-sec" }, h("h2", null, "Local taste to pair it with"),
      h("p", { class: "muted" }, "Qloo's picks for this audience in each top country: collaborators, co-promotions and playlist or watch-party tie-ins."), taste(plan)),
    callTrail(plan),
    plan.caveats?.length ? h("section", { class: "rel-sec" }, h("h3", null, "What this can't tell you"), h("ul", { class: "muted" }, plan.caveats.map((c) => h("li", null, c)))) : null);
}

export function renderRelease(root, isCurrent, preset = {}) {
  document.title = "Plan a release - AFTERSHOCK";
  const out = h("div", { "aria-live": "polite" });
  const name = h("input", { id: "rel-name", type: "text", maxlength: "120", required: true, value: preset.name || "", placeholder: "Title, artist or comedian" });
  const kind = h("select", { id: "rel-kind" }, KINDS.map(([v, l]) => h("option", { value: v, selected: v === (preset.kind || "film") }, l)));
  const like = h("input", { id: "rel-like", type: "text", maxlength: "600", placeholder: "Optional: up to 3 comparables, comma separated" });
  const go = h("button", { type: "submit", class: "btn btn-primary" }, "Plan it with Qloo");
  const examples = h("div", { class: "rel-examples" });

  const show = (plan) => { out.replaceChildren(result(plan)); out.scrollIntoView({ block: "start", behavior: "smooth" }); };
  const runLive = () => {
    const n = name.value.trim();
    if (!n) { name.focus(); return; }
    go.disabled = true;
    out.replaceChildren(loading("Asking Qloo: 24 countries, the cities, venues and local taste. About 20 seconds.", true));
    planRelease(n, kind.value, like.value).then((plan) => { if (isCurrent()) show(plan); })
      .catch((err) => { if (isCurrent()) out.replaceChildren(failBox(err, "the release planner")); })
      .finally(() => { go.disabled = false; });
  };

  add(root,
    h("section", { class: "rel-hero" },
      h("p", { class: "eyebrow mono" }, "Plan a release"),
      h("h1", null, "Releasing something new? ", h("em", null, "Find its audience first.")),
      h("p", { class: "lede" }, "A new film, series, album or comedy special, or a tour. Qloo's taste graph ranks countries and cities by how closely they match the audience, finds venues there, and names the local shows, films and artists to pair it with. If Qloo has never heard of your title, give it a few comparables."),
      h("form", { class: "rel-form card", onsubmit: (e) => { e.preventDefault(); runLive(); } },
        h("label", { for: "rel-name" }, "What are you releasing?"), name,
        h("label", { for: "rel-kind" }, "Kind"), kind,
        h("label", { for: "rel-like" }, "Like (for something Qloo doesn't know yet)"), like,
        go),
      h("p", { class: "rail-h mono" }, "Or open a worked example"), examples),
    out);

  getReleaseExamples().then((idx) => {
    if (!isCurrent()) return;
    examples.replaceChildren(...idx.examples.map((x) => h("button", { type: "button", class: "rail-chip", onclick: () => {
      out.replaceChildren(loading("this example"));
      getReleaseExample(x.slug).then((plan) => { if (isCurrent()) show(plan); }).catch((err) => out.replaceChildren(failBox(err, "the example")));
    } }, h("span", null, h("span", { class: "rc-t" }, x.name), h("span", { class: "rc-n mono" }, `${x.headline}: ${x.top_countries.map((c) => c.name).join(", ")}`)))));
    if (!preset.name && idx.examples[0]) getReleaseExample(idx.examples[0].slug).then((plan) => { if (isCurrent()) out.replaceChildren(result(plan)); }).catch(() => {});
  }).catch(() => { examples.replaceChildren(h("p", { class: "muted" }, "Worked examples are not available right now; type a title above.")); });
}
