// The AI's names Qloo did not back, in two kinds. "Not placed": Qloo knows the name but does not put it among its picks
// for these viewers here; shown struck through with the reason in words (never colour alone). "No Qloo data yet": Qloo has no
// entity of that name, which is a gap in Qloo's coverage and not a judgement on the name; shown unstruck on its own line.
// Used by the plan page, the storm page and the live check box.
import { h } from "./dom.js";

export const NOT_PLACED_REASON = "not in Qloo's picks for these viewers here";
const SHOWN = 8;
const DOMAIN_WORD = { artist: "artist", tv_show: "TV show", movie: "film", brand: "brand" };

/** {placed: [...], unknown: [...]} from a plan's `rejected` list, ignoring rows without a name. */
export function splitRejected(rejected) {
  const list = (rejected || []).filter((r) => r && r.name);
  return { placed: list.filter((r) => r.verdict !== "not_in_qloo"), unknown: list.filter((r) => r.verdict === "not_in_qloo") };
}

/** Struck-through names (not placed) and, separately, the names Qloo has no data on; at most SHOWN of each, then
 *  "and N more". Nothing when there are none. */
export function rejectedList(rejected) {
  const { placed, unknown } = splitRejected(rejected);
  if (!placed.length && !unknown.length) return null;
  const more = (list) => (list.length > SHOWN ? h("p", { class: "plan-note" }, `and ${list.length - SHOWN} more`) : null);
  return h("div", { class: "rejected" },
    placed.length ? h("div", null,
      h("p", { class: "plan-note mono" }, "Left out, because Qloo's data does not link them to these viewers here:"),
      h("ul", { class: "rejected-list" }, placed.slice(0, SHOWN).map((r) => h("li", null,
        h("s", null, r.name), h("span", { class: "rejected-why" }, ` (${DOMAIN_WORD[r.domain] ?? r.domain}): ${NOT_PLACED_REASON}`)))),
      more(placed)) : null,
    unknown.length ? h("p", { class: "plan-note unknown-line" }, h("span", { class: "mono" }, "No Qloo data yet, so check these yourself: "),
      unknown.slice(0, SHOWN).map((r) => r.name).join(", "), unknown.length > SHOWN ? `, and ${unknown.length - SHOWN} more` : "", ".") : null);
}
