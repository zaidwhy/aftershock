export function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids.flat()) if (k != null && k !== false) el.append(k.nodeType ? k : document.createTextNode(String(k)));
  return el;
}
const NS = "http://www.w3.org/2000/svg";
export function s(tag, attrs, ...kids) {
  const el = document.createElementNS(NS, tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) if (v != null) el.setAttribute(k, v);
  for (const k of kids.flat()) if (k != null) el.append(k.nodeType ? k : document.createTextNode(String(k)));
  return el;
}
export const loading = (what) => h("p", { class: "status", role: "status" }, h("span", { class: "pulse", "aria-hidden": "true" }), `Loading ${what}...`);
export function errorBox(what, err, retry) {
  return h("div", { class: "status status-error", role: "alert" },
    h("p", null, h("strong", null, `Could not load ${what}. `), err.message || String(err)),
    retry ? h("button", { type: "button", class: "btn", onclick: retry }, "Try again") : null);
}
// Element.append writes null as the text "null"; conditional sections pass null when absent.
export function add(parent, ...kids) {
  parent.append(...kids.flat().filter((k) => k != null && k !== false));
}
