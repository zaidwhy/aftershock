// About: who builds AFTERSHOCK, who it is for, what it is built on, and where it goes next. Team details live in
// TEAM so the one place to correct them is here.
import { h, add } from "./dom.js";

const TEAM = {
  name: "Solstine",
  members: ["Zaid Ali Syed", "Hasnat Shaikh", "Shravni Gorde", "Farhan Khan"],
  email: "sidzaid72@gmail.com",
  repo: "https://github.com/zaidwhy/aftershock",
};

const card = (title, ...body) => h("div", { class: "card" }, h("h3", null, title), ...body);
const list = (items) => h("ul", null, items.map((x) => h("li", null, x)));

export function renderAbout(root) {
  document.title = "About - AFTERSHOCK";
  add(root,
    h("section", { class: "rel-hero" },
      h("p", { class: "eyebrow mono" }, "About"),
      h("h1", null, "We find the ", h("em", null, "next country"), " before the hit gets there."),
      h("p", { class: "lede" }, "AFTERSHOCK is a launch agent built for the Qloo hackathon. When a title breaks out in one country, it forecasts where it charts next from Netflix's own history, then uses Qloo's taste graph to plan the launch there: which artists, brands and shows that audience loves, which cities it lives in, and which venues fit. An AI proposes; Qloo decides.")),
    h("section", { "aria-labelledby": "who-h" },
      h("h2", { id: "who-h" }, "Who it is for"),
      h("div", { class: "cards" },
        card("Music labels and artist teams", h("p", null, "A catalogue song or an artist whose fans overlap a show's audience gets a one-week window when that show lands in a new country: a playlist push, a post, a local ad, a show announcement.")),
        card("Promoters and venues", h("p", null, "Which cities hold the audience, and which comedy clubs, music venues or cinemas sit there. Plan a release does the same for a new act or a tour.")),
        card("Brand marketers", h("p", null, "Local brands Qloo links to that audience in that country, checked one by one instead of guessed by an AI.")),
        card("Distributors and creators releasing something new", h("p", null, "A film, series, album or comedy special that has not launched yet: where its audience is, country by country, and what local taste to pair it with.")))),
    h("section", { "aria-labelledby": "built-h" },
      h("h2", { id: "built-h" }, "What it is built on"),
      h("div", { class: "cards" },
        h("div", { class: "card card-qloo" }, h("h3", null, h("span", { class: "qloo-mark" }, "Qloo")),
          list(["/v2/insights for artists, shows, films and brands per audience and country, and to confirm or reject each AI name",
            "urn:heatmap for the cities where an audience lives", "urn:entity:destination to rank countries for a new release",
            "urn:entity:place with venue tags for comedy clubs, music venues and cinemas", "/search to resolve every name strictly"])),
        card("Public data", list(["Netflix's public weekly Top 10, 94 countries, since 2021 (the forecast)", "Wikimedia pageviews", "MusicBrainz (CC0)", "OpenStreetMap place names"])))),
    h("section", { "aria-labelledby": "next-h" },
      h("h2", { id: "next-h" }, "Where it goes next"),
      h("div", { class: "cards" },
        card("More charts, with permission", h("p", null, "Netflix is the only streamer we found that publishes per-country weekly charts with years of history, which is what let us backtest on 829 past breakouts. Any other chart (music, video, other streamers) plugs into the same forecast once its terms allow it; we do not scrape.")),
        card("Demand where there is no release", h("p", null, "With streaming availability data, the agent could flag countries where Qloo sees the audience but the title is not offered, so a distributor can license it there. Not built yet.")),
        card("Live shows and comedy", h("p", null, "Plan a release already handles comedians and touring artists. Next: ticketing and event calendars, so a promoter sees open dates beside the audience.")),
        card("What it will not claim", h("p", null, "No customers, pilots or prices yet. Forecasts are probabilities, graded in public on the ledger from 15 November.")))),
    h("section", { "aria-labelledby": "team-h" },
      h("h2", { id: "team-h" }, "The team"),
      h("div", { class: "card" },
        h("h3", null, `Team ${TEAM.name}`),
        h("p", { class: "team-line" }, TEAM.members.join("  ·  ")),
        h("p", null, "Contact: ", h("span", { class: "mono", style: "user-select:all" }, TEAM.email)),
        h("p", null, h("a", { href: TEAM.repo }, "Code, method and every test on GitHub")))));
}
