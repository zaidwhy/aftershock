// What comes after the hackathon, as a timeline: the same five steps as the Devpost story's "What's next", in the
// order they would happen. Permission comes first: the weekly runs are paused until Netflix allows them. Shown on
// the home page and on About.
import { h } from "./dom.js";

const STEPS = [
  ["Now", "Permission first", "Weekly runs are paused. Ask Netflix; add another chart only once its terms allow it."],
  ["Once permitted", "Graded in public", "Every prediction recorded in advance checked against the real Top 10, misses included."],
  ["Next", "Demand without a release", "Countries where Qloo sees the audience but the show is not on Netflix there yet."],
  ["Next", "Tours and live shows", "Event calendars beside the audience, so a promoter sees open dates."],
  ["Then", "A first real test", "With a label, a brand or a promoter: does acting on a plan move streams, sales or tickets?"],
];

export function roadmap() {
  return h("ol", { class: "roadmap" }, STEPS.map(([when, title, line]) =>
    h("li", null, h("span", { class: "rm-when mono" }, when), h("strong", { class: "rm-title" }, title), h("span", { class: "rm-line" }, line))));
}
