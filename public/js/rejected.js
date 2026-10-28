// The AI names Qloo did not back, shown struck through with the reason in words. Used by the plan page and the storm page.
import { h } from "./dom.js";

const REJECT_REASON = { not_placed: "Qloo does not link it to these viewers here", not_in_qloo: "Qloo does not know it" };
const REJECT_SHOWN = 8;
const DOMAIN_WORD = { artist: "artist", tv_show: "TV show", movie: "film", brand: "brand" };

/** The AI's names that Qloo did not back, struck through with the reason in words (never colour alone): at most
 *  REJECT_SHOWN, then "and N more". Nothing when there are none. */
export function rejectedList(rejected) {
  const list = (rejected || []).filter((r) => r && r.name);
  if (!list.length) return null;
  const more = list.length - REJECT_SHOWN;
  return h("div", { class: "rejected" },
    h("p", { class: "plan-note mono" }, "Not used, because Qloo could not back them:"),
    h("ul", { class: "rejected-list" }, list.slice(0, REJECT_SHOWN).map((r) => h("li", null,
      h("s", null, r.name), h("span", { class: "rejected-why" }, ` (${DOMAIN_WORD[r.domain] ?? r.domain}): ${REJECT_REASON[r.verdict] ?? "Qloo could not back it"}`)))),
    more > 0 ? h("p", { class: "plan-note" }, `and ${more} more`) : null);
}
