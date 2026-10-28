// "Try it": one typed name checked by Qloo now, the same check the weekly run applies to every AI-proposed name
// (aftershock/grounded_plan.py check_name, GET /api/check). Everything else on the page is precomputed and keeps working
// when this call fails.
import { h } from "./dom.js";
import { checkName } from "./api.js";
import { NOT_PLACED_REASON } from "./rejected.js";

const DOMAINS = [["artist", "Artist"], ["brand", "Brand"], ["tv_show", "TV show"], ["movie", "Film"]];
const WORD = Object.fromEntries(DOMAINS.map(([k, v]) => [k, v.toLowerCase()]));

/** The verdict for a checked name, in plain words and not by colour alone. */
export function verdictNode(res, domain, title, country) {
  const name = res.name;
  if (res.verdict === "confirmed") {
    return h("p", { class: "check-out check-yes" }, h("strong", null, "Confirmed by Qloo: "), h("span", { class: "check-name" }, name),
      ` (${WORD[domain]}) is linked to the audience of ${title} in ${country}.`);
  }
  if (res.verdict === "not_placed") {
    return h("p", { class: "check-out check-no" }, h("s", null, name), ` (${WORD[domain]}): ${NOT_PLACED_REASON}. Qloo knows it, but does not put it among its picks for this audience.`);
  }
  return h("p", { class: "check-out check-unknown" }, h("span", { class: "mono" }, "No Qloo data yet (check locally): "), h("span", { class: "check-name" }, name),
    `. Qloo has no ${WORD[domain]} with exactly this name, which is a gap in its coverage and not a verdict on the name.`);
}

export function checkBox(storm, code, title, country) {
  const input = h("input", { type: "text", id: "check-name", maxlength: "80", autocomplete: "off", spellcheck: "false" });
  const domain = h("select", { id: "check-domain", class: "wm-select" }, DOMAINS.map(([k, v]) => h("option", { value: k }, v)));
  const out = h("div", { class: "check-result", "aria-live": "polite" });
  const go = h("button", { type: "submit", class: "btn btn-small" }, "Check with Qloo");
  const run = () => {
    const name = input.value.trim().replace(/\s+/g, " ");
    if (!name) { out.replaceChildren(h("p", { class: "status status-error" }, "Type a name first.")); input.focus(); return; }
    go.disabled = true;
    out.replaceChildren(h("p", { class: "status", role: "status" }, "Asking Qloo..."));
    checkName(storm, code, domain.value, name).then((res) => out.replaceChildren(verdictNode(res, domain.value, title, country)))
      .catch((err) => out.replaceChildren(h("p", { class: "status status-error" }, err.message || "Qloo could not be reached just now. The rest of this page still works.")))
      .finally(() => { go.disabled = false; });
  };
  return h("li", { class: "plan-step plan-check" },
    h("p", { class: "plan-step-n mono" }, "Live: this asks Qloo now"),
    h("h3", null, "Try it: type an artist, brand, show or film"),
    h("p", { class: "plan-found" }, `Qloo checks it against the audience of ${title} in ${country}, the same check the agent ran on every AI name above.`),
    h("form", { class: "lookup-form check-form", novalidate: true, onsubmit: (e) => { e.preventDefault(); run(); } },
      h("div", { class: "field" }, h("label", { for: "check-name" }, "Name"), input),
      h("div", { class: "field" }, h("label", { for: "check-domain" }, "Kind"), domain),
      go),
    out);
}
