// "Plan a launch": the agent's steps for one title in one country appear one by one, then the Launch Brief.
// The steps and the brief are built by aftershock/launch_brief.py and ride on each launch_kit row as `brief`.
import { h, loading, errorBox, add } from "./dom.js";
import { getStorms, getStorm } from "./api.js";

const STEP_MS = 450;
const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const planHref = (id, code) => `#/plan/${encodeURIComponent(id)}/${encodeURIComponent(code)}`;
const kitRows = (st) => (st.launch_kit || []).filter((r) => r.brief);

/** The week's top storm that has a launch kit, and its first kit country: {id, title, code, country}, or null. */
export async function defaultPlan() {
  const { storms } = await getStorms();
  const ranked = storms.filter((s) => s.has_kit).sort((a, b) => (b.top_forecast?.probability ?? -1) - (a.top_forecast?.probability ?? -1));
  for (const s of ranked.slice(0, 3)) {
    const row = kitRows(await getStorm(s.id))[0];
    if (row) return { id: s.id, title: s.title, code: row.code, country: row.brief.brief.country };
  }
  return null;
}

/** Plain-text-to-Markdown for the downloaded file, built from the brief alone. */
export function briefMarkdown(b, url) {
  const list = (items) => items.map((x) => `- ${x}`);
  const partners = b.partners.flatMap((g) => [`**${g.label}**`, ...list(g.picks.map((p) =>
    p.name + (p.source === "ai_confirmed" ? (p.also_in_qloo_kit ? " (AI pick confirmed by Qloo; also in Qloo's kit)" : " (AI pick confirmed by Qloo)") : " (Qloo's kit)"))), ""]);
  return [`# Launch brief: ${b.title} in ${b.country}`, "", b.headline, "",
    `## Summary`, b.summary, `*${b.summary_source === "template" ? "Template summary" : "Written by AI, every name checked against Qloo"}.*`, "",
    "## Where to start", ...(b.cities.length ? list(b.cities) : ["Qloo returned no named places for this country."]), "",
    "## Partners to approach", ...partners,
    "## What not to claim", ...list(b.avoid), "",
    "## Evidence", ...list(b.evidence), "", url ? `Source: ${url}` : ""].join("\n");
}

function stepCard(s, n) {
  return h("li", { class: "plan-step" },
    h("p", { class: "plan-step-n mono" }, `Step ${n}`),
    h("h3", null, s.title),
    h("p", { class: "plan-found" }, s.found),
    s.decision ? h("p", { class: "plan-decision" }, h("span", { class: "plan-rule mono" }, "Rule applied"), " ", s.decision) : null);
}

function briefCard(st, made) {
  const b = made.brief;
  const note = b.summary_source === "template" ? "Template summary, no AI wrote it." : "Written by AI, every name checked against Qloo.";
  return h("article", { class: "plan-brief", "aria-labelledby": "brief-h" },
    h("p", { class: "eyebrow" }, "Deliverable"),
    h("h2", { id: "brief-h" }, `Launch brief: ${b.title} in ${b.country}`),
    h("p", { class: "plan-headline" }, b.headline),
    h("section", { "aria-labelledby": "bs-sum" },
      h("h3", { id: "bs-sum" }, "Summary"), h("p", null, b.summary), h("p", { class: "plan-note mono" }, note)),
    h("section", { "aria-labelledby": "bs-cities" },
      h("h3", { id: "bs-cities" }, "Where to start"),
      b.cities.length ? h("ul", null, b.cities.map((c) => h("li", null, c))) : h("p", null, "Qloo returned no named places for this country.")),
    h("section", { "aria-labelledby": "bs-partners" },
      h("h3", { id: "bs-partners" }, "Partners to approach"),
      h("p", { class: "plan-note mono" }, b.partner_basis === "ai_confirmed" ? "AI picks that Qloo confirmed come first." : "Qloo's own kit for this title and country."),
      h("dl", { class: "plan-partners" }, b.partners.map((g) => h("div", null,
        h("dt", null, g.label),
        h("dd", null, g.picks.flatMap((p, i) => [i ? ", " : null, p.name,
          p.source === "ai_confirmed" && p.also_in_qloo_kit ? h("span", { class: "plan-both" }, " (also in Qloo's kit)") : null])))))),
    h("section", { "aria-labelledby": "bs-avoid" },
      h("h3", { id: "bs-avoid" }, "What not to claim"), h("ul", null, b.avoid.map((a) => h("li", null, a)))),
    h("section", { "aria-labelledby": "bs-evidence" },
      h("h3", { id: "bs-evidence" }, "Evidence"), h("ul", null, b.evidence.map((a) => h("li", null, a)))),
    h("p", { class: "plan-note" }, "Forecast locked in the public ", h("a", { href: "#/ledger" }, "ledger"), " before the outcome exists. ",
      h("a", { href: `#/storm/${encodeURIComponent(st.id)}` }, "Full forecast for this title"), "."));
}

function controls(st, made) {
  const status = h("span", { class: "muted", role: "status" });
  const flash = (msg) => { status.textContent = msg; setTimeout(() => { status.textContent = ""; }, 2500); };
  const copy = h("button", { type: "button", class: "btn btn-small" }, "Copy link");
  copy.addEventListener("click", () => {
    if (!navigator.clipboard?.writeText) return flash("Copy blocked; use the address bar.");
    navigator.clipboard.writeText(location.href).then(() => flash("Link copied"), () => flash("Copy blocked; use the address bar."));
  });
  const download = h("button", { type: "button", class: "btn btn-small" }, "Download brief");
  download.addEventListener("click", () => {
    const b = made.brief;
    const url = URL.createObjectURL(new Blob([briefMarkdown(b, location.href)], { type: "text/markdown;charset=utf-8" }));
    const a = h("a", { href: url, download: `launch-brief-${st.id}-${b.code}.md`.toLowerCase(), hidden: true });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    flash("Downloaded");
  });
  const print = h("button", { type: "button", class: "btn btn-small", onclick: () => window.print() }, "Print");
  return h("div", { class: "plan-actions no-print" }, copy, download, print, status);
}

function pickers(storms, st, code) {
  const rows = st ? kitRows(st) : [];
  const title = h("select", { id: "plan-title", class: "wm-select" }, storms.map((s) =>
    h("option", { value: s.id, selected: st && s.id === st.id }, s.title + (s.season ? ` ${s.season}` : ""))));
  const country = h("select", { id: "plan-country", class: "wm-select", disabled: !rows.length }, rows.map((r) =>
    h("option", { value: r.code, selected: r.code === code }, r.brief.brief.country)));
  title.addEventListener("change", () => {
    country.disabled = true;
    getStorm(title.value).then((next) => {
      const first = kitRows(next)[0];
      if (first) location.hash = planHref(next.id, first.code);
    }).catch(() => { country.disabled = false; });
  });
  country.addEventListener("change", () => { location.hash = planHref(st.id, country.value); });
  return h("div", { class: "plan-pick no-print" },
    h("div", { class: "field" }, h("label", { for: "plan-title" }, "Title"), title),
    h("div", { class: "field" }, h("label", { for: "plan-country" }, "Country"), country));
}

export function renderPlan(root, isCurrent, id, code) {
  document.title = "Plan a launch - AFTERSHOCK";
  const body = h("div", null, loading("this week's titles"));
  add(root,
    h("div", { class: "no-print" },
      h("h1", null, "Plan a launch"),
      h("p", { class: "pitch" }, "Pick a breakout title and a country. The agent shows each step it takes, from the forecast to Qloo's taste data, and ends with a brief you can hand to a local partner.")),
    body);
  const fail = (err) => { if (isCurrent()) body.replaceChildren(errorBox("the launch planner", err)); };

  if (!id) {
    defaultPlan().then((d) => {
      if (!isCurrent()) return;
      if (d) location.replace(planHref(d.id, d.code));
      else body.replaceChildren(h("p", { class: "status" }, "No title has a Qloo launch kit this week."));
    }).catch(fail);
    return;
  }

  Promise.all([getStorms(), getStorm(id)]).then(([{ storms }, st]) => {
    if (!isCurrent()) return;
    const options = storms.filter((s) => s.has_kit);
    if (!options.some((s) => s.id === st.id)) options.unshift({ id: st.id, title: st.title, season: st.season });
    const row = kitRows(st).find((r) => r.code.toLowerCase() === code.toLowerCase());
    body.replaceChildren(pickers(options, st, row?.code));
    if (!row) {
      add(body, h("p", { class: "status status-error", role: "alert" },
        `No launch kit for ${code} on ${st.title}. Pick one of its kit countries above.`));
      return;
    }
    const made = row.brief;
    const region = h("div", { class: "plan-steps-region", "aria-live": "polite", "aria-label": "The agent's steps" });
    const list = h("ol", { class: "plan-steps no-print" });
    region.append(list);
    add(body, h("h2", { class: "plan-run-h no-print" }, `The agent's steps: ${st.title} in ${row.brief.brief.country}`), region);
    const finish = () => {
      if (!isCurrent()) return;
      add(body, briefCard(st, made), controls(st, made));
    };
    let shown = 0;
    const next = () => {
      if (!isCurrent()) return;
      list.append(stepCard(made.steps[shown], shown + 1));
      shown += 1;
      if (shown < made.steps.length) setTimeout(next, STEP_MS); else finish();
    };
    if (reduced()) {
      made.steps.forEach((s, i) => list.append(stepCard(s, i + 1)));
      finish();
    } else next();
  }).catch((err) => {
    if (!isCurrent()) return;
    if (err.status === 404) body.replaceChildren(h("p", { class: "status status-error", role: "alert" }, err.message),
      h("p", null, h("a", { href: "#/plan" }, "Plan a different launch")));
    else fail(err);
  });
}
