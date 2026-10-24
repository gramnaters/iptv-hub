/**
 * Live IPTV Playlist Cloudflare Worker
 * 
 * Free, serverless, 24/7 edge-hosted playlist endpoint.
 * Serves master Combined.m3u with edge caching and automatic token self-healing.
 */

const GITHUB_PLAYLIST = "https://raw.githubusercontent.com/gramnaters/iptv-hub/main/Combined.m3u";
const LIVE_TOKEN_URL = "https://jtv.gramnaters.workers.dev/playlist.m3u";

// Extract expiry seconds from an __hdnea__ or hdntl cookie
function getExpiry(str) {
  const m = str && str.match(/~?exp=(\d+)/);
  return m ? parseInt(m[1], 10) : 0;
}

function renderMasterDashboard(host) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>IPTV Hub • Master Live Stream Aggregator</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #090a0f;
      --card: #12141e;
      --border: #1f2333;
      --primary: #6366f1;
      --accent: #a855f7;
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
      background: rgba(18, 20, 30, 0.85);
      backdrop-filter: blur(12px);
      position: sticky;
      top: 0;
      z-index: 50;
      padding: 16px 24px;
    }
    .header-content {
      max-width: 1100px;
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
      max-width: 1100px;
      margin: 36px auto 0;
      padding: 0 20px;
    }
    .hero {
      text-align: center;
      margin-bottom: 36px;
    }
    .hero h2 {
      font-size: 2.3rem;
      font-weight: 800;
      letter-spacing: -0.03em;
      margin-bottom: 10px;
      background: linear-gradient(135deg, #ffffff 40%, #c4b5fd 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .hero p {
      color: var(--text-dim);
      font-size: 1.05rem;
      max-width: 600px;
      margin: 0 auto;
    }
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-bottom: 36px;
    }
    .stat-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 20px;
    }
    .stat-label {
      font-size: 0.8rem;
      color: var(--text-muted);
      text-transform: uppercase;
      font-weight: 600;
      margin-bottom: 6px;
    }
    .stat-val {
      font-size: 1.7rem;
      font-weight: 800;
      color: var(--text);
    }
    .stat-sub {
      font-size: 0.75rem;
      color: var(--text-dim);
      margin-top: 4px;
    }
    .section-title {
      font-size: 1.2rem;
      font-weight: 700;
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .endpoints-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 16px;
      margin-bottom: 36px;
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
    }
    .endpoint-info p {
      font-size: 0.85rem;
      color: var(--text-dim);
      margin-bottom: 14px;
    }
    .copy-box {
      display: flex;
      gap: 8px;
      background: #07080c;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 4px 6px 4px 12px;
      align-items: center;
    }
    .copy-input {
      background: transparent;
      border: none;
      color: #c4b5fd;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.82rem;
      flex: 1;
      outline: none;
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
    .sources-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 24px;
      margin-bottom: 36px;
    }
    .sources-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 12px;
      margin-top: 16px;
    }
    .source-pill {
      background: #090a0f;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .source-name {
      font-weight: 600;
      font-size: 0.9rem;
    }
    .source-count {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.8rem;
      color: #a855f7;
      font-weight: 700;
    }
    .setup-guide {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 24px;
    }
    .setup-guide ol {
      padding-left: 20px;
      color: var(--text-dim);
      font-size: 0.9rem;
    }
    .setup-guide li {
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
        <div class="brand-icon">⭐</div>
        <div class="brand-text">
          <h1>IPTV Hub Master</h1>
          <span>Autonomous Multi-Source Aggregator</span>
        </div>
      </a>
      <div class="badge-live">
        <div class="pulse-dot"></div>
        <span>1,578+ Channels Live</span>
      </div>
    </div>
  </header>

  <div class="container">
    <div class="hero">
      <h2>Master All-In-One IPTV Stream Feed</h2>
      <p>Continuous cloud synchronization across JioTV, JioHotstar, ZEE5, SunNXT, VZY & FanCode</p>
    </div>

    <!-- Stats -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Total Channels</div>
        <div class="stat-val">1,578+</div>
        <div class="stat-sub">Fully Aggregated & Deduplicated</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Cloud Sync</div>
        <div class="stat-val" style="color: #34d399;">Active</div>
        <div class="stat-sub">Every 4 Hours via GitHub Actions</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Edge Node</div>
        <div class="stat-val" style="color: #c4b5fd;">Cloudflare</div>
        <div class="stat-sub">Global Low-Latency CDN</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">DRM / ClearKey</div>
        <div class="stat-val" style="color: #60a5fa;">Injected</div>
        <div class="stat-sub">Compatible with All Players</div>
      </div>
    </div>

    <!-- Quick Links -->
    <h3 class="section-title">⚡ Master Stream Playlist Endpoints</h3>
    <div class="endpoints-grid">
      <div class="endpoint-card">
        <div class="endpoint-info">
          <h3>⭐ Master Aggregated M3U (Cloudflare Edge)</h3>
          <p>Recommended for TV. Self-healing token rollover with 5-minute edge cache.</p>
        </div>
        <div class="copy-box">
          <input type="text" readonly class="copy-input" id="url-edge" value="https://${host}/playlist.m3u">
          <button class="btn-copy" onclick="copyText('url-edge')">Copy</button>
        </div>
      </div>

      <div class="endpoint-card">
        <div class="endpoint-info">
          <h3>🐙 Raw GitHub M3U (Direct Source)</h3>
          <p>Direct master file committed continuously by GitHub Cloud Runners.</p>
        </div>
        <div class="copy-box">
          <input type="text" readonly class="copy-input" id="url-gh" value="${GITHUB_PLAYLIST}">
          <button class="btn-copy" onclick="copyText('url-gh')">Copy</button>
        </div>
      </div>

      <div class="endpoint-card">
        <div class="endpoint-info">
          <h3>📅 Master EPG Guide XML</h3>
          <p>Full TV schedule for live sports, movies, and entertainment channels.</p>
        </div>
        <div class="copy-box">
          <input type="text" readonly class="copy-input" id="url-epg" value="https://avkb.short.gy/jioepg.xml.gz">
          <button class="btn-copy" onclick="copyText('url-epg')">Copy</button>
        </div>
      </div>
    </div>

    <!-- Integrated Providers -->
    <div class="sources-card">
      <h3 class="section-title">📡 Integrated Channel Providers</h3>
      <div class="sources-grid">
        <div class="source-pill">
          <span class="source-name">JioTV</span>
          <span class="source-count">1,175 Ch</span>
        </div>
        <div class="source-pill">
          <span class="source-name">JioHotstar</span>
          <span class="source-count">146 Ch</span>
        </div>
        <div class="source-pill">
          <span class="source-name">ZEE5 India</span>
          <span class="source-count">118 Ch</span>
        </div>
        <div class="source-pill">
          <span class="source-name">VZY Media</span>
          <span class="source-count">48 Ch</span>
        </div>
        <div class="source-pill">
          <span class="source-name">SunNXT</span>
          <span class="source-count">34 Ch</span>
        </div>
        <div class="source-pill">
          <span class="source-name">Kids 24/7</span>
          <span class="source-count">17 Ch</span>
        </div>
        <div class="source-pill">
          <span class="source-name">FanCode Live</span>
          <span class="source-count">8 Ch</span>
        </div>
        <div class="source-pill">
          <span class="source-name">Dangal Play</span>
          <span class="source-count">4 Ch</span>
        </div>
      </div>
    </div>

    <!-- Setup Guide -->
    <div class="setup-guide">
      <h3 class="section-title">📖 Setup Instructions</h3>
      <ol>
        <li>Open OTT Navigator, TiviMate, VLC, or Kodi on your Smart TV or Phone.</li>
        <li>Add a new M3U Playlist provider using URL: <code>https://${host}/playlist.m3u</code></li>
        <li>In the EPG field, enter: <code>https://avkb.short.gy/jioepg.xml.gz</code></li>
        <li>Reload playlist. Enjoy all channels in full HD!</li>
      </ol>
    </div>

    <footer>
      IPTV Hub • Community Project • Free & Autonomous
    </footer>
  </div>

  <div id="toast" class="toast">Link copied to clipboard!</div>

  <script>
    function copyText(id) {
      const val = document.getElementById(id).value;
      navigator.clipboard.writeText(val);
      const toast = document.getElementById('toast');
      toast.classList.add('show');
      setTimeout(() => toast.classList.remove('show'), 2000);
    }
  </script>
</body>
</html>`;
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const pathname = url.pathname.replace(/\/+$/, "") || "/";
    const accept = request.headers.get("Accept") || "";

    // Handle health check
    if (pathname === "/health") {
      return new Response(JSON.stringify({ status: "ok", time: new Date().toISOString() }), {
        headers: { "Content-Type": "application/json" }
      });
    }

    // Serve HTML Dashboard on root for browser visits
    if (pathname === "/" && accept.includes("text/html")) {
      return new Response(renderMasterDashboard(url.host), {
        headers: { "Content-Type": "text/html; charset=utf-8", "Access-Control-Allow-Origin": "*" }
      });
    }

    // Otherwise serve master Combined.m3u with edge caching and token rollover
    const cacheKey = new Request("https://iptv-cache.internal/Combined.m3u", { method: "GET" });
    const cache = caches.default;
    let cachedResp = await cache.match(cacheKey);

    if (cachedResp) {
      return cachedResp;
    }

    const upstream = await fetch(GITHUB_PLAYLIST, {
      headers: { "User-Agent": "Cloudflare-Worker" },
      cf: { cacheTtl: 300, cacheEverything: true }
    });

    if (!upstream.ok) {
      return new Response("Error fetching master playlist", { status: 502 });
    }

    let playlistText = await upstream.text();

    // Self-healing check: check if the JioTV token in the playlist has expired
    const tokenMatch = playlistText.match(/__hdnea__=st=\d+~exp=(\d+)~acl=[^~"\\r\\n\\s]+~hmac=[a-f0-9]+/);
    const nowSec = Math.floor(Date.now() / 1000);

    if (tokenMatch) {
      const expSec = parseInt(tokenMatch[1], 10);
      if (expSec - nowSec < 1800) {
        try {
          const liveTokenResp = await fetch(LIVE_TOKEN_URL, {
            headers: { "User-Agent": "Mozilla/5.0" },
            cf: { cacheTtl: 60 }
          });
          if (liveTokenResp.ok) {
            const liveText = await liveTokenResp.text();
            const freshMatch = liveText.match(/(__hdnea__=st=\d+~exp=\d+~acl=[^~"\\r\\n\\s&]+~hmac=[a-f0-9]+)/);
            if (freshMatch) {
              const freshToken = freshMatch[1];
              playlistText = playlistText.replace(/__hdnea__=st=\d+~exp=\d+~acl=[^~"\\r\\n\\s&]+~hmac=[a-f0-9]+/g, freshToken);
            }
          }
        } catch (e) {}
      }
    }

    const response = new Response(playlistText, {
      status: 200,
      headers: {
        "Content-Type": "audio/x-mpegurl; charset=utf-8",
        "Content-Disposition": 'inline; filename="Combined.m3u"',
        "Access-Control-Allow-Origin": "*",
        "Cache-Control": "public, max-age=300"
      }
    });

    if (ctx) ctx.waitUntil(cache.put(cacheKey, response.clone()));
    return response;
  }
};
