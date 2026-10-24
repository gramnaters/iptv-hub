import { CHANNELS } from "./channels.js";

const USER_AGENT = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36";
const KV_KEY = "token";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, HEAD, POST, OPTIONS",
  "Access-Control-Allow-Headers": "*",
};

function formatIST(date) {
  try {
    return new Intl.DateTimeFormat('en-IN', {
      timeZone: 'Asia/Kolkata',
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
      hour12: false
    }).format(date) + " IST";
  } catch (e) {
    return date.toISOString();
  }
}

function parseExpiry(token) {
  const m = token && token.match(/exp=(\d+)/);
  return m ? Number(m[1]) * 1000 : 0;
}

function parseTokenDetails(token) {
  const expMatch = token && token.match(/exp=(\d+)/);
  const aclMatch = token && token.match(/acl=([^~]+)/);
  const idMatch = token && token.match(/id=([^~]+)/);
  const hmacMatch = token && token.match(/hmac=([a-f0-9]+)/);
  const expSec = expMatch ? Number(expMatch[1]) : 0;
  const expMs = expSec * 1000;
  const expHuman = expMs ? formatIST(new Date(expMs)) : "";
  return {
    exp: String(expSec),
    exp_human: expHuman,
    acl: aclMatch ? aclMatch[1] : "/*",
    id: idMatch ? idMatch[1] : "",
    hmac: hmacMatch ? hmacMatch[1] : ""
  };
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

function buildDataJson(host, token) {
  const expMs = parseExpiry(token);
  const leftMs = Math.max(0, expMs - Date.now());
  const leftHours = Number((leftMs / 3600000).toFixed(2));
  const parsed = parseTokenDetails(token);

  const channelList = CHANNELS.map(ch => {
    const m = (ch.streamUrl || "").match(/hls\/live\/(\d+)\/([^\/]+)\/master\.m3u8/);
    const liveId = m ? m[1] : "";
    const streamName = m ? m[2] : (ch.slug || ch.id);
    const streamUrl = token ? `${ch.streamUrl}?${token}` : `https://${host}/${ch.slug}.m3u8`;

    return {
      name: ch.name,
      slug: ch.slug || ch.id,
      group: (ch.group || "Entertainment").replace("SonyLIV | ", "").replace("Sony LIV", "Entertainment"),
      live_id: liveId,
      stream: streamName,
      url: streamUrl,
      headers: {
        "User-Agent": USER_AGENT,
        "Referer": "https://www.sonyliv.com/",
        "Origin": "https://www.sonyliv.com",
        "Cookie": token || ""
      }
    };
  });

  return {
    ok: true,
    version: "2.5",
    generated_at: formatIST(new Date()),
    timezone: "Asia/Kolkata",
    token_expires: parsed.exp_human,
    expires_in_hours: leftHours,
    total_channels: CHANNELS.length,
    download_m3u: `https://${host}/playlist.m3u?download=1`,
    view_m3u: `https://${host}/playlist.m3u`,
    cdn: {
      host: "dishmt.slivcdn.com",
      source_url: `https://dishmt.slivcdn.com/hls/live/?${token}`,
      path_base: "/hls/live",
      note: "hdnea token embedded directly in every stream URL as ?hdnea=..."
    },
    cookie: {
      name: "hdnea",
      full_value: token || "",
      cookie_header: token ? `Cookie: ${token}` : "",
      curl_flag: token ? `-b "${token}"` : "",
      parsed: parsed,
      notes: "Akamai token. Already appended to each URL as ?hdnea=... — Cookie header optional."
    },
    channels: channelList,
    debug: []
  };
}

function buildPlaylist(host, token) {
  const expMs = parseExpiry(token);
  const expHuman = expMs ? formatIST(new Date(expMs)) : "";

  const lines = [
    "#EXTM3U",
    "# SonyLIV Direct CDN Playlist v2.5",
    `# Generated  : ${formatIST(new Date())}`,
    `# Token Exp  : ${expHuman}`,
    "# CDN Host   : dishmt.slivcdn.com",
    `# Channels   : ${CHANNELS.length}`,
    "# Token embedded in each URL as ?hdnea=...",
    token ? `# Cookie: ${token}` : "",
    ""
  ];

  for (const ch of CHANNELS) {
    const slug = (ch.slug || ch.id || "").trim();
    const name = (ch.name || "").trim();
    const logo = (ch.logo || "").trim();
    const group = (ch.group || "SonyLIV Entertainment").trim();
    if (!slug || !name) continue;

    const streamUrl = token ? `${ch.streamUrl}?${token}` : `https://${host}/${slug}.m3u8`;

    lines.push(
      `#EXTINF:-1 tvg-id="${ch.id || slug}.sonyliv" tvg-name="${name}" tvg-logo="${logo}" group-title="${group}" group-logo="https://upload.wikimedia.org/wikipedia/commons/f/f7/SonyLIV_2020.png",${name}`
    );
    lines.push(`#EXTVLCOPT:http-user-agent=${USER_AGENT}`);
    lines.push(`#EXTVLCOPT:http-referrer=https://www.sonyliv.com/`);
    if (token) lines.push(`#EXTVLCOPT:http-cookie=${token}`);
    lines.push(`#EXTHTTP:{"User-Agent":"${USER_AGENT}","Referrer":"https://www.sonyliv.com/","Origin":"https://www.sonyliv.com"${token ? ',"Cookie":"' + token + '"' : ''}}`);
    lines.push(streamUrl);
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
          expiresIn: parseTokenDetails(token).exp_human,
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

    // M3U Playlist if requested via ?m3u or /playlist.m3u or /live.m3u
    if (url.searchParams.has("m3u") || path === "/playlist.m3u" || path === "/live.m3u") {
      const isDownload = url.searchParams.has("download");
      return new Response(buildPlaylist(host, token), {
        headers: {
          ...CORS,
          "Content-Type": "application/vnd.apple.mpegurl; charset=utf-8",
          "Content-Disposition": isDownload ? 'attachment; filename="sonyliv.m3u"' : 'inline; filename="sonyliv.m3u"',
          "Cache-Control": "public, max-age=300",
        },
      });
    }

    // Root / or /data or /channels.json -> PremiumPlug-style JSON
    if (path === "/" || path === "/data" || path === "/channels.json") {
      return new Response(JSON.stringify(buildDataJson(host, token), null, 4), {
        headers: {
          ...CORS,
          "Content-Type": "application/json; charset=utf-8",
          "Cache-Control": "public, max-age=60",
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
        expiresIn: parseTokenDetails(token).exp_human,
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
