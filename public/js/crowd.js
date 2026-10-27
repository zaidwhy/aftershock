// Verdict wording from the age bands each audience leans to. Pure functions, no DOM, so the chip and the
// sentence beside it always come from the same bands (and so a test can run them under node).
const ORDER = ["24_and_younger", "25_to_29", "30_to_34", "35_to_44", "45_to_54", "55_and_older"];
const SHORT = { "24_and_younger": "under 25", "25_to_29": "25-29", "30_to_34": "30-34", "35_to_44": "35-44", "45_to_54": "45-54", "55_and_older": "55+" };

/** Bands in age order, whatever order they arrived in; unknown names dropped. */
export const inAgeOrder = (leans) => ORDER.filter((b) => (leans || []).includes(b));

/** "25-29, 30-34 and 45-54", youngest first. */
export function bandText(leans) {
  const l = inAgeOrder(leans).map((k) => SHORT[k]);
  return l.length < 2 ? l[0] ?? "no clear age group" : `${l.slice(0, -1).join(", ")} and ${l[l.length - 1]}`;
}

/** Same crowd: every artist band is one of the show's. New crowd: no band in common. Otherwise partly new. */
export function crowd(showLeans, artistLeans) {
  const show = inAgeOrder(showLeans), artist = inAgeOrder(artistLeans);
  if (!show.length || !artist.length) return null;
  const shared = artist.filter((b) => show.includes(b)).length;
  if (shared === artist.length) return { label: "Same crowd", cls: "v-same" };
  if (shared === 0) return { label: "New crowd", cls: "v-new" };
  return { label: "Partly new crowd", cls: "v-part" };
}

/** "Kate Bush's listeners skew older" when the artist's oldest (or youngest) band is 2+ bands from the show's. */
export function gapNote(name, showLeans, artistLeans) {
  const show = inAgeOrder(showLeans).map((b) => ORDER.indexOf(b)), artist = inAgeOrder(artistLeans).map((b) => ORDER.indexOf(b));
  if (!show.length || !artist.length) return null;
  const who = /s$/i.test(name) ? `${name}'` : `${name}'s`;
  if (Math.max(...artist) - Math.max(...show) >= 2) return `${who} listeners skew older.`;
  if (Math.min(...show) - Math.min(...artist) >= 2) return `${who} listeners skew younger.`;
  return null;
}
