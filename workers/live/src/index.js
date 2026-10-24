const GITHUB_PLAYLIST = "https://raw.githubusercontent.com/gramnaters/iptv-hub/main/Combined.m3u";
const LIVE_TOKEN_URL = "https://jtv.gramnaters.workers.dev/playlist.m3u";

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const pathname = url.pathname.replace(/\/+$/, "") || "/";

    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
          "Access-Control-Allow-Headers": "*"
        }
      });
    }

    // Health check
    if (pathname === "/health" || pathname === "/status") {
      return Response.json({
        status: "healthy",
        uptime: "continuous",
        service: "live",
        master_playlist: `https://${url.host}/playlist.m3u`,
        sources: [
          "JioTV (1,175 chs)",
          "JioHotstar (146 chs)",
          "ZEE5 (118 chs)",
          "SonyLIV (22 chs)",
          "SunNXT (34 chs)",
          "VZY (48 chs)",
          "Kids & Free (39 chs)",
          "Live Sports (FanCode, Willow, Prime)"
        ],
        timestamp: new Date().toISOString()
      }, {
        headers: { "Access-Control-Allow-Origin": "*" }
      });
    }

    // Serve master Combined.m3u with edge caching and token self-healing
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
      return new Response("Error fetching master playlist\n", { status: 502 });
    }

    let playlistText = await upstream.text();

    // Check if the JioTV token in the playlist has expired
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
