/**
 * PLUG-X API -> M3U worker for OTT Navigator / TiViMate.
 *
 * The PlugX API (POST .../api.php, action=login) returns one big JSON catalog
 * with no per-playlist export URL. This worker logs in on demand, caches the
 * catalog for the API's own refresh cadence (240 s), and serves:
 *
 *   /                  HTML/JSON index of all 17 playlists + URLs
 *   /all.m3u           master playlist, every channel grouped by its playlist
 *   /<slug>.m3u        one playlist (e.g. /jiostb.m3u, /jiohotstar.m3u)
 *   /p/<id>.m3u        one playlist by numeric id (e.g. /p/8.m3u)
 *   /health            catalog state (source, counts, cache age)
 *
 * Only the API call happens on Cloudflare egress. The emitted M3U contains
 * DIRECT stream URLs + header/DRM directives, so the player fetches the media
 * from the client's own (residential) IP -- no datacenter CDN block.
 */
const API = "https://plugxaura.app/Plugxlive/api.php";
const UA = "Premium Plugx"; // required by the API; without it -> 403
const CACHE_KEY = "https://plugx-api.internal/catalog";
const TTL = 210; // seconds; API refresh_seconds=240, refresh a bit earlier

const EPG = "https://raw.githubusercontent.com/gramnaters/iptv-hub/refs/heads/main/epg.xml.gz";

function creds(env) {
  return {
    action: "login",
    name: env.PLUGX_NAME || "PLUGX",
    username: env.PLUGX_USER || "PLUGX",
    password: env.PLUGX_PASS || "PLUGX2211",
    device_id: env.PLUGX_DEVID || "0a0f3889-8839-4845-8cb3-044b44b17889",
    device_name: "PlugX-Worker",
    version_code: 16,
  };
}

let mem = { data: null, ts: 0 };

async function getCatalog(env) {
  const now = Date.now();
  // 1) in-isolate memory
  if (mem.data && now - mem.ts < TTL * 1000) return { data: mem.data, age: Math.floor((now - mem.ts) / 1000), src: "memory" };
  // 2) Cache API (shared across isolates)
  try {
    const cached = await caches.default.match(CACHE_KEY);
    if (cached) {
      const j = await cached.json();
      mem = { data: j, ts: now };
      return { data: j, age: Math.floor((now - mem.ts) / 1000), src: "cache" };
    }
  } catch { /* ignore */ }
  // 3) fresh login
  const r = await fetch(API, {
    method: "POST",
    headers: { "Content-Type": "application/json", "User-Agent": UA },
    body: JSON.stringify(creds(env)),
  });
  if (!r.ok) throw new Error(`PlugX API HTTP ${r.status}`);
  const j = await r.json();
  if (!j.ok) throw new Error(`PlugX login failed: ${j.error || "unknown"}`);
  mem = { data: j.data, ts: now };
  try {
    await caches.default.put(CACHE_KEY, new Response(JSON.stringify(j.data), {
      headers: { "cache-control": `max-age=${TTL}` },
    }));
  } catch { /* ignore */ }
  return { data: j.data, age: 0, src: "api" };
}

const slug = s => String(s || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "playlist";
const xml = s => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

function emitChannel(out, c, group) {
  const raw = String(c.stream_url || "").trim();
  if (!raw) return;
  const h = c.headers || {};
  let cookie = String(h.cookie || h.Cookie || "").trim();
  const name = String(c.name || "Channel").replace(/[\r\n]+/g, " ").replace(/"/g, "'");
  const logo = String(c.logo || "").replace(/[\r\n]+/g, " ").replace(/"/g, "'");
  out.push(`#EXTINF:-1 tvg-id="${c.id || ""}" tvg-name="${xml(name)}" tvg-logo="${xml(logo)}" group-title="${xml(group)}",${xml(name)}`);

  // Some rows append "?|cookie=<token>&referer=...&user-agent=..." to the URL.
  // That separator is not a real query param; auth goes in headers instead.
  const hadPipe = raw.includes("|cookie=");
  let url = raw.split("|cookie=")[0].replace(/[?&]+$/, "");
  const isDash = /\.mpd(\?|$)/i.test(url) || ["mpd", "dash"].includes(String(c.manifest_type || "").toLowerCase());
  const ua = String(h["user-agent"] || h["User-Agent"] || UA).trim() || UA;

  if (isDash) {
    out.push("#KODIPROP:inputstream=inputstream.adaptive");
    out.push("#KODIPROP:inputstream.adaptive.manifest_type=mpd");
    let sh = `User-Agent=${ua}`;
    if (cookie) sh += `&Cookie=${cookie}`;
    if (h.Referer || h.referer) sh += `&Referer=${h.Referer || h.referer}`;
    out.push(`#KODIPROP:inputstream.adaptive.stream_headers=${sh}`);
    if (String(c.license_type || "").toLowerCase() === "clearkey" && c.license_key) {
      out.push("#KODIPROP:inputstream.adaptive.license_type=clearkey");
      out.push(`#KODIPROP:inputstream.adaptive.license_key=${c.license_key}`);
    }
  }

  if (cookie) {
    if (hadPipe) {
      // Header-only auth (Hotstar): EXTVLCOPT + EXTHTTP, URL stays clean.
      out.push(`#EXTVLCOPT:http-user-agent=${ua}`);
      out.push(`#EXTVLCOPT:http-cookie=${cookie}`);
      if (h.Referer || h.referer) out.push(`#EXTVLCOPT:http-referrer=${h.Referer || h.referer}`);
      out.push(`#EXTHTTP:${JSON.stringify({ ...h, Cookie: cookie, "User-Agent": ua }).replace(/[\r\n]+/g, " ")}`);
    } else {
      // Jio & most others accept the token as a query param -- most portable.
      url += (url.includes("?") ? "&" : "?") + cookie.replace(/^\?/, "");
      out.push(`#EXTVLCOPT:http-user-agent=${ua}`);
    }
  } else if (ua) {
    out.push(`#EXTVLCOPT:http-user-agent=${ua}`);
  }
  out.push(url);
}

// Normalise a category label to the clean name the app shows.
function cleanGroup(name, source) {
  let g = String(name || "").trim().replace(/\s+/g, " ");
  if (!g || /^(other|others|unknown|unspecified)$/i.test(g)) g = "Other";
  // "Dangal Play | Dangal Play" / "WOW KIDZ" inside its own source -> just the source label
  if (source && g.toLowerCase() === source.toLowerCase()) g = source;
  return g;
}
const num = v => { const n = Number(v); return Number.isFinite(n) ? n : 1e9; };

function buildM3U(data, filterId, origin) {
  const cats = new Map((data.categories || []).map(c => [c.id, c]));
  const pls = new Map((data.playlists || []).map(p => [p.id, p]));
  const out = [`#EXTM3U x-tvg-url="${EPG}" url-tvg="${EPG}" refresh="300" plugx-worker="plugx-api"`];
  const now = Math.floor(Date.now() / 1000);

  // Arrange exactly like the app: source playlists -> their categories (by
  // sort_order) -> channels (by channel_number). Groups are contiguous and
  // cleanly named, so OTT Navigator shows them in the same order as the app.
  const playlists = [...pls.values()]
    .filter(p => filterId == null ? p.id !== 16 : p.id === filterId) // Opplex opt-in only
    .sort((a, b) => num(a.sort_order) - num(b.sort_order) || num(a.id) - num(b.id));

  let n = 0;
  for (const p of playlists) {
    const source = p.name;
    const channels = (data.channels || []).filter(c => c.playlist_id === p.id);
    // filter expired + bucket by category
    const buckets = new Map();
    for (const c of channels) {
      const exp = /(?:exp|Expires)[=%3D]*(\d{10})/i.exec(c.stream_url || "") ||
                  /(?:exp|Expires)[=%3D]*(\d{10})/i.exec(JSON.stringify(c.headers || {}));
      if (exp && Number(exp[1]) <= now) continue;
      const cid = c.category_id;
      if (!buckets.has(cid)) buckets.set(cid, []);
      buckets.get(cid).push(c);
    }
    const orderedCats = [...buckets.entries()].sort((a, b) =>
      num((cats.get(a[0]) || {}).sort_order) - num((cats.get(b[0]) || {}).sort_order) ||
      String((cats.get(a[0]) || {}).name).localeCompare(String((cats.get(b[0]) || {}).name)));

    for (const [cid, chans] of orderedCats) {
      const catName = cleanGroup((cats.get(cid) || {}).name, source);
      // Individual playlist -> bare category name (app style). Master -> source
      // prefix, except when the category IS the source (avoid "X | X").
      const group = filterId == null
        ? (catName === source ? source : `${source} | ${catName}`)
        : catName;
      chans.sort((a, b) => num(a.channel_number) - num(b.channel_number) || String(a.name).localeCompare(String(b.name)));
      for (const c of chans) { emitChannel(out, c, group); n++; }
    }
  }
  return { body: out.join("\n") + "\n", count: n };
}

const json = (o, s = 200) => new Response(JSON.stringify(o, null, 2), { status: s, headers: { "content-type": "application/json; charset=utf-8", "access-control-allow-origin": "*" } });
const html = (s, st = 200) => new Response(s, { status: st, headers: { "content-type": "text/html; charset=utf-8", "access-control-allow-origin": "*" } });

function indexPage(data, origin, age, src) {
  const rows = (data.playlists || []).map(p => `<li><a href="${origin}/${slug(p.name)}.m3u">${p.name}</a> <small>(/p/${p.id}.m3u)</small></li>`).join("");
  return html(`<!doctype html><meta charset="utf-8"><title>PLUG-X API</title>
<h1>PLUG-X API -> M3U</h1>
<p>Catalog: <b>${(data.channels || []).length}</b> channels / <b>${(data.playlists || []).length}</b> playlists
 | cache age <b>${age}s</b> via <b>${src}</b></p>
<ul>
<li><a href="${origin}/all.m3u">ALL channels (master)</a></li>
${rows}
</ul>
<p>Endpoints: <code>/all.m3u</code>, <code>/&lt;slug&gt;.m3u</code>, <code>/p/&lt;id&gt;.m3u</code>, <code>/health</code></p>`);
}

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    try {
      if (url.pathname === "/health") {
        const { data, age, src } = await getCatalog(env);
        return json({ ok: true, source: src, cache_age_s: age, playlists: (data.playlists || []).length, channels: (data.channels || []).length });
      }
      const { data, age, src } = await getCatalog(env);
      if (url.pathname === "/" || url.pathname === "/index.html") return indexPage(data, url.origin, age, src);

      let filterId = null;
      if (url.pathname === "/all.m3u" || url.pathname === "/playlist.m3u") {
        filterId = null;
      } else {
        let m = url.pathname.match(/^\/p\/(\d+)\.m3u$/);
        if (m) filterId = Number(m[1]);
        else {
          m = url.pathname.match(/^\/([a-z0-9-]+)\.m3u$/);
          if (m) {
            const p = (data.playlists || []).find(p => slug(p.name) === m[1]);
            if (!p) return new Response("unknown playlist\n", { status: 404 });
            filterId = p.id;
          } else return new Response("not found — see /\n", { status: 404 });
        }
      }
      const { body, count } = buildM3U(data, filterId, url.origin);
      return new Response(body, { headers: {
        "content-type": "audio/x-mpegurl; charset=utf-8",
        "access-control-allow-origin": "*",
        "cache-control": `public, max-age=${TTL}`,
        "x-plugx-channels": String(count),
        "x-plugx-cache": `${src}:${age}s`,
      } });
    } catch (e) {
      return json({ ok: false, error: String(e && e.message || e) }, 500);
    }
  }
};
