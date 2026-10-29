// Motion that carries no new information: numbers count up and bars fill when they scroll into view, sections
// rise in. Every effect is added by script and only to what the observer will reveal, so with script off, or with
// reduced motion asked for, the page is simply static and complete.

const COUNT = ".stat-v, .qp-v, .fc-v, .plan-tiles .proof-v, .wh-v";
const REVEAL = "main > section:not(.stage), .rel-sec, .card, .quake li, .storm-list li, .plan-brief";
const NUMBER = /^(\D*)(\d[\d,]*(?:\.\d+)?)(.*)$/;

const calm = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

function countUp(el) {
  const m = el.textContent.trim().match(NUMBER);
  if (!m) return;
  const [, before, raw, after] = m;
  const target = Number(raw.replace(/,/g, ""));
  const decimals = (raw.split(".")[1] || "").length;
  const commas = raw.includes(",");
  const fmt = (v) => {
    const fixed = v.toFixed(decimals);
    return commas ? Number(fixed).toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) : fixed;
  };
  const start = performance.now(), ms = 900;
  const step = (now) => {
    const k = Math.min(1, (now - start) / ms);
    el.textContent = `${before}${fmt(target * (1 - (1 - k) ** 3))}${after}`;
    if (k < 1) requestAnimationFrame(step);
    else el.textContent = `${before}${raw}${after}`;
  };
  requestAnimationFrame(step);
}

const seen = new WeakSet();
let observer = null;

function watch(el) {
  if (seen.has(el)) return;
  seen.add(el);
  if (el.matches(REVEAL)) el.classList.add("reveal");
  observer.observe(el);
}

function scan(node) {
  if (!(node instanceof Element)) return;
  for (const sel of [COUNT, REVEAL]) {
    if (node.matches(sel)) watch(node);
    node.querySelectorAll(sel).forEach(watch);
  }
  node.querySelectorAll(".qp-bar, .fc-card").forEach(watch);
}

/** Watch the app for content as views render it, and animate each piece the first time it is seen. */
export function startMotion(app) {
  if (calm() || !("IntersectionObserver" in window)) return;
  observer = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      const el = e.target;
      observer.unobserve(el);
      el.classList.add("in");
      if (el.matches(COUNT)) countUp(el);
    }
  }, { rootMargin: "0px 0px -6% 0px", threshold: 0 });
  new MutationObserver((records) => records.forEach((r) => r.addedNodes.forEach(scan))).observe(app, { childList: true, subtree: true });
  scan(app);
}
