// The guided tour: a cursor glides to each feature, the feature is cut out of a blurred, dimmed page, and a card
// says what it does. Runs once on a first visit to the home page and again from the Tour button.
import { h, s } from "./dom.js";

const SEEN_KEY = "aftershock-tour-seen";
const PAD = 8;
const STEPS = [
  { sel: '[data-tour="globe"]', title: "This week's breakouts, live", text: "Each glowing country is where a Netflix title just broke out. Arcs show where it is forecast to chart next. Drag to spin, scroll to zoom, click any country for its chance and the reason." },
  { sel: '[data-tour="rail"]', title: "Follow one breakout", text: "Pick a title: the globe flies to it, draws its next countries, and raises Qloo's city heatmap where that audience lives." },
  { sel: '[data-tour="plan"]', title: "Plan a launch", text: "The agent's seven steps, all visible: forecast, Qloo's own picks, an AI's ideas, Qloo checking every one, the cities, artists matched to cities, and a Launch Brief to download." },
  { sel: '[data-tour="release"]', title: "Plan a release", text: "Releasing a new film, series, album or comedy special, or going on tour? Qloo ranks countries and cities by audience affinity, suggests venues, and names the local taste to pair with." },
  { sel: '[data-tour="qloo"]', title: "Why Qloo decides", text: "An AI alone named partners Qloo could not back 71% of the time. So the AI only proposes; Qloo's taste graph decides what goes in the plan." },
  { sel: '[data-nav="scorecard"]', title: "Scorecard and ledger", text: "Every test we ran, misses included, and 3,240 forecasts locked in public before their outcomes, graded from 15 November." },
  { sel: '[data-tour="chat"]', title: "Ask AFTERSHOCK", text: "The agent answers in plain words: why a title is missing, why it is breaking in a country, where a release could work, or what any feature does. It shows every step it took." },
  { sel: '[data-tour="replay"]', title: "That's the tour", text: "Replay it any time from here. The About page says who built this and who it is for." },
];

const cursorIcon = () => s("svg", { viewBox: "0 0 24 24", width: 26, height: 26, "aria-hidden": "true" },
  s("path", { d: "M4 2l16 9-7 1.6L9.5 20z", fill: "#fff", stroke: "#07090D", "stroke-width": 1.4, "stroke-linejoin": "round" }));

let active = null;

export function startTour() {
  if (active) return;
  if (!document.querySelector(STEPS[0].sel)) {
    // Every step but the header ones lives on the home page.
    location.hash = "#/";
    setTimeout(startTour, 900);
    return;
  }
  const blur = h("div", { class: "tour-blur" });
  const hole = h("div", { class: "tour-hole" });
  const cursor = h("div", { class: "tour-cursor" }, cursorIcon());
  const step = h("p", { class: "tour-step mono" });
  const title = h("h3", null);
  const text = h("p", null);
  const back = h("button", { type: "button", class: "btn btn-ghost" }, "Back");
  const next = h("button", { type: "button", class: "btn btn-primary" }, "Next");
  const skip = h("button", { type: "button", class: "btn btn-ghost" }, "Skip");
  const card = h("div", { class: "tour-card", role: "dialog", "aria-modal": "true", "aria-label": "Guided tour" }, step, title, text, h("div", { class: "tour-nav" }, skip, back, next));
  document.body.append(blur, hole, cursor, card);
  cursor.style.left = `${innerWidth / 2}px`;
  cursor.style.top = `${innerHeight / 2}px`;

  let i = 0;
  const steps = STEPS.filter((st) => document.querySelector(st.sel));
  const place = () => {
    const el = document.querySelector(steps[i].sel);
    if (!el) return;
    const r = el.getBoundingClientRect();
    const box = { x: Math.max(4, r.left - PAD), y: Math.max(4, r.top - PAD), w: Math.min(innerWidth - 8, r.width + PAD * 2), h: Math.min(innerHeight - 8, r.height + PAD * 2) };
    Object.assign(hole.style, { left: `${box.x}px`, top: `${box.y}px`, width: `${box.w}px`, height: `${box.h}px` });
    // The blur covers everything except the target, so the feature stays sharp.
    blur.style.clipPath = `path(evenodd, "M0 0H${innerWidth}V${innerHeight}H0Z M${box.x} ${box.y}h${box.w}v${box.h}h${-box.w}Z")`;
    cursor.style.left = `${box.x + box.w / 2}px`;
    cursor.style.top = `${box.y + Math.min(box.h / 2, 60)}px`;
    const cw = card.offsetWidth, ch = card.offsetHeight;
    const below = box.y + box.h + 14 + ch < innerHeight;
    const top = below ? box.y + box.h + 14 : Math.max(12, box.y - ch - 14);
    const left = Math.min(innerWidth - cw - 12, Math.max(12, box.x + box.w / 2 - cw / 2));
    // A target taller than the screen leaves no room above or below: the card sits over its lower part.
    card.style.top = `${box.h > innerHeight - ch - 40 ? innerHeight - ch - 16 : top}px`;
    card.style.left = `${left}px`;
  };
  const show = () => {
    const st = steps[i];
    step.textContent = `${i + 1} of ${steps.length}`;
    title.textContent = st.title;
    text.textContent = st.text;
    back.hidden = i === 0;
    next.textContent = i === steps.length - 1 ? "Done" : "Next";
    const el = document.querySelector(st.sel);
    const pinned = el && (getComputedStyle(el).position === "fixed" || el.closest(".site-head"));
    if (el && !pinned) el.scrollIntoView({ block: "center", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    // Follow the target while the smooth scroll runs, so the cut-out lands where the feature ends up.
    const until = performance.now() + (pinned ? 0 : 900);
    const track = () => { place(); if (performance.now() < until && active) requestAnimationFrame(track); };
    track();
    next.focus({ preventScroll: true });
  };
  const keys = (e) => {
    if (e.key === "Escape") end();
    else if (e.key === "ArrowRight") next.click();
    else if (e.key === "ArrowLeft" && i > 0) back.click();
  };
  const end = () => {
    [blur, hole, cursor, card].forEach((n) => n.remove());
    removeEventListener("resize", place);
    removeEventListener("keydown", keys);
    active = null;
    try { localStorage.setItem(SEEN_KEY, "1"); } catch { /* storage blocked: the tour simply shows again next visit */ }
  };
  next.onclick = () => { if (i === steps.length - 1) end(); else { i += 1; show(); } };
  back.onclick = () => { i = Math.max(0, i - 1); show(); };
  skip.onclick = end;
  blur.onclick = () => next.click();
  addEventListener("resize", place);
  addEventListener("keydown", keys);
  active = { end };
  show();
}

/** First visit to the home page: start the tour once the globe has had time to appear. */
export function maybeAutoTour() {
  let seen = false;
  try { seen = localStorage.getItem(SEEN_KEY) === "1"; } catch { seen = false; }
  if (seen || navigator.webdriver) return;
  setTimeout(() => { if (/^#\/?$/.test(location.hash || "#/")) startTour(); }, 2600);
}
