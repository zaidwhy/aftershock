// "What the agent did": the last weekly run as a plain-language timeline, from /data/agent_run.json
// (written by scripts/run_forecasts.py, exported by scripts/export_static.py).
import { h, loading, errorBox, add } from "./dom.js";
import { getAgentRun } from "./api.js";

const whole = (n) => n.toLocaleString("en-US");
const day = (iso) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const time = (iso) => new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC" }) + " UTC";

/** One line for the home page under the proof row; stays hidden when there is no log. */
export function agentLine(box, isCurrent) {
  getAgentRun().then((run) => {
    if (!isCurrent() || !run?.summary) return;
    const s = run.summary;
    box.append(`Last updated ${day(run.finished)} by our automatic weekly run: ${whole(s.breakouts)} trending shows, ${whole(s.launch_kits)} launch plans. `,
      h("a", { href: "#/agent" }, "See what it did"), ".");
    box.hidden = false;
  }).catch(() => {});
}

export function renderAgent(root, isCurrent) {
  document.title = "What the agent did - AFTERSHOCK";
  const box = h("div", null, loading("the agent's last run"));
  add(root, h("h1", null, "What the agent did this week"),
    h("p", { class: "pitch" }, "AFTERSHOCK ran on its own every Tuesday (a GitHub Actions job) with nobody pressing a button. Those runs are paused until Netflix permits reading its files; this page shows the last one, step by step, with what each step found."),
    box);
  getAgentRun().then((run) => {
    if (!isCurrent()) return;
    box.replaceChildren();
    add(box,
      h("p", { class: "muted mono" }, `Last run: ${time(run.finished)} | Netflix data for the week of ${day(run.netflix_week)}`,
        run.dry_run ? " | a dry run: it did not write to the ledger" : null),
      h("ol", { class: "agent-steps" }, run.steps.map((s) => h("li", null,
        h("span", { class: "agent-n mono", "aria-label": "Count" }, s.count == null ? "-" : whole(s.count)),
        h("div", null, h("p", { class: "agent-text" }, s.text),
          s.detail ? h("p", { class: "agent-detail" }, s.detail) : null,
          s.not_found?.length ? h("details", { class: "row-details" }, h("summary", null, `Not found in Qloo (${s.not_found.length})`),
            h("p", null, s.not_found.join("; "))) : null)))),
      h("p", { class: "muted" }, "Every forecast is locked in the public ledger before Netflix publishes the week it is graded on; ",
        h("a", { href: "#/ledger" }, "open the ledger"), " or see how past forecasts scored on the ", h("a", { href: "#/scorecard" }, "scorecard"), "."));
  }).catch((err) => { if (isCurrent()) box.replaceChildren(errorBox("the agent's last run", err)); });
}
