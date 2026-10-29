// What comes after the hackathon, as a timeline: the same five steps as the Devpost story's "What's next", in the
// order they would happen. Shown on the home page and on About.
import { h } from "./dom.js";

const STEPS = [
  ["From 15 Nov", "Graded in public", "Every locked forecast checked against the real chart, misses included."],
  ["Before any real use", "Permission first", "Ask Netflix. Add another chart only once its terms allow it."],
  ["Next", "Demand without a release", "Countries where Qloo sees the audience but the title is not offered yet."],
  ["Next", "Tours and live shows", "Event calendars beside the audience, so a promoter sees open dates."],
  ["Then", "A first real test", "With a label or promoter: does acting on a brief move streams or tickets?"],
];

export function roadmap() {
  return h("ol", { class: "roadmap" }, STEPS.map(([when, title, line]) =>
    h("li", null, h("span", { class: "rm-when mono" }, when), h("strong", { class: "rm-title" }, title), h("span", { class: "rm-line" }, line))));
}
