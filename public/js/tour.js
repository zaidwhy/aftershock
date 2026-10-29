// The guided tour tells the product as a story and does each step for real: the cursor glides to a feature, the
// feature is cut out of a blurred page, and where it helps the tour acts (follows a breakout on the globe, asks the
// chat a question) so the visitor sees it work instead of reading about it. Runs once on a first visit to the home
// page and again from the Tour button; Play advances on its own.
import { h, s } from "./dom.js";

const SEEN_KEY = "aftershock-tour-seen";
const PAD = 8;
const AUTO_MS = 7000;
const TYPE_MS = 38;
const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

/** Click the way a person would, and show the cursor doing it. */
function press(el, cursor) {
  if (!el) return;
  const r = el.getBoundingClientRect();
  cursor.style.left = `${r.left + r.width / 2}px`;
  cursor.style.top = `${r.top + r.height / 2}px`;
  const ring = h("span", { class: "tour-click", style: `left:${r.left + r.width / 2}px;top:${r.top + r.height / 2}px` });
  document.body.append(ring);
  setTimeout(() => ring.remove(), 700);
  el.click();
}

const chatOpen = () => !document.querySelector(".chat")?.hidden;
const closeChat = () => { if (chatOpen()) document.querySelector(".chat .gp-close")?.click(); };

const STEPS = [
  { sel: '[data-tour="globe"]', clearOf: ".stage-copy h1", kicker: "The tremor",
    title: "Every week, something breaks out",
    text: "Each glowing country is where a Netflix title just entered the Top 10 and nowhere else. The arcs are where it is likely to go next. Drag the globe; click any country." },
  { sel: '[data-tour="rail"]', kicker: "The aftershock", title: "Follow one breakout",
    text: "Watch: we follow Nightwatch, a Danish horror film. The globe flies to Denmark, draws its likely next countries, and the panel says how likely, where it ranks, and why.",
    act: async (cursor) => {
      const chip = [...document.querySelectorAll(".rail-chip")].find((c) => /nightwatch/i.test(c.textContent))
        || document.querySelectorAll(".rail-chip")[1];
      press(chip, cursor);
      return 2600;
    },
    then: '[data-tour="globe"]' },
  { sel: '[data-tour="plan"]', kicker: "The plan", title: "From forecast to Launch Brief",
    text: "Seven visible steps: the forecast, Qloo's own picks, an AI's ideas, Qloo checking every one, the cities, artists matched to cities, and a brief that says what each claim rests on." },
  { sel: '[data-tour="release"]', kicker: "Something new", title: "Plan a release",
    text: "A film, an album, a comedy special or a tour that is not out yet. Qloo finds the countries, the cities, the venues and the local taste. Try Kevin Hart." },
  { sel: '[data-tour="qloo"]', kicker: "The check", title: "Why Qloo decides",
    text: "An AI alone named partners Qloo could not back 71% of the time. So the AI only proposes, and Qloo's taste graph decides what goes in the plan." },
  { sel: ".fc-band", kicker: "The proof", title: "Does the forecast work?",
    text: "On 829 past breakouts it never saw, its top 3 caught the next market 2.4 times as often as the obvious guess. A triage tool, not a crystal ball; every miss is on the Scorecard." },
  { sel: '[data-tour="chat"]', then: ".chat", kicker: "Ask anything", title: "Ask AFTERSHOCK",
    text: "Watch: we ask why Nightwatch is breaking in Norway. It answers from the site's own tools and shows every step it took. No AI writes the answer, so it cannot make one up.",
    act: async (cursor) => {
      if (!chatOpen()) press(document.querySelector('[data-tour="chat"]'), cursor);
      await wait(400);
      const input = document.querySelector(".chat-form input");
      if (!input) return 0;
      const question = "why is nightwatch breaking in norway";
      input.value = "";
      for (const ch of question) { input.value += ch; await wait(reduced() ? 0 : TYPE_MS); }
      input.form?.requestSubmit();
      return 1800;
    },
    leave: closeChat },
  { sel: '[data-tour="theme"]', kicker: "Your way", title: "Light or dark",
    text: "Prefer daylight? Switch themes here; the globe changes with it. Your choice is remembered on this browser." },
  { sel: '[data-tour="replay"]', kicker: "That's it", title: "Replay any time",
    text: "The tour lives here. The About page says who built AFTERSHOCK, who it is for, and what it does not claim." },
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
  const kicker = h("p", { class: "tour-step mono" });
  const title = h("h3", null);
  const text = h("p", null);
  const progress = h("div", { class: "tour-progress", "aria-hidden": "true" });
  const back = h("button", { type: "button", class: "btn btn-ghost" }, "Back");
  const next = h("button", { type: "button", class: "btn btn-primary" }, "Next");
  const play = h("button", { type: "button", class: "btn btn-ghost tour-play", "aria-pressed": "false" }, "Play");
  const skip = h("button", { type: "button", class: "btn btn-ghost" }, "Skip");
  const card = h("div", { class: "tour-card", role: "dialog", "aria-modal": "true", "aria-label": "Guided tour" },
    progress, kicker, title, text, h("div", { class: "tour-nav" }, skip, play, h("span", { class: "tour-gap" }), back, next));
  document.body.append(blur, hole, cursor, card);
  cursor.style.left = `${innerWidth / 2}px`;
  cursor.style.top = `${innerHeight / 2}px`;

  const steps = STEPS.filter((st) => document.querySelector(st.sel) || st.act);
  progress.append(...steps.map(() => h("span", null)));
  let i = 0;
  let target = null;
  let timer = null;
  let ticket = 0;

  const place = () => {
    const el = document.querySelector(target);
    if (!el) return;
    const r = el.getBoundingClientRect();
    let edge = r.left;
    // A target that sits under other content (the globe under the headline) starts where that content ends.
    const over = steps[i].clearOf && document.querySelector(steps[i].clearOf)?.getBoundingClientRect();
    if (over && over.right > edge && over.right < r.right - 200) edge = over.right + PAD;
    const box = { x: Math.max(4, edge - PAD), y: Math.max(4, r.top - PAD), w: Math.min(innerWidth - 8, r.right - edge + PAD * 2), h: Math.min(innerHeight - 8, r.height + PAD * 2) };
    Object.assign(hole.style, { left: `${box.x}px`, top: `${box.y}px`, width: `${box.w}px`, height: `${box.h}px` });
    // The blur covers everything except the target, so the feature stays sharp.
    blur.style.clipPath = `path(evenodd, "M0 0H${innerWidth}V${innerHeight}H0Z M${box.x} ${box.y}h${box.w}v${box.h}h${-box.w}Z")`;
    const cw = card.offsetWidth, ch = card.offsetHeight;
    const below = box.y + box.h + 14 + ch < innerHeight;
    const above = box.y - ch - 14 > 0;
    // Beside the target when it is too tall for a card above or below (the globe, the open chat).
    const side = !below && !above;
    const top = side ? Math.min(innerHeight - ch - 16, Math.max(12, box.y + 16)) : below ? box.y + box.h + 14 : box.y - ch - 14;
    const left = side ? (box.x > cw + 28 ? box.x - cw - 14 : Math.min(innerWidth - cw - 12, box.x + 16))
      : Math.min(innerWidth - cw - 12, Math.max(12, box.x + box.w / 2 - cw / 2));
    // Mid-scroll the target can still sit off screen; the card never follows it out of view.
    card.style.top = `${Math.min(innerHeight - ch - 12, Math.max(12, top))}px`;
    card.style.left = `${Math.max(12, left)}px`;
  };
  // Follow the target while scrolls and the globe's camera settle, so the cut-out lands where the feature ends up.
  const track = (ms) => {
    const until = performance.now() + ms;
    const tick = () => { place(); if (performance.now() < until && active) requestAnimationFrame(tick); };
    tick();
  };
  const pointAt = () => {
    const el = document.querySelector(target);
    if (!el) return;
    const r = el.getBoundingClientRect();
    cursor.style.left = `${Math.max(r.left, 12) + Math.min(r.width, innerWidth) / 2}px`;
    cursor.style.top = `${r.top + Math.min(r.height / 2, 60)}px`;
  };
  const schedule = () => {
    clearTimeout(timer);
    if (play.getAttribute("aria-pressed") === "true" && i < steps.length - 1) timer = setTimeout(() => go(i + 1), AUTO_MS);
  };
  async function go(to) {
    const mine = ++ticket;
    steps[i]?.leave?.();
    i = Math.max(0, Math.min(steps.length - 1, to));
    const st = steps[i];
    target = st.sel;
    kicker.textContent = `${i + 1} / ${steps.length}  ${st.kicker}`;
    title.textContent = st.title;
    text.textContent = st.text;
    [...progress.children].forEach((seg, k) => seg.classList.toggle("on", k <= i));
    back.hidden = i === 0;
    next.textContent = i === steps.length - 1 ? "Done" : "Next";
    const el = document.querySelector(st.sel);
    const pinned = el && (getComputedStyle(el).position === "fixed" || el.closest(".site-head"));
    if (el && !pinned) el.scrollIntoView({ block: "center", behavior: reduced() ? "auto" : "smooth" });
    track(pinned ? 0 : 900);
    setTimeout(pointAt, pinned ? 0 : 700);
    next.focus({ preventScroll: true });
    if (st.act) {
      await wait(pinned ? 200 : 950);
      if (mine !== ticket || !active) return;
      const settle = await st.act(cursor);
      if (mine !== ticket || !active) return;
      if (st.then) {
        target = st.then;
        // Show the result from its top (the globe is taller than many screens), just under the sticky header.
        const r = document.querySelector(target)?.getBoundingClientRect();
        if (r && getComputedStyle(document.querySelector(target)).position !== "fixed") window.scrollTo({ top: Math.max(0, r.top + scrollY - 72), behavior: reduced() ? "auto" : "smooth" });
      }
      track(Math.max(settle || 0, st.then ? 900 : 0));
    }
    schedule();
  }
  const keys = (e) => {
    if (e.key === "Escape") end();
    else if (e.key === "ArrowRight") next.click();
    else if (e.key === "ArrowLeft" && i > 0) back.click();
  };
  const end = () => {
    clearTimeout(timer);
    ticket += 1;
    steps[i]?.leave?.();
    [blur, hole, cursor, card].forEach((n) => n.remove());
    removeEventListener("resize", place);
    removeEventListener("scroll", place);
    removeEventListener("keydown", keys);
    active = null;
    try { localStorage.setItem(SEEN_KEY, "1"); } catch { /* storage blocked: the tour simply shows again next visit */ }
  };
  next.onclick = () => { if (i === steps.length - 1) end(); else go(i + 1); };
  back.onclick = () => go(i - 1);
  skip.onclick = end;
  play.onclick = () => {
    const on = play.getAttribute("aria-pressed") !== "true";
    play.setAttribute("aria-pressed", String(on));
    play.textContent = on ? "Pause" : "Play";
    if (on && i === steps.length - 1) go(0); else schedule();
  };
  blur.onclick = () => next.click();
  addEventListener("resize", place);
  // A smooth scroll can outlast any fixed tracking window, so re-place on every scroll while the tour is open.
  addEventListener("scroll", place, { passive: true });
  addEventListener("keydown", keys);
  active = { end };
  go(0);
}

/** First visit to the home page: start the tour once the globe has had time to appear. */
export function maybeAutoTour() {
  let seen = false;
  try { seen = localStorage.getItem(SEEN_KEY) === "1"; } catch { seen = false; }
  if (seen || navigator.webdriver) return;
  setTimeout(() => { if (/^#\/?$/.test(location.hash || "#/")) startTour(); }, 2600);
}
