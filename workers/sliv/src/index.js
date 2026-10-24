import { CHANNELS } from "./channels.js";

const USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36";
const KV_KEY = "token";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, HEAD, POST, OPTIONS",
  "Access-Control-Allow-Headers": "*",
};

function parseExpiry(token) {
  const m = token && token.match(/exp=(\d+)/);
  return m ? Number(m[1]) * 1000 : 0;
}

function getRemainingHours(token) {
  const exp = parseExpiry(token);
  if (!exp) return "0.0h";
  const leftMs = Math.max(0, exp - Date.now());
  return `${(leftMs / 3600000).toFixed(1)}h`;
}

async function mintToken() {
  const r1 = await fetch("https://apiv2.sonyliv.com/AGL/1.4/A/ENG/WEB/ALL/GETTOKEN", {
    headers: { "User-Agent": USER_AGENT },
  });
  if (!r1.ok) throw new Error(`GETTOKEN HTTP ${r1.status}`);
  const data1 = await r1.json();
  const jwt = data1.resultObj;
  if (!jwt || typeof jwt !== "string") throw new Error("No JWT in GETTOKEN");

  const r2 = await fetch("https://apiv2.sonyliv.com/AGL/1.5/A/ENG/WEB/IN/CONTENT/VIDEOURL/VOD/1000022678", {
    headers: {
      "User-Agent": USER_AGENT,
      "security_token": jwt,
    },
  });
  if (!r2.ok) throw new Error(`VIDEOURL HTTP ${r2.status}`);
  const data2 = await r2.json();
  const videoUrl = data2.resultObj?.videoURL || "";
  const match = videoUrl.match(/[?&](hdnea=[^&]+)/);
  if (!match) throw new Error("No hdnea token in videoURL");
  return match[1];
}

async function getOrRefreshToken(env, force = false) {
  if (!force && env.SONY_CACHE) {
    try {
      const cached = await env.SONY_CACHE.get(KV_KEY);
      if (cached) {
        const exp = parseExpiry(cached);
        if (exp - Date.now() > 3600000) {
          return cached;
        }
      }
    } catch (e) {
      console.warn("KV get error:", e);
    }
  }

  try {
    const freshToken = await mintToken();
    if (env.SONY_CACHE && freshToken) {
      const exp = parseExpiry(freshToken);
      const ttlSec = Math.max(60, Math.floor((exp - Date.now()) / 1000));
      await env.SONY_CACHE.put(KV_KEY, freshToken, { expirationTtl: ttlSec });
    }
    return freshToken;
  } catch (err) {
    if (env.SONY_CACHE) {
      const cached = await env.SONY_CACHE.get(KV_KEY);
      if (cached) return cached;
    }
    throw err;
  }
}

function buildPlaylist(host) {
  const lines = [
    "#EXTM3U",
    `# Total Channels: ${CHANNELS.length}`,
    `# Source: https://${host}`,
    ""
  ];

  for (const ch of CHANNELS) {
    const slug = (ch.slug || ch.id || "").trim();
    const name = (ch.name || "").trim();
    const logo = (ch.logo || "").trim();
    const group = (ch.group || "Sony LIV").trim();
    if (!slug || !name) continue;

    lines.push(
      `#EXTINF:-1 tvg-id="${ch.id || slug}" tvg-name="${name}" tvg-logo="${logo}" group-title="${group}" group-logo="https://upload.wikimedia.org/wikipedia/commons/f/f7/SonyLIV_2020.png",${name}`
    );
    lines.push(`#EXTVLCOPT:http-user-agent=${USER_AGENT}`);
    lines.push(`https://${host}/${slug}.m3u8`);
    lines.push("");
  }

  return lines.join("\n").trim() + "\n";
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";
    const host = url.host;

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS });
    }

    // Force mint token endpoint
    if (path === "/mint" && request.method === "POST") {
      try {
        const token = await getOrRefreshToken(env, true);
        return Response.json({
          ok: true,
          token: token.substring(0, 30) + "...",
          expiresIn: getRemainingHours(token),
          timestamp: new Date().toISOString()
        }, { headers: CORS });
      } catch (err) {
        return Response.json({ ok: false, error: err.message }, { status: 500, headers: CORS });
      }
    }

    let token = "";
    try {
      token = await getOrRefreshToken(env, false);
    } catch (e) {
      console.warn("Could not load token:", e);
    }

    // Root / or /playlist.m3u or /live.m3u -> Pure M3U playlist (tgaadi style)
    if (path === "/" || path === "/playlist.m3u" || path === "/live.m3u") {
      return new Response(buildPlaylist(host), {
        headers: {
          ...CORS,
          "Content-Type": "application/vnd.apple.mpegurl",
          "Content-Disposition": 'inline; filename="sonyliv.m3u"',
          "Cache-Control": "public, max-age=300",
        },
      });
    }

    // Channel metadata JSON
    if (path === "/channels.json") {
      return new Response(JSON.stringify(CHANNELS, null, 2), {
        headers: {
          ...CORS,
          "Content-Type": "application/json; charset=utf-8",
          "Cache-Control": "public, max-age=600",
        },
      });
    }

    // Status check
    if (path === "/status" || path === "/health" || path === "/token.json") {
      const exp = parseExpiry(token);
      return Response.json({
        ok: !!token && exp > Date.now(),
        service: "sonyliv-worker",
        clean_url: `https://${host}`,
        channels: CHANNELS.length,
        expiresIn: getRemainingHours(token),
        ttl: exp ? Math.max(0, Math.floor((exp - Date.now()) / 1000)) : 0,
        status: token && exp > Date.now() ? "active" : "standby",
        timestamp: new Date().toISOString()
      }, { headers: CORS });
    }

    // Handle channel stream resolution: /:slug.m3u8 or /live/:slug.m3u8
    const match = path.match(/(?:^\/live\/|^\/)([0-9a-zA-Z\-_]+)(?:\.m3u8)?$/);
    if (!match) {
      return new Response("Invalid channel path. Use /{slug}.m3u8\n", { status: 400, headers: CORS });
    }

    const channelSlug = match[1].toLowerCase();
    const ch = CHANNELS.find(c => 
      (c.slug && c.slug.toLowerCase() === channelSlug) || 
      (c.id && c.id.toLowerCase() === channelSlug)
    );

    if (!ch) {
      return new Response(`Channel slug "${channelSlug}" not found.\n`, { status: 404, headers: CORS });
    }

    if (!token) {
      try {
        token = await getOrRefreshToken(env, true);
      } catch (err) {
        return new Response(`Error acquiring token: ${err.message}\n`, { status: 503, headers: CORS });
      }
    }

    const targetUrl = `${ch.streamUrl}?${token}`;
    return new Response(null, {
      status: 302,
      headers: {
        ...CORS,
        "Location": targetUrl,
        "Cache-Control": "no-store, no-cache, must-revalidate",
      },
    });
  },
};
