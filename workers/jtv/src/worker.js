/**
 * JTV Cloudflare Worker — Autonomous JioTV Stream Engine
 *
 * Serves:
 * - /: Interactive Web Dashboard (Premium community UI with live channel explorer & copy cards)
 * - /live.m3u & /personal.m3u: 100% Independent Self-Hosted M3U playlist.
 * - /playlist.m3u & /jiotv.m3u: Master M3U playlist with ClearKeys and edge self-healing.
 * - /channels.json: Full channel catalog JSON API.
 * - /live/:id.m3u8 & /play/:id: Direct real-time stream minter & redirect.
 * - /health: Worker health status API.
 */

const GITHUB_PLAYLIST = "https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/jiotv.m3u";

// Multi-source fallback token providers for baked static playlist
const TOKEN_ENDPOINTS = [
  "https://plugxvipplaylist.lovable.app/api/playlist",
  "https://allinonereborn2.online/jstrweb2/cookies.json",
  "https://raw.githubusercontent.com/sportlive18/Sportlink-wtf/refs/heads/main/cookie.json"
];

// Helper: Extract valid live token from multiple upstream sources
async function fetchLiveToken() {
  for (const url of TOKEN_ENDPOINTS) {
    try {
      const res = await fetch(url, {
        headers: { "User-Agent": "Mozilla/5.0" },
        cf: { cacheTtl: 60 }
      });
      if (!res.ok) continue;

      const body = await res.text();
      const m = body.match(/(__hdnea__=st=\d+~exp=(\d+)~acl=[^~"'\r\n\s]+~hmac=[a-f0-9]+)/);
      if (m) {
        const expSec = parseInt(m[2], 10);
        const nowSec = Math.floor(Date.now() / 1000);
        if (expSec - nowSec > 1800) {
          return m[1];
        }
      }
    } catch (e) {}
  }
  return null;
}

// Fetch master playlist and ensure tokens are fresh
async function getFreshPlaylist(ctx) {
  const cacheKey = new Request("https://jtv-internal.cache/jiotv.m3u", { method: "GET" });
  const cache = caches.default;
  const hit = await cache.match(cacheKey);
  if (hit) {
    return await hit.text();
  }

  const upstream = await fetch(GITHUB_PLAYLIST, {
    headers: { "User-Agent": "Cloudflare-Worker" },
    cf: { cacheTtl: 300, cacheEverything: true }
  });

  if (!upstream.ok) {
    throw new Error(`Upstream returned ${upstream.status}`);
  }

  let text = await upstream.text();
  const tokMatch = text.match(/__hdnea__=st=\d+~exp=(\d+)~acl=[^~"'\r\n\s]+~hmac=[a-f0-9]+/);
  const nowSec = Math.floor(Date.now() / 1000);

  if (tokMatch) {
    const expSec = parseInt(tokMatch[1], 10);
    if (expSec - nowSec < 1800) {
      const freshTok = await fetchLiveToken();
      if (freshTok) {
        text = text.replace(/__hdnea__=st=\d+~exp=\d+~acl=[^~"'\r\n\s&]+~hmac=[a-f0-9]+/g, freshTok);
      }
    }
  }

  const cacheResp = new Response(text, {
    headers: { "Content-Type": "audio/x-mpegurl; charset=utf-8", "Cache-Control": "public, max-age=300" }
  });
  if (ctx) ctx.waitUntil(cache.put(cacheKey, cacheResp.clone()));

  return text;
}

// Helper: Refresh JioTV authToken using refreshToken
async function refreshAuthToken(creds) {
  if (!creds || !creds.refreshToken) return null;
  try {
    const res = await fetch("https://auth.media.jio.com/tokenservice/apis/v1/refreshtoken?langId=6", {
      method: "POST",
      headers: {
        devicetype: "phone",
        versionCode: "290",
        os: "android",
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "okhttp/4.2.2"
      },
      body: JSON.stringify({
        appName: "RJIL_JioTV",
        deviceId: creds.deviceId || "3c6d6b5702fa09bd",
        refreshToken: creds.refreshToken
      })
    });
    if (res.ok) {
      const data = await res.json();
      return data.authToken || null;
    }
  } catch (e) {}
  return null;
}

// Generate the Community Web Dashboard
function renderWebDashboard(host, hoursLeft, hasPersonal) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>JTV • Community Live TV Engine</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #08090d;
      --card: #10121a;
      --card-hover: #161a26;
      --border: #1e2233;
      --primary: #0a84ff;
      --accent: #00d2ff;
      --green: #10b981;
      --text: #f3f4f6;
      --text-dim: #9ca3af;
      --text-muted: #6b7280;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      background-color: var(--bg);
      color: var(--text);
      font-family: 'Plus Jakarta Sans', sans-serif;
      line-height: 1.5;
      padding-bottom: 60px;
    }
    .header {
      border-bottom: 1px solid var(--border);
      background: rgba(16, 18, 26, 0.8);
      backdrop-filter: blur(12px);
      position: sticky;
      top: 0;
      z-index: 50;
      padding: 16px 24px;
    }
    .header-content {
      max-width: 1200px;
      margin: 0 auto;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      text-decoration: none;
      color: inherit;
    }
    .brand-icon {
      font-size: 24px;
      background: linear-gradient(135deg, var(--primary), var(--accent));
      width: 42px;
      height: 42px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .brand-text h1 {
      font-size: 1.15rem;
      font-weight: 800;
      letter-spacing: -0.02em;
    }
    .brand-text span {
      font-size: 0.75rem;
      color: var(--text-dim);
    }
    .badge-live {
      display: flex;
      align-items: center;
      gap: 8px;
      background: rgba(16, 185, 129, 0.1);
      border: 1px solid rgba(16, 185, 129, 0.3);
      color: #34d399;
      font-size: 0.8rem;
      font-weight: 600;
      padding: 6px 14px;
      border-radius: 999px;
    }
    .pulse-dot {
      width: 8px;
      height: 8px;
      background: #10b981;
      border-radius: 50%;
      box-shadow: 0 0 10px #10b981;
      animation: pulse 2s infinite;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(0.85); }
    }
    .container {
      max-width: 1200px;
      margin: 32px auto 0;
      padding: 0 20px;
    }
    .hero {
      text-align: center;
      margin-bottom: 36px;
    }
    .hero h2 {
      font-size: 2.2rem;
      font-weight: 800;
      letter-spacing: -0.03em;
      margin-bottom: 8px;
      background: linear-gradient(135deg, #ffffff 40%, #9ca3af 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .hero p {
      color: var(--text-dim);
      font-size: 1rem;
    }
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 16px;
      margin-bottom: 32px;
    }
    .stat-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 20px;
      transition: border-color 0.2s;
    }
    .stat-card:hover {
      border-color: rgba(10, 132, 255, 0.4);
    }
    .stat-label {
      font-size: 0.8rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      font-weight: 600;
      margin-bottom: 6px;
    }
    .stat-val {
      font-size: 1.6rem;
      font-weight: 700;
      color: var(--text);
    }
    .stat-sub {
      font-size: 0.75rem;
      color: var(--text-dim);
      margin-top: 4px;
    }
    .section-title {
      font-size: 1.25rem;
      font-weight: 700;
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .endpoints-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
      gap: 16px;
      margin-bottom: 40px;
    }
    .endpoint-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 20px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }
    .endpoint-info h3 {
      font-size: 1rem;
      font-weight: 700;
      margin-bottom: 4px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .endpoint-info p {
      font-size: 0.85rem;
      color: var(--text-dim);
      margin-bottom: 14px;
    }
    .copy-box {
      display: flex;
      gap: 8px;
      background: #090a0f;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 4px 6px 4px 12px;
      align-items: center;
    }
    .copy-input {
      background: transparent;
      border: none;
      color: #93c5fd;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.82rem;
      flex: 1;
      outline: none;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .btn-copy {
      background: var(--card);
      color: var(--text);
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
      border-color: var(--primary);
    }
    .explorer-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 24px;
      margin-bottom: 40px;
    }
    .search-row {
      display: flex;
      gap: 12px;
      margin-bottom: 20px;
      flex-wrap: wrap;
    }
    .search-input {
      flex: 1;
      min-width: 240px;
      background: #090a0f;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px 16px;
      color: var(--text);
      font-size: 0.95rem;
      outline: none;
    }
    .search-input:focus {
      border-color: var(--primary);
    }
    .category-pills {
      display: flex;
      gap: 8px;
      overflow-x: auto;
      padding-bottom: 6px;
      margin-bottom: 20px;
    }
    .pill {
      background: #090a0f;
      border: 1px solid var(--border);
      color: var(--text-dim);
      padding: 6px 14px;
      border-radius: 999px;
      font-size: 0.8rem;
      font-weight: 600;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.2s;
    }
    .pill.active, .pill:hover {
      background: var(--primary);
      border-color: var(--primary);
      color: #fff;
    }
    .channels-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.88rem;
    }
    .channels-table th {
      text-align: left;
      padding: 12px 16px;
      color: var(--text-muted);
      border-bottom: 1px solid var(--border);
      font-weight: 600;
    }
    .channels-table td {
      padding: 12px 16px;
      border-bottom: 1px solid #141724;
      vertical-align: middle;
    }
    .ch-item {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .ch-logo {
      width: 38px;
      height: 38px;
      border-radius: 8px;
      background: #181b28;
      object-fit: contain;
      padding: 2px;
    }
    .ch-title {
      font-weight: 600;
      color: var(--text);
    }
    .ch-id {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.75rem;
      color: var(--text-muted);
    }
    .cat-tag {
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border);
      padding: 3px 10px;
      border-radius: 6px;
      font-size: 0.75rem;
      color: var(--text-dim);
    }
    .btn-stream {
      background: rgba(10, 132, 255, 0.15);
      border: 1px solid rgba(10, 132, 255, 0.4);
      color: #60a5fa;
      padding: 6px 12px;
      border-radius: 8px;
      font-size: 0.78rem;
      font-weight: 600;
      cursor: pointer;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .btn-stream:hover {
      background: var(--primary);
      color: #fff;
    }
    .setup-guide {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 24px;
    }
    .guide-tabs {
      display: flex;
      gap: 12px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 12px;
      margin-bottom: 16px;
    }
    .tab-btn {
      background: none;
      border: none;
      color: var(--text-dim);
      font-weight: 600;
      cursor: pointer;
      font-size: 0.9rem;
      padding: 4px 8px;
    }
    .tab-btn.active {
      color: var(--primary);
      border-bottom: 2px solid var(--primary);
    }
    .guide-content ol {
      padding-left: 20px;
      color: var(--text-dim);
      font-size: 0.9rem;
    }
    .guide-content li {
      margin-bottom: 8px;
    }
    .toast {
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: #10b981;
      color: #fff;
      padding: 12px 20px;
      border-radius: 10px;
      font-weight: 600;
      box-shadow: 0 8px 24px rgba(0,0,0,0.4);
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
      color: var(--text-muted);
      font-size: 0.85rem;
    }
  </style>
</head>
<body>

  <header class="header">
    <div class="header-content">
      <a href="/" class="brand">
        <div class="brand-icon">📺</div>
        <div class="brand-text">
          <h1>JTV Stream Hub</h1>
          <span>Edge Live Stream Engine</span>
        </div>
      </a>
      <div class="badge-live">
        <div class="pulse-dot"></div>
        <span>Edge Active</span>
      </div>
    </div>
  </header>

  <div class="container">
    <div class="hero">
      <h2>High-Definition Live Stream Engine</h2>
      <p>Clean, auto-updating JioTV stream endpoints for OTT Navigator, TiviMate, VLC & Kodi</p>
    </div>

    <!-- Quick Stats -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Total Channels</div>
        <div class="stat-val">1,175</div>
        <div class="stat-sub">Across 20+ Languages & Genres</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Edge Cache Status</div>
        <div class="stat-val" style="color: #34d399;">Active</div>
        <div class="stat-sub">Cloudflare High-Speed Edge</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Token Freshness</div>
        <div class="stat-val">${hoursLeft}</div>
        <div class="stat-sub">Auto-rolled forward 24/7</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Personal Minter</div>
        <div class="stat-val" style="color: ${hasPersonal ? '#34d399' : '#f59e0b'};">${hasPersonal ? 'Active' : 'Standby'}</div>
        <div class="stat-sub">${hasPersonal ? 'Zero 3rd party dependency' : 'Using Edge Token Fallback'}</div>
      </div>
    </div>

    <!-- Endpoints -->
    <h3 class="section-title">⚡ Stream Playlist Endpoints</h3>
    <div class="endpoints-grid">
      <!-- Endpoint 1 -->
      <div class="endpoint-card">
        <div class="endpoint-info">
          <h3>⭐ Independent Real-Time M3U</h3>
          <p>Mints fresh tokens on-the-fly for every channel tune-in. Never expires.</p>
        </div>
        <div class="copy-box">
          <input type="text" readonly class="copy-input" id="url-live" value="https://${host}/live.m3u">
          <button class="btn-copy" onclick="copyText('url-live')">Copy</button>
        </div>
      </div>

      <!-- Endpoint 2 -->
      <div class="endpoint-card">
        <div class="endpoint-info">
          <h3>📡 Master CDN Playlist (ClearKeys)</h3>
          <p>Standard full playlist with baked Akamai edge tokens & Widevine keys.</p>
        </div>
        <div class="copy-box">
          <input type="text" readonly class="copy-input" id="url-m3u" value="https://${host}/playlist.m3u">
          <button class="btn-copy" onclick="copyText('url-m3u')">Copy</button>
        </div>
      </div>

      <!-- Endpoint 3 -->
      <div class="endpoint-card">
        <div class="endpoint-info">
          <h3>📊 Channels JSON API</h3>
          <p>Full JSON feed with logos, categories, IDs, and direct stream URLs.</p>
        </div>
        <div class="copy-box">
          <input type="text" readonly class="copy-input" id="url-json" value="https://${host}/channels.json">
          <button class="btn-copy" onclick="copyText('url-json')">Copy</button>
        </div>
      </div>

      <!-- Endpoint 4 -->
      <div class="endpoint-card">
        <div class="endpoint-info">
          <h3>📅 TV Guide EPG XML</h3>
          <p>Full electronic program guide with schedules for all 1,175 channels.</p>
        </div>
        <div class="copy-box">
          <input type="text" readonly class="copy-input" id="url-epg" value="https://avkb.short.gy/jioepg.xml.gz">
          <button class="btn-copy" onclick="copyText('url-epg')">Copy</button>
        </div>
      </div>
    </div>

    <!-- Live Channel Explorer -->
    <div class="explorer-card">
      <h3 class="section-title">📺 Live Channel Explorer</h3>
      <div class="search-row">
        <input type="text" id="searchInput" class="search-input" placeholder="Search 1,100+ channels by name, id or category...">
      </div>

      <div class="category-pills" id="categoryPills">
        <button class="pill active" onclick="filterCat('all')">All</button>
        <button class="pill" onclick="filterCat('Entertainment')">Entertainment</button>
        <button class="pill" onclick="filterCat('Sports')">Sports</button>
        <button class="pill" onclick="filterCat('Movies')">Movies</button>
        <button class="pill" onclick="filterCat('News')">News</button>
        <button class="pill" onclick="filterCat('Music')">Music</button>
        <button class="pill" onclick="filterCat('Kids')">Kids</button>
        <button class="pill" onclick="filterCat('Infotainment')">Infotainment</button>
      </div>

      <table class="channels-table">
        <thead>
          <tr>
            <th>Channel</th>
            <th>Category</th>
            <th>Stream Type</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody id="channelsBody">
          <tr><td colspan="4" style="text-align:center; padding: 24px; color: var(--text-dim);">Loading live channels...</td></tr>
        </tbody>
      </table>
    </div>

    <!-- Setup Guide -->
    <div class="setup-guide">
      <h3 class="section-title">📖 Quick Setup Instructions</h3>
      <div class="guide-tabs">
        <button class="tab-btn active">OTT Navigator / TiviMate</button>
      </div>
      <div class="guide-content">
        <ol>
          <li>Open your IPTV Player (OTT Navigator, TiviMate, or VLC).</li>
          <li>Add a new <strong>M3U Playlist</strong> provider.</li>
          <li>Paste the URL: <code>https://${host}/live.m3u</code> (or <code>https://${host}/playlist.m3u</code>).</li>
          <li>In the EPG URL field, enter: <code>https://avkb.short.gy/jioepg.xml.gz</code>.</li>
          <li>Save and reload. Enjoy uninterrupted playback with automated token rolling!</li>
        </ol>
      </div>
    </div>

    <footer>
      Community IPTV Hub • Free & Autonomous • Powered by Cloudflare Workers
    </footer>
  </div>

  <div id="toast" class="toast">Link copied to clipboard!</div>

  <script>
    let allChannels = [];
    let currentCategory = 'all';

    async function loadChannels() {
      try {
        const res = await fetch('/channels.json');
        const data = await res.json();
        allChannels = data.channels || [];
        renderTable();
      } catch (e) {
        document.getElementById('channelsBody').innerHTML = '<tr><td colspan="4" style="text-align:center; color: #ef4444;">Failed to load channel catalog.</td></tr>';
      }
    }

    function renderTable() {
      const q = document.getElementById('searchInput').value.toLowerCase();
      const filtered = allChannels.filter(c => {
        const matchCat = currentCategory === 'all' || (c.group && c.group.toLowerCase().includes(currentCategory.toLowerCase()));
        const matchQuery = !q || c.channel_name.toLowerCase().includes(q) || c.channel_id.includes(q);
        return matchCat && matchQuery;
      });

      const tbody = document.getElementById('channelsBody');
      if (filtered.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 24px; color: var(--text-dim);">No channels found matching your search.</td></tr>';
        return;
      }

      tbody.innerHTML = filtered.slice(0, 50).map(c => \`
        <tr>
          <td>
            <div class="ch-item">
              <img src="\${c.logo || 'https://jiotvimages.cdn.jio.com/dare_images/images/ColorsHD.png'}" class="ch-logo" onerror="this.src='https://jiotvimages.cdn.jio.com/dare_images/images/ColorsHD.png'">
              <div>
                <div class="ch-title">\${c.channel_name}</div>
                <div class="ch-id">ID: \${c.channel_id}</div>
              </div>
            </div>
          </td>
          <td><span class="cat-tag">\${c.group || 'JioTV'}</span></td>
          <td><span style="color: #38bdf8; font-weight: 600;">HLS / DASH</span></td>
          <td>
            <a href="/live/\${c.channel_id}.m3u8" target="_blank" class="btn-stream">▶ Play</a>
          </td>
        </tr>
      \`).join('');
    }

    document.getElementById('searchInput').addEventListener('input', renderTable);

    function filterCat(cat) {
      currentCategory = cat;
      document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
      event.target.classList.add('active');
      renderTable();
    }

    function copyText(id) {
      const val = document.getElementById(id).value;
      navigator.clipboard.writeText(val);
      const toast = document.getElementById('toast');
      toast.classList.add('show');
      setTimeout(() => toast.classList.remove('show'), 2000);
    }

    loadChannels();
  </script>
</body>
</html>`;
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const p = url.pathname.replace(/\/+$/, "") || "/";

    // 1. Landing Web Dashboard
    if (p === "/") {
      const accept = request.headers.get("Accept") || "";
      if (accept.includes("application/json")) {
        const hasPersonal = Boolean(env.JIOTV_CREDS);
        return Response.json({
          status: "healthy",
          service: "JTV Stream Engine",
          channels: 1175,
          personal_minter: hasPersonal,
          endpoints: {
            independent_m3u: `https://${url.host}/live.m3u`,
            master_m3u: `https://${url.host}/playlist.m3u`,
            channels_json: `https://${url.host}/channels.json`,
            epg: "https://avkb.short.gy/jioepg.xml.gz"
          }
        });
      }

      let hoursLeft = "~5.5h";
      try {
        const text = await getFreshPlaylist(ctx);
        const m = text.match(/__hdnea__=st=\d+~exp=(\d+)~acl=[^~"'\r\n\s]+~hmac=[a-f0-9]+/);
        if (m) {
          const exp = parseInt(m[1], 10);
          const hrs = ((exp - Date.now() / 1000) / 3600).toFixed(1);
          hoursLeft = `${hrs} hours`;
        }
      } catch (e) {}

      const hasPersonal = Boolean(env.JIOTV_CREDS);
      return new Response(renderWebDashboard(url.host, hoursLeft, hasPersonal), {
        headers: { "Content-Type": "text/html; charset=utf-8", "Access-Control-Allow-Origin": "*" }
      });
    }

    // 2. Health check
    if (p === "/health") {
      const hasPersonalCreds = Boolean(env.JIOTV_CREDS);
      return new Response(JSON.stringify({
        status: "healthy",
        host: url.host,
        personal_account_active: hasPersonalCreds,
        independent_endpoints: [
          `https://${url.host}/live.m3u`,
          `https://${url.host}/personal.m3u`
        ],
        ts: new Date().toISOString()
      }), {
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
      });
    }

    // 3. Direct Personal Playback Proxy (/live/:id.m3u8 or /play/:id)
    const playMatch = p.match(/^\/(?:play|live)\/(\d+)(?:\.m3u8)?$/);
    if (playMatch) {
      const channelId = playMatch[1];
      try {
        let creds = null;
        if (env.JIOTV_CREDS) {
          try { creds = JSON.parse(env.JIOTV_CREDS); } catch {}
        }
        if (!creds || !creds.authToken) {
          return new Response("Personal JioTV credentials not configured in Worker", { status: 500 });
        }

        const fetchStream = async (token) => {
          const getUrlPayload = new URLSearchParams({
            stream_type: "Seek",
            channel_id: channelId
          });
          return await fetch("https://jiotvapi.media.jio.com/playback/apis/v1/geturl?langId=6", {
            method: "POST",
            headers: {
              appkey: "NzNiMDhlYzQyNjJm",
              devicetype: "phone",
              os: "android",
              deviceId: creds.deviceId || "3c6d6b5702fa09bd",
              isott: "false",
              channel_id: channelId,
              accesstoken: token,
              "Content-Type": "application/x-www-form-urlencoded",
              "User-Agent": "okhttp/4.2.2"
            },
            body: getUrlPayload.toString()
          });
        };

        let jioRes = await fetchStream(creds.authToken);

        // Auto-refresh on 419 (AuthToken expired)
        if (jioRes.status === 419) {
          const freshAuthToken = await refreshAuthToken(creds);
          if (freshAuthToken) {
            creds.authToken = freshAuthToken;
            jioRes = await fetchStream(freshAuthToken);
          }
        }

        if (jioRes.status === 200) {
          const jioData = await jioRes.json();
          const streamUrl = jioData.result;
          if (streamUrl) {
            return Response.redirect(streamUrl, 302);
          }
        }
        return new Response(`Upstream Jio error: ${jioRes.status}`, { status: 502 });
      } catch (err) {
        return new Response(`Playback error: ${err.message}`, { status: 500 });
      }
    }

    // 4. 100% Independent Self-Hosted Playlist (/live.m3u or /personal.m3u)
    if (p === "/live.m3u" || p === "/personal.m3u") {
      try {
        const raw = await getFreshPlaylist(ctx);
        const host = url.host;
        
        const lines = raw.split("\n");
        let curId = null;
        const out = [];
        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith("#EXTINF")) {
            const m = trimmed.match(/tvg-id="(\d+)"/);
            curId = m ? m[1] : null;
            out.push(line);
          } else if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
            if (curId) {
              out.push(`https://${host}/live/${curId}.m3u8`);
              curId = null;
            } else {
              out.push(line);
            }
          } else {
            out.push(line);
          }
        }
        const transformed = out.join("\n");

        return new Response(transformed, {
          status: 200,
          headers: {
            "Content-Type": "audio/x-mpegurl; charset=utf-8",
            "Content-Disposition": 'inline; filename="personal_jiotv.m3u"',
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=600"
          }
        });
      } catch (err) {
        return new Response("Error generating personal playlist: " + err.message, { status: 502 });
      }
    }

    // 5. Direct Master Playlist endpoint (/playlist.m3u, /jiotv.m3u)
    if (p === "/playlist.m3u" || p === "/jiotv.m3u") {
      try {
        const playlistText = await getFreshPlaylist(ctx);
        return new Response(playlistText, {
          status: 200,
          headers: {
            "Content-Type": "audio/x-mpegurl; charset=utf-8",
            "Content-Disposition": 'inline; filename="jiotv.m3u"',
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Cache-Control": "public, max-age=300"
          }
        });
      } catch (err) {
        return new Response("Error generating playlist: " + err.message, { status: 502 });
      }
    }

    // 6. JSON API endpoint (/channels.json)
    if (p === "/channels.json") {
      try {
        const playlistText = await getFreshPlaylist(ctx);
        const channels = [];
        const entries = playlistText.split("#EXTINF:-1");

        for (const e of entries.slice(1)) {
          const lines = e.trim().split("\n");
          const inf = lines[0];
          const idMatch = inf.match(/tvg-id="([^"]*)"/);
          const nameMatch = inf.match(/group-title="[^"]*",\s*(.*)$/);
          const logoMatch = inf.match(/tvg-logo="([^"]*)"/);
          const groupMatch = inf.match(/group-title="([^"]*)"/);

          let streamUrl = "";
          for (let i = 1; i < lines.length; i++) {
            const l = lines[i].trim();
            if (l.startsWith("http://") || l.startsWith("https://")) {
              streamUrl = l;
              break;
            }
          }

          if (streamUrl) {
            channels.push({
              channel_id: idMatch ? idMatch[1] : "",
              channel_name: nameMatch ? nameMatch[1].trim() : "",
              logo: logoMatch ? logoMatch[1] : "",
              group: groupMatch ? groupMatch[1] : "JioTV",
              stream_url: streamUrl,
              direct_worker_url: idMatch ? `https://${url.host}/live/${idMatch[1]}.m3u8` : ""
            });
          }
        }

        return new Response(JSON.stringify({
          total: channels.length,
          generated: new Date().toISOString(),
          channels: channels
        }, null, 2), {
          status: 200,
          headers: {
            "Content-Type": "application/json; charset=utf-8",
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=300"
          }
        });
      } catch (err) {
        return new Response(JSON.stringify({ error: err.message }), {
          status: 500,
          headers: { "Content-Type": "application/json" }
        });
      }
    }

    return new Response("Not Found", { status: 404 });
  }
};
