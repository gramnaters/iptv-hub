import { CHANNELS } from "./channels.js";

const USER_AGENT = "com.graymatrix.did;Android TV;5.82.6(203230929);Android(10);Xiaomi(Redmi Note 8 Pro)";
const UPSTREAM_BASE = "http://premiumplug.fun/tee/zee5.php";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
  "Access-Control-Allow-Headers": "*",
};

function renderDashboard(host) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ZEE5 Live • Stream Engine</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0b0716;
      --card: #130d24;
      --card-hover: #1c1436;
      --border: #291c4d;
      --primary: #8b5cf6;
      --primary-hover: #7c3aed;
      --secondary: #ec4899;
      --text: #f3f4f6;
      --text-dim: #9ca3af;
      --success: #10b981;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg);
      background-image: 
        radial-gradient(at 0% 0%, rgba(139, 92, 246, 0.15) 0px, transparent 50%),
        radial-gradient(at 100% 100%, rgba(236, 72, 153, 0.1) 0px, transparent 50%);
      color: var(--text);
      font-family: 'Plus Jakarta Sans', sans-serif;
      min-height: 100vh;
      padding-bottom: 60px;
    }
    .header {
      background: rgba(11, 7, 22, 0.85);
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
      background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.25rem;
      font-weight: 800;
      box-shadow: 0 4px 12px rgba(139, 92, 246, 0.4);
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
      background: linear-gradient(135deg, #fff 40%, #c084fc 100%);
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
      border-color: rgba(139, 92, 246, 0.4);
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
      background: #06040d;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 4px 6px 4px 12px;
      align-items: center;
      margin-top: 12px;
    }
    .copy-input {
      background: transparent;
      border: none;
      color: #c084fc;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.82rem;
      flex: 1;
      outline: none;
    }
    .btn-copy {
      background: #1f143d;
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
      background: #0d091a;
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
      background: #18102e;
      padding: 4px;
    }
    .ch-name {
      font-weight: 600;
      font-size: 0.88rem;
      margin-bottom: 2px;
    }
    .ch-genre {
      font-size: 0.75rem;
      color: var(--text-dim);
    }
    .ch-id {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.7rem;
      color: #a855f7;
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
        <div class="brand-icon">Z5</div>
        <div>
          <h1 style="font-size:1.15rem; font-weight:800;">ZEE5 Live</h1>
          <span style="font-size:0.75rem; color:var(--text-dim);">On-Demand Stream Resolver</span>
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
      <h2>Live Entertainment & Regional Network</h2>
      <p>High-speed stream proxy with automated signed CDN token resolution</p>
    </div>

    <div class="stats">
      <div class="card">
        <div class="stat-label">Total Channels</div>
        <div class="stat-val">${CHANNELS.length}</div>
      </div>
      <div class="card">
        <div class="stat-label">Stream Resolver</div>
        <div class="stat-val" style="color:#a855f7;">Active</div>
        <div style="font-size:0.75rem; color:var(--text-dim); margin-top:4px;">Signed CDN Token Routing</div>
      </div>
      <div class="card">
        <div class="stat-label">Playback Protocol</div>
        <div class="stat-val" style="color:#38bdf8;">HLS / M3U8</div>
      </div>
    </div>

    <h3 style="margin-bottom:14px; font-size:1.15rem;">⚡ Endpoints & Playlists</h3>
    <div class="endpoints">
      <div class="card">
        <h4 style="font-size:0.95rem; font-weight:700;">📺 Master ZEE5 Playlist (M3U)</h4>
        <p style="font-size:0.85rem; color:var(--text-dim); margin-top:4px;">Direct M3U playlist with all ${CHANNELS.length} channels configured.</p>
        <div class="copy-box">
          <input type="text" readonly class="copy-input" id="u-m3u" value="https://${host}/playlist.m3u">
          <button class="btn-copy" onclick="copy('u-m3u')">Copy</button>
        </div>
      </div>

      <div class="card">
        <h4 style="font-size:0.95rem; font-weight:700;">📡 Stream Resolver Endpoint</h4>
        <p style="font-size:0.85rem; color:var(--text-dim); margin-top:4px;">Direct stream URL pattern for any individual channel.</p>
        <div class="copy-box">
          <input type="text" readonly class="copy-input" id="u-res" value="https://${host}/live/{channel_id}.m3u8">
          <button class="btn-copy" onclick="copy('u-res')">Copy</button>
        </div>
      </div>

      <div class="card">
        <h4 style="font-size:0.95rem; font-weight:700;">📊 Channels Catalog (JSON)</h4>
        <p style="font-size:0.85rem; color:var(--text-dim); margin-top:4px;">Machine-readable channel metadata, logos, and IDs.</p>
        <div class="copy-box">
          <input type="text" readonly class="copy-input" id="u-json" value="https://${host}/channels.json">
          <button class="btn-copy" onclick="copy('u-json')">Copy</button>
        </div>
      </div>
    </div>

    <div class="card" style="margin-bottom:36px;">
      <div class="controls">
        <h3 style="font-size:1.15rem;">📺 Live Channels Directory</h3>
        <input type="text" id="search" class="search-input" placeholder="Search by channel name, genre, or ID..." oninput="filterChannels()">
      </div>
      <div class="channels-grid" id="channels-container">
        ${CHANNELS.map(c => `
          <div class="ch-card" data-name="${(c.name || '').toLowerCase()}" data-id="${(c.id || '').toLowerCase()}" data-genre="${(c.genre || '').toLowerCase()}">
            <img src="${c.logo || 'https://www.zee5.com/favicon.ico'}" class="ch-logo" loading="lazy" onerror="this.src='https://www.zee5.com/favicon.ico'">
            <div style="flex:1; overflow:hidden;">
              <div class="ch-name" title="${c.name}">${c.name}</div>
              <div class="ch-genre">${c.genre || 'Entertainment'} • ${c.language || 'India'}</div>
              <div class="ch-id">${c.id}</div>
            </div>
          </div>
        `).join('')}
      </div>
    </div>

    <footer>ZEE5 Live Stream Engine • Community IPTV Hub</footer>
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
        const id = card.getAttribute('data-id');
        const genre = card.getAttribute('data-genre');
        if (name.includes(q) || id.includes(q) || genre.includes(q)) {
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

function buildPlaylist(host) {
  const lines = [
    "#EXTM3U",
    `# Total Channels: ${CHANNELS.length}`,
    `# Source: https://${host}`,
    ""
  ];

  for (const ch of CHANNELS) {
    const cid = (ch.id || "").trim();
    const name = (ch.name || "").trim();
    const logo = (ch.logo || "").trim();
    const genre = (ch.genre || "Entertainment").trim();
    const group = (ch.group || "ZEE5 India").trim();
    if (!cid || !name) continue;

    lines.push(
      `#EXTINF:-1 tvg-id="${cid}" tvg-name="${name}" tvg-logo="${logo}" tvg-category="${genre}" group-title="${group}" group-logo="https://upload.wikimedia.org/wikipedia/commons/5/5a/Zee5-official-logo.jpeg",${name}`
    );
    lines.push(`#EXTVLCOPT:http-user-agent=${USER_AGENT}`);
    lines.push(`https://${host}/live/${cid}.m3u8`);
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

    if (path === "/") {
      if (accept.includes("text/html")) {
        return new Response(renderDashboard(host), {
          headers: {
            ...CORS,
            "Content-Type": "text/html; charset=utf-8",
            "Cache-Control": "public, max-age=60",
          },
        });
      }
      return new Response(buildPlaylist(host), {
        headers: {
          ...CORS,
          "Content-Type": "application/vnd.apple.mpegurl",
          "Content-Disposition": 'inline; filename="zee5.m3u"',
          "Cache-Control": "public, max-age=300",
        },
      });
    }

    if (path === "/playlist.m3u" || path === "/live.m3u") {
      return new Response(buildPlaylist(host), {
        headers: {
          ...CORS,
          "Content-Type": "application/vnd.apple.mpegurl",
          "Content-Disposition": 'inline; filename="zee5.m3u"',
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

    if (path === "/status" || path === "/health") {
      return Response.json({
        ok: true,
        service: "zee-worker",
        clean_url: `https://${host}`,
        channels: CHANNELS.length,
        status: "active",
        timestamp: new Date().toISOString()
      }, { headers: CORS });
    }

    // Handle channel stream resolution: /live/:id or /live/:id.m3u8 or /:id.m3u8
    const match = path.match(/(?:^\/live\/|^\/)([0-9a-zA-Z\-_]+)(?:\.m3u8)?$/);
    if (!match) {
      return new Response("Invalid channel path. Use /live/:channel_id.m3u8\n", { status: 400, headers: CORS });
    }

    const channelId = match[1];
    const targetUrl = `${UPSTREAM_BASE}/${channelId}.m3u8`;

    try {
      const upstreamRes = await fetch(targetUrl, {
        method: "GET",
        headers: {
          "User-Agent": USER_AGENT,
        },
        redirect: "manual",
      });

      const location = upstreamRes.headers.get("location");
      if (location && (upstreamRes.status === 302 || upstreamRes.status === 301)) {
        return new Response(null, {
          status: 302,
          headers: {
            ...CORS,
            "Location": location,
            "Cache-Control": "no-store, no-cache, must-revalidate",
          },
        });
      }

      const body = await upstreamRes.arrayBuffer();
      const headers = new Headers(upstreamRes.headers);
      for (const [k, v] of Object.entries(CORS)) {
        headers.set(k, v);
      }
      headers.set("Cache-Control", "no-store");
      return new Response(body, {
        status: upstreamRes.status,
        headers,
      });

    } catch (err) {
      return new Response(`Error resolving stream: ${err.message}\n`, {
        status: 502,
        headers: CORS,
      });
    }
  },
};
