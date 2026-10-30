// About: who builds AFTERSHOCK, who it is for, what it is built on, and where it goes next. Team details live in
// TEAM so the one place to correct them is here.
import { h, add } from "./dom.js";
import { roadmap } from "./roadmap.js";

const TEAM = {
  name: "Solstine",
  members: ["Zaid Ali Syed", "Hasnat Shaikh", "Shravni Gorde", "Farhan Khan"],
  email: "sidzaid72@gmail.com",
  repo: "https://github.com/zaidwhy/aftershock",
  video: "https://youtu.be/99EfYU-mKl0",
};

const card = (title, ...body) => h("div", { class: "card" }, h("h3", null, title), ...body);
const list = (items) => h("ul", null, items.map((x) => h("li", null, x)));

export function renderAbout(root) {
  document.title = "About - AFTERSHOCK";
  add(root,
    h("section", { class: "rel-hero" },
      h("p", { class: "eyebrow mono" }, "About"),
      h("h1", null, "We find the ", h("em", null, "next country"), " before the show gets there."),
      h("p", { class: "lede" }, "Built for the Qloo hackathon. When a Netflix show gets popular in one country, AFTERSHOCK predicts which country is next and plans the launch there with Qloo's audience data. An AI suggests; Qloo decides.")),
    h("section", { "aria-labelledby": "who-h" },
      h("h2", { id: "who-h" }, "Who it is for"),
      h("div", { class: "cards" },
        card("Brand marketers", h("p", null, "Moment marketing on a show before it trends in your country (a meme, a scene, a line), and the local brands Qloo links to its viewers.")),
        card("Labels and artist teams", h("p", null, "A one-week window to push a song where a show is about to land.")),
        card("Promoters and venues", h("p", null, "The cities that hold the audience, and the venues in them.")),
        card("Anyone releasing something new", h("p", null, "A film, series, album or special: where its audience is, country by country.")))),
    h("section", { "aria-labelledby": "built-h" },
      h("h2", { id: "built-h" }, "What it is built on"),
      h("div", { class: "cards" },
        h("div", { class: "card card-qloo" }, h("h3", null, h("span", { class: "qloo-mark" }, "Qloo")),
          list(["/v2/insights for artists, shows, films and brands per audience and country, and to confirm or reject each AI name",
            "urn:heatmap for the cities where an audience lives", "urn:entity:destination to rank countries for a new release",
            "urn:entity:place with venue tags for comedy clubs, music venues and cinemas", "/search to resolve every name strictly"])),
        card("Public data", list(["Netflix's public weekly Top 10, 94 countries, since 2021 (for the predictions)", "Wikimedia pageviews", "MusicBrainz (CC0)", "OpenStreetMap place names"])))),
    h("section", { "aria-labelledby": "next-h" },
      h("h2", { id: "next-h" }, "What's next"),
      roadmap(),
      card("Data, and what we cannot claim", list([
        "No permission from Netflix is claimed; its Terms of Use restrict automated access and reuse, so this is a hackathon prototype.",
        "No customers, pilots or prices yet.",
        "Predictions are chances, not promises. Checking them against real results is paused until Netflix permits reading its newer files."]))),
    h("section", { "aria-labelledby": "team-h" },
      h("h2", { id: "team-h" }, "The team"),
      h("div", { class: "card" },
        h("h3", null, `Team ${TEAM.name}`),
        h("p", { class: "team-line" }, TEAM.members.join("  ·  ")),
        h("p", null, "Contact: ", h("span", { class: "mono", style: "user-select:all" }, TEAM.email)),
        h("p", null, h("a", { href: TEAM.video }, "The 2-minute demo video"), "  ·  ", h("a", { href: TEAM.repo }, "Code, method and every test on GitHub")))));
}
