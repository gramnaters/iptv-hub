const USER_AGENT = "com.graymatrix.did;Android TV;5.82.6(203230929);Android(10);Xiaomi(Redmi Note 8 Pro)";
const UPSTREAM_BASE = "http://premiumplug.fun/tee/zee5.php";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
  "Access-Control-Allow-Headers": "*",
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS });
    }

    if (path === "/" || path === "/status") {
      return Response.json({
        ok: true,
        service: "zee-worker",
        clean_url: "https://zee.gramnaters.workers.dev",
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
      // Fetch upstream redirect without auto-following to capture the signed CDN token
      const upstreamRes = await fetch(targetUrl, {
        method: "GET",
        headers: {
          "User-Agent": USER_AGENT,
        },
        redirect: "manual",
      });

      // If upstream returns a 302 redirect with signed token location
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

      // If upstream returned content directly, pipe it
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
