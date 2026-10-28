let cfg = { mock: false, apiBase: "/api", dataBase: "/data", mockBase: "mock" };
export const setConfig = (c) => { cfg = c; };
export const isMock = () => cfg.mock;

async function getJson(url) {
  let res;
  try { res = await fetch(url, { headers: { Accept: "application/json" } }); }
  catch { throw new Error(`Could not reach ${url}. Check your connection and try again.`); }
  if (res.status === 429) {
    let detail = "";
    try { detail = (await res.json()).detail || ""; } catch { /* body not JSON */ }
    throw Object.assign(new Error("Rate limit reached. Try again later."), { status: 429, detail });
  }
  if (!res.ok) {
    let detail = "";
    try { const j = await res.json(); detail = j.detail || j.error || ""; } catch { /* body not JSON */ }
    // Our own errors are written as sentences for visitors; show those alone. Anything else (a
    // validation list, an HTML error page) keeps the technical form so it can still be reported.
    if (typeof detail === "string" && detail) throw Object.assign(new Error(detail), { status: res.status });
    throw Object.assign(new Error(`${url} returned HTTP ${res.status}`), { status: res.status });
  }
  try { return await res.json(); } catch { throw new Error(`${url} sent a response that was not JSON.`); }
}

// Read-only data is exported to static files (scripts/export_static.py), so it needs no function cold start.
// Only the live Qloo calls (/api/ripple, /api/scout) go to the API.
const stat = (name, mockName) => getJson(cfg.mock ? `${cfg.mockBase}/${mockName ?? name}.json` : `${cfg.dataBase}/${name}.json`);
export const getStorms = () => stat("storms");
export const getStorm = (id) => stat(`storms/${encodeURIComponent(id)}`, `storm-${encodeURIComponent(id)}`);
export const getArtists = () => stat("artists");
export const getArtist = (slug) => stat(`artists/${encodeURIComponent(slug)}`);
export const getScorecard = () => stat("scorecard");
export const getReplays = () => stat("replays");
export const getLedger = () => stat("ledger");
export const getAgentRun = () => (cfg.mock ? Promise.reject(new Error("The agent log is not part of the mock data.")) : stat("agent_run"));

/** A plain question for the keyword agent (aftershock/ask.py). Song and artist questions use a live Qloo slot. */
export async function askAgent(question) {
  if (cfg.mock) throw new Error("Ask the agent needs the live API; mock mode has no agent.");
  return getJson(`${cfg.apiBase}/ask?q=${encodeURIComponent(question.slice(0, 200))}`);
}

/** One typed name checked live by Qloo for a title's audience in a launch-kit country (GET /api/check). */
export async function checkName(storm, country, domain, name) {
  if (cfg.mock) throw new Error("The live check needs the live API; mock mode has none.");
  return getJson(`${cfg.apiBase}/check?storm=${encodeURIComponent(storm)}&country=${encodeURIComponent(country)}&domain=${encodeURIComponent(domain)}&name=${encodeURIComponent(name.slice(0, 80))}`);
}

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
    // Derive band names like the API does: the bands each audience over-indexes on, strongest first.
    const leans = (age) => (age ? Object.keys(age).filter((b) => age[b] > 0).sort((a, b) => age[b] - age[a]) : undefined);
    const clean = out.map(({ fit, artist_age, ...rest }) => ({ ...rest, leans: leans(artist_age) }));
    return { show_leans: leans(r.show_age), songs: clean, resolved: true };
  }
  const q = songs.map((s) => `${s.song}|${s.artist}`).join(";");
  const when = asOf ? `&as_of=${encodeURIComponent(asOf)}` : "";
  return getJson(`${cfg.apiBase}/ripple?show=${encodeURIComponent(show)}&songs=${encodeURIComponent(q)}${when}`);
}

/** Netflix history for a typed title: the record, or null when Netflix's Top 10 never listed it (404). */
export async function lookupTitle(name) {
  if (cfg.mock) return null;
  let res;
  try { res = await fetch(`${cfg.apiBase}/title?name=${encodeURIComponent(name.slice(0, 80))}`, { headers: { Accept: "application/json" } }); }
  catch { throw new Error("Could not reach the title lookup. Check your connection and try again."); }
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`The title lookup returned HTTP ${res.status}.`);
  return res.json();
}
