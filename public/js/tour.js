// The guided tour: an intro that says what AFTERSHOCK is (drawn on a seismograph), then seven short steps. Each step lifts one feature out of
// a blurred page, a cursor points at it, and where seeing beats reading the tour acts itself (follows a breakout on
// the globe, asks the chat a question). One line of text per step; dots, Back and Next; Esc or the cross to leave.
import { h, s } from "./dom.js";

const SEEN_KEY = "aftershock-tour-seen";
const PAD = 10;
const TYPE_MS = 34;
const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
// The hero copy sits over the globe's box; a spotlight on the globe starts where the copy ends.
const HERO_COPY = [".stage-copy h1", ".stage-copy .lede", ".stage-copy .cta-row", ".stage-copy .tour-link", ".stage-copy .stats-q", ".stage-stats"];

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
  { sel: '[data-tour="globe"]', clearOf: HERO_COPY, title: "This week, on a globe",
    text: "Each glowing country is where a Netflix show or film just got popular. The lines point to where we predict it goes next." },
  { sel: '[data-tour="globe"]', clearOf: HERO_COPY, title: "Follow one show",
    text: "Nightwatch, a Danish thriller film, is popular in Denmark. We predict Norway is the most likely next country, and the panel says why.",
    act: async () => {
      const chip = [...document.querySelectorAll(".rail-chip")].find((c) => /nightwatch/i.test(c.textContent))
        || document.querySelectorAll(".rail-chip")[1];
      // Follow it without sending the cursor down to the row of shows: the eye stays on the globe.
      chip?.click();
      return 2400;
    } },
  { sel: '[data-tour="plan"]', title: "Get the launch plan",
    text: "For the next country: the cities where fans live, and the local artists and brands Qloo's data supports." },
  { sel: '[data-tour="release"]', title: "Planning your own release?",
    text: "A film, an album, a comedy show or a tour: see which countries, cities and venues would love it." },
  { sel: '[data-tour="qloo"]', title: "Why Qloo matters",
    text: "An AI alone suggests partners with confidence, but Qloo's audience data supported only 29% of them. So here the AI suggests, and Qloo decides." },
  { sel: '[data-tour="chat"]', title: "Ask in plain words",
    text: "Ask about any show or country. Watch it answer, with the steps it took.",
    act: async (cursor, aim) => {
      if (!chatOpen()) press(document.querySelector('[data-tour="chat"]'), cursor);
      // The button hides as the chat opens; move the spotlight to the chat at once, not after the typing.
      aim(".chat");
      await wait(400);
      const input = document.querySelector(".chat-form input");
      if (!input) return 0;
      const question = "why is nightwatch heading to norway";
      input.value = "";
      for (const ch of question) { input.value += ch; await wait(reduced() ? 0 : TYPE_MS); }
      input.form?.requestSubmit();
      return 1600;
    },
    leave: closeChat },
  { sel: '[data-tour="theme"]', title: "Light or dark, your call",
    text: "Switch themes here. The Tour button beside it replays this tour any time." },
];

// What AFTERSHOCK is, before any step: the three things a first-time visitor needs (what, why special, why try).
const INTRO_POINTS = [
  ["What it is", "When a Netflix show or film gets popular in one country, AFTERSHOCK predicts which country it reaches next."],
  ["What makes it special", "Qloo's data on what people really like checks every launch idea, so each plan fits that country's audience."],
  ["Why try it", "See this week's predictions, and for each one a launch plan: the cities, the local artists, the brands."],
];

const cursorIcon = () => s("svg", { viewBox: "0 0 24 24", width: 24, height: 24, "aria-hidden": "true" },
  s("path", { d: "M4 2l16 9-7 1.6L9.5 20z", fill: "#fff", stroke: "#07090D", "stroke-width": 1.4, "stroke-linejoin": "round" }));

/** A seismograph trace: calm, one tremor, then smaller aftershocks. */
function seismograph() {
  const pts = [];
  for (let x = 0; x <= 600; x += 6) {
    const quake = Math.exp(-(((x - 210) / 34) ** 2)) * 58 + Math.exp(-(((x - 360) / 26) ** 2)) * 26 + Math.exp(-(((x - 470) / 20) ** 2)) * 12;
    pts.push(`${x},${(60 + Math.sin(x * 1.7) * (2 + quake)).toFixed(1)}`);
  }
  const d = `M${pts.join(" L")}`;
  // The pen rides the trace at the same pace and easing as the stroke that draws it.
  const pen = s("circle", { class: "tour-pen", r: 4.5 },
    s("animateMotion", { dur: "1.8s", begin: "0.2s", fill: "freeze", calcMode: "spline", keyTimes: "0;1", keySplines: ".4 0 .2 1", path: d }));
  return s("svg", { class: "tour-seismo", viewBox: "0 0 600 120", "aria-hidden": "true" },
    s("line", { class: "tour-base", x1: 0, y1: 60, x2: 600, y2: 60 }),
    s("path", { d, pathLength: 1 }), pen);
}

/** Three shock rings, one per tremor on the trace, each softer than the last. */
const shockRings = () => h("div", { class: "tour-rings", "aria-hidden": "true" }, h("span"), h("span"), h("span"));

let active = null;

function remember() {
  try { localStorage.setItem(SEEN_KEY, "1"); } catch { /* storage blocked: the tour simply shows again next visit */ }
}

export function startTour() {
  if (active) return;
  if (!document.querySelector(STEPS[0].sel)) {
    // The steps live on the home page.
    location.hash = "#/";
    setTimeout(startTour, 900);
    return;
  }
  const veil = h("div", { class: "tour-veil" });
  const introKeys = (e) => { if (e.key === "Escape") { leave(); remember(); } };
  const leave = () => { veil.remove(); active = null; removeEventListener("keydown", introKeys); };
  const go = h("button", { type: "button", class: "btn btn-primary" }, "Show me around (60 s)");
  veil.append(h("div", { class: "tour-intro", role: "dialog", "aria-modal": "true", "aria-label": "Welcome" },
    shockRings(),
    seismograph(),
    h("p", { class: "tour-step mono" }, "Welcome to AFTERSHOCK"),
    h("h2", null, "Shows travel. ", h("em", null, "See where next.")),
    h("ul", { class: "tour-points" }, INTRO_POINTS.map(([k, v]) => h("li", null, h("strong", null, k), h("span", null, v)))),
    h("p", { class: "tour-name" }, "Why the name? After an earthquake, smaller aftershocks follow nearby. Popular shows travel the same way."),
    h("div", { class: "tour-intro-actions" }, go,
      h("button", { type: "button", class: "btn btn-ghost", onclick: () => { leave(); remember(); } }, "I'll explore")),
    h("p", { class: "tour-keys mono" }, h("kbd", null, "Enter"), " to start, ", h("kbd", null, "Esc"), " to skip")));
  go.addEventListener("click", () => { leave(); run(); });
  document.body.append(veil);
  addEventListener("keydown", introKeys);
  active = { intro: true };
  go.focus();
}

function run() {
  // Step 1 is the whole week, whatever the globe was showing before.
  window.dispatchEvent(new CustomEvent("aftershock:globe-reset"));
  const blur = h("div", { class: "tour-blur" });
  const shield = h("div", { class: "tour-shield" });
  const hole = h("div", { class: "tour-hole" });
  const cursor = h("div", { class: "tour-cursor" }, cursorIcon());
  const count = h("span", { class: "tour-count mono" });
  const title = h("h3", null);
  const text = h("p", null);
  const dots = h("div", { class: "tour-dots", role: "tablist", "aria-label": "Tour steps" });
  const back = h("button", { type: "button", class: "btn btn-ghost btn-small" }, "Back");
  const next = h("button", { type: "button", class: "btn btn-primary btn-small" }, "Next");
  const close = h("button", { type: "button", class: "tour-x", "aria-label": "Close the tour" }, "×");
  const card = h("div", { class: "tour-card", role: "dialog", "aria-modal": "true", "aria-label": "Guided tour" },
    close, count, title, text, h("div", { class: "tour-foot" }, dots, h("span", { class: "tour-gap" }), back, next));
  document.body.append(blur, hole, shield, cursor, card);
  cursor.style.left = `${innerWidth / 2}px`;
  cursor.style.top = `${innerHeight / 2}px`;

  const steps = STEPS.filter((st) => document.querySelector(st.sel));
  dots.append(...steps.map((_, k) => h("button", { type: "button", role: "tab", "aria-label": `Step ${k + 1}`, onclick: () => show(k) })));
  let i = 0;
  let target = null;
  let ticket = 0;
  let frame = 0;

  const place = () => {
    const el = document.querySelector(target);
    if (!el) return;
    const r = el.getBoundingClientRect();
    // A target that has just hidden has no box; keep the spotlight where it was rather than jump to the corner.
    if (!r.width || !r.height) return;
    let edge = r.left;
    for (const sel of steps[i].clearOf || []) {
      const over = document.querySelector(sel)?.getBoundingClientRect();
      if (over && over.width && over.right > edge && over.right < r.right - 240 && over.bottom > r.top && over.top < r.bottom) edge = over.right + PAD;
    }
    const box = { x: Math.max(4, edge - PAD), y: Math.max(4, r.top - PAD), w: Math.min(innerWidth - 8, r.right - edge + PAD * 2), h: Math.min(innerHeight - 8, r.height + PAD * 2) };
    Object.assign(hole.style, { left: `${box.x}px`, top: `${box.y}px`, width: `${box.w}px`, height: `${box.h}px` });
    // The blur covers everything except the target, so the feature stays sharp.
    blur.style.clipPath = `path(evenodd, "M0 0H${innerWidth}V${innerHeight}H0Z M${box.x} ${box.y}h${box.w}v${box.h}h${-box.w}Z")`;
    const cw = card.offsetWidth, ch = card.offsetHeight;
    const roomLeft = box.x - 16 >= cw, roomRight = innerWidth - (box.x + box.w) - 16 >= cw;
    const roomBelow = innerHeight - (box.y + box.h) - 14 >= ch, roomAbove = box.y - 14 >= ch;
    let top, left;
    // Tall targets (the globe, the open chat) take the card beside them, level with their top.
    const tall = box.h > innerHeight * 0.45 && (roomLeft || roomRight);
    if (!tall && (roomBelow || roomAbove)) {
      top = roomBelow ? box.y + box.h + 14 : box.y - ch - 14;
      left = box.x + box.w / 2 - cw / 2;
    } else if (roomLeft || roomRight) {
      top = box.y + 12;
      left = roomLeft ? box.x - cw - 16 : roomRight ? box.x + box.w + 16 : box.x + 16;
    } else {
      // No room anywhere (a phone, a full-width target): dock at the bottom like a sheet, so the target's top shows.
      top = innerHeight - ch - 12;
      left = innerWidth / 2 - cw / 2;
    }
    // Never off screen, even mid-scroll.
    card.style.top = `${Math.min(innerHeight - ch - 12, Math.max(12, top))}px`;
    card.style.left = `${Math.min(innerWidth - cw - 12, Math.max(12, left))}px`;
  };
  const pointAt = () => {
    const el = document.querySelector(target);
    if (!el) return;
    const r = el.getBoundingClientRect();
    const x = Math.max(r.left, parseFloat(hole.style.left) || r.left);
    cursor.style.left = `${x + Math.min(r.right - x, innerWidth) / 2}px`;
    cursor.style.top = `${r.top + Math.min(r.height / 2, 80)}px`;
  };
  const scrollTo = (el) => {
    if (!el || getComputedStyle(el).position === "fixed" || el.closest(".site-head")) return;
    const r = el.getBoundingClientRect();
    // Tall targets show from their top, just under the sticky header, leaving room for the card below; short ones
    // sit mid-screen.
    const y = r.height > innerHeight * 0.4 ? r.top + scrollY - 72 : r.top + scrollY - (innerHeight - r.height) / 2;
    window.scrollTo({ top: Math.max(0, y), behavior: reduced() ? "auto" : "smooth" });
  };
  async function show(to) {
    const mine = ++ticket;
    if (to !== i) steps[i]?.leave?.();
    i = Math.max(0, Math.min(steps.length - 1, to));
    const st = steps[i];
    target = st.sel;
    count.textContent = String(i + 1).padStart(2, "0");
    title.textContent = st.title;
    text.textContent = st.text;
    [...dots.children].forEach((d, k) => { d.classList.toggle("on", k === i); d.setAttribute("aria-selected", String(k === i)); });
    back.disabled = i === 0;
    next.textContent = i === steps.length - 1 ? "Done" : "Next";
    card.classList.remove("tour-in");
    void card.offsetWidth;
    card.classList.add("tour-in");
    scrollTo(document.querySelector(target));
    setTimeout(pointAt, 650);
    next.focus({ preventScroll: true });
    if (st.act) {
      await wait(800);
      if (mine !== ticket || !active) return;
      await st.act(cursor, (sel) => { if (mine === ticket) { target = sel; setTimeout(pointAt, 350); } });
    }
  }
  const keys = (e) => {
    if (e.key === "Tab") {
      // Keep keyboard focus on the card's own buttons, so Enter cannot follow a link on the page behind it.
      const stops = [...card.querySelectorAll("button:not(:disabled)")];
      e.preventDefault();
      stops[(stops.indexOf(document.activeElement) + (e.shiftKey ? -1 : 1) + stops.length) % stops.length]?.focus();
    } else if (e.key === "Escape") end();
    else if (e.key === "ArrowRight") next.click();
    else if (e.key === "ArrowLeft" && i > 0) back.click();
  };
  const end = () => {
    ticket += 1;
    steps[i]?.leave?.();
    cancelAnimationFrame(frame);
    [blur, hole, shield, cursor, card].forEach((n) => n.remove());
    removeEventListener("resize", place);
    removeEventListener("keydown", keys);
    removeEventListener("hashchange", end);
    active = null;
    remember();
    // Leave the page as the visitor found it: the whole week on the globe, at the top.
    // Jump, then let the globe ease back on the next frame: a smooth scroll while the globe re-renders stalls weak GPUs.
    window.scrollTo({ top: 0, behavior: "auto" });
    requestAnimationFrame(() => window.dispatchEvent(new CustomEvent("aftershock:globe-reset")));
  };
  next.onclick = () => { if (i === steps.length - 1) end(); else show(i + 1); };
  back.onclick = () => show(i - 1);
  close.onclick = end;
  shield.onclick = () => { card.classList.remove("tour-nudge"); void card.offsetWidth; card.classList.add("tour-nudge"); next.focus({ preventScroll: true }); };
  addEventListener("resize", place);
  addEventListener("keydown", keys);
  // If the page changes anyway (the back button, a typed address), close cleanly instead of pointing at nothing.
  addEventListener("hashchange", end);
  // Scrolls, the globe's camera and the chat panel all move the target; keep the cut-out on it every frame.
  const follow = () => { if (active) { place(); frame = requestAnimationFrame(follow); } };
  active = { end };
  follow();
  show(0);
}

/** First visit to the home page: open the tour's intro once the globe has had time to appear. */
export function maybeAutoTour() {
  let seen = false;
  try { seen = localStorage.getItem(SEEN_KEY) === "1"; } catch { seen = false; }
  if (seen || navigator.webdriver) return;
  setTimeout(() => { if (/^#\/?$/.test(location.hash || "#/")) startTour(); }, 2600);
}
