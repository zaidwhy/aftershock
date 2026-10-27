let cfg = { mock: false, apiBase: "/api", dataBase: "/data", mockBase: "mock" };
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

// Read-only data is exported to static files (scripts/export_static.py), so it needs no function cold start.
// Only the live Qloo calls (/api/ripple, /api/scout) go to the API.
const stat = (name, mockName) => getJson(cfg.mock ? `${cfg.mockBase}/${mockName ?? name}.json` : `${cfg.dataBase}/${name}.json`);
export const getStorms = () => stat("storms");
export const getStorm = (id) => stat(`storms/${encodeURIComponent(id)}`, `storm-${encodeURIComponent(id)}`);
export const getScorecard = () => stat("scorecard");
export const getReplays = () => stat("replays");

export async function scoutShow(show) {
  if (cfg.mock) throw new Error("Sync Scout needs the live API; mock mode has no scout data.");
  return getJson(`${cfg.apiBase}/scout?show=${encodeURIComponent(show)}`);
}

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
