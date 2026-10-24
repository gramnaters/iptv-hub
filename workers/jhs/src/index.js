/**
 * jhs — JioHotstar live playlist, self-minting.
 *
 * The streams are gated by one Akamai `hdntl` token (acl=/*, 24h). It is minted
 * from the owner's Hotstar session via Cloudflare Browser Rendering Puppeteer.
 */

import { CHANNELS } from "./channels.js";
import { USER_TOKEN as SEED_TOKEN, MINTED_AT as SEED_MINTED_AT } from "./token.js";
import puppeteer from "@cloudflare/puppeteer";

const KV_KEY = "hs:token:v1";
const MIN_TTL_MS = 8 * 60 * 60 * 1000;
const COOKIE_KEYS = ["deviceId", "userHID", "userPID", "userCountryCode", "sessionUserUP", "userUP"];

const USER_AGENT = "Hotstar;in.startv.hotstar/25.02.24.8.11169@Premium Plugx(Android/15)";
const REFERER = "https://www.hotstar.com/";
const ORIGIN = "https://www.hotstar.com";

const APP_UA = "Hotstar;in.startv.hotstar/25.02.24.8.11169";
const WEB_CLIENT = "platform:web;app_version:26.09.23.1;browser:Chrome;schema_version:0.0.1";
const BFF = "https://www.hotstar.com/api/internal/bff/v2/start";
const ORIGIN_URL = "https://www.hotstar.com/robots.txt";

const CAPS = { ads: ["non_ssai", "ssai"], audio_channel: ["stereo"], container: ["fmp4", "fmp4br", "ts"], dvr: ["short"], dynamic_range: ["sdr"], encryption: ["plain"], ladder: ["web", "tv", "phone"], package: ["dash", "hls"], resolution: ["sd", "hd", "fhd"], video_codec: ["h264"], video_codec_non_secure: ["h265", "h264"] };
const DRM = { hdcp_version: ["HDCP_V2_2"], widevine_security_level: [], playready_security_level: [] };

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
  "Access-Control-Allow-Headers": "*",
};

/* ------------------------------------------------------------------ helpers */

const tokenExp = (t) => {
  const m = t && t.match(/exp=(\d+)/);
  return m ? Number(m[1]) * 1000 : 0;
};

const tokenTtl = (t) => Math.max(0, tokenExp(t) - Date.now());

const stateOf = (token, mintedAt, source) => {
  const expMs = tokenExp(token);
  const leftMs = Math.max(0, expMs - Date.now());
  return {
    ok: leftMs > 0,
    source,
    mintedAt,
    exp: expMs ? new Date(expMs).toISOString() : null,
    expiresInHours: Number((leftMs / 3600000).toFixed(2)),
    totalChannels: CHANNELS.length,
  };
};

/* ----------------------------------------------------------------------- kv */

async function loadState(env) {
  try {
    const raw = await env.HS_CACHE.get(KV_KEY, "json");
    if (raw && raw.token && tokenTtl(raw.token) > 0) {
      return { token: raw.token, mintedAt: raw.mintedAt, source: "kv" };
    }
  } catch (e) {
    console.warn("kv read failed:", e && e.message);
  }
  return { token: SEED_TOKEN, mintedAt: SEED_MINTED_AT, source: "seed" };
}

async function storeToken(env, token) {
  const mintedAt = new Date().toISOString();
  await env.HS_CACHE.put(KV_KEY, JSON.stringify({ token, mintedAt }), {
    expirationTtl: 60 * 60 * 24 * 30,
  });
  return mintedAt;
}

/* --------------------------------------------------------------------- mint */

async function mintInPage(args) {
  const { dl, session, jar, client } = args;
  const headers = (tok, extra) => Object.assign({
    Accept: "application/json",
    "Content-Type": "application/json",
    "x-hs-usertoken": tok,
    "x-hs-platform": "web",
    "x-hs-app": "260923001",
    "x-country-code": "in",
    "x-hs-accept-language": "eng",
    "x-hs-device-id": jar.deviceId,
    "x-hs-client": client,
    "x-hs-retry-count": "0",
    "x-hs-is-retry": "false",
  }, extra || {});

  const post = async (tok, extra) => {
    const r = await fetch("/api/internal/bff/v2/start", {
      method: "POST",
      headers: headers(tok, extra),
      body: JSON.stringify({ deeplink_url: dl, app_launch_count: 34 }),
    });
    const text = (await r.text()).split("\\/").join("/");
    return { status: r.status, text, tok: r.headers.get("x-hs-usertoken"), ps: r.headers.get("x-hs-setproxystate") };
  };

  const first = await post(session, null);
  if (first.status !== 200) return { error: "bff step 1 -> HTTP " + first.status, body: first.text.slice(0, 160) };

  const second = await post(first.tok || session, {
    "x-hs-proxystate": first.ps || "",
    "x-hs-proxystate-ud": "loc=" + (jar.fresh_loc || ""),
    "x-hs-client-targeting": "ad_id:" + jar.deviceId + ";user_lat:false;",
  });
  if (second.status !== 200) return { error: "bff step 2 -> HTTP " + second.status, body: second.text.slice(0, 160) };

  const m = second.text.match(/https:\/\/(?:livetv|live09p|jcevents)\.hotstar\.com\/[^"'\s]+/);
  if (!m) return { error: "no livetv url in bff payload" };
  return { manifestUrl: m[0] };
}

async function mintWithBrowser(env) {
  if (!env.MYBROWSER) throw new Error("MYBROWSER binding missing");
  const rawCookie = env.HS_COOKIE;
  if (!rawCookie) throw new Error("HS_COOKIE secret missing");

  let jar = {};
  try {
    jar = JSON.parse(rawCookie);
  } catch {
    for (const line of rawCookie.split(/\r?\n/)) {
      const p = line.split("\t");
      if (p.length >= 7) jar[p[5]] = p[6].trim();
    }
  }
  const session = jar.sessionUserUP || jar.userUP || jar.fresh_userUP;
  if (!session) throw new Error("no sessionUserUP in HS_COOKIE");

  const probe = CHANNELS[0];
  const dl =
    `/in/shows/${probe.slug || "star-sports-1-hd"}/${probe.id}/live/watch` +
    `?client_capabilities=${encodeURIComponent(JSON.stringify(CAPS))}` +
    `&drm_parameters=${encodeURIComponent(JSON.stringify(DRM))}&request_features=consent_supported`;

  const browser = await puppeteer.launch(env.MYBROWSER);
  try {
    const page = await browser.newPage();
    await page.setUserAgent(APP_UA);
    await page.setCookie(
      ...COOKIE_KEYS.filter((k) => jar[k]).map((name) => ({
        name,
        value: jar[name],
        domain: ".hotstar.com",
        path: "/",
      })),
    );

    await page.goto(ORIGIN_URL, { waitUntil: "domcontentloaded", timeout: 25000 });
    const res = await page.evaluate(mintInPage, { dl, session, jar, client: WEB_CLIENT });
    if (!res || !res.manifestUrl) {
      throw new Error((res && res.error) || "empty evaluate response");
    }

    const intercepted = await page.evaluate(async (url) => {
      const r = await fetch(url, { method: "GET", credentials: "include" });
      return { status: r.status };
    }, res.manifestUrl);

    const cookies = await page.cookies("https://hotstar.com", "https://akamaized.net");
    const h = cookies.find((c) => c.name === "hdntl");
    if (!h || !h.value) {
      throw new Error(`no hdntl cookie set (status was ${intercepted.status})`);
    }

    return "hdntl=" + h.value;
  } finally {
    await browser.close().catch(() => {});
  }
}

async function refresh(env, force) {
  const current = await loadState(env);
  const left = tokenTtl(current.token);
  if (!force && left > MIN_TTL_MS) {
    return { minted: false, reason: "ttl-ok", leftHours: Number((left / 3600000).toFixed(2)) };
  }
  const token = await mintWithBrowser(env);
  const mintedAt = await storeToken(env, token);
  return { minted: true, mintedAt, exp: new Date(tokenExp(token)).toISOString() };
}

/* ------------------------------------------------------------------ playlist */

function buildPlaylist(hdntl) {
  const lines = ["#EXTM3U x-tvg-url=\"https://avkb.short.gy/jioepg.xml.gz\""];
  for (const ch of CHANNELS) {
    const logo = ch.logo ? ` tvg-logo="${ch.logo}"` : "";
    const group = ch.group ? ` group-title="${ch.group}"` : "";
    lines.push(`#EXTINF:-1 tvg-id="${ch.id}" tvg-name="${ch.name}"${logo}${group},${ch.name}`);
    if (ch.type === "dash") {
      lines.push("#KODIPROP:inputstream=inputstream.adaptive");
      lines.push("#KODIPROP:inputstream.adaptive.manifest_type=mpd");
      if (ch.keyId && ch.key) {
        lines.push("#KODIPROP:inputstream.adaptive.license_type=clearkey");
        lines.push(`#KODIPROP:inputstream.adaptive.license_key=${ch.keyId}:${ch.key}`);
      }
    }
    lines.push(`#EXTVLCOPT:http-user-agent=${USER_AGENT}`);
    lines.push(`#EXTVLCOPT:http-referrer=${REFERER}`);
    lines.push(`#EXTVLCOPT:http-extra-headers=Origin: ${ORIGIN}`);
    if (hdntl) {
      lines.push(`#EXTVLCOPT:http-cookie=${hdntl}`);
      lines.push(`#EXTHTTP:${JSON.stringify({ Origin: ORIGIN, Referer: REFERER, Cookie: hdntl })}`);
    }
    lines.push(ch.url);
    lines.push("");
  }
  return lines.join("\n");
}

function renderJhsDashboard(host, state) {
  const hrs = state.expiresInHours ? state.expiresInHours + " hours" : "Active";
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>JioHotstar • Live Stream Engine</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #060913;
      --card: #0d1326;
      --border: #182240;
      --primary: #2563eb;
      --accent: #38bdf8;
      --text: #f8fafc;
      --text-dim: #94a3b8;
    }
    * { margin:0; padding:0; box-sizing:border-box; }
    body { background: var(--bg); color: var(--text); font-family: 'Plus Jakarta Sans', sans-serif; padding-bottom: 60px; }
    .header { border-bottom: 1px solid var(--border); background: rgba(13,19,38,0.85); backdrop-filter: blur(12px); padding: 16px 24px; position: sticky; top:0; z-index:50; }
    .header-inner { max-width: 1100px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; }
    .brand { display: flex; align-items: center; gap: 12px; text-decoration: none; color: inherit; }
    .brand-icon { font-size: 22px; background: linear-gradient(135deg, #1e40af, #0284c7); width: 40px; height: 40px; border-radius: 10px; display:flex; align-items:center; justify-content:center; }
    .badge { display: flex; align-items: center; gap: 8px; background: rgba(16,185,129,0.1); border: 1px solid rgba(16,185,129,0.3); color: #34d399; font-size: 0.8rem; font-weight: 600; padding: 6px 14px; border-radius: 999px; }
    .dot { width: 8px; height: 8px; background: #10b981; border-radius: 50%; box-shadow: 0 0 8px #10b981; }
    .container { max-width: 1100px; margin: 32px auto 0; padding: 0 20px; }
    .hero { text-align: center; margin-bottom: 32px; }
    .hero h2 { font-size: 2.2rem; font-weight: 800; margin-bottom: 8px; }
    .hero p { color: var(--text-dim); }
    .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 32px; }
    .card { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 20px; }
    .stat-label { font-size: 0.8rem; color: var(--text-dim); text-transform: uppercase; font-weight: 600; margin-bottom: 6px; }
    .stat-val { font-size: 1.6rem; font-weight: 800; color: #fff; }
    .endpoints { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; margin-bottom: 36px; }
    .copy-box { display: flex; gap: 8px; background: #05070e; border: 1px solid var(--border); border-radius: 10px; padding: 4px 6px 4px 12px; align-items: center; margin-top: 12px; }
    .copy-input { background: transparent; border: none; color: #7dd3fc; font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; flex: 1; outline: none; }
    .btn-copy { background: #1e293b; color: #fff; border: 1px solid var(--border); padding: 8px 14px; border-radius: 8px; font-size: 0.8rem; font-weight: 600; cursor: pointer; }
    .btn-copy:hover { background: var(--primary); }
    .channels-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; max-height: 480px; overflow-y: auto; padding-right: 6px; }
    .ch-card { background: #070a14; border: 1px solid var(--border); border-radius: 12px; padding: 12px 14px; display: flex; align-items: center; gap: 12px; }
    .ch-logo { width: 36px; height: 36px; object-fit: contain; border-radius: 8px; background: #111827; }
    .ch-name { font-weight: 600; font-size: 0.88rem; }
    .ch-group { font-size: 0.75rem; color: var(--text-dim); }
    .toast { position: fixed; bottom: 24px; right: 24px; background: #10b981; color: #fff; padding: 12px 20px; border-radius: 10px; font-weight: 600; opacity: 0; transform: translateY(20px); transition: all 0.3s; z-index: 100; }
    .toast.show { opacity: 1; transform: translateY(0); }
    footer { text-align: center; margin-top: 50px; color: var(--text-dim); font-size: 0.85rem; }
  </style>
</head>
<body>
  <header class="header">
    <div class="header-inner">
      <a href="/" class="brand">
        <div class="brand-icon">⭐</div>
        <div>
          <h1 style="font-size:1.15rem; font-weight:800;">JioHotstar Live</h1>
          <span style="font-size:0.75rem; color:var(--text-dim);">Puppeteer Autonomous Minter</span>
        </div>
      </a>
      <div class="badge">
        <div class="dot"></div>
        <span>${CHANNELS.length} Channels Live</span>
      </div>
    </div>
  </header>

  <div class="container">
    <div class="hero">
      <h2>Live TV & Sports Streaming Engine</h2>
      <p>Autonomous Akamai token self-minting powered by Cloudflare Browser Rendering</p>
    </div>

    <div class="stats">
      <div class="card">
        <div class="stat-label">Total Channels</div>
        <div class="stat-val">${CHANNELS.length}</div>
      </div>
      <div class="card">
        <div class="stat-label">Token Status</div>
        <div class="stat-val" style="color:#34d399;">Active</div>
        <div style="font-size:0.75rem; color:var(--text-dim); margin-top:4px;">${hrs} remaining</div>
      </div>
      <div class="card">
        <div class="stat-label">Auto Refresh</div>
        <div class="stat-val" style="color:#38bdf8;">Hourly Cron</div>
      </div>
    </div>

    <h3 style="margin-bottom:14px; font-size:1.15rem;">⚡ Stream Playlist Endpoints</h3>
    <div class="endpoints">
      <div class="card">
        <h4 style="font-size:0.95rem; font-weight:700;">⭐ Master JioHotstar Playlist (M3U)</h4>
        <p style="font-size:0.85rem; color:var(--text-dim); margin-top:4px;">Direct M3U feed with baked Akamai hdntl cookie headers.</p>
        <div class="copy-box">
          <input type="text" readonly class="copy-input" id="u-m3u" value="https://${host}/playlist.m3u">
          <button class="btn-copy" onclick="copy('u-m3u')">Copy</button>
        </div>
      </div>

      <div class="card">
        <h4 style="font-size:0.95rem; font-weight:700;">📊 Token Freshness Status (JSON)</h4>
        <p style="font-size:0.85rem; color:var(--text-dim); margin-top:4px;">Real-time KV token expiration timestamp & health.</p>
        <div class="copy-box">
          <input type="text" readonly class="copy-input" id="u-status" value="https://${host}/status">
          <button class="btn-copy" onclick="copy('u-status')">Copy</button>
        </div>
      </div>
    </div>

    <div class="card" style="margin-bottom:36px;">
      <h3 style="margin-bottom:16px; font-size:1.15rem;">📺 Included Live Channels</h3>
      <div class="channels-grid">
        ${CHANNELS.map(c => `
          <div class="ch-card">
            <img src="${c.logo || 'https://www.hotstar.com/favicon.ico'}" class="ch-logo" onerror="this.src='https://www.hotstar.com/favicon.ico'">
            <div>
              <div class="ch-name">${c.name}</div>
              <div class="ch-group">${c.group || 'Live TV'}</div>
            </div>
          </div>
        `).join('')}
      </div>
    </div>

    <footer>JioHotstar Live Engine • Community IPTV Hub</footer>
  </div>
  <div id="toast" class="toast">Link copied!</div>
  <script>
    function copy(id) {
      navigator.clipboard.writeText(document.getElementById(id).value);
      const t = document.getElementById('toast');
      t.classList.add('show');
      setTimeout(() => t.classList.remove('show'), 2000);
    }
  </script>
</body>
</html>`;
}

/* --------------------------------------------------------------------- main */

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";
    const accept = request.headers.get("Accept") || "";

    if (request.method === "OPTIONS") return new Response(null, { headers: CORS });

    if (path === "/status") {
      const state = await loadState(env);
      const payload = { ...stateOf(state.token, state.mintedAt, state.source), cookieConfigured: !!env.HS_COOKIE, cron: "0 * * * *" };
      return Response.json(payload, { headers: CORS });
    }

    if (path === "/mint") {
      if (request.method !== "POST") {
        return new Response("POST required\n", { status: 405, headers: CORS });
      }
      const auth = request.headers.get("Authorization") || "";
      if (!env.MINT_SECRET || auth !== "Bearer " + env.MINT_SECRET) {
        return new Response("unauthorized\n", { status: 401, headers: CORS });
      }
      try {
        const result = await refresh(env, true);
        return Response.json(result, { headers: CORS });
      } catch (e) {
        return Response.json({ minted: false, error: (e && e.message) || String(e) }, { status: 502, headers: CORS });
      }
    }

    const state = await loadState(env);

    // Serve HTML Dashboard on root for browser visits
    if (path === "/" && accept.includes("text/html")) {
      return new Response(renderJhsDashboard(url.host, state), {
        headers: { ...CORS, "Content-Type": "text/html; charset=utf-8" }
      });
    }

    return new Response(buildPlaylist(state.token), {
      headers: {
        ...CORS,
        "Content-Type": "application/vnd.apple.mpegurl; charset=utf-8",
        "Content-Disposition": 'inline; filename="jhs.m3u"',
        "Cache-Control": "public, max-age=300",
      },
    });
  },

  async scheduled(event, env, ctx) {
    ctx.waitUntil(
      refresh(env, false).catch((e) => console.error("scheduled mint failed:", (e && e.stack) || e)),
    );
  },
};
