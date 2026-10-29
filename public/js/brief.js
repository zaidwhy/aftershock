import { pct } from "./format.js";

const fold = (n) => n.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
const LOVES = [["tv_show", "shows: "], ["movie", "films: "], ["brand", "brands: "]];

/** The title-specific picks for one kit country: names that are also on the country's own list are left out. */
export function specificPicks(row, domain) {
  const common = new Set((row.control?.[domain] || []).map(fold));
  return (row.kit?.[domain] || []).map((e) => e.name).filter((n) => !common.has(fold(n)));
}

function countryLine(st, row) {
  const fc = (st.spillover?.forecasts || []).find((f) => f.code === row.code);
  const name = fc?.name ?? row.code;
  const horizon = st.spillover?.horizon_weeks ?? 4;
  const chance = fc ? `${pct(fc.probability)} chance of charting within ${horizon} weeks${fc.why ? ` (${fc.why})` : ""}. ` : "";
  const artists = specificPicks(row, "artist");
  const rest = LOVES.map(([d, lead]) => [lead, specificPicks(row, d)]).filter(([, names]) => names.length)
    .map(([lead, names]) => lead + names.join(", "));
  const loves = artists.length || rest.length
    ? `Audience here loves: ${[artists.length ? artists.join(", ") : "no title-specific artists", ...rest].join("; ")}. `
    : "Nothing in Qloo's picks goes beyond what the whole country already likes. ";
  const places = row.hotspots?.places?.length ? `Start in: ${row.hotspots.places.join(", ")}. ` : "";
  const kind = row.specificity == null ? "" : `Qloo's picks are ${row.generic ? "mostly the whole country's taste" : "specific to this title"}.`;
  return `${name}: ${chance}${loves}${places}${kind}`.trim();
}

/** Plain-text launch brief for a storm, ready to paste into an email or a chat. */
export function launchBrief(st, url, kitRows) {
  const origin = (st.origin_countries || []).map((c) => c.name).join(", ");
  const lock = st.spillover?.locked_at
    ? `Forecast locked ${String(st.spillover.locked_at).slice(0, 10)}, ledger id ${st.spillover.ledger_id}`
    : "Forecast not locked yet";
  return [`${st.title}${st.season ? ` ${st.season}` : ""}: launch brief`,
    `Broke out in ${origin} (week of ${st.origin_week}).`, "",
    ...kitRows.flatMap((r) => [countryLine(st, r), ""]),
    url, lock].join("\n");
}
