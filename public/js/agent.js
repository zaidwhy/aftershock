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

// The run log was written in the project's working vocabulary; shown to visitors, it reads in the site's words.
const LOG_WORDS = [[/\btitles that broke out\b/g, "shows that got popular"], [/\bbreakouts?'s\b/g, "show's"], [/\bbreakouts\b/g, "shows"],
  [/\bbreakout\b/g, "show"], [/\blaunch kits\b/g, "launch plans"], [/\btitle-specific\b/g, "specific to their show"],
  [/\bmostly countrywide taste\b/g, "mostly the whole country's taste"], [/\bhotspot places\b/g, "places where fans live"],
  [/\bForecast every other country\b/g, "Predict every other country"], [/\bcountry forecasts\b/g, "country predictions"],
  [/\bforecasts\b/g, "predictions"], [/\bforecast\b/g, "prediction"], [/\bthe public ledger\b/g, "the prediction history"],
  [/\btitles\b/g, "shows"], [/\bcharted\b/g, "reached the Top 10"]];
const plainLog = (text) => LOG_WORDS.reduce((t, [re, w]) => t.replace(re, w), text || "");

export function renderAgent(root, isCurrent) {
  document.title = "The automatic run - AFTERSHOCK";
  const box = h("div", null, loading("the agent's last run"));
  add(root, h("h1", null, "The automatic run"),
    h("p", { class: "pitch" }, "Every Tuesday AFTERSHOCK ran on its own (a GitHub Actions job), with nobody pressing a button: it read Netflix's new Top 10 lists, found the shows getting popular, predicted where they go next and built the launch plans. Those runs are paused until Netflix permits reading its files; this page shows the last one, step by step."),
    box);
  getAgentRun().then((run) => {
    if (!isCurrent()) return;
    box.replaceChildren();
    add(box,
      h("p", { class: "muted mono" }, `Last run: ${time(run.finished)} | Netflix data for the week of ${day(run.netflix_week)}`,
        run.dry_run ? " | a dry run: it did not write to the prediction history" : null),
      h("ol", { class: "agent-steps" }, run.steps.map((s) => h("li", null,
        h("span", { class: "agent-n mono", "aria-label": "Count" }, s.count == null ? "-" : whole(s.count)),
        h("div", null, h("p", { class: "agent-text" }, plainLog(s.text)),
          s.detail ? h("p", { class: "agent-detail" }, plainLog(s.detail)) : null,
          s.not_found?.length ? h("details", { class: "row-details" }, h("summary", null, `Not found in Qloo (${s.not_found.length})`),
            h("p", null, s.not_found.join("; "))) : null)))),
      h("p", { class: "muted" }, "Every prediction is recorded before Netflix publishes the result; ",
        h("a", { href: "#/ledger" }, "see the prediction history"), " or how the predictions did in ", h("a", { href: "#/scorecard" }, "prediction results"), "."));
  }).catch((err) => { if (isCurrent()) box.replaceChildren(errorBox("the agent's last run", err)); });
}
