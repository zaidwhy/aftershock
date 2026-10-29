// AFTERSHOCK frontend. Config: real API by default (same origin /api/...), mocks only with ?mock=1.
const USE_MOCK = new URLSearchParams(location.search).has("mock");
export const CONFIG = {
  mock: USE_MOCK,
  apiBase: "/api",
  dataBase: "/data",
  mockBase: "mock",
};

import { setConfig } from "./js/api.js";
import { renderHome, renderStorm, renderRipple, renderTry, renderScout, renderScorecard, renderLedger, renderMethod, renderNotFound } from "./js/views.js";
import { renderAgent } from "./js/agent.js";
import { renderPlan } from "./js/plan.js";
import { renderArtists, renderArtist } from "./js/artists.js";
import { renderRelease } from "./js/release.js";
import { renderAbout } from "./js/about.js";
import { mountChat } from "./js/chat.js";
import { startTour, maybeAutoTour } from "./js/tour.js";
import { startMotion } from "./js/motion.js";

setConfig(CONFIG);

const app = document.getElementById("app");
let token = 0;

const routes = [
  [/^#\/?(?:\?(.*))?$/, (m) => (el, t) => renderHome(el, t, new URLSearchParams(m[1] || "").get("follow"))],
  [/^#\/storm\/([^/]+)$/, (m) => (el, t) => renderStorm(el, decodeURIComponent(m[1]), t)],
  [/^#\/ripple\/([^/]+)$/, (m) => (el, t) => renderRipple(el, decodeURIComponent(m[1]), t)],
  [/^#\/try$/, () => renderTry],
  [/^#\/scout$/, () => renderScout],
  [/^#\/scorecard$/, () => renderScorecard],
  [/^#\/ledger$/, () => renderLedger],
  [/^#\/method$/, () => renderMethod],
  [/^#\/agent$/, () => renderAgent],
  [/^#\/artists$/, () => renderArtists],
  [/^#\/artist\/([^/]+)$/, (m) => (el, t) => renderArtist(el, decodeURIComponent(m[1]), t)],
  [/^#\/release(?:\?(.*))?$/, (m) => (el, t) => { const q = new URLSearchParams(m[1] || ""); renderRelease(el, t, Object.fromEntries(["name", "kind", "like", "region", "home", "goal", "run"].map((k) => [k, q.get(k) || ""]))); }],
  [/^#\/about$/, () => renderAbout],
  [/^#\/plan(?:\/([^/]+)\/([^/]+))?$/, (m) => (el, t) => renderPlan(el, t, m[1] && decodeURIComponent(m[1]), m[2] && decodeURIComponent(m[2]))],
];

function route() {
  const hash = location.hash || "#/";
  const my = ++token;
  const isCurrent = () => my === token;
  let view = renderNotFound;
  for (const [re, make] of routes) {
    const m = hash.match(re);
    if (m) { view = make(m); break; }
  }
  document.querySelectorAll("nav [data-nav]").forEach((a) => {
    const key = a.dataset.nav;
    const on = (key === "home" && (hash === "#/" || hash === "#" || hash.startsWith("#/?") || hash.startsWith("#/storm/") || hash.startsWith("#/ripple/"))) || hash === `#/${key}` || (key === "plan" && hash.startsWith("#/plan/")) || (key === "artists" && hash.startsWith("#/artist/")) || (key === "release" && hash.startsWith("#/release"));
    if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
  // The secondary pages live under "More": close it after a pick and mark it when one of them is open.
  const more = document.querySelector(".nav-more");
  if (more) { more.open = false; more.classList.toggle("is-current", !!more.querySelector("[aria-current]")); }
  app.replaceChildren();
  app.classList.remove("route-in");
  void app.offsetWidth;
  app.classList.add("route-in");
  view(app, isCurrent);
  const h1 = app.querySelector("h1");
  if (h1) { h1.tabIndex = -1; h1.focus({ preventScroll: true }); }
  window.scrollTo(0, 0);
}

window.addEventListener("hashchange", route);
window.addEventListener("aftershock:tour", startTour);
document.querySelector('[data-tour="replay"]')?.addEventListener("click", startTour);
// Dark is the default; the choice is kept per browser, and the globe repaints itself on the event.
const themeBtn = document.querySelector(".theme-btn");
const showTheme = () => { const light = document.documentElement.dataset.theme === "light"; themeBtn?.setAttribute("aria-label", light ? "Switch to dark mode" : "Switch to light mode"); };
themeBtn?.addEventListener("click", () => {
  const light = document.documentElement.dataset.theme !== "light";
  if (light) document.documentElement.dataset.theme = "light"; else delete document.documentElement.dataset.theme;
  try { localStorage.setItem("aftershock-theme", light ? "light" : "dark"); } catch { /* storage blocked: the choice lasts this visit */ }
  showTheme();
  window.dispatchEvent(new CustomEvent("aftershock:theme"));
});
showTheme();
route();
mountChat();
startMotion(app);
maybeAutoTour();
