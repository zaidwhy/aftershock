// Motion that carries no new information: bars fill when they scroll into view and sections rise in. Numbers never
// animate: a screenshot or a reader caught mid count-up showed wrong figures, which reads as a contradiction.
// Every effect is added by script and only to what the observer will reveal, so with script off, or with reduced
// motion asked for, the page is simply static and complete.

const REVEAL = "main > section:not(.stage), .rel-sec, .card, .quake li, .flow li, .roadmap li, .storm-list li, .plan-brief";
const FILL = ".qp-bar, .fc-card";
const calm = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

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
  // The node itself counts too: a view can append a bar or a card on its own, after its section is already in.
  for (const sel of [REVEAL, FILL]) {
    if (node.matches(sel)) watch(node);
    node.querySelectorAll(sel).forEach(watch);
  }
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
    }
  }, { rootMargin: "0px 0px -6% 0px", threshold: 0 });
  new MutationObserver((records) => records.forEach((r) => r.addedNodes.forEach(scan))).observe(app, { childList: true, subtree: true });
  scan(app);
}
