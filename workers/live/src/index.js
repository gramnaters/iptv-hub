/**
 * Live IPTV Playlist Cloudflare Worker
 * 
 * Free, serverless, 24/7 edge-hosted playlist endpoint (like PremiumPlug).
 * Serves master Combined.m3u with edge caching and automatic token self-healing.
 */

const GITHUB_PLAYLIST = "https://raw.githubusercontent.com/gramnaters/iptv-hub/main/Combined.m3u";
// Self-hosted autonomous token source from our own jtv worker (zero third-party dependency)
const LIVE_TOKEN_URL = "https://jtv.gramnaters.workers.dev/playlist.m3u";

// Extract expiry seconds from an __hdnea__ or hdntl cookie
function getExpiry(str) {
  const m = str && str.match(/~?exp=(\d+)/);
  return m ? parseInt(m[1], 10) : 0;
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const pathname = url.pathname;

    // Handle health check
    if (pathname === "/health") {
      return new Response(JSON.stringify({ status: "ok", time: new Date().toISOString() }), {
        headers: { "Content-Type": "application/json" }
      });
    }

    // 1. Fetch the master playlist from repository (cached for 5 minutes)
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

    // 2. Self-healing check: check if the JioTV token in the playlist has expired
    const tokenMatch = playlistText.match(/__hdnea__=st=\d+~exp=(\d+)~acl=[^~"\r\n\s]+~hmac=[a-f0-9]+/);
    const nowSec = Math.floor(Date.now() / 1000);

    if (tokenMatch) {
      const expSec = parseInt(tokenMatch[1], 10);
      // If token is expiring within 30 minutes, dynamically fetch a live token and patch
      if (expSec - nowSec < 1800) {
        try {
          const freshResp = await fetch(LIVE_TOKEN_URL, {
            headers: { "User-Agent": "Mozilla/5.0" },
            cf: { cacheTtl: 60 }
          });
          if (freshResp.ok) {
            const freshText = await freshResp.text();
            const freshMatch = freshText.match(/(__hdnea__=st=\d+~exp=\d+~acl=\/\*~hmac=[a-f0-9]+)/);
            if (freshMatch) {
              const freshToken = freshMatch[1];
              // Replace all old __hdnea__ tokens with fresh token
              playlistText = playlistText.replace(/__hdnea__=st=\d+~exp=\d+~acl=[^~"'\r\n\s&]+~hmac=[a-f0-9]+/g, freshToken);
            }
          }
        } catch (e) {
          // Non-fatal, serve what we have
        }
      }
    }

    const resp = new Response(playlistText, {
      status: 200,
      headers: {
        "Content-Type": "application/vnd.apple.mpegurl; charset=utf-8",
        "Content-Disposition": 'inline; filename="Combined.m3u"',
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
        "Cache-Control": "public, max-age=300",
        "X-Playlist-Updated": new Date().toISOString()
      }
    });

    // Store in Cloudflare edge cache for 5 minutes
    ctx.waitUntil(cache.put(cacheKey, resp.clone()));

    return resp;
  }
};
