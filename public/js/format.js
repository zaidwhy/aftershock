const ORDINAL = ["", "", "second ", "third ", "fourth ", "fifth "];
/** "Most likely next country", "Second most likely next country", ... "Number 7 of 15": a chance means little without its rank. */
export const rankLabel = (rank, of) => (rank >= 1 && rank <= 5 ? `${ORDINAL[rank]}most likely next country`.replace(/^./, (c) => c.toUpperCase()) : `Number ${rank} of ${of} likely next countries`);
export const pct = (p) => (p == null ? "n/a" : p > 0 && p < 0.005 ? "<1%" : `${Math.round(p * 100)}%`);
export const num2 = (n) => (n == null ? "n/a" : (n >= 0 ? "+" : "-") + Math.abs(n).toFixed(2));
export const plain2 = (n) => (n == null ? "n/a" : n.toFixed(2));
export function views(n) {
  if (n == null) return "n/a";
  if (n >= 1e6) return `${(n / 1e6).toFixed(n >= 1e7 ? 0 : 1).replace(/\.0$/, "")}M`;
  if (n >= 1e3) return `${Math.round(n / 1e3)}k`;
  return String(n);
}
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const monthLabel = (ym) => { const [y, m] = ym.split("-"); return `${MONTHS[+m - 1]} ${y}`; };
export const dateLabel = (iso) => {
  if (!iso) return "n/a";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toISOString().slice(0, 16).replace("T", " ") + " UTC";
};
export const BANDS = [
  ["24_and_younger", "24-", "24 and younger"], ["25_to_29", "25-29", "25 to 29"], ["30_to_34", "30-34", "30 to 34"],
  ["35_to_44", "35-44", "35 to 44"], ["45_to_54", "45-54", "45 to 54"], ["55_and_older", "55+", "55 and older"],
];

/** The forecast's reason in plain words: "Norway joined 12 of 67 past breakouts that started in Denmark" reads
 *  "12 of 67 shows popular first in Denmark later reached Norway's Top 10 too". Unknown shapes pass through. */
export const plainWhy = (why) => {
  const m = /^(.+?) joined (\d+) of (\d+) past breakouts that started in (.+)$/.exec(why || "");
  return m ? `${m[2]} of ${m[3]} shows popular first in ${m[4]} later reached ${m[1]}'s Top 10 too` : why || "";
};
