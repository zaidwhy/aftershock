let cfg = { mock: false, apiBase: "/api", mockBase: "mock" };
export const setConfig = (c) => { cfg = c; };
export const isMock = () => cfg.mock;

async function getJson(url) {
  let res;
  try { res = await fetch(url, { headers: { Accept: "application/json" } }); }
  catch { throw new Error(`Could not reach ${url}. Check your connection and try again.`); }
  if (res.status === 429) throw new Error("Rate limit reached (10 live scorings per hour per visitor, 300 per day overall). Try again later.");
  if (!res.ok) {
    let detail = "";
    try { const j = await res.json(); detail = j.detail || j.error || ""; } catch { /* body not JSON */ }
    throw new Error(`${url} returned HTTP ${res.status}${detail ? ": " + detail : ""}`);
  }
  try { return await res.json(); } catch { throw new Error(`${url} sent a response that was not JSON.`); }
}

export const getStorms = () => getJson(cfg.mock ? `${cfg.mockBase}/storms.json` : `${cfg.apiBase}/storms`);
export const getStorm = (id) => getJson(cfg.mock ? `${cfg.mockBase}/storm-${encodeURIComponent(id)}.json` : `${cfg.apiBase}/storms/${encodeURIComponent(id)}`);
export const getScorecard = () => getJson(cfg.mock ? `${cfg.mockBase}/scorecard.json` : `${cfg.apiBase}/scorecard`);
export const getRipples = () => getJson(cfg.mock ? `${cfg.mockBase}/ripples.json` : `${cfg.apiBase}/ripples`);
export const getRipple = (id) => getJson(cfg.mock ? `${cfg.mockBase}/ripple-${encodeURIComponent(id)}.json` : `${cfg.apiBase}/ripples/${encodeURIComponent(id)}`);
export const getReplays = () => getJson(cfg.mock ? `${cfg.mockBase}/replays.json` : `${cfg.apiBase}/replays`);

export async function scoreSongs(show, songs, asOf) {
  if (cfg.mock) {
    const r = await getJson(`${cfg.mockBase}/ripple.json`);
    // Mock mode: match typed songs against the three canned songs, flag the rest unresolved.
    const norm = (s) => s.trim().toLowerCase();
    const canned = new Map(r.songs.map((s) => [norm(s.song), s]));
    const out = songs.map(({ song, artist }) => canned.get(norm(song)) || { song, artist, resolved: false });
    return { show_age: r.show_age, songs: out, resolved: true };
  }
  const q = songs.map((s) => `${s.song}|${s.artist}`).join(";");
  const when = asOf ? `&as_of=${encodeURIComponent(asOf)}` : "";
  return getJson(`${cfg.apiBase}/ripple?show=${encodeURIComponent(show)}&songs=${encodeURIComponent(q)}${when}`);
}
