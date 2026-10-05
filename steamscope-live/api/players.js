// api/players.js
// A tiny "middleman" (proxy) that runs on Vercel's servers, not in the visitor's browser.
//
// Why it exists: a web page's JavaScript is not allowed to read responses from
// api.steampowered.com, because Steam doesn't send the CORS header that browsers require.
// Server code has no such rule, so this function calls Steam and hands the numbers back
// to the page from YOUR domain, where the browser trusts it.
//
// Usage from the page:  GET /api/players?appids=730,570,578080
// Returns:              { "counts": { "730": 812345, "570": 401234, "578080": null }, "fetchedAt": "..." }
// (null means Steam had no count for that app, e.g. a DLC or a removed game.)

const STEAM_URL = 'https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid=';
const MAX_APPS = 20;           // cap per request, so nobody can use this to hammer Steam
const TIMEOUT_MS = 4000;       // give up on a slow Steam reply after 4 seconds

async function fetchOne(appid) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(STEAM_URL + appid, { signal: controller.signal });
    if (!res.ok) return null;
    const body = await res.json();
    // Steam's reply looks like: { "response": { "player_count": 812345, "result": 1 } }
    // result === 1 means success; anything else means "no count for this app".
    const r = body && body.response;
    return r && r.result === 1 && Number.isFinite(r.player_count) ? r.player_count : null;
  } catch (err) {
    return null;               // network error or timeout: report "unknown", never crash
  } finally {
    clearTimeout(timer);
  }
}

module.exports = async function handler(req, res) {
  // Keep only valid numeric app IDs, drop duplicates, and cap the list.
  const raw = String((req.query && req.query.appids) || '');
  const appids = [...new Set(raw.split(',').map(s => s.trim()).filter(s => /^\d{1,10}$/.test(s)))].slice(0, MAX_APPS);

  if (appids.length === 0) {
    res.status(400).json({ error: 'Pass one or more numeric app IDs, e.g. /api/players?appids=730,570' });
    return;
  }

  // Ask Steam for every app at the same time, instead of one after another.
  const values = await Promise.all(appids.map(fetchOne));
  const counts = {};
  appids.forEach((id, i) => { counts[id] = values[i]; });

  // Let Vercel's CDN reuse this answer for 60 seconds. Steam only updates its numbers
  // about every 5 minutes anyway, so this keeps us fast and polite to Steam's servers.
  res.setHeader('Cache-Control', 's-maxage=60, stale-while-revalidate=120');
  res.status(200).json({ counts, fetchedAt: new Date().toISOString() });
};
