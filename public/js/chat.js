// The floating agent on every page. It sends the question to /api/ask, the same fixed-rule router as before (no
// language model), so every answer comes from a tool result and the steps it took sit one click away.
import { h, add } from "./dom.js";
import { askAgent, getStorms } from "./api.js";
import { answerCard, stepsList, topBreakout } from "./ask.js";
import { failBox } from "./audience.js";

const STARTERS = ["What can you do?", "Why isn't Squid Game here?", "Where should I release a comedy special?", "How does it use Qloo?"];

export function mountChat() {
  const log = h("div", { class: "chat-log", "aria-live": "polite" });
  const input = h("input", { type: "text", maxlength: "200", autocomplete: "off", placeholder: "Ask about a title, a country or a feature", "aria-label": "Your question" });
  const send = h("button", { type: "submit", class: "btn btn-primary" }, "Ask");
  const sugg = h("div", { class: "chat-sugg" });
  const fab = h("button", { type: "button", class: "chat-fab", "aria-expanded": "false", "data-tour": "chat" }, h("span", { class: "dot", "aria-hidden": "true" }), "Ask AFTERSHOCK");
  const panel = h("section", { class: "chat", role: "dialog", "aria-label": "Ask AFTERSHOCK", hidden: true },
    h("header", { class: "chat-head" },
      h("div", null, h("h2", null, "Ask AFTERSHOCK"), h("p", null, "Answers from this week's run and the site's own tools. Every step shown.")),
      h("button", { type: "button", class: "gp-close", "aria-label": "Close chat", onclick: () => toggle(false) }, "×")),
    log, sugg,
    h("form", { class: "chat-form", onsubmit: (e) => { e.preventDefault(); ask(input.value); } }, input, send));

  const say = (who, ...kids) => {
    const m = h("div", { class: `msg msg-${who}` }, ...kids);
    log.append(m);
    log.scrollTop = log.scrollHeight;
    return m;
  };
  const chips = (list) => sugg.replaceChildren(...list.map((q) => h("button", { type: "button", onclick: () => ask(q) }, q)));

  async function ask(text) {
    const q = String(text || "").trim();
    if (!q) { input.focus(); return; }
    input.value = "";
    say("me", q);
    const pending = say("bot", h("p", { class: "muted" }, "Choosing a tool..."));
    send.disabled = true;
    try {
      const res = await askAgent(q);
      pending.replaceChildren();
      add(pending, answerCard(res, ask),
        res.links?.length ? h("div", { class: "msg-links" }, res.links.map((l) => h("a", { href: l.href, onclick: () => { if (matchMedia("(max-width: 700px)").matches) toggle(false); } }, l.label))) : null,
        res.steps?.length ? h("details", null, h("summary", null, `How it answered (${res.steps.length} step${res.steps.length === 1 ? "" : "s"})`), stepsList(res.steps)) : null);
    } catch (err) {
      pending.replaceChildren(failBox(err, "the agent"));
    } finally {
      send.disabled = false;
      log.scrollTop = log.scrollHeight;
    }
  }

  function toggle(open) {
    panel.hidden = !open;
    fab.hidden = open;
    fab.setAttribute("aria-expanded", String(open));
    if (open) input.focus(); else fab.focus();
  }
  fab.addEventListener("click", () => toggle(true));
  panel.addEventListener("keydown", (e) => { if (e.key === "Escape") toggle(false); });
  window.addEventListener("aftershock:chat", (e) => { toggle(true); if (e.detail) ask(e.detail); });

  say("bot", h("p", null, "Hi. Ask me where a breakout goes next, why it is breaking in a country, why a title is missing, or what any part of this site does."));
  chips(STARTERS);
  // The first starter names a title that is really breaking out this week, so it always has an answer.
  getStorms().then((st) => {
    const top = topBreakout(st.storms);
    if (top?.top_forecast) chips([`Why is ${top.title} breaking in ${top.top_forecast.name}?`, ...STARTERS]);
  }).catch(() => {});
  document.body.append(fab, panel);
}
