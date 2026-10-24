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

  // Mint fresh token
  try {
    const freshToken = await mintToken();
    if (env.SONY_CACHE && freshToken) {
      const exp = parseExpiry(freshToken);
      const ttlSec = Math.max(60, Math.floor((exp - Date.now()) / 1000));
      await env.SONY_CACHE.put(KV_KEY, freshToken, { expirationTtl: ttlSec });
    }
    return freshToken;
  } catch (err) {
    // If minting fails, fallback to existing cached token if available
    if (env.SONY_CACHE) {
      const cached = await env.SONY_CACHE.get(KV_KEY);
      if (cached) return cached;
    }
    throw err;
  }
}

function renderDashboard(host, token) {
  const remaining = token ? getRemainingHours(token) : "Standby";
  const isValid = token && parseExpiry(token) > Date.now();

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SonyLIV Live • Stream Engine</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #070c18;
      --card: #0f172a;
      --card-hover: #1e293b;
      --border: #1e293b;
      --primary: #3b82f6;
      --primary-hover: #2563eb;
      --accent: #f59e0b;
      --text: #f8fafc;
      --text-dim: #94a3b8;
      --success: #10b981;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg);
      background-image: 
        radial-gradient(at 0% 0%, rgba(59, 130, 246, 0.15) 0px, transparent 50%),
        radial-gradient(at 100% 100%, rgba(245, 158, 11, 0.1) 0px, transparent 50%);
      color: var(--text);
      font-family: 'Plus Jakarta Sans', sans-serif;
      min-height: 100vh;
      padding-bottom: 60px;
    }
    .header {
      background: rgba(7, 12, 24, 0.85);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border);
      position: sticky;
      top: 0;
      z-index: 50;
    }
    .header-inner {
      max-width: 1200px;
      margin: 0 auto;
      padding: 16px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      text-decoration: none;
      color: #fff;
    }
    .brand-icon {
      width: 40px;
      height: 40px;
      background: linear-gradient(135deg, #2563eb 0%, #f59e0b 100%);
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.15rem;
      font-weight: 800;
      box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: rgba(16, 185, 129, 0.12);
      border: 1px solid rgba(16, 185, 129, 0.3);
      color: var(--success);
      padding: 6px 12px;
      border-radius: 999px;
      font-size: 0.8rem;
      font-weight: 600;
    }
    .dot {
      width: 7px;
      height: 7px;
      background: var(--success);
      border-radius: 50%;
      box-shadow: 0 0 8px var(--success);
    }
    .container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 36px 24px 0;
    }
    .hero {
      text-align: center;
      margin-bottom: 36px;
    }
    .hero h2 {
      font-size: 2.2rem;
      font-weight: 800;
      margin-bottom: 8px;
      background: linear-gradient(135deg, #fff 40%, #93c5fd 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .hero p {
      color: var(--text-dim);
      font-size: 1.05rem;
    }
    .stats {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-bottom: 32px;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 20px;
      transition: border-color 0.2s;
    }
    .card:hover {
      border-color: rgba(59, 130, 246, 0.4);
    }
    .stat-label {
      font-size: 0.8rem;
      color: var(--text-dim);
      text-transform: uppercase;
      font-weight: 600;
      margin-bottom: 6px;
    }
    .stat-val {
      font-size: 1.6rem;
      font-weight: 800;
      color: #fff;
    }
    .endpoints {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 16px;
      margin-bottom: 36px;
    }
    .copy-box {
      display: flex;
      gap: 8px;
      background: #030712;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 4px 6px 4px 12px;
      align-items: center;
      margin-top: 12px;
    }
    .copy-input {
      background: transparent;
      border: none;
      color: #93c5fd;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.82rem;
      flex: 1;
      outline: none;
    }
    .btn-copy {
      background: #1e293b;
      color: #fff;
      border: 1px solid var(--border);
      padding: 8px 14px;
      border-radius: 8px;
      font-size: 0.8rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
    }
    .btn-copy:hover {
      background: var(--primary);
    }
    .controls {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 20px;
      align-items: center;
      justify-content: space-between;
    }
    .search-input {
      background: var(--card);
      border: 1px solid var(--border);
      color: #fff;
      padding: 10px 16px;
      border-radius: 10px;
      font-size: 0.9rem;
      width: 100%;
      max-width: 340px;
      outline: none;
    }
    .search-input:focus {
      border-color: var(--primary);
    }
    .channels-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(270px, 1fr));
      gap: 12px;
      max-height: 520px;
      overflow-y: auto;
      padding-right: 6px;
    }
    .channels-grid::-webkit-scrollbar {
      width: 6px;
    }
    .channels-grid::-webkit-scrollbar-thumb {
      background: var(--border);
      border-radius: 4px;
    }
    .ch-card {
      background: #090e1c;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px 14px;
      display: flex;
      align-items: center;
      gap: 12px;
      transition: transform 0.15s, border-color 0.15s;
    }
    .ch-card:hover {
      transform: translateY(-2px);
      border-color: var(--primary);
      background: var(--card-hover);
    }
    .ch-logo {
      width: 44px;
      height: 44px;
      object-fit: contain;
      border-radius: 8px;
      background: #111827;
      padding: 4px;
    }
    .ch-name {
      font-weight: 600;
      font-size: 0.88rem;
      margin-bottom: 2px;
    }
    .ch-group {
      font-size: 0.75rem;
      color: var(--text-dim);
    }
    .ch-slug {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.7rem;
      color: #60a5fa;
      margin-top: 2px;
    }
    .toast {
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: var(--success);
      color: #fff;
      padding: 12px 20px;
      border-radius: 10px;
      font-weight: 600;
      box-shadow: 0 10px 25px rgba(0,0,0,0.5);
      opacity: 0;
      transform: translateY(20px);
      transition: all 0.3s;
      z-index: 100;
    }
    .toast.show {
      opacity: 1;
      transform: translateY(0);
    }
    footer {
      text-align: center;
      margin-top: 50px;
      color: var(--text-dim);
      font-size: 0.85rem;
    }
  </style>
</head>
<body>
  <header class="header">
    <div class="header-inner">
      <a href="/" class="brand">
        <div class="brand-icon">SL</div>
        <div>
          <h1 style="font-size:1.15rem; font-weight:800;">SonyLIV Live</h1>
          <span style="font-size:0.75rem; color:var(--text-dim);">Wildcard Akamai Minter</span>
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
      <h2>Live TV, Movies & Sports Streaming Engine</h2>
      <p>Direct Akamai CDN token authentication with seamless HLS stream playback</p>
    </div>

    <div class="stats">
      <div class="card">
        <div class="stat-label">Total Channels</div>
        <div class="stat-val">${CHANNELS.length}</div>
      </div>
      <div class="card">
        <div class="stat-label">Token Status</div>
        <div class="stat-val" style="color:${isValid ? '#34d399' : '#f59e0b'};">${isValid ? 'Active' : 'Refreshing'}</div>
        <div style="font-size:0.75rem; color:var(--text-dim); margin-top:4px;">${remaining} validity</div>
      </div>
      <div class="card">
        <div class="stat-label">Streaming Quality</div>
        <div class="stat-val" style="color:#60a5fa;">Full HD 1080p</div>
      </div>
    </div>

    <h3 style="margin-bottom:14px; font-size:1.15rem;">⚡ Endpoints & Playlists</h3>
    <div class="endpoints">
      <div class="card">
        <h4 style="font-size:0.95rem; font-weight:700;">📺 Master SonyLIV Playlist (M3U)</h4>
        <p style="font-size:0.85rem; color:var(--text-dim); margin-top:4px;">Direct M3U playlist feed compatible with TiviMate & IPTV players.</p>
        <div class="copy-box">
          <input type="text" readonly class="copy-input" id="u-m3u" value="https://${host}/playlist.m3u">
          <button class="btn-copy" onclick="copy('u-m3u')">Copy</button>
        </div>
      </div>

      <div class="card">
        <h4 style="font-size:0.95rem; font-weight:700;">📡 Stream Resolver Endpoint</h4>
        <p style="font-size:0.85rem; color:var(--text-dim); margin-top:4px;">Individual 302 stream resolution with fresh Akamai tokens.</p>
        <div class="copy-box">
          <input type="text" readonly class="copy-input" id="u-res" value="https://${host}/{slug}.m3u8">
          <button class="btn-copy" onclick="copy('u-res')">Copy</button>
        </div>
      </div>

      <div class="card">
        <h4 style="font-size:0.95rem; font-weight:700;">📊 Channels Catalog (JSON)</h4>
        <p style="font-size:0.85rem; color:var(--text-dim); margin-top:4px;">Machine-readable channel list, slugs, and high-res logos.</p>
        <div class="copy-box">
          <input type="text" readonly class="copy-input" id="u-json" value="https://${host}/channels.json">
          <button class="btn-copy" onclick="copy('u-json')">Copy</button>
        </div>
      </div>
    </div>

    <div class="card" style="margin-bottom:36px;">
      <div class="controls">
        <h3 style="font-size:1.15rem;">📺 Live Channels Directory</h3>
        <input type="text" id="search" class="search-input" placeholder="Search by channel name, slug, or category..." oninput="filterChannels()">
      </div>
      <div class="channels-grid" id="channels-container">
        ${CHANNELS.map(c => `
          <div class="ch-card" data-name="${(c.name || '').toLowerCase()}" data-slug="${(c.slug || '').toLowerCase()}" data-group="${(c.group || '').toLowerCase()}">
            <img src="${c.logo || 'https://www.sonyliv.com/favicon.ico'}" class="ch-logo" loading="lazy" onerror="this.src='https://www.sonyliv.com/favicon.ico'">
            <div style="flex:1; overflow:hidden;">
              <div class="ch-name" title="${c.name}">${c.name}</div>
              <div class="ch-group">${c.group || 'SonyLIV'}</div>
              <div class="ch-slug">${c.slug || c.id}</div>
            </div>
          </div>
        `).join('')}
      </div>
    </div>

    <footer>SonyLIV Live Stream Engine • Community IPTV Hub</footer>
  </div>

  <div id="toast" class="toast">Link copied!</div>

  <script>
    function copy(id) {
      const el = document.getElementById(id);
      navigator.clipboard.writeText(el.value).then(() => {
        showToast();
      });
    }
    function showToast() {
      const t = document.getElementById('toast');
      t.classList.add('show');
      setTimeout(() => t.classList.remove('show'), 2000);
    }
    function filterChannels() {
      const q = document.getElementById('search').value.toLowerCase();
      const cards = document.querySelectorAll('.ch-card');
      cards.forEach(card => {
        const name = card.getAttribute('data-name');
        const slug = card.getAttribute('data-slug');
        const group = card.getAttribute('data-group');
        if (name.includes(q) || slug.includes(q) || group.includes(q)) {
          card.style.display = 'flex';
        } else {
          card.style.display = 'none';
        }
      });
    }
  </script>
</body>
</html>`;
}

function buildPlaylist(host, token) {
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
    // If token is provided, link direct or via worker proxy
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

    const accept = request.headers.get("Accept") || "";

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

    if (path === "/") {
      if (accept.includes("text/html")) {
        return new Response(renderDashboard(host, token), {
          headers: {
            ...CORS,
            "Content-Type": "text/html; charset=utf-8",
            "Cache-Control": "public, max-age=60",
          },
        });
      }
      return new Response(buildPlaylist(host, token), {
        headers: {
          ...CORS,
          "Content-Type": "application/vnd.apple.mpegurl",
          "Content-Disposition": 'inline; filename="sonyliv.m3u"',
          "Cache-Control": "public, max-age=300",
        },
      });
    }

    if (path === "/playlist.m3u" || path === "/live.m3u") {
      return new Response(buildPlaylist(host, token), {
        headers: {
          ...CORS,
          "Content-Type": "application/vnd.apple.mpegurl",
          "Content-Disposition": 'inline; filename="sonyliv.m3u"',
          "Cache-Control": "public, max-age=300",
        },
      });
    }

    if (path === "/channels.json") {
      return new Response(JSON.stringify(CHANNELS, null, 2), {
        headers: {
          ...CORS,
          "Content-Type": "application/json; charset=utf-8",
          "Cache-Control": "public, max-age=600",
        },
      });
    }

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
